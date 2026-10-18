"""Build the blinded calibration materials, and unblind them afterwards.

  --build : draw 120 sentences stratified over the five majority classes and
            the three eras (8 per cell where available, filled from the
            largest cells otherwise), add 10 duplicates under second display
            identifiers as self-consistency controls, shuffle, and write
            data/calibration/blind.json (text only) and key.json (never read
            before the review is recorded).
  --score : read data/calibration/reviewer.jsonl, join to the key, compute
            survival rates per class, the forward-transfer matrix, own-use
            survival, and duplicate consistency; write results/calibration.json.
"""
from __future__ import annotations
import argparse, json, os, random, sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))
from stats import wilson  # noqa: E402

RDIR = os.path.join(BASE, "data", "rating")
CDIR = os.path.join(BASE, "data", "calibration")
SEED = 20261018
CLASSES = ["capability", "risk", "market", "governance", "other"]
ERAS = {"2015-2019": range(2015, 2020), "2020-2023": range(2020, 2024), "2024-2026": range(2024, 2027)}
N_TOTAL, N_DUP = 120, 10


def era_of(y):
    for e, r in ERAS.items():
        if y in r:
            return e


def build():
    items = {it["did"]: it for it in json.load(open(os.path.join(RDIR, "items.json")))["items"]}
    labels = json.load(open(os.path.join(RDIR, "labels.json")))
    sents = json.load(open(os.path.join(BASE, "data", "sentences.json")))
    non_ai = {s["id"] for f in sents["filings"] for s in f["ai_sentences"] if s.get("non_ai")}
    cells = defaultdict(list)
    for did, l in labels.items():
        if l["sid"] in non_ai or l.get("class_majority") is None:
            continue
        cells[(l["class_majority"], era_of(l["year"]))].append(did)
    rng = random.Random(SEED)
    per_cell = N_TOTAL // (len(CLASSES) * len(ERAS))     # 8
    chosen = []
    for c in CLASSES:
        for e in ERAS:
            pool = sorted(cells[(c, e)])
            rng.shuffle(pool)
            chosen += pool[:per_cell]
    # fill the remainder from the whole eligible pool, without replacement
    rest = sorted(set(d for v in cells.values() for d in v) - set(chosen))
    rng.shuffle(rest)
    chosen += rest[:N_TOTAL - len(chosen)]
    dups = rng.sample(chosen, N_DUP)
    displays = [(d, 0) for d in chosen] + [(d, 1) for d in dups]
    rng.shuffle(displays)
    os.makedirs(CDIR, exist_ok=True)
    blind, key = [], []
    for k, (d, rep) in enumerate(displays):
        cid = f"c{k + 1:03d}"
        blind.append({"cid": cid, "text": items[d]["text"]})
        l = labels[d]
        key.append({"cid": cid, "did": d, "rep": rep, "class_majority": l["class_majority"],
                    "own_majority": l["own_majority"], "era": era_of(l["year"]),
                    "disputed": l["disputed"] or l["own_disputed"]})
    json.dump(blind, open(os.path.join(CDIR, "blind.json"), "w"), indent=1)
    json.dump(key, open(os.path.join(CDIR, "key.json"), "w"), indent=1)
    json.dump({"seed": SEED, "n_units": len(chosen), "n_displays": len(displays), "n_duplicates": N_DUP,
               "cells": {f"{c}|{e}": len(cells[(c, e)]) for c in CLASSES for e in ERAS}},
              open(os.path.join(CDIR, "manifest.json"), "w"), indent=1)
    print(f"{len(chosen)} units, {len(displays)} displays -> {CDIR}/blind.json")


def score():
    key = {k["cid"]: k for k in json.load(open(os.path.join(CDIR, "key.json")))}
    rev = {}
    for line in open(os.path.join(CDIR, "reviewer.jsonl")):
        line = line.strip()
        if line:
            j = json.loads(line)
            rev[j["cid"]] = j
    missing = [c for c in key if c not in rev]
    if missing:
        print("missing reviewer calls:", missing); sys.exit(1)
    # duplicate consistency
    by_did = defaultdict(list)
    for cid, k in key.items():
        by_did[k["did"]].append(rev[cid])
    dup_pairs = [v for v in by_did.values() if len(v) == 2]
    dup_class_ok = sum(1 for a, b in dup_pairs if a["class"] == b["class"])
    dup_own_ok = sum(1 for a, b in dup_pairs if a["own_use"] == b["own_use"])
    # survival and transfer on rep == 0 displays
    transfer = defaultdict(Counter)
    own_conf = Counter()
    era_surv = defaultdict(lambda: [0, 0])
    for cid, k in key.items():
        if k["rep"] != 0:
            continue
        r = rev[cid]
        transfer[k["class_majority"]][r["class"]] += 1
        own_conf[(k["own_majority"], r["own_use"])] += 1
        era_surv[k["era"]][0] += (r["class"] == k["class_majority"])
        era_surv[k["era"]][1] += 1
    surv = {}
    tmat = {}
    for c in CLASSES:
        n = sum(transfer[c].values())
        s = transfer[c][c]
        surv[c] = {"survived": s, "n": n, "rate": s / n if n else None, "wilson": wilson(s, n) if n else None}
        tmat[c] = {j: transfer[c][j] / n for j in CLASSES} if n else {}
    own = {"true_survived": own_conf[(True, True)], "true_n": own_conf[(True, True)] + own_conf[(True, False)],
           "false_survived": own_conf[(False, False)], "false_n": own_conf[(False, False)] + own_conf[(False, True)]}
    own["true_rate"] = own["true_survived"] / own["true_n"] if own["true_n"] else None
    own["false_rate"] = own["false_survived"] / own["false_n"] if own["false_n"] else None
    res = {"n_units": sum(1 for k in key.values() if k["rep"] == 0), "n_displays": len(key),
           "duplicates": {"n": len(dup_pairs), "class_consistent": dup_class_ok, "own_consistent": dup_own_ok},
           "survival_by_class": surv, "transfer_matrix": tmat,
           "overall_survival": sum(s["survived"] for s in surv.values()) / sum(s["n"] for s in surv.values()),
           "survival_by_era": {e: {"survived": v[0], "n": v[1], "rate": v[0] / v[1] if v[1] else None}
                               for e, v in era_surv.items()},
           "own_use": own,
           "reviewer": "Claude Fable 5.1, orchestrating model, blind to the key"}
    os.makedirs(os.path.join(BASE, "results"), exist_ok=True)
    json.dump(res, open(os.path.join(BASE, "results", "calibration.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("transfer_matrix",)}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if a.build:
        build()
    if a.score:
        score()
