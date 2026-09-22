from agri_shock.geospatial.association import associate_reported_district


EVENT = {"event_id": "nrsc-vellore", "payload": {"reported_state": "Tamil Nadu", "reported_district": "Vellore", "geometry_json": None}}
REFERENCES = ({"source_state": "Tamil Nadu", "source_district": "Vellore", "district_id": "in:tn:vellore"},)


def test_exact_reported_district_associates_without_flood_geometry() -> None:
    result = associate_reported_district(EVENT, REFERENCES)
    assert result is not None
    assert result.district_id == "in:tn:vellore"
    assert result.method == "source_reported_district"
    assert result.uses_flood_geometry is False


def test_wrong_or_ambiguous_district_does_not_associate() -> None:
    wrong = {**EVENT, "payload": {**EVENT["payload"], "reported_district": "Chennai"}}
    assert associate_reported_district(wrong, REFERENCES) is None
    assert associate_reported_district(EVENT, REFERENCES + REFERENCES) is None


def test_replay_is_deterministic_and_boundary_is_not_flood_geometry() -> None:
    first = associate_reported_district(EVENT, REFERENCES)
    assert first == associate_reported_district(EVENT, REFERENCES)
    geometry_event = {**EVENT, "payload": {**EVENT["payload"], "geometry_json": "{\\\"type\\\":\\\"Polygon\\\"}"}}
    assert associate_reported_district(geometry_event, REFERENCES) is None
