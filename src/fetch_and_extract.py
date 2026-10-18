"""Download each sampled 10-K main document and extract every sentence that
mentions AI.

The sentence splitter, the length rule (60 to 1,200 characters) and the digit
rule (under 25 percent digits) are the companion study's, unchanged. The term
list differs from the companion's in exactly the two preregistered ways: `\\bml\\b`
is dropped and the standalone abbreviation is matched case-sensitively. The
pattern that matched is recorded for every sentence so the term audit can rerun.
"""
from __future__ import annotations
import html, json, os, re, time, urllib.request
from collections import Counter

UA = os.environ.get("SEC_USER_AGENT",
                    "Ishaan Shah academic research ishaanshah101@gmail.com")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(BASE, "data", "sample_filings.json")
RAW = os.path.join(BASE, "data", "filings")
OUT = os.path.join(BASE, "data", "sentences.json")

# Fixed in the preregistration before any filing was read.
AI_PATTERNS_CI = [
    r"artificial intelligence", r"artificial-intelligence", r"machine learning",
    r"generative ai", r"large language model", r"deep learning", r"neural network",
    r"foundation model", r"\bgenai\b",
]
AI_PATTERNS_CS = [r"\bAI\b", r"\bAI-"]
AI_RE_CI = re.compile("|".join(AI_PATTERNS_CI), re.I)
AI_RE_CS = re.compile("|".join(AI_PATTERNS_CS))
PATTERN_NAMES = [(re.compile(p, re.I), p) for p in AI_PATTERNS_CI] + \
                [(re.compile(p), p) for p in AI_PATTERNS_CS]


def url_for(adsh, cik, doc):
    a = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{a}/{doc}"


def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 2000:
        return open(path, "rb").read()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            data = urllib.request.urlopen(req, timeout=120).read()
            open(path, "wb").write(data)
            return data
        except Exception:
            if attempt == 4:
                return None
            time.sleep(2 + 3 * attempt)


def to_text(raw: bytes) -> str:
    """Identical to the companion study."""
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|ix:header)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ").replace("’", "'").replace("“", '"') \
         .replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


ABBREV = r"(?<!\bNo)(?<!\bInc)(?<!\bLtd)(?<!\bCorp)(?<!\bCo)(?<!\bU\.S)(?<!\bU\.K)" \
         r"(?<!\bMr)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bvs)(?<!\be\.g)(?<!\bi\.e)(?<!\bApprox)"
SPLIT_RE = re.compile(ABBREV + r"(?<=[.!?])\s+(?=[A-Z(\"'])")


def sentences(text):
    return [p.strip() for p in SPLIT_RE.split(text) if p.strip()]


def matched_patterns(s):
    return [name for rx, name in PATTERN_NAMES if rx.search(s)]


def main():
    os.makedirs(RAW, exist_ok=True)
    sample = json.load(open(SAMPLE))
    out, failures = [], []
    counter = 0
    for i, f in enumerate(sample["filings"], 1):
        url = url_for(f["adsh"], f["cik"], f["doc"])
        path = os.path.join(RAW, f"{f['adsh']}_{f['doc']}"[:180])
        raw = fetch(url, path)
        if not raw:
            failures.append({"adsh": f["adsh"], "url": url})
            print(f"  [{i:3d}/{len(sample['filings'])}] FAILED {url}", flush=True)
            continue
        text = to_text(raw)
        sents = sentences(text)
        hits = []
        for j, s in enumerate(sents):
            if not (AI_RE_CI.search(s) or AI_RE_CS.search(s)):
                continue
            if not (60 <= len(s) <= 1200):
                continue
            if sum(c.isdigit() for c in s) > len(s) * 0.25:
                continue
            counter += 1
            hits.append({"id": f"s{counter:05d}", "idx": j, "text": s,
                         "patterns": matched_patterns(s)})
        out.append({**f, "url": url, "chars": len(text), "n_sentences": len(sents),
                    "ai_sentences": hits, "n_ai": len(hits)})
        print(f"  [{i:3d}/{len(sample['filings'])}] {f['year']} {str(f['name'])[:40]:40s} "
              f"{len(text):>9,} chars  {len(hits):>4} AI sentences", flush=True)
        time.sleep(0.2)

    json.dump({"ai_patterns_case_insensitive": AI_PATTERNS_CI,
               "ai_patterns_case_sensitive": AI_PATTERNS_CS,
               "filings": out, "failures": failures}, open(OUT, "w"), indent=1)
    tot = sum(f["n_ai"] for f in out)
    print(f"\nfilings fetched: {len(out)} of {len(sample['filings'])}  failures: {len(failures)}")
    print(f"AI sentences total: {tot}")
    by_year = Counter()
    for f in out:
        by_year[f["year"]] += f["n_ai"]
    print("by year:", dict(sorted(by_year.items())))


if __name__ == "__main__":
    main()
