"""Streaming policy contracts that can be tested without a Spark runtime."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class EventTimePolicy:
    watermark_hours: int

    def __post_init__(self) -> None:
        if self.watermark_hours <= 0:
            raise ValueError("watermark_hours must be positive and evidence-based")

    @property
    def spark_duration(self) -> str:
        return f"{self.watermark_hours} hours"
