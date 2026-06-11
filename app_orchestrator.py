import os
from typing import Dict, Any, Optional
from typing_extensions import TypedDict
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

llm         = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)
search_tool = TavilySearch(max_results=3)

# =====================================================================
# COST TRACKER (unchanged)
# =====================================================================
INPUT_COST_PER_TOKEN  = 0.00000059
OUTPUT_COST_PER_TOKEN = 0.00000079

class CostTracker(BaseCallbackHandler):
    def __init__(self):
        self.total_input_tokens  = 0
        self.total_output_tokens = 0
        self.total_cost_usd      = 0.0
        self.call_count          = 0

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        usage         = response.llm_output.get("token_usage", {}) if response.llm_output else {}
        input_tokens  = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        self.total_input_tokens  += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd      += (input_tokens  * INPUT_COST_PER_TOKEN +
                                     output_tokens * OUTPUT_COST_PER_TOKEN)
        self.call_count += 1
        print(f"   💰 LLM call #{self.call_count} | in={input_tokens} out={output_tokens} | run cost=${self.total_cost_usd:.6f}")

    def get_summary(self) -> Dict:
        return {
            "total_tokens" : self.total_input_tokens + self.total_output_tokens,
            "input_tokens" : self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd"     : round(self.total_cost_usd, 6),
            "llm_calls"    : self.call_count,
        }

    def reset(self):
        self.total_input_tokens  = 0
        self.total_output_tokens = 0
        self.total_cost_usd      = 0.0
        self.call_count          = 0

cost_tracker = CostTracker()


# =====================================================================
# 1. SHARED STATE
# =====================================================================
class PlatformState(TypedDict):
    task            : str
    plan            : str
    research_data   : str
    current_draft   : str
    review_feedback : str
    loop_count      : int
    review_score    : int
    human_approved  : Optional[bool]   # None=pending, True=approved, False=rejected
    human_feedback  : Optional[str]    # human's note to the writer


# =====================================================================
# RETRY WRAPPER (unchanged)
# =====================================================================
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _search_with_retry(query: str) -> Any:
    print("   🔄 Calling Tavily search...")
    return search_tool.invoke({"query": query})


# =====================================================================
# 2. AGENT NODES
# =====================================================================

def planner_node(state: PlatformState) -> Dict:
    print("\n[🧠 Planner Agent] Devising Strategy...")
    prompt = f"Task: {state['task']}\nCreate a step-by-step roadmap."
    if state.get("review_feedback"):
        prompt += (
            f"\n\nPrevious AI review score: {state.get('review_score', 0)}/10"
            f"\nAI feedback: {state['review_feedback']}"
        )
    if state.get("human_approved") is False and state.get("human_feedback"):
        prompt += (
            f"\n\n⚠️ HUMAN REVIEWER REJECTED the previous draft."
            f"\nHuman feedback (fix this first):\n{state['human_feedback']}"
        )
    response = llm.invoke(prompt, config={"callbacks": [cost_tracker]})
    return {
        "plan"          : response.content,
        "loop_count"    : state.get("loop_count", 0) + 1,
        "human_approved": None,
        "human_feedback": None,
    }


def researcher_node(state: PlatformState) -> Dict:
    print("\n[🔍 Researcher Agent] Gathering Facts via Web Search...")
    try:
        results = _search_with_retry(state["task"])
    except Exception as e:
        print(f"   ❌ Tavily failed: {e}")
        results = "Web search unavailable. Use general knowledge."
    prompt = (
        f"Summarize these search results for task '{state['task']}':\n{results}"
    )
    response = llm.invoke(prompt, config={"callbacks": [cost_tracker]})
    return {"research_data": response.content}


def writer_node(state: PlatformState) -> Dict:
    print("\n[✍️ Writer Agent] Drafting Output...")
    prompt = (
        f"Write a comprehensive document for: '{state['task']}'.\n"
        f"Follow this plan: {state['plan']}\n"
        f"Use this research: {state['research_data']}"
    )
    if state.get("review_score", 0) > 0 and state.get("review_feedback"):
        prompt += (
            f"\n\nRevision loop #{state.get('loop_count', 1)}. "
            f"Previous score: {state['review_score']}/10. "
            f"Fix: {state['review_feedback']}"
        )
    response = llm.invoke(prompt, config={"callbacks": [cost_tracker]})
    return {"current_draft": response.content}


