"""Business logic for dashboard and admin analytics."""

from __future__ import annotations

import sqlite3


def get_analytics_overview(connection: sqlite3.Connection) -> dict:
    user_count = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    video_count = connection.execute("SELECT COUNT(*) AS total FROM videos").fetchone()["total"]
    completed_count = connection.execute(
        "SELECT COUNT(*) AS total FROM videos WHERE status = 'completed'"
    ).fetchone()["total"]
    published_count = connection.execute(
        "SELECT COUNT(*) AS total FROM videos WHERE is_published = 1"
    ).fetchone()["total"]
    evaluation_row = connection.execute(
        """
        SELECT
            AVG(rouge_1) AS avg_rouge_1,
            AVG(rouge_2) AS avg_rouge_2,
            AVG(rouge_l) AS avg_rouge_l
        FROM evaluations
        """
    ).fetchone()

    return {
        "total_users": user_count,
        "total_videos": video_count,
        "completed_videos": completed_count,
        "published_videos": published_count,
        "average_rouge_1": evaluation_row["avg_rouge_1"],
        "average_rouge_2": evaluation_row["avg_rouge_2"],
        "average_rouge_l": evaluation_row["avg_rouge_l"],
    }
