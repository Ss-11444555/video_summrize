"""Educational multimodal visual understanding pipeline."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from backend.app.core.config import settings

from ai.vision.annotation_service import save_annotated_frame
from ai.vision.clip_service import classify_image_topics
from ai.vision.equation_service import extract_equations
from ai.vision.models import EducationalExplanation, FrameUnderstanding
from ai.vision.ocr_service import extract_text
from ai.vision.reasoning_service import generate_educational_explanation
from ai.vision.vlm_service import analyze_image_semantics


def _has_formula_evidence(ocr_text: str, equations: List[str]) -> bool:
    if equations:
        return True
    normalized = ocr_text.casefold()
    return any(token in normalized for token in ("=", "\\frac", "\\sum", "\\int", "\\sqrt", "slope", "integral", "derivative"))


def _has_graph_evidence(ocr_text: str, explanation_text: str) -> bool:
    normalized = " ".join([ocr_text, explanation_text]).casefold()
    return any(
        token in normalized
        for token in (
            "x-axis",
            "y-axis",
            "axis",
            "plot",
            "graph",
            "chart",
            "loss",
            "epoch",
            "bar chart",
            "line graph",
        )
    )


def _has_diagram_evidence(ocr_text: str, explanation_text: str) -> bool:
    normalized = " ".join([ocr_text, explanation_text]).casefold()
    return any(
        token in normalized
        for token in (
            "diagram",
            "flowchart",
            "arrow",
            "connected layers",
            "input layer",
            "hidden layer",
            "output layer",
            "neural network",
        )
    )


def _is_supported_visual_concept(concept: str, explanation: EducationalExplanation) -> bool:
    normalized = concept.casefold()
    ocr_text = str(explanation.evidence.get("ocr_text") or "")
    equations = explanation.evidence.get("equations") or []
    explanation_text = " ".join([explanation.summary, explanation.explanation])

    if "equation" in normalized or "formula" in normalized:
        return _has_formula_evidence(ocr_text, list(equations))
    if "graph" in normalized or "chart" in normalized or "plot" in normalized:
        return _has_graph_evidence(ocr_text, explanation_text)
    if "diagram" in normalized or "flowchart" in normalized or "network" in normalized:
        return _has_diagram_evidence(ocr_text, explanation_text)
    return True


def _compose_caption(explanation: EducationalExplanation) -> str:
    concepts = [
        concept
        for concept in explanation.key_concepts[:5]
        if _is_supported_visual_concept(concept, explanation)
    ]
    parts = [
        "Topic: {}".format(explanation.topic),
        "Summary: {}".format(explanation.summary),
        "Explanation: {}".format(explanation.explanation),
    ]
    if concepts:
        parts.append("Key concepts: {}".format(", ".join(concepts)))
    return "\n".join(part for part in parts if part).strip()


def understand_image(
    image_path: Path,
    *,
    question: Optional[str] = None,
    annotated_output_dir: Optional[Path] = None,
) -> FrameUnderstanding:
    """Run OCR, equation extraction, VLM analysis, CLIP, and LLM reasoning for one image."""

    ocr = extract_text(
        image_path,
        language=settings.ocr_language,
        use_gpu=settings.enable_gpu,
        min_confidence=settings.ocr_min_confidence,
    )
    equations = extract_equations(
        image_path,
        ocr_text=ocr.text,
        nougat_command=settings.nougat_command,
        force_model_ocr=settings.force_math_ocr,
    )
    vision = analyze_image_semantics(
        image_path,
        ocr=ocr,
        equations=equations,
        model_name=settings.vision_language_model,
        provider=settings.vision_language_provider,
        use_gpu=settings.enable_gpu,
        allow_downloads=settings.allow_model_downloads,
        question=question,
    )
    embeddings = classify_image_topics(
        image_path,
        model_name=settings.clip_model,
        use_gpu=settings.enable_gpu,
    )
    explanation = generate_educational_explanation(
        ocr=ocr,
        equations=equations,
        vision=vision,
        embeddings=embeddings,
        provider=settings.reasoning_provider,
        model_name=settings.reasoning_model,
        question=question,
    )
    annotated_image_path = save_annotated_frame(
        image_path=image_path,
        output_dir=annotated_output_dir or settings.annotated_frames_dir,
        ocr=ocr,
        equations=equations,
        vision=vision,
        embeddings=embeddings,
        topic=explanation.topic,
    )

    return FrameUnderstanding(
        timestamp_seconds=0.0,
        image_path=image_path,
        filename=image_path.name,
        annotated_image_path=annotated_image_path,
        caption_text=_compose_caption(explanation),
        model_name="{} + {} + {}".format(settings.vision_language_model, settings.clip_model, settings.reasoning_model),
        ocr=ocr,
        equations=equations,
        vision=vision,
        embeddings=embeddings,
        explanation=explanation,
    )


def understand_frames(
    frames: Iterable[Dict],
    *,
    annotated_output_dir: Optional[Path] = None,
) -> List[Dict]:
    """Batch educational understanding for extracted video frames."""

    results: List[Dict] = []
    selected_frames = _select_representative_frames(list(frames), settings.max_visual_frames)
    for frame in selected_frames:
        understanding = understand_image(
            Path(frame["absolute_path"]),
            annotated_output_dir=annotated_output_dir,
        )
        results.append(
            {
                "timestamp_seconds": frame["timestamp_seconds"],
                "absolute_path": frame["absolute_path"],
                "filename": frame["filename"],
                "annotated_absolute_path": understanding.annotated_image_path,
                "annotated_filename": understanding.annotated_image_path.name if understanding.annotated_image_path else None,
                "caption_text": understanding.caption_text,
                "model_name": understanding.model_name,
                "ocr_text": understanding.ocr.text,
                "equations": understanding.equations.latex,
                "equation_images": [str(path) for path in understanding.equations.image_paths],
                "visual_type": understanding.vision.visual_type,
                "topic": understanding.explanation.topic,
                "change_score": frame.get("change_score"),
            }
        )
    return results


def _select_representative_frames(frames: List[Dict], max_frames: int) -> List[Dict]:
    if max_frames <= 0 or len(frames) <= max_frames:
        return frames
    if max_frames == 1:
        return [frames[len(frames) // 2]]

    last_index = len(frames) - 1
    selected_indexes = {
        round(index * last_index / (max_frames - 1))
        for index in range(max_frames)
    }
    return [frame for index, frame in enumerate(frames) if index in selected_indexes]


def understanding_to_api_dict(understanding: FrameUnderstanding) -> Dict:
    data = asdict(understanding)
    data["image_path"] = str(understanding.image_path)
    return data
