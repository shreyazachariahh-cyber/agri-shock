# Phase 13D automated historical-acquisition assessment

## Fixed scope

This assessment applies only to the predeclared Tamil Nadu window from
01-Dec-2022 through 31-Dec-2022. It does not inspect prices, modify the
baseline methodology, or select a subset of dates.

## Official AGMARKNET report investigation

The official [Market-wise, Commodity-wise Daily Report for State/UT]
(https://agmarknet.gov.in/marketwisedailystatereportinput) was inspected in
the public browser UI on 2026-10-05.

- The visible report interface contains a custom State/UT selector and a
  single date control.
- The normal UI can select `Tamil Nadu` and accept `2022-12-01` as its date.
- Its native HTML form is a GET form targeting the input URL and exposes only
  the `date` field. State is held in a client-side custom control, not a
  documented native field.
- The result page is session-backed and does not encode its filters in the
  result URL.
- No visible date-range control, public bulk-export control, documented API,
  or stable query-string request contract was found.

Therefore, a direct HTTP client cannot be implemented safely: it would have
to infer the application's undocumented client request for State/UT. AgriShock
does not do that. The public one-date UI is suitable for human exports, but a
project-owned browser bot has not been added because the report's normal CSV
download/result contract was not independently validated for programmatic
reuse. It must not attempt CAPTCHA, authentication, session-cookie replay, or
access-control workarounds.

## Official OGD assessment

The official [OGD mandi catalogue](https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi)
does advertise an API/download and identifies AGMARKNET/DMI as its source.
However, the repository's validated API workflow requires
`DATA_GOV_IN_API_KEY`, the catalogue is described as current-daily rather than
as a complete historical archive, and the earlier authenticated CSV attempt
returned a zero-byte file. No credential-free, verified historical Vellore
download/API route was established. It is not a substitute for the fixed
official AGMARKNET daily report window.

## Reproducible fallback

All 31 calendar dates must be attempted in the official UI. A successful CSV
is saved as delivered; no manual renaming is needed. A portal response that
explicitly says no data is recorded separately. Afterwards the existing
`agmarknet_state_report` command discovers the files by their internal report
date, stages and hashes only the fixed December 2022 window, deduplicates
identical files, withholds conflicting same-date files, writes replay/DLQ
artifacts, and emits the Vellore/Paddy(Common)/variety coverage audit.

An absent local CSV is intentionally recorded as `missing_report_dates`
(not acquired or unavailable). It becomes `known_no_data_dates` only when the
operator actually saw the official no-data result and supplies it explicitly.
