# 🤖 AGENT-OS — Autonomous Multi-Agent Task Platform

> A production-grade multi-agent AI system where specialized agents autonomously plan, research, write, and review tasks — with self-reflection scoring, human-in-the-loop approval, JWT authentication, real-time WebSocket streaming, and persistent Redis memory.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2+-purple?style=flat-square)](https://langchain-ai.github.io/langgraph)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## 🚀 Live Demo

**Backend API:** [agent-platform-production-a13b.up.railway.app/docs](https://agent-platform-production-a13b.up.railway.app/docs)  
**Frontend:** *(coming soon — deploying to Vercel next)*

---

## ✨ What This Does

Submit any task in plain English. A team of 4 specialized AI agents collaborate autonomously to complete it:

1. 🧠 **Planner** — reads your task, creates a step-by-step strategy
2. 🔍 **Researcher** — searches the live web for real-time facts (Tavily)
3. ✍️ **Writer** — combines plan + research into a full document
4. 👤 **Human Review** — pipeline pauses, you approve or reject the draft
5. 🛡️ **Reviewer** — scores the output 0–10 on 4 quality criteria
6. 🔄 **Self-Reflection** — if score below 7, loops back with specific feedback until approved

Every run streams live to your dashboard over WebSocket. Token cost tracked in real time.

---

## 🏗️ System Architecture

```
User (Next.js Dashboard)
        │
        ├── POST /register → bcrypt hash → SQLite
        ├── POST /login    → verify → JWT token
        │
        └── WebSocket /ws/task?token=xxx
                │
                ├── [Auth] JWT verified before connection accepted
                ├── [DB]   TaskRun row created (status=running)
                │
                └── LangGraph StateGraph (Redis checkpointer)
                        │
                        ├── planner_node    → writes plan to shared state
                        ├── researcher_node → Tavily search → research_data
                        ├── writer_node     → synthesizes draft
                        ├── human_review    → PAUSE (breakpoint)
                        └── reviewer_node   → scores 0-10
                                │
                                ├── score >= 7 → EXIT → send to dashboard
                                └── score < 7  → LOOP → back to planner
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **AI Orchestration** | LangGraph 1.2, LangChain |
| **LLM** | Groq Llama 3.3 70B (versatile) |
| **Web Search** | Tavily Search API |
| **Backend** | FastAPI, Uvicorn |
| **Real-time** | WebSocket (native FastAPI) |
| **Memory** | Redis (LangGraph AsyncRedisSaver) |
| **Database** | SQLite → PostgreSQL (production) |
| **Auth** | JWT (python-jose) + bcrypt |
| **Retry Logic** | Tenacity (exponential backoff) |
| **Cost Tracking** | LangChain callback (CostTracker) |
| **Frontend** | Next.js 14, Tailwind, Framer Motion |

---

## 📁 Project Structure

```
agent-platform/
├── main_api.py          # FastAPI server + WebSocket endpoint
├── app_orchestrator.py  # LangGraph StateGraph + all 4 agent nodes
├── auth.py              # JWT token creation + bcrypt password hashing
├── models.py            # SQLAlchemy User + TaskRun tables + Pydantic schemas
├── database.py          # SQLAlchemy engine + get_db dependency
├── requirements.txt     # Python dependencies
├── .env.example         # Required environment variables (template)
└── test_tier2.py        # WebSocket integration test
```

---

## ⚡ Quick Start

### Prerequisites
- Python 3.11+
- Docker (for Redis)
- API Keys: [Groq](https://console.groq.com) + [Tavily](https://tavily.com)

### 1. Clone and Setup

```bash
git clone https://github.com/mohini198/agent-platform.git
cd agent-platform
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
GROQ_API_KEY=your_groq_key_here
TAVILY_API_KEY=your_tavily_key_here
SECRET_KEY=your_64_char_secret_here
DATABASE_URL=sqlite:///./agent_platform.db
```

Generate SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Start Redis

```bash
docker run -d -p 6379:6379 --name redis-agent redis:alpine
```

### 4. Run the Server

```bash
python main_api.py
```

Server runs at `http://localhost:8000`  
API docs at `http://localhost:8000/docs`

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/register` | Create account |
| `POST` | `/login` | Get JWT token |
| `GET` | `/history?token=xxx` | Task run history |
| `POST` | `/approve/{thread_id}` | Human approval decision |
| `WS` | `/ws/task?token=xxx` | Real-time agent stream |

---

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for Llama 3.3 70B | ✅ |
| `TAVILY_API_KEY` | Tavily web search API key | ✅ |
| `SECRET_KEY` | JWT signing secret (64 chars) | ✅ |
| `DATABASE_URL` | SQLAlchemy DB URL | ✅ |

---

## 🏢 Production Architecture Comparison

This system implements the same core patterns used by:

| Company | Their System | What We Share |
|---------|-------------|---------------|
| **Salesforce** | Agentforce | Multi-agent orchestration |
| **Cognition** | Devin | Self-reflection loops |
| **Harvey AI** | Legal agents | Human-in-the-loop approval |
| **Klarna** | Support agents | WebSocket streaming |

---

## 🧠 Key Technical Decisions

**Why LangGraph over sequential chains?**  
LangGraph supports cycles — the Reviewer can loop back to the Planner. Sequential chains can't do this.

**Why WebSocket over REST?**  
Agent pipelines take 30–60 seconds. WebSocket streams each agent's status the moment it finishes instead of blocking until the end.

**Why Redis checkpointer?**  
State is saved after every node. Human-in-the-loop breakpoints work by pausing mid-graph and resuming with the human's decision injected into state.

**Why bcrypt over passlib?**  
passlib has a compatibility bug with bcrypt 4.x on Windows. Direct bcrypt usage avoids this entirely.

---

## 👤 Author

**Mohini** — AI Engineer  
GitHub: [@mohini198](https://github.com/mohini198)

---

