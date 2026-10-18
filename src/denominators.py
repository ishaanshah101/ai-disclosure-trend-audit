"""Count the 10-K filings in each calendar year from the EDGAR full index.

Each quarter's form.idx lists one row per filing. A row is counted when its form
type is exactly `10-K`, so amendments (10-K/A), transition reports (10-KT) and
the obsolete 10-K405 are excluded, matching the frame definition in
src/frame.py. The 2026 count runs through the fourth quarter's index as of the
day the script is run, which is recorded in the output.
"""
from __future__ import annotations
import datetime, json, os, re, time, urllib.request

UA = os.environ.get("SEC_USER_AGENT",
                    "Ishaan Shah academic research ishaanshah101@gmail.com")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "form_index")
OUT = os.path.join(BASE, "data", "denominators.json")
YEARS = range(2015, 2027)
LAST_DAY = "2026-10-18"


def fetch(year, q):
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, f"{year}Q{q}.idx")
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return open(path, "rb").read()
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/form.idx"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            data = urllib.request.urlopen(req, timeout=120).read()
            open(path, "wb").write(data)
            return data
        except Exception:
            if attempt == 4:
                return None
            time.sleep(3 + 3 * attempt)


def count_10k(raw, last_day=None):
    """form.idx columns are fixed width: Form Type (12), Company Name (62),
    CIK (12), Date Filed (12), File Name. Count rows with form type `10-K`,
    optionally only those filed on or before last_day."""
    n, adshs = 0, set()
    text = raw.decode("latin-1")
    started = False
    for line in text.splitlines():
        if not started:
            if line.startswith("-----"):
                started = True
            continue
        form = line[:12].strip()
        if form != "10-K":
            continue
        date = line[86:98].strip()
        if last_day and date > last_day:
            continue
        fname = line[98:].strip()
        m = re.search(r"/(\d{10}-\d{2}-\d{6})\.txt$", fname)
        key = m.group(1) if m else fname
        if key in adshs:
            continue
        adshs.add(key)
        n += 1
    return n


def main():
    out = {"form_type": "10-K", "last_day": LAST_DAY,
           "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "years": {}}
    for y in YEARS:
        total, quarters = 0, {}
        for q in (1, 2, 3, 4):
            if y == 2026 and q == 4 and LAST_DAY < "2026-10-01":
                break
            raw = fetch(y, q)
            if raw is None:
                quarters[f"Q{q}"] = None
                continue
            c = count_10k(raw, LAST_DAY if y == 2026 else None)
            quarters[f"Q{q}"] = c
            total += c
            time.sleep(0.3)
        out["years"][str(y)] = {"total_10k": total, "quarters": quarters}
        print(y, total, quarters, flush=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
