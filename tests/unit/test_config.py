import pytest

from agri_shock.common.config import Settings


def test_settings_use_safe_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KAFKA_BOOTSTRAP_SERVERS", raising=False)
    settings = Settings.from_environment()
    assert settings.kafka_bootstrap_servers == "localhost:9092"
    assert settings.shock_lookahead_days is None


def test_settings_reject_non_positive_watermark(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WATERMARK_HOURS", "0")
    with pytest.raises(ValueError, match="WATERMARK_HOURS"):
        Settings.from_environment()
