# Dashboard image capture

No image is committed until a reviewer captures it from the actual local
Kibana dashboard. Do not generate, retouch, or substitute a mockup.

After provisioning the real dashboard with `--dark-appearance`, refresh Kibana,
switch to dashboard view/full-screen mode, and capture the following genuine
images:

1. `vellore-dashboard-hero.png` — first viewport showing the AgriShock header,
   Vellore/Michaung context, `REPLAYED HISTORICAL`, LOW status, confidence,
   associations, and observed-versus-baseline comparison.
2. `vellore-dashboard-interpretation.png` — LOW explanation with price movement
   and robust anomaly cards.
3. `vellore-dashboard-pipeline.png` — compact pipeline-evidence panel.

Use the dashboard's pinned real-historical filter and Dec 2023 time range.
Avoid browser/profile chrome and any local paths, account information, or
synthetic records. Review every capture before committing it; the image must
not imply a causal finding, a flood footprint, or a normalized severity score.

## Exact hero capture

```powershell
python scripts/provision_kibana_dashboard.py --url http://localhost:5601 --dark-appearance
```

Open `http://localhost:5601`, select **AgriShock — Vellore real historical
case**, wait for the values and price bars to load, click **Full screen**, and
use the operating system's screenshot tool. Save the unedited capture as
`docs/images/vellore-dashboard-hero.png`. Confirm the filter still pins
`replayed_historical` and the Vellore signal ID before saving.
