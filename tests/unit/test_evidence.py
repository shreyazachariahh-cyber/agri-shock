import pytest

from agri_shock.processing.evidence import (
    ShockEvidence,
    validate_evidence,
)


def test_valid_shock_evidence():
    evidence = ShockEvidence(
        district_id="KL-ERN",
        commodity_id="paddy",
        shock_type="flood",
        shock_severity=0.9,
        observed_price=1850,
        baseline_price=2450,
        deviation_pct=-24.49,
        robust_z_score=-3.1,
        days_after_shock=2,
        control_difference_pct=-18.0,
    )

    validate_evidence(evidence)


def test_invalid_weather_severity():
    evidence = ShockEvidence(
        district_id="KL-ERN",
        commodity_id="paddy",
        shock_type="flood",
        shock_severity=1.5,
        observed_price=1850,
        baseline_price=2450,
        deviation_pct=-24.49,
        robust_z_score=-3.1,
        days_after_shock=2,
        control_difference_pct=None,
    )

    with pytest.raises(ValueError):
        validate_evidence(evidence)


def test_negative_days_are_rejected():
    evidence = ShockEvidence(
        district_id="KL-ERN",
        commodity_id="paddy",
        shock_type="flood",
        shock_severity=0.9,
        observed_price=1850,
        baseline_price=2450,
        deviation_pct=-24.49,
        robust_z_score=-3.1,
        days_after_shock=-1,
        control_difference_pct=None,
    )

    with pytest.raises(ValueError):
        validate_evidence(evidence)