"""General utility helpers used across the backend."""

from __future__ import annotations

import json
from typing import Any, Optional


def parse_json_text(value: Optional[str]) -> Any:
    if not value:
        return None

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
