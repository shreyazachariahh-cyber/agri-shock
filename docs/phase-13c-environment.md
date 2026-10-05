# Phase 13C — real environmental data and bounded geography

## Scope and scientific guardrail

This phase prepares real-source environmental input for the selected Tamil
Nadu / Cyclone Michaung / Vellore December 2023 case. It does not associate
prices with the event, calculate an anomaly, calculate a signal, or make a
causal claim.

## Authoritative sources

| Role | Source | What it supports | Limitation |
|---|---|---|---|
| Event context and window | [IMD RSMC Michaung report](https://rsmcnewdelhi.imd.gov.in/download.php?path=uploads%2Freport%2F26%2F26_0580dd_Michaung%2BReport_Final_Sir.pdf) | Severe Cyclonic Storm Michaung, 1–6 Dec 2023; heavy through extremely heavy rain over north coastal Tamil Nadu on 3–4 Dec | It does not itself establish a Vellore district rainfall measurement. |
| Vellore affected geography | [NRSC/NDEM rapid flood assessment](https://ndem.nrsc.gov.in/documents/Disaster_Document/2023/TN/tncyclone50dsc07122023_0600hrs/tncyclone50dsc07122023_0600hrs_report.pdf) | Map `2023/CY/TN/01a/07122023`, issued 7 Dec 2023; Vellore is in the affected-district table and has 144 ha in the report's rapid satellite assessment | Preliminary rapid map, no ground verification, coverage limited to satellite availability; it supplies no reusable per-district flood polygon. |
| Boundary source | [NWIC/GSI District NWIC GeoJSON](https://nwdp.nwic.gov.in/dataset/district-boundary/resource/8d9aa2e9-9806-4f26-a4ac-48ba21e9b96d) | Official downloadable GeoJSON resource, last updated 1 May 2025 | Artifact download must succeed and its actual feature schema/CRS must be inspected before it is accepted as a pipeline boundary snapshot. |
| Bounded market identity | [AGMARKNET Market Profile](https://agmarknet.gov.in/viewmarketprofileinputpublic) | Interactive official selection directly showed `Tamil Nadu → Vellore → Vellore APMC` | Final profile is CAPTCHA-gated; no CAPTCHA was submitted/bypassed and no nationwide master is claimed. |

## Canonical event adapter

`agri_shock.ingestion.historical_environment` converts a deterministic,
human-reviewed extract of a preserved NRSC/NDEM document into a labelled
`replayed_historical` `flood_event` envelope. It requires the original
document's SHA-256, NRSC URL, map ID, district, source observation date and a
bounded evidence window. It rejects invalid/missing fields, non-NRSC URLs,
negative area, and an attempted severity value.

The canonical `event_time` is the NRSC observation day, 7 Dec 2023, expressed
as `2023-12-07T00:00:00Z` because the envelope requires a timestamp. The
payload carries `event_time_precision: day`; this is **not** a claimed
observation hour. The evidence window is 3–7 Dec 2023: the start is IMD's
realised-rainfall period, and the end is NRSC's satellite observation date.
`inundated_area_hectares=144` is preserved as an observed report field, not
converted into `alert_level` or `shock_severity`. No polygon is manufactured.

Because the existing generic flood geospatial join requires GeoJSON,
a district-reported event with `geometry_json: null` will deliberately enter
unresolved-flood remediation until a compatible district-association contract
is enabled and validated. Bronze preserves its complete raw/provenance payload.

## Bounded reference snapshot

`data/case_studies/tamil-nadu-michaung-2023/market-reference.v1.json` contains
only the Vellore APMC relationship observed on the official selector. Its IDs
are AgriShock deterministic IDs, not alleged government identifiers. The
snapshot validator requires exact state+market uniqueness and an AGMARKNET
HTTPS evidence URL; it returns unresolved for absent markets and never fuzzy
matches. It is **case-study reference data**, not a nationwide market master.
No control market is admitted in this phase because its authoritative
market-to-district mapping and unaffected-geography evidence have not yet been
captured.

## Verified raw artifacts and manifest

The following local, gitignored artifacts were subsequently retrieved in WSL
and verified by this phase. They are kept unchanged under
`data/local/source-acquisition/environment/`:

| Artifact | SHA-256 verified by AgriShock | Result |
|---|---|---|
| `nrsc-michaung-vellore-2023.pdf` | `f045f6f21ecd1d5fb819ed4a23872e3f515dcff1386da6f4a7057219da2f2a1a` | PDF text confirms the 07 Dec 2023 (0600 IST) acquisition, lists Vellore, and reports 144 ha. |
| `district_nwic_geojson.zip` | `44c734cc72139f2447dcebfe2791cac862dc5ba265e158912d797cf3410d5c37` | Contains the declared EPSG:7755 district GeoJSON. |
| Extracted `district_nwic.GeoJSON` | `2b27a478e24d8c51b0655e74ce3f4f880e75c752e4597550d6fc925ed06ac201` | 733 features; exactly one `Tamil Nadu` / `Vellore` feature. |

The originally supplied NRSC hash omitted the leading `f0`; AgriShock records
the computed 64-character hash above. The preservation manifest records that
these were manually retrieved in WSL before Phase 13C continuation; an exact
download timestamp was not available and is not invented.

The NWIC feature declares `urn:ogc:def:crs:EPSG::7755`, a projected WGS 84 /
India NSF Lambert Conformal Conic coordinate system. The pipeline requires
WGS84 GeoJSON, so `geospatial.boundaries.extract_vellore_boundary` transforms
the source using EPSG:7755's inverse LCC (2SP) parameters to EPSG:4326. The
result is structurally checked for finite coordinates, closed rings,
self-intersections, and WGS84 bounds. The output is a **district reference
polygon**, not observed flood geometry and not a claim that all of Vellore was
inundated.

The reviewed NRSC extraction and its replayable output were created locally.
To reproduce the conversion:

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/c/Users/shrey/Documents/Codex/2026-08-29/hi/outputs/agri-shock && . .venv-wsl/bin/activate && python -m agri_shock.ingestion.historical_environment data/local/source-acquisition/environment/tamil-nadu-michaung-2023/ndem-vellore-extract.json --output data/local/source-acquisition/environment/tamil-nadu-michaung-2023/ndem-vellore.replayed.ndjson --manifest data/local/source-acquisition/environment/tamil-nadu-michaung-2023/ndem-vellore.manifest.json'
```

The download command must use `curl --fail --location` against the exact URLs
above; validate with `sha256sum` before creating the extract. Do not use a
mirror, a CAPTCHA bypass, or a hand-drawn geometry.

## Completion gate

Phase 13C is complete: real-source environmental evidence, bounded market
identity, reviewed extraction, canonical replay event, and WGS84 district
reference were all produced without market-shock analysis. Phase 13D
subsequently loaded the bounded reference into Delta and completed the price /
event study without introducing a control market. See the
[completed case study](phase-13d-real-analytics.md).
