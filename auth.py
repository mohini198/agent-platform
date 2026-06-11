import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv

import bcrypt  # use bcrypt directly — avoids passlib compatibility bug on Windows

load_dotenv()

# =====================================================================
# 1. CONFIGURATION
# =====================================================================
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# =====================================================================
# 2. PASSWORD HASHING — using bcrypt directly (no passlib)
# =====================================================================
def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt directly.
    Truncates to 72 bytes first to avoid the passlib/bcrypt Windows bug.
    """
    password_bytes = plain_password.encode("utf-8")[:72]  # bcrypt hard limit
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")  # store as string in DB


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against its stored bcrypt hash.
    Returns True if match, False if not.
    """
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# =====================================================================
# 3. JWT TOKEN CREATION & DECODING
# =====================================================================
class TokenData(BaseModel):
    """Data embedded inside the JWT payload."""
    user_id: int
    email: str


def create_access_token(user_id: int, email: str) -> str:
    """
    Create a signed JWT token that expires in ACCESS_TOKEN_EXPIRE_MINUTES.
    Returns the token string — send this back to the frontend on login.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    """
    Decode and validate a JWT token.
    Returns TokenData if valid.
    Raises HTTP 401 if expired or tampered.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")

        if user_id is None or email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload is malformed.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenData(user_id=int(user_id), email=email)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =====================================================================
# 4. FASTAPI DEPENDENCY — get_current_user
# =====================================================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    FastAPI dependency — inject into any HTTP route to protect it.

    Usage:
        @app.get("/me")
        async def me(user: TokenData = Depends(get_current_user)):
            return {"user_id": user.user_id, "email": user.email}

    For WebSocket — call decode_access_token(token) directly instead.
    """
    return decode_access_token(token)