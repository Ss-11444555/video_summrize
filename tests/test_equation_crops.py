"""Tests for preserving original equation image crops."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from ai.vision.equation_service import _save_equation_crops
from ai.vision.models import OCRBlock


class EquationCropTests(unittest.TestCase):
    def test_math_ocr_block_saves_original_image_crop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "frame.jpg"
            output_dir = root / "equation_crops"
            image = np.full((120, 240, 3), 255, dtype=np.uint8)
            cv2.putText(image, "f'(x)=(x+h-x)/h", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
            cv2.imwrite(str(image_path), image)

            crops = _save_equation_crops(
                image_path,
                [
                    OCRBlock(
                        text="f'(x)=(x+h-x)/h",
                        confidence=0.9,
                        bbox=[[20, 48], [190, 48], [190, 76], [20, 76]],
                    )
                ],
                output_dir,
            )

            self.assertEqual(len(crops), 1)
            self.assertTrue(crops[0].exists())
            crop = cv2.imread(str(crops[0]))
            self.assertIsNotNone(crop)
            self.assertLess(crop.shape[0], image.shape[0])
            self.assertLess(crop.shape[1], image.shape[1])


if __name__ == "__main__":
    unittest.main()
