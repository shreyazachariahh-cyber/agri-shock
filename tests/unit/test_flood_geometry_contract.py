import json
from datetime import datetime, timezone

from agri_shock.ingestion.normalizers import normalize_flood


def test_flood_normalization_serializes_geometry_for_silver_spatial_processing() -> None:
    event = normalize_flood(
        {
            "properties": {
                "eventid": "1102678",
                "fromdate": "2024-06-10",
                "todate": "2024-06-12",
                "alertlevel": "orange",
            },
            "geometry": {"type": "Point", "coordinates": [94.1, 27.2]},
        },
        ingestion_time=datetime(2024, 6, 13, tzinfo=timezone.utc),
    )
    assert json.loads(event.payload["geometry_json"])["type"] == "Point"
    assert event.event_time == datetime(2024, 6, 10, tzinfo=timezone.utc)
