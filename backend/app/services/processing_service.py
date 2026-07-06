"""Business logic for video processing orchestration."""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, status

from ai.evaluation.rouge_service import build_reference_summary, evaluate_summary_with_rouge
from ai.fusion.fusion_service import build_multimodal_context
from ai.nlp.preprocessing import preprocess_multimodal_text
from ai.speech.subtitle_service import transcribe_from_existing_subtitles
from ai.speech.whisper_service import transcribe_audio_file
from ai.summarization.llm_service import generate_structured_summary
from ai.summarization.slide_summary_service import generate_slide_summaries
from ai.vision.equation_fallback_service import apply_transcript_equation_fallbacks
from ai.vision.educational_pipeline import understand_frames
from backend.app.core.config import settings
from backend.app.core.database import commit_with_retry, create_connection
from backend.app.utils.file_handler import sanitize_filename
from backend.app.utils.logger import get_logger
from backend.app.utils.media import extract_audio_from_video, extract_frames_from_video


logger = get_logger(__name__)


class VideoProcessingCancelled(RuntimeError):
    """Raised when a teacher deletes a video while its pipeline is running."""


def _ensure_video_exists(connection: sqlite3.Connection, video_id: int) -> None:
    row = connection.execute(
        "SELECT id FROM videos WHERE id = ?",
        (video_id,),
    ).fetchone()
    if row is None:
        raise VideoProcessingCancelled("Video was deleted while processing.")


def create_processing_job(connection: sqlite3.Connection, video_id: int) -> None:
    connection.execute(
        """
        INSERT INTO processing_jobs (
            video_id,
            stage,
            progress_percent,
            status_message
        )
        VALUES (?, 'queued', 8.00, 'Video uploaded and waiting for processing.')
        """,
        (video_id,),
    )
    commit_with_retry(connection)


def _update_processing_job(
    connection: sqlite3.Connection,
    video_id: int,
    stage: str,
    progress_percent: float,
    status_message: str,
    completed: bool = False,
) -> None:
    connection.execute(
        """
        UPDATE processing_jobs
        SET
            stage = ?,
            progress_percent = ?,
            status_message = ?,
            started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
            completed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE completed_at END
        WHERE video_id = ?
        """,
        (stage, progress_percent, status_message, 1 if completed else 0, video_id),
    )
    commit_with_retry(connection)


def _update_video_status(connection: sqlite3.Connection, video_id: int, status_value: str) -> None:
    connection.execute(
        "UPDATE videos SET status = ? WHERE id = ?",
        (status_value, video_id),
    )
    commit_with_retry(connection)


