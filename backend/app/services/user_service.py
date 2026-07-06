"""Business logic for user management."""

from __future__ import annotations

import sqlite3
from typing import Dict, List

from fastapi import HTTPException, status

from backend.app.core.database import commit_with_retry
from backend.app.core.security import hash_password, verify_password
from backend.app.services.video_service import delete_video


def _course_id(teacher_id: int, course_name: str) -> str:
    return "{}:{}".format(teacher_id, course_name)


def _clean_workspace_name(name: str) -> str:
    cleaned = " ".join(name.strip().split())
    if len(cleaned) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course workspace name is required.")
    if len(cleaned) > 120:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course workspace name is too long.")
    return cleaned


def create_teacher_workspace(
    connection: sqlite3.Connection,
    current_user: dict,
    name: str,
) -> Dict:
    workspace_name = _clean_workspace_name(name)
    try:
        cursor = connection.execute(
            """
            INSERT INTO teacher_workspaces (teacher_id, name)
            VALUES (?, ?)
            """,
            (current_user["id"], workspace_name),
        )
        commit_with_retry(connection)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This course workspace already exists.")

    row = connection.execute(
        """
        SELECT id, teacher_id, name, created_at
        FROM teacher_workspaces
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    return _serialize_workspace(connection, row)


def _serialize_workspace(connection: sqlite3.Connection, row: sqlite3.Row) -> Dict:
    counts = connection.execute(
        """
        SELECT
            COUNT(videos.id) AS video_count,
            SUM(CASE WHEN videos.status = 'completed' THEN 1 ELSE 0 END) AS completed_video_count
        FROM videos
        WHERE videos.workspace_id = ?
        """,
        (row["id"],),
    ).fetchone()
    students = connection.execute(
        """
        SELECT COUNT(DISTINCT student_id) AS student_count
        FROM course_registrations
        WHERE teacher_id = ? AND course_name = ? AND status = 'accepted'
        """,
        (row["teacher_id"], row["name"]),
    ).fetchone()
    return {
        "id": row["id"],
        "name": row["name"],
        "teacher_id": row["teacher_id"],
        "video_count": int(counts["video_count"] or 0),
        "completed_video_count": int(counts["completed_video_count"] or 0),
        "student_count": int(students["student_count"] or 0),
        "created_at": row["created_at"],
    }


def list_teacher_workspaces(connection: sqlite3.Connection, current_user: dict) -> List[Dict]:
    rows = connection.execute(
        """
        SELECT id, teacher_id, name, created_at
        FROM teacher_workspaces
        WHERE teacher_id = ?
        ORDER BY created_at ASC, name ASC
        """,
        (current_user["id"],),
    ).fetchall()
    return [_serialize_workspace(connection, row) for row in rows]


def list_users(connection: sqlite3.Connection) -> List[Dict]:
    rows = connection.execute(
        """
        SELECT id, full_name, email, role, is_active, created_at
        FROM users
        ORDER BY created_at DESC
        """
    ).fetchall()

    return [
        {
            "id": row["id"],
            "full_name": row["full_name"],
            "email": row["email"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _serialize_account(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
    }


def update_current_user(
    connection: sqlite3.Connection,
    current_user: dict,
    full_name: str,
    email: str,
    password: str | None = None,
) -> Dict:
    cleaned_name = " ".join(full_name.strip().split())
    cleaned_email = email.strip().lower()

    if len(cleaned_name) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full name is required.")
    if "@" not in cleaned_email or "." not in cleaned_email.split("@")[-1]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address.")

    existing = connection.execute(
        """
        SELECT id
        FROM users
        WHERE email = ? AND id <> ?
        """,
        (cleaned_email, current_user["id"]),
    ).fetchone()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This email is already used.")

    if password and password.strip():
        if len(password) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
        connection.execute(
            """
            UPDATE users
            SET full_name = ?, email = ?, password_hash = ?
            WHERE id = ?
            """,
            (cleaned_name, cleaned_email, hash_password(password), current_user["id"]),
        )
    else:
        connection.execute(
            """
            UPDATE users
            SET full_name = ?, email = ?
            WHERE id = ?
            """,
            (cleaned_name, cleaned_email, current_user["id"]),
        )

    commit_with_retry(connection)

    row = connection.execute(
        """
        SELECT id, full_name, email, role, is_active
        FROM users
        WHERE id = ?
        """,
        (current_user["id"],),
    ).fetchone()
    return _serialize_account(row)


def delete_current_user(connection: sqlite3.Connection, current_user: dict, password: str) -> Dict:
    row = connection.execute(
        """
        SELECT id, password_hash
        FROM users
        WHERE id = ?
        """,
        (current_user["id"],),
    ).fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password verification failed.")

    video_rows = connection.execute(
        """
        SELECT id
        FROM videos
        WHERE owner_id = ?
        """,
        (current_user["id"],),
    ).fetchall()
    for video_row in video_rows:
        delete_video(connection, int(video_row["id"]), current_user)

    connection.execute("DELETE FROM users WHERE id = ?", (current_user["id"],))
    commit_with_retry(connection)
    return {"message": "Account deleted successfully."}


def list_courses_for_student(connection: sqlite3.Connection, current_user: dict) -> List[Dict]:
    rows = connection.execute(
        """
        SELECT
            videos.owner_id AS teacher_id,
            users.full_name AS teacher_name,
            users.email AS teacher_email,
            videos.course_name,
            COALESCE(
                (
                    SELECT course_registrations.status
                    FROM course_registrations
                    WHERE course_registrations.teacher_id = videos.owner_id
                    AND course_registrations.student_id = ?
                    AND course_registrations.course_name = videos.course_name
                    LIMIT 1
                ),
                'none'
            ) AS registration_status,
            COUNT(*) AS published_videos_count,
            SUM(CASE WHEN videos.status = 'completed' THEN 1 ELSE 0 END) AS completed_videos_count,
            SUM(
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM video_assignments
                    WHERE video_assignments.video_id = videos.id
                    AND video_assignments.student_id = ?
                ) THEN 1 ELSE 0 END
            ) AS assigned_videos_count,
            SUM(
                CASE WHEN videos.status = 'completed'
                AND EXISTS (
                    SELECT 1
                    FROM video_assignments
                    WHERE video_assignments.video_id = videos.id
                    AND video_assignments.student_id = ?
                ) THEN 1 ELSE 0 END
            ) AS assigned_completed_videos_count
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE videos.is_published = 1
        AND users.role = 'teacher'
        AND users.is_active = 1
        GROUP BY videos.owner_id, videos.course_name
        ORDER BY
            registration_status = 'accepted' DESC,
            assigned_videos_count > 0 DESC,
            registration_status = 'pending' DESC,
            videos.course_name ASC,
            users.full_name ASC
        """,
        (current_user["id"], current_user["id"], current_user["id"]),
    ).fetchall()

    return [
        {
            "id": _course_id(row["teacher_id"], row["course_name"]),
            "course_name": row["course_name"],
            "teacher_id": row["teacher_id"],
            "teacher_name": row["teacher_name"],
            "teacher_email": row["teacher_email"],
            "registered": row["registration_status"] == "accepted",
            "registration_status": row["registration_status"],
            "published_videos_count": int(row["published_videos_count"] or 0),
            "completed_videos_count": int(row["completed_videos_count"] or 0),
            "assigned_videos_count": int(row["assigned_videos_count"] or 0),
            "assigned_completed_videos_count": int(row["assigned_completed_videos_count"] or 0),
            "has_assigned_videos": int(row["assigned_videos_count"] or 0) > 0,
        }
        for row in rows
    ]


def register_student_to_course(
    connection: sqlite3.Connection,
    teacher_id: int,
    course_name: str,
    current_user: dict,
) -> Dict:
    cleaned_course_name = course_name.strip()
    if not cleaned_course_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course name is required.")

    course_row = connection.execute(
        """
        SELECT videos.owner_id AS teacher_id, users.full_name AS teacher_name
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE videos.owner_id = ?
        AND videos.course_name = ?
        AND videos.is_published = 1
        AND users.role = 'teacher'
        AND users.is_active = 1
        LIMIT 1
        """,
        (teacher_id, cleaned_course_name),
    ).fetchone()

    if not course_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    connection.execute(
        """
        INSERT INTO course_registrations (teacher_id, student_id, course_name, status, decided_at)
        VALUES (?, ?, ?, 'pending', NULL)
        ON CONFLICT(teacher_id, student_id, course_name)
        DO UPDATE SET
            status = CASE
                WHEN course_registrations.status = 'accepted' THEN course_registrations.status
                ELSE 'pending'
            END,
            decided_at = CASE
                WHEN course_registrations.status = 'accepted' THEN course_registrations.decided_at
                ELSE NULL
            END
        """,
        (teacher_id, current_user["id"], cleaned_course_name),
    )
    commit_with_retry(connection)

    registration_row = connection.execute(
        """
        SELECT id, status
        FROM course_registrations
        WHERE teacher_id = ? AND student_id = ? AND course_name = ?
        """,
        (teacher_id, current_user["id"], cleaned_course_name),
    ).fetchone()

    return {
        "message": "Course access request sent.",
        "registration_id": registration_row["id"],
        "course_id": _course_id(teacher_id, cleaned_course_name),
        "course_name": cleaned_course_name,
        "teacher_id": teacher_id,
        "teacher_name": course_row["teacher_name"],
        "student_id": current_user["id"],
        "status": registration_row["status"],
    }


def list_course_registration_requests(connection: sqlite3.Connection, current_user: dict) -> List[Dict]:
    rows = connection.execute(
        """
        SELECT
            course_registrations.id,
            course_registrations.course_name,
            course_registrations.student_id,
            course_registrations.status,
            course_registrations.created_at,
            users.full_name AS student_name,
            users.email AS student_email
        FROM course_registrations
        JOIN users ON users.id = course_registrations.student_id
        WHERE course_registrations.teacher_id = ?
        ORDER BY
            course_registrations.status = 'pending' DESC,
            course_registrations.created_at DESC
        """,
        (current_user["id"],),
    ).fetchall()

    return [
        {
            "id": row["id"],
            "course_name": row["course_name"],
            "student_id": row["student_id"],
            "student_name": row["student_name"],
            "student_email": row["student_email"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def decide_course_registration(
    connection: sqlite3.Connection,
    registration_id: int,
    decision: str,
    current_user: dict,
) -> Dict:
    if decision not in {"accepted", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be accepted or rejected.")

    registration_row = connection.execute(
        """
        SELECT
            course_registrations.id,
            course_registrations.course_name,
            course_registrations.student_id,
            course_registrations.created_at,
            users.full_name AS student_name,
            users.email AS student_email
        FROM course_registrations
        JOIN users ON users.id = course_registrations.student_id
        WHERE course_registrations.id = ?
        AND course_registrations.teacher_id = ?
        """,
        (registration_id, current_user["id"]),
    ).fetchone()

    if not registration_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course access request not found.")

    connection.execute(
        """
        UPDATE course_registrations
        SET status = ?, decided_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (decision, registration_id),
    )
    commit_with_retry(connection)

    return {
        "id": registration_row["id"],
        "course_name": registration_row["course_name"],
        "student_id": registration_row["student_id"],
        "student_name": registration_row["student_name"],
        "student_email": registration_row["student_email"],
        "status": decision,
        "created_at": registration_row["created_at"],
    }
