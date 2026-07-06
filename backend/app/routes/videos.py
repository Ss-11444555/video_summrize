"""Video upload and listing API routes."""

from __future__ import annotations

import sqlite3
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from backend.app.core.database import get_db_connection
from backend.app.core.dependencies import get_current_user, get_current_user_from_header_or_query, require_roles
from backend.app.schemas.video_schema import (
    VideoBulkAssignmentResponse,
    VideoDeleteResponse,
    VideoAssignmentRequest,
    VideoAssignmentResponse,
    VideoResponse,
    VideoUploadResponse,
)
from backend.app.services.processing_service import create_processing_job, run_multimodal_pipeline
from backend.app.services.video_service import (
    assign_video_to_all_students,
    assign_video_to_registered_students,
    assign_video_to_student,
    create_video,
    create_video_from_youtube,
    delete_video,
    get_video_by_id,
    get_video_file_response,
    list_videos,
)


router = APIRouter(prefix="/videos", tags=["Videos"])


@router.get("", response_model=List[VideoResponse])
def get_videos(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    workspace_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return list_videos(connection, current_user, search=search, status_filter=status_filter, workspace_id=workspace_id)


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    course_name: str = Form(...),
    reference_summary: str = Form(...),
    module_week: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    is_published: bool = Form(default=False),
    workspace_id: Optional[int] = Form(default=None),
    video_file: UploadFile = File(...),
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    video = await create_video(
        connection=connection,
        upload_file=video_file,
        title=title,
        course_name=course_name,
        reference_summary=reference_summary,
        module_week=module_week,
        description=description,
        is_published=is_published,
        current_user=current_user,
        workspace_id=workspace_id,
    )
    create_processing_job(connection, video["id"])
    background_tasks.add_task(run_multimodal_pipeline, video["id"])
    updated_video = get_video_by_id(connection, video["id"], current_user)
    return {"message": "Video uploaded successfully.", "video": updated_video}


@router.post("/youtube", response_model=VideoUploadResponse)
def import_youtube_video(
    background_tasks: BackgroundTasks,
    youtube_url: str = Form(...),
    title: str = Form(...),
    course_name: str = Form(...),
    reference_summary: str = Form(...),
    module_week: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    is_published: bool = Form(default=False),
    workspace_id: Optional[int] = Form(default=None),
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    video = create_video_from_youtube(
        connection=connection,
        video_url=youtube_url,
        title=title,
        course_name=course_name,
        reference_summary=reference_summary,
        module_week=module_week,
        description=description,
        is_published=is_published,
        current_user=current_user,
        workspace_id=workspace_id,
    )
    create_processing_job(connection, video["id"])
    background_tasks.add_task(run_multimodal_pipeline, video["id"])
    updated_video = get_video_by_id(connection, video["id"], current_user)
    return {"message": "YouTube video imported successfully.", "video": updated_video}


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id: int,
    current_user: dict = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return get_video_by_id(connection, video_id, current_user)


@router.delete("/{video_id}", response_model=VideoDeleteResponse)
def delete_teacher_video(
    video_id: int,
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return delete_video(
        connection=connection,
        video_id=video_id,
        current_user=current_user,
    )


@router.get("/{video_id}/stream")
def stream_video(
    video_id: int,
    quality: Optional[str] = None,
    current_user: dict = Depends(get_current_user_from_header_or_query),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return get_video_file_response(connection, video_id, current_user, quality=quality)


@router.post("/{video_id}/assign", response_model=VideoAssignmentResponse)
def assign_video(
    video_id: int,
    payload: VideoAssignmentRequest,
    current_user: dict = Depends(require_roles("teacher", "admin")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return assign_video_to_student(
        connection=connection,
        video_id=video_id,
        student_email=payload.student_email,
        current_user=current_user,
    )


@router.post("/{video_id}/assign/course-registered", response_model=VideoBulkAssignmentResponse)
def assign_video_to_course_registered_students(
    video_id: int,
    current_user: dict = Depends(require_roles("teacher", "admin")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return assign_video_to_registered_students(
        connection=connection,
        video_id=video_id,
        current_user=current_user,
    )


@router.post("/{video_id}/assign/all-students", response_model=VideoBulkAssignmentResponse)
def assign_video_to_every_student(
    video_id: int,
    current_user: dict = Depends(require_roles("teacher", "admin")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return assign_video_to_all_students(
        connection=connection,
        video_id=video_id,
        current_user=current_user,
    )
