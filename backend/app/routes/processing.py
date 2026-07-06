"""Processing status API routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.app.core.database import get_db_connection
from backend.app.core.dependencies import get_current_user
from backend.app.schemas.processing_schema import ProcessingStatusResponse
from backend.app.services.processing_service import get_processing_status
from backend.app.services.video_service import get_video_by_id


router = APIRouter(prefix="/processing", tags=["Processing"])


@router.get("/{video_id}", response_model=ProcessingStatusResponse)
def get_video_processing_status(
    video_id: int,
    current_user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    get_video_by_id(connection, video_id, current_user)
    return get_processing_status(connection, video_id)
