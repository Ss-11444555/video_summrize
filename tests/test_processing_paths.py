"""Tests for processing artifact path helpers."""

from __future__ import annotations

import unittest

from backend.app.core.config import settings
from backend.app.services import processing_service


class ProcessingPathTests(unittest.TestCase):
    def test_video_artifact_folder_name_uses_video_id_and_safe_title(self):
        self.assertEqual(
            processing_service._video_artifact_folder_name(42, "Week 1: OCR / Slides"),
            "video_42_Week_1_OCR_Slides",
        )

    def test_annotated_absolute_path_is_stored_relative_to_project(self):
        annotated_path = (
            settings.database_path.parent
            / "backend"
            / "storage"
            / "annotated_frames"
            / "video_42_Week_1"
            / "frame_0001_annotated.jpg"
        )

        self.assertEqual(
            processing_service._caption_annotated_frame_path(
                {"annotated_absolute_path": annotated_path}
            ),
            "backend/storage/annotated_frames/video_42_Week_1/frame_0001_annotated.jpg",
        )


if __name__ == "__main__":
    unittest.main()
