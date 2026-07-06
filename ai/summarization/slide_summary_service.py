"""Slide-level summaries from frame captions and matching transcript ranges."""

from __future__ import annotations

import json
import os
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from backend.app.core.config import settings


PROMPT_VERSION = "v1_slide_interval_summaries"
MAX_SLIDE_SUMMARY_OUTPUT_TOKENS = 5000
MAX_SLIDE_TRANSCRIPT_CHARS = 2200
MAX_SLIDE_CAPTION_CHARS = 1400


class SlideSummaryItem(BaseModel):
    frame_index: int = Field(description="One-based frame index from the provided slide items.")
    summary_text: str = Field(description="Concise student-friendly summary for this slide interval.")
    key_points: List[str] = Field(description="Important learning points from this slide interval.")
    transcript_excerpt: Optional[str] = Field(
        default=None,
        description="Short excerpt or paraphrase of the transcript evidence used.",
    )


class SlideSummaryOutput(BaseModel):
    slide_summaries: List[SlideSummaryItem] = Field(description="One summary for each provided slide item.")


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


def _format_seconds(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, second_value = divmod(total, 60)
    hours, minute_value = divmod(minutes, 60)
    return "{:02d}:{:02d}:{:02d}".format(hours, minute_value, second_value)


def _segment_overlaps(segment: Dict, start_seconds: float, end_seconds: float) -> bool:
    segment_start = float(segment.get("start_seconds") or segment.get("start") or 0.0)
    segment_end = float(segment.get("end_seconds") or segment.get("end") or segment_start)
    return segment_start < end_seconds and segment_end >= start_seconds


def _transcript_for_range(transcript_segments: Iterable[Dict], start_seconds: float, end_seconds: float) -> str:
    texts: List[str] = []
    for segment in transcript_segments:
        if _segment_overlaps(segment, start_seconds, end_seconds):
            text = str(segment.get("text") or segment.get("segment_text") or "").strip()
            if text:
                texts.append(text)
    return " ".join(texts).strip()


def _last_transcript_end(transcript_segments: List[Dict], fallback: float) -> float:
    if not transcript_segments:
        return fallback
    return max(
        float(segment.get("end_seconds") or segment.get("end") or segment.get("start_seconds") or 0.0)
        for segment in transcript_segments
    )


def build_slide_summary_inputs(captions: Iterable[Dict], transcript_segments: Iterable[Dict]) -> List[Dict]:
    ordered_captions = sorted(
        [caption for caption in captions if caption],
        key=lambda item: float(item.get("timestamp_seconds") or item.get("frame_timestamp_seconds") or 0.0),
    )
    ordered_segments = sorted(
        [segment for segment in transcript_segments if segment],
        key=lambda item: float(item.get("start_seconds") or item.get("start") or 0.0),
    )

    slide_inputs: List[Dict] = []
    for index, caption in enumerate(ordered_captions):
        start_seconds = float(caption.get("timestamp_seconds") or caption.get("frame_timestamp_seconds") or 0.0)
        if index + 1 < len(ordered_captions):
            end_seconds = float(
                ordered_captions[index + 1].get("timestamp_seconds")
                or ordered_captions[index + 1].get("frame_timestamp_seconds")
                or start_seconds
            )
        else:
            end_seconds = _last_transcript_end(ordered_segments, start_seconds)

        if end_seconds <= start_seconds:
            end_seconds = start_seconds

        transcript_text = _transcript_for_range(ordered_segments, start_seconds, end_seconds)
        slide_inputs.append(
            {
                "frame_index": index + 1,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "start_label": _format_seconds(start_seconds),
                "end_label": _format_seconds(end_seconds),
                "frame_path": caption.get("frame_path"),
                "annotated_frame_path": caption.get("annotated_frame_path"),
                "caption_text": str(caption.get("caption_text") or "").strip(),
                "ocr_text": str(caption.get("ocr_text") or "").strip(),
                "equations": list(caption.get("equations") or []),
                "equation_images": list(caption.get("equation_images") or caption.get("equation_image_paths") or []),
                "equation_source": caption.get("equation_source"),
                "equation_fallback_notes": caption.get("equation_fallback_notes"),
                "visual_type": caption.get("visual_type"),
                "topic": caption.get("topic"),
                "transcript_text": transcript_text,
            }
        )

    return slide_inputs


def _fallback_summary(item: Dict) -> Dict:
    transcript = str(item.get("transcript_text") or "").strip()
    caption = str(item.get("caption_text") or "").strip()
    source_text = transcript or caption or "No transcript or caption evidence is available for this slide interval."
    summary = source_text[:420].strip()
    if len(source_text) > 420:
        summary += "..."

    key_points = []
    if item.get("topic"):
        key_points.append("Topic: {}".format(item["topic"]))
    if caption:
        key_points.append(caption[:180])
    if transcript:
        key_points.append(transcript[:180])

    return {
        "frame_index": item["frame_index"],
        "summary_text": summary,
        "key_points": key_points[:3],
        "transcript_excerpt": transcript[:260] if transcript else None,
    }


def _merge_llm_output(slide_inputs: List[Dict], parsed_items: List[Dict], model_name: str) -> List[Dict]:
    by_index = {int(item.get("frame_index") or 0): item for item in parsed_items}
    summaries: List[Dict] = []
    for item in slide_inputs:
        generated = by_index.get(item["frame_index"]) or _fallback_summary(item)
        summaries.append(
            {
                **item,
                "summary_text": generated.get("summary_text") or _fallback_summary(item)["summary_text"],
                "key_points": list(generated.get("key_points") or []),
                "transcript_excerpt": generated.get("transcript_excerpt"),
                "model_name": model_name,
                "prompt_version": PROMPT_VERSION,
            }
        )
    return summaries


def generate_slide_summaries(
    captions: Iterable[Dict],
    transcript_segments: Iterable[Dict],
    model_name: Optional[str] = None,
) -> List[Dict]:
    slide_inputs = build_slide_summary_inputs(captions, transcript_segments)
    if not slide_inputs:
        return []

    selected_model = model_name or settings.reasoning_model
    llm_items = [
        {
            "frame_index": item["frame_index"],
            "time_range": "{} to {}".format(item["start_label"], item["end_label"]),
            "topic": item.get("topic"),
            "visual_type": item.get("visual_type"),
            "frame_caption": item["caption_text"][:MAX_SLIDE_CAPTION_CHARS],
            "ocr_text": item["ocr_text"][:MAX_SLIDE_CAPTION_CHARS],
            "equations": item["equations"][:8],
            "equation_source": item.get("equation_source"),
            "transcript_during_this_slide": item["transcript_text"][:MAX_SLIDE_TRANSCRIPT_CHARS],
        }
        for item in slide_inputs
    ]

    instructions = (
        "You create slide-level study summaries for a lecture video. "
        "Each item represents one slide or important frame interval. "
        "Use only the frame caption, OCR/equation evidence, and transcript spoken during that slide interval. "
        "Do not use outside facts. Do not mix evidence from other slide intervals. "
        "Write concise student-friendly summaries that explain what the teacher is covering on that slide. "
        "If the transcript is missing, summarize from the visual evidence only."
    )
    user_input = (
        "Create one summary for every slide item below. Preserve each frame_index.\n\n"
        "{items}"
    ).format(items=json.dumps(llm_items, ensure_ascii=True, indent=2))

    try:
        client = _get_openai_client()
        response = client.responses.parse(
            model=selected_model,
            instructions=instructions,
            input=user_input,
            temperature=0.2,
            max_output_tokens=MAX_SLIDE_SUMMARY_OUTPUT_TOKENS,
            text_format=SlideSummaryOutput,
        )
        parsed = response.output_parsed
        if parsed:
            data = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()
        else:
            data = json.loads(_extract_output_text(response))
        return _merge_llm_output(slide_inputs, data.get("slide_summaries") or [], selected_model)
    except Exception:
        return [
            {
                **item,
                **_fallback_summary(item),
                "model_name": "extractive_fallback",
                "prompt_version": PROMPT_VERSION,
            }
            for item in slide_inputs
        ]
