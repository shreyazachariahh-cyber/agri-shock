import pytest
from agri_shock.streaming.joins import ShockJoinPolicy

def test_lookahead_must_be_positive() -> None:
    assert ShockJoinPolicy(14).lookahead_days == 14
    with pytest.raises(ValueError):
        ShockJoinPolicy(0)
