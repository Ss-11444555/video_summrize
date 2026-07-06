"""Business logic for processed outputs and evaluation results."""

from __future__ import annotations

import sqlite3

from fastapi import HTTPException, status

from backend.app.services.video_service import can_access_video
from backend.app.utils.helpers import parse_json_text


def _match_transcript_at_timestamp(transcript_segments: list[dict], timestamp_seconds: float) -> dict:
    overlapping_segments = [
        segment
        for segment in transcript_segments
        if segment["start_seconds"] <= timestamp_seconds <= segment["end_seconds"]
    ]

    if not overlapping_segments and transcript_segments:
        nearest_segment = min(
            transcript_segments,
            key=lambda segment: min(
                abs(segment["start_seconds"] - timestamp_seconds),
                abs(segment["end_seconds"] - timestamp_seconds),
            ),
        )
        overlapping_segments = [nearest_segment]

    if not overlapping_segments:
        return {
            "text": None,
            "start_seconds": None,
            "end_seconds": None,
        }

    return {
        "text": " ".join(segment["text"] for segment in overlapping_segments).strip(),
        "start_seconds": min(segment["start_seconds"] for segment in overlapping_segments),
        "end_seconds": max(segment["end_seconds"] for segment in overlapping_segments),
    }


def _parse_equations(value: str | None) -> list[str]:
    parsed = parse_json_text(value)
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    if value:
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _parse_string_list(value: str | None) -> list[str]:
    parsed = parse_json_text(value)
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    if value:
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def get_video_result(connection: sqlite3.Connection, video_id: int, current_user: dict) -> dict:
    video_row = connection.execute(
        """
        SELECT videos.*, users.full_name AS owner_name
        FROM videos
        JOIN users ON users.id = videos.owner_id
        WHERE videos.id = ?
        """,
        (video_id,),
    ).fetchone()

    if not video_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    if not can_access_video(connection, video_row, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot access this result.")

    transcript_row = connection.execute(
        "SELECT * FROM transcripts WHERE video_id = ?",
        (video_id,),
    ).fetchone()
    fusion_row = connection.execute(
        "SELECT * FROM multimodal_outputs WHERE video_id = ?",
        (video_id,),
    ).fetchone()
    summary_row = connection.execute(
        "SELECT * FROM summaries WHERE video_id = ?",
        (video_id,),
    ).fetchone()
    evaluation_row = connection.execute(
        "SELECT * FROM evaluations WHERE video_id = ?",
        (video_id,),
    ).fetchone()
    caption_rows = connection.execute(
        """
        SELECT
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
            change_score
        FROM frame_captions
        WHERE video_id = ?
        ORDER BY frame_timestamp_seconds ASC
        """,
        (video_id,),
    ).fetchall()
    slide_summary_rows = connection.execute(
        """
        SELECT
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
            transcript_excerpt
        FROM slide_summaries
        WHERE video_id = ?
        ORDER BY frame_index ASC, start_seconds ASC
        """,
        (video_id,),
    ).fetchall()
    transcript_segment_rows = connection.execute(
        """
        SELECT start_seconds, end_seconds, segment_text
        FROM transcript_segments
        WHERE video_id = ?
        ORDER BY start_seconds ASC
        """,
        (video_id,),
    ).fetchall()
    transcript_segments = [
        {
            "start_seconds": float(row["start_seconds"]),
            "end_seconds": float(row["end_seconds"]),
            "text": row["segment_text"],
        }
        for row in transcript_segment_rows
    ]

    return {
        "video_id": video_row["id"],
        "title": video_row["title"],
        "course_name": video_row["course_name"],
        "transcript": transcript_row["raw_text"] if transcript_row else None,
        "cleaned_transcript": transcript_row["cleaned_text"] if transcript_row else None,
        "transcript_segments": transcript_segments,
        "captions": [
            {
                "timestamp_seconds": float(row["frame_timestamp_seconds"]),
                "frame_path": row["frame_path"],
                "annotated_frame_path": row["annotated_frame_path"],
                "caption_text": row["caption_text"],
                "ocr_text": row["ocr_text"],
                "equations": _parse_equations(row["equations_text"]),
                "equation_images": _parse_string_list(row["equation_image_paths"]),
                "equation_source": row["equation_source"],
                "equation_fallback_notes": row["equation_fallback_notes"],
                "visual_type": row["visual_type"],
                "topic": row["topic"],
                "change_score": row["change_score"],
                "transcript_text": transcript_match["text"],
                "transcript_start_seconds": transcript_match["start_seconds"],
                "transcript_end_seconds": transcript_match["end_seconds"],
            }
            for row in caption_rows
            for transcript_match in [
                _match_transcript_at_timestamp(transcript_segments, float(row["frame_timestamp_seconds"]))
            ]
        ],
        "slide_summaries": [
            {
                "frame_index": int(row["frame_index"]),
                "start_seconds": float(row["start_seconds"]),
                "end_seconds": float(row["end_seconds"]),
                "frame_path": row["frame_path"],
                "annotated_frame_path": row["annotated_frame_path"],
                "caption_text": row["caption_text"],
                "ocr_text": row["ocr_text"],
                "equations": _parse_equations(row["equations_text"]),
                "equation_images": _parse_string_list(row["equation_image_paths"]),
                "equation_source": row["equation_source"],
                "equation_fallback_notes": row["equation_fallback_notes"],
                "visual_type": row["visual_type"],
                "topic": row["topic"],
                "transcript_text": row["transcript_text"],
                "summary_text": row["summary_text"],
                "key_points": _parse_equations(row["key_points"]),
                "transcript_excerpt": row["transcript_excerpt"],
            }
            for row in slide_summary_rows
        ],
        "fused_text": fusion_row["fused_text"] if fusion_row else None,
        "redundancy_removed_text": fusion_row["redundancy_removed_text"] if fusion_row else None,
        "summary_title": summary_row["summary_title"] if summary_row else None,
        "summary_text": summary_row["summary_text"] if summary_row else None,
        "structured_summary": parse_json_text(summary_row["structured_summary"]) if summary_row else None,
        "evaluation": {
            "rouge_1": evaluation_row["rouge_1"] if evaluation_row else None,
            "rouge_2": evaluation_row["rouge_2"] if evaluation_row else None,
            "rouge_l": evaluation_row["rouge_l"] if evaluation_row else None,
            "evaluation_notes": evaluation_row["evaluation_notes"] if evaluation_row else None,
        } if evaluation_row else None,
    }
