"""Actionable local runtime checks; imports no optional runtime package eagerly."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _host_port(bootstrap: str) -> tuple[str, int]:
    host, separator, port = bootstrap.rpartition(":")
    if not separator or not host or not port.isdigit():
        raise ValueError("KAFKA_BOOTSTRAP_SERVERS must be host:port")
    return host, int(port)


def _java_check() -> CheckResult:
    if shutil.which("java") is None:
        return CheckResult("java", False, "Java 17 is required; install a JDK and add it to PATH.")
    result = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
    version = (result.stderr or result.stdout).splitlines()[0] if result.returncode == 0 else "java -version failed"
    return CheckResult("java", result.returncode == 0, version)


def _module_check(name: str) -> CheckResult:
    available = importlib.util.find_spec(name) is not None
    return CheckResult(name, available, "available" if available else f"Install agri-shock[streaming] ({name} missing).")


def _tcp_check(name: str, host: str, port: int) -> CheckResult:
    try:
        with socket.create_connection((host, port), timeout=2):
            return CheckResult(name, True, f"reachable at {host}:{port}")
    except OSError as error:
        return CheckResult(name, False, f"not reachable at {host}:{port}: {error}")


def _http_check(url: str) -> CheckResult:
    try:
        with urlopen(url, timeout=3) as response:
            return CheckResult("elasticsearch", 200 <= response.status < 300, f"{url} returned HTTP {response.status}")
    except (OSError, URLError) as error:
        detail = getattr(error, "reason", error)
        return CheckResult("elasticsearch", False, f"not reachable at {url}: {detail}")


def _root_path_check(name: str, value: str) -> CheckResult:
    if not value:
        return CheckResult(f"path:{name}", False, f"set {name} in .env")
    path = Path(value)
    existing_parent = path
    while not existing_parent.exists() and existing_parent != existing_parent.parent:
        existing_parent = existing_parent.parent
    writable = existing_parent.exists() and os.access(existing_parent, os.W_OK)
    return CheckResult(
        f"path:{name}", writable,
        f"writable parent for {value}" if writable else f"path is not writable: {value}",
    )


def _windows_hadoop_check(env: dict[str, str]) -> CheckResult:
    """Require an auditable helper for direct Windows Spark, never a random binary."""
    if platform.system() != "Windows":
        return CheckResult("windows-hadoop", True, "not required outside native Windows")
    hadoop_home = env.get("HADOOP_HOME", "")
    manifest_path = env.get("AGRISHOCK_WINUTILS_MANIFEST", "")
    if not hadoop_home or not manifest_path:
        return CheckResult(
            "windows-hadoop",
            False,
            "native Windows Spark requires an approved Hadoop 3.3.4 helper; use WSL2 (recommended) or set HADOOP_HOME and AGRISHOCK_WINUTILS_MANIFEST",
        )
    executable = Path(hadoop_home) / "bin" / "winutils.exe"
    manifest = Path(manifest_path)
    if not executable.is_file() or not manifest.is_file():
        return CheckResult("windows-hadoop", False, "HADOOP_HOME/bin/winutils.exe or its manifest is missing")
    try:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        expected_hash = str(metadata["sha256"]).lower()
        actual_hash = sha256(executable.read_bytes()).hexdigest()
        valid = (
            metadata.get("hadoop_version") == "3.3.4"
            and Path(str(metadata["artifact"])).resolve() == executable.resolve()
            and expected_hash == actual_hash
            and expected_hash != "replace-with-the-sha256-of-your-organization-approved-build"
        )
    except (KeyError, OSError, json.JSONDecodeError) as error:
        return CheckResult("windows-hadoop", False, f"invalid approved-helper manifest: {error}")
    return CheckResult(
        "windows-hadoop",
        valid,
        "approved Hadoop 3.3.4 helper verified" if valid else "helper manifest/version/hash verification failed",
    )


def run_preflight(environment: dict[str, str] | None = None, check_services: bool = True) -> list[CheckResult]:
    """Return every result; callers decide whether a failed preflight aborts."""
    env = os.environ if environment is None else environment
    results = [
        CheckResult("python", sys.version_info[:2] == (3, 11), f"running Python {sys.version.split()[0]}; require Python 3.11"),
        CheckResult("virtualenv", sys.prefix != sys.base_prefix, "active virtual environment" if sys.prefix != sys.base_prefix else "activate the project virtual environment"),
        _java_check(),
        _module_check("pyspark"),
        _module_check("delta"),
        _module_check("sedona"),
        CheckResult("docker", shutil.which("docker") is not None, "available" if shutil.which("docker") else "install Docker Desktop and ensure docker is on PATH"),
        _windows_hadoop_check(env),
    ]
    required = (
        "WATERMARK_HOURS", "SHOCK_LOOKAHEAD_DAYS", "DELTA_ROOT", "CHECKPOINT_ROOT",
        "MARKET_DIMENSION_PATH", "DISTRICT_BOUNDARY_PATH",
    )
    for name in required:
        value = env.get(name, "")
        results.append(CheckResult(f"env:{name}", bool(value), "configured" if value else f"set {name} in .env"))
    for name in ("MARKET_DIMENSION_PATH", "DISTRICT_BOUNDARY_PATH"):
        value = env.get(name, "")
        if value:
            results.append(CheckResult(f"path:{name}", Path(value).exists(), f"{value}" if Path(value).exists() else f"missing path: {value}"))
    for name in ("DELTA_ROOT", "CHECKPOINT_ROOT"):
        results.append(_root_path_check(name, env.get(name, "")))
    if check_services:
        bootstrap = env.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        try:
            host, port = _host_port(bootstrap)
            results.append(_tcp_check("kafka", host, port))
        except ValueError as error:
            results.append(CheckResult("kafka", False, str(error)))
        results.append(_http_check(env.get("ELASTICSEARCH_URL", "http://localhost:9200")))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Check AgriShock local runtime prerequisites")
    parser.add_argument("--skip-services", action="store_true", help="skip Kafka/Elasticsearch reachability only")
    args = parser.parse_args()
    results = run_preflight(check_services=not args.skip_services)
    for result in results:
        print(f"{'PASS' if result.ok else 'FAIL'} {result.name}: {result.detail}")
    if not all(result.ok for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
