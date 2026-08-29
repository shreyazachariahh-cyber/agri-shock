from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Sequence

@dataclass(frozen=True, slots=True)
class PriceObservation:
    observation_date: date
    modal_price: float

@dataclass(frozen=True, slots=True)
class Baseline:
    median_price: float
    mad: float
    sample_size: int
    season: int

@dataclass(frozen=True, slots=True)
class PriceAnomaly:
    observed_price: float
    baseline_price: float
    deviation_pct: float
    robust_z_score: float | None

def seasonal_baseline(history: Sequence[PriceObservation], target_date: date, minimum_observations: int) -> Baseline | None:
    if minimum_observations <= 0:
        raise ValueError("minimum_observations must be positive")
    values = [item.modal_price for item in history if item.observation_date.month == target_date.month and item.observation_date < target_date]
    if len(values) < minimum_observations:
        return None
    center = median(values)
    return Baseline(float(center), float(median([abs(value - center) for value in values])), len(values), target_date.month)

def price_anomaly(observed_price: float, baseline: Baseline) -> PriceAnomaly:
    if observed_price < 0 or baseline.median_price <= 0:
        raise ValueError("prices and baseline must be positive")
    deviation = (observed_price - baseline.median_price) / baseline.median_price * 100
    robust_z = None if baseline.mad == 0 else (observed_price - baseline.median_price) / (1.4826 * baseline.mad)
    return PriceAnomaly(observed_price, baseline.median_price, deviation, robust_z)

def control_difference(affected: PriceAnomaly, controls: Sequence[PriceAnomaly]) -> float | None:
    return None if not controls else affected.deviation_pct - float(median([control.deviation_pct for control in controls]))
