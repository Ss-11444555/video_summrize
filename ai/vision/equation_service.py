"""Equation recognition for educational visual content."""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2

from ai.vision.models import EquationResult, OCRBlock


INLINE_EQUATION_PATTERNS = (
    r"\b[a-zA-Z]\s*=\s*[-+*/^(). a-zA-Z0-9]+",
    r"\b(?:sin|cos|tan|log|ln|lim|sum|int)\b[^,\n;]*",
    r"\\(?:frac|sum|int|sqrt|lim|alpha|beta|theta|lambda|sigma|mu)\b[^,\n;]*",
)
MATH_TRIGGER_PATTERN = re.compile(
    r"(=|\\frac|\\sum|\\int|\\sqrt|[∫∑√∞∂πθ≤≥→]|"
    r"\b(?:sin|cos|tan|log|ln|lim|derivative|gradient|equation|formula)\b|"
    r"[a-zA-Z]\s*[+\-*/^]\s*[a-zA-Z0-9])",
    re.IGNORECASE,
)
MAX_EQUATION_LENGTH = 220
MAX_EQUATION_CROPS = 4
EQUATION_CROP_PADDING = 18


@lru_cache(maxsize=1)
def _load_latex_ocr_model():
    try:
        from pix2tex.cli import LatexOCR  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "Math OCR is not installed. Install pix2tex or configure a Nougat OCR command."
        ) from error

    return LatexOCR()


def _extract_equations_from_text(text: str) -> List[str]:
    equations: List[str] = []
    for pattern in INLINE_EQUATION_PATTERNS:
        for match in re.findall(pattern, text or ""):
            value = " ".join(match.strip().split())
            if _is_usable_latex(value) and value not in equations:
                equations.append(value)
    return equations


def _is_usable_latex(value: str) -> bool:
    text = " ".join(str(value or "").strip().split())
    if not text or len(text) > MAX_EQUATION_LENGTH:
        return False

    if text.count("\\") > 18 or len(re.findall(r"[{}]", text)) > 28:
        return False

    return bool(MATH_TRIGGER_PATTERN.search(text))


def _run_pix2tex(image_path: Path) -> List[str]:
    from PIL import Image

    model = _load_latex_ocr_model()
    latex = str(model(Image.open(image_path))).strip()
    return [latex] if latex else []


