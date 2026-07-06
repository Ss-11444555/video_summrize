"""LLM-backed chat agent scoped to one processed video."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import Optional

from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.services.result_service import get_video_result


MAX_CONTEXT_MOMENTS = 8
MAX_CONTEXT_CHARS = 9000
MAX_CHAT_OUTPUT_TOKENS = 900

STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "can",
    "could",
    "does",
    "for",
    "from",
    "give",
    "how",
    "into",
    "jump",
    "lecture",
    "me",
    "move",
    "part",
    "please",
    "show",
    "take",
    "tell",
    "that",
    "the",
    "there",
    "this",
    "time",
    "to",
    "video",
    "what",
    "when",
    "where",
    "why",
    "with",
    "you",
}


class VideoChatLLMOutput(BaseModel):
    answer: str = Field(description="Helpful answer grounded only in the provided video context.")
    timestamp_seconds: Optional[float] = Field(
        default=None,
        description="Best timestamp to jump to when the student asks to find or go to a part of the video.",
    )
    should_seek: bool = Field(description="True only when the user asked to navigate or find a part of the video.")
    evidence: Optional[str] = Field(default=None, description="Short context quote or paraphrase used for the answer.")


def _get_openai_client():
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as error:
        raise RuntimeError("The 'openai' package is not installed. Run 'pip install -r requirements.txt' first.") from error

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


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]+", " ", value.lower())).strip()


def _stem(token: str) -> str:
    return re.sub(r"(ing|ed|es|s)$", "", token)


def _keywords(value: str) -> list[str]:
    tokens = [_stem(token) for token in _normalize(value).split()]
    return [token for token in tokens if len(token) > 2 and token not in STOP_WORDS]


def _format_timestamp(seconds: float) -> str:
    total = max(int(seconds), 0)
    return "{:02d}:{:02d}".format(total // 60, total % 60)


def _is_navigation_message(message: str) -> bool:
    text = _normalize(message)
    return bool(re.search(r"\b(go|jump|move|take|seek|find|show|where)\b", text)) or "what time" in text


def _build_moments(result: dict) -> list[dict]:
    moments: list[dict] = []

    for caption in result.get("captions", []) or []:
        timestamp = float(caption.get("timestamp_seconds") or caption.get("transcript_start_seconds") or 0.0)
        caption_text = caption.get("caption_text") or ""
        transcript_text = caption.get("transcript_text") or ""
        text = " ".join(part for part in [caption_text, transcript_text] if part).strip()
        if text:
            moments.append(
                {
                    "timestamp_seconds": timestamp,
                    "time_label": _format_timestamp(timestamp),
                    "kind": "caption",
                    "text": text,
                }
            )

    for segment in result.get("transcript_segments", []) or []:
        text = segment.get("text") or ""
        if text.strip():
            timestamp = float(segment.get("start_seconds") or 0.0)
            moments.append(
                {
                    "timestamp_seconds": timestamp,
                    "time_label": _format_timestamp(timestamp),
                    "kind": "transcript",
                    "text": text.strip(),
                }
            )

    return moments


def _score_moment(moment: dict, message: str, query_tokens: list[str]) -> int:
    text = _normalize(moment["text"])
    query = _normalize(message)
    score = 0

    if query and query in text:
        score += 20

    for token in query_tokens:
        if re.search(r"\b{}\b".format(re.escape(token)), text):
            score += 5
        elif token in text:
            score += 2

    if moment["kind"] == "transcript":
        score += 1
    return score


def _select_relevant_moments(result: dict, message: str) -> list[dict]:
    moments = _build_moments(result)
    query_tokens = _keywords(message)

    if not moments:
        return []

    if not query_tokens:
        return moments[:MAX_CONTEXT_MOMENTS]

    ranked = sorted(
        (
            {"moment": moment, "score": _score_moment(moment, message, query_tokens)}
            for moment in moments
        ),
        key=lambda item: item["score"],
        reverse=True,
    )
    selected = [item["moment"] for item in ranked if item["score"] > 0]
    return (selected or moments)[:MAX_CONTEXT_MOMENTS]


def _build_context(result: dict, message: str) -> str:
    structured_summary = result.get("structured_summary") or {}
    summary_parts = [
        "Video title: {}".format(result.get("title") or "Untitled video"),
        "Course: {}".format(result.get("course_name") or "Unknown course"),
        "Summary: {}".format(result.get("summary_text") or "No summary available."),
    ]
    if structured_summary.get("key_concepts"):
        summary_parts.append("Key concepts: {}".format(", ".join(structured_summary["key_concepts"][:8])))
    if structured_summary.get("important_points"):
        summary_parts.append("Important points: {}".format("; ".join(structured_summary["important_points"][:8])))

    moment_lines = []
    for index, moment in enumerate(_select_relevant_moments(result, message), start=1):
        moment_lines.append(
            "[{index}] time={time} seconds={seconds:.2f} source={kind}\n{text}".format(
                index=index,
                time=moment["time_label"],
                seconds=moment["timestamp_seconds"],
                kind=moment["kind"],
                text=moment["text"][:1200],
            )
        )

    context = "\n".join(summary_parts)
    if moment_lines:
        context += "\n\nRelevant timed evidence from this same video:\n" + "\n\n".join(moment_lines)
    else:
        context += "\n\nNo timed transcript or caption evidence is available for this video."

    return context[:MAX_CONTEXT_CHARS]


def _fallback_chat_response(result: dict, message: str, error: Optional[Exception] = None) -> dict:
    moments = _select_relevant_moments(result, message)
    navigation = _is_navigation_message(message)
    prefix = "The LLM chat model is not available right now, so I used the current video's processed text. "
    if moments:
        moment = moments[0]
        evidence = moment["text"][:360]
        if navigation:
            return {
                "answer": prefix + "I found the closest matching part at {}. {}".format(moment["time_label"], evidence),
                "timestamp_seconds": moment["timestamp_seconds"],
                "should_seek": True,
                "evidence": evidence,
            }
        return {
            "answer": prefix + "Closest context from this video: {}".format(evidence),
            "timestamp_seconds": moment["timestamp_seconds"],
            "should_seek": False,
            "evidence": evidence,
        }

    return {
        "answer": prefix + (result.get("summary_text") or "I could not find enough processed content for this video yet."),
        "timestamp_seconds": None,
        "should_seek": False,
        "evidence": None,
    }


def ask_video_chat_agent(
    connection: sqlite3.Connection,
    video_id: int,
    current_user: dict,
    message: str,
) -> dict:
    cleaned_message = message.strip()
    if not cleaned_message:
        return {
            "answer": "Ask a question about the current video.",
            "timestamp_seconds": None,
            "should_seek": False,
            "evidence": None,
        }

    result = get_video_result(connection, video_id, current_user)
    context = _build_context(result, cleaned_message)
    navigation = _is_navigation_message(cleaned_message)

    instructions = (
        "You are a student learning agent inside a video summary page. "
        "Answer only from the provided current-video context. Do not use other videos or outside facts. "
        "If the context is not enough, say that the video does not provide enough information. "
        "If the student asks to go, jump, find, show, or locate a topic, choose the best timestamp from the timed evidence "
        "and set should_seek=true. For normal explanation questions, answer clearly in simple student-friendly language. "
        "Keep answers concise."
    )
    user_input = (
        "Student question: {question}\n"
        "Navigation intent detected by app: {navigation}\n\n"
        "Current video context:\n{context}"
    ).format(question=cleaned_message, navigation=str(navigation).lower(), context=context)

    try:
        client = _get_openai_client()
        response = client.responses.parse(
            model=settings.reasoning_model,
            instructions=instructions,
            input=user_input,
            temperature=0.2,
            max_output_tokens=MAX_CHAT_OUTPUT_TOKENS,
            text_format=VideoChatLLMOutput,
        )
        parsed = response.output_parsed
        if parsed:
            data = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()
        else:
            data = json.loads(_extract_output_text(response))

        if not navigation:
            data["should_seek"] = False
        return {
            "answer": data.get("answer") or "I could not answer from this video.",
            "timestamp_seconds": data.get("timestamp_seconds"),
            "should_seek": bool(data.get("should_seek")),
            "evidence": data.get("evidence"),
        }
    except Exception as error:
        return _fallback_chat_response(result, cleaned_message, error)
