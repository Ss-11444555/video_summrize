"""Request and response schemas for processing job state."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ProcessingStatusResponse(BaseModel):
    video_id: int
    stage: str
    progress_percent: float
    status_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: str
