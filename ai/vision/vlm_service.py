"""Vision-language model adapters for semantic educational image analysis."""

from __future__ import annotations

import base64
import io
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from PIL import Image

from ai.vision.models import EquationResult, OCRResult, VisionLanguageResult


EDUCATIONAL_VISUAL_PROMPT = (
    "Analyze this educational image like a tutor reading the slide directly. Identify only visual elements "
    "that are actually visible. Read the title, headings, formulas, examples, arrows, highlighted boxes, "
    "colors, and layout when they are visible. Explain what each visible formula or example is teaching. "
    "Use OCR as helpful evidence, but inspect the image directly when OCR is noisy or incomplete. Do not infer "
    "graphs, charts, formulas, code, tables, or diagrams unless they are visibly present. If a formula is visible "
    "but partly unreadable, state the readable structure and mark the uncertain part instead of inventing it."
)


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


def _image_to_data_url(image_path: Path) -> str:
    image = Image.open(image_path).convert("RGB")
    image.thumbnail((1536, 1536))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=86)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/jpeg;base64,{}".format(encoded)


@lru_cache(maxsize=1)
def _load_hf_vlm(model_name: str, use_gpu: bool, allow_downloads: bool):
    try:
        import torch  # type: ignore
        from transformers import AutoModelForVision2Seq, AutoProcessor  # type: ignore
    except ImportError as error:
        raise RuntimeError("Transformers and torch are required for local LLaVA/Qwen2-VL inference.") from error

    processor = AutoProcessor.from_pretrained(
        model_name,
        trust_remote_code=True,
        local_files_only=not allow_downloads,
    )
    dtype = torch.float16 if use_gpu and torch.cuda.is_available() else torch.float32
    model = AutoModelForVision2Seq.from_pretrained(
        model_name,
        torch_dtype=dtype,
        device_map="auto" if use_gpu and torch.cuda.is_available() else None,
        trust_remote_code=True,
        local_files_only=not allow_downloads,
    )
    if not (use_gpu and torch.cuda.is_available()):
        model.to("cpu")
    model.eval()
    return processor, model, torch


def _analyze_with_openai(image_path: Path, model_name: str, prompt: str) -> str:
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": _image_to_data_url(image_path)},
                ],
            }
        ],
        temperature=0.1,
        max_output_tokens=700,
    )
    return _extract_output_text(response)


def _analyze_with_hf(image_path: Path, model_name: str, prompt: str, use_gpu: bool, allow_downloads: bool) -> str:
    processor, model, torch = _load_hf_vlm(model_name, use_gpu, allow_downloads)
    image = Image.open(image_path).convert("RGB")
    inputs = processor(text=prompt, images=image, return_tensors="pt")
    inputs = {key: value.to(model.device) for key, value in inputs.items()}
    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=400)
    return processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()


def _infer_visual_type(ocr_text: str, equations: List[str], analysis_text: str) -> str:
    evidence_text = " ".join([ocr_text, " ".join(equations)]).casefold()
    analysis = analysis_text.casefold()
    combined = " ".join([evidence_text, analysis])
    has_equation_text = bool(equations) or any(
        token in evidence_text
        for token in ("=", "\\frac", "\\sum", "\\int", "\\sqrt", "slope", "integral", "derivative")
    )
    if has_equation_text:
        return "equation"

    has_graph_evidence = any(token in evidence_text for token in ("epoch", "loss", "axis", "plot", "graph", "chart")) or any(
        phrase in analysis
        for phrase in (
            "visible graph",
            "visible chart",
            "line graph",
            "bar chart",
            "x-axis",
            "y-axis",
            "data plot",
        )
    )
    if has_graph_evidence:
        return "graph"

    has_neural_diagram_evidence = any(token in evidence_text for token in ("layer", "neural", "network", "architecture")) or any(
        phrase in analysis
        for phrase in (
            "visible neural network",
            "network diagram",
            "connected layers",
            "input layer",
            "hidden layer",
            "output layer",
        )
    )
    if has_neural_diagram_evidence:
        return "neural_network_diagram"
    if any(token in combined for token in ("def ", "class ", "return", "function", "code")):
        return "code_screenshot"
    if any(token in combined for token in ("table", "row", "column")):
        return "table"
    if any(token in combined for token in ("flow", "arrow", "process", "step")):
        return "flowchart"
    return "educational_image"


