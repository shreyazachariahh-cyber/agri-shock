"""Validate or provision the version-controlled AgriShock Kibana bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_objects(path: Path) -> list[dict[str, object]]:
    objects: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or not isinstance(value.get("type"), str) or not isinstance(value.get("id"), str):
            raise ValueError(f"invalid saved object at line {number}")
        identity = (value["type"], value["id"])
        if identity in seen:
            raise ValueError(f"duplicate saved object {identity}")
        seen.add(identity)
        objects.append(value)
    if not objects:
        raise ValueError("saved-object bundle is empty")
    return objects


def validate_bundle(objects: list[dict[str, object]]) -> None:
    dashboards = [item for item in objects if item["type"] == "dashboard"]
    if not dashboards:
        raise ValueError("bundle must contain a dashboard")
    primary = next((item for item in dashboards if item["id"] == "agrishock-real-historical"), None)
    if primary is None:
        raise ValueError("bundle must contain the real historical dashboard")
    source = str(primary["attributes"]["kibanaSavedObjectMeta"]["searchSourceJSON"])
    if "fixture_kind: replayed_historical" not in source:
        raise ValueError("real dashboard must pin replayed_historical provenance")
    if "70ad06f7c3b849dd56b870c77f9dff20d187c802ec2d6c0eea7374f92b9e6c79" not in source:
        raise ValueError("real dashboard must pin the verified Vellore signal")
    visualizations = {item["id"]: item for item in objects if item["type"] == "visualization"}
    price_comparison = visualizations.get("agrishock-real-price-comparison")
    if price_comparison is None:
        raise ValueError("bundle must contain the real price comparison")
    chart_state = str(price_comparison["attributes"]["visState"])
    if '"type":"vega"' not in chart_state or "baseline_price" not in chart_state or "observed_price" not in chart_state:
        raise ValueError("real price comparison must be a Vega chart over Gold price fields")


def provision(objects: list[dict[str, object]], url: str) -> None:
    for item in objects:
        endpoint = f"{url.rstrip('/')}/api/saved_objects/{item['type']}/{item['id']}?overwrite=true"
        body = json.dumps({"attributes": item.get("attributes", {}), "references": item.get("references", [])}).encode("utf-8")
        request = Request(endpoint, data=body, method="POST", headers={"Content-Type": "application/json", "kbn-xsrf": "agrishock-dashboard-provisioner"})
        try:
            with urlopen(request, timeout=15) as response:
                if response.status not in (200, 201):
                    raise RuntimeError(f"Kibana returned HTTP {response.status} for {item['type']}/{item['id']}")
        except (HTTPError, URLError) as error:
            raise RuntimeError(f"could not provision {item['type']}/{item['id']} into Kibana") from error


def set_dark_appearance(url: str) -> None:
    """Enable Kibana's supported local dark appearance preference."""
    endpoint = f"{url.rstrip('/')}/api/kibana/settings"
    body = json.dumps({"changes": {"theme:darkMode": "enabled"}}).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "kbn-xsrf": "agrishock-dashboard-provisioner"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f"Kibana returned HTTP {response.status} while enabling dark appearance")
    except (HTTPError, URLError) as error:
        raise RuntimeError("could not enable Kibana dark appearance") from error


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision AgriShock Kibana saved objects")
    parser.add_argument("--bundle", type=Path, default=Path("dashboards/kibana/agri_shock_real_historical.ndjson"))
    parser.add_argument("--url", default="http://localhost:5601")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dark-appearance", action="store_true", help="enable Kibana's supported local dark appearance")
    args = parser.parse_args()
    objects = load_objects(args.bundle)
    validate_bundle(objects)
    if args.validate_only:
        print(f"Validated {len(objects)} Kibana saved objects")
        return
    if args.dark_appearance:
        set_dark_appearance(args.url)
    provision(objects, args.url)
    print(f"Provisioned {len(objects)} Kibana saved objects into {args.url}")


if __name__ == "__main__":
    main()
