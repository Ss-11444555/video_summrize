"""CLIP semantic embedding and lightweight topic classification."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, List

from PIL import Image

from ai.vision.models import EmbeddingResult


DEFAULT_TOPIC_LABELS = (
    "machine learning loss graph",
    "linear equation",
    "neural network architecture diagram",
    "programming code screenshot",
    "data table",
    "scientific diagram",
    "flowchart",
    "lecture slide",
    "mathematical formula",
    "chart or plot",
)


@lru_cache(maxsize=1)
def _load_clip(model_name: str, use_gpu: bool):
    try:
        import torch  # type: ignore
        from transformers import CLIPModel, CLIPProcessor  # type: ignore
    except ImportError as error:
        raise RuntimeError("Transformers and torch are required for CLIP embeddings.") from error

    processor = CLIPProcessor.from_pretrained(model_name)
    model = CLIPModel.from_pretrained(model_name)
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    return processor, model, torch, device


def classify_image_topics(
    image_path: Path,
    *,
    model_name: str,
    use_gpu: bool,
    labels: Iterable[str] = DEFAULT_TOPIC_LABELS,
    top_k: int = 3,
) -> EmbeddingResult:
    try:
        processor, model, torch, device = _load_clip(model_name, use_gpu)
        image = Image.open(image_path).convert("RGB")
        label_list = list(labels)
        inputs = processor(text=label_list, images=image, return_tensors="pt", padding=True)
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
            probabilities = outputs.logits_per_image.softmax(dim=1)[0]
        ranked = sorted(
            zip(label_list, probabilities.tolist()),
            key=lambda item: item[1],
            reverse=True,
        )[:top_k]
        return EmbeddingResult(
            topics=["{} ({:.2f})".format(label, score) for label, score in ranked],
            model_name=model_name,
            status="ok",
        )
    except Exception as error:
        return EmbeddingResult(topics=[], model_name=model_name, status="unavailable", error=str(error))
