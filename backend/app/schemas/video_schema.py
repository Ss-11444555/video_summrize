"""Request and response schemas for video operations."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class VideoResponse(BaseModel):
    id: int
    title: str
    course_name: str
    module_week: Optional[str] = None
    description: Optional[str] = None
    source_filename: str
    stored_path: str
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    owner_id: int
    workspace_id: Optional[int] = None
    owner_name: str
    status: str
    is_published: bool
    created_at: str
    updated_at: str


class VideoUploadResponse(BaseModel):
    message: str
    video: VideoResponse


class VideoDeleteResponse(BaseModel):
    message: str
    video_id: int
    deleted_files: int
    cleanup_warnings: list[str]


class VideoAssignmentRequest(BaseModel):
    student_email: str


class VideoAssignmentResponse(BaseModel):
    message: str
    video_id: int
    student_id: int
    student_email: str


class VideoBulkAssignmentResponse(BaseModel):
    message: str
    video_id: int
    course_name: str
    assigned_count: int
    already_assigned_count: int
    total_registered_students: int
