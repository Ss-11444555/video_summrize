"""Regression tests for educational visual-understanding fallbacks."""

from __future__ import annotations

import unittest

from ai.vision.models import EquationResult, OCRResult, VisionLanguageResult
from ai.vision.educational_pipeline import _compose_caption
from ai.vision.models import EducationalExplanation
from ai.vision.reasoning_service import _sanitize_unsupported_equation_claim, _sanitize_unsupported_visual_claim
from ai.vision.vlm_service import _heuristic_explanation, _infer_visual_type


class EducationalVisionHeuristicTests(unittest.TestCase):
    def test_loss_graph_is_explained_as_model_convergence(self):
        explanation = _heuristic_explanation("Training loss over epoch", [])

        self.assertEqual(explanation["topic"], "Machine learning training loss")
        self.assertIn("converging", explanation["explanation"])
        self.assertEqual(_infer_visual_type("loss epoch", [], explanation["explanation"]), "graph")

    def test_slope_intercept_equation_is_explained(self):
        explanation = _heuristic_explanation("y = mx + b", ["y = mx + b"])

        self.assertEqual(explanation["topic"], "Linear equations")
        self.assertIn("slope", explanation["explanation"])
        self.assertEqual(_infer_visual_type("y = mx + b", ["y = mx + b"], explanation["explanation"]), "equation")

    def test_neural_network_diagram_is_explained(self):
        explanation = _heuristic_explanation("input layer hidden layer output layer neural network", [])

        self.assertEqual(explanation["topic"], "Neural network architecture")
        self.assertIn("connected layers", explanation["explanation"])
        self.assertEqual(
            _infer_visual_type("input layer hidden layer output layer", [], explanation["explanation"]),
            "neural_network_diagram",
        )

    def test_equation_type_requires_actual_equation_evidence(self):
        self.assertEqual(
            _infer_visual_type("", [], "This slide is equation-focused but OCR is empty."),
            "educational_image",
        )

    def test_unsupported_equation_claim_is_sanitized_before_reasoning(self):
        vision = VisionLanguageResult(
            topic="Educational slide (equation-focused)",
            explanation="No readable OCR text or LaTeX was extracted.",
            visual_type="equation",
        )
        sanitized = _sanitize_unsupported_equation_claim(
            vision,
            OCRResult(text="", language="en"),
            EquationResult(latex=[]),
        )

        self.assertEqual(sanitized.topic, "Educational slide")
        self.assertEqual(sanitized.visual_type, "educational_slide")

    def test_unsupported_graph_claim_is_sanitized_before_reasoning(self):
        vision = VisionLanguageResult(
            topic="Educational slide",
            explanation="This appears to be a graph, but no visual evidence is available.",
            visual_type="graph",
        )
        sanitized = _sanitize_unsupported_visual_claim(
            vision,
            OCRResult(text="", language="en"),
            EquationResult(latex=[]),
        )

        self.assertEqual(sanitized.visual_type, "educational_slide")

    def test_caption_is_readable_and_filters_unsupported_visual_concepts(self):
        caption = _compose_caption(
            EducationalExplanation(
                topic="Attention mechanisms",
                summary="The slide introduces attention in sequence models.",
                explanation="The text explains how attention weights help models focus on relevant tokens.",
                key_concepts=["graph", "equation", "attention"],
                evidence={"ocr_text": "Attention mechanisms in transformers", "equations": []},
                model_name="test",
            )
        )

        self.assertIn("\nSummary:", caption)
        self.assertNotIn("graph", caption.casefold())
        self.assertNotIn("equation", caption.casefold())
        self.assertIn("attention", caption.casefold())


if __name__ == "__main__":
    unittest.main()
