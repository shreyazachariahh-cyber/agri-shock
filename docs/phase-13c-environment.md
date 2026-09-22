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

## Raw-artifact acquisition and manifest

Raw artifacts belong beneath the gitignored `data/local/source-acquisition/`.
They must be saved unchanged, with a manifest recording provider, source URL,
original filename, retrieval time, SHA-256, source type, filters/context, and
the `replayed_historical` classification. The current desktop runner could not
download the official PDFs or NWIC ZIP: its HTTP layer reported an
authentication/proxy failure, the browser cancelled the ZIP download, and its
WSL service was inaccessible. No absent file has been represented as obtained.

After successfully preserving the NRSC document and creating a reviewed JSON
extract, run:

```powershell
wsl.exe -d Ubuntu -- bash -lc 'cd /mnt/c/Users/shrey/Documents/Codex/2026-08-29/hi/outputs/agri-shock && . .venv-wsl/bin/activate && python -m agri_shock.ingestion.historical_environment data/local/source-acquisition/environment/tamil-nadu-michaung-2023/ndem-vellore-extract.json --output data/local/source-acquisition/environment/tamil-nadu-michaung-2023/ndem-vellore.replayed.ndjson --manifest data/local/source-acquisition/environment/tamil-nadu-michaung-2023/ndem-vellore.manifest.json'
```

The download command must use `curl --fail --location` against the exact URLs
above; validate with `sha256sum` before creating the extract. Do not use a
mirror, a CAPTCHA bypass, or a hand-drawn geometry.

## Completion gate

The adapter and bounded market reference are ready. Phase 13C remains
incomplete until the official NRSC and NWIC artifacts are actually preserved,
their SHA-256 values recorded, the NWIC feature schema/CRS is checked, and the
Vellore boundary is validated before conversion into the Delta reference input.
