import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from sqlalchemy.orm import Session

from app_orchestrator import workflow, cost_tracker
from database import engine, get_db
from models import Base, User, TaskRun, UserRegisterRequest, TokenResponse
from auth import hash_password, verify_password, create_access_token, decode_access_token

app = FastAPI(title="Autonomous Task Automation Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(bind=engine)
REDIS_URI = os.getenv("REDIS_URL", os.getenv("REDIS_URI", "redis://localhost:6379"))

# =====================================================================
# PAUSE REGISTRY — stores asyncio Events + human decisions per thread
# =====================================================================
pending_reviews : dict  = {}   # thread_id → asyncio.Event
review_decisions: dict  = {}   # thread_id → {approved, feedback}


# =====================================================================
# AUTH ROUTES (unchanged)
# =====================================================================
@app.post("/register", status_code=201)
async def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    new_user = User(email=request.email, hashed_password=hash_password(request.password))
    db.add(new_user); db.commit(); db.refresh(new_user)
    print(f"✅ Registered: {new_user.email}")
    return {"message": "Account created successfully. You can now log in."}


@app.post("/login", response_model=TokenResponse)
async def login(request: UserRegisterRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated.")
    token = create_access_token(user_id=user.id, email=user.email)
    print(f"🔑 Login: {user.email}")
    return TokenResponse(access_token=token, token_type="bearer", user_id=user.id, email=user.email)


@app.get("/history")
async def get_history(token: str, db: Session = Depends(get_db)):
    user_data = decode_access_token(token)
    runs = (db.query(TaskRun).filter(TaskRun.user_id == user_data.user_id)
            .order_by(TaskRun.started_at.desc()).limit(50).all())
    return [{"id": r.id, "task_prompt": r.task_prompt, "status": r.status,
             "loop_count": r.loop_count, "tokens_used": r.tokens_used,
             "cost_usd": round(r.cost_usd, 6), "started_at": r.started_at.isoformat(),
             "completed_at": r.completed_at.isoformat() if r.completed_at else None}
            for r in runs]


# =====================================================================
# APPROVE ROUTE — frontend calls this when user clicks Approve/Reject
# =====================================================================
class ApprovalRequest(BaseModel):
    approved : bool
    feedback : Optional[str] = ""
    token    : str


@app.post("/approve/{thread_id}")
async def approve_task(thread_id: str, request: ApprovalRequest):
    decode_access_token(request.token)   # verify token
    if thread_id not in pending_reviews:
        raise HTTPException(status_code=404,
                            detail="No pipeline paused for this thread_id.")
    review_decisions[thread_id] = {"approved": request.approved,
                                   "feedback": request.feedback or ""}
    pending_reviews[thread_id].set()
    action = "APPROVED ✅" if request.approved else "REJECTED 🔄"
    print(f"👤 Human {action} thread={thread_id}")
    return {"message": f"Decision: {'approved' if request.approved else 'rejected'}",
            "thread_id": thread_id}


# =====================================================================
# WEBSOCKET — with breakpoint-based HITL
# =====================================================================
@app.websocket("/ws/task")
async def websocket_endpoint(websocket: WebSocket, token: str,
                              db: Session = Depends(get_db)):
    origin = websocket.headers.get("origin", "NO ORIGIN HEADER")
    print(f"🔍 WebSocket connection attempt from origin: {origin}")

    try:
        user_data = decode_access_token(token)
    except Exception as e:
        print(f"❌ Token decode failed: {type(e).__name__}: {e}")
        await websocket.close(code=1008)
        return
    user= db.query(User).filter(User.id == user_data.user_id).first()
    if not user or not user.is_active:
        await websocket.close(code=1008); return

    await websocket.accept()
    print(f"🔌 {user.email} connected.")
    task_run  = None
    thread_id = "default"

    try:
        while True:
            data        = await websocket.receive_text()
            payload     = json.loads(data)
            task_prompt = payload.get("task")
            thread_id   = payload.get("thread_id", f"user_{user.id}_session")

            cost_tracker.reset()
            task_run = TaskRun(user_id=user.id, thread_id=thread_id,
                               task_prompt=task_prompt, status="running")
            db.add(task_run); db.commit(); db.refresh(task_run)

            await websocket.send_json({"event": "status",
                "message": "🤖 System Initializing: Compiling specialized workers..."})
            await asyncio.sleep(0.5)

            async with AsyncRedisSaver.from_conn_string(REDIS_URI) as checkpointer:
                await checkpointer.asetup()

                # ── HITL: compile with breakpoint BEFORE human_review ──
                compiled_graph = workflow.compile(
                    checkpointer=checkpointer,
                    interrupt_before=["human_review"]   # pauses here automatically
                )
                config = {"configurable": {"thread_id": thread_id}}
                inputs = {
                    "task"          : task_prompt,
                    "loop_count"    : 0,
                    "review_score"  : 0,
                    "human_approved": None,
                    "human_feedback": None,
                }

                pipeline_done = False
                current_input = inputs

                while not pipeline_done:
                    interrupted = False

                    async for event in compiled_graph.astream(
                        current_input, config=config, stream_mode="updates"
                    ):
                        for node_name, output in event.items():
                            if node_name == "planner":
                                await websocket.send_json({"event": "status",
                                    "message": "🧠 Planner Agent complete. Strategy written."})
                            elif node_name == "researcher":
                                await websocket.send_json({"event": "status",
                                    "message": "🔍 Researcher Agent complete. Facts gathered."})
                            elif node_name == "writer":
                                await websocket.send_json({"event": "status",
                                    "message": "✍️ Writer Agent complete. Draft ready for review."})
                            elif node_name == "reviewer":
                                score = output.get("review_score", 0)
                                if score >= 7:
                                    await websocket.send_json({"event": "status",
                                        "message": f"🛡️ Reviewer: Score {score}/10 — APPROVED."})
                                else:
                                    await websocket.send_json({"event": "status",
                                        "message": f"⚠️ Reviewer: Score {score}/10 — REJECTED. Revising."})
                        await asyncio.sleep(0.1)

                    # ── Check if graph paused at breakpoint ────────────
                    graph_state = await compiled_graph.aget_state(config)
                    next_nodes  = graph_state.next

                    if "human_review" in next_nodes:
                        # Graph paused before human_review — get current draft
                        current_draft = graph_state.values.get("current_draft", "")
                        current_score = graph_state.values.get("review_score", 0)

                        print(f"⏸️  Paused for human review | thread={thread_id}")

                        # Send draft to frontend for human to review
                        await websocket.send_json({
                            "event"        : "human_review",
                            "thread_id"    : thread_id,
                            "current_draft": current_draft,
                            "review_score" : current_score,
                            "message"      : "✋ Pipeline paused. Please review the draft.",
                        })

                        # Register event and wait for /approve to be called
                        event_obj = asyncio.Event()
                        pending_reviews[thread_id] = event_obj

                        try:
                            await asyncio.wait_for(event_obj.wait(), timeout=600)
                        except asyncio.TimeoutError:
                            review_decisions[thread_id] = {"approved": True,
                                                           "feedback": "Auto-approved: timeout."}
                            print(f"⏱️  Timeout — auto-approving thread={thread_id}")

                        decision = review_decisions.pop(thread_id, {"approved": True, "feedback": ""})
                        pending_reviews.pop(thread_id, None)

                        await websocket.send_json({"event": "status",
                            "message": f"👤 Human {'APPROVED ✅' if decision['approved'] else 'REJECTED 🔄'} — resuming pipeline."})

                        # ── Resume: update state with human decision ───
                        await compiled_graph.aupdate_state(
                            config,
                            {
                                "human_approved": decision["approved"],
                                "human_feedback": decision["feedback"],
                            }
                        )
                        current_input = None  # use None to resume from checkpoint

                    else:
                        # No more breakpoints — pipeline finished
                        pipeline_done = True

                # Fetch final output
                final_state = await compiled_graph.aget_state(config)
                final_draft = final_state.values.get("current_draft", "No output compiled.")
                final_loops = final_state.values.get("loop_count", 0)
                final_score = final_state.values.get("review_score", 0)

            await websocket.send_json({"event": "complete", "result": final_draft})

            cost_summary           = cost_tracker.get_summary()
            task_run.status        = "completed"
            task_run.final_output  = final_draft
            task_run.loop_count    = final_loops
            task_run.tokens_used   = cost_summary["total_tokens"]
            task_run.cost_usd      = cost_summary["cost_usd"]
            task_run.completed_at  = datetime.now(timezone.utc)
            user.total_tasks_run  += 1
            user.total_tokens_used += cost_summary["total_tokens"]
            db.commit()

            print(f"✅ Task {task_run.id} | score={final_score}/10 | "
                  f"tokens={cost_summary['total_tokens']} | cost=${cost_summary['cost_usd']:.6f}")

            await websocket.send_json({"event": "cost",
                "tokens": cost_summary["total_tokens"],
                "cost_usd": cost_summary["cost_usd"]})

    except WebSocketDisconnect:
        print(f"🔌 {user.email} disconnected.")
        pending_reviews.pop(thread_id, None)

    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"❌ Error: {type(e).__name__}: {e}")
        if task_run:
            task_run.status = "failed"; db.commit()
        await websocket.send_json({"event": "error", "message": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main_api:app", host="127.0.0.1", port=8000, reload=True)