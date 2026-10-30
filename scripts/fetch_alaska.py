"""Alaska Ballot Measure 2 (repeal ranked-choice voting) from the Alaska Division of Elections.

civicAPI doesn't carry this measure, so we read Alaska's own "Election Summary Report"
PDF, the statewide results file the Division of Elections updates on election night.
We turn the PDF into text with `pdftotext -layout` (from poppler-utils), which keeps the
visual layout. Each contest then looks like this:

    BM#1 23RCF2 (Vote for 1)
    Precincts Reported: 400 of 402 (99.50%)
    ...
    Candidate                               Party           Total
    YES                                                  117,962        72.20%
    NO                                                    45,418        27.80%
    Total Votes                                          163,380

(That example is the real August primary's measure, used to test this parser.)

Used by scripts/fetch_results.py. To test on its own:
    python scripts/fetch_alaska.py [URL] ["title pattern"]
"""

import re
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# Change this if the Division of Elections posts the general election somewhere else.
SUMMARY_URL = "https://www.elections.alaska.gov/enr26/results/ElectionSummaryReportRPT.pdf"
# On the ballot as "Ballot Measure 2", file number 24ESEG.
MEASURE_PATTERN = r"(BM\s*#?\s*2\b|24ESEG|Ballot\s+Measure\s+(No\.\s*)?2\b)"


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "abholder-elections/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e):
            raise
        # Alaska's server leaves out part of its certificate chain. Browsers quietly fetch the
        # missing piece; Python doesn't, so the secure connection fails. This is a public,
        # read-only results file, so we retry without certificate checking and say so in the log.
        print("WARN: elections.alaska.gov certificate chain incomplete; fetching without verification")
        with urllib.request.urlopen(req, timeout=60, context=ssl._create_unverified_context()) as r:
            return r.read()


def pdf_text(url):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(download(url))
        f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"],
                              capture_output=True, text=True, check=True).stdout


def find_contest(text, title_pattern):
    """Lines of the first contest whose title matches, from its title to 'Total Votes'."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "(Vote for" in line and re.search(title_pattern, line, re.I):
            block = [line]
            for nxt in lines[i + 1:]:
                block.append(nxt)
                if nxt.strip().startswith("Total Votes"):
                    break
            return block
    return None


def parse_contest(block):
    """{'reporting': %, 'votes': {name: count}} from a contest's lines."""
    pct = re.search(r"Precincts Reported:\s*\d+\s+of\s+\d+\s*\(([\d.]+)%\)", "\n".join(block))
    votes, in_rows = {}, False
    for line in block:
        if line.strip().startswith("Candidate"):
            in_rows = True
            continue
        if line.strip().startswith("Total Votes"):
            break
        # A row ends with:  <count>  <percent>%   e.g. "YES      117,962   72.20%"
        m = re.match(r"\s*(.+?)\s{2,}(?:[A-Z]{2,3}\s+)?([\d,]+)\s+[\d.]+%\s*$", line)
        if in_rows and m:
            votes[m.group(1).strip()] = int(m.group(2).replace(",", ""))
    return {"reporting": float(pct.group(1)) if pct else 0, "votes": votes}


def ballot_measure_2(url=SUMMARY_URL):
    """Results for Ballot Measure 2 in our results.json shape, or None if not posted yet."""
    text = pdf_text(url)
    if "GENERAL ELECTION" not in text[:1500].upper():
        print("Alaska report is not the general election yet; skipping")
        return None
    block = find_contest(text, MEASURE_PATTERN)
    if not block:
        print("Alaska report has no Ballot Measure 2 contest; skipping")
        return None
    r = parse_contest(block)
    return {"reporting": r["reporting"], "called": None,
            "votes": {"Yes": r["votes"].get("YES", 0), "No": r["votes"].get("NO", 0)}}


if __name__ == "__main__":
    text = pdf_text(sys.argv[1] if len(sys.argv) > 1 else SUMMARY_URL)
    block = find_contest(text, sys.argv[2] if len(sys.argv) > 2 else MEASURE_PATTERN)
    print("\n".join(block) if block else "contest not found")
    if block:
        print(parse_contest(block))
