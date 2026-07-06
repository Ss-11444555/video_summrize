"""Shared FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

import sqlite3
from typing import Callable

from fastapi import Depends, Header, HTTPException, Query, status

from backend.app.core.database import get_db_connection
from backend.app.core.security import decode_access_token
from backend.app.services.auth_service import get_user_by_id


def get_current_user(
    authorization: str = Header(default=""),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header.",
        )

    token = authorization.replace("Bearer ", "", 1).strip()
    payload = decode_access_token(token)
    user = get_user_by_id(connection, int(payload["sub"]))

    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return user


def get_current_user_from_header_or_query(
    authorization: str = Header(default=""),
    access_token: str = Query(default=""),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "", 1).strip()
    else:
        token = access_token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization token.",
        )

    payload = decode_access_token(token)
    user = get_user_by_id(connection, int(payload["sub"]))

    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    return user


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(current_user=Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )

        return current_user

    return dependency
