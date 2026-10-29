"""Pull election-night results from civicAPI into data/results.json.

civicAPI (https://civicapi.org) is a free results service that needs no key. Every
race or measure in data/races.json with a "civic" block gets results:
  {"doc": "senate", "region": "tx"}  -> the national Senate document, Texas entry
  {"doc": "house",  "region": "mo-05"} -> the national House document, MO-5 entry
  {"races": [87243]}                 -> a single civicAPI race (measures, state offices)

Local items civicAPI doesn't carry (Jackson County, Parkville) come from
data/results_local.json, which is edited by hand on election night.

The page also reads civicAPI directly in the browser, so this file is the backup
copy and the history (every update is a commit).

Run it locally:  python scripts/fetch_results.py
"""

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RACES = ROOT / "data" / "races.json"
LOCAL = ROOT / "data" / "results_local.json"
OUT = ROOT / "data" / "results.json"
BASE = "https://civicapi.org/api/v2"
DOCS = {"senate": 87528, "house": 87524}
ELECTION_DATE = "2026-11-03"
ALLOW_TEST = "--test" in sys.argv  # civicAPI runs fake "test elections" before the real night


def get(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": "abholder-elections/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            print(f"  {path}: {e} (try {attempt + 1}/3)")
            time.sleep(5 * (attempt + 1))
    return None


def usable(doc):
    """Skip missing docs, test elections, and races from some other date."""
    if not doc:
        return False
    if doc.get("test_data") and not ALLOW_TEST:
        return False
    return (doc.get("election_date") or ELECTION_DATE).startswith(ELECTION_DATE)


def match(our_candidates, civic_candidates, percent_reporting):
    """Turn civicAPI's candidate list into our shape, keyed by the names we use.

    Names don't always match exactly ("Randall (Randy) Langkraehr" vs "Randy Langkraehr",
    "Jennifer" vs "Jen"), so we match on last name. Anyone we don't track is lumped into "Other".
    """
    votes, called = {}, None
    for cc in civic_candidates:
        cname = cc.get("name", "")
        ours = next((c["name"] for c in our_candidates
                     if c["name"].split()[-1].lower() in cname.lower()), None)
        if cname in ("Yes", "No"):
            ours = cname
        key = ours or "Other"
        votes[key] = votes.get(key, 0) + (cc.get("votes") or 0)
        if cc.get("winner"):
            called = {"Yes": "Passed", "No": "Failed"}.get(cname, ours or cname)
    if not votes.get("Other"):
        votes.pop("Other", None)
    return {"reporting": percent_reporting or 0, "called": called, "votes": votes}


def main():
    races = json.loads(RACES.read_text())
    docs = {name: get(f"race/{rid}") for name, rid in DOCS.items()}
    for name, doc in docs.items():
        if doc and doc.get("test_data") and not ALLOW_TEST:
            print(f"civicAPI {name} document is TEST data; ignoring it")
    cache = {}

    results = {}
    for section in races["sections"]:
        for item in section.get("races", []) + section.get("measures", []):
            civic = item.get("civic")
            if not civic:
                continue
            cands = item.get("candidates", [])
            if "doc" in civic:
                doc = docs.get(civic["doc"])
                region = (doc or {}).get("region_results", {}).get(civic["region"]) if usable(doc) else None
                if region:
                    results[item["id"]] = match(cands, region.get("candidates", []), region.get("percent_reporting"))
            else:
                best = None
                for rid in civic["races"]:
                    if rid not in cache:
                        cache[rid] = get(f"race/{rid}")
                        time.sleep(0.5)
                    doc = cache[rid]
                    if not usable(doc):
                        continue
                    r = match(cands, doc.get("candidates", []), doc.get("percent_reporting"))
                    if best is None or sum(r["votes"].values()) > sum(best["votes"].values()):
                        best = r
                if best:
                    results[item["id"]] = best

    # Only keep entries that have actual votes, so the page shows "no results yet" until counting starts.
    results = {k: v for k, v in results.items() if sum(v["votes"].values()) > 0 or v["called"]}

    # Hand-entered local results win over anything automatic.
    if LOCAL.exists():
        local = json.loads(LOCAL.read_text()).get("results", {})
        results.update({k: v for k, v in local.items() if not k.startswith("_")})

    OUT.write_text(json.dumps({
        "source": "civicAPI (civicapi.org); local results entered by hand",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds") if results else None,
        "results": results,
    }, indent=2) + "\n")
    print(f"wrote {len(results)} results to data/{OUT.name}")


if __name__ == "__main__":
    main()