def analyze_image_semantics(
    image_path: Path,
    *,
    ocr: OCRResult,
    equations: EquationResult,
    model_name: str,
    provider: str,
    use_gpu: bool,
    allow_downloads: bool,
    question: Optional[str] = None,
) -> VisionLanguageResult:
    context_prompt = (
        "{base}\n\n"
        "OCR text:\n{ocr}\n\n"
        "Detected equations:\n{equations}\n\n"
        "Question: {question}\n\n"
        "If OCR and detected equations are empty, inspect the image directly and describe the visible slide content. "
        "Do not say the image is equation-focused unless a formula or equation is visibly present. "
        "Do not mention graphs, charts, diagrams, tables, or code unless those elements are visibly present.\n\n"
        "Return sections: Topic, What is visible, Formulas/examples, Educational meaning, Key observations. "
        "For formulas/examples, include the exact visible expression when readable and explain the symbols."
    ).format(
        base=EDUCATIONAL_VISUAL_PROMPT,
        ocr=ocr.text or "No OCR text detected.",
        equations=", ".join(equations.latex) or "No equations detected.",
        question=question or "Explain this educational image.",
    )

    try:
        if provider == "openai":
            analysis_text = _analyze_with_openai(image_path, model_name, context_prompt)
        else:
            analysis_text = _analyze_with_hf(image_path, model_name, context_prompt, use_gpu, allow_downloads)
    except Exception as error:
        fallback = _heuristic_explanation(ocr.text, equations.latex)
        return VisionLanguageResult(
            topic=fallback["topic"],
            explanation=fallback["explanation"],
            visual_type=_infer_visual_type(ocr.text, equations.latex, fallback["explanation"]),
            key_observations=fallback["observations"],
            model_name=model_name,
            status="unavailable",
            error=str(error),
        )

    lines = [line.strip(" -") for line in analysis_text.splitlines() if line.strip()]
    topic = lines[0].replace("Topic:", "").strip() if lines else "Educational visual content"
    return VisionLanguageResult(
        topic=topic[:180],
        explanation=analysis_text,
        visual_type=_infer_visual_type(ocr.text, equations.latex, analysis_text),
        key_observations=lines[1:6],
        model_name=model_name,
        status="ok",
    )


def _heuristic_explanation(ocr_text: str, equations: List[str]) -> dict:
    combined = " ".join([ocr_text, " ".join(equations)]).casefold()
    if "y" in combined and "=" in combined and ("mx" in combined or "m x" in combined):
        return {
            "topic": "Linear equations",
            "explanation": "This appears to show the slope-intercept form of a linear equation, where m is the slope and b is the y-intercept.",
            "observations": ["A visible equation uses y as a dependent variable.", "The expression describes a straight-line relationship."],
        }
    if "loss" in combined and "epoch" in combined:
        return {
            "topic": "Machine learning training loss",
            "explanation": "This graph appears to show training loss over epochs; a decreasing loss trend indicates that the model is converging during training.",
            "observations": ["The graph references loss and epochs.", "The educational focus is model optimization."],
        }
    if "neural" in combined or "layer" in combined:
        return {
            "topic": "Neural network architecture",
            "explanation": "This diagram appears to represent a neural network structure with connected layers that transform inputs into outputs.",
            "observations": ["Layer terminology is visible.", "The image likely explains model structure."],
        }
    return {
        "topic": "Educational visual content",
        "explanation": "The image contains educational material. OCR and equation evidence should be combined with a vision-language model for deeper explanation.",
        "observations": [text for text in ocr_text.splitlines()[:3] if text],
    }
