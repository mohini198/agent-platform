from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float,
    Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from database import Base

# =====================================================================
# 1. USER TABLE
# =====================================================================
class User(Base):
    """
    Stores one row per registered user.
    Columns:
        id               → auto-incrementing primary key
        email            → unique login identifier
        hashed_password  → bcrypt hash, never plain text
        is_active        → soft-disable accounts without deleting
        created_at       → signup timestamp
        total_tasks_run  → lifetime task counter (incremented per run)
        total_tokens_used→ lifetime token counter (for cost dashboard)
    """
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    email            = Column(String, unique=True, index=True, nullable=False)
    hashed_password  = Column(String, nullable=False)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_tasks_run  = Column(Integer, default=0)
    total_tokens_used= Column(Integer, default=0)

    # Relationship — lets you do user.task_runs to get all runs for that user
    task_runs = relationship("TaskRun", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


# =====================================================================
# 2. TASKRUN TABLE
# =====================================================================
class TaskRun(Base):
    """
    Stores one row per agent pipeline execution.
    Every time a user submits a task through the WebSocket,
    a TaskRun row is created and updated as the pipeline runs.

    Columns:
        id            → auto-incrementing primary key
        user_id       → foreign key to users.id (who ran this task)
        thread_id     → the LangGraph Redis thread_id for memory continuity
        task_prompt   → what the user asked
        final_output  → the completed draft from the Writer agent
        status        → "running" | "completed" | "failed"
        loop_count    → how many Reviewer→Planner loops occurred
        tokens_used   → total tokens consumed across all 4 agents
        cost_usd      → estimated dollar cost (tokens × price per token)
        started_at    → when the WebSocket received the task
        completed_at  → when the pipeline hit END
    """
    __tablename__ = "task_runs"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    thread_id    = Column(String, nullable=False)
    task_prompt  = Column(Text, nullable=False)
    final_output = Column(Text, nullable=True)       # Null until pipeline completes
    status       = Column(String, default="running") # "running" | "completed" | "failed"
    loop_count   = Column(Integer, default=0)
    tokens_used  = Column(Integer, default=0)
    cost_usd     = Column(Float, default=0.0)
    started_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)   # Set when status → "completed"

    # Relationship back to User
    owner = relationship("User", back_populates="task_runs")

    def __repr__(self):
        return f"<TaskRun id={self.id} user_id={self.user_id} status={self.status}>"


# =====================================================================
# 3. PYDANTIC SCHEMAS (request/response shapes for the API)
# =====================================================================
# These are NOT database tables — they define what JSON goes in/out of
# your FastAPI routes. Keep them here so everything stays in one place.

from pydantic import BaseModel, EmailStr
from typing import Optional

class UserRegisterRequest(BaseModel):
    """Body for POST /register"""
    email: EmailStr
    password: str

class UserLoginRequest(BaseModel):
    """Body for POST /login"""
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    """Response from POST /login — what the frontend receives"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str

class TaskRunResponse(BaseModel):
    """Single task run — used in GET /history"""
    id: int
    thread_id: str
    task_prompt: str
    final_output: Optional[str]
    status: str
    loop_count: int
    tokens_used: int
    cost_usd: float
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True   # Lets Pydantic read SQLAlchemy model objects directly