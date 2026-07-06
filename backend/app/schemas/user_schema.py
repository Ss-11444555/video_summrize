"""Request and response schemas for user management."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class UserListResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    created_at: str


class CourseDirectoryResponse(BaseModel):
    id: str
    course_name: str
    teacher_id: int
    teacher_name: str
    teacher_email: str
    registered: bool
    registration_status: str
    published_videos_count: int
    completed_videos_count: int
    assigned_videos_count: int
    assigned_completed_videos_count: int
    has_assigned_videos: bool


class CourseRegistrationResponse(BaseModel):
    message: str
    registration_id: int
    course_id: str
    course_name: str
    teacher_id: int
    teacher_name: str
    student_id: int
    status: str


class CourseRegistrationRequestResponse(BaseModel):
    id: int
    course_name: str
    student_id: int
    student_name: str
    student_email: str
    status: str
    created_at: str


class WorkspaceCreateRequest(BaseModel):
    name: str


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    teacher_id: int
    video_count: int
    completed_video_count: int
    student_count: int
    created_at: str


class UserUpdateRequest(BaseModel):
    full_name: str
    email: str
    password: Optional[str] = None


class AccountDeleteRequest(BaseModel):
    password: str


class AccountDeleteResponse(BaseModel):
    message: str
