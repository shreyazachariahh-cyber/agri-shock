from pathlib import Path

from agri_shock.runtime import preflight


def test_preflight_reports_missing_configuration_and_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(preflight, "_java_check", lambda: preflight.CheckResult("java", True, "17"))
    monkeypatch.setattr(preflight, "_module_check", lambda name: preflight.CheckResult(name, True, "available"))
    monkeypatch.setattr(preflight.shutil, "which", lambda name: "tool" if name == "docker" else None)
    environment = {
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "ELASTICSEARCH_URL": "http://localhost:9200",
        "WATERMARK_HOURS": "72",
        "SHOCK_LOOKAHEAD_DAYS": "14",
        "DELTA_ROOT": str(tmp_path / "delta"),
        "CHECKPOINT_ROOT": str(tmp_path / "checkpoints"),
        "MARKET_DIMENSION_PATH": str(tmp_path / "missing-market"),
        "DISTRICT_BOUNDARY_PATH": str(tmp_path / "missing-boundary"),
    }
    results = preflight.run_preflight(environment, check_services=False)
    by_name = {result.name: result for result in results}
    assert not by_name["path:MARKET_DIMENSION_PATH"].ok
    assert by_name["path:CHECKPOINT_ROOT"].ok
    assert by_name["env:WATERMARK_HOURS"].ok


def test_invalid_kafka_bootstrap_is_an_actionable_service_failure(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "_java_check", lambda: preflight.CheckResult("java", True, "17"))
    monkeypatch.setattr(preflight, "_module_check", lambda name: preflight.CheckResult(name, True, "available"))
    monkeypatch.setattr(preflight.shutil, "which", lambda name: "tool")
    results = preflight.run_preflight({"KAFKA_BOOTSTRAP_SERVERS": "not-a-host", "ELASTICSEARCH_URL": "http://localhost:9200"})
    kafka = next(result for result in results if result.name == "kafka")
    assert not kafka.ok
    assert "host:port" in kafka.detail
