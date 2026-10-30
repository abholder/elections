"""Prediction-market odds from Kalshi's public API into data/markets.json.

Kalshi is a regulated prediction market: people trade contracts that pay $1 if an
outcome happens, so a contract's price (in dollars) reads as the market's estimated
chance. Its market data is free to read, no account or key needed:
    https://api.elections.kalshi.com/trade-api/v2

What we read:
  - Chamber control: events CONTROLS-2026 (Senate) and CONTROLH-2026 (House)
  - Senate races:    events SENATE{ST}-26 (Ohio's special is SENATEOHS-26)
  - House races:     series KXHOUSERACE, one event per district ("AZ-01")
Each event has one market per candidate (or party). We use the midpoint between the
best bid and ask, which is steadier than the last trade, falling back to the last trade.
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_results import pick  # same name-matching rules as everywhere else

ROOT = Path(__file__).resolve().parent.parent
RACES = ROOT / "data" / "races.json"
OUT = ROOT / "data" / "markets.json"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
SPECIAL_EVENTS = {"oh-sen": "SENATEOHS-26"}  # races whose event name doesn't follow the pattern


def get(path, **q):
    url = f"{BASE}{path}" + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"User-Agent": "abholder-elections/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def price(m):
    """Market price as a 0-100 chance."""
    bid, ask = float(m.get("yes_bid_dollars") or 0), float(m.get("yes_ask_dollars") or 0)
    p = (bid + ask) / 2 if bid > 0 and ask > 0 else float(m.get("last_price_dollars") or 0)
    return round(p * 100)


def party_of(m):
    t = m.get("ticker", "")
    return "D" if t.endswith("-D") else "R" if t.endswith("-R") else None


def race_odds(markets, candidates):
    """{our candidate name: chance} for one race's markets."""
    names = [m.get("yes_sub_title") or "" for m in markets]
    out = {}
    for m in markets:
        ours = pick(candidates, names, m.get("yes_sub_title") or "")
        if not ours:  # some markets are named by party ("Republican party")
            p = party_of(m)
            match = [c for c in candidates if c["party"] == p]
            ours = match[0]["name"] if len(match) == 1 and p else None
        if ours:
            out[ours] = price(m)
    return out


def house_events():
    """{'az-01': 'KXHOUSERACE-AZ01-26', ...} by paging through the House race series."""
    found, cursor = {}, None
    for _ in range(20):
        q = {"series_ticker": "KXHOUSERACE", "limit": 200}
        if cursor:
            q["cursor"] = cursor
        r = get("/events", **q)
        for e in r.get("events", []):
            sub = (e.get("sub_title") or "").strip()  # e.g. "AZ-01"
            if "-" in sub and e.get("event_ticker", "").endswith("-26"):
                found[sub.lower()] = e["event_ticker"]
        cursor = r.get("cursor")
        if not cursor:
            break
        time.sleep(0.3)
    return found


def main():
    races = json.loads(RACES.read_text())
    out = {"source": "Kalshi (kalshi.com)", "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "control": {}, "races": {}}
    problems = []

    for chamber, event in (("Senate", "CONTROLS-2026"), ("House", "CONTROLH-2026")):
        try:
            ms = get("/markets", event_ticker=event)["markets"]
            out["control"][chamber] = {party_of(m): price(m) for m in ms if party_of(m)}
        except Exception as e:
            problems.append(f"{event}: {e}")

    try:
        house = house_events()
    except Exception as e:
        house, _ = {}, problems.append(f"House events: {e}")

    for section in races["sections"]:
        for race in section.get("races", []):
            rid = race["id"]
            if rid.endswith("-sen"):
                event = SPECIAL_EVENTS.get(rid, f"SENATE{rid[:2].upper()}-26")
            elif rid in house:
                event = house[rid]
            else:
                continue
            try:
                odds = race_odds(get("/markets", event_ticker=event)["markets"], race["candidates"])
                if odds:
                    out["races"][rid] = odds
                else:
                    problems.append(f"{rid}: no markets matched our candidates")
            except Exception as e:
                problems.append(f"{rid} ({event}): {e}")
            time.sleep(0.2)

    out["problems"] = problems
    if not out["races"] and not out["control"]:
        sys.exit("Kalshi returned nothing; keeping the old file. " + "; ".join(problems))
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"control: {out['control']}; {len(out['races'])} races")
    for p in problems:
        print("WARN", p)


if __name__ == "__main__":
    main()
