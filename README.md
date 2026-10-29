# Midterms 2026 Tracker

Live site: **https://abholder.github.io/elections**

Tracks the 2026 midterms: key Senate and House races, Missouri, Kansas City and Parkville, plus notable ballot measures in other states. It shows forecasts, campaign money and (on election night) results.

## How it works

```
GitHub Action (timer)  →  scripts/fetch_fec.py  →  data/money.json  →  commit
GitHub Pages           →  index.html + app.js load data/*.json on every visit
```

| File | What it is | Updated by |
|---|---|---|
| `data/races.json` | The list of races, candidates and ballot questions | Hand |
| `data/forecasts.json` | Control odds, generic ballot, per-race odds (with sources/dates) | Hand |
| `data/money.json` | FEC fundraising totals | The Action, hourly |
| `data/results.json` | Vote counts on election night | Coming next |
| `index.html`, `style.css`, `app.js` | The page | Hand |

## Common tasks

- **Add a race:** copy an existing entry in `data/races.json`, change the fields, commit. The Action runs automatically and pulls its money data.
- **Refresh data now:** Actions tab → *Update data* → *Run workflow*.
- **Run the money script on your own computer:** `FEC_API_KEY=yourkey python scripts/fetch_fec.py`
- **Wrong FEC candidate matched?** Hover a candidate's money on the site to see the FEC id. Add `"fec_id": "H6XX00000"` inside that candidate's `fec` block to pin the right one.
