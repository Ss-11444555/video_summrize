"""User data model definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class UserRecord:
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
