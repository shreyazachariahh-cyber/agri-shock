import pytest
from agri_shock.streaming.contracts import EventTimePolicy

def test_watermark_requires_explicit_positive_duration() -> None:
    assert EventTimePolicy(72).spark_duration == "72 hours"
    with pytest.raises(ValueError):
        EventTimePolicy(0)