def _upsert_transcript(
    connection: sqlite3.Connection,
    video_id: int,
    raw_text: str,
    cleaned_text: str,
    language_code: Optional[str],
    whisper_model: str,
    word_count: int,
) -> None:
    existing = connection.execute(
        "SELECT id FROM transcripts WHERE video_id = ?",
        (video_id,),
    ).fetchone()

    if existing:
        connection.execute(
            """
            UPDATE transcripts
            SET
                raw_text = ?,
                cleaned_text = ?,
                language_code = ?,
                whisper_model = ?,
                word_count = ?
            WHERE video_id = ?
            """,
            (raw_text, cleaned_text, language_code, whisper_model, word_count, video_id),
        )
    else:
        connection.execute(
            """
            INSERT INTO transcripts (
                video_id,
                raw_text,
                cleaned_text,
                language_code,
                whisper_model,
                word_count
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (video_id, raw_text, cleaned_text, language_code, whisper_model, word_count),
        )

    commit_with_retry(connection)


def _replace_transcript_segments(connection: sqlite3.Connection, video_id: int, segments: List[dict]) -> None:
    connection.execute("DELETE FROM transcript_segments WHERE video_id = ?", (video_id,))

    for segment in segments:
        text = str(segment.get("text") or "").strip()
        if not text:
            continue

        start_seconds = float(segment.get("start") or 0.0)
        end_seconds = float(segment.get("end") or start_seconds)
        connection.execute(
            """
            INSERT INTO transcript_segments (
                video_id,
                start_seconds,
                end_seconds,
                segment_text
            )
            VALUES (?, ?, ?, ?)
            """,
            (video_id, start_seconds, end_seconds, text),
        )

    commit_with_retry(connection)


def _storage_relative_path(*parts: str) -> str:
    return (Path("backend") / "storage" / Path(*parts)).as_posix()


def _relative_project_path(path_value) -> Optional[str]:
    if not path_value:
        return None

    candidate = Path(path_value)
    if not candidate.is_absolute():
        return candidate.as_posix()

    project_root = settings.database_path.parent.resolve()
    try:
        return candidate.resolve().relative_to(project_root).as_posix()
    except ValueError:
        return candidate.as_posix()


def _caption_frame_path(caption: dict) -> str:
    return str(caption.get("frame_path") or _storage_relative_path("frames", caption["filename"]))


def _caption_annotated_frame_path(caption: dict) -> Optional[str]:
    annotated_path = _relative_project_path(caption.get("annotated_frame_path"))
    if annotated_path:
        return annotated_path

    annotated_path = _relative_project_path(caption.get("annotated_absolute_path"))
    if annotated_path:
        return annotated_path

    annotated_filename = caption.get("annotated_filename")
    if not annotated_filename:
        return None
    return _storage_relative_path("annotated_frames", str(annotated_filename))


def _caption_equation_image_paths(caption: dict) -> List[str]:
    image_paths = caption.get("equation_images") or caption.get("equation_image_paths") or []
    relative_paths: List[str] = []
    for image_path in image_paths:
        relative_path = _relative_project_path(image_path)
        if relative_path:
            relative_paths.append(relative_path)
    return relative_paths


def _replace_frame_captions(connection: sqlite3.Connection, video_id: int, captions: List[dict]) -> None:
    connection.execute("DELETE FROM frame_captions WHERE video_id = ?", (video_id,))

    for caption in captions:
        relative_frame_path = _caption_frame_path(caption)
        relative_annotated_frame_path = _caption_annotated_frame_path(caption)
        connection.execute(
            """
            INSERT INTO frame_captions (
                video_id,
                frame_timestamp_seconds,
                frame_path,
                annotated_frame_path,
                caption_text,
                ocr_text,
                equations_text,
                equation_image_paths,
                equation_source,
                equation_fallback_notes,
                visual_type,
                topic,
                change_score,
                visual_model
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                caption["timestamp_seconds"],
                relative_frame_path,
                relative_annotated_frame_path,
                caption["caption_text"],
                caption.get("ocr_text"),
                json.dumps(caption.get("equations", []), ensure_ascii=True),
                json.dumps(_caption_equation_image_paths(caption), ensure_ascii=True),
                caption.get("equation_source"),
                caption.get("equation_fallback_notes"),
                caption.get("visual_type"),
                caption.get("topic"),
                caption.get("change_score"),
                caption["model_name"],
            ),
        )

    commit_with_retry(connection)


def _video_artifact_folder_name(video_id: int, title: Optional[str] = None) -> str:
    safe_title = sanitize_filename(title or "")
    return "video_{}_{}".format(video_id, safe_title) if safe_title else "video_{}".format(video_id)


def _annotated_dir_for_video(video_id: int, title: Optional[str] = None) -> Path:
    annotated_dir = settings.annotated_frames_dir / _video_artifact_folder_name(video_id, title)
    annotated_dir.mkdir(parents=True, exist_ok=True)
    return annotated_dir


def _equation_crop_dir_for_video(video_id: int, title: Optional[str] = None) -> Path:
    crop_dir = settings.equation_crops_dir / _video_artifact_folder_name(video_id, title)
    crop_dir.mkdir(parents=True, exist_ok=True)
    return crop_dir


