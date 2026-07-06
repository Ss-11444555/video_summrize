"""Video data model definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class VideoRecord:
    id: int
    title: str
    course_name: str
    module_week: Optional[str]
    owner_id: int
    status: str
    is_published: bool
