"""Transcript-based equation recovery when visual extraction misses formulas."""

from __future__ import annotations

import json
import os
import re
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field


MAX_TRANSCRIPT_CONTEXT_CHARS = 2400
MAX_CAPTION_CONTEXT_CHARS = 900
MAX_OCR_CONTEXT_CHARS = 900
MAX_FALLBACK_EQUATIONS = 3

MATH_LANGUAGE_PATTERN = re.compile(
    r"("
    r"\\frac|\\lim|\\int|\\sum|=|"
    r"\b(?:equation|formula|derivative|differentiate|differentiation|integral|integrate|limit|"
    r"average rate of change|instantaneous rate|slope|secant|tangent|quotient|denominator|numerator|"
    r"f of x|f\(x\)|x plus h|x minus h|h approaches|approaches zero|over h|divided by|"
    r"power rule|chain rule|product rule|quotient rule|dx|dy|d over dx)\b"
    r")",
    re.IGNORECASE,
)

LATEX_SIGNAL_PATTERN = re.compile(
    r"(\\frac|\\lim|\\int|\\sum|\\sqrt|\\to|\\infty|[_^{}]|=|[a-zA-Z]\s*[+\-*/]\s*[a-zA-Z0-9])"
)


class TranscriptEquationOutput(BaseModel):
    equations: List[str] = Field(
        default_factory=list,
        description="Likely equations written in LaTeX, without surrounding prose.",
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Brief note explaining what transcript evidence supported the equations.",
    )


def _segment_start(segment: Dict) -> float:
    return float(segment.get("start_seconds") or segment.get("start") or 0.0)


def _segment_end(segment: Dict) -> float:
    return float(segment.get("end_seconds") or segment.get("end") or _segment_start(segment))


def _segment_text(segment: Dict) -> str:
    return str(segment.get("segment_text") or segment.get("text") or "").strip()


def _last_transcript_end(transcript_segments: List[Dict], fallback: float) -> float:
    if not transcript_segments:
        return fallback
    return max(_segment_end(segment) for segment in transcript_segments)


def _caption_timestamp(caption: Dict) -> float:
    return float(caption.get("timestamp_seconds") or caption.get("frame_timestamp_seconds") or 0.0)


def _transcript_for_interval(
    transcript_segments: Iterable[Dict],
    start_seconds: float,
    end_seconds: float,
    *,
    context_padding_seconds: float = 10.0,
) -> str:
    padded_start = max(start_seconds - context_padding_seconds, 0.0)
    padded_end = max(end_seconds + context_padding_seconds, padded_start)
    texts: List[str] = []
    for segment in transcript_segments:
        segment_start = _segment_start(segment)
        segment_end = _segment_end(segment)
        if segment_start < padded_end and segment_end >= padded_start:
            text = _segment_text(segment)
            if text:
                texts.append(text)
    return " ".join(texts).strip()


def _build_caption_intervals(captions: List[Dict], transcript_segments: List[Dict]) -> List[Dict]:
    ordered_captions = sorted(captions, key=_caption_timestamp)
    last_end = _last_transcript_end(transcript_segments, _caption_timestamp(ordered_captions[-1]) if ordered_captions else 0.0)
    intervals: List[Dict] = []

    for index, caption in enumerate(ordered_captions):
        start_seconds = _caption_timestamp(caption)
        end_seconds = _caption_timestamp(ordered_captions[index + 1]) if index + 1 < len(ordered_captions) else last_end
        if end_seconds <= start_seconds:
            end_seconds = start_seconds + 30.0
        intervals.append(
            {
                "caption": caption,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
            }
        )

    return intervals


def _has_math_language(*values: str) -> bool:
    combined = " ".join(str(value or "") for value in values)
    return bool(MATH_LANGUAGE_PATTERN.search(combined))


def _is_usable_latex(value: str) -> bool:
    text = " ".join(str(value or "").strip().split())
    if not text or len(text) > 260:
        return False
    if text.count("\\") > 24 or len(re.findall(r"[{}]", text)) > 36:
        return False
    return bool(LATEX_SIGNAL_PATTERN.search(text))


