"""Business logic for login and role handling."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from backend.app.core.database import commit_with_retry
from backend.app.core.security import create_access_token, hash_password, verify_password


SEED_ACCOUNT_PASSWORDS = {
    "admin@thinknote.ai": "Admin123!",
    "teacher@thinknote.ai": "Teacher123!",
    "student@thinknote.ai": "Student123!",
}


def _serialize_user(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
    }


def get_user_by_email(connection: sqlite3.Connection, email: str) -> Optional[Dict[str, Any]]:
    row = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    return dict(row) if row else None


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    row = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "password_hash": row["password_hash"],
        "created_at": row["created_at"],
    }


def bootstrap_seed_account_passwords(connection: sqlite3.Connection) -> None:
    rows = connection.execute("SELECT id, email, password_hash FROM users").fetchall()
    for row in rows:
        placeholder_hash = str(row["password_hash"])
        if placeholder_hash.endswith("_password_hash_here"):
            account_password = SEED_ACCOUNT_PASSWORDS.get(row["email"], "Password123!")
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(account_password), row["id"]),
            )

    commit_with_retry(connection)


def login_user(connection: sqlite3.Connection, email: str, password: str) -> Dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1",
        (email,),
    ).fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(
        {
            "sub": str(row["id"]),
            "email": row["email"],
            "role": row["role"],
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _serialize_user(row),
    }
