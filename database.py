import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# 1. DATABASE CONNECTION
# =====================================================================
# Reads DATABASE_URL from your .env file.
# Development:  sqlite:///./agent_platform.db   (zero setup, file-based)
# Production:   postgresql://user:pass@host/dbname  (swap when deploying)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agent_platform.db")

# connect_args is required for SQLite only — allows multiple threads
# (FastAPI runs async, so multiple requests hit the DB simultaneously)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,   # Set to True temporarily if you want to see raw SQL queries in terminal
)

# =====================================================================
# 2. SESSION FACTORY
# =====================================================================
# Each request gets its own database session, opened and closed cleanly.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# =====================================================================
# 3. BASE CLASS
# =====================================================================
# All your models (User, TaskRun) inherit from this.
# SQLAlchemy uses it to track which classes map to which tables.
Base = declarative_base()

# =====================================================================
# 4. get_db — FastAPI DEPENDENCY
# =====================================================================
def get_db():
    """
    Yields a database session for each request, then closes it cleanly.

    Usage in any route in main_api.py:
        from database import get_db
        from sqlalchemy.orm import Session

        @app.post("/register")
        async def register(db: Session = Depends(get_db)):
            db.add(new_user)
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()