"""Draw visual evidence overlays on extracted video frames."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ai.vision.models import EmbeddingResult, EquationResult, OCRBlock, OCRResult, VisionLanguageResult


Color = Tuple[int, int, int]

TEXT_COLOR: Color = (0, 170, 0)
EQUATION_COLOR: Color = (220, 90, 20)
PANEL_COLOR: Color = (24, 38, 44)
PANEL_TEXT_COLOR: Color = (255, 255, 255)


def _box_points(bbox: Optional[Sequence[Sequence[float]]]) -> Optional[np.ndarray]:
    if not bbox:
        return None

    points = []
    for point in bbox:
        if len(point) < 2:
            continue
        points.append([int(round(float(point[0]))), int(round(float(point[1])))])

    if len(points) < 2:
        return None
    return np.array(points, dtype=np.int32)


def _box_anchor(points: np.ndarray) -> Tuple[int, int]:
    min_x = int(np.min(points[:, 0]))
    min_y = int(np.min(points[:, 1]))
    return max(min_x, 0), max(min_y - 8, 14)


def _is_equation_like(text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    formula_tokens = ("=", "+", "-", "/", "\\", "^", "_", "∑", "√", "∫", "lim", "sin", "cos", "tan")
    return any(token in value for token in formula_tokens) and any(character.isdigit() for character in value)


def _should_label_block(block: OCRBlock) -> bool:
    text = " ".join(str(block.text or "").split())
    if not text:
        return False
    if _is_equation_like(text):
        return True
    return block.confidence >= 0.75 and len(text) >= 12


def _put_label(image, label: str, origin: Tuple[int, int], color: Color) -> None:
    text = label[:64]
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.48
    thickness = 1
    (width, height), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = origin
    y = max(y, height + baseline + 4)
    cv2.rectangle(image, (x, y - height - baseline - 5), (x + width + 8, y + 4), color, -1)
    cv2.putText(image, text, (x + 4, y - baseline), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def _draw_block(image, block: OCRBlock, *, show_label: bool = False) -> bool:
    points = _box_points(block.bbox)
    if points is None:
        return False

    is_equation = _is_equation_like(block.text)
    color = EQUATION_COLOR if is_equation else TEXT_COLOR
    label = "Equation: {}".format(block.text) if is_equation else "Text: {}".format(block.text)

    cv2.polylines(image, [points], isClosed=True, color=color, thickness=2)
    if show_label:
        _put_label(image, label, _box_anchor(points), color)
    return True


def _wrap_label(value: str, max_chars: int = 58) -> List[str]:
    words = value.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = "{} {}".format(current, word).strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [value[:max_chars]]


def _draw_panel(image, labels: Iterable[str]) -> None:
    lines: List[str] = []
    for label in labels:
        value = " ".join(str(label or "").split())
        if not value:
            continue
        lines.extend(_wrap_label(value))

    if not lines:
        return

    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    thickness = 1
    line_height = 19
    padding = 10
    width = min(max(cv2.getTextSize(line, font, scale, thickness)[0][0] for line in lines) + padding * 2, image.shape[1] - 20)
    height = line_height * len(lines) + padding * 2
    x = 10
    y = 10

    overlay = image.copy()
    cv2.rectangle(overlay, (x, y), (x + width, y + height), PANEL_COLOR, -1)
    cv2.addWeighted(overlay, 0.86, image, 0.14, 0, image)

    for index, line in enumerate(lines):
        cv2.putText(
            image,
            line,
            (x + padding, y + padding + 14 + index * line_height),
            font,
            scale,
            PANEL_TEXT_COLOR,
            thickness,
            cv2.LINE_AA,
        )


def save_annotated_frame(
    *,
    image_path: Path,
    output_dir: Path,
    ocr: OCRResult,
    equations: EquationResult,
    vision: VisionLanguageResult,
    embeddings: EmbeddingResult,
    topic: Optional[str],
) -> Optional[Path]:
    """Save a copy of the frame with boxes and high-level visual labels."""

    image = cv2.imread(str(image_path))
    if image is None:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    drew_boxes = False
    labeled_blocks = 0
    for block in ocr.blocks:
        show_label = labeled_blocks < 12 and _should_label_block(block)
        drew_block = _draw_block(image, block, show_label=show_label)
        if drew_block and show_label:
            labeled_blocks += 1
        drew_boxes = drew_block or drew_boxes

    labels = [
        "Topic: {}".format(topic) if topic else "",
        "Visual type: {}".format(str(vision.visual_type).replace("_", " ")) if vision.visual_type else "",
    ]
    if equations.latex:
        labels.append("Equations: {}".format(", ".join(equations.latex[:3])))
    if embeddings.topics:
        labels.append("CLIP topics: {}".format(", ".join(embeddings.topics[:3])))
    if ocr.text:
        labels.append("OCR text detected: {} block(s)".format(len(ocr.blocks)))
    if not drew_boxes and not any(labels):
        return None

    _draw_panel(image, labels)
    output_path = output_dir / "{}_annotated.jpg".format(image_path.stem)
    cv2.imwrite(str(output_path), image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return output_path