def _replace_slide_summaries(connection: sqlite3.Connection, video_id: int, slide_summaries: List[dict]) -> None:
    connection.execute("DELETE FROM slide_summaries WHERE video_id = ?", (video_id,))

    for item in slide_summaries:
        connection.execute(
            """
            INSERT INTO slide_summaries (
                video_id,
                frame_index,
                start_seconds,
                end_seconds,
                frame_path,
                annotated_frame_path,
                caption_text,
                ocr_text,
                equations_text,
                equation_image_paths,
                equation_source,
                equation_fallback_notes,
                visual_type,
                topic,
                transcript_text,
                summary_text,
                key_points,
                transcript_excerpt,
                model_name,
                prompt_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id,
                item["frame_index"],
                item["start_seconds"],
                item["end_seconds"],
                item.get("frame_path"),
                item.get("annotated_frame_path"),
                item.get("caption_text") or "",
                item.get("ocr_text"),
                json.dumps(item.get("equations", []), ensure_ascii=True),
                json.dumps(_caption_equation_image_paths(item), ensure_ascii=True),
                item.get("equation_source"),
                item.get("equation_fallback_notes"),
                item.get("visual_type"),
                item.get("topic"),
                item.get("transcript_text"),
                item.get("summary_text") or "",
                json.dumps(item.get("key_points", []), ensure_ascii=True),
                item.get("transcript_excerpt"),
                item.get("model_name"),
                item.get("prompt_version"),
            ),
        )

    commit_with_retry(connection)


def _debug_dir_for_video(video_id: int, title: Optional[str] = None) -> Path:
    debug_dir = settings.results_dir / "caption_debug" / _video_artifact_folder_name(video_id, title)
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


def _format_seconds(seconds: object) -> str:
    try:
        value = float(seconds or 0.0)
    except (TypeError, ValueError):
        value = 0.0

    minutes, second_value = divmod(int(value), 60)
    hours, minute_value = divmod(minutes, 60)
    return "{:02d}:{:02d}:{:02d}".format(hours, minute_value, second_value)


def _youtube_url_from_description(description: Optional[str]) -> Optional[str]:
    prefix = "Imported from YouTube:"
    if not description or prefix not in description:
        return None
    return description.split(prefix, 1)[1].strip() or None


def _write_transcription_source_debug_file(
    *,
    video_id: int,
    video_row: sqlite3.Row,
    video_path: Path,
    transcription_result: dict,
    audio_path: Optional[Path],
) -> Path:
    debug_dir = _debug_dir_for_video(video_id, video_row["title"])
    source_url = _youtube_url_from_description(video_row["description"])
    source_type = "YouTube import" if source_url else "Uploaded video file"
    transcript_source = transcription_result.get("source")
    transcript_method = (
        "Existing subtitle transcript"
        if transcript_source
        else "Whisper transcription from extracted video audio"
    )

    output_path = debug_dir / "transcription_source.txt"
    lines = [
        "Transcription Source Evidence",
        "=============================",
        "Video ID: {}".format(video_id),
        "Title: {}".format(video_row["title"]),
        "Source type: {}".format(source_type),
        "YouTube URL: {}".format(source_url or "Not a YouTube import"),
        "Stored video file: {}".format(video_path),
        "Transcript method: {}".format(transcript_method),
        "Subtitle transcript file: {}".format(transcript_source or "Not used"),
        "Extracted audio file: {}".format(audio_path or "Not used"),
        "Transcription model/source: {}".format(transcription_result.get("model_name") or "unknown"),
        "Detected language: {}".format(transcription_result.get("language") or "unknown"),
        "Word count: {}".format(transcription_result.get("word_count") or 0),
        "",
        "Meaning:",
        "The transcript was taken from the saved video source above. If a subtitle file is listed, the backend parsed that source subtitle. If an audio file is listed, the backend extracted audio from the saved video and sent that audio to Whisper.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _write_caption_debug_files(video_id: int, title: str, captions: List[dict]) -> List[Path]:
    debug_dir = _debug_dir_for_video(video_id, title)
    written_paths: List[Path] = []

    for index, caption in enumerate(captions, start=1):
        annotated_frame_path = _caption_annotated_frame_path(caption)
        equation_image_paths = _caption_equation_image_paths(caption)
        output_path = debug_dir / "frame_{:04d}_caption.txt".format(index)
        equations = caption.get("equations") or []
        lines = [
            "Frame Caption Evidence",
            "======================",
            "Video ID: {}".format(video_id),
            "Frame number: {}".format(index),
            "Frame image: {}".format(_caption_frame_path(caption)),
            "Annotated frame image: {}".format(annotated_frame_path or "No annotated frame saved."),
            "Frame timestamp: {} ({:.2f}s)".format(
                _format_seconds(caption.get("timestamp_seconds")),
                float(caption.get("timestamp_seconds") or 0.0),
            ),
            "Visual type: {}".format(caption.get("visual_type") or "Not classified"),
            "Topic: {}".format(caption.get("topic") or "Not detected"),
            "Change score: {}".format(caption.get("change_score") if caption.get("change_score") is not None else "Not available"),
            "Visual model: {}".format(caption.get("model_name") or "Not available"),
            "",
            "OCR text from this picture:",
            caption.get("ocr_text") or "No OCR text detected.",
            "",
            "Equations detected from this picture:",
            "\n".join("- {}".format(equation) for equation in equations) if equations else "No equations detected.",
            "Equation source: {}".format(caption.get("equation_source") or "unknown"),
            "Equation fallback notes: {}".format(caption.get("equation_fallback_notes") or "None"),
            "",
            "Original equation image crops:",
            "\n".join("- {}".format(path) for path in equation_image_paths) if equation_image_paths else "No equation crops saved.",
            "",
            "Caption generated from this picture:",
            caption.get("caption_text") or "No caption generated.",
        ]
        output_path.write_text("\n".join(lines), encoding="utf-8")
        written_paths.append(output_path)

    return written_paths


def _debug_stage_dir_for_video(stage_name: str, video_id: int, title: Optional[str] = None) -> Path:
    debug_dir = settings.results_dir / stage_name / _video_artifact_folder_name(video_id, title)
    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


def _write_fusion_debug_files(video_id: int, title: str, fusion_result: dict) -> List[Path]:
    debug_dir = _debug_stage_dir_for_video("fusion_debug", video_id, title)
    outputs = {
        "01_transcript_input.txt": fusion_result.get("transcript_text") or "",
        "02_captions_input.txt": fusion_result.get("captions_text") or "",
        "03_fused_output.txt": fusion_result.get("fused_text") or "",
    }

    written_paths: List[Path] = []
    for filename, content in outputs.items():
        output_path = debug_dir / filename
        output_path.write_text(str(content), encoding="utf-8")
        written_paths.append(output_path)

    return written_paths


def _write_nlp_debug_files(video_id: int, title: str, preprocessing_result: dict) -> List[Path]:
    debug_dir = _debug_stage_dir_for_video("nlp_debug", video_id, title)
    sentences = preprocessing_result.get("sentences") or []
    sentence_lines = [
        "{:04d}. {}".format(index, sentence)
        for index, sentence in enumerate(sentences, start=1)
    ]
    metadata_lines = [
        "NLP Preprocessing Evidence",
        "==========================",
        "Video ID: {}".format(video_id),
        "Title: {}".format(title),
        "Token count after redundancy removal: {}".format(preprocessing_result.get("token_count") or 0),
        "Unique sentence count: {}".format(len(sentences)),
        "",
        "Meaning:",
        "These files show the difference between the fused text before NLP cleaning and the final reduced text sent to summarization.",
    ]
    outputs = {
        "00_metadata.txt": "\n".join(metadata_lines),
        "01_cleaned_transcript.txt": preprocessing_result.get("cleaned_transcript") or "",
        "02_cleaned_captions.txt": preprocessing_result.get("cleaned_captions") or "",
        "03_cleaned_fused_text.txt": preprocessing_result.get("cleaned_fused_text") or "",
        "04_unique_sentences.txt": "\n".join(sentence_lines),
        "05_redundancy_removed_summary_input.txt": preprocessing_result.get("redundancy_removed_text") or "",
    }

    written_paths: List[Path] = []
    for filename, content in outputs.items():
        output_path = debug_dir / filename
        output_path.write_text(str(content), encoding="utf-8")
        written_paths.append(output_path)

    return written_paths


def _upsert_multimodal_output(
    connection: sqlite3.Connection,
    video_id: int,
    fused_text: str,
    redundancy_removed_text: str,
    token_count: int,
) -> None:
    existing = connection.execute(
        "SELECT id FROM multimodal_outputs WHERE video_id = ?",
        (video_id,),
    ).fetchone()

    if existing:
        connection.execute(
            """
            UPDATE multimodal_outputs
            SET
                fused_text = ?,
                redundancy_removed_text = ?,
                token_count = ?
            WHERE video_id = ?
            """,
            (fused_text, redundancy_removed_text, token_count, video_id),
        )
    else:
        connection.execute(
            """
            INSERT INTO multimodal_outputs (
                video_id,
                fused_text,
                redundancy_removed_text,
                token_count
            )
            VALUES (?, ?, ?, ?)
            """,
            (video_id, fused_text, redundancy_removed_text, token_count),
        )

    commit_with_retry(connection)


def _upsert_summary(
    connection: sqlite3.Connection,
    video_id: int,
    summary_title: str,
    summary_text: str,
    structured_summary: dict,
    llm_model: str,
    prompt_version: str,
) -> None:
    existing = connection.execute(
        "SELECT id FROM summaries WHERE video_id = ?",
        (video_id,),
    ).fetchone()

    serialized_summary = json.dumps(structured_summary, ensure_ascii=True)

    if existing:
        connection.execute(
            """
            UPDATE summaries
            SET
                summary_title = ?,
                summary_text = ?,
                structured_summary = ?,
                llm_model = ?,
                prompt_version = ?
            WHERE video_id = ?
            """,
            (summary_title, summary_text, serialized_summary, llm_model, prompt_version, video_id),
        )
    else:
        connection.execute(
            """
            INSERT INTO summaries (
                video_id,
                summary_title,
                summary_text,
                structured_summary,
                llm_model,
                prompt_version
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (video_id, summary_title, summary_text, serialized_summary, llm_model, prompt_version),
        )

    commit_with_retry(connection)


def _upsert_evaluation(
    connection: sqlite3.Connection,
    video_id: int,
    reference_summary: str,
    rouge_1: float,
    rouge_2: float,
    rouge_l: float,
    evaluation_notes: str,
) -> None:
    existing = connection.execute(
        "SELECT id FROM evaluations WHERE video_id = ?",
        (video_id,),
    ).fetchone()

    if existing:
        connection.execute(
            """
            UPDATE evaluations
            SET
                reference_summary = ?,
                rouge_1 = ?,
                rouge_2 = ?,
                rouge_l = ?,
                evaluation_notes = ?
            WHERE video_id = ?
            """,
            (reference_summary, rouge_1, rouge_2, rouge_l, evaluation_notes, video_id),
        )
    else:
        connection.execute(
            """
            INSERT INTO evaluations (
                video_id,
                reference_summary,
                rouge_1,
                rouge_2,
                rouge_l,
                evaluation_notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (video_id, reference_summary, rouge_1, rouge_2, rouge_l, evaluation_notes),
        )

    commit_with_retry(connection)


def run_multimodal_pipeline(video_id: int) -> None:
    connection = create_connection()
    try:
        video_row = connection.execute(
            "SELECT id, title, course_name, description, source_filename, stored_path FROM videos WHERE id = ?",
            (video_id,),
        ).fetchone()

        if not video_row:
            raise ValueError("Video not found for processing.")

        video_path = settings.database_path.parent / video_row["stored_path"]
        if not video_path.exists():
            raise FileNotFoundError("Uploaded video file does not exist: {}".format(video_path))

        video_stem = Path(video_row["stored_path"]).stem
        youtube_url = _youtube_url_from_description(video_row["description"])
        source_type = "YouTube import" if youtube_url else "uploaded video file"

        logger.info(
            "[TRANSCRIPTION SOURCE] Video %s starts processing. Source type=%s; YouTube URL=%s; stored video=%s",
            video_id,
            source_type,
            youtube_url or "not applicable",
            video_path,
        )

        _update_video_status(connection, video_id, "processing")
        _update_processing_job(
            connection,
            video_id,
            "transcription",
            15.0,
            "Checking existing subtitles or YouTube transcript before Whisper.",
        )
        transcription_result = transcribe_from_existing_subtitles(video_path)
        audio_path: Optional[Path] = None

        if transcription_result is None:
            audio_output_name = "{}.wav".format(video_stem)
            audio_path = settings.audio_dir / audio_output_name

            _update_processing_job(connection, video_id, "audio_extraction", 30.0, "No source transcript found. Extracting audio with ffmpeg.")
            extract_audio_from_video(video_path, audio_path)
            logger.info(
                "[TRANSCRIPTION SOURCE] Video %s has no source subtitle transcript. Extracted audio from stored video: %s -> %s",
                video_id,
                video_path,
                audio_path,
            )

            _update_processing_job(connection, video_id, "transcription", 55.0, "Running Whisper transcription.")
            transcription_result = transcribe_audio_file(audio_path, model_name=settings.whisper_model)
            logger.info(
                "[TRANSCRIPTION SOURCE] Video %s transcript generated by Whisper from extracted audio. Audio=%s; model=%s; words=%s",
                video_id,
                audio_path,
                transcription_result.get("model_name"),
                transcription_result.get("word_count"),
            )
        else:
            _update_processing_job(connection, video_id, "transcription", 55.0, "Using existing subtitle transcript and skipping Whisper.")
            logger.info(
                "[TRANSCRIPTION SOURCE] Video %s transcript parsed from source subtitle file. Subtitle=%s; stored video=%s; words=%s",
                video_id,
                transcription_result.get("source"),
                video_path,
                transcription_result.get("word_count"),
            )

        _ensure_video_exists(connection, video_id)
        transcript_debug_path = _write_transcription_source_debug_file(
            video_id=video_id,
            video_row=video_row,
            video_path=video_path,
            transcription_result=transcription_result,
            audio_path=audio_path,
        )
        logger.info(
            "[TRANSCRIPTION SOURCE] Video %s proof file written: %s",
            video_id,
            transcript_debug_path,
        )

        _upsert_transcript(
            connection=connection,
            video_id=video_id,
            raw_text=transcription_result["text"],
            cleaned_text=transcription_result["text"].strip(),
            language_code=transcription_result.get("language"),
            whisper_model=transcription_result["model_name"],
            word_count=transcription_result["word_count"],
        )
        _replace_transcript_segments(connection, video_id, transcription_result.get("segments", []))

        _update_processing_job(
            connection,
            video_id,
            "frame_extraction",
            72.0,
            "Extracting slide-change and scene-change keyframes for educational visual understanding.",
        )
        extracted_frames = extract_frames_from_video(
            video_path=video_path,
            frames_dir=settings.frames_dir,
            frame_interval_seconds=settings.frame_interval_seconds,
            frame_prefix=video_stem,
            scene_change_threshold=settings.scene_change_threshold,
            min_frame_gap_seconds=settings.min_frame_gap_seconds,
            frame_sample_seconds=settings.frame_sample_seconds,
            duplicate_frame_threshold=settings.duplicate_frame_threshold,
            frame_jpeg_quality=settings.frame_jpeg_quality,
            save_all_sampled_frames=settings.save_all_sampled_frames,
        )

        _ensure_video_exists(connection, video_id)
        _update_processing_job(connection, video_id, "captioning", 88.0, "Running OCR, equation recognition, VLM analysis, CLIP topic matching, and LLM reasoning.")
        annotated_output_dir = _annotated_dir_for_video(video_id, video_row["title"])
        caption_results = understand_frames(
            extracted_frames,
            annotated_output_dir=annotated_output_dir,
        )
        caption_results = apply_transcript_equation_fallbacks(
            captions=caption_results,
            transcript_segments=transcription_result.get("segments", []),
            model_name=settings.reasoning_model,
        )
        _ensure_video_exists(connection, video_id)
        _replace_frame_captions(connection, video_id, caption_results)
        caption_debug_paths = _write_caption_debug_files(video_id, video_row["title"], caption_results)
        logger.info(
            "[CAPTION DEBUG] Video %s wrote %s per-frame caption evidence files to %s",
            video_id,
            len(caption_debug_paths),
            _debug_dir_for_video(video_id, video_row["title"]),
        )

        _update_processing_job(connection, video_id, "fusion", 93.0, "Combining transcript and educational visual explanations.")
        fusion_result = build_multimodal_context(transcription_result["text"], caption_results)
        fusion_debug_paths = _write_fusion_debug_files(video_id, video_row["title"], fusion_result)
        logger.info(
            "[FUSION DEBUG] Video %s wrote %s fusion evidence files to %s",
            video_id,
            len(fusion_debug_paths),
            _debug_stage_dir_for_video("fusion_debug", video_id, video_row["title"]),
        )

        _update_processing_job(connection, video_id, "nlp", 97.0, "Cleaning and reducing multimodal content.")
        preprocessing_result = preprocess_multimodal_text(
            transcript_text=fusion_result["transcript_text"],
            captions_text=fusion_result["captions_text"],
            fused_text=fusion_result["fused_text"],
        )
        _ensure_video_exists(connection, video_id)
        nlp_debug_paths = _write_nlp_debug_files(video_id, video_row["title"], preprocessing_result)
        logger.info(
            "[NLP DEBUG] Video %s wrote %s NLP preprocessing evidence files to %s",
            video_id,
            len(nlp_debug_paths),
            _debug_stage_dir_for_video("nlp_debug", video_id, video_row["title"]),
        )

        _upsert_transcript(
            connection=connection,
            video_id=video_id,
            raw_text=transcription_result["text"],
            cleaned_text=preprocessing_result["cleaned_transcript"],
            language_code=transcription_result.get("language"),
            whisper_model=transcription_result["model_name"],
            word_count=transcription_result["word_count"],
        )
        _upsert_multimodal_output(
            connection=connection,
            video_id=video_id,
            fused_text=preprocessing_result["cleaned_fused_text"],
            redundancy_removed_text=preprocessing_result["redundancy_removed_text"],
            token_count=preprocessing_result["token_count"],
        )

        _update_processing_job(connection, video_id, "summarization", 99.0, "Generating educational summary with LLM.")
        summary_result = generate_structured_summary(
            course_name=video_row["course_name"],
            lecture_title=video_row["title"],
            processed_multimodal_text=preprocessing_result["redundancy_removed_text"] or preprocessing_result["cleaned_fused_text"],
        )
        _ensure_video_exists(connection, video_id)
        _upsert_summary(
            connection=connection,
            video_id=video_id,
            summary_title=summary_result["summary_title"],
            summary_text=summary_result["summary_text"],
            structured_summary=summary_result["structured_summary"],
            llm_model=summary_result["model_name"],
            prompt_version=summary_result["prompt_version"],
        )

        slide_summary_captions = [
            {
                **caption,
                "frame_path": _caption_frame_path(caption),
                "annotated_frame_path": _caption_annotated_frame_path(caption),
                "equation_images": _caption_equation_image_paths(caption),
            }
            for caption in caption_results
        ]
        slide_summaries = generate_slide_summaries(
            captions=slide_summary_captions,
            transcript_segments=transcription_result.get("segments", []),
        )
        _replace_slide_summaries(connection, video_id, slide_summaries)

        _update_processing_job(connection, video_id, "evaluation", 99.5, "Evaluating generated summary with ROUGE.")
        existing_evaluation = connection.execute(
            "SELECT reference_summary FROM evaluations WHERE video_id = ?",
            (video_id,),
        ).fetchone()
        reference_bundle = build_reference_summary(
            explicit_reference_summary=existing_evaluation["reference_summary"] if existing_evaluation else None,
            redundancy_removed_text=preprocessing_result["redundancy_removed_text"],
        )
        rouge_result = evaluate_summary_with_rouge(
            reference_text=reference_bundle["reference_summary"],
            candidate_text=summary_result["summary_text"],
        )
        _upsert_evaluation(
            connection=connection,
            video_id=video_id,
            reference_summary=reference_bundle["reference_summary"],
            rouge_1=rouge_result["rouge_1"],
            rouge_2=rouge_result["rouge_2"],
            rouge_l=rouge_result["rouge_l"],
            evaluation_notes=reference_bundle["evaluation_notes"],
        )

        _update_video_status(connection, video_id, "completed")
        _update_processing_job(
            connection,
            video_id,
            "completed",
            100.0,
            "Whisper, educational visual understanding, NLP preprocessing, and LLM summarization completed successfully.",
            completed=True,
        )
    except Exception as error:
        video_still_exists = connection.execute(
            "SELECT id FROM videos WHERE id = ?",
            (video_id,),
        ).fetchone()
        if video_still_exists is None:
            if "video_row" in locals() and video_row is not None:
                from backend.app.services.video_service import cleanup_deleted_video_artifacts

                cleanup_deleted_video_artifacts(
                    video_id=video_id,
                    title=video_row["title"],
                    stored_path=video_row["stored_path"],
                )
            logger.info("Processing stopped because video %s was deleted.", video_id)
            return

        _update_video_status(connection, video_id, "failed")
        _update_processing_job(
            connection,
            video_id,
            "failed",
            100.0,
            "Multimodal pipeline failed: {}".format(error),
            completed=True,
        )
        raise
    finally:
        connection.close()


def get_processing_status(connection: sqlite3.Connection, video_id: int) -> dict:
    row = connection.execute(
        """
        SELECT video_id, stage, progress_percent, status_message, started_at, completed_at, updated_at
        FROM processing_jobs
        WHERE video_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (video_id,),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found for this video.",
        )

    return {
        "video_id": row["video_id"],
        "stage": row["stage"],
        "progress_percent": float(row["progress_percent"]),
        "status_message": row["status_message"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "updated_at": row["updated_at"],
    }
