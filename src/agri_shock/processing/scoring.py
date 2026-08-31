from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from agri_shock.processing.evidence import ShockEvidence


@dataclass(frozen=True, slots=True)
class ScorePolicy:
    max_weather: float
    max_price_decline: float
    max_volatility: float
    max_temporal: float
    max_control: float
    lookahead_days: int
    high_threshold: float
    medium_threshold: float

    def __post_init__(self) -> None:
        total = sum(
            (
                self.max_weather,
                self.max_price_decline,
                self.max_volatility,
                self.max_temporal,
                self.max_control,
            )
        )

        if round(total, 6) != 100:
            raise ValueError("score contribution caps must total 100")

        if self.lookahead_days <= 0:
            raise ValueError("lookahead_days must be positive")

        if not 0 <= self.medium_threshold <= self.high_threshold <= 100:
            raise ValueError("thresholds must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class DistressSignal:
    distress_score: float
    risk_level: str
    component_scores: Mapping[str, float]
    data_confidence: float


def score_signal(
    weather_severity: float,
    negative_deviation_pct: float,
    negative_robust_z: float | None,
    days_after_shock: int,
    lookahead_days: int,
    affected_vs_control_pct: float | None,
    data_confidence: float,
    policy: ScorePolicy,
) -> DistressSignal:

    if not 0 <= data_confidence <= 1:
        raise ValueError("data_confidence must be between 0 and 1")

    if lookahead_days <= 0 or days_after_shock < 0:
        raise ValueError("invalid temporal inputs")

    weather = (
        policy.max_weather
        * min(max(weather_severity, 0), 1)
    )

    price = (
        policy.max_price_decline
        * min(max(negative_deviation_pct, 0) / 30, 1)
    )

    volatility = (
        policy.max_volatility
        * min(max(negative_robust_z or 0, 0) / 3, 1)
    )

    temporal = (
        policy.max_temporal
        * max(
            0,
            1 - days_after_shock / lookahead_days,
        )
    )

    control = (
        0
        if affected_vs_control_pct is None
        else policy.max_control
        * min(
            max(-affected_vs_control_pct, 0) / 20,
            1,
        )
    )

    score = round(
        weather
        + price
        + volatility
        + temporal
        + control,
        2,
    )

    risk = (
        "HIGH"
        if score >= policy.high_threshold
        else "MEDIUM"
        if score >= policy.medium_threshold
        else "LOW"
    )

    return DistressSignal(
        score,
        risk,
        {
            "weather": weather,
            "price_decline": price,
            "volatility": volatility,
            "temporal_proximity": temporal,
            "control_difference": control,
        },
        data_confidence,
    )


def score_evidence(
    evidence: ShockEvidence,
    data_confidence: float,
    policy: ScorePolicy,
) -> DistressSignal:

    negative_deviation = max(
        -evidence.deviation_pct,
        0,
    )

    return score_signal(
        weather_severity=evidence.shock_severity,
        negative_deviation_pct=negative_deviation,
        negative_robust_z=evidence.robust_z_score,
        days_after_shock=evidence.days_after_shock,
        lookahead_days=policy.lookahead_days,
        affected_vs_control_pct=evidence.control_difference_pct,
        data_confidence=data_confidence,
        policy=policy,
    )
