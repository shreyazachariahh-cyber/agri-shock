from pathlib import Path

from scripts.provision_kibana_dashboard import load_objects, provision, validate_bundle


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "dashboards" / "kibana" / "agri_shock_real_historical.ndjson"


def test_real_historical_dashboard_bundle_is_valid_and_pinned() -> None:
    objects = load_objects(BUNDLE)
    validate_bundle(objects)
    primary = next(item for item in objects if item["type"] == "dashboard" and item["id"] == "agrishock-real-historical")
    source = primary["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"]
    assert "fixture_kind: replayed_historical" in source
    assert "synthetic_demo" not in source
    assert len(objects) == 11


def test_dashboard_metric_panels_use_supported_gold_fields() -> None:
    objects = load_objects(BUNDLE)
    visualizations = {item["id"]: item for item in objects if item["type"] == "visualization"}
    for identifier, field in {
        "agrishock-real-signal-strength": "signal_strength",
        "agrishock-real-confidence": "data_confidence.value",
        "agrishock-real-observed-price": "observed_price",
        "agrishock-real-baseline-price": "baseline_price",
        "agrishock-real-deviation": "deviation_pct",
        "agrishock-real-robust-z": "robust_z_score",
    }.items():
        assert field in visualizations[identifier]["attributes"]["visState"]


def test_provision_uses_stable_saved_object_ids(monkeypatch) -> None:
    objects = load_objects(BUNDLE)
    requests = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr("scripts.provision_kibana_dashboard.urlopen", fake_urlopen)
    provision(objects, "http://kibana.test/")

    assert len(requests) == len(objects)
    assert all(request.method == "POST" for request, _timeout in requests)
    assert all("overwrite=true" in request.full_url for request, _timeout in requests)
    assert all(request.headers["Kbn-xsrf"] == "agrishock-dashboard-provisioner" for request, _timeout in requests)
