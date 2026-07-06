"""Request and response schemas for the student video chat agent."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class VideoChatRequest(BaseModel):
    message: str


class VideoChatResponse(BaseModel):
    answer: str
    timestamp_seconds: Optional[float] = None
    should_seek: bool = False
    evidence: Optional[str] = None
