"""Blind, shuffle and assign every corpus sentence to two of six rater passes, and
insert the known-answer controls.

Blinding: the registrant's name (several variants) and ticker are removed from
the sentence text; sentences get display identifiers that carry no information
about filing, year or order; the order is a seeded shuffle across all filings and
years. Each sentence goes to exactly two raters by a fixed rule: the 15 unordered
pairs of six raters are cycled through the shuffled order.

Known-answer controls: 30 sentences from the companion study's calibration set
whose class was fixed by its blinded reviewer and agreed with by its automated
passes. They are inserted unmarked into the stream. Their key is written to a
separate file and never shown to a rater.
"""
from __future__ import annotations
import itertools, json, os, re, random
from collections import Counter

SEED = 20261018
N_RATERS = 6
BATCH = 50
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENT = os.path.join(BASE, "data", "sentences.json")
OUTDIR = os.path.join(BASE, "data", "rating")
COMPANION = os.path.join(os.path.dirname(BASE), "ishaanshah101", "ai-claims-audit",
                         "data", "calibration")
CONTROL_PLAN = {"capability": 8, "risk": 8, "market": 6, "other": 6, "governance": 2}
SUFFIXES = r"(?:,?\s+(?:inc|corp|corporation|co|company|ltd|limited|plc|llc|lp|l\.p|n\.v|s\.a|holdings?|group|international|incorporated|trust|bancorp|financial)\.?)+$"


def name_variants(display):
    """From 'Facebook Inc  (META)  (CIK 0001326801)' build the strings to redact."""
    if not display:
        return [], None
    parts = re.split(r"\s{2,}\(", display)
    name = parts[0].strip()
    ticker = None
    m = re.search(r"\(([A-Z.\-]{1,6})\)", display)
    if m and not m.group(1).startswith("CIK"):
        ticker = m.group(1)
    name = re.sub(r"\s*/[A-Z]{2}/?\s*$", "", name)          # trailing /DE/
    variants = {name}
    stripped = re.sub(SUFFIXES, "", name, flags=re.I).strip(" ,.")
    if len(stripped) >= 4:
        variants.add(stripped)
    variants = {v for v in variants if len(v) >= 4}
    return sorted(variants, key=len, reverse=True), ticker


def redact(text, variants, ticker):
    """Remove the registrant's name (allowing any punctuation or spacing between
    its tokens, so that 'C3.ai' also catches 'C3 AI') and its ticker. A ticker
    that is itself an AI term (C3.ai trades as AI) is not redacted, because that
    would erase the very term being rated."""
    n = 0
    for v in variants:
        toks = re.findall(r"[A-Za-z0-9]+", v)
        if not toks:
            continue
        pat = r"\W*".join(re.escape(t) for t in toks)
        text, k = re.subn(pat, "[the registrant]", text, flags=re.I)
        n += k
    if ticker and len(ticker) >= 2 and not re.fullmatch(r"AI", ticker):
        text, k = re.subn(r"\b" + re.escape(ticker) + r"\b", "[TICKER]", text)
        n += k
    text = re.sub(r"(\[the registrant\]\W*){2,}", "[the registrant] ", text)
    return text, n


def load_controls(rng):
    blind = {b["did"]: b["text"] for b in json.load(open(os.path.join(COMPANION, "c1_blind.json")))}
    key = {k["did"]: k for k in json.load(open(os.path.join(COMPANION, "c1_key.json")))}
    rev = {}
    for line in open(os.path.join(COMPANION, "c1_reviewer.jsonl")):
        line = line.strip()
        if line:
            r = json.loads(line)
            rev[r["did"]] = r["class"]
    pool = {c: [] for c in CONTROL_PLAN}
    for did, text in blind.items():
        k = key.get(did)
        if not k or k.get("rep", 0) != 0:
            continue
        if did in rev and rev[did] == k["prior"] and k["prior"] in pool:
            pool[k["prior"]].append({"did": did, "text": text, "class": k["prior"]})
    controls = []
    for c, n in CONTROL_PLAN.items():
        cand = sorted(pool[c], key=lambda x: x["did"])
        rng.shuffle(cand)
        controls.extend(cand[:n])
    return controls


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    rng = random.Random(SEED)
    d = json.load(open(SENT))
    items, leak_stats = [], Counter()
    for f in d["filings"]:
        variants, ticker = name_variants(f.get("name"))
        for s in f["ai_sentences"]:
            text, n = redact(s["text"], variants, ticker)
            leak_stats["redacted_sentences" if n else "untouched"] += 1
            items.append({"sid": s["id"], "adsh": f["adsh"], "year": f["year"],
                          "text": text, "redactions": n})
    controls = load_controls(rng)
    for i, c in enumerate(controls):
        items.append({"sid": f"ctrl{i:02d}", "adsh": None, "year": None,
                      "text": c["text"], "control_class": c["class"],
                      "control_source": c["did"], "redactions": 0})
    rng.shuffle(items)
    for k, it in enumerate(items):
        it["did"] = f"d{k + 1:05d}"
    pairs = list(itertools.combinations(range(N_RATERS), 2))
    assign = {r: [] for r in range(N_RATERS)}
    for k, it in enumerate(items):
        a, b = pairs[k % len(pairs)]
        it["raters"] = [a, b]
        assign[a].append(it)
        assign[b].append(it)
    json.dump({"seed": SEED, "n_items": len(items), "n_controls": len(controls),
               "batch": BATCH, "items": items}, open(os.path.join(OUTDIR, "items.json"), "w"), indent=1)
    json.dump([{"did": it["did"], "sid": it["sid"], "class": it["control_class"],
                "source": it["control_source"]} for it in items if it["sid"].startswith("ctrl")],
              open(os.path.join(OUTDIR, "controls_key.json"), "w"), indent=1)
    for r, lst in assign.items():
        batches = [lst[i:i + BATCH] for i in range(0, len(lst), BATCH)]
        bdir = os.path.join(OUTDIR, f"rater_{r}")
        os.makedirs(bdir, exist_ok=True)
        for j, b in enumerate(batches):
            with open(os.path.join(bdir, f"batch_{j:02d}.tsv"), "w") as fh:
                for it in b:
                    fh.write(f"{it['did']}\t{it['text']}\n")
        print(f"rater {r}: {len(lst)} items in {len(batches)} batches")
    print(f"items {len(items)} (controls {len(controls)}), redaction: {dict(leak_stats)}")


if __name__ == "__main__":
    main()
