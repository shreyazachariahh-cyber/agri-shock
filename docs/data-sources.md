# Data-source feasibility (Phase 0)

Verified on 2026-08-29. “Accessible” means the source and its documented
interface were independently checked; it does not promise availability from
every network. Source adapters must keep captured raw payloads and must label
fixtures and replay data.

## 1. AGMARKNET mandi prices through OGD India

- **Catalogue:** [Current daily price of various commodities from various
  markets (Mandi)](https://sandbox.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi).
- **Purpose:** primary price observations. The catalogue says it is generated
  from AGMARKNET and contains daily wholesale minimum, maximum, and modal
  prices by market/commodity.
- **API:** data.gov.in catalogue APIs conventionally expose resource endpoints
  under `https://api.data.gov.in/resource/{resource-id}` and require an
  `api-key`; the API key is configuration, never source control. `format`,
  `limit`, `offset`, and resource-specific filters are expected parameters.
- **Granularity / fields:** daily; state, district, market, commodity, variety,
  arrival date, min/max/modal price, and units when supplied. Validate actual
  headers against the selected resource before binding a production adapter.
- **Historical use:** the catalogue is current-daily and lists a 2024 update.
  It does *not* by itself guarantee a complete historical time series. Phase 1
  must acquire and version a legal, reproducible historical extract for the
  selected case study (for example, a portal export) rather than imply that a
  live endpoint provides it.
- **Live test:** attempted `GET` to the documented resource pattern with the
  public demonstration key. This host’s command-line HTTP client failed before
  connecting because Windows TLS credentials are unavailable. Treat live
  response shape and rate limits as unverified in this environment.
- **Limitations:** API-key/key-quota policy and historical coverage require
  verification when a real project key and target resource are selected.

### Historical discovery workflow

AgriShock uses the official OGD resource identifier
`9ef84268-d588-465a-a308-a864a43d0070` through
`https://api.data.gov.in/resource/{resource-id}`. A `DATA_GOV_IN_API_KEY` is
required and is supplied only at runtime as the `api-key` request parameter.
The acquisition command deliberately limits discovery requests to 1–100 rows:

```bash
python -m agri_shock.ingestion.historical_mandi fetch \
  --output-dir data/local/source-acquisition/ogd-mandi --limit 10
```

It writes a raw response, replayable NDJSON labelled `replayed_historical`,
and a manifest containing provider, catalogue/resource references, retrieval
time, non-secret request parameters, observed raw fields, accepted/rejected
counts, and row-level rejection reasons. These files are local runtime data
and are not committed. The companion audit command reports date extent,
dimensions, varieties, and critical-field missing rates:

```bash
python -m agri_shock.ingestion.historical_mandi audit --raw-file PATH_TO_RAW_JSON
```

The documented catalogue describes prices as rupees per quintal; the OGD
converter records this explicit source assumption as `INR/quintal` only when a
row lacks `Price_Unit`. Variety is included in the stable source identity, so
same-day varieties cannot collapse into one replay event.

## 2. IMD districtwise rainfall

- **Documentation:** [IMD API documentation](https://mausam.imd.gov.in/imd_latest/contents/api.pdf).
- **Endpoint:** `https://mausam.imd.gov.in/api/districtwise_rainfall_api.php?id={obj_id}`.
- **Authentication:** documentation shows no API key.
- **Format / fields:** JSON fields include `OBJ_ID`, `District`, `Date`, Daily
  Actual, Daily Normal, Daily Departure Per, Daily Category, plus weekly,
  monthly and cumulative figures.
- **Granularity / cadence:** district and daily (rainfall day is reported to
  IMD’s stated observation schedule). Categories are LE/E/N/D/LD/NR/ND and
  correspond to documented departure ranges.
- **Live test:** the endpoint was opened in the in-app browser for `id=164`;
  it returned: `Your IP 136.233.9.121 needs to be whitelisted`. Therefore the
  adapter must handle a source-access rejection and Phase 1 uses a clearly
  labelled historical fixture/replay until approved access is available.
- **Historical availability:** the rainfall page directs historical queries to
  IMD contacts; no open historical API commitment was established.

## 3. GDACS flood events

- **Documentation:** [GDACS API quick start](https://www.gdacs.org/Documents/2025/GDACS_API_quickstart_v1.pdf)
  and [Swagger](https://www.gdacs.org/gdacsapi/swagger/index.html).
- **Endpoint:** `https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH`
  with parameters such as `eventlist=FL`, `fromdate`, `todate`, and
  `alertlevel`. The documented response is GeoJSON; feeds are also available.
- **Authentication / rate limits:** no authentication stated in the quick
  start. No specific rate limit was found; use a conservative, configurable
  polling interval and exponential backoff.
- **Granularity / fields:** event-level geometry and timing, flood event ID,
  alert level, and related metadata. Event geometry is not a district label;
  map it spatially.
- **Live test:** browser navigation to the API was blocked by the local
  browser client (`ERR_BLOCKED_BY_CLIENT`); command-line TLS failed before a
  request. The public documentation was reachable, but endpoint payload shape
  remains unverified on this host.
- **Limitations:** alert level is GDACS’s alert classification, not agricultural
  impact or farmer-distress severity. Geometry and start/end availability vary.

## 4. NASA EONET (secondary / corroborative only)

- **Documentation:** [EONET v3](https://eonet.gsfc.nasa.gov/docs/v3).
- **Endpoint:** `https://eonet.gsfc.nasa.gov/api/v3/events` and `/geojson`.
  Supports `category`, `status`, `days`, `start`, `end`, `bbox`, and `limit`.
- **Authentication / format:** no key is documented; JSON or GeoJSON.
- **Granularity / fields:** event ID, title, optional description, categories,
  geometries and dates, source, and `closed` timestamp where known.
- **Live test:** local browser client blocked API navigation; CLI TLS failed
  before connection. Documentation is reachable. Do not make EONET a hard
  dependency for the MVP.
- **Limitations:** it is a global event tracker; coverage/latency and geometry
  are source dependent. It cannot validate local flood impact by itself.

## 5. District boundaries

- **Preferred source:** [National Water Data Portal / GSI district boundary
  dataset](https://www.nwdp.nwic.gov.in/dataset/district-boundary), advertised
  as GeoJSON, KML, and SHP and updated in 2025.
- **Fallback:** [Government Map Service district layer](https://mapservice.gov.in/mapserviceserv176/rest/services/dbt/bankNewCSC/MapServer/4),
  which supports GeoJSON queries but reports older administrative coverage.
- **Use:** immutable, versioned local GeoParquet/GeoJSON snapshot with source
  version/date stored in metadata. Match flood geometry to polygons using
  `ST_Intersects`; match mandi coordinates to polygons with `ST_Contains`.
- **Limitation:** district creation/renaming and source spelling differences
  require a curated alias/crosswalk table. Never join solely on display names.

## Source policy

Each adapter exposes `fetch()`, `normalize()`, and `validate()`; it emits raw
payload metadata and a stable source fingerprint. If a source is inaccessible,
the adapter fails visibly and a fixture must be declared `replayed_historical`
or `synthetic_failure_injection`—never presented as live data.
