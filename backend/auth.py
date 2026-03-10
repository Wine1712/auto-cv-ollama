# backend/auth.py
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt  # PyJWT

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "720"))  # 12 hours


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        return False


def validate_password(password: str) -> Optional[str]:
    """
    Rules:
    - >= 8 chars
    - 1 uppercase
    - 1 lowercase
    - 1 digit
    - 1 special char
    """
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Z]", password):
        return "Password must include at least 1 uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must include at least 1 lowercase letter."
    if not re.search(r"\d", password):
        return "Password must include at least 1 number."
    if not re.search(r"[^\w\s]", password):
        return "Password must include at least 1 special character."
    return None


def generate_verify_token() -> str:
    return secrets.token_urlsafe(32)


def create_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload
    except Exception:
        return None