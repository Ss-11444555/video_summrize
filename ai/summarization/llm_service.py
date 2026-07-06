"""LLM-based structured summary generation."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


DEFAULT_SUMMARY_MODEL = "gpt-5.2"
PROMPT_VERSION = "v2_student_study_guide"
MAX_SUMMARY_OUTPUT_TOKENS = 7000


class DetailedTopicNote(BaseModel):
    topic_title: str = Field(description="Clear title for this topic or subtopic.")
    explanation: str = Field(description="Student-friendly explanation of the topic.")
    important_details: List[str] = Field(description="Important facts, steps, relationships, or technical details.")
    examples_or_visuals: List[str] = Field(description="Examples, slide details, diagrams, equations, or visual evidence.")
    student_takeaway: str = Field(description="What the student should remember from this topic.")


class LectureSummaryOutput(BaseModel):
    summary_title: str = Field(description="Short title for the generated lecture summary.")
    main_topic: str = Field(description="The central topic of the lecture in one sentence.")
    summary_text: str = Field(description="A short one-paragraph summary of the full lecture.")
    detailed_topic_notes: List[DetailedTopicNote] = Field(description="Detailed notes for all important lecture topics and subtopics.")
    key_concepts: List[str] = Field(description="Major learning concepts from the lecture.")
    important_points: List[str] = Field(description="Complete learning points that preserve important lecture information.")
    definitions_and_terms: List[str] = Field(description="Important terms and definitions explained clearly.")
    examples: List[str] = Field(description="Examples or demonstrations mentioned in the lecture.")
    visual_and_equation_notes: List[str] = Field(description="Important slide, diagram, graph, OCR, equation, or visual notes.")
    revision_notes: List[str] = Field(description="Actionable notes for student revision.")
    final_understanding: str = Field(description="What the student should understand after studying this lecture.")


def _get_openai_client():
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "The 'openai' package is not installed. Run 'pip install -r requirements.txt' first."
        ) from error

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing in the .env file.")

    return OpenAI(api_key=api_key)


def _extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    text_chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                text_chunks.append(text_value)

    return "\n".join(text_chunks).strip()


def _summary_to_dict(summary: LectureSummaryOutput) -> Dict:
    if hasattr(summary, "model_dump"):
        return summary.model_dump()
    return summary.dict()


def generate_structured_summary(
    course_name: str,
    lecture_title: str,
    processed_multimodal_text: str,
    model_name: Optional[str] = None,
) -> Dict:
    client = _get_openai_client()
    selected_model = model_name or DEFAULT_SUMMARY_MODEL

    instructions = (
        "You are an educational summarization assistant. "
        "Generate a balanced lecture study guide that includes both a short overview and detailed learning notes. "
        "Use the transcript and visual evidence together, including slide text, OCR, equations, diagrams, examples, "
        "and frame explanations when available. "
        "The goal is full student understanding, not only a brief abstract. "
        "Start with one main topic sentence and one small summary paragraph, then explain all important topics and subtopics. "
        "For each detailed topic note, include a topic title, explanation, important details, examples or visuals, "
        "and what the student should remember. "
        "Keep repetition low, but do not remove meaningful information. "
        "Use clear student-friendly language. "
        "Prefer complete coverage over extreme brevity."
    )

    user_input = (
        "Course: {course}\n"
        "Lecture Title: {title}\n\n"
        "Processed Multimodal Content:\n"
        "{content}\n\n"
        "Return a structured study guide with: main_topic, small summary_text, detailed_topic_notes, "
        "complete learning points, definitions and terms, visual and equation notes, revision notes, "
        "and final understanding. Do not make the answer too short."
    ).format(
        course=course_name,
        title=lecture_title,
        content=processed_multimodal_text,
    )

    response = client.responses.parse(
        model=selected_model,
        instructions=instructions,
        input=user_input,
        temperature=0.2,
        max_output_tokens=MAX_SUMMARY_OUTPUT_TOKENS,
        text_format=LectureSummaryOutput,
    )

    response_text = _extract_output_text(response)
    if not response_text:
        raise RuntimeError("The OpenAI response did not return any summary text.")

    parsed_summary = response.output_parsed
    if not parsed_summary:
        try:
            structured_summary = json.loads(response_text)
        except json.JSONDecodeError as error:
            raise RuntimeError("The LLM response was not valid structured summary JSON.") from error
    else:
        structured_summary = _summary_to_dict(parsed_summary)

    required_keys = {
        "summary_title",
        "main_topic",
        "summary_text",
        "detailed_topic_notes",
        "key_concepts",
        "important_points",
        "definitions_and_terms",
        "examples",
        "visual_and_equation_notes",
        "revision_notes",
        "final_understanding",
    }
    missing_keys = required_keys.difference(structured_summary.keys())
    if missing_keys:
        raise RuntimeError(
            "The LLM response is missing required summary fields: {}".format(", ".join(sorted(missing_keys)))
        )

    return {
        "summary_title": structured_summary["summary_title"],
        "summary_text": structured_summary["summary_text"],
        "structured_summary": structured_summary,
        "model_name": selected_model,
        "prompt_version": PROMPT_VERSION,
        "raw_response_text": response_text,
    }
