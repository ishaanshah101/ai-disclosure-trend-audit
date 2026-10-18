"""Exploratory: registrant size for every sampled filing, from the SEC XBRL
company-facts API. For each sampled filing the total assets fact (us-gaap
Assets) reported in that very filing (matching accession number) is taken; if
the filing reports none, the fact for the same fiscal year from any 10-K is
used and flagged. Writes data/xbrl_size.json.
"""
from __future__ import annotations
import json, os, time, urllib.request

UA = os.environ.get("SEC_USER_AGENT", "Ishaan Shah academic research ishaanshah101@gmail.com")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(BASE, "data", "sample_filings.json")
OUT = os.path.join(BASE, "data", "xbrl_size.json")


def facts(cik):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 2 * attempt)
        except Exception:
            time.sleep(2 + 2 * attempt)
    return None


def main():
    sample = json.load(open(SAMPLE))
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    cache = {}
    for i, f in enumerate(sample["filings"], 1):
        if f["adsh"] in out:
            continue
        cik = f["cik"]
        if cik not in cache:
            cache[cik] = facts(cik)
            time.sleep(0.2)
        d = cache[cik]
        rec = {"cik": cik, "year": f["year"], "assets": None, "source": None}
        if d:
            units = d.get("facts", {}).get("us-gaap", {}).get("Assets", {}).get("units", {}).get("USD", [])
            same = [u for u in units if u.get("accn") == f["adsh"] and u.get("form") == "10-K"]
            if same:
                best = max(same, key=lambda u: u.get("end", ""))
                rec.update(assets=best["val"], source="same_filing", end=best.get("end"), fy=best.get("fy"))
            else:
                fy = int(f["period_ending"][:4]) if f.get("period_ending") else None
                alt = [u for u in units if u.get("form") == "10-K" and u.get("fp") == "FY" and fy and u.get("fy") == fy]
                if alt:
                    best = max(alt, key=lambda u: u.get("end", ""))
                    rec.update(assets=best["val"], source="same_fy_other_filing", end=best.get("end"), fy=best.get("fy"))
        out[f["adsh"]] = rec
        if i % 25 == 0:
            json.dump(out, open(OUT, "w"), indent=1)
            print(f"  {i}/{len(sample['filings'])}", flush=True)
    json.dump(out, open(OUT, "w"), indent=1)
    n = sum(1 for r in out.values() if r["assets"] is not None)
    print(f"assets found for {n} of {len(out)} filings -> {OUT}")


if __name__ == "__main__":
    main()
