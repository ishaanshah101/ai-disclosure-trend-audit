"""Enumerate the sampling frame for every calendar year from 2015 to 2026: each
10-K filing whose full text matches the exact phrase "artificial intelligence"
according to EDGAR full-text search.

EDGAR returns one hit per document, not per filing. A 10-K filing can therefore
appear several times (the main document, an exhibit, an amendment). Hits are
collapsed to filings by accession number, and the frame used for sampling is
restricted to original 10-K filings (form 10-K, not 10-K/A) in which the main
10-K document itself matched. All raw hits are kept in the output so that the
restriction can be undone.

The SEC asks for a descriptive User-Agent with a contact address on automated
requests and for no more than ten requests per second. Replicators should set
SEC_USER_AGENT to their own contact.
"""
from __future__ import annotations
import json, os, sys, time, urllib.parse, urllib.request
from collections import Counter, defaultdict

UA = os.environ.get("SEC_USER_AGENT",
                    "Ishaan Shah academic research ishaanshah101@gmail.com")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "frame.json")
QUERY = '"artificial intelligence"'
FORMS = "10-K"
YEARS = list(range(2015, 2027))
LAST_DAY = "2026-10-18"          # the day the preregistration was written
PAGE = 100                       # EDGAR returns up to 100 hits per page


def fts(start, end, frm=0, query=QUERY):
    q = urllib.parse.urlencode({"q": query, "forms": FORMS, "dateRange": "custom",
                                "startdt": start, "enddt": end, "from": frm})
    req = urllib.request.Request("https://efts.sec.gov/LATEST/search-index?" + q,
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(6):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:
            if attempt == 5:
                raise
            time.sleep(2 + 3 * attempt)


def enumerate_year(year):
    start = f"{year}-01-01"
    end = f"{year}-12-31" if year < 2026 else LAST_DAY
    first = fts(start, end, 0)
    total = first["hits"]["total"]["value"]
    hits, seen = [], set()
    frm = 0
    while True:
        d = first if frm == 0 else fts(start, end, frm)
        page = d["hits"]["hits"]
        if not page:
            break
        for h in page:
            if h["_id"] in seen:
                continue
            seen.add(h["_id"])
            s = h["_source"]
            hits.append({
                "id": h["_id"],
                "adsh": s.get("adsh"),
                "form": s.get("form"),
                "file_type": s.get("file_type"),
                "root_forms": s.get("root_forms"),
                "cik": (s.get("ciks") or [None])[0],
                "ciks": s.get("ciks"),
                "name": (s.get("display_names") or [None])[0],
                "sic": (s.get("sics") or [None])[0],
                "file_date": s.get("file_date"),
                "period_ending": s.get("period_ending"),
                "state": (s.get("biz_states") or [None])[0],
                "doc": h["_id"].split(":")[-1],
            })
        frm += PAGE
        if frm >= total or frm >= 10000:
            break
        time.sleep(0.25)
    return total, hits


def collapse(hits):
    """One row per accession number, flagging whether the main 10-K matched."""
    by_adsh = defaultdict(list)
    for h in hits:
        by_adsh[h["adsh"]].append(h)
    rows = []
    for adsh, hs in by_adsh.items():
        main = [h for h in hs if h["file_type"] == "10-K" and h["form"] == "10-K"]
        form = hs[0]["form"]
        r = dict(hs[0])
        r["n_docs_matched"] = len(hs)
        r["file_types"] = sorted({h["file_type"] for h in hs})
        r["main_matched"] = bool(main)
        r["is_amendment"] = form != "10-K"
        if main:
            r["doc"] = main[0]["doc"]
            r["id"] = main[0]["id"]
        rows.append(r)
    return rows


def main():
    out = {"query": QUERY, "forms": FORMS, "last_day": LAST_DAY, "years": {}}
    for y in YEARS:
        total, hits = enumerate_year(y)
        rows = collapse(hits)
        frame = [r for r in rows if r["main_matched"] and not r["is_amendment"]]
        reg = len({r["cik"] for r in frame})
        out["years"][str(y)] = {
            "reported_total_hits": total, "collected_hits": len(hits),
            "filings_any_doc": len(rows),
            "filings_main_10k": len(frame), "registrants_main_10k": reg,
            "file_type_counts": dict(Counter(h["file_type"] for h in hits)),
            "form_counts": dict(Counter(h["form"] for h in hits)),
            "rows": rows,
        }
        print(f"{y}: hits {total:5d} collected {len(hits):5d} -> filings {len(rows):5d}, "
              f"original 10-K main-doc matches {len(frame):5d} ({reg} registrants)",
              flush=True)
        time.sleep(0.3)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print("->", OUT)


if __name__ == "__main__":
    main()
