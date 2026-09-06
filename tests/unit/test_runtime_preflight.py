from pathlib import Path
from hashlib import sha256
import json

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


def test_native_windows_requires_a_verified_hadoop_helper(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(preflight.platform, "system", lambda: "Windows")
    missing = preflight._windows_hadoop_check({})
    assert not missing.ok
    assert "WSL2" in missing.detail

    executable = tmp_path / "hadoop" / "bin" / "winutils.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"organization-approved-test-helper")
    manifest = tmp_path / "helper.json"
    manifest.write_text(json.dumps({
        "hadoop_version": "3.3.4",
        "artifact": str(executable),
        "sha256": sha256(executable.read_bytes()).hexdigest(),
        "provenance": "organization-controlled build",
    }), encoding="utf-8")
    result = preflight._windows_hadoop_check({"HADOOP_HOME": str(tmp_path / "hadoop"), "AGRISHOCK_WINUTILS_MANIFEST": str(manifest)})
    assert result.ok
