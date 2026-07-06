"""Tests for subtitle transcript extraction."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai.speech.subtitle_service import find_sidecar_subtitle, parse_subtitle_file


class SubtitleServiceTests(unittest.TestCase):
    def test_parse_vtt_subtitle_file_into_transcript_segments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "lecture.en.vtt"
            subtitle_path.write_text(
                "\n".join(
                    [
                        "WEBVTT",
                        "",
                        "00:00:01.000 --> 00:00:03.500",
                        "<c>Linear equation y = mx + b</c>",
                        "",
                        "00:00:05.000 --> 00:00:07.000",
                        "m is the slope and b is the intercept.",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = parse_subtitle_file(subtitle_path)

            self.assertEqual(result["language"], "en")
            self.assertEqual(result["segments"][0]["start"], 1.0)
            self.assertEqual(result["segments"][0]["end"], 3.5)
            self.assertIn("Linear equation y = mx + b", result["text"])
            self.assertEqual(result["model_name"], "source_subtitles")

    def test_parse_youtube_vtt_removes_overlapping_repeated_cues(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            subtitle_path = Path(temp_dir) / "lecture.en.vtt"
            subtitle_path.write_text(
                "\n".join(
                    [
                        "WEBVTT",
                        "",
                        "00:00:03.280 --> 00:00:05.430 align:start position:0%",
                        "uh<00:00:03.480><c> okay</c><00:00:03.679><c> hi</c><00:00:03.840><c> everyone</c>",
                        "",
                        "00:00:05.430 --> 00:00:05.440 align:start position:0%",
                        "uh okay hi everyone",
                        "",
                        "00:00:05.440 --> 00:00:08.030 align:start position:0%",
                        "uh okay hi everyone",
                        "I'm<00:00:05.560><c> a</c><00:00:05.720><c> first</c><00:00:06.000><c> year</c>",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = parse_subtitle_file(subtitle_path)

            self.assertEqual(result["text"], "uh okay hi everyone I'm a first year")
            self.assertEqual([segment["text"] for segment in result["segments"]], ["uh okay hi everyone", "I'm a first year"])

    def test_find_sidecar_subtitle_prefers_english(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "lecture.mp4"
            video_path.write_bytes(b"video")
            (root / "lecture.es.vtt").write_text("WEBVTT", encoding="utf-8")
            english = root / "lecture.en.vtt"
            english.write_text("WEBVTT", encoding="utf-8")

            self.assertEqual(find_sidecar_subtitle(video_path), english)


if __name__ == "__main__":
    unittest.main()
