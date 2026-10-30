"""Temporary: dump raw Kalshi market fields for a few markets."""
import json, urllib.request
from pathlib import Path
BASE = "https://api.elections.kalshi.com/trade-api/v2"
def get(p):
    return json.load(urllib.request.urlopen(urllib.request.Request(BASE + p, headers={"User-Agent": "abholder-elections/1.0"}), timeout=30))
out = {}
for p in ["/markets?event_ticker=SENATESC-26", "/markets?event_ticker=SENATENE-26", "/markets?event_ticker=KXHOUSERACE-AZ01-26", "/markets?event_ticker=CONTROLS-2026", "/markets?event_ticker=CONTROLH-2026", "/markets?event_ticker=KXHOUSERACE-MO05-26"]:
    try: out[p] = get(p).get("markets", [])
    except Exception as e: out[p] = str(e)
Path("probe").mkdir(exist_ok=True)
Path("probe/kalshi2.json").write_text(json.dumps(out, indent=1))