def _run_nougat_command(image_path: Path, command: str) -> List[str]:
    completed = subprocess.run(
        [command, str(image_path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Nougat OCR command failed.")

    output = completed.stdout.strip()
    return [line.strip() for line in output.splitlines() if line.strip()]


def _block_bounds(block: OCRBlock) -> Optional[Tuple[float, float, float, float]]:
    if not block.bbox:
        return None

    points = [
        (float(point[0]), float(point[1]))
        for point in block.bbox
        if len(point) >= 2
    ]
    if not points:
        return None

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _is_math_ocr_block(block: OCRBlock) -> bool:
    text = " ".join(str(block.text or "").strip().split())
    if not text:
        return False

    if MATH_TRIGGER_PATTERN.search(text):
        return True

    math_chars = sum(1 for character in text if character in "=+-*/^_()[]{}<>%\\∫∑√∞∂πθ≤≥→")
    alnum_chars = sum(1 for character in text if character.isalnum())
    return math_chars >= 1 and alnum_chars >= 1


def _vertical_overlap(first: Tuple[float, float, float, float], second: Tuple[float, float, float, float]) -> float:
    top = max(first[1], second[1])
    bottom = min(first[3], second[3])
    overlap = max(bottom - top, 0.0)
    smallest_height = max(min(first[3] - first[1], second[3] - second[1]), 1.0)
    return overlap / smallest_height


def _expanded_row_region(
    math_bounds: Tuple[float, float, float, float],
    all_bounds: Sequence[Tuple[OCRBlock, Tuple[float, float, float, float]]],
) -> Tuple[float, float, float, float]:
    row_blocks = []
    math_height = max(math_bounds[3] - math_bounds[1], 1.0)
    math_center_y = (math_bounds[1] + math_bounds[3]) / 2.0

    for block, bounds in all_bounds:
        block_height = max(bounds[3] - bounds[1], 1.0)
        block_center_y = (bounds[1] + bounds[3]) / 2.0
        same_line = (
            _vertical_overlap(math_bounds, bounds) >= 0.35
            or abs(block_center_y - math_center_y) <= max(math_height, block_height) * 0.75
        )
        if not same_line:
            continue

        horizontal_gap = max(bounds[0] - math_bounds[2], math_bounds[0] - bounds[2], 0.0)
        if horizontal_gap <= max(math_height * 8.0, 180.0):
            row_blocks.append((block, bounds))

    if not row_blocks:
        return math_bounds

    return (
        min(bounds[0] for _, bounds in row_blocks),
        min(bounds[1] for _, bounds in row_blocks),
        max(bounds[2] for _, bounds in row_blocks),
        max(bounds[3] for _, bounds in row_blocks),
    )


def _clamp_region(
    region: Tuple[float, float, float, float],
    image_width: int,
    image_height: int,
    padding: int = EQUATION_CROP_PADDING,
) -> Optional[Tuple[int, int, int, int]]:
    left = max(int(region[0]) - padding, 0)
    top = max(int(region[1]) - padding, 0)
    right = min(int(region[2]) + padding, image_width)
    bottom = min(int(region[3]) + padding, image_height)

    if right - left < 8 or bottom - top < 8:
        return None
    return left, top, right, bottom


def _region_overlap_ratio(first: Tuple[int, int, int, int], second: Tuple[int, int, int, int]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(right - left, 0) * max(bottom - top, 0)
    if intersection <= 0:
        return 0.0

    first_area = max(first[2] - first[0], 1) * max(first[3] - first[1], 1)
    second_area = max(second[2] - second[0], 1) * max(second[3] - second[1], 1)
    return intersection / float(min(first_area, second_area))


def _candidate_equation_regions(
    ocr_blocks: Iterable[OCRBlock],
    image_width: int,
    image_height: int,
) -> List[Tuple[int, int, int, int]]:
    blocks_with_bounds = [
        (block, bounds)
        for block in ocr_blocks
        for bounds in [_block_bounds(block)]
        if bounds is not None
    ]
    math_bounds = [
        bounds
        for block, bounds in blocks_with_bounds
        if _is_math_ocr_block(block)
    ]

    regions: List[Tuple[int, int, int, int]] = []
    for bounds in math_bounds:
        row_region = _expanded_row_region(bounds, blocks_with_bounds)
        clamped = _clamp_region(row_region, image_width, image_height)
        if clamped is None:
            continue
        if any(_region_overlap_ratio(clamped, existing) >= 0.72 for existing in regions):
            continue
        regions.append(clamped)
        if len(regions) >= MAX_EQUATION_CROPS:
            break

    return regions


def _save_equation_crops(
    image_path: Path,
    ocr_blocks: Iterable[OCRBlock],
    output_dir: Optional[Path],
) -> List[Path]:
    if output_dir is None:
        return []

    image = cv2.imread(str(image_path))
    if image is None:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    image_height, image_width = image.shape[:2]
    crop_paths: List[Path] = []
    for index, (left, top, right, bottom) in enumerate(
        _candidate_equation_regions(list(ocr_blocks), image_width, image_height),
        start=1,
    ):
        crop = image[top:bottom, left:right]
        if crop.size == 0:
            continue
        output_path = output_dir / "{}_equation_{:04d}.jpg".format(image_path.stem, index)
        cv2.imwrite(str(output_path), crop, [cv2.IMWRITE_JPEG_QUALITY, 96])
        crop_paths.append(output_path)

    return crop_paths


def _run_formula_model_on_candidates(
    image_path: Path,
    crop_paths: Sequence[Path],
    nougat_command: str,
) -> List[str]:
    if nougat_command:
        return _run_nougat_command(image_path, nougat_command)

    candidate_paths = list(crop_paths) or [image_path]
    outputs: List[str] = []
    last_error: Optional[Exception] = None
    for candidate_path in candidate_paths:
        try:
            outputs.extend(_run_pix2tex(candidate_path))
        except Exception as error:
            last_error = error

    if not outputs and last_error is not None:
        raise last_error
    return outputs


def extract_equations(
    image_path: Path,
    *,
    ocr_text: str = "",
    ocr_blocks: Iterable[OCRBlock] = (),
    crop_output_dir: Optional[Path] = None,
    nougat_command: str = "",
    force_model_ocr: bool = False,
) -> EquationResult:
    """Convert visible educational equations into LaTeX-like text."""

    text_equations = _extract_equations_from_text(ocr_text)
    ocr_block_list = list(ocr_blocks)
    crop_paths = _save_equation_crops(image_path, ocr_block_list, crop_output_dir)
    should_run_model = (
        force_model_ocr
        or bool(text_equations)
        or bool(crop_paths)
        or bool(MATH_TRIGGER_PATTERN.search(ocr_text or ""))
    )
    if not should_run_model:
        return EquationResult(latex=[], image_paths=crop_paths, status="skipped")

    try:
        model_equations = _run_formula_model_on_candidates(image_path, crop_paths, nougat_command)
    except Exception as error:
        if text_equations:
            return EquationResult(latex=text_equations, image_paths=crop_paths, status="partial", error=str(error))
        return EquationResult(latex=[], image_paths=crop_paths, status="unavailable", error=str(error))

    equations = []
    for equation in text_equations + model_equations:
        value = " ".join(str(equation or "").strip().split())
        if _is_usable_latex(value) and value not in equations:
            equations.append(value)

    return EquationResult(latex=equations, image_paths=crop_paths, status="ok")
