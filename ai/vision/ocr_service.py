"""PaddleOCR-backed text extraction for educational images."""

from __future__ import annotations

import re
from functools import lru_cache
import inspect
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ai.vision.models import OCRBlock, OCRResult


_PADDLE_RUNTIME_DISABLED_REASON: Optional[str] = None
TESSERACT_PSM_MODES = (6, 11, 13)
MATH_CHARS = set("=+-*/^_()[]{}.,:;<>%$\\'|")


@lru_cache(maxsize=4)
def _load_paddle_ocr(language: str, use_gpu: bool):
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "PaddleOCR is not installed. Install project dependencies to enable multilingual slide OCR."
        ) from error

    signature = inspect.signature(PaddleOCR)
    parameters = signature.parameters
    if "use_angle_cls" in parameters or "use_gpu" in parameters:
        kwargs = {"use_angle_cls": True, "lang": language, "show_log": False}
        if "use_gpu" in parameters:
            kwargs["use_gpu"] = use_gpu
        return PaddleOCR(**kwargs)

    kwargs = {
        "lang": language,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": True,
    }
    if "device" in parameters:
        kwargs["device"] = "gpu" if use_gpu else "cpu"
    return PaddleOCR(**kwargs)


def _normalize_line(raw_line) -> Optional[OCRBlock]:
    try:
        bbox = raw_line[0]
        text, confidence = raw_line[1]
    except (IndexError, TypeError, ValueError):
        return None

    text = " ".join(str(text).strip().split())
    if not text:
        return None

    return OCRBlock(text=text, confidence=float(confidence or 0.0), bbox=bbox)


def _dedupe_blocks(blocks: List[OCRBlock]) -> List[OCRBlock]:
    seen = set()
    unique_blocks: List[OCRBlock] = []
    for block in blocks:
        key = block.text.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_blocks.append(block)
    return unique_blocks


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


def _normalize_ocr_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _is_plausible_ocr_block(block: OCRBlock, image_shape: Tuple[int, int, int]) -> bool:
    text = _normalize_ocr_text(block.text)
    if not text:
        return False

    bounds = _block_bounds(block)
    if bounds is None:
        return False

    left, top, right, bottom = bounds
    width = max(right - left, 0.0)
    height = max(bottom - top, 0.0)
    image_height, image_width = image_shape[:2]
    if width < 2.0 or height < 2.0:
        return False
    if width > image_width * 0.98 or height > image_height * 0.45:
        return False

    if re.fullmatch(r"[\W_]+", text, flags=re.UNICODE):
        return len(text) >= 2 and block.confidence >= 0.85 and any(character in MATH_CHARS for character in text)

    if len(text) == 1:
        return block.confidence >= 0.75 and (text.isalnum() or text in MATH_CHARS)

    meaningful_chars = sum(1 for character in text if character.isalnum() or character in MATH_CHARS)
    meaningful_ratio = meaningful_chars / max(len(text), 1)
    if meaningful_ratio < 0.45:
        return False

    has_letter_or_digit = any(character.isalnum() for character in text)
    has_formula_shape = any(character in MATH_CHARS for character in text) and has_letter_or_digit
    if len(text) <= 2:
        return block.confidence >= 0.62 and (has_letter_or_digit or has_formula_shape)

    return block.confidence >= 0.34 or has_formula_shape


def _text_region_score(block: OCRBlock) -> float:
    text = _normalize_ocr_text(block.text)
    if len(text) < 3 or block.confidence < 0.65:
        return 0.0
    if not any(character.isalnum() for character in text):
        return 0.0
    return len(text) * max(block.confidence, 0.01)


def _filter_to_dominant_text_half(blocks: List[OCRBlock], image_shape: Tuple[int, int, int]) -> List[OCRBlock]:
    if len(blocks) < 5:
        return blocks

    image_width = float(image_shape[1])
    midpoint = image_width / 2.0
    scores = [0.0, 0.0]
    for block in blocks:
        bounds = _block_bounds(block)
        if bounds is None:
            continue
        left, _, right, _ = bounds
        center_x = (left + right) / 2.0
        scores[0 if center_x < midpoint else 1] += _text_region_score(block)

    dominant_index = 0 if scores[0] >= scores[1] else 1
    weaker_score = scores[1 - dominant_index]
    dominant_score = scores[dominant_index]
    if dominant_score < 55.0 or dominant_score < max(weaker_score * 2.5, 1.0):
        return blocks

    filtered: List[OCRBlock] = []
    for block in blocks:
        bounds = _block_bounds(block)
        if bounds is None:
            continue
        left, _, right, _ = bounds
        center_x = (left + right) / 2.0
        block_index = 0 if center_x < midpoint else 1
        if block_index == dominant_index:
            filtered.append(block)
    return filtered


