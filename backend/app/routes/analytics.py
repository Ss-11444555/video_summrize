"""Analytics API routes for admin dashboards."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.app.core.database import get_db_connection
from backend.app.core.dependencies import require_roles
from backend.app.services.analytics_service import get_analytics_overview


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
def analytics_overview(
    _: dict = Depends(require_roles("admin")),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return get_analytics_overview(connection)
