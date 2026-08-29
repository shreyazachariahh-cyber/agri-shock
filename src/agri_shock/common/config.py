"""Configuration at the process boundary; secrets remain in environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _positive_int_or_none(value: str | None, name: str) -> int | None:
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str
    kafka_bootstrap_servers: str
    elasticsearch_url: str
    log_level: str
    shock_lookahead_days: int | None
    watermark_hours: int | None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            environment=os.getenv("AGRISHOCK_ENV", "development"),
            kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            elasticsearch_url=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            shock_lookahead_days=_positive_int_or_none(os.getenv("SHOCK_LOOKAHEAD_DAYS"), "SHOCK_LOOKAHEAD_DAYS"),
            watermark_hours=_positive_int_or_none(os.getenv("WATERMARK_HOURS"), "WATERMARK_HOURS"),
        )
