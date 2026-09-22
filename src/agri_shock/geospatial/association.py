"""Pure contract for authoritative district-reported event association."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DistrictReportedAssociation:
    event_id: str
    district_id: str
    method: str = "source_reported_district"
    uses_flood_geometry: bool = False


def associate_reported_district(event: Mapping[str, object], references: tuple[Mapping[str, str], ...]) -> DistrictReportedAssociation | None:
    """Resolve only one exact source-reported state/district reference pair."""
    payload = event.get("payload")
    if not isinstance(payload, Mapping) or payload.get("geometry_json") is not None:
        return None
    state, district, event_id = (str(payload.get("reported_state", "")).strip(), str(payload.get("reported_district", "")).strip(), str(event.get("event_id", "")).strip())
    if not state or not district or not event_id:
        return None
    matches = [reference for reference in references if reference["source_state"].strip().upper() == state.upper() and reference["source_district"].strip().upper() == district.upper()]
    if len(matches) != 1:
        return None
    return DistrictReportedAssociation(event_id, matches[0]["district_id"])
