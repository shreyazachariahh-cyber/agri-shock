import pytest

from agri_shock.common.config import Settings
from agri_shock.streaming.app import KAFKA_PACKAGE, SEDONA_PACKAGE, start_application


def test_spark_kafka_package_matches_locked_runtime() -> None:
    assert KAFKA_PACKAGE.endswith(":3.5.6")
    assert "_2.12" in KAFKA_PACKAGE
    assert "sedona-spark-shaded-3.5_2.12" in SEDONA_PACKAGE


def test_streaming_requires_explicit_watermark() -> None:
    settings = Settings("development", "localhost:9092", "http://localhost:9200", "INFO", None, None, "data/delta", "data/checkpoints", None, None)
    with pytest.raises(ValueError, match="WATERMARK_HOURS"):
        start_application(settings)


def test_streaming_requires_versioned_geographic_references() -> None:
    settings = Settings("development", "localhost:9092", "http://localhost:9200", "INFO", 14, 72, "data/delta", "data/checkpoints", None, None)
    with pytest.raises(ValueError, match="MARKET_DIMENSION_PATH"):
        start_application(settings)
