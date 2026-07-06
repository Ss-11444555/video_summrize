"""Educational visual understanding API routes."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile

from ai.vision.educational_pipeline import understand_image
from backend.app.core.dependencies import get_current_user
from backend.app.schemas.educational_vision_schema import EducationalImageAnalysisResponse


router = APIRouter(prefix="/education/vision", tags=["Educational Vision"])


@router.post("/analyze-image", response_model=EducationalImageAnalysisResponse)
async def analyze_educational_image(
    image_file: UploadFile = File(...),
    question: Optional[str] = Form(default=None),
    current_user: dict = Depends(get_current_user),
):
    suffix = Path(image_file.filename or "educational-image.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
        temporary_path = Path(temporary_file.name)
        temporary_file.write(await image_file.read())

    try:
        understanding = understand_image(temporary_path, question=question)
    finally:
        temporary_path.unlink(missing_ok=True)

    return {
        "topic": understanding.explanation.topic,
        "summary": understanding.explanation.summary,
        "explanation": understanding.explanation.explanation,
        "key_concepts": understanding.explanation.key_concepts,
        "visual_type": understanding.vision.visual_type,
        "ocr_text": understanding.ocr.text,
        "equations_latex": understanding.equations.latex,
        "equation_image_paths": [str(path) for path in understanding.equations.image_paths],
        "clip_topics": understanding.embeddings.topics,
        "components": {
            "ocr": {
                "engine": understanding.ocr.engine,
                "status": understanding.ocr.status,
                "error": understanding.ocr.error,
            },
            "equation_recognition": {
                "engine": understanding.equations.engine,
                "status": understanding.equations.status,
                "error": understanding.equations.error,
            },
            "vision_language_model": {
                "model_name": understanding.vision.model_name,
                "status": understanding.vision.status,
                "error": understanding.vision.error,
            },
            "clip_embeddings": {
                "model_name": understanding.embeddings.model_name,
                "status": understanding.embeddings.status,
                "error": understanding.embeddings.error,
            },
            "reasoning_llm": {
                "model_name": understanding.explanation.model_name,
                "status": understanding.explanation.status,
            },
        },
        "evidence": understanding.explanation.evidence,
    }
