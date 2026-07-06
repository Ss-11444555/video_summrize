"""Tests for scene-change frame extraction."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from backend.app.utils.media import extract_frames_from_video


def _write_test_video(video_path: Path, colors: list[tuple[int, int, int]], fps: int = 5) -> None:
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        float(fps),
        (96, 64),
    )
    if not writer.isOpened():
        raise RuntimeError("Could not create test video.")

    try:
        for color in colors:
            frame = np.full((64, 96, 3), color, dtype=np.uint8)
            for _ in range(fps * 5):
                writer.write(frame)
    finally:
        writer.release()


class MediaFrameExtractionTests(unittest.TestCase):
    def test_extracts_frames_at_visual_scene_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "slides.avi"
            frames_dir = root / "frames"
            _write_test_video(video_path, [(0, 0, 0), (255, 255, 255), (80, 80, 80)])

            frames = extract_frames_from_video(
                video_path=video_path,
                frames_dir=frames_dir,
                frame_interval_seconds=30,
                frame_prefix="slides",
                scene_change_threshold=0.08,
                min_frame_gap_seconds=1,
                frame_sample_seconds=1,
            )

            timestamps = [frame["timestamp_seconds"] for frame in frames]
            self.assertEqual(len(frames), 3)
            self.assertEqual(timestamps[0], 0.0)
            self.assertTrue(any(4.0 <= timestamp <= 6.0 for timestamp in timestamps))
            self.assertTrue(any(9.0 <= timestamp <= 11.0 for timestamp in timestamps))

    def test_stable_video_skips_duplicate_periodic_keyframes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "stable.avi"
            frames_dir = root / "frames"
            _write_test_video(video_path, [(120, 120, 120), (120, 120, 120), (120, 120, 120)])

            frames = extract_frames_from_video(
                video_path=video_path,
                frames_dir=frames_dir,
                frame_interval_seconds=5,
                frame_prefix="stable",
                scene_change_threshold=0.08,
                min_frame_gap_seconds=1,
                frame_sample_seconds=1,
            )

            self.assertEqual([frame["timestamp_seconds"] for frame in frames], [0.0])

    def test_duplicate_filter_skips_returning_to_recent_same_slide(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "duplicates.avi"
            frames_dir = root / "frames"
            _write_test_video(video_path, [(0, 0, 0), (255, 255, 255), (0, 0, 0)])

            frames = extract_frames_from_video(
                video_path=video_path,
                frames_dir=frames_dir,
                frame_interval_seconds=30,
                frame_prefix="duplicates",
                scene_change_threshold=0.08,
                duplicate_frame_threshold=0.04,
                min_frame_gap_seconds=1,
                frame_sample_seconds=1,
            )

            self.assertEqual([frame["timestamp_seconds"] for frame in frames], [0.0, 5.0])

    def test_save_all_sampled_frames_bypasses_duplicate_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "all_sampled.avi"
            frames_dir = root / "frames"
            _write_test_video(video_path, [(120, 120, 120), (120, 120, 120), (120, 120, 120)])

            frames = extract_frames_from_video(
                video_path=video_path,
                frames_dir=frames_dir,
                frame_interval_seconds=30,
                frame_prefix="all_sampled",
                scene_change_threshold=0.08,
                min_frame_gap_seconds=8,
                frame_sample_seconds=5,
                save_all_sampled_frames=True,
            )

            self.assertEqual([frame["timestamp_seconds"] for frame in frames], [0.0, 5.0, 10.0])

    def test_zero_sample_seconds_checks_every_video_frame_when_saving_all(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "every_frame.avi"
            frames_dir = root / "frames"
            _write_test_video(video_path, [(20, 20, 20)], fps=5)

            frames = extract_frames_from_video(
                video_path=video_path,
                frames_dir=frames_dir,
                frame_interval_seconds=30,
                frame_prefix="every_frame",
                frame_sample_seconds=0,
                save_all_sampled_frames=True,
            )

            self.assertEqual(len(frames), 25)
            self.assertEqual(frames[0]["timestamp_seconds"], 0.0)
            self.assertEqual(frames[-1]["timestamp_seconds"], 4.8)


if __name__ == "__main__":
    unittest.main()
