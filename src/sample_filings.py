"""Draw the filing sample: within each calendar year, one filing per registrant
and a simple random sample of registrants, under a fixed seed.

The draw is 30 filings in 2015, 2016 and 2017 and 25 in each year from 2018 to
2026, 315 in all, as preregistered. Within a year the draw is not stratified, so
the sample's sector mix tracks the frame's.
"""
from __future__ import annotations
import json, os
from collections import Counter
import numpy as np

SEED = 20261018
PER_YEAR = {y: (30 if y <= 2017 else 25) for y in range(2015, 2027)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAME = os.path.join(BASE, "data", "frame.json")
OUT = os.path.join(BASE, "data", "sample_filings.json")


def sector(sic):
    """Four broad strata from the SEC's SIC code, identical to the companion study."""
    if not sic or not str(sic).isdigit():
        return "other"
    s = int(sic)
    if 7370 <= s <= 7379 or 3570 <= s <= 3579 or 3660 <= s <= 3679:
        return "technology"
    if 2833 <= s <= 2836 or 3826 <= s <= 3851 or 8000 <= s <= 8099 or s == 5912:
        return "healthcare"
    if 6000 <= s <= 6799:
        return "finance_realestate"
    return "other"


def main():
    frame = json.load(open(FRAME))
    rng = np.random.default_rng(SEED)
    chosen = []
    for y in range(2015, 2027):
        rows = [r for r in frame["years"][str(y)]["rows"]
                if r["main_matched"] and not r["is_amendment"]]
        by_cik = {}
        for r in sorted(rows, key=lambda r: (r["cik"] or "", r["adsh"] or "")):
            by_cik.setdefault(r["cik"], []).append(r)
        ciks = sorted(by_cik)
        # one filing per registrant, chosen at random when there are several
        uniq = []
        for c in ciks:
            opts = by_cik[c]
            uniq.append(opts[int(rng.integers(len(opts)))] if len(opts) > 1 else opts[0])
        n = min(PER_YEAR[y], len(uniq))
        pick = rng.permutation(len(uniq))[:n]
        for i in sorted(int(i) for i in pick):
            r = dict(uniq[i])
            r["year"] = y
            r["sector"] = sector(r["sic"])
            chosen.append(r)
        print(f"{y}: frame {len(rows)} filings, {len(uniq)} registrants, drew {n}  "
              f"{dict(Counter(sector(uniq[int(i)]['sic']) for i in pick))}")
    reps = Counter(r["cik"] for r in chosen)
    multi = {c: n for c, n in reps.items() if n > 1}
    json.dump({"seed": SEED, "per_year": PER_YEAR, "n": len(chosen),
               "registrants_drawn_in_more_than_one_year": multi,
               "filings": chosen}, open(OUT, "w"), indent=1)
    print(f"\nsampled {len(chosen)} filings, {len(reps)} distinct registrants, "
          f"{len(multi)} drawn in more than one year -> {OUT}")


if __name__ == "__main__":
    main()
