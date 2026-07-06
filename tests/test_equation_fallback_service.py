"""Tests for transcript-based equation fallback."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from ai.vision.equation_fallback_service import (
    _transcript_for_interval,
    apply_transcript_equation_fallbacks,
)


class EquationFallbackServiceTests(unittest.TestCase):
    def test_transcript_interval_includes_nearby_math_context(self):
        transcript = [
            {"start": 9.0, "end": 11.0, "text": "We start the derivative definition."},
            {"start": 12.0, "end": 18.0, "text": "It is f of x plus h minus f of x over h."},
            {"start": 60.0, "end": 65.0, "text": "Unrelated topic."},
        ]

        result = _transcript_for_interval(transcript, 20.0, 30.0, context_padding_seconds=10.0)

        self.assertIn("f of x plus h", result)
        self.assertNotIn("Unrelated topic", result)

    def test_fallback_fills_empty_equations_from_llm_result(self):
        captions = [
            {
                "timestamp_seconds": 10.0,
                "caption_text": "Average rate of change slide",
                "ocr_text": "",
                "equations": [],
            },
            {
                "timestamp_seconds": 50.0,
                "caption_text": "Already detected",
                "ocr_text": "",
                "equations": ["y=mx+b"],
            },
        ]
        transcript = [
            {
                "start": 12.0,
                "end": 20.0,
                "text": "The formula is f of x plus h minus f of x divided by h.",
            }
        ]

        with patch(
            "ai.vision.equation_fallback_service.infer_equations_from_transcript",
            return_value={
                "equations": [r"\frac{f(x+h)-f(x)}{h}"],
                "source": "transcript_llm_fallback",
                "notes": "Spoken derivative quotient.",
            },
        ):
            result = apply_transcript_equation_fallbacks(
                captions=captions,
                transcript_segments=transcript,
                model_name="test-model",
            )

        self.assertEqual(result[0]["equations"], [r"\frac{f(x+h)-f(x)}{h}"])
        self.assertEqual(result[0]["equation_source"], "transcript_llm_fallback")
        self.assertEqual(result[1]["equation_source"], "visual_extractor")


if __name__ == "__main__":
    unittest.main()
