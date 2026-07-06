"""Helper functions for file saving and path management."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    return safe_name.strip("._") or "uploaded_video"


async def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = await upload_file.read()
    destination.write_bytes(content)
