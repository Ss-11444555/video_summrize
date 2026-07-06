"""Request and response schemas for processed results."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class CaptionResponse(BaseModel):
    timestamp_seconds: float
    frame_path: Optional[str] = None
    annotated_frame_path: Optional[str] = None
    caption_text: str
    ocr_text: Optional[str] = None
    equations: List[str] = Field(default_factory=list)
    equation_images: List[str] = Field(default_factory=list)
    equation_source: Optional[str] = None
    equation_fallback_notes: Optional[str] = None
    visual_type: Optional[str] = None
    topic: Optional[str] = None
    change_score: Optional[float] = None
    transcript_text: Optional[str] = None
    transcript_start_seconds: Optional[float] = None
    transcript_end_seconds: Optional[float] = None


class TranscriptSegmentResponse(BaseModel):
    start_seconds: float
    end_seconds: float
    text: str


class SlideSummaryResponse(BaseModel):
    frame_index: int
    start_seconds: float
    end_seconds: float
    frame_path: Optional[str] = None
    annotated_frame_path: Optional[str] = None
    caption_text: str
    ocr_text: Optional[str] = None
    equations: List[str] = Field(default_factory=list)
    equation_images: List[str] = Field(default_factory=list)
    equation_source: Optional[str] = None
    equation_fallback_notes: Optional[str] = None
    visual_type: Optional[str] = None
    topic: Optional[str] = None
    transcript_text: Optional[str] = None
    summary_text: str
    key_points: List[str] = Field(default_factory=list)
    transcript_excerpt: Optional[str] = None


class RougeResponse(BaseModel):
    rouge_1: Optional[float] = None
    rouge_2: Optional[float] = None
    rouge_l: Optional[float] = None
    evaluation_notes: Optional[str] = None


class ResultResponse(BaseModel):
    video_id: int
    title: str
    course_name: str
    transcript: Optional[str] = None
    cleaned_transcript: Optional[str] = None
    transcript_segments: List[TranscriptSegmentResponse] = Field(default_factory=list)
    captions: List[CaptionResponse]
    slide_summaries: List[SlideSummaryResponse] = Field(default_factory=list)
    fused_text: Optional[str] = None
    redundancy_removed_text: Optional[str] = None
    summary_title: Optional[str] = None
    summary_text: Optional[str] = None
    structured_summary: Optional[Any] = None
    evaluation: Optional[RougeResponse] = None
