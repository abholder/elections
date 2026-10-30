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
| `data/results.json` | Vote counts on election night | `scripts/fetch_results.py` via the *Update results* Action |
| `data/polls.json` | Polling averages per race (VoteHub polls, simple average) | `scripts/fetch_polls.py`, hourly |
| `data/early_vote.json` | Early/mail ballots cast by state, with daily history | `scripts/fetch_early_vote.py`, hourly (UF updates ~daily) |
| `index.html`, `style.css`, `app.js` | The page | Hand |

## Election night

- **National and Missouri statewide results** come from [civicAPI](https://civicapi.org), free and keyless. The page reads civicAPI directly in the browser every 2 minutes (GitHub's timer runs late on busy nights), and the *Update results* Action saves a copy to `data/results.json` every 5 minutes as a backup and history.
- **Alaska Ballot Measure 2** isn't in civicAPI. `scripts/fetch_alaska.py` reads the state's Election Summary Report PDF (tested against the August primary report). If the state posts the general election at a different address, update `SUMMARY_URL` in that file.
- **Alaska Senate** uses ranked-choice voting: if no one tops 50% of first choices on election night, the ranked-choice count is Nov. 18.
- **Local items** (Jackson County, Parkville) are shown for reference only; no results feed.
- **Rehearsal:** add `?rehearsal` to the site URL to show civicAPI's test elections, if one is running. Without it, test data is always ignored.
- **The morning of Nov. 3:** check that civicAPI isn't still flagging its data as a test (if it were, real results would be ignored).

## The clock

GitHub's built-in timer is best-effort and fired only once in 12 hours on this repo. `.github/workflows/scheduler.yml` keeps a steady clock instead: it stays running ~5.5 hours, starts *Update data* hourly (and *Update results* every 5 minutes on election night, every 30 minutes the week after), then starts a fresh copy of itself. Its own timer only restarts the chain if it ever breaks. It stops by itself after Nov. 14, 2026. To stop everything: Actions tab → *Scheduler* → "…" → Disable workflow.

## Common tasks

- **Add a race:** copy an existing entry in `data/races.json`, change the fields, commit. The Action runs automatically and pulls its money data.
- **Refresh data now:** Actions tab → *Update data* → *Run workflow*.
- **Run the money script on your own computer:** `FEC_API_KEY=yourkey python scripts/fetch_fec.py`
- **Wrong FEC candidate matched?** Hover a candidate's money on the site to see the FEC id. Add `"fec_id": "H6XX00000"` inside that candidate's `fec` block to pin the right one.
