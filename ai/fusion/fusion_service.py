"""Multimodal fusion logic for transcript and educational visual evidence."""

from __future__ import annotations

from typing import Dict, Iterable, List


def _format_caption_lines(captions: Iterable[Dict]) -> List[str]:
    lines: List[str] = []
    for caption in captions:
        timestamp = float(caption["timestamp_seconds"])
        minutes = int(timestamp // 60)
        seconds = int(timestamp % 60)
        evidence_parts = []
        if caption.get("topic"):
            evidence_parts.append("topic: {}".format(caption["topic"]))
        if caption.get("visual_type"):
            evidence_parts.append("visual type: {}".format(str(caption["visual_type"]).replace("_", " ")))
        if caption.get("equations"):
            evidence_parts.append("equations: {}".format(", ".join(caption["equations"])))
        if caption.get("ocr_text"):
            evidence_parts.append("detected text: {}".format(str(caption["ocr_text"]).replace("\n", " ")))
        evidence = " Evidence in this picture: {}".format("; ".join(evidence_parts)) if evidence_parts else ""
        lines.append(
            "[{:02d}:{:02d}] {}".format(
                minutes,
                seconds,
                caption["caption_text"].strip() + evidence,
            )
        )
    return lines


def build_multimodal_context(transcript_text: str, captions: Iterable[Dict]) -> Dict[str, str]:
    cleaned_transcript = transcript_text.strip()
    caption_lines = _format_caption_lines(captions)
    captions_block = "\n".join(caption_lines)

    fused_sections = [
        "TRANSCRIPT",
        cleaned_transcript or "No transcript available.",
        "",
        "EDUCATIONAL VISUAL EVIDENCE",
        captions_block or "No educational visual evidence available.",
    ]

    fused_text = "\n".join(fused_sections).strip()

    return {
        "transcript_text": cleaned_transcript,
        "captions_text": captions_block,
        "fused_text": fused_text,
    }
