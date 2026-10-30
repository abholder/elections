"""Temporary: see how Kalshi's public API names our Senate and House markets."""
import json, time, urllib.request, urllib.parse
from pathlib import Path
BASE = "https://api.elections.kalshi.com/trade-api/v2"
def get(path, **q):
    url = f"{BASE}{path}" + ("?" + urllib.parse.urlencode(q) if q else "")
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "abholder-elections/1.0"}), timeout=30))
    except Exception as e:
        return {"error": str(e), "url": url}
out = {}
for t in ["SENATESC-26", "SENATETX-26", "SENATEOH-26", "SENATEOHS-26", "SENATEAK-26"]:
    r = get(f"/events/{t}", with_nested_markets="true")
    ev = r.get("event", r)
    out[t] = {"title": ev.get("title"), "error": r.get("error"),
              "markets": [{k: m.get(k) for k in ("ticker", "yes_sub_title", "subtitle", "last_price", "yes_bid", "yes_ask", "status", "close_time")}
                          for m in (ev.get("markets") or r.get("markets") or [])]}
    time.sleep(0.5)
# find series/events mentioning Senate/House for 2026
found, cursor = [], None
for _ in range(40):
    q = {"limit": 200, "status": "open"}
    if cursor: q["cursor"] = cursor
    r = get("/events", **q)
    for e in r.get("events", []):
        t = (e.get("title") or "") + " " + (e.get("event_ticker") or "")
        if any(w in t for w in ("Senate", "SENATE", "House", "HOUSE")):
            found.append({k: e.get(k) for k in ("event_ticker", "series_ticker", "title", "sub_title")})
    cursor = r.get("cursor")
    if not cursor: break
    time.sleep(0.3)
out["events_found"] = found
Path("probe").mkdir(exist_ok=True)
Path("probe/kalshi.json").write_text(json.dumps(out, indent=1))
print(len(found))
