"""Small deterministic geometry reference implementation for mapping tests.

Production Spark jobs use the same canonical IDs with Sedona ST_Intersects.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

Point = tuple[float, float]  # longitude, latitude in WGS84

@dataclass(frozen=True, slots=True)
class DistrictBoundary:
    district_id: str
    state_id: str
    boundary_version: str
    polygon: tuple[Point, ...]

@dataclass(frozen=True, slots=True)
class MatchResult:
    district_id: str | None
    method: str
    boundary_version: str | None

def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray-casting check for a closed or open simple polygon."""
    x, y = point
    inside = False
    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside

def map_point_to_district(point: Point, boundaries: Sequence[DistrictBoundary]) -> MatchResult:
    matches = [boundary for boundary in boundaries if point_in_polygon(point, boundary.polygon)]
    if len(matches) != 1:
        return MatchResult(None, "unresolved" if not matches else "ambiguous", None)
    match = matches[0]
    return MatchResult(match.district_id, "point_in_polygon", match.boundary_version)
