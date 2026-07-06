"""Media-processing utilities for video and audio conversion."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


def ensure_ffmpeg_installed() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is not installed or not available in the system PATH.")


def extract_audio_from_video(video_path: Path, audio_path: Path) -> None:
    ensure_ffmpeg_installed()
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(audio_path),
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "ffmpeg audio extraction failed: {}".format(completed.stderr.strip() or completed.stdout.strip())
        )


def extract_frames_from_video(
    video_path: Path,
    frames_dir: Path,
    frame_interval_seconds: int,
    frame_prefix: str,
    scene_change_threshold: float = 0.14,
    min_frame_gap_seconds: int = 8,
    frame_sample_seconds: int = 4,
    duplicate_frame_threshold: float = 0.04,
    frame_jpeg_quality: int = 95,
    save_all_sampled_frames: bool = False,
) -> List[Dict]:
    frames_dir.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open the video file for frame extraction.")

    fps = capture.get(cv2.CAP_PROP_FPS) or 0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fps <= 0 or total_frames <= 0:
        capture.release()
        raise RuntimeError("Could not determine video FPS or total frame count.")

    sample_interval_frames = 1 if frame_sample_seconds <= 0 else max(int(fps * frame_sample_seconds), 1)
    max_gap_frames = max(int(fps * max(frame_interval_seconds, 1)), 1)
    min_gap_frames = max(int(fps * max(min_frame_gap_seconds, 0)), 0)
    current_frame = 0
    extracted_frames: List[Dict] = []
    frame_index = 1
    last_saved_frame: Optional[int] = None
    last_saved_signature: Optional[np.ndarray] = None
    recent_saved_signatures: List[np.ndarray] = []
    jpeg_quality = min(max(int(frame_jpeg_quality), 1), 100)

    try:
        while current_frame < total_frames:
            capture.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            success, frame = capture.read()
            if not success:
                break

            signature = _build_frame_signature(frame)
            if save_all_sampled_frames:
                should_save = True
                change_score = (
                    1.0
                    if last_saved_signature is None
                    else _frame_change_score(signature, last_saved_signature)
                )
            else:
                should_save, change_score = _should_save_frame(
                    current_frame=current_frame,
                    last_saved_frame=last_saved_frame,
                    current_signature=signature,
                    last_saved_signature=last_saved_signature,
                    recent_saved_signatures=recent_saved_signatures,
                    scene_change_threshold=scene_change_threshold,
                    duplicate_frame_threshold=duplicate_frame_threshold,
                    min_gap_frames=min_gap_frames,
                    max_gap_frames=max_gap_frames,
                )

            if should_save:
                output_name = "{}_frame_{:04d}.jpg".format(frame_prefix, frame_index)
                output_path = frames_dir / output_name
                cv2.imwrite(str(output_path), frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])

                extracted_frames.append(
                    {
                        "timestamp_seconds": round(current_frame / fps, 2),
                        "absolute_path": output_path,
                        "filename": output_name,
                        "change_score": round(change_score, 4),
                    }
                )

                frame_index += 1
                last_saved_frame = current_frame
                last_saved_signature = signature
                recent_saved_signatures.append(signature)
                recent_saved_signatures = recent_saved_signatures[-8:]

            current_frame += sample_interval_frames
    finally:
        capture.release()

    if not extracted_frames:
        raise RuntimeError("No frames were extracted from the uploaded video.")

    return extracted_frames


def _build_frame_signature(frame) -> np.ndarray:
    resized = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
    grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(grayscale, (5, 5), 0)


def _frame_change_score(current_signature: np.ndarray, previous_signature: np.ndarray) -> float:
    difference = cv2.absdiff(current_signature, previous_signature)
    return float(np.mean(difference) / 255.0)


def _should_save_frame(
    *,
    current_frame: int,
    last_saved_frame: Optional[int],
    current_signature: np.ndarray,
    last_saved_signature: Optional[np.ndarray],
    recent_saved_signatures: List[np.ndarray],
    scene_change_threshold: float,
    duplicate_frame_threshold: float,
    min_gap_frames: int,
    max_gap_frames: int,
) -> Tuple[bool, float]:
    if last_saved_frame is None or last_saved_signature is None:
        return True, 1.0

    frames_since_last_save = current_frame - last_saved_frame
    if frames_since_last_save < min_gap_frames:
        return False, 0.0

    change_score = _frame_change_score(current_signature, last_saved_signature)
    if recent_saved_signatures:
        nearest_saved_score = min(
            _frame_change_score(current_signature, saved_signature)
            for saved_signature in recent_saved_signatures
        )
        if nearest_saved_score <= duplicate_frame_threshold:
            return False, nearest_saved_score

    if change_score >= scene_change_threshold:
        return True, change_score

    return frames_since_last_save >= max_gap_frames, change_score
