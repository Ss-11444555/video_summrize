"""Tests for structured summarization schema expectations."""

from __future__ import annotations

import unittest

from ai.summarization.llm_service import LectureSummaryOutput


class SummarizationSchemaTests(unittest.TestCase):
    def test_student_study_guide_schema_keeps_legacy_and_detailed_fields(self):
        schema = LectureSummaryOutput.model_json_schema()
        required = set(schema["required"])

        self.assertTrue(
            {
                "summary_title",
                "main_topic",
                "summary_text",
                "key_concepts",
                "important_points",
                "examples",
                "revision_notes",
            }.issubset(required)
        )
        self.assertTrue(
            {
                "detailed_topic_notes",
                "definitions_and_terms",
                "visual_and_equation_notes",
                "final_understanding",
            }.issubset(required)
        )


if __name__ == "__main__":
    unittest.main()
