"""Shared data models for educational visual understanding."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class OCRBlock:
    text: str
    confidence: float = 0.0
    bbox: Optional[List[List[float]]] = None


@dataclass(frozen=True)
class OCRResult:
    text: str
    language: Optional[str]
    blocks: List[OCRBlock] = field(default_factory=list)
    engine: str = "paddleocr"
    status: str = "ok"
    error: Optional[str] = None


@dataclass(frozen=True)
class EquationResult:
    latex: List[str] = field(default_factory=list)
    image_paths: List[Path] = field(default_factory=list)
    engine: str = "math-ocr"
    status: str = "ok"
    error: Optional[str] = None


@dataclass(frozen=True)
class VisionLanguageResult:
    topic: str
    explanation: str
    visual_type: str
    key_observations: List[str] = field(default_factory=list)
    model_name: str = "vision-language"
    status: str = "ok"
    error: Optional[str] = None


@dataclass(frozen=True)
class EmbeddingResult:
    topics: List[str] = field(default_factory=list)
    model_name: str = "clip"
    status: str = "ok"
    error: Optional[str] = None


@dataclass(frozen=True)
class EducationalExplanation:
    topic: str
    summary: str
    explanation: str
    key_concepts: List[str]
    evidence: Dict[str, object]
    model_name: str
    status: str = "ok"


@dataclass(frozen=True)
class FrameUnderstanding:
    timestamp_seconds: float
    image_path: Path
    filename: str
    annotated_image_path: Optional[Path]
    caption_text: str
    model_name: str
    ocr: OCRResult
    equations: EquationResult
    vision: VisionLanguageResult
    embeddings: EmbeddingResult
    explanation: EducationalExplanation
