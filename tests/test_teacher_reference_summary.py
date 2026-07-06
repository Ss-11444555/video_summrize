"""Tests for teacher-written ROUGE references during video upload."""

import sqlite3
import unittest

from fastapi import HTTPException

from backend.app.services.video_service import _clean_reference_summary, _insert_video_record


class TeacherReferenceSummaryTests(unittest.TestCase):
    def test_blank_reference_summary_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            _clean_reference_summary("   ")

        self.assertEqual(context.exception.status_code, 400)

    def test_reference_summary_is_saved_with_video(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                course_name TEXT NOT NULL,
                module_week TEXT,
                description TEXT,
                source_filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_size_bytes INTEGER,
                owner_id INTEGER NOT NULL,
                workspace_id INTEGER,
                status TEXT NOT NULL,
                is_published INTEGER NOT NULL
            );
            CREATE TABLE evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL UNIQUE,
                reference_summary TEXT,
                rouge_1 REAL,
                rouge_2 REAL,
                rouge_l REAL,
                evaluation_notes TEXT
            );
            """
        )

        video_id = _insert_video_record(
            connection,
            title="Calculus Lecture",
            course_name="Mathematics",
            reference_summary="The lecture explains derivatives and the power rule.",
            module_week="Week 2",
            description=None,
            source_filename="lecture.mp4",
            stored_path="backend/storage/uploads/lecture.mp4",
            file_size_bytes=100,
            is_published=False,
            current_user={"id": 7},
        )

        evaluation = connection.execute(
            "SELECT reference_summary, evaluation_notes FROM evaluations WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        connection.close()

        self.assertEqual(
            evaluation["reference_summary"],
            "The lecture explains derivatives and the power rule.",
        )
        self.assertIn("Teacher-written", evaluation["evaluation_notes"])


if __name__ == "__main__":
    unittest.main()
