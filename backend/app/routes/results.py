"""Transcript, caption, summary, and evaluation API routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.app.core.database import get_db_connection
from backend.app.core.dependencies import get_current_user
from backend.app.schemas.chat_schema import VideoChatRequest, VideoChatResponse
from backend.app.schemas.result_schema import ResultResponse
from backend.app.services.result_service import get_video_result
from backend.app.services.video_chat_service import ask_video_chat_agent


router = APIRouter(prefix="/results", tags=["Results"])


@router.get("/{video_id}", response_model=ResultResponse)
def get_result(
    video_id: int,
    current_user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return get_video_result(connection, video_id, current_user)


@router.post("/{video_id}/chat", response_model=VideoChatResponse)
def chat_with_video(
    video_id: int,
    payload: VideoChatRequest,
    current_user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return ask_video_chat_agent(connection, video_id, current_user, payload.message)
