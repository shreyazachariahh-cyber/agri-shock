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

### AGMARKNET 2.0 public historical reports (Phase 13A discovery)

The official [AGMARKNET 2.0 Prices & Arrival Reports](https://agmarknet.gov.in/pricearrivalreportlist)
are a separate, public browser-reporting interface operated by DMI. They do
not require an API key for the price-report queries tested during Phase 13A.
The reports are session-backed form submissions; their result URLs do not
encode the selected filters, so a reproducible acquisition must retain both
the raw export and a manifest of the selected filters.

The strongest verified price report is **Market-wise, Commodity-wise Daily
Report for State/UT**:

- Input: [official report form](https://agmarknet.gov.in/marketwisedailystatereportinput),
  with State/UT and date filters.
- Result: [official report result](https://agmarknet.gov.in/marketwisedailystatereportoutput),
  with an Export control (CSV, Excel, and PDF shown by the UI).
- Observed fields: state and report date in the title; market context rows;
  commodity group context rows; Commodity; Arrivals; Unit of Arrivals; Variety;
  Minimum Price; Maximum Price; Modal Price; Unit of Price.
- Explicit unit evidence: real rows label price as `Rs./Quintal`. A source
  adapter must retain the row-level unit and reject non-quintal rows unless a
  compatible canonical-unit conversion is deliberately implemented. For
  example, the same real Himachal report included `Rs./Bundle` rows, which
  are not interchangeable with wholesale price-per-quintal observations.
- Real queries observed: Tamil Nadu on 2023-12-26, including
  `Thammampati APMC` / Onion / Other / 3000.00 / 3300.00 / 3150.00
  Rs./Quintal; and Himachal Pradesh on 2023-07-10, including multiple
  markets and varieties. These observations establish source availability,
  not a case-study result or a causal inference.

This report does **not** expose district in its downloadable/table contract.
Its context-only rows also require a stateful parser: blank Commodity or
Arrivals cells inherit the preceding market/commodity context and must never
be treated as complete independent records.

The official [Market Profile](https://agmarknet.gov.in/viewmarketprofileinputpublic)
provides a first-party hierarchical reference lookup of State/UT → District →
Market. Phase 13A verified that its Tamil Nadu → Salem market list contains
`Thammampati APMC`, establishing an official, deterministic mapping for that
specific market name in that state/district context. The final profile lookup
requires a CAPTCHA. We did not solve, bypass, automate around, or submit it.
The interface has no verified bulk export or stable, versioned market-ID
download. Consequently it is not yet a sufficient reproducible master-data
source for a general State + Market → District reference table. AgriShock must
leave unverified/ambiguous mappings unresolved rather than infer districts
from market names.

**Phase 13A verified facts:** official historical AGMARKNET price availability
was confirmed for Tamil Nadu 2023 and Himachal Pradesh 2023. The reports carry
explicit row-level price units, including both `Rs./Quintal` and
`Rs./Bundle`, and have a stateful structure. They omit district. The official
Market Profile proves that State → District → Market relationships exist, but
reproducible bulk acquisition is blocked by CAPTCHA and the absence of a
verified export. A nationwide bulk-reference discovery was completed without
finding a verified, retrievable master. No source rows from this browser
investigation have been committed as fixtures or presented as a complete
coverage extract.

### Phase 13A geography-reference investigation

The following official Government of India sources were checked before
declaring the historical-price importer blocked on district resolution:

- OGD/data.gov.in: the nationwide DMI/AGMARKNET mandi resource exposes a
  district field in its documented record schema, but its API requires a
  personal key and the authenticated CSV route yielded a zero-byte download in
  this investigation. It is therefore not a usable non-authenticated bulk
  reference acquisition path.
- AGMARKNET 2.0: the public Market Profile confirms that State → District →
  Market relationships are maintained, but the final profile request is
  CAPTCHA-gated and no public bulk export/versioned market master was found.
- eNAM: the public [Aspirational Districts mapping](https://enam.gov.in/aspirational-districts)
  is a first-party State/District/Mandi table, but it is explicitly limited to
  aspirational districts and cannot serve as a national master. The public
  [eNAM Mandi contact interface](https://enam.gov.in/apmc-contact-details)
  exposes State, District, and APMC filters, but did not return its underlying
  state/reference options in the tested session and offers no verified export.
  An official, dated eNAM Directory artifact was identified at
  `https://logistics.enam.gov.in/web/assest/download/eNAM_Directory_20210720.pdf`,
  but its official host timed out from both the browser and retrieval service.
  Because its contents, coverage, and version semantics could not be directly
  retrieved from the official host, it is not used as AgriShock reference data.
- eNAM's public [Trade Details](https://enam.gov.in/dashboard/trade-data)
  report has State, APMC, commodity, price, unit, and date fields, but no
  district field in the displayed table. It is therefore not a replacement for
  the required district-bearing historical price contract.

No official, bulk, versioned State + District + Market/APMC reference was
both discovered **and successfully retrieved** during this phase. The only
verified official market-to-district evidence is the interactive AGMARKNET
Market Profile and eNAM's limited aspirational-district table. Neither is a
replayable national master. Consequently, the historical importer must not
promote market-only AGMARKNET observations into canonical price events. The
next acceptable acquisition is either (1) an officially downloadable,
versioned market master, or (2) an official district-bearing historical price
export. Until then, rows remain raw/provenanced observations rather than
canonical geography-resolved analytics input.

### Vellore case-study daily-report importer (Phase 13D)

The official **Market-wise, Commodity-wise Daily Report for State/UT** has a
public form at the input route and a session-backed result route. The visible
form exposes State/UT and date controls, but its result URL has no filters and
the site does not publish a stable HTTP payload contract. AgriShock therefore
does not automate a guessed POST or replay browser cookies outside the normal
form. The supported reproducible route is an operator-exported official CSV:

```powershell
& .\.venv\Scripts\python.exe -m agri_shock.ingestion.agmarknet_state_report `
  --report-file data/local/source-acquisition/agmarknet/tamil-nadu-2023-12-04.csv `
  --market-reference data/case_studies/tamil-nadu-michaung-2023/market-reference.v1.json `
  --output-dir data/local/source-acquisition/agmarknet/replay `
  --target-market 'Vellore APMC' --target-commodity 'Paddy(Common)'
```

The importer records the unchanged raw-report path and SHA-256 in a manifest,
retains report-level date/state and stateful market/commodity context, labels
accepted rows `replayed_historical`, and writes rejects separately. Only the
case-scoped official Vellore reference supplies district. `ADT 37` and
`Other` remain different event identities. The importer accepts only the
source's explicit `Rs./Quintal` rows for this series; it neither combines nor
converts incompatible rows such as `Rs./Bundle`.

### Scoped case-study reference strategy and Phase 13A completion

The general/production ingestion contract is unchanged: source observations
without authoritative geographic resolution remain unresolved and observable
in remediation output. They are never promoted to canonical market geography
by guessing from a market name.

The eventual portfolio case study may instead use a **small, versioned,
provenance-backed reference snapshot** limited to that case's participating
markets. Each State → District → Market row must be evidenced by an
authoritative official source and retain its source URL/reference, retrieval
date, source provenance, and any available official identifier. This is not a
nationwide market master, must not be reused outside its documented scope, and
must be versioned with the case-study artifact. Ambiguous or unsupported rows
remain unresolved.

This bounded strategy is scientifically defensible because it preserves the
same no-inference geography requirement while making the evidence and scope of
each association inspectable. It also preserves the following safeguards:

- Geography is never guessed.
- Incompatible price units are never silently combined.
- CAPTCHA is never bypassed.
- An unofficial dataset never silently becomes canonical.
- Case selection is based on data completeness and analytical feasibility—not
  on whichever candidate has the most dramatic price movement or signal.

**Phase 13A completion note:** discovery and source validation are complete.
Bounded geography resolution is a prerequisite for the selected case study and
will be addressed after case selection; this phase does not select a case or
run the analytical signal model.

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

## Phase 13C bounded real environmental source policy

For the selected Tamil Nadu / Cyclone Michaung / Vellore December 2023 case,
the authoritative environmental evidence is the IMD RSMC Michaung report and
the NRSC/NDEM rapid flood assessment. The NRSC assessment reports Vellore at
district level, with a rapid satellite-derived inundated-area estimate; it
does not provide a reusable Vellore flood polygon. AgriShock therefore stores
the reported district and raw area measurement without manufacturing geometry,
an alert level, or a model severity.

The official NWIC-published GSI District Boundary GeoJSON is the candidate
boundary source. Phase 13C subsequently preserved the official ZIP locally,
verified its SHA-256, and programmatically inspected the 733-feature GeoJSON.
The unique `Tamil Nadu` / `Vellore` MultiPolygon has source feature `id=569`,
state code `33`, district code `595`, and source agency `Survey of India
(SOI)`. Its declared EPSG:7755 coordinates are explicitly transformed to the
pipeline's WGS84 GeoJSON representation; no coordinates are merely relabelled.
A source page is never treated as an artifact.

The only market reference admitted in Phase 13C is the versioned,
case-scoped `Tamil Nadu → Vellore → Vellore APMC` snapshot. Its evidence is an
interactive AGMARKNET Market Profile selection, it is not a nationwide master,
and it must not be generalized to another market or case. Controls remain
unresolved unless supported by their own official mapping and unaffected-area
evidence.
