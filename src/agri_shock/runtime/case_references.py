"""Write Delta dimensions from a bounded, authoritative case snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agri_shock.geospatial.case_reference import load_case_market_snapshot


def case_reference_rows(snapshot_path: Path, boundary_geojson_path: Path) -> tuple[list[tuple[str, ...]], list[tuple[str, ...]]]:
    """Return strict market and district dimension rows for the case snapshot.

    The supplied geometry is a district reference only.  It is never described
    as a flood footprint and no market outside the bounded snapshot is added.
    """
    markets = load_case_market_snapshot(snapshot_path)
    geojson = json.loads(boundary_geojson_path.read_text(encoding="utf-8"))
    features = geojson.get("features", []) if isinstance(geojson, dict) else []
    market_rows: list[tuple[str, ...]] = []
    district_rows: list[tuple[str, ...]] = []
    for market in markets:
        market_rows.append((str(market["market_id"]), str(market["district_id"]), str(market["state_id"]), str(market["source_state"]), str(market["source_district"]), str(market["source_market"])))
        matched = [feature for feature in features if isinstance(feature, dict) and isinstance(feature.get("properties"), dict) and str(feature["properties"].get("source_state", feature["properties"].get("STATE", feature["properties"].get("state", "")))).casefold() == str(market["source_state"]).casefold() and str(feature["properties"].get("source_district", feature["properties"].get("DISTRICT", feature["properties"].get("district", "")))).casefold() == str(market["source_district"]).casefold()]
        if len(matched) != 1:
            raise ValueError(f"expected exactly one district reference feature for {market['source_state']}/{market['source_district']}")
        geometry = matched[0].get("geometry")
        if not isinstance(geometry, dict):
            raise ValueError("district reference feature has no GeoJSON geometry")
        district_rows.append((str(market["district_id"]), str(market["source_state"]), str(market["source_district"]), json.dumps(geometry, separators=(",", ":"))))
    return market_rows, district_rows


def write_case_references(snapshot_path: Path, boundary_geojson_path: Path, market_path: Path, district_path: Path) -> None:
    from agri_shock.streaming.app import create_smoke_delta_spark
    market_rows, district_rows = case_reference_rows(snapshot_path, boundary_geojson_path)
    spark = create_smoke_delta_spark("agrishock-case-reference-data")
    try:
        spark.createDataFrame(market_rows, ["market_id", "district_id", "state_id", "source_state", "source_district", "source_market"]).write.format("delta").mode("overwrite").save(str(market_path))
        spark.createDataFrame(district_rows, ["district_id", "source_state", "source_district", "geometry_json"]).write.format("delta").mode("overwrite").save(str(district_path))
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Write bounded official case-reference Delta dimensions")
    parser.add_argument("--market-reference", type=Path, required=True)
    parser.add_argument("--district-boundary", type=Path, required=True)
    parser.add_argument("--market-dimension", type=Path, required=True)
    parser.add_argument("--district-dimension", type=Path, required=True)
    args = parser.parse_args()
    write_case_references(args.market_reference, args.district_boundary, args.market_dimension, args.district_dimension)
    print("Wrote bounded case-study market and district Delta dimensions")


if __name__ == "__main__":
    main()
