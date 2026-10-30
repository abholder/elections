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

    add_history(history, datetime.now(timezone.utc).date().isoformat(), states)

    OUT.write_text(json.dumps({
        "source": "University of Florida Election Lab",
        "source_url": "https://election.lab.ufl.edu/early-vote/2026-early-voting/",
        "license": "CC BY-NC-ND 4.0",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": sum(s["voted_all"] for s in states.values()),
        "states": states,
        "history": dict(sorted(history.items())),
    }, indent=1) + "\n")
    print(f"{len(states)} states, {sum(s['voted_all'] for s in states.values()):,} ballots cast; "
          f"history has {len(history)} days")


if __name__ == "__main__":
    main()