def _sort_blocks_reading_order(blocks: List[OCRBlock]) -> List[OCRBlock]:
    def key(block: OCRBlock) -> Tuple[float, float]:
        bounds = _block_bounds(block)
        if bounds is None:
            return 0.0, 0.0
        left, top, _, bottom = bounds
        line_bucket = round(((top + bottom) / 2.0) / 18.0)
        return float(line_bucket), left

    return sorted(blocks, key=key)


def _prepare_ocr_blocks_for_result(
    blocks: List[OCRBlock],
    variant_name: str,
    image_shape: Tuple[int, int, int],
) -> List[OCRBlock]:
    scaled_blocks = _scale_blocks_for_original_image(blocks, variant_name)
    plausible_blocks = [
        block
        for block in scaled_blocks
        if _is_plausible_ocr_block(block, image_shape)
    ]
    region_blocks = _filter_to_dominant_text_half(plausible_blocks, image_shape)
    return _dedupe_blocks(_sort_blocks_reading_order(region_blocks))


def _build_ocr_variants(image_path: Path) -> List[Tuple[str, np.ndarray]]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError("OpenCV could not read image for OCR: {}".format(image_path))

    variants: List[Tuple[str, np.ndarray]] = [("original", image)]
    upscaled = cv2.resize(image, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    variants.append(("upscaled", upscaled))

    upscaled_3x = cv2.resize(image, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    variants.append(("upscaled_3x", upscaled_3x))

    lab = cv2.cvtColor(upscaled, cv2.COLOR_BGR2LAB)
    lightness, channel_a, channel_b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_lightness = clahe.apply(lightness)
    contrast = cv2.cvtColor(cv2.merge((enhanced_lightness, channel_a, channel_b)), cv2.COLOR_LAB2BGR)
    variants.append(("contrast", contrast))

    denoised = cv2.fastNlMeansDenoisingColored(contrast, None, 5, 5, 7, 21)
    variants.append(("denoised", denoised))

    blurred = cv2.GaussianBlur(contrast, (0, 0), 1.0)
    sharpened = cv2.addWeighted(contrast, 1.55, blurred, -0.55, 0)
    variants.append(("sharpened", sharpened))

    grayscale = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    adaptive = cv2.adaptiveThreshold(
        grayscale,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    variants.append(("adaptive_threshold", cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR)))

    _, otsu = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("otsu_threshold", cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR)))

    if float(np.mean(grayscale)) < 95.0:
        inverted = cv2.bitwise_not(grayscale)
        inverted_bgr = cv2.cvtColor(inverted, cv2.COLOR_GRAY2BGR)
        variants.append(("inverted_dark_slide", inverted_bgr))

    return variants


def _run_ocr_on_image(ocr, image, min_confidence: float) -> List[OCRBlock]:
    try:
        raw_result = ocr.ocr(image, cls=True)
    except TypeError:
        try:
            raw_result = ocr.ocr(image)
        except TypeError:
            raw_result = ocr.predict(image)

    blocks: List[OCRBlock] = []
    for page in raw_result or []:
        if isinstance(page, dict):
            blocks.extend(_normalize_paddle_dict_result(page, min_confidence))
            continue
        for raw_line in page or []:
            block = _normalize_line(raw_line)
            if block and block.confidence >= min_confidence:
                blocks.append(block)
    return _dedupe_blocks(blocks)


def _normalize_paddle_dict_result(result: dict, min_confidence: float) -> List[OCRBlock]:
    texts = result.get("rec_texts") or result.get("text") or []
    scores = result.get("rec_scores") or result.get("scores") or []
    boxes = result.get("rec_boxes") or result.get("dt_polys") or []
    blocks: List[OCRBlock] = []
    for index, text in enumerate(texts):
        confidence = float(scores[index]) if index < len(scores) else 0.0
        if confidence < min_confidence:
            continue
        value = " ".join(str(text).strip().split())
        if value:
            bbox = boxes[index].tolist() if index < len(boxes) and hasattr(boxes[index], "tolist") else None
            blocks.append(OCRBlock(text=value, confidence=confidence, bbox=bbox))
    return blocks


def _run_tesseract_on_image(image, language: str, min_confidence: float, psm: int = 6) -> List[OCRBlock]:
    try:
        import pytesseract  # type: ignore
    except ImportError as error:
        raise RuntimeError("pytesseract is not installed.") from error

    tess_language = "eng" if language == "en" else language
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    data = pytesseract.image_to_data(
        rgb_image,
        lang=tess_language,
        config="--oem 3 --psm {}".format(psm),
        output_type=pytesseract.Output.DICT,
    )

    blocks: List[OCRBlock] = []
    for index, raw_text in enumerate(data.get("text", [])):
        text = " ".join(str(raw_text).strip().split())
        if not text:
            continue

        try:
            confidence = float(data["conf"][index]) / 100.0
        except (ValueError, TypeError):
            confidence = 0.0
        if confidence < min_confidence:
            continue

        left = float(data["left"][index])
        top = float(data["top"][index])
        width = float(data["width"][index])
        height = float(data["height"][index])
        bbox = [[left, top], [left + width, top], [left + width, top + height], [left, top + height]]
        blocks.append(OCRBlock(text=text, confidence=confidence, bbox=bbox))

    return _dedupe_blocks(blocks)


