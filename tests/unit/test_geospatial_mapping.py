from agri_shock.geospatial.mapping import DistrictBoundary, map_point_to_district

def test_point_maps_to_canonical_district() -> None:
    boundary = DistrictBoundary("IN.MH.NASHIK", "IN.MH", "gsi-2025", ((73, 19), (75, 19), (75, 21), (73, 21)))
    result = map_point_to_district((74, 20), [boundary])
    assert result.district_id == "IN.MH.NASHIK"
    assert result.boundary_version == "gsi-2025"

def test_unmapped_point_is_not_name_matched() -> None:
    boundary = DistrictBoundary("IN.MH.NASHIK", "IN.MH", "gsi-2025", ((73, 19), (75, 19), (75, 21), (73, 21)))
    assert map_point_to_district((80, 20), [boundary]).district_id is None
