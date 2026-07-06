"""SQLite connection helpers and database initialization."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Generator

from backend.app.core.config import ROOT_DIR, settings
from backend.app.utils.file_handler import ensure_directories


SCHEMA_PATH = ROOT_DIR / "database" / "schema.sql"
SEED_PATH = ROOT_DIR / "database" / "seed.sql"


def create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(settings.database_path, check_same_thread=False, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA busy_timeout = 30000;")
    return connection


def configure_database(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("PRAGMA journal_mode = WAL;")
    except sqlite3.OperationalError:
        # Another process can briefly lock SQLite during startup or after a failed
        # background job. busy_timeout still protects normal reads/writes.
        pass


def is_database_locked(error: sqlite3.OperationalError) -> bool:
    return "database is locked" in str(error).lower()


def commit_with_retry(
    connection: sqlite3.Connection,
    *,
    attempts: int = 5,
    delay_seconds: float = 0.75,
) -> None:
    last_error: sqlite3.OperationalError | None = None

    for attempt in range(attempts):
        try:
            connection.commit()
            return
        except sqlite3.OperationalError as error:
            if not is_database_locked(error):
                raise
            last_error = error
            time.sleep(delay_seconds * (attempt + 1))

    connection.rollback()
    raise last_error or sqlite3.OperationalError("database is locked")


def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    connection = create_connection()
    try:
        yield connection
    finally:
        connection.close()


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    query = """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
    """
    row = connection.execute(query, (table_name,)).fetchone()
    return row is not None


def ensure_user_scoping_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS teacher_workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(teacher_id, name),
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_teacher_workspaces_teacher_id ON teacher_workspaces(teacher_id)"
    )
    video_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(videos)").fetchall()
    }
    if "workspace_id" not in video_columns:
        connection.execute("ALTER TABLE videos ADD COLUMN workspace_id INTEGER REFERENCES teacher_workspaces(id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_videos_workspace_id ON videos(workspace_id)")

    teacher_rows = connection.execute(
        "SELECT id FROM users WHERE role = 'teacher' AND is_active = 1"
    ).fetchall()
    for teacher in teacher_rows:
        course_rows = connection.execute(
            """
            SELECT DISTINCT course_name
            FROM videos
            WHERE owner_id = ?
            AND TRIM(COALESCE(course_name, '')) <> ''
            """,
            (teacher["id"],),
        ).fetchall()
        for course in course_rows:
            connection.execute(
                """
                INSERT OR IGNORE INTO teacher_workspaces (teacher_id, name)
                VALUES (?, ?)
                """,
                (teacher["id"], course["course_name"]),
            )

    connection.execute(
        """
        UPDATE videos
        SET workspace_id = (
            SELECT teacher_workspaces.id
            FROM teacher_workspaces
            WHERE teacher_workspaces.teacher_id = videos.owner_id
            AND teacher_workspaces.name = videos.course_name
            LIMIT 1
        )
        WHERE workspace_id IS NULL
        """
    )

    connection.execute("DROP TABLE IF EXISTS teacher_registrations")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS course_registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            course_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
            decided_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(teacher_id, student_id, course_name),
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_course_registrations_teacher_id ON course_registrations(teacher_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_course_registrations_student_id ON course_registrations(student_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_course_registrations_course_name ON course_registrations(course_name)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS video_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            assigned_by INTEGER NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(video_id, student_id),
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_video_assignments_video_id ON video_assignments(video_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_video_assignments_student_id ON video_assignments(student_id)"
    )
    commit_with_retry(connection)


def ensure_visual_understanding_schema(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "frame_captions"):
        return

    caption_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(frame_captions)").fetchall()
    }
    missing_columns = {
        "visual_model": "TEXT",
        "ocr_text": "TEXT",
        "equations_text": "TEXT",
        "equation_image_paths": "TEXT",
        "equation_source": "TEXT",
        "equation_fallback_notes": "TEXT",
        "visual_type": "TEXT",
        "topic": "TEXT",
        "change_score": "REAL",
        "annotated_frame_path": "TEXT",
    }
    for column_name, column_type in missing_columns.items():
        if column_name not in caption_columns:
            connection.execute("ALTER TABLE frame_captions ADD COLUMN {} {}".format(column_name, column_type))

    connection.execute("CREATE INDEX IF NOT EXISTS idx_frame_captions_video_id ON frame_captions(video_id)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_frame_captions_timestamp ON frame_captions(frame_timestamp_seconds)"
    )

    commit_with_retry(connection)


def ensure_transcript_segments_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS transcript_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            segment_text TEXT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_transcript_segments_video_id ON transcript_segments(video_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_transcript_segments_time ON transcript_segments(start_seconds, end_seconds)"
    )
    commit_with_retry(connection)


def ensure_slide_summaries_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS slide_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            frame_index INTEGER NOT NULL,
            start_seconds REAL NOT NULL,
            end_seconds REAL NOT NULL,
            frame_path TEXT,
            annotated_frame_path TEXT,
            caption_text TEXT NOT NULL,
            ocr_text TEXT,
            equations_text TEXT,
            equation_image_paths TEXT,
            equation_source TEXT,
            equation_fallback_notes TEXT,
            visual_type TEXT,
            topic TEXT,
            transcript_text TEXT,
            summary_text TEXT NOT NULL,
            key_points TEXT,
            transcript_excerpt TEXT,
            model_name TEXT,
            prompt_version TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_slide_summaries_video_id ON slide_summaries(video_id)")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_slide_summaries_time ON slide_summaries(start_seconds, end_seconds)"
    )
    summary_columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(slide_summaries)").fetchall()
    }
    if "annotated_frame_path" not in summary_columns:
        connection.execute("ALTER TABLE slide_summaries ADD COLUMN annotated_frame_path TEXT")
    if "equation_image_paths" not in summary_columns:
        connection.execute("ALTER TABLE slide_summaries ADD COLUMN equation_image_paths TEXT")
    if "equation_source" not in summary_columns:
        connection.execute("ALTER TABLE slide_summaries ADD COLUMN equation_source TEXT")
    if "equation_fallback_notes" not in summary_columns:
        connection.execute("ALTER TABLE slide_summaries ADD COLUMN equation_fallback_notes TEXT")
    commit_with_retry(connection)


def init_database() -> None:
    ensure_directories(
        [
            settings.upload_dir,
            settings.audio_dir,
            settings.frames_dir,
            settings.annotated_frames_dir,
            settings.equation_crops_dir,
            settings.results_dir,
            settings.database_path.parent,
        ]
    )

    connection = create_connection()
    try:
        configure_database(connection)

        if not _table_exists(connection, "users"):
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            connection.executescript(schema_sql)
            commit_with_retry(connection)

        ensure_user_scoping_tables(connection)
        ensure_visual_understanding_schema(connection)
        ensure_transcript_segments_schema(connection)
        ensure_slide_summaries_schema(connection)

        user_count = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if user_count == 0 and SEED_PATH.exists():
            seed_sql = SEED_PATH.read_text(encoding="utf-8")
            connection.executescript(seed_sql)
            commit_with_retry(connection)
    finally:
        connection.close()
