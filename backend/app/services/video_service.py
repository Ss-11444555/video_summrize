"""Business logic for video storage and retrieval."""

from __future__ import annotations

import json
import sqlite3
import time
import mimetypes
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Optional

from fastapi import HTTPException, UploadFile, status

from backend.app.core.database import commit_with_retry, is_database_locked
from backend.app.core.config import settings
from backend.app.utils.file_handler import sanitize_filename, save_upload_file

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
except ImportError:  # pragma: no cover - handled at runtime with a clear API error.
    YoutubeDL = None
    DownloadError = Exception


def _serialize_video(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "course_name": row["course_name"],
        "module_week": row["module_week"],
        "description": row["description"],
        "source_filename": row["source_filename"],
        "stored_path": row["stored_path"],
        "duration_seconds": row["duration_seconds"],
        "file_size_bytes": row["file_size_bytes"],
        "owner_id": row["owner_id"],
        "workspace_id": row["workspace_id"],
        "owner_name": row["owner_name"],
        "status": row["status"],
        "is_published": bool(row["is_published"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _insert_video_record(
    connection: sqlite3.Connection,
    *,
    title: str,
    course_name: str,
    reference_summary: str,
    module_week: Optional[str],
    description: Optional[str],
    source_filename: str,
    stored_path: str,
    file_size_bytes: int,
    is_published: bool,
    current_user: dict,
    workspace_id: Optional[int] = None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO videos (
            title,
            course_name,
            module_week,
            description,
            source_filename,
            stored_path,
            file_size_bytes,
            owner_id,
            workspace_id,
            status,
            is_published
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?)
        """,
        (
            title,
            course_name,
            module_week,
            description,
            source_filename,
            stored_path,
            file_size_bytes,
            current_user["id"],
            workspace_id,
            1 if is_published else 0,
        ),
    )
    video_id = int(cursor.lastrowid)
    connection.execute(
        """
        INSERT INTO evaluations (video_id, reference_summary, evaluation_notes)
        VALUES (?, ?, ?)
        """,
        (
            video_id,
            reference_summary,
            "Teacher-written reference summary saved during upload; ROUGE scores are calculated after processing.",
        ),
    )
    commit_with_retry(connection)
    return video_id


def _clean_reference_summary(reference_summary: str) -> str:
    cleaned_summary = reference_summary.strip()
    if not cleaned_summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A teacher reference summary is required before uploading the video.",
        )
    return cleaned_summary


def _is_supported_youtube_url(video_url: str) -> bool:
    parsed = urlparse(video_url.strip())
    host = parsed.netloc.lower()
    return parsed.scheme in {"http", "https"} and (
        host == "youtu.be"
        or host.endswith(".youtu.be")
        or host == "youtube.com"
        or host.endswith(".youtube.com")
    )


def _resolve_optional_project_path(path_value: str) -> Path:
    candidate = Path(path_value).expanduser()
    if candidate.is_absolute():
        return candidate
    return settings.database_path.parent / candidate


def _apply_ytdlp_cookie_options(ydl_options: dict) -> None:
    if settings.ytdlp_cookies_file:
        ydl_options["cookiefile"] = str(_resolve_optional_project_path(settings.ytdlp_cookies_file))
        return

    if settings.ytdlp_cookies_from_browser:
        ydl_options["cookiesfrombrowser"] = (settings.ytdlp_cookies_from_browser,)


def _download_youtube_with_fallbacks(cleaned_url: str, base_options: dict) -> dict:
    format_candidates = [
        "bv*[height<=720]+ba/b[height<=720]/best",
        "best[height<=720]/best",
        "best",
    ]
    last_error: Exception | None = None

    for format_selector in format_candidates:
        ydl_options = dict(base_options)
        ydl_options["format"] = format_selector
        try:
            with YoutubeDL(ydl_options) as ydl:
                return ydl.extract_info(cleaned_url, download=True)
        except DownloadError as error:
            last_error = error
            if "Requested format is not available" not in str(error):
                raise

    raise last_error or RuntimeError("Could not download YouTube video with any configured format.")


def can_access_video(connection: sqlite3.Connection, video_row: sqlite3.Row, current_user: dict) -> bool:
    if current_user["role"] == "admin":
        return True
    if current_user["role"] == "teacher":
        return video_row["owner_id"] == current_user["id"]

    if not bool(video_row["is_published"]):
        return False

    assignment = connection.execute(
        """
        SELECT id
        FROM video_assignments
        WHERE video_id = ? AND student_id = ?
        """,
        (video_row["id"], current_user["id"]),
    ).fetchone()
    if assignment is not None:
        return True

    course_registration = connection.execute(
        """
        SELECT id
        FROM course_registrations
        WHERE teacher_id = ?
        AND student_id = ?
        AND course_name = ?
        AND status = 'accepted'
        """,
        (video_row["owner_id"], current_user["id"], video_row["course_name"]),
    ).fetchone()
    return course_registration is not None


def list_videos(
    connection: sqlite3.Connection,
    current_user: dict,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    workspace_id: Optional[int] = None,
) -> List[Dict]:
    query = """
        SELECT videos.*, users.full_name AS owner_name
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE 1 = 1
    """
    params: list = []

    if current_user["role"] == "teacher":
        query += " AND videos.owner_id = ?"
        params.append(current_user["id"])
        if workspace_id is not None:
            query += " AND videos.workspace_id = ?"
            params.append(workspace_id)
    elif current_user["role"] == "student":
        query += """
            AND videos.is_published = 1
            AND (
                EXISTS (
                    SELECT 1
                    FROM video_assignments
                    WHERE video_assignments.video_id = videos.id
                    AND video_assignments.student_id = ?
                )
                OR EXISTS (
                    SELECT 1
                    FROM course_registrations
                    WHERE course_registrations.teacher_id = videos.owner_id
                    AND course_registrations.student_id = ?
                    AND course_registrations.course_name = videos.course_name
                    AND course_registrations.status = 'accepted'
                )
            )
        """
        params.extend([current_user["id"], current_user["id"]])

    if search:
        query += " AND (videos.title LIKE ? OR videos.course_name LIKE ? OR videos.description LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    if status_filter:
        query += " AND videos.status = ?"
        params.append(status_filter)

    query += " ORDER BY videos.created_at DESC"
    rows = connection.execute(query, tuple(params)).fetchall()
    return [_serialize_video(row) for row in rows]


def get_video_by_id(connection: sqlite3.Connection, video_id: int, current_user: dict) -> dict:
    row = connection.execute(
        """
        SELECT videos.*, users.full_name AS owner_name
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE videos.id = ?
        """,
        (video_id,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    if not can_access_video(connection, row, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this video.")

    return _serialize_video(row)


def _parse_stored_paths(path_value: Optional[str]) -> List[str]:
    if not path_value:
        return []

    try:
        parsed = json.loads(path_value)
    except (json.JSONDecodeError, TypeError):
        return [path_value]

    if isinstance(parsed, list):
        return [str(item) for item in parsed if item]
    return [str(parsed)] if parsed else []


def _managed_storage_roots() -> tuple[Path, ...]:
    return (
        settings.upload_dir.resolve(),
        settings.audio_dir.resolve(),
        settings.frames_dir.resolve(),
        settings.annotated_frames_dir.resolve(),
        settings.equation_crops_dir.resolve(),
        settings.results_dir.resolve(),
    )


def _resolve_managed_storage_path(path_value: str | Path) -> Optional[Path]:
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = settings.database_path.parent / candidate
    resolved = candidate.resolve()

    if any(resolved == root or resolved.is_relative_to(root) for root in _managed_storage_roots()):
        return resolved
    return None


def _remove_managed_paths(paths: set[Path]) -> tuple[int, List[str]]:
    deleted_count = 0
    warnings: List[str] = []

    for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
        managed_path = _resolve_managed_storage_path(path)
        if managed_path is None or not managed_path.exists():
            continue

        try:
            if managed_path.is_dir():
                shutil.rmtree(managed_path)
            else:
                managed_path.unlink()
            deleted_count += 1
        except OSError as error:
            warnings.append("{}: {}".format(managed_path.name, error))

    return deleted_count, warnings


def _video_storage_paths(connection: sqlite3.Connection, video_row: sqlite3.Row) -> set[Path]:
    video_id = int(video_row["id"])
    source_path = _resolve_managed_storage_path(video_row["stored_path"])
    paths = deleted_video_artifact_paths(
        video_id=video_id,
        title=video_row["title"],
        stored_path=video_row["stored_path"],
    )

    if source_path is not None:
        paths.add(source_path)

    for row in connection.execute(
        """
        SELECT frame_path, annotated_frame_path, equation_image_paths
        FROM frame_captions
        WHERE video_id = ?
        """,
        (video_id,),
    ).fetchall():
        for path_value in (row["frame_path"], row["annotated_frame_path"]):
            if path_value:
                resolved = _resolve_managed_storage_path(path_value)
                if resolved is not None:
                    paths.add(resolved)
        for path_value in _parse_stored_paths(row["equation_image_paths"]):
            resolved = _resolve_managed_storage_path(path_value)
            if resolved is not None:
                paths.add(resolved)

    for row in connection.execute(
        """
        SELECT frame_path, annotated_frame_path, equation_image_paths
        FROM slide_summaries
        WHERE video_id = ?
        """,
        (video_id,),
    ).fetchall():
        for path_value in (row["frame_path"], row["annotated_frame_path"]):
            if path_value:
                resolved = _resolve_managed_storage_path(path_value)
                if resolved is not None:
                    paths.add(resolved)
        for path_value in _parse_stored_paths(row["equation_image_paths"]):
            resolved = _resolve_managed_storage_path(path_value)
            if resolved is not None:
                paths.add(resolved)

    return paths


def deleted_video_artifact_paths(
    *,
    video_id: int,
    title: Optional[str],
    stored_path: str,
) -> set[Path]:
    paths: set[Path] = set()
    source_path = _resolve_managed_storage_path(stored_path)
    if source_path is not None:
        paths.add(source_path)
        for sidecar in source_path.parent.glob(source_path.stem + ".*"):
            if sidecar == source_path or sidecar.suffix.lower() in {".vtt", ".srt"}:
                paths.add(sidecar)
        paths.add(settings.audio_dir / (source_path.stem + ".wav"))
        paths.update(settings.frames_dir.glob(source_path.stem + "_frame_*.jpg"))
        paths.update(settings.annotated_frames_dir.glob(source_path.stem + "_frame_*_annotated.jpg"))

    paths.add(settings.upload_dir / "qualities" / str(video_id))
    safe_title = sanitize_filename(title or "")
    artifact_names = {"video_{}".format(video_id)}
    if safe_title:
        artifact_names.add("video_{}_{}".format(video_id, safe_title))

    for root in (settings.annotated_frames_dir, settings.equation_crops_dir):
        for artifact_name in artifact_names:
            paths.add(root / artifact_name)
        paths.update(root.glob("video_{}_*".format(video_id)))
    if settings.results_dir.exists():
        for stage_dir in settings.results_dir.iterdir():
            if stage_dir.is_dir():
                for artifact_name in artifact_names:
                    paths.add(stage_dir / artifact_name)
                paths.update(stage_dir.glob("video_{}_*".format(video_id)))

    return paths


def cleanup_deleted_video_artifacts(
    *,
    video_id: int,
    title: Optional[str],
    stored_path: str,
) -> tuple[int, List[str]]:
    return _remove_managed_paths(
        deleted_video_artifact_paths(
            video_id=video_id,
            title=title,
            stored_path=stored_path,
        )
    )


def delete_video(
    connection: sqlite3.Connection,
    video_id: int,
    current_user: dict,
) -> dict:
    video_row = connection.execute(
        "SELECT * FROM videos WHERE id = ?",
        (video_id,),
    ).fetchone()

    if not video_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    if video_row["owner_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete videos that you uploaded.",
        )
    storage_paths = _video_storage_paths(connection, video_row)
    connection.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    commit_with_retry(connection)
    deleted_files, cleanup_warnings = _remove_managed_paths(storage_paths)

    return {
        "message": "Lecture deleted successfully.",
        "video_id": video_id,
        "deleted_files": deleted_files,
        "cleanup_warnings": cleanup_warnings,
    }


VIDEO_QUALITY_HEIGHTS = {
    "720": 720,
    "480": 480,
    "360": 360,
}


def _quality_output_path(video_id: int, source_path: Path, quality: str) -> Path:
    quality_dir = settings.upload_dir / "qualities" / str(video_id)
    source_stem = sanitize_filename(source_path.stem)
    return quality_dir / "{}_{}p.mp4".format(source_stem, quality)


def _get_video_height(source_path: Path) -> Optional[int]:
    if shutil.which("ffprobe") is None:
        return None

    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "csv=p=0",
            str(source_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None

    try:
        return int(completed.stdout.strip().splitlines()[0])
    except (IndexError, ValueError):
        return None


def _ensure_quality_variant(video_id: int, source_path: Path, quality: str) -> Path:
    if quality not in VIDEO_QUALITY_HEIGHTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported video quality.")

    height = VIDEO_QUALITY_HEIGHTS[quality]
    source_height = _get_video_height(source_path)
    if source_height is not None and source_height <= height:
        return source_path

    output_path = _quality_output_path(video_id, source_path, quality)
    if output_path.exists() and output_path.stat().st_size > 0:
        return output_path

    if shutil.which("ffmpeg") is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ffmpeg is required to generate video quality variants.",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".tmp.mp4")
    if temporary_path.exists():
        temporary_path.unlink()

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vf",
        "scale=-2:{}".format(height),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(temporary_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        if temporary_path.exists():
            temporary_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate {}p video stream: {}".format(
                quality,
                completed.stderr.strip() or completed.stdout.strip(),
            ),
        )

    temporary_path.replace(output_path)
    return output_path


def get_video_file_response(
    connection: sqlite3.Connection,
    video_id: int,
    current_user: dict,
    quality: Optional[str] = None,
):
    from fastapi.responses import FileResponse

    video = get_video_by_id(connection, video_id, current_user)
    video_path = settings.database_path.parent / video["stored_path"]

    if not video_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored video file was not found.")

    requested_quality = str(quality or "auto").strip().lower().removesuffix("p")
    stream_path = (
        _ensure_quality_variant(video_id, video_path, requested_quality)
        if requested_quality in VIDEO_QUALITY_HEIGHTS
        else video_path
    )

    media_type = mimetypes.guess_type(str(stream_path))[0] or "video/mp4"
    return FileResponse(
        path=stream_path,
        media_type=media_type,
        filename=stream_path.name if stream_path != video_path else video["source_filename"],
    )


async def create_video(
    connection: sqlite3.Connection,
    upload_file: UploadFile,
    title: str,
    course_name: str,
    reference_summary: str,
    module_week: Optional[str],
    description: Optional[str],
    is_published: bool,
    current_user: dict,
    workspace_id: Optional[int] = None,
) -> dict:
    reference_summary = _clean_reference_summary(reference_summary)

    if workspace_id is not None:
        workspace_row = connection.execute(
            """
            SELECT id, name
            FROM teacher_workspaces
            WHERE id = ? AND teacher_id = ?
            """,
            (workspace_id, current_user["id"]),
        ).fetchone()
        if not workspace_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        course_name = workspace_row["name"]

    original_name = upload_file.filename or "uploaded_video.mp4"
    safe_name = "{}_{}".format(int(time.time()), sanitize_filename(original_name))
    destination = settings.upload_dir / safe_name

    await save_upload_file(upload_file, destination)
    file_size_bytes = destination.stat().st_size

    try:
        video_id = _insert_video_record(
            connection,
            title=title,
            course_name=course_name,
            reference_summary=reference_summary,
            module_week=module_week,
            description=description,
            source_filename=original_name,
            stored_path=str(Path("backend/storage/uploads") / safe_name),
            file_size_bytes=file_size_bytes,
            is_published=is_published,
            current_user=current_user,
            workspace_id=workspace_id,
        )
    except sqlite3.OperationalError as error:
        if destination.exists():
            destination.unlink()

        if is_database_locked(error):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "The SQLite database is locked. Close DB Browser for SQLite or any other app "
                    "using thinknote_ai.db, then try the upload again."
                ),
            ) from error
        raise

    return get_video_by_id(connection, int(video_id), current_user)


def create_video_from_youtube(
    connection: sqlite3.Connection,
    video_url: str,
    title: str,
    course_name: str,
    reference_summary: str,
    module_week: Optional[str],
    description: Optional[str],
    is_published: bool,
    current_user: dict,
    workspace_id: Optional[int] = None,
) -> dict:
    reference_summary = _clean_reference_summary(reference_summary)

    if workspace_id is not None:
        workspace_row = connection.execute(
            """
            SELECT id, name
            FROM teacher_workspaces
            WHERE id = ? AND teacher_id = ?
            """,
            (workspace_id, current_user["id"]),
        ).fetchone()
        if not workspace_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")
        course_name = workspace_row["name"]

    cleaned_url = video_url.strip()
    if not _is_supported_youtube_url(cleaned_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid YouTube video URL.",
        )

    if YoutubeDL is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube import requires yt-dlp. Install dependencies with: pip install -r requirements.txt",
        )

    safe_title = sanitize_filename(title or "youtube_lecture")
    unique_prefix = "{}_{}".format(int(time.time()), safe_title)
    output_template = str(settings.upload_dir / (unique_prefix + ".%(ext)s"))
    downloaded_path: Path | None = None

    ydl_options = {
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt/srt/best",
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"node": {}},
    }
    _apply_ytdlp_cookie_options(ydl_options)

    try:
        info = _download_youtube_with_fallbacks(cleaned_url, ydl_options)
        with YoutubeDL(ydl_options) as ydl:
            prepared = ydl.prepare_filename(info)
            candidate_path = Path(prepared)
            if not candidate_path.exists():
                merged_path = candidate_path.with_suffix(".mp4")
                if merged_path.exists():
                    candidate_path = merged_path

            if not candidate_path.exists():
                raise FileNotFoundError("Downloaded YouTube video file was not found.")

            downloaded_path = candidate_path
            source_title = info.get("title") or title or "YouTube lecture"
            source_filename = downloaded_path.name
            relative_path = str(Path("backend/storage/uploads") / source_filename)
            file_size_bytes = downloaded_path.stat().st_size

        try:
            video_id = _insert_video_record(
                connection,
                title=title or source_title,
                course_name=course_name,
                reference_summary=reference_summary,
                module_week=module_week,
                description=(description or "").strip() or "Imported from YouTube: {}".format(cleaned_url),
                source_filename=source_filename,
                stored_path=relative_path,
                file_size_bytes=file_size_bytes,
                is_published=is_published,
                current_user=current_user,
                workspace_id=workspace_id,
            )
        except sqlite3.OperationalError as error:
            if downloaded_path and downloaded_path.exists():
                downloaded_path.unlink()
            if is_database_locked(error):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "The SQLite database is locked. Close DB Browser for SQLite or any other app "
                        "using thinknote_ai.db, then try the YouTube import again."
                    ),
                ) from error
            raise
    except HTTPException:
        raise
    except Exception as error:
        if downloaded_path and downloaded_path.exists():
            downloaded_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not download YouTube video: {}".format(error),
        ) from error

    return get_video_by_id(connection, video_id, current_user)


def assign_video_to_student(
    connection: sqlite3.Connection,
    video_id: int,
    student_email: str,
    current_user: dict,
) -> dict:
    video_row = connection.execute(
        """
        SELECT videos.*, users.full_name AS owner_name
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE videos.id = ?
        """,
        (video_id,),
    ).fetchone()

    if not video_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    if current_user["role"] == "teacher" and video_row["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only assign your own videos.")

    cleaned_email = student_email.strip().lower()
    student_row = connection.execute(
        """
        SELECT id, email, role, is_active
        FROM users
        WHERE email = ?
        """,
        (cleaned_email,),
    ).fetchone()

    if not student_row or student_row["role"] != "student" or not bool(student_row["is_active"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active student account not found.")

    connection.execute(
        """
        INSERT OR IGNORE INTO video_assignments (video_id, student_id, assigned_by)
        VALUES (?, ?, ?)
        """,
        (video_id, student_row["id"], current_user["id"]),
    )
    connection.execute("UPDATE videos SET is_published = 1 WHERE id = ?", (video_id,))
    commit_with_retry(connection)

    return {
        "message": "Video assigned to student.",
        "video_id": video_id,
        "student_id": student_row["id"],
        "student_email": student_row["email"],
    }


def assign_video_to_registered_students(
    connection: sqlite3.Connection,
    video_id: int,
    current_user: dict,
) -> dict:
    video_row = connection.execute(
        """
        SELECT videos.*, users.full_name AS owner_name
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE videos.id = ?
        """,
        (video_id,),
    ).fetchone()

    if not video_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    if current_user["role"] == "teacher" and video_row["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only assign your own videos.")

    student_rows = connection.execute(
        """
        SELECT users.id, users.email
        FROM course_registrations
        JOIN users ON users.id = course_registrations.student_id
        WHERE course_registrations.teacher_id = ?
        AND course_registrations.course_name = ?
        AND course_registrations.status = 'accepted'
        AND users.role = 'student'
        AND users.is_active = 1
        ORDER BY users.full_name ASC, users.email ASC
        """,
        (video_row["owner_id"], video_row["course_name"]),
    ).fetchall()

    if not student_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No accepted students are registered for this course.",
        )

    assigned_count = 0
    for student in student_rows:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO video_assignments (video_id, student_id, assigned_by)
            VALUES (?, ?, ?)
            """,
            (video_id, student["id"], current_user["id"]),
        )
        assigned_count += int(cursor.rowcount or 0)

    connection.execute("UPDATE videos SET is_published = 1 WHERE id = ?", (video_id,))
    commit_with_retry(connection)

    total_students = len(student_rows)
    already_assigned_count = total_students - assigned_count
    return {
        "message": "Video assigned to registered course students.",
        "video_id": video_id,
        "course_name": video_row["course_name"],
        "assigned_count": assigned_count,
        "already_assigned_count": already_assigned_count,
        "total_registered_students": total_students,
    }


def assign_video_to_all_students(
    connection: sqlite3.Connection,
    video_id: int,
    current_user: dict,
) -> dict:
    video_row = connection.execute(
        """
        SELECT videos.*, users.full_name AS owner_name
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE videos.id = ?
        """,
        (video_id,),
    ).fetchone()

    if not video_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    if current_user["role"] == "teacher" and video_row["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only assign your own videos.")

    student_rows = connection.execute(
        """
        SELECT id, email
        FROM users
        WHERE role = 'student'
        AND is_active = 1
        ORDER BY full_name ASC, email ASC
        """
    ).fetchall()

    if not student_rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active student accounts were found.")

    assigned_count = 0
    for student in student_rows:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO video_assignments (video_id, student_id, assigned_by)
            VALUES (?, ?, ?)
            """,
            (video_id, student["id"], current_user["id"]),
        )
        assigned_count += int(cursor.rowcount or 0)

    connection.execute("UPDATE videos SET is_published = 1 WHERE id = ?", (video_id,))
    commit_with_retry(connection)

    total_students = len(student_rows)
    already_assigned_count = total_students - assigned_count
    return {
        "message": "Video assigned to all active students.",
        "video_id": video_id,
        "course_name": video_row["course_name"],
        "assigned_count": assigned_count,
        "already_assigned_count": already_assigned_count,
        "total_registered_students": total_students,
    }
