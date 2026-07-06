"""LLM reasoning over OCR, equation, CLIP, and VLM evidence."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ai.vision.models import EducationalExplanation, EmbeddingResult, EquationResult, OCRResult, VisionLanguageResult


class EducationalVisualOutput(BaseModel):
    topic: str = Field(description="Primary educational topic.")
    summary: str = Field(description="One-sentence educational summary.")
    explanation: str = Field(description="Clear step-by-step tutor explanation of the visible image.")
    key_concepts: List[str] = Field(description="Important concepts represented in the image.")


def _extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text.strip()

    chunks: List[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)
    return "\n".join(chunks).strip()


def _to_dict(parsed: EducationalVisualOutput) -> Dict:
    if hasattr(parsed, "model_dump"):
        return parsed.model_dump()
    return parsed.dict()


def _fallback_reasoning(
    vision: VisionLanguageResult,
    ocr: OCRResult,
    equations: EquationResult,
    embeddings: EmbeddingResult,
    model_name: str,
) -> EducationalExplanation:
    concepts = []
    if vision.visual_type != "educational_image":
        concepts.append(vision.visual_type.replace("_", " "))
    concepts.extend([topic.split(" (", 1)[0] for topic in embeddings.topics[:2]])
    concepts.extend(equations.latex[:2])
    concepts = [concept for index, concept in enumerate(concepts) if concept and concept not in concepts[:index]]

    return EducationalExplanation(
        topic=vision.topic,
        summary=vision.explanation.splitlines()[0][:300] if vision.explanation else vision.topic,
        explanation=vision.explanation,
        key_concepts=concepts[:6],
        evidence={
            "ocr_text": ocr.text,
            "equations": equations.latex,
            "clip_topics": embeddings.topics,
            "vision_status": vision.status,
        },
        model_name=model_name,
        status="fallback",
    )


def _has_formula_evidence(ocr: OCRResult, equations: EquationResult) -> bool:
    if equations.latex:
        return True
    text = ocr.text.casefold()
    return any(token in text for token in ("=", "\\frac", "\\sum", "\\int", "\\sqrt", "slope", "integral", "derivative"))


def _has_supported_visual_evidence(visual_type: str, vision: VisionLanguageResult, ocr: OCRResult, equations: EquationResult) -> bool:
    ocr_text = ocr.text.casefold()
    explanation_text = " ".join([vision.topic, vision.explanation, " ".join(vision.key_observations)]).casefold()

    if visual_type == "equation":
        return _has_formula_evidence(ocr, equations)
    if visual_type == "graph":
        return any(token in ocr_text for token in ("epoch", "loss", "axis", "plot", "graph", "chart")) or any(
            phrase in explanation_text
            for phrase in ("visible graph", "visible chart", "line graph", "bar chart", "x-axis", "y-axis", "data plot")
        )
    if visual_type in {"neural_network_diagram", "flowchart"}:
        return any(token in ocr_text for token in ("layer", "neural", "network", "architecture", "flow", "arrow", "process", "step")) or any(
            phrase in explanation_text
            for phrase in ("visible diagram", "network diagram", "connected layers", "input layer", "hidden layer", "flowchart")
        )
    return True


def _sanitize_unsupported_equation_claim(
    vision: VisionLanguageResult,
    ocr: OCRResult,
    equations: EquationResult,
) -> VisionLanguageResult:
    if vision.visual_type == "equation" and _has_formula_evidence(ocr, equations):
        return vision
    if vision.visual_type != "equation":
        return vision

    return VisionLanguageResult(
        topic="Educational slide",
        explanation=(
            "This frame appears to be an educational slide. No readable OCR text or equation text was extracted, "
            "so the caption should describe only visibly supported slide content and avoid equation-specific claims."
        ),
        visual_type="educational_slide",
        key_observations=vision.key_observations,
        model_name=vision.model_name,
        status=vision.status,
        error=vision.error,
    )


def _sanitize_unsupported_visual_claim(
    vision: VisionLanguageResult,
    ocr: OCRResult,
    equations: EquationResult,
) -> VisionLanguageResult:
    vision = _sanitize_unsupported_equation_claim(vision, ocr, equations)
    if _has_supported_visual_evidence(vision.visual_type, vision, ocr, equations):
        return vision

    return VisionLanguageResult(
        topic=vision.topic.replace(" (graph-focused)", "").replace(" (diagram-focused)", "").strip() or "Educational slide",
        explanation=(
            "This frame appears to be an educational slide. The caption should describe only visibly supported "
            "content and omit graph, chart, diagram, table, code, or equation claims when there is no evidence."
        ),
        visual_type="educational_slide",
        key_observations=vision.key_observations,
        model_name=vision.model_name,
        status=vision.status,
        error=vision.error,
    )


@lru_cache(maxsize=1)
def _load_local_reasoning_pipeline(model_name: str):
    try:
        import torch  # type: ignore
        from transformers import pipeline  # type: ignore
    except ImportError as error:
        raise RuntimeError("Transformers and torch are required for local Llama-style reasoning.") from error

    return pipeline(
        "text-generation",
        model=model_name,
        device_map="auto" if torch.cuda.is_available() else None,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )


def _generate_with_local_reasoner(model_name: str, evidence: Dict[str, object]) -> Dict:
    generator = _load_local_reasoning_pipeline(model_name)
    prompt = (
        "You are an educational multimodal reasoning engine. Explain the educational meaning "
        "of this visual evidence as JSON with topic, summary, explanation, and key_concepts. "
        "The explanation should teach the slide step by step: visible title, formulas, examples, "
        "arrows or highlighted regions, and what each important symbol means when evidence supports it.\n\n"
        "Evidence:\n{}\n\nJSON:"
    ).format(json.dumps(evidence, ensure_ascii=True))
    outputs = generator(prompt, max_new_tokens=700, do_sample=False)
    text = outputs[0]["generated_text"][len(prompt):].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError("Local reasoning model did not return JSON.")
    return json.loads(text[start : end + 1])


def generate_educational_explanation(
    *,
    ocr: OCRResult,
    equations: EquationResult,
    vision: VisionLanguageResult,
    embeddings: EmbeddingResult,
    provider: str,
    model_name: str,
    question: Optional[str] = None,
) -> EducationalExplanation:
    """Generate a student-facing explanation from multimodal evidence."""

    vision = _sanitize_unsupported_visual_claim(vision, ocr, equations)

    evidence = {
        "ocr_text": ocr.text,
        "equations_latex": equations.latex,
        "vision_topic": vision.topic,
        "vision_type": vision.visual_type,
        "vision_explanation": vision.explanation,
        "clip_topics": embeddings.topics,
        "question": question or "Explain this educational image.",
    }

    try:
        if provider == "local":
            data = _generate_with_local_reasoner(model_name, evidence)
        else:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                return _fallback_reasoning(vision, ocr, equations, embeddings, model_name)

            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=api_key)
            response = client.responses.parse(
                model=model_name,
                instructions=(
                    "You are an educational multimodal reasoning engine. Use OCR, equation recognition, "
                    "vision-language analysis, and CLIP topic evidence to explain the educational meaning. "
                    "Do not describe only objects. Teach the visible slide step by step. Include visible titles, "
                    "main formulas, worked examples, arrows, highlighted boxes, colors, and symbol meanings when "
                    "the evidence supports them. Explain graphs, equations, diagrams, code, tables, and slides only when evidence supports them. "
                    "Do not claim a slide is equation-focused unless equations_latex is non-empty or OCR text contains a visible formula. "
                    "When OCR/equation text is noisy but the vision-language analysis directly reads a formula, use that visual reading and note uncertainty for unclear symbols. "
                    "When OCR and equations are empty, state only what the vision analysis directly supports. "
                    "Omit graph, chart, diagram, table, code, and equation details entirely when they are not visible."
                ),
                input=json.dumps(evidence, ensure_ascii=True),
                temperature=0.15,
                max_output_tokens=900,
                text_format=EducationalVisualOutput,
            )
            parsed = response.output_parsed
            if parsed:
                data = _to_dict(parsed)
            else:
                data = json.loads(_extract_output_text(response))
    except Exception:
        return _fallback_reasoning(vision, ocr, equations, embeddings, model_name)

    return EducationalExplanation(
        topic=data["topic"],
        summary=data["summary"],
        explanation=data["explanation"],
        key_concepts=data["key_concepts"],
        evidence={
            "ocr_text": ocr.text,
            "equations": equations.latex,
            "clip_topics": embeddings.topics,
            "vision_type": vision.visual_type,
        },
        model_name=model_name,
        status="ok",
    )
