"""Request/response schemas for user signup."""

from __future__ import annotations

import re
from typing import Literal
from typing import Optional

from pydantic import BaseModel, field_validator


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str
    role: Literal["teacher", "student"]
    workspace_name: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        if len(cleaned) > 100:
            raise ValueError("Full name must be 100 characters or less.")
        return cleaned

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not EMAIL_PATTERN.match(cleaned):
            raise ValueError("Enter a valid email address.")
        if len(cleaned) > 255:
            raise ValueError("Email must be 255 characters or less.")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if len(value) > 128:
            raise ValueError("Password must be 128 characters or less.")
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must include at least one letter and one number.")
        return value

    @field_validator("workspace_name")
    @classmethod
    def validate_workspace_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            return None
        if len(cleaned) < 2:
            raise ValueError("Course name must be at least 2 characters.")
        if len(cleaned) > 120:
            raise ValueError("Course name must be 120 characters or less.")
        return cleaned


class SignupResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