# =====================================================================
# HUMAN REVIEW NODE  — HITL via breakpoint (no interrupt() call)
# =====================================================================
# This node is a simple pass-through that reads human_approved from state.
# The actual PAUSE happens via a breakpoint set on this node when
# compiling the graph in main_api.py.
#
# How breakpoints work:
#   compiled_graph = workflow.compile(
#       checkpointer=checkpointer,
#       interrupt_before=["human_review"]   ← graph pauses BEFORE this node
#   )
#
# The graph saves state to Redis and stops. main_api.py detects the pause,
# sends the draft to the frontend, waits for POST /approve, then calls
# astream() again with updated state (human_approved + human_feedback).
# The graph resumes from human_review_node with the new values in state.
# =====================================================================
def human_review_node(state: PlatformState) -> Dict:
    """
    Reads human_approved from state (set by main_api.py before resuming).
    On first pass: human_approved is None — graph was paused before this node.
    On resume:     human_approved is True/False — set by the /approve endpoint.
    """
    approved = state.get("human_approved")
    feedback = state.get("human_feedback", "")
    print(f"\n[👤 Human Review] Decision: {'APPROVED' if approved else 'REJECTED'} | feedback='{feedback}'")
    # Just pass state through — routing happens in route_after_human
    return {}


def reviewer_node(state: PlatformState) -> Dict:
    print("\n[🛡️ Reviewer Agent] Auditing Quality with Self-Reflection...")
    prompt = (
        f"Review this draft for '{state['task']}'.\n\n"
        f"DRAFT:\n{state['current_draft']}\n\n"
        f"Score 0-10 on: accuracy(3), completeness(3), structure(2), writing(2).\n"
        f"FORMAT:\nSCORE: [0-10]\nVERDICT: [APPROVED or REJECTED]\n"
        f"FEEDBACK: [issues or 'Meets all quality standards.']\n"
        f"RULES: 7+ = APPROVED. 6 or below = REJECTED."
    )
    response      = llm.invoke(prompt, config={"callbacks": [cost_tracker]})
    feedback_text = response.content
    score = 0
    for line in feedback_text.split("\n"):
        if line.strip().upper().startswith("SCORE:"):
            try:
                score = int(line.split(":")[1].strip().split()[0])
                score = max(0, min(10, score))
            except (ValueError, IndexError):
                score = 0
            break
    verdict = "APPROVED" if score >= 7 else "REJECTED"
    print(f"   📊 Review score: {score}/10 → {verdict}")
    return {"review_feedback": feedback_text, "review_score": score}


# =====================================================================
# 3. ROUTING FUNCTIONS
# =====================================================================

def route_after_human(state: PlatformState) -> str:
    if state.get("human_approved") is True:
        print("   ✅ Human approved → routing to AI Reviewer.")
        return "go_to_reviewer"
    print("   🔄 Human rejected → routing back to Planner.")
    return "go_to_planner"


def routing_gatekeeper(state: PlatformState) -> str:
    score      = state.get("review_score", 0)
    loop_count = state.get("loop_count", 0)
    if loop_count >= 3:
        print(f"\n⚠️  Max loops reached. Force-exiting. Score: {score}/10")
        return "exit_pipeline"
    if score >= 7:
        print(f"\n✅ Score {score}/10 — APPROVED.")
        return "exit_pipeline"
    print(f"\n🔄 Score {score}/10 — REJECTED. Loop {loop_count}/3")
    return "send_to_planner"


# =====================================================================
# 4. GRAPH — compiled WITHOUT breakpoint here
#    Breakpoint is set in main_api.py at compile time:
#    workflow.compile(checkpointer=..., interrupt_before=["human_review"])
# =====================================================================
workflow = StateGraph(PlatformState)

workflow.add_node("planner",      planner_node)
workflow.add_node("researcher",   researcher_node)
workflow.add_node("writer",       writer_node)
workflow.add_node("human_review", human_review_node)
workflow.add_node("reviewer",     reviewer_node)

workflow.add_edge(START,        "planner")
workflow.add_edge("planner",    "researcher")
workflow.add_edge("researcher", "writer")
workflow.add_edge("writer",     "human_review")

workflow.add_conditional_edges(
    "human_review", route_after_human,
    {"go_to_reviewer": "reviewer", "go_to_planner": "planner"}
)
workflow.add_conditional_edges(
    "reviewer", routing_gatekeeper,
    {"send_to_planner": "planner", "exit_pipeline": END}
)