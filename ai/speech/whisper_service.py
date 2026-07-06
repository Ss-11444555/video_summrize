"""Whisper transcription service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from backend.app.core.config import settings


@lru_cache(maxsize=1)
def _get_whisper_module():
    try:
        import whisper  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "The 'openai-whisper' package is not installed. Run 'pip install -r requirements.txt' first."
        ) from error

    return whisper


@lru_cache(maxsize=2)
def load_whisper_model(model_name: str):
    whisper = _get_whisper_module()
    return whisper.load_model(model_name)


def _transcribe_with_model(
    audio_path: Path,
    model_name: str,
    language: Optional[str],
) -> Dict:
    model = load_whisper_model(model_name)

    transcribe_options = {
        "task": "transcribe",
        "fp16": False,
        "verbose": False,
    }
    if language:
        transcribe_options["language"] = language

    result = model.transcribe(str(audio_path), **transcribe_options)
    segments = result.get("segments", [])

    return {
        "text": (result.get("text") or "").strip(),
        "language": result.get("language"),
        "segments": segments,
        "word_count": len((result.get("text") or "").split()),
        "model_name": model_name,
    }


def transcribe_audio_file(
    audio_path: Path,
    model_name: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict:
    selected_model = model_name or settings.whisper_model
    fallback_model = settings.whisper_fallback_model.strip()

    try:
        return _transcribe_with_model(audio_path, selected_model, language)
    except Exception:
        if not fallback_model or fallback_model == selected_model:
            raise
        return _transcribe_with_model(audio_path, fallback_model, language)
