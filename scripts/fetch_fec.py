"""Pull campaign fundraising totals from the FEC for every candidate in data/races.json.

How it works:
  1. Read data/races.json and collect every candidate that has an "fec" block.
  2. Find that candidate's FEC id (search by last name + state + office + district),
     unless races.json pins one with "fec_id".
  3. Ask the FEC for that candidate's 2026-cycle totals: raised, spent, cash on hand.
  4. Write everything to data/money.json.

Runs on GitHub Actions (see .github/workflows/update-data.yml), but you can run it
on your own computer too:   FEC_API_KEY=yourkey python scripts/fetch_fec.py

Uses only Python's standard library, so there is nothing to install.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RACES = ROOT / "data" / "races.json"
OUT = ROOT / "data" / "money.json"
API = "https://api.open.fec.gov/v1"
CYCLE = 2026
KEY = os.environ.get("FEC_API_KEY") or "DEMO_KEY"


class RateLimited(Exception):
    """The FEC said 'too many requests' and waiting didn't help. Stop the run."""


def get(path, **params):
    """GET an FEC endpoint and return the parsed JSON. Retries once on a rate limit."""
    params["api_key"] = KEY
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(2):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt == 0:
                    time.sleep(15)
                    continue
                # Rate limits last an hour, so more waiting won't help. Give up and let
                # main() keep the previous numbers. (The shared DEMO_KEY hits this fast.)
                raise RateLimited("FEC rate limit hit. Is the FEC_API_KEY secret set?")
            raise


def find_candidate_id(fec, full_name):
    """Search the FEC for a candidate and return (candidate_id, name_as_fec_lists_it)."""
    params = {"q": fec["q"], "state": fec["state"], "office": fec["office"],
              "election_year": CYCLE, "per_page": 20}
    if fec.get("district"):
        params["district"] = fec["district"]
    results = get("/candidates/search/", **params).get("results", [])
    if not results:
        return None, None
    # Several people can share a last name (lots of Browns in Ohio). Rank matches:
    # first name also matches > has actually raised money > alphabetical.
    # FEC lists names as "LAST, FIRST MIDDLE".
    first = full_name.split()[0].upper()
    results.sort(key=lambda c: (first not in c.get("name", "").upper(),
                                not c.get("has_raised_funds"),
                                c.get("name", "")))
    best = results[0]
    return best["candidate_id"], best.get("name")


def get_totals(candidate_id):
    data = get(f"/candidate/{candidate_id}/totals/", cycle=CYCLE, election_full="true")
    rows = data.get("results", [])
    if not rows:
        return None
    t = rows[0]
    return {
        "raised": t.get("receipts"),
        "spent": t.get("disbursements"),
        "cash_on_hand": t.get("last_cash_on_hand_end_period"),
        "through": (t.get("coverage_end_date") or "")[:10] or None,
    }


def main():
    races = json.loads(RACES.read_text())
    previous = json.loads(OUT.read_text())["candidates"] if OUT.exists() else {}

    out, problems, rate_limited = {}, [], False
    for section in races["sections"]:
        for race in section.get("races", []):
            for c in race.get("candidates", []):
                fec = c.get("fec")
                if not fec:
                    continue
                key = f'{race["id"]}|{c["name"]}'
                try:
                    cid = c.get("fec_id") or fec.get("fec_id")
                    fec_name = None
                    if not cid:
                        cid, fec_name = find_candidate_id(fec, c["name"])
                    if not cid:
                        problems.append(f"{c['name']}: not found in FEC search")
                        continue
                    totals = get_totals(cid)
                    out[key] = {"fec_id": cid, "fec_name": fec_name, **(totals or {})}
                    print(f"ok   {c['name']:<28} {cid}  raised={out[key].get('raised')}")
                except RateLimited as e:
                    problems.append(str(e))
                    rate_limited = True
                    break
                except Exception as e:  # keep going; one bad candidate shouldn't sink the run
                    problems.append(f"{c['name']}: {e}")
                    if key in previous:  # keep the last good numbers instead of blanking them
                        out[key] = previous[key]
                time.sleep(0.5)  # be gentle with the API
            if rate_limited:
                break
        if rate_limited:
            break

    # Anyone we didn't reach this run keeps their previous numbers.
    for key, val in previous.items():
        out.setdefault(key, val)

    OUT.write_text(json.dumps({
        "source": "Federal Election Commission (api.open.fec.gov)",
        "cycle": CYCLE,
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidates": out,
        "problems": problems,
    }, indent=2) + "\n")

    print(f"\nwrote {len(out)} candidates to data/{OUT.name}")
    for p in problems:
        print("WARN", p)
    if KEY == "DEMO_KEY":
        print("NOTE: using the shared DEMO_KEY. Add an FEC_API_KEY repo secret for reliable runs.")
    if not out:
        sys.exit("No data fetched at all. Check the FEC_API_KEY secret.")


if __name__ == "__main__":
    main()