def _best_tesseract_result(
    variants: List[Tuple[str, np.ndarray]],
    language: str,
    min_confidence: float,
    image_shape: Tuple[int, int, int],
) -> Tuple[str, List[OCRBlock], float]:
    candidates = []
    for variant_name, variant_image in variants:
        for psm in TESSERACT_PSM_MODES:
            blocks = _run_tesseract_on_image(variant_image, language, min_confidence, psm=psm)
            result_variant = "tesseract:psm{}:{}".format(psm, variant_name)
            result_blocks = _prepare_ocr_blocks_for_result(blocks, result_variant, image_shape)
            candidates.append((result_variant, result_blocks, _score_blocks(result_blocks)))
    return max(candidates, key=lambda item: item[2])


def _score_blocks(blocks: List[OCRBlock]) -> float:
    if not blocks:
        return 0.0
    text = " ".join(block.text for block in blocks)
    text_length = len(text)
    average_confidence = sum(block.confidence for block in blocks) / len(blocks)
    meaningful_chars = sum(1 for character in text if character.isalnum() or character in "=+-*/^_()[]{}.,:;<>%$\\")
    meaningful_ratio = meaningful_chars / max(text_length, 1)
    block_bonus = min(len(blocks), 12) * 2.0
    return (text_length * max(average_confidence, 0.01) * max(meaningful_ratio, 0.25)) + block_bonus


def extract_text(
    image_path: Path,
    *,
    language: str = "en",
    use_gpu: bool = False,
    min_confidence: float = 0.30,
) -> OCRResult:
    """Extract visible text from slides, charts, code screenshots, and diagrams."""

    global _PADDLE_RUNTIME_DISABLED_REASON

    try:
        variants = _build_ocr_variants(image_path)
        image_shape = variants[0][1].shape
        if _PADDLE_RUNTIME_DISABLED_REASON:
            raise RuntimeError(_PADDLE_RUNTIME_DISABLED_REASON)
        try:
            ocr = _load_paddle_ocr(language, use_gpu)
            candidates = []
            for variant_name, variant_image in variants:
                blocks = _run_ocr_on_image(ocr, variant_image, min_confidence)
                result_variant = "paddleocr:{}".format(variant_name)
                result_blocks = _prepare_ocr_blocks_for_result(blocks, result_variant, image_shape)
                candidates.append((result_variant, result_blocks, _score_blocks(result_blocks)))
            best_variant, blocks, _ = max(candidates, key=lambda item: item[2])
        except Exception as paddle_error:
            _PADDLE_RUNTIME_DISABLED_REASON = str(paddle_error)
            raise
    except Exception as error:
        try:
            variants = _build_ocr_variants(image_path)
            best_variant, blocks, _ = _best_tesseract_result(variants, language, min_confidence, variants[0][1].shape)
        except Exception as fallback_error:
            return OCRResult(
                text="",
                language=language,
                status="unavailable",
                error="PaddleOCR failed: {}; Tesseract failed: {}".format(error, fallback_error),
            )

    return OCRResult(
        text="\n".join(block.text for block in blocks),
        language=language,
        blocks=blocks,
        engine=best_variant,
        status="ok" if blocks else "empty",
    )


def _scale_blocks_for_original_image(blocks: List[OCRBlock], variant_name: str) -> List[OCRBlock]:
    """Map OCR boxes from preprocessing variants back to the original frame size."""

    scale = _variant_scale_factor(variant_name)
    if scale == 1.0:
        return blocks

    scaled_blocks: List[OCRBlock] = []
    for block in blocks:
        if not block.bbox:
            scaled_blocks.append(block)
            continue
        scaled_bbox = [
            [float(point[0]) / scale, float(point[1]) / scale]
            for point in block.bbox
            if len(point) >= 2
        ]
        scaled_blocks.append(
            OCRBlock(
                text=block.text,
                confidence=block.confidence,
                bbox=scaled_bbox or block.bbox,
            )
        )
    return scaled_blocks


def _variant_scale_factor(variant_name: str) -> float:
    name = variant_name.rsplit(":", 1)[-1]
    if name == "original":
        return 1.0
    if name.endswith("_3x"):
        return 3.0
    return 2.0
