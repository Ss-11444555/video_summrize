"""Schemas for educational visual understanding APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    engine: Optional[str] = None
    model_name: Optional[str] = None
    status: str
    error: Optional[str] = None


class EducationalImageAnalysisResponse(BaseModel):
    topic: str
    summary: str
    explanation: str
    key_concepts: List[str]
    visual_type: str
    ocr_text: str
    equations_latex: List[str]
    equation_image_paths: List[str] = Field(default_factory=list)
    clip_topics: List[str]
    components: Dict[str, ComponentStatus]
    evidence: Dict[str, Any]
