"""Subtitle transcript extraction before Whisper fallback."""

from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


TIMESTAMP_PATTERN = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,3})?)\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,3})?)"
)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _subtitle_time_to_seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return round(hours * 3600 + minutes * 60 + seconds, 3)


def _clean_subtitle_text(lines: List[str]) -> str:
    cleaned_lines = []
    for line in lines:
        value = html.unescape(TAG_PATTERN.sub("", line)).strip()
        if not value or value.isdigit() or value.upper().startswith("WEBVTT"):
            continue
        cleaned_lines.append(" ".join(value.split()))
    return " ".join(cleaned_lines).strip()


def _remove_overlapping_repeated_prefix(previous_text: str, current_text: str) -> str:
    previous_words = previous_text.split()
    current_words = current_text.split()
    max_overlap = min(len(previous_words), len(current_words))

    for overlap_size in range(max_overlap, 0, -1):
        if previous_words[-overlap_size:] == current_words[:overlap_size]:
            return " ".join(current_words[overlap_size:]).strip()

    return current_text


def parse_subtitle_file(subtitle_path: Path) -> Dict:
    content = subtitle_path.read_text(encoding="utf-8-sig", errors="ignore")
    lines = content.splitlines()
    segments: List[Dict] = []
    transcript_parts: List[str] = []
    index = 0

    while index < len(lines):
        match = TIMESTAMP_PATTERN.search(lines[index])
        if not match:
            index += 1
            continue

        start_seconds = _subtitle_time_to_seconds(match.group("start"))
        end_seconds = _subtitle_time_to_seconds(match.group("end"))
        index += 1
        text_lines = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1

        text = _clean_subtitle_text(text_lines)
        if text:
            new_text = _remove_overlapping_repeated_prefix(" ".join(transcript_parts), text)
            if new_text:
                transcript_parts.append(new_text)
                segments.append({"start": start_seconds, "end": end_seconds, "text": new_text})

    text = " ".join(transcript_parts).strip()
    return {
        "text": text,
        "language": _infer_language_from_subtitle_name(subtitle_path),
        "segments": segments,
        "word_count": len(text.split()),
        "model_name": "source_subtitles",
        "source": str(subtitle_path),
    }


def _infer_language_from_subtitle_name(subtitle_path: Path) -> Optional[str]:
    parts = subtitle_path.name.split(".")
    if len(parts) >= 3:
        return parts[-2]
    return None


def _sidecar_priority(path: Path) -> tuple[int, str]:
    name = path.name.casefold()
    if ".en." in name or ".en-" in name or name.endswith(".en.vtt") or name.endswith(".en.srt"):
        return (0, name)
    return (1, name)


def find_sidecar_subtitle(video_path: Path) -> Optional[Path]:
    candidates: List[Path] = []
    for extension in ("*.vtt", "*.srt"):
        candidates.extend(video_path.parent.glob("{}.*".format(video_path.stem) + extension[1:]))
        candidates.extend(video_path.parent.glob("{}{}".format(video_path.stem, extension[1:])))
    existing = [path for path in candidates if path.exists() and path.stat().st_size > 0]
    if not existing:
        return None
    return sorted(existing, key=_sidecar_priority)[0]


def _video_has_subtitles(video_path: Path) -> bool:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "s",
        "-show_entries",
        "stream=index",
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return False
    try:
        data = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return False
    return bool(data.get("streams"))


def extract_embedded_subtitle(video_path: Path) -> Optional[Path]:
    if not _video_has_subtitles(video_path):
        return None

    output_path = video_path.with_suffix(".embedded.vtt")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-map",
        "0:s:0",
        str(output_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        return None
    return output_path


def transcribe_from_existing_subtitles(video_path: Path) -> Optional[Dict]:
    subtitle_path = find_sidecar_subtitle(video_path) or extract_embedded_subtitle(video_path)
    if not subtitle_path:
        return None

    result = parse_subtitle_file(subtitle_path)
    if not result["text"]:
        return None
    return result
