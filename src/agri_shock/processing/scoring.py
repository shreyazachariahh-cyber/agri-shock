from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True, slots=True)
class ScorePolicy:
    max_weather: float; max_price_decline: float; max_volatility: float; max_temporal: float; max_control: float; high_threshold: float; medium_threshold: float
    def __post_init__(self) -> None:
        if round(sum((self.max_weather, self.max_price_decline, self.max_volatility, self.max_temporal, self.max_control)), 6) != 100:
            raise ValueError("score contribution caps must total 100")

@dataclass(frozen=True, slots=True)
class DistressSignal:
    distress_score: float; risk_level: str; component_scores: Mapping[str, float]; data_confidence: float

def score_signal(weather_severity: float, negative_deviation_pct: float, negative_robust_z: float | None, days_after_shock: int, lookahead_days: int, affected_vs_control_pct: float | None, data_confidence: float, policy: ScorePolicy) -> DistressSignal:
    if not 0 <= data_confidence <= 1 or lookahead_days <= 0 or days_after_shock < 0:
        raise ValueError("invalid confidence or temporal inputs")
    weather = policy.max_weather * min(max(weather_severity, 0), 1)
    price = policy.max_price_decline * min(max(negative_deviation_pct, 0) / 30, 1)
    volatility = policy.max_volatility * min(max(negative_robust_z or 0, 0) / 3, 1)
    temporal = policy.max_temporal * max(0, 1 - days_after_shock / lookahead_days)
    control = 0 if affected_vs_control_pct is None else policy.max_control * min(max(-affected_vs_control_pct, 0) / 20, 1)
    score = round((weather + price + volatility + temporal + control) * data_confidence, 2)
    risk = "HIGH" if score >= policy.high_threshold else "MEDIUM" if score >= policy.medium_threshold else "LOW"
    return DistressSignal(score, risk, {"weather": weather, "price_decline": price, "volatility": volatility, "temporal_proximity": temporal, "control_difference": control}, data_confidence)
