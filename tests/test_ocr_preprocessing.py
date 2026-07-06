"""Tests for OCR preprocessing helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from ai.vision.models import OCRBlock
from ai.vision.ocr_service import (
    _build_ocr_variants,
    _prepare_ocr_blocks_for_result,
    _scale_blocks_for_original_image,
    _score_blocks,
)


class OCRPreprocessingTests(unittest.TestCase):
    def test_dark_slide_gets_inverted_variant(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "dark_slide.jpg"
            image = np.zeros((80, 160, 3), dtype=np.uint8)
            cv2.putText(image, "Slide Text", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
            cv2.imwrite(str(image_path), image)

            variant_names = [name for name, _ in _build_ocr_variants(image_path)]

            self.assertIn("original", variant_names)
            self.assertIn("upscaled", variant_names)
            self.assertIn("upscaled_3x", variant_names)
            self.assertIn("contrast", variant_names)
            self.assertIn("denoised", variant_names)
            self.assertIn("sharpened", variant_names)
            self.assertIn("adaptive_threshold", variant_names)
            self.assertIn("otsu_threshold", variant_names)
            self.assertIn("inverted_dark_slide", variant_names)

    def test_ocr_score_prefers_more_confident_longer_text(self):
        weak = [OCRBlock(text="AI", confidence=0.4)]
        strong = [OCRBlock(text="Five multi-agent strategies", confidence=0.8)]

        self.assertGreater(_score_blocks(strong), _score_blocks(weak))

    def test_scale_blocks_handles_three_times_upscale(self):
        blocks = [
            OCRBlock(
                text="small text",
                confidence=0.9,
                bbox=[[30.0, 60.0], [90.0, 60.0], [90.0, 90.0], [30.0, 90.0]],
            )
        ]

        scaled = _scale_blocks_for_original_image(blocks, "paddleocr:upscaled_3x")

        self.assertEqual(scaled[0].bbox[0], [10.0, 20.0])
        self.assertEqual(scaled[0].bbox[2], [30.0, 30.0])

    def test_ocr_filter_drops_presenter_side_noise_when_slide_side_dominates(self):
        blocks = [
            OCRBlock(text="differentiation", confidence=0.95, bbox=[[746, 31], [1227, 31], [1227, 82], [746, 82]]),
            OCRBlock(text="Finding the Equation", confidence=0.96, bbox=[[803, 135], [1000, 135], [1000, 152], [803, 152]]),
            OCRBlock(text="Measuring Instantaneous Velocity", confidence=0.96, bbox=[[842, 432], [1132, 432], [1132, 448], [842, 448]]),
            OCRBlock(text="x", confidence=0.93, bbox=[[1129, 180], [1138, 180], [1138, 190], [1129, 190]]),
            OCRBlock(text="wey", confidence=0.64, bbox=[[344, 219], [435, 219], [435, 276], [344, 276]]),
            OCRBlock(text="LX", confidence=0.44, bbox=[[465, 426], [487, 426], [487, 455], [465, 455]]),
        ]

        filtered = _prepare_ocr_blocks_for_result(blocks, "tesseract:psm6:original", (720, 1280, 3))
        texts = [block.text for block in filtered]

        self.assertIn("differentiation", texts)
        self.assertIn("x", texts)
        self.assertNotIn("wey", texts)
        self.assertNotIn("LX", texts)


if __name__ == "__main__":
    unittest.main()
