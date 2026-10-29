"""Alaska Ballot Measure 2 (repeal ranked-choice voting) from the Alaska Division of Elections.

civicAPI doesn't carry this measure, so we read Alaska's own "Election Summary Report"
PDF, the statewide results file the Division of Elections updates on election night.

The report lists each contest as:
    <contest title> (Vote for 1)
    YES   12,345   51.20%
    NO    11,765   48.80%
    Total Votes ...
    Precincts Reported: 120 of 403 (29.78%)

Used by scripts/fetch_results.py; run on its own to test:
    python scripts/fetch_alaska.py [URL] ["contest title pattern"]
Needs the pypdf package (pip install pypdf).
"""

import io
import re
import sys
import urllib.request

# Update this if the Division of Elections posts the general election somewhere else.
SUMMARY_URL = "https://www.elections.alaska.gov/enr26/results/ElectionSummaryReportRPT.pdf"
MEASURE_PATTERN = r"(BM\s*#?\s*2\b|Ballot\s+Measure\s+(No\.\s*)?2\b)"


def pdf_text(url):
    from pypdf import PdfReader  # imported here so the rest of the site never needs it
    req = urllib.request.Request(url, headers={"User-Agent": "abholder-elections/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        reader = PdfReader(io.BytesIO(r.read()))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def find_contest(text, title_pattern):
    """Return the chunk of report text for the first contest whose title matches."""
    m = re.search(title_pattern + r".{0,80}?\(Vote for", text, re.I | re.S)
    if not m:
        return None
    end = text.find("Precincts Reported", m.end())
    end = text.find("\n", end) if end != -1 else m.end() + 3000
    return text[m.start(): end if end != -1 else None]


def parse_measure(block):
    """Pull YES/NO totals and the precincts-reported percentage out of one contest block."""
    def count(label):
        m = re.search(rf"\b{label}\b\s+([\d,]+)", block)
        return int(m.group(1).replace(",", "")) if m else 0
    pct = re.search(r"Precincts Reported:\s*\d+\s+of\s+\d+\s*\(([\d.]+)%\)", block)
    return {"reporting": float(pct.group(1)) if pct else 0,
            "called": None,
            "votes": {"Yes": count("YES"), "No": count("NO")}}


def ballot_measure_2(url=SUMMARY_URL):
    """Results dict for Ballot Measure 2, or None if it isn't in the report yet."""
    text = pdf_text(url)
    if "General Election" not in text[:2000]:
        return None  # still the primary report; nothing to show
    block = find_contest(text, MEASURE_PATTERN)
    return parse_measure(block) if block else None


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else SUMMARY_URL
    pattern = sys.argv[2] if len(sys.argv) > 2 else MEASURE_PATTERN
    text = pdf_text(url)
    block = find_contest(text, pattern)
    print(block or "contest not found")
    if block:
        print(parse_measure(block))
