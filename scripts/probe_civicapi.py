"""One-off: ask civicAPI what Nov 3, 2026 races it has for the places we track.
Runs on GitHub Actions (civicAPI isn't reachable from Claude's workspace) and saves probe/civicapi.json."""
import json, time, urllib.parse, urllib.request
from pathlib import Path

BASE = "https://civicapi.org/api/v2"
def get(path, **q):
    url = f"{BASE}/{path}" + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"User-Agent": "abholder-elections/1.0"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except Exception as e:
        return {"error": str(e), "url": url}

def slim(x):
    if isinstance(x, dict) and "error" in x: return x
    rows = x if isinstance(x, list) else x.get("races") or x.get("results") or x.get("data") or x
    if not isinstance(rows, list): return {"raw_keys": list(x)[:30] if isinstance(x, dict) else str(type(x))}
    keep = ("id", "election_id", "election_name", "election_type", "election_scope", "province", "district", "municipality", "test_data", "percent_reporting")
    return [{k: r.get(k) for k in keep if k in r} | {"candidates": [c.get("name") for c in r.get("candidates", [])][:6]} for r in rows if isinstance(r, dict)]

out = {"status": get("status"), "dates": get("getElectionDates", country="US")}
for q in ["Nevada", "Idaho", "Massachusetts", "Michigan", "Alaska", "Maryland", "Ohio Issue", "Virginia"]:
    out[q] = slim(get("race/search", startDate="2026-11-03", endDate="2026-11-03", country="US", query=q, limit=500))
    time.sleep(1)
for rid in (87243, 87242, 87244, 139733, 140000, 163201, 170005):
    r = get(f"race/{rid}")
    if isinstance(r, dict):
        r.pop("region_results", None)
    out[f"race_{rid}"] = r
    time.sleep(1)
Path("probe").mkdir(exist_ok=True)
Path("probe/civicapi.json").write_text(json.dumps(out, indent=1))
print({k: (len(v) if isinstance(v, list) else v) for k, v in out.items() if k != "dates"})
