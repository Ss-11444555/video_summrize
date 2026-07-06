"""Authentication API routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.app.core.database import get_db_connection
from backend.app.core.dependencies import get_current_user
from backend.app.schemas.auth_schema import LoginRequest, TokenResponse, UserResponse
from backend.app.schemas.signup_schema import SignupRequest, SignupResponse
from backend.app.services.auth_service import login_user
from backend.app.services.signup_service import signup_user



router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, connection: sqlite3.Connection = Depends(get_db_connection)):
    return login_user(connection, payload.email, payload.password)


@router.post("/signup", response_model=SignupResponse, status_code=201)
def signup(payload: SignupRequest, connection: sqlite3.Connection = Depends(get_db_connection)):
    return signup_user(
        connection,
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        workspace_name=payload.workspace_name,
    )


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    return current_user
