from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShockEvidence:
    district_id: str
    commodity_id: str
    shock_type: str
    shock_severity: float
    observed_price: float
    baseline_price: float
    deviation_pct: float
    robust_z_score: float | None
    days_after_shock: int
    control_difference_pct: float | None


def validate_evidence(evidence: ShockEvidence) -> None:
    if not evidence.district_id.strip():
        raise ValueError("district_id must not be empty")

    if not evidence.commodity_id.strip():
        raise ValueError("commodity_id must not be empty")

    if not evidence.shock_type.strip():
        raise ValueError("shock_type must not be empty")

    if not 0 <= evidence.shock_severity <= 1:
        raise ValueError("shock_severity must be between 0 and 1")

    if evidence.observed_price < 0:
        raise ValueError("observed_price must not be negative")

    if evidence.baseline_price <= 0:
        raise ValueError("baseline_price must be positive")

    if evidence.days_after_shock < 0:
        raise ValueError("days_after_shock must not be negative")