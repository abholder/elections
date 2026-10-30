"""Pull election-night results from civicAPI into data/results.json.

civicAPI (https://civicapi.org) is a free results service that needs no key. Every
race or measure in data/races.json with a "civic" block gets results:
  {"doc": "senate", "region": "tx"}  -> the national Senate document, Texas entry
  {"doc": "house",  "region": "mo-05"} -> the national House document, MO-5 entry
  {"races": [87243]}                 -> a single civicAPI race (measures, state offices)

Alaska Ballot Measure 2 isn't in civicAPI, so items with "source": "alaska" are read from
Alaska's own results PDF (see scripts/fetch_alaska.py).

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


def norm(name):
    return " ".join(name.lower().replace("\u201c", "").replace("\u201d", "").replace('"', "").split())


def pick(our_candidates, civic_names, cname):
    """Which of our candidates is civicAPI's `cname`? Returns our name, or None.

    1. Exact name match wins ("Dan Sullivan" == "Dan Sullivan").
    2. Otherwise match on last name ("Randall (Randy) Langkraehr" -> "Randy Langkraehr"),
       but ONLY if nobody else in the race shares that last name. Alaska's Senate ballot has
       both "Dan Sullivan" and "Daniel J. Jr. Sullivan", and they must not be merged.
    """
    for c in our_candidates:
        if norm(c["name"]) == norm(cname):
            return c["name"]
    for c in our_candidates:
        last = c["name"].split()[-1].lower()
        if last in cname.lower():
            sharing = [n for n in civic_names if last in n.lower()]
            exact_elsewhere = any(norm(n) == norm(c["name"]) for n in civic_names)
            if len(sharing) == 1 and not exact_elsewhere:
                return c["name"]
    return None


def match(our_candidates, civic_candidates, percent_reporting):
    """Turn civicAPI's candidate list into our shape, keyed by the names we use.
    Anyone we don't track is lumped into "Other"."""
    names = [cc.get("name", "") for cc in civic_candidates]
    votes, called = {}, None
    for cc in civic_candidates:
        cname = cc.get("name", "")
        ours = cname if cname in ("Yes", "No") else pick(our_candidates, names, cname)
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

    # Alaska Ballot Measure 2 comes from the state's own report. If that fails, the rest still publishes.
    alaska_items = [m for s in races["sections"] for m in s.get("measures", []) if m.get("source") == "alaska"]
    if alaska_items:
        try:
            import fetch_alaska
            r = fetch_alaska.ballot_measure_2()
            if r and sum(r["votes"].values()) > 0:
                for m in alaska_items:
                    results[m["id"]] = r
        except Exception as e:
            print(f"WARN Alaska report: {e}")

    OUT.write_text(json.dumps({
        "source": "civicAPI (civicapi.org); Alaska Division of Elections",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds") if results else None,
        "results": results,
    }, indent=2) + "\n")
    print(f"wrote {len(results)} results to data/{OUT.name}")


if __name__ == "__main__":
    main()
