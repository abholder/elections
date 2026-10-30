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
| `data/forecasts.json` | Decision Desk HQ forecast (control + each Senate race) and the generic ballot, with dates | Hand / daily scheduled task |
| `data/money.json` | FEC fundraising totals | The Action, twice a day |
| `data/results.json` | Vote counts on election night | `scripts/fetch_results.py` via the *Update results* Action |
| `data/markets.json` | Kalshi prediction-market odds: chamber control and each race | `scripts/fetch_kalshi.py`, twice a day |
| `data/polls.json` | Polling averages per race (VoteHub polls, simple average) | `scripts/fetch_polls.py`, twice a day |
| `data/early_vote.json` | Early/mail ballots cast by state, with daily history | `scripts/fetch_early_vote.py`, twice a day (UF updates ~daily) |
| `index.html`, `style.css`, `app.js` | The page | Hand |

## Election night

- **National and Missouri statewide results** come from [civicAPI](https://civicapi.org), free and keyless. The page reads civicAPI directly in the browser every 2 minutes (GitHub's timer runs late on busy nights), and the *Update results* Action saves a copy to `data/results.json` every 5 minutes as a backup and history.
- **Alaska Ballot Measure 2** isn't in civicAPI. `scripts/fetch_alaska.py` reads the state's Election Summary Report PDF (tested against the August primary report). If the state posts the general election at a different address, update `SUMMARY_URL` in that file.
- **Alaska Senate** uses ranked-choice voting: if no one tops 50% of first choices on election night, the ranked-choice count is Nov. 18.
- **Local items** (Jackson County, Parkville) are shown for reference only; no results feed.
- **Official results links:** every card links to that state's (or county board's) official results page, listed under `official_results` in `data/races.json`. Checked Oct. 30 from GitHub's servers:
  - **Loaded fine:** AK, CO, FL, GA, IA, ID, KS, MA, MD, MI, MO, NC, NE, NV, PA, SC, TX, UT, VA, WA, KC Election Board, Jackson County, Platte County.
  - **Blocked automated checks** (confirmed by search to be the official page; should open normally in a browser): AZ, ME, MN, NH, NY, OH.
  - **Showing past elections for now:** CA redirected to its "prior elections" page. Other states may show the last election until Nov. 3 results start.
- **Rehearsal:** add `?rehearsal` to the site URL to show civicAPI's test elections, if one is running. Without it, test data is always ignored.
- **The morning of Nov. 3:** check that civicAPI isn't still flagging its data as a test (if it were, real results would be ignored).

## When things run

- **Before election night:** *Update data* (money, early vote, polls) runs twice a day, around 6am and 6pm Central, using GitHub's built-in timer. That timer sometimes skips runs, so each time gets a few tries; runs that find nothing new don't save anything.
- **Election night** (Tue 6pm to Wed 6am Central): the *Scheduler* workflow stays awake and starts *Update results* every 5 minutes and *Update data* hourly. The page also reads civicAPI directly every 2 minutes, so most results appear even without it.
- **Nov. 4-13:** *Update results* runs twice a day for late-counted ballots.
- **Anytime:** Actions tab -> pick a workflow -> *Run workflow* to refresh now.

## Common tasks

- **Add a race:** copy an existing entry in `data/races.json`, change the fields, commit. The Action runs automatically and pulls its money data.
- **Refresh data now:** Actions tab → *Update data* → *Run workflow*.
- **Run the money script on your own computer:** `FEC_API_KEY=yourkey python scripts/fetch_fec.py`
- **Wrong FEC candidate matched?** Hover a candidate's money on the site to see the FEC id. Add `"fec_id": "H6XX00000"` inside that candidate's `fec` block to pin the right one.
