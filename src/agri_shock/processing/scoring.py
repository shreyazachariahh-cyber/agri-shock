"""Transparent non-causal market shock signal evaluation."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

from agri_shock.processing.confidence import DataConfidence
from agri_shock.processing.evidence import ShockEvidence


def _required_float(name: str) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        raise ValueError(f"{name} must be configured")
    return float(value)


def _required_int(name: str) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        raise ValueError(f"{name} must be configured")
    return int(value)


@dataclass(frozen=True, slots=True)
class SignalPolicy:
    """Explicit, reviewable caps and thresholds for an analytical signal."""

    max_shock_severity: float
    max_price_decline: float
    max_robust_abnormality: float
    max_temporal_proximity: float
    max_control_difference: float
    lookahead_days: int
    high_threshold: float
    medium_threshold: float

    def __post_init__(self) -> None:
        contribution_caps = (
            self.max_shock_severity,
            self.max_price_decline,
            self.max_robust_abnormality,
            self.max_temporal_proximity,
            self.max_control_difference,
        )
        if round(sum(contribution_caps), 6) != 100:
            raise ValueError("signal contribution caps must total 100")
        if any(value < 0 for value in contribution_caps):
            raise ValueError("signal contribution caps cannot be negative")
        if self.lookahead_days <= 0:
            raise ValueError("lookahead_days must be positive")
        if not 0 <= self.medium_threshold <= self.high_threshold <= 100:
            raise ValueError("thresholds must be between 0 and 100")

    @classmethod
    def from_environment(cls) -> "SignalPolicy":
        """Load a deliberately explicit policy at the process boundary.

        No scoring defaults are hidden in code: deployment must choose and
        document its own contribution caps and alert thresholds.
        """

        return cls(
            max_shock_severity=_required_float("SIGNAL_MAX_SHOCK_SEVERITY"),
            max_price_decline=_required_float("SIGNAL_MAX_PRICE_DECLINE"),
            max_robust_abnormality=_required_float("SIGNAL_MAX_ROBUST_ABNORMALITY"),
            max_temporal_proximity=_required_float("SIGNAL_MAX_TEMPORAL_PROXIMITY"),
            max_control_difference=_required_float("SIGNAL_MAX_CONTROL_DIFFERENCE"),
            lookahead_days=_required_int("SIGNAL_LOOKAHEAD_DAYS"),
            high_threshold=_required_float("SIGNAL_HIGH_THRESHOLD"),
            medium_threshold=_required_float("SIGNAL_MEDIUM_THRESHOLD"),
        )


@dataclass(frozen=True, slots=True)
class MarketShockSignal:
    signal_strength: float | None
    signal_level: str
    component_scores: Mapping[str, float]
    data_confidence: DataConfidence


def evaluate_signal(
    evidence: ShockEvidence,
    confidence: DataConfidence,
    policy: SignalPolicy,
) -> MarketShockSignal:
    """Evaluate statistical co-occurrence; confidence never changes strength."""
    if not confidence.is_sufficient:
        return MarketShockSignal(None, "INSUFFICIENT_EVIDENCE", {}, confidence)

    decline_pct = max(-evidence.deviation_pct, 0)
    robust_decline = max(-(evidence.robust_z_score or 0), 0)
    weather = policy.max_shock_severity * evidence.shock_severity
    price = policy.max_price_decline * min(decline_pct / 30, 1)
    robust = policy.max_robust_abnormality * min(robust_decline / 3, 1)
    temporal = policy.max_temporal_proximity * max(
        0, 1 - evidence.days_after_shock / policy.lookahead_days
    )
    control = 0.0
    if evidence.control_difference_pct is not None:
        control = policy.max_control_difference * min(
            max(-evidence.control_difference_pct, 0) / 20, 1
        )

    strength = round(weather + price + robust + temporal + control, 2)
    level = (
        "HIGH"
        if strength >= policy.high_threshold
        else "MEDIUM"
        if strength >= policy.medium_threshold
        else "LOW"
    )
    return MarketShockSignal(
        strength,
        level,
        {
            "shock_severity": round(weather, 2),
            "price_decline": round(price, 2),
            "robust_abnormality": round(robust, 2),
            "temporal_proximity": round(temporal, 2),
            "control_difference": round(control, 2),
        },
        confidence,
    )