def _clean_equations(values: Iterable[str]) -> List[str]:
    equations: List[str] = []
    for value in values:
        text = " ".join(str(value or "").strip().split())
        text = text.strip("`$ ")
        if text.startswith("\\(") and text.endswith("\\)"):
            text = text[2:-2].strip()
        if text.startswith("\\[") and text.endswith("\\]"):
            text = text[2:-2].strip()
        if _is_usable_latex(text) and text not in equations:
            equations.append(text)
    return equations[:MAX_FALLBACK_EQUATIONS]


def _extract_response_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    chunks: List[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)
    return "\n".join(chunks).strip()


def infer_equations_from_transcript(
    *,
    transcript_text: str,
    ocr_text: str,
    caption_text: str,
    model_name: str,
) -> Dict:
    """Ask the reasoning LLM to recover likely LaTeX equations from spoken math."""

    transcript = transcript_text.strip()
    if not transcript or not _has_math_language(transcript, ocr_text, caption_text):
        return {"equations": [], "source": "none", "notes": "No math-like transcript context."}

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {"equations": [], "source": "none", "notes": "OPENAI_API_KEY is missing."}

    from openai import OpenAI  # type: ignore

    evidence = {
        "transcript_near_frame": transcript[:MAX_TRANSCRIPT_CONTEXT_CHARS],
        "ocr_text_from_frame": str(ocr_text or "")[:MAX_OCR_CONTEXT_CHARS],
        "frame_caption": str(caption_text or "")[:MAX_CAPTION_CONTEXT_CHARS],
    }
    instructions = (
        "Recover mathematical formulas from lecture transcript evidence when image-based equation OCR failed. "
        "Return only equations that are directly supported by the transcript/OCR/caption. "
        "Convert spoken math into valid LaTeX. Do not invent unrelated formulas. "
        "If the transcript is ambiguous, return an empty equations list. "
        "Do not include prose inside equations."
    )
    user_input = (
        "Image equation extraction found no usable equation. "
        "Use the transcript near this frame to recover the likely equation, if the teacher clearly says one.\n\n"
        "{}"
    ).format(json.dumps(evidence, ensure_ascii=True, indent=2))

    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model=model_name,
        instructions=instructions,
        input=user_input,
        temperature=0.0,
        max_output_tokens=700,
        text_format=TranscriptEquationOutput,
    )
    parsed = response.output_parsed
    if parsed:
        data = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()
    else:
        data = json.loads(_extract_response_text(response))

    equations = _clean_equations(data.get("equations") or [])
    return {
        "equations": equations,
        "source": "transcript_llm_fallback" if equations else "none",
        "notes": data.get("explanation") or "Recovered from transcript near the frame timestamp.",
    }


def apply_transcript_equation_fallbacks(
    *,
    captions: List[Dict],
    transcript_segments: Iterable[Dict],
    model_name: str,
) -> List[Dict]:
    """Fill empty visual-equation slots from nearby transcript context."""

    segment_list = [segment for segment in transcript_segments if segment]
    enriched_captions = [dict(caption) for caption in captions]
    intervals = _build_caption_intervals(enriched_captions, segment_list)

    for interval in intervals:
        caption = interval["caption"]
        current_equations = [str(equation).strip() for equation in caption.get("equations") or [] if str(equation).strip()]
        if current_equations:
            caption["equation_source"] = caption.get("equation_source") or "visual_extractor"
            continue

        transcript_text = _transcript_for_interval(
            segment_list,
            interval["start_seconds"],
            interval["end_seconds"],
        )
        if not _has_math_language(transcript_text, caption.get("ocr_text") or "", caption.get("caption_text") or ""):
            caption["equation_source"] = caption.get("equation_source") or "none"
            continue

        try:
            result = infer_equations_from_transcript(
                transcript_text=transcript_text,
                ocr_text=caption.get("ocr_text") or "",
                caption_text=caption.get("caption_text") or "",
                model_name=model_name,
            )
        except Exception as error:
            caption["equation_source"] = "fallback_failed"
            caption["equation_fallback_notes"] = str(error)
            continue

        if result["equations"]:
            caption["equations"] = result["equations"]
            caption["equation_source"] = result["source"]
            caption["equation_fallback_notes"] = result.get("notes")
        else:
            caption["equation_source"] = caption.get("equation_source") or "none"
            caption["equation_fallback_notes"] = result.get("notes")

    return enriched_captions
