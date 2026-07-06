"""Tests for owner-only lecture deletion."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from backend.app.services.video_service import delete_video


def _create_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE videos (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE frame_captions (
            id INTEGER PRIMARY KEY,
            video_id INTEGER NOT NULL,
            frame_path TEXT,
            annotated_frame_path TEXT,
            equation_image_paths TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
        CREATE TABLE slide_summaries (
            id INTEGER PRIMARY KEY,
            video_id INTEGER NOT NULL,
            frame_path TEXT,
            annotated_frame_path TEXT,
            equation_image_paths TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
        CREATE TABLE summaries (
            id INTEGER PRIMARY KEY,
            video_id INTEGER NOT NULL,
            summary_text TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
        """
    )
    return connection


class VideoDeletionTests(unittest.TestCase):
    def test_owner_deletes_video_database_rows_and_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            storage = root / "backend" / "storage"
            settings = SimpleNamespace(
                database_path=root / "thinknote_ai.db",
                upload_dir=storage / "uploads",
                audio_dir=storage / "audio",
                frames_dir=storage / "frames",
                annotated_frames_dir=storage / "annotated_frames",
                equation_crops_dir=storage / "equation_crops",
                results_dir=storage / "results",
            )
            for directory in (
                settings.upload_dir,
                settings.audio_dir,
                settings.frames_dir,
                settings.annotated_frames_dir,
                settings.equation_crops_dir,
                settings.results_dir,
            ):
                directory.mkdir(parents=True)

            video_path = settings.upload_dir / "lecture.mp4"
            frame_path = settings.frames_dir / "lecture_frame_0001.jpg"
            video_path.write_bytes(b"video")
            frame_path.write_bytes(b"frame")

            connection = _create_database()
            connection.execute(
                "INSERT INTO videos VALUES (1, 'Lecture', ?, 7, 'completed')",
                ("backend/storage/uploads/lecture.mp4",),
            )
            connection.execute(
                "INSERT INTO frame_captions VALUES (1, 1, ?, NULL, '[]')",
                ("backend/storage/frames/lecture_frame_0001.jpg",),
            )
            connection.execute("INSERT INTO summaries VALUES (1, 1, 'Summary')")
            connection.commit()

            with patch("backend.app.services.video_service.settings", settings):
                result = delete_video(connection, 1, {"id": 7, "role": "teacher"})

            self.assertEqual(result["video_id"], 1)
            self.assertIsNone(connection.execute("SELECT id FROM videos WHERE id = 1").fetchone())
            self.assertIsNone(connection.execute("SELECT id FROM summaries WHERE video_id = 1").fetchone())
            self.assertFalse(video_path.exists())
            self.assertFalse(frame_path.exists())
            connection.close()

    def test_teacher_cannot_delete_another_teachers_video(self):
        connection = _create_database()
        connection.execute(
            "INSERT INTO videos VALUES (1, 'Lecture', 'backend/storage/uploads/lecture.mp4', 8, 'completed')"
        )
        connection.commit()

        with self.assertRaises(HTTPException) as context:
            delete_video(connection, 1, {"id": 7, "role": "teacher"})

        self.assertEqual(context.exception.status_code, 403)
        connection.close()

    def test_processing_video_can_be_deleted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            storage = root / "backend" / "storage"
            settings = SimpleNamespace(
                database_path=root / "thinknote_ai.db",
                upload_dir=storage / "uploads",
                audio_dir=storage / "audio",
                frames_dir=storage / "frames",
                annotated_frames_dir=storage / "annotated_frames",
                equation_crops_dir=storage / "equation_crops",
                results_dir=storage / "results",
            )
            for directory in (
                settings.upload_dir,
                settings.audio_dir,
                settings.frames_dir,
                settings.annotated_frames_dir,
                settings.equation_crops_dir,
                settings.results_dir,
            ):
                directory.mkdir(parents=True)

            video_path = settings.upload_dir / "lecture.mp4"
            video_path.write_bytes(b"video")
            connection = _create_database()
            connection.execute(
                "INSERT INTO videos VALUES (1, 'Lecture', ?, 7, 'processing')",
                ("backend/storage/uploads/lecture.mp4",),
            )
            connection.commit()

            with patch("backend.app.services.video_service.settings", settings):
                result = delete_video(connection, 1, {"id": 7, "role": "teacher"})

            self.assertEqual(result["video_id"], 1)
            self.assertIsNone(connection.execute("SELECT id FROM videos WHERE id = 1").fetchone())
            self.assertFalse(video_path.exists())
            connection.close()


if __name__ == "__main__":
    unittest.main()
