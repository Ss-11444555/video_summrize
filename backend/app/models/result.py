"""Processing result data model definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class RougeScore:
    rouge_1: Optional[float]
    rouge_2: Optional[float]
    rouge_l: Optional[float]
