"""Extract a bounded WGS84 district reference from NWIC/GSI GeoJSON.

NWIC's published district resource declares EPSG:7755 (India NSF Lambert
Conformal Conic).  GeoJSON consumed by the current Sedona pipeline is WGS84
longitude/latitude, so source coordinates must be transformed explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import atan, atan2, cos, isfinite, log, pi, sin, sqrt, tan
from pathlib import Path
from typing import Any, Iterable, Mapping


NWIC_SOURCE_CRS = "urn:ogc:def:crs:EPSG::7755"
TARGET_GEOJSON_CRS = "EPSG:4326"
NWIC_GSI_SOURCE_URL = (
    "https://nwdp.nwic.gov.in/dataset/6c1af675-1dec-4927-882c-c1ba9d73f76b/"
    "resource/8d9aa2e9-9806-4f26-a4ac-48ba21e9b96d/download/district_nwic_geojson.zip"
)


class BoundaryValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BoundaryExtraction:
    feature_count: int
    source_geojson_sha256: str
    source_zip_sha256: str
    district_id: str
    source_feature_id: int
    geometry_type: str
    source_crs: str
    target_crs: str


# EPSG:7755 / WGS 84 India NSF LCC, Lambert Conformal Conic (2SP).
_A = 6378137.0
_INVERSE_FLATTENING = 298.257223563
_E2 = (1 / _INVERSE_FLATTENING) * (2 - (1 / _INVERSE_FLATTENING))
_E = sqrt(_E2)
_LAT_0 = 24.0 * pi / 180
_LON_0 = 80.0 * pi / 180
_LAT_1 = 12.472955 * pi / 180
_LAT_2 = 35.1728044444444 * pi / 180
_FALSE_EASTING = 4_000_000.0
_FALSE_NORTHING = 4_000_000.0


def _m(latitude: float) -> float:
    return cos(latitude) / sqrt(1 - _E2 * sin(latitude) ** 2)


def _t(latitude: float) -> float:
    return tan(pi / 4 - latitude / 2) / ((1 - _E * sin(latitude)) / (1 + _E * sin(latitude))) ** (_E / 2)


_N = (log(_m(_LAT_1)) - log(_m(_LAT_2))) / (log(_t(_LAT_1)) - log(_t(_LAT_2)))
_F = _m(_LAT_1) / (_N * _t(_LAT_1) ** _N)
_RHO_0 = _A * _F * _t(_LAT_0) ** _N


def inverse_epsg_7755(easting: float, northing: float) -> tuple[float, float]:
    """Return WGS84 `(longitude, latitude)` for one EPSG:7755 coordinate."""
    if not isfinite(easting) or not isfinite(northing):
        raise BoundaryValidationError("nonfinite_source_coordinate")
    dx = easting - _FALSE_EASTING
    dy = _RHO_0 - (northing - _FALSE_NORTHING)
    rho = sqrt(dx * dx + dy * dy)
    if _N < 0:
        rho = -rho
    t_value = (rho / (_A * _F)) ** (1 / _N)
    latitude = pi / 2 - 2 * atan(t_value)
    for _ in range(12):
        next_latitude = pi / 2 - 2 * atan(
            t_value * ((1 - _E * sin(latitude)) / (1 + _E * sin(latitude))) ** (_E / 2)
        )
        if abs(next_latitude - latitude) < 1e-13:
            latitude = next_latitude
            break
        latitude = next_latitude
    longitude = _LON_0 + atan2(dx, dy) / _N
    result = (longitude * 180 / pi, latitude * 180 / pi)
    if not all(isfinite(value) for value in result):
        raise BoundaryValidationError("nonfinite_transformed_coordinate")
    return result


def _coordinates(geometry: Mapping[str, Any]) -> Iterable[tuple[float, float]]:
    if geometry.get("type") != "MultiPolygon":
        raise BoundaryValidationError("expected_multipolygon")
    polygons = geometry.get("coordinates")
    if not isinstance(polygons, list) or not polygons:
        raise BoundaryValidationError("missing_multipolygon_coordinates")
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise BoundaryValidationError("invalid_polygon")
        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise BoundaryValidationError("invalid_ring")
            if ring[0] != ring[-1]:
                raise BoundaryValidationError("unclosed_ring")
            for position in ring:
                if not isinstance(position, list) or len(position) < 2:
                    raise BoundaryValidationError("invalid_position")
                x, y = float(position[0]), float(position[1])
                if not isfinite(x) or not isfinite(y):
                    raise BoundaryValidationError("nonfinite_source_coordinate")
                yield x, y


def _segments_intersect(first: tuple[float, float], second: tuple[float, float], third: tuple[float, float], fourth: tuple[float, float]) -> bool:
    def orient(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (orient(first, second, third) * orient(first, second, fourth) < 0 and orient(third, fourth, first) * orient(third, fourth, second) < 0)


def _validate_transformed_rings(coordinates: Any) -> None:
    for polygon in coordinates:
        for ring in polygon:
            points = [(float(point[0]), float(point[1])) for point in ring]
            if len(points) < 4 or points[0] != points[-1]:
                raise BoundaryValidationError("invalid_transformed_ring")
            for longitude, latitude in points:
                if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                    raise BoundaryValidationError("transformed_coordinate_out_of_wgs84_bounds")
            for index in range(len(points) - 1):
                for other in range(index + 2, len(points) - 1):
                    if index == 0 and other == len(points) - 2:
                        continue
                    if _segments_intersect(points[index], points[index + 1], points[other], points[other + 1]):
                        raise BoundaryValidationError("self_intersecting_transformed_ring")


def _transform_multipolygon(geometry: Mapping[str, Any]) -> dict[str, Any]:
    list(_coordinates(geometry))  # validates source structure before transforming
    transformed = [
        [[list(inverse_epsg_7755(float(position[0]), float(position[1]))) for position in ring] for ring in polygon]
        for polygon in geometry["coordinates"]
    ]
    _validate_transformed_rings(transformed)
    return {"type": "MultiPolygon", "coordinates": transformed}


def extract_vellore_boundary(source_geojson: Path, source_zip_sha256: str, output_path: Path) -> BoundaryExtraction:
    """Select exactly one official Vellore feature and write WGS84 GeoJSON."""
    normalized_zip_hash = source_zip_sha256.lower()
    if len(normalized_zip_hash) != 64 or any(character not in "0123456789abcdef" for character in normalized_zip_hash):
        raise BoundaryValidationError("invalid_source_zip_sha256")
    raw_bytes = source_geojson.read_bytes()
    document = json.loads(raw_bytes)
    source_crs = document.get("crs", {}).get("properties", {}).get("name")
    if source_crs != NWIC_SOURCE_CRS:
        raise BoundaryValidationError("unexpected_source_crs")
    features = document.get("features")
    if not isinstance(features, list):
        raise BoundaryValidationError("missing_features")
    matches = [
        feature for feature in features
        if feature.get("properties", {}).get("state_name") == "Tamil Nadu"
        and feature.get("properties", {}).get("district") == "Vellore"
    ]
    if len(matches) != 1:
        raise BoundaryValidationError("vellore_feature_not_unique")
    feature = matches[0]
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
        raise BoundaryValidationError("invalid_feature")
    for field, expected in (("state", "TN"), ("stcode", "33"), ("dtcode", "595"), ("src_agency", "Survey of India (SOI)")):
        if str(properties.get(field, "")).strip() != expected:
            raise BoundaryValidationError(f"unexpected_{field}")
    transformed_geometry = _transform_multipolygon(geometry)
    source_geojson_sha256 = sha256(raw_bytes).hexdigest()
    bounded = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "district_id": "in:tn:vellore",
                "source_state": "Tamil Nadu",
                "source_district": "Vellore",
                "source_feature_id": properties["id"],
                "source_objectid": properties["objectid"],
                "source_state_code": properties["stcode"],
                "source_district_code": properties["dtcode"],
                "source_agency": properties["src_agency"],
                "reference_scope": "case-study reference geography",
                "not_flood_footprint": True,
                "source_url": NWIC_GSI_SOURCE_URL,
                "source_zip_sha256": normalized_zip_hash,
                "source_geojson_sha256": source_geojson_sha256,
                "source_crs": NWIC_SOURCE_CRS,
                "target_crs": TARGET_GEOJSON_CRS,
                "transformation": "EPSG:7755 inverse Lambert Conformal Conic (2SP) to EPSG:4326",
            },
            "geometry": transformed_geometry,
        }],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bounded, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return BoundaryExtraction(
        feature_count=len(features), source_geojson_sha256=source_geojson_sha256,
        source_zip_sha256=normalized_zip_hash, district_id="in:tn:vellore",
        source_feature_id=int(properties["id"]), geometry_type=transformed_geometry["type"],
        source_crs=NWIC_SOURCE_CRS, target_crs=TARGET_GEOJSON_CRS,
    )
