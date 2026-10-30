"""Build simple polling averages for our races from VoteHub into data/polls.json.

VoteHub (https://votehub.com/polls/api/) publishes every Senate, House and governor
poll it tracks in one free JSON feed (free for civic and journalistic use, with credit).

Our average is deliberately simple and transparent, not a model:
  1. Take general-election polls for the race that ended in the last 45 days.
  2. Drop internal polls and polls sponsored by a party-aligned group.
  3. Keep one poll per pollster (its latest), preferring likely voters (LV) over
     registered voters (RV) over all adults.
  4. Average each candidate's share across those polls.
If a race has no poll in the last 45 days, we use its 3 most recent polls since
August 1 and mark the average as "stale".

Usage:
  python scripts/fetch_polls.py                  # live feed
  python scripts/fetch_polls.py --file polls.json  # test on a saved copy
"""

import gzip
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_results import pick  # same name-matching rules as election-night results

ROOT = Path(__file__).resolve().parent.parent
RACES = ROOT / "data" / "races.json"
OUT = ROOT / "data" / "polls.json"
URL = "https://api.votehub.com/polls"
WINDOW_DAYS = 45
SINCE = "2026-08-01"
POP_RANK = {"lv": 0, "rv": 1, "v": 1, "a": 2}


def load_feed():
    if "--file" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--file") + 1])
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt") as f:
            return json.load(f)
    req = urllib.request.Request(URL, headers={"User-Agent": "abholder-elections/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def race_key(p, senate_states):
    """VoteHub poll -> our race id ('tx-sen', 'mo-05'), or None if we don't track it."""
    if p.get("poll_type") == "us-senator":
        state = re.sub(r"^\d{4}\s+", "", p.get("subject") or "").strip().lower()
        return senate_states.get(state)
    if p.get("poll_type") == "us-representative":
        m = re.search(r"\b([A-Z]{2})-(\d{1,2}|AL)\b", f'{p.get("seat_name") or ""} {p.get("subject") or ""}')
        return f"{m.group(1).lower()}-{m.group(2).zfill(2).lower()}" if m else None
    return None


def average(polls, candidates, today):
    usable = [p for p in polls if not p.get("internal") and not p.get("partisan")]
    recent = [p for p in usable if p["end_date"] >= (today - timedelta(days=WINDOW_DAYS)).isoformat()]
    stale = not recent
    pool = recent or sorted(usable, key=lambda p: p["end_date"])[-3:]

    best = {}  # one poll per pollster: latest, then LV > RV > adults
    for p in pool:
        k = p.get("pollster") or "?"
        rank = (p["end_date"], -POP_RANK.get(p.get("population"), 3))
        if k not in best or rank > best[k][0]:
            best[k] = (rank, p)
    chosen = sorted((p for _, p in best.values()), key=lambda p: p["end_date"], reverse=True)
    if not chosen:
        return None

    rows = []
    for p in chosen:
        names = [a["choice"] for a in p.get("answers") or []]
        values = {}
        for a in p.get("answers") or []:
            ours = pick(candidates, names, a["choice"])
            if ours and a.get("pct") is not None:
                values[ours] = a["pct"]
        if len(values) >= 2:  # must poll at least two of our candidates (skips primary polls)
            rows.append({"pollster": p.get("pollster"), "end": p["end_date"], "pop": p.get("population"),
                         "n": p.get("sample_size"), "url": p.get("url"), "values": values})
    if not rows:
        return None
    avg = {}
    for c in candidates:
        vals = [r["values"][c["name"]] for r in rows if c["name"] in r["values"]]
        if vals:
            avg[c["name"]] = round(sum(vals) / len(vals), 1)
    return {"count": len(rows), "from": min(r["end"] for r in rows), "to": max(r["end"] for r in rows),
            "stale": stale, "avg": avg, "polls": rows[:6]}


def main():
    races = json.loads(RACES.read_text())
    senate_states = {}
    tracked = {}
    for s in races["sections"]:
        for r in s.get("races", []):
            if r["id"].endswith("-sen"):
                senate_states[re.sub(r"\s*\(.*\)", "", r["title"]).lower()] = r["id"]
            tracked[r["id"]] = r

    feed = load_feed()
    by_race = {}
    for p in feed:
        if (p.get("end_date") or "") < SINCE:
            continue
        rid = race_key(p, senate_states)
        if rid in tracked:
            by_race.setdefault(rid, []).append(p)

    today = date.today()
    out = {}
    for rid, polls in by_race.items():
        a = average(polls, tracked[rid]["candidates"], today)
        if a:
            out[rid] = a

    OUT.write_text(json.dumps({
        "source": "VoteHub (votehub.com)",
        "method": f"Simple average: polls ending in the last {WINDOW_DAYS} days, no internal or party-sponsored polls, one poll per pollster (latest; likely voters preferred).",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "races": dict(sorted(out.items())),
    }, indent=1) + "\n")
    print(f"averages for {len(out)} races: " + ", ".join(
        f"{k} ({v['count']})" for k, v in sorted(out.items())))


if __name__ == "__main__":
    main()
