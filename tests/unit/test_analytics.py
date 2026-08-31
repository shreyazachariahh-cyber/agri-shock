from datetime import date

import pytest

from agri_shock.processing.analytics import (
    PriceObservation,
    price_anomaly,
    seasonal_baseline,
    control_difference,
)


def test_baseline_requires_minimum_observations():
    history = [
        PriceObservation(date(2025, 1, 10), 100),
        PriceObservation(date(2025, 1, 20), 110),
    ]

    result = seasonal_baseline(
        history,
        date(2026, 1, 10),
        minimum_observations=3,
    )

    assert result is None


def test_baseline_uses_historical_median():
    history = [
        PriceObservation(date(2025, 1, 10), 100),
        PriceObservation(date(2025, 1, 20), 110),
        PriceObservation(date(2025, 1, 30), 120),
    ]

    result = seasonal_baseline(
        history,
        date(2026, 1, 10),
        minimum_observations=3,
    )

    assert result is not None
    assert result.median_price == 110
    assert result.sample_size == 3
    assert result.season == 1


def test_price_anomaly_calculates_negative_deviation():
    history = [
        PriceObservation(date(2025, 1, 10), 100),
        PriceObservation(date(2025, 1, 20), 110),
        PriceObservation(date(2025, 1, 30), 120),
    ]

    baseline = seasonal_baseline(
        history,
        date(2026, 1, 10),
        minimum_observations=3,
    )

    anomaly = price_anomaly(80, baseline)

    assert anomaly.observed_price == 80
    assert anomaly.baseline_price == 110
    assert anomaly.deviation_pct < 0
    assert anomaly.robust_z_score is not None


def test_mad_zero_returns_no_robust_z_score():
    history = [
        PriceObservation(date(2025, 1, 10), 100),
        PriceObservation(date(2025, 1, 20), 100),
        PriceObservation(date(2025, 1, 30), 100),
    ]

    baseline = seasonal_baseline(
        history,
        date(2026, 1, 10),
        minimum_observations=3,
    )

    anomaly = price_anomaly(90, baseline)

    assert anomaly.robust_z_score is None


def test_control_difference_uses_median_control_movement():
    affected = price_anomaly(
        70,
        type(
            "Baseline",
            (),
            {"median_price": 100, "mad": 10},
        )(),
    )

    control_a = price_anomaly(
        95,
        type(
            "Baseline",
            (),
            {"median_price": 100, "mad": 10},
        )(),
    )

    control_b = price_anomaly(
        100,
        type(
            "Baseline",
            (),
            {"median_price": 100, "mad": 10},
        )(),
    )

    result = control_difference(affected, [control_a, control_b])

    assert result is not None
    assert result < 0


def test_invalid_price_is_rejected():
    history = [
        PriceObservation(date(2025, 1, 10), 100),
        PriceObservation(date(2025, 1, 20), 100),
        PriceObservation(date(2025, 1, 30), 100),
    ]

    baseline = seasonal_baseline(
        history,
        date(2026, 1, 10),
        minimum_observations=3,
    )

    with pytest.raises(ValueError):
        price_anomaly(-10, baseline)