"""Pull early-vote statistics from the University of Florida Election Lab into data/early_vote.json.

UF's Election Lab (Michael McDonald) collects early and mail voting numbers from every
state that reports them and publishes one CSV for the whole country:
    https://election.lab.ufl.edu/data-downloads/earlyvote/2026/US.csv

The numbers are licensed CC BY-NC-ND 4.0: free for non-commercial use with credit.
The page credits UF and links back.

This script keeps:
  - "states": the latest numbers for every state
  - "history": one entry per day (national total and each state's total), so the
    page can draw a line of ballots cast over time

Usage:
  python scripts/fetch_early_vote.py                 # fetch today's file
  python scripts/fetch_early_vote.py --seed DIR      # also load old snapshots from DIR
"""

import csv
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "early_vote.json"
URL = "https://election.lab.ufl.edu/data-downloads/earlyvote/2026/US.csv"
FIELDS = ["voted_all", "inperson_all", "accept_all", "request_all", "turn_2022", "voted_dem", "voted_rep", "voted_none"]

# Kansas City-area counties. UF also publishes one file per state with a row per county
# (Missouri's comes from an AP feed that splits Kansas City's own election board out of
# Jackson County). (state, row name in UF's file, label we show)
COUNTY_URL = "https://election.lab.ufl.edu/data-downloads/earlyvote/2026/{st}_county.csv"
LOCAL = [
    ("MO", "Kansas City", "Kansas City (Jackson Co. part)"),
    ("MO", "Rest of Jackson County", "Jackson County, outside KC"),
    ("MO", "Clay County", "Clay County, MO"),
    ("MO", "Platte County", "Platte County, MO"),
    ("KS", "Johnson", "Johnson County, KS"),
]
LOCAL_FIELDS = ["voted_all", "inperson_all", "accept_all", "request_all", "voted_dem", "voted_rep", "voted_none"]
# Hand-entered numbers for counties the feed hasn't picked up yet (shown with their source and date).
MANUAL = ROOT / "data" / "early_vote_manual.json"


def get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "abholder-elections/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8-sig")


def parse_counties(text, st):
    """One state's county CSV -> {'MO|Clay County': {...}} for the counties in LOCAL."""
    wanted = {name: label for s, name, label in LOCAL if s == st}
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        name = (row.get("county") or "").strip()
        if name in wanted:
            out[f"{st}|{name}"] = {"label": wanted[name], "state": st,
                                   **{f: num(row.get(f)) for f in LOCAL_FIELDS}}
    return out


def local_counties():
    counties = {}
    for st in sorted({s for s, _, _ in LOCAL}):
        try:
            counties.update(parse_counties(get_text(COUNTY_URL.format(st=st)), st))
        except Exception as e:
            print(f"WARN {st} county file: {e}")
    manual = json.loads(MANUAL.read_text()).get("counties", {}) if MANUAL.exists() else {}
    for key, m in manual.items():
        c = counties.get(key)
        if key.startswith("_") or (c and c["voted_all"] > 0):
            continue  # the feed has real numbers now; the hand-entered ones are no longer needed
        st, name = key.split("|")
        label = next((l for s, n, l in LOCAL if s == st and n == name), name)
        counties[key] = {"label": label, "state": st, **{f: 0 for f in LOCAL_FIELDS},
                         "voted_all": m["voted_all"], "manual": {k: m.get(k) for k in ("as_of", "source", "url")}}
    return counties


def num(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def parse(text):
    """CSV text -> {state_abbv: {...}}. UF's file sometimes repeats a state; keep the first."""
    states = {}
    for row in csv.DictReader(io.StringIO(text)):
        ab = (row.get("state_abbv") or "").strip()
        if not ab or ab in states:
            continue
        states[ab] = {
            "name": row.get("state"),
            **{f: num(row.get(f)) for f in FIELDS},
            "last_update": row.get("last_update"),
            "source": row.get("data_source"),
            "notes": None if row.get("notes") in (None, "", "NA") else row["notes"],
        }
    return states


def to_iso(us_date):
    """'10/28/2026' -> '2026-10-28'."""
    try:
        return datetime.strptime(us_date, "%m/%d/%Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def add_history(history, day, states):
    history[day] = {
        "total": sum(s["voted_all"] for s in states.values()),
        "states": {ab: s["voted_all"] for ab, s in states.items()},
    }


def main():
    data = json.loads(OUT.read_text()) if OUT.exists() else {"history": {}}
    history = data.get("history", {})

    if "--seed" in sys.argv:  # one-time backfill from saved daily snapshots
        folder = Path(sys.argv[sys.argv.index("--seed") + 1])
        for f in sorted(folder.glob("*.csv")):
            day = f"{f.name[:4]}-{f.name[4:6]}-{f.name[6:8]}"  # names look like 20261028T1423_hash.csv
            add_history(history, day, parse(f.read_text()))

    req = urllib.request.Request(URL, headers={"User-Agent": "abholder-elections/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        states = parse(r.read().decode("utf-8-sig"))
    if not states:
        sys.exit("UF file had no rows; keeping the old data")

    today = datetime.now(timezone.utc).date().isoformat()
    add_history(history, today, states)

    counties = local_counties()
    local_history = data.get("local_history", {})
    if counties:
        local_history[today] = {k: c["voted_all"] for k, c in counties.items() if not c.get("manual")}

    OUT.write_text(json.dumps({
        "source": "University of Florida Election Lab",
        "source_url": "https://election.lab.ufl.edu/early-vote/2026-early-voting/",
        "license": "CC BY-NC-ND 4.0",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": sum(s["voted_all"] for s in states.values()),
        "states": states,
        "history": dict(sorted(history.items())),
        "local": counties or data.get("local", {}),
        "local_order": [f"{s}|{n}" for s, n, _ in LOCAL],
        "local_history": dict(sorted(local_history.items())),
    }, indent=1) + "\n")
    print(f"{len(states)} states, {sum(s['voted_all'] for s in states.values()):,} ballots cast; "
          f"history has {len(history)} days")


if __name__ == "__main__":
    main()
