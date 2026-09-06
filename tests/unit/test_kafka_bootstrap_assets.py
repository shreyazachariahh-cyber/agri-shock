from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_has_separate_host_and_container_listeners() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "INTERNAL://kafka:9092" in compose
    assert "EXTERNAL://localhost:9092" in compose
    assert '"9092:29092"' in compose
    assert "kafka-init:" in compose


def test_topic_bootstrap_is_idempotent_and_complete() -> None:
    script = (ROOT / "scripts" / "init-kafka-topics.sh").read_text(encoding="utf-8")
    assert "--if-not-exists" in script
    for topic in ("mandi-prices", "weather-events", "flood-events", "market-shock-signals", "dead-letter-events"):
        assert f"create_topic {topic}" in script
