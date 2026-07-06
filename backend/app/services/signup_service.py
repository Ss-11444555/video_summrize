"""Business logic for creating new users (signup)."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from backend.app.core.database import commit_with_retry
from backend.app.core.security import create_access_token, hash_password
from backend.app.core.dependencies import require_roles  # noqa: F401 (keeps parity with project style)


def _serialize_user_min(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
    }


def get_user_by_email_db(connection: sqlite3.Connection, email: str) -> Optional[Dict[str, Any]]:
    row = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    return dict(row) if row else None


def signup_user(
    connection: sqlite3.Connection,
    *,
    full_name: str,
    email: str,
    password: str,
    role: str,
    workspace_name: Optional[str] = None,
) -> Dict[str, Any]:
    full_name = " ".join(full_name.strip().split())
    email = email.strip().lower()
    role = role.strip().lower()

    if role not in {"teacher", "student"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only teacher and student signup are allowed.",
        )

    existing = get_user_by_email_db(connection, email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists.",
        )

    password_hash = hash_password(password)

    cursor = connection.execute(
        """
        INSERT INTO users (full_name, email, password_hash, role, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (full_name, email, password_hash, role),
    )
    user_id = cursor.lastrowid

    if role == "teacher":
        initial_workspace = " ".join((workspace_name or "My First Course").strip().split())
        connection.execute(
            """
            INSERT INTO teacher_workspaces (teacher_id, name)
            VALUES (?, ?)
            """,
            (user_id, initial_workspace),
        )
    commit_with_retry(connection)

    row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Signup succeeded but user was not found.")

    token = create_access_token({"sub": str(row["id"]), "email": row["email"], "role": row["role"]})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _serialize_user_min(row),
    }

