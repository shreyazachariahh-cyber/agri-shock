from agri_shock.processing.confidence import ConfidencePolicy, EvidenceQuality, assess_confidence
from agri_shock.processing.evidence import ShockEvidence
from agri_shock.processing.scoring import SignalPolicy, evaluate_signal

SIGNAL_POLICY = SignalPolicy(20, 30, 20, 10, 20, 14, 70, 40)
CONFIDENCE_POLICY = ConfidencePolicy(5, 20, 10, 0.2, 0.1)

def evidence(control: float | None = -20, days: int = 1, decline: float = -30, z: float | None = -3) -> ShockEvidence:
    return ShockEvidence("IN.KL", "onion", "flood", 0.9, 700, 1000, decline, z, days, control)

def high_quality(control: bool = True):
    return assess_confidence(EvidenceQuality(20, 10, 0.0, 0.0, True, control, True, True), CONFIDENCE_POLICY)

def test_local_control_difference_materially_changes_strength() -> None:
    strong = evaluate_signal(evidence(-20), high_quality(), SIGNAL_POLICY)
    weak = evaluate_signal(evidence(-2), high_quality(), SIGNAL_POLICY)
    assert strong.signal_strength and weak.signal_strength and strong.signal_strength > weak.signal_strength

def test_no_price_decline_is_low_signal() -> None:
    signal = evaluate_signal(evidence(control=0, decline=0, z=0), high_quality(), SIGNAL_POLICY)
    assert signal.signal_level == "LOW"

def test_insufficient_baseline_is_not_scored() -> None:
    confidence = assess_confidence(EvidenceQuality(2, 2, 0, 0, True, True, True, True), CONFIDENCE_POLICY)
    signal = evaluate_signal(evidence(), confidence, SIGNAL_POLICY)
    assert signal.signal_level == "INSUFFICIENT_EVIDENCE"
    assert signal.signal_strength is None

def test_missing_control_lowers_confidence_but_keeps_strength_interpretable() -> None:
    with_control = evaluate_signal(evidence(), high_quality(True), SIGNAL_POLICY)
    without_control = evaluate_signal(evidence(None), high_quality(False), SIGNAL_POLICY)
    assert without_control.data_confidence.value < with_control.data_confidence.value
    assert without_control.signal_strength is not None

def test_temporal_and_shock_components_are_explicit_and_deterministic() -> None:
    first = evaluate_signal(evidence(days=0), high_quality(), SIGNAL_POLICY)
    later = evaluate_signal(evidence(days=14), high_quality(), SIGNAL_POLICY)
    assert first == evaluate_signal(evidence(days=0), high_quality(), SIGNAL_POLICY)
    assert first.component_scores["temporal_proximity"] > later.component_scores["temporal_proximity"]
    assert first.component_scores["shock_severity"] == 18


def test_zero_mad_equivalent_has_no_robust_score_and_remains_interpretable() -> None:
    signal = evaluate_signal(evidence(z=None), high_quality(), SIGNAL_POLICY)
    assert signal.component_scores["robust_abnormality"] == 0
    assert signal.signal_strength is not None

def test_invalid_signal_policy_is_rejected() -> None:
    try:
        SignalPolicy(1, 1, 1, 1, 1, 14, 70, 40)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid policy accepted")


def test_signal_policy_can_be_loaded_from_explicit_environment(monkeypatch) -> None:
    values = {
        "SIGNAL_MAX_SHOCK_SEVERITY": "20",
        "SIGNAL_MAX_PRICE_DECLINE": "30",
        "SIGNAL_MAX_ROBUST_ABNORMALITY": "20",
        "SIGNAL_MAX_TEMPORAL_PROXIMITY": "10",
        "SIGNAL_MAX_CONTROL_DIFFERENCE": "20",
        "SIGNAL_LOOKAHEAD_DAYS": "14",
        "SIGNAL_HIGH_THRESHOLD": "70",
        "SIGNAL_MEDIUM_THRESHOLD": "40",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    assert SignalPolicy.from_environment() == SIGNAL_POLICY
