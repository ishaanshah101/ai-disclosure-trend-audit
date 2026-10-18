"""The phrase-reuse measure: for each AI sentence, how many other registrants have
filed a 10-K containing the same core phrase, according to EDGAR full-text search
over the entire 10-K corpus (2001 to the present).

Core phrase: lower-case the sentence, tokenise it the way the search index does
(alphanumeric runs, keeping an internal apostrophe), and take the window of L
consecutive tokens starting at the first AI term. If that window would run past
the end of the sentence, it is shifted left. If the window contains a digit or an
apostrophe, which the index may tokenise differently, the start is moved right by
one token at a time, up to five times, to find a cleaner window; failing that the
original window is used. The sentence's own filing is expected to be among the
hits; a zero-hit result is a normalisation failure and is reported as such.

Usage:
  python src/phrase_reuse.py --pilot        # pilot on the companion corpus
  python src/phrase_reuse.py                # the full corpus
"""
from __future__ import annotations
import argparse, json, os, re, sys, time, urllib.parse, urllib.request

UA = os.environ.get("SEC_USER_AGENT",
                    "Ishaan Shah academic research ishaanshah101@gmail.com")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENTENCES = os.path.join(BASE, "data", "sentences.json")
OUT = os.path.join(BASE, "data", "phrase_reuse.json")
L = 12
AI_FIRST = re.compile(r"artificial intelligence|artificial-intelligence|machine learning|"
                      r"generative ai|large language model|deep learning|neural network|"
                      r"foundation model|\bgenai\b|\bAI\b|\bAI-", re.I)
TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def core_phrase(text, L=L):
    low = text.lower()
    toks = [(m.group(0), m.start()) for m in TOKEN.finditer(low)]
    if not toks:
        return None
    m = AI_FIRST.search(text)
    start_char = m.start() if m else 0
    idx = 0
    for i, (t, pos) in enumerate(toks):
        if pos >= start_char:
            idx = i
            break
    n = len(toks)
    if n <= L:
        return " ".join(t for t, _ in toks)
    idx = min(idx, n - L)
    base = idx
    clean = lambda w: not any(("'" in t) or any(c.isdigit() for c in t) for t in w)
    for shift in range(0, 6):
        s = base + shift
        if s + L > n:
            break
        window = [t for t, _ in toks[s:s + L]]
        if clean(window):
            return " ".join(window)
    return " ".join(t for t, _ in toks[base:base + L])


def fts_phrase(phrase, retries=6):
    q = urllib.parse.urlencode({"q": f'"{phrase}"', "forms": "10-K",
                                "dateRange": "custom", "startdt": "2001-01-01",
                                "enddt": "2026-10-18", "from": 0})
    req = urllib.request.Request("https://efts.sec.gov/LATEST/search-index?" + q,
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
            total = d["hits"]["total"]["value"]
            # the entity aggregation lists distinct filers for the whole result set
            ent = d.get("aggregations", {}).get("entity_filter", {}).get("buckets", [])
            ciks = set()
            for b in ent:
                k = str(b.get("key", ""))
                mm = re.search(r"CIK (\d{10})", k)
                ciks.add(mm.group(1) if mm else k)
            # fall back to the hits on the first page when the aggregation is absent
            if not ent:
                for h in d["hits"]["hits"]:
                    for c in h["_source"].get("ciks") or []:
                        ciks.add(c)
            return {"total_hits": total, "n_ciks": len(ciks), "ciks": sorted(ciks),
                    "agg_truncated": len(ent) >= 100}
        except Exception as e:
            if attempt == retries - 1:
                return {"error": str(e)}
            time.sleep(2 + 3 * attempt)


def run(sentences, own_cik_of, L=L, sleep=0.35, log_every=50, out_path=None, resume=None):
    done = dict(resume or {})
    for i, s in enumerate(sentences, 1):
        sid = s["id"]
        if sid in done and "error" not in done[sid]:
            continue
        phrase = core_phrase(s["text"], L)
        res = fts_phrase(phrase) if phrase else {"error": "no tokens"}
        own = str(own_cik_of(s)).zfill(10) if own_cik_of(s) else None
        rec = {"phrase": phrase, "L": L, **res}
        if "error" not in res:
            others = [c for c in res["ciks"] if c != own]
            rec["self_hit"] = own in res["ciks"] if own else None
            rec["reuse_ciks"] = len(others)
            del rec["ciks"]
        done[sid] = rec
        if out_path and i % log_every == 0:
            json.dump(done, open(out_path, "w"), indent=1)
            print(f"  {i}/{len(sentences)}", flush=True)
        time.sleep(sleep)
    if out_path:
        json.dump(done, open(out_path, "w"), indent=1)
    return done


def pilot():
    """Twenty sentences from the companion study's published 2025 corpus, three
    window lengths, recorded before any sentence from this study is queried."""
    import random
    comp = os.path.join(os.path.dirname(BASE), "ishaanshah101", "ai-claims-audit",
                        "data", "sentences.json")
    d = json.load(open(comp))
    pool = []
    for f in d["filings"]:
        for s in f["ai_sentences"]:
            pool.append({"id": f"{f['adsh']}:{s['idx']}", "text": s["text"], "cik": f["cik"]})
    rng = random.Random(20261018)
    pick = rng.sample(pool, 20)
    result = {}
    for Lp in (8, 10, 12, 16):
        res = run(pick, lambda s: s["cik"], L=Lp, sleep=0.3)
        result[str(Lp)] = res
        selfhit = sum(1 for r in res.values() if r.get("self_hit"))
        reuse = sorted(r.get("reuse_ciks", -1) for r in res.values())
        print(f"L={Lp}: self-hit {selfhit}/20, reuse_ciks sorted {reuse}", flush=True)
    json.dump({"seed": 20261018, "sentences": pick, "results": result},
              open(os.path.join(BASE, "data", "phrase_pilot.json"), "w"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    a = ap.parse_args()
    if a.pilot:
        pilot(); return
    d = json.load(open(SENTENCES))
    sents, cik_of = [], {}
    for f in d["filings"]:
        for s in f["ai_sentences"]:
            sents.append({"id": s["id"], "text": s["text"]})
            cik_of[s["id"]] = f["cik"]
    resume = json.load(open(OUT)) if os.path.exists(OUT) else {}
    run(sents, lambda s: cik_of[s["id"]], L=L, out_path=OUT, resume=resume)
    print("->", OUT)


if __name__ == "__main__":
    main()
