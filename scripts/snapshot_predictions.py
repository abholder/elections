"""Freeze every prediction on the site into data/predictions_final.json, once, before polls close.

After the election the page compares this snapshot with the actual winners ("How the
forecasts did"). The snapshot has to be taken BEFORE results start: once votes come in,
markets and models move toward the answer, and comparing against them would be cheating.

Cutoff: Nov 3, 2026, 22:00 UTC (4pm Central, 5pm Eastern), an hour before the first polls
close (parts of Indiana and Kentucky, 6pm Eastern).

What gets frozen, per race:
  - Kalshi:          favored candidate and market price (fetched fresh at snapshot time)
  - Decision Desk HQ: favored candidate and model win chance (from data/forecasts.json,
                      updated by the daily scheduled task that morning)
  - Polls:           leader and margin of our polling average (data/polls.json)
Plus chamber control from Kalshi and Decision Desk HQ.

Safety rules:
  - Never overwrites an existing snapshot (the first good one wins).
  - Refuses to run after the first polls close unless --force is passed.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "predictions_final.json"
CUTOFF = datetime(2026, 11, 3, 22, 0, tzinfo=timezone.utc)
FIRST_POLLS_CLOSE = datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc)


def load(name):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else {}


def leader_of(odds):
    """{'Name': pct, ...} -> {'leader': name, 'pct': pct} for the favorite."""
    if not odds:
        return None
    name, pct = max(odds.items(), key=lambda kv: kv[1])
    return {"leader": name, "pct": pct}


def main():
    now = datetime.now(timezone.utc)
    if OUT.exists():  # not an error: a backup run just finds the job already done
        print(f"{OUT.name} already exists (taken {json.loads(OUT.read_text()).get('taken_at')}); not overwriting.")
        return
    if now >= FIRST_POLLS_CLOSE and "--force" not in sys.argv:
        print("Polls have started closing; a snapshot now would include results. Use --force to override.")
        return

    # Fresh market prices right at the cutoff.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_kalshi.py")], check=False)

    races = load("races.json")
    markets, forecasts, polls = load("markets.json"), load("forecasts.json"), load("polls.json")

    snap_races = {}
    for section in races.get("sections", []):
        for race in section.get("races", []):
            rid = race["id"]
            entry = {"title": race["title"], "section": section["id"]}
            if k := leader_of(markets.get("races", {}).get(rid)):
                entry["kalshi"] = k
            if d := forecasts.get("races", {}).get("odds", {}).get(rid):
                entry["ddhq"] = {"leader": d["leader"], "pct": d["pct"]}
            if p := polls.get("races", {}).get(rid):
                ranked = sorted(p["avg"].items(), key=lambda kv: kv[1], reverse=True)
                if len(ranked) >= 2:
                    entry["polls"] = {"leader": ranked[0][0], "margin": round(ranked[0][1] - ranked[1][1], 1),
                                      "count": p["count"]}
            if len(entry) > 2:  # has at least one prediction
                snap_races[rid] = entry

    control = {}
    for c in forecasts.get("control", []):
        ch = c["chamber"]
        control[ch] = {"ddhq": next(({"D": f["d"], "R": f["r"]} for f in c["forecasts"]
                                     if f["source"] == "Decision Desk HQ"), None),
                       "kalshi": markets.get("control", {}).get(ch)}

    OUT.write_text(json.dumps({
        "taken_at": now.isoformat(timespec="seconds"),
        "cutoff": CUTOFF.isoformat(),
        "about": "Predictions frozen before polls closed, for comparing with actual results.",
        "sources": {
            "kalshi": {"name": "Kalshi", "kind": "prediction market", "as_of": markets.get("updated")},
            "ddhq": {"name": "Decision Desk HQ", "kind": "forecast model", "as_of": forecasts.get("races", {}).get("as_of")},
            "polls": {"name": "Polling average (VoteHub polls)", "kind": "polls", "as_of": polls.get("updated")},
        },
        "control": control,
        "races": snap_races,
    }, indent=1) + "\n")
    print(f"Snapshot of {len(snap_races)} races saved at {now:%H:%M} UTC")


if __name__ == "__main__":
    main()
