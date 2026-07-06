"""Application configuration and environment loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)


def _resolve_storage_path(relative_path: str) -> Path:
    return ROOT_DIR / relative_path


def _resolve_database_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only SQLite is supported in the current project setup.")

    sqlite_path = database_url[len(prefix):]
    if sqlite_path.startswith("./"):
        sqlite_path = sqlite_path[2:]

    return ROOT_DIR / sqlite_path


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_host: str
    app_port: int
    secret_key: str
    database_url: str
    database_path: Path
    upload_dir: Path
    audio_dir: Path
    frames_dir: Path
    annotated_frames_dir: Path
    equation_crops_dir: Path
    results_dir: Path
    whisper_model: str
    whisper_fallback_model: str
    ocr_language: str
    ocr_min_confidence: float
    nougat_command: str
    vision_language_model: str
    vision_language_provider: str
    clip_model: str
    reasoning_provider: str
    reasoning_model: str
    enable_gpu: bool
    allow_model_downloads: bool
    max_visual_frames: int
    force_math_ocr: bool
    frame_interval_seconds: int
    frame_sample_seconds: int
    scene_change_threshold: float
    duplicate_frame_threshold: float
    min_frame_gap_seconds: int
    frame_jpeg_quality: int
    save_all_sampled_frames: bool
    ytdlp_cookies_file: str
    ytdlp_cookies_from_browser: str


settings = Settings(
    app_name=os.getenv("APP_NAME", "ThinkNote AI"),
    app_env=os.getenv("APP_ENV", "development"),
    app_host=os.getenv("APP_HOST", "127.0.0.1"),
    app_port=int(os.getenv("APP_PORT", "8000")),
    secret_key=os.getenv("SECRET_KEY", "change-this-secret-key"),
    database_url=os.getenv("DATABASE_URL", "sqlite:///./thinknote_ai.db"),
    database_path=_resolve_database_path(os.getenv("DATABASE_URL", "sqlite:///./thinknote_ai.db")),
    upload_dir=_resolve_storage_path(os.getenv("UPLOAD_DIR", "backend/storage/uploads")),
    audio_dir=_resolve_storage_path(os.getenv("AUDIO_DIR", "backend/storage/audio")),
    frames_dir=_resolve_storage_path(os.getenv("FRAMES_DIR", "backend/storage/frames")),
    annotated_frames_dir=_resolve_storage_path(os.getenv("ANNOTATED_FRAMES_DIR", "backend/storage/annotated_frames")),
    equation_crops_dir=_resolve_storage_path(os.getenv("EQUATION_CROPS_DIR", "backend/storage/equation_crops")),
    results_dir=_resolve_storage_path(os.getenv("RESULTS_DIR", "backend/storage/results")),
    whisper_model=os.getenv("WHISPER_MODEL", "base"),
    whisper_fallback_model=os.getenv("WHISPER_FALLBACK_MODEL", "medium"),
    ocr_language=os.getenv("OCR_LANGUAGE", "en"),
    ocr_min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.30")),
    nougat_command=os.getenv("NOUGAT_COMMAND", "").strip(),
    vision_language_model=os.getenv("VISION_LANGUAGE_MODEL", "Qwen/Qwen2-VL-2B-Instruct"),
    vision_language_provider=os.getenv("VISION_LANGUAGE_PROVIDER", "local").strip().lower(),
    clip_model=os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32"),
    reasoning_provider=os.getenv("REASONING_PROVIDER", "openai").strip().lower(),
    reasoning_model=os.getenv("REASONING_MODEL", os.getenv("LLM_MODEL", "gpt-5.2")),
    enable_gpu=os.getenv("ENABLE_GPU", "true").strip().lower() in {"1", "true", "yes"},
    allow_model_downloads=os.getenv("ALLOW_MODEL_DOWNLOADS", "false").strip().lower() in {"1", "true", "yes"},
    max_visual_frames=int(os.getenv("MAX_VISUAL_FRAMES", "0")),
    force_math_ocr=os.getenv("FORCE_MATH_OCR", "false").strip().lower() in {"1", "true", "yes"},
    frame_interval_seconds=int(os.getenv("FRAME_INTERVAL_SECONDS", "30")),
    frame_sample_seconds=int(os.getenv("FRAME_SAMPLE_SECONDS", "4")),
    scene_change_threshold=float(os.getenv("SCENE_CHANGE_THRESHOLD", "0.14")),
    duplicate_frame_threshold=float(os.getenv("DUPLICATE_FRAME_THRESHOLD", "0.04")),
    min_frame_gap_seconds=int(os.getenv("MIN_FRAME_GAP_SECONDS", "8")),
    frame_jpeg_quality=int(os.getenv("FRAME_JPEG_QUALITY", "95")),
    save_all_sampled_frames=os.getenv("SAVE_ALL_SAMPLED_FRAMES", "false").strip().lower() in {"1", "true", "yes"},
    ytdlp_cookies_file=os.getenv("YTDLP_COOKIES_FILE", "").strip(),
    ytdlp_cookies_from_browser=os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip().lower(),
)
