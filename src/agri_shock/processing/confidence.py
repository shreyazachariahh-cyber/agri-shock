"""Evidence-quality confidence, deliberately independent from signal strength."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ConfidencePolicy:
    minimum_baseline_observations: int
    target_baseline_observations: int
    target_unique_trading_days: int
    maximum_missing_rate: float
    maximum_duplicate_rate: float
    def __post_init__(self) -> None:
        if not 0 < self.minimum_baseline_observations <= self.target_baseline_observations:
            raise ValueError("baseline observation thresholds are invalid")
        if self.target_unique_trading_days <= 0 or not 0 <= self.maximum_missing_rate <= 1 or not 0 <= self.maximum_duplicate_rate <= 1:
            raise ValueError("confidence policy rates are invalid")

@dataclass(frozen=True, slots=True)
class EvidenceQuality:
    historical_observations: int
    unique_trading_days: int
    missing_data_rate: float
    duplicate_rate: float
    geography_canonicalized: bool
    has_control_comparison: bool
    shock_time_known: bool
    required_fields_present: bool
    def __post_init__(self) -> None:
        if self.historical_observations < 0 or self.unique_trading_days < 0:
            raise ValueError("observation counts cannot be negative")
        if not 0 <= self.missing_data_rate <= 1 or not 0 <= self.duplicate_rate <= 1:
            raise ValueError("data rates must be between 0 and 1")

@dataclass(frozen=True, slots=True)
class DataConfidence:
    value: float
    is_sufficient: bool
    reasons: tuple[str, ...]

def assess_confidence(quality: EvidenceQuality, policy: ConfidencePolicy) -> DataConfidence:
    reasons: list[str] = []
    if quality.historical_observations < policy.minimum_baseline_observations:
        reasons.append("insufficient_historical_baseline")
    if not quality.geography_canonicalized:
        reasons.append("geography_not_canonicalized")
    if not quality.shock_time_known:
        reasons.append("shock_time_unknown")
    if not quality.required_fields_present:
        reasons.append("required_fields_missing")
    if not quality.has_control_comparison:
        reasons.append("control_comparison_unavailable")
    if quality.missing_data_rate > policy.maximum_missing_rate:
        reasons.append("missing_data_rate_exceeds_policy")
    if quality.duplicate_rate > policy.maximum_duplicate_rate:
        reasons.append("duplicate_rate_exceeds_policy")
    components = (min(quality.historical_observations / policy.target_baseline_observations, 1), min(quality.unique_trading_days / policy.target_unique_trading_days, 1), 1 - quality.missing_data_rate, 1 - quality.duplicate_rate, float(quality.geography_canonicalized), float(quality.has_control_comparison), float(quality.shock_time_known), float(quality.required_fields_present))
    insufficient = {"insufficient_historical_baseline", "geography_not_canonicalized", "shock_time_unknown", "required_fields_missing"}
    return DataConfidence(round(sum(components) / len(components), 3), not any(reason in insufficient for reason in reasons), tuple(reasons))
