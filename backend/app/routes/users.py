"""Admin user management API routes."""

from __future__ import annotations

import sqlite3
from typing import List

from fastapi import APIRouter, Depends

from backend.app.core.database import get_db_connection
from backend.app.core.dependencies import require_roles
from backend.app.schemas.user_schema import (
    AccountDeleteRequest,
    AccountDeleteResponse,
    CourseDirectoryResponse,
    CourseRegistrationRequestResponse,
    CourseRegistrationResponse,
    UserUpdateRequest,
    UserListResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from backend.app.services.user_service import (
    create_teacher_workspace,
    delete_current_user,
    decide_course_registration,
    list_course_registration_requests,
    list_courses_for_student,
    list_users,
    list_teacher_workspaces,
    register_student_to_course,
    update_current_user,
)


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=List[UserListResponse])
def get_users(
    _: dict = Depends(require_roles("admin")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return list_users(connection)


@router.put("/me")
def update_me(
    payload: UserUpdateRequest,
    current_user: dict = Depends(require_roles("admin", "teacher", "student")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return update_current_user(connection, current_user, payload.full_name, payload.email, payload.password)


@router.delete("/me", response_model=AccountDeleteResponse)
def delete_me(
    payload: AccountDeleteRequest,
    current_user: dict = Depends(require_roles("admin", "teacher", "student")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return delete_current_user(connection, current_user, payload.password)


@router.get("/workspaces", response_model=List[WorkspaceResponse])
def get_workspaces(
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return list_teacher_workspaces(connection, current_user)


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
def create_workspace(
    payload: WorkspaceCreateRequest,
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return create_teacher_workspace(connection, current_user, payload.name)


@router.get("/courses", response_model=List[CourseDirectoryResponse])
def get_courses(
    current_user: dict = Depends(require_roles("student")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return list_courses_for_student(connection, current_user)


@router.post("/courses/{teacher_id}/register", response_model=CourseRegistrationResponse)
def register_course(
    teacher_id: int,
    course_name: str,
    current_user: dict = Depends(require_roles("student")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return register_student_to_course(connection, teacher_id, course_name, current_user)


@router.get("/teacher/course-requests", response_model=List[CourseRegistrationRequestResponse])
def get_course_registration_requests(
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return list_course_registration_requests(connection, current_user)


@router.post(
    "/teacher/course-requests/{registration_id}/accept",
    response_model=CourseRegistrationRequestResponse,
)
def accept_course_registration_request(
    registration_id: int,
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return decide_course_registration(connection, registration_id, "accepted", current_user)


@router.post(
    "/teacher/course-requests/{registration_id}/reject",
    response_model=CourseRegistrationRequestResponse,
)
def reject_course_registration_request(
    registration_id: int,
    current_user: dict = Depends(require_roles("teacher")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return decide_course_registration(connection, registration_id, "rejected", current_user)
