"""Human validation of the language-model labels.

`python src/human_validation.py build` draws a seeded, stratified sample of 300
corpus sentences and writes a blinded coding sheet for each of two human coders
(data/human_validation/coder_A.csv and coder_B.csv, identical sentences in
different random orders). The sheets carry the redacted sentence text the model
raters saw and nothing else.

The stratification oversamples the cells the referee review identified as the
hardest: capability against other, and own-use inside risk sentences.

`python src/human_validation.py score` reads the two completed sheets, and reports
human-human agreement, model-human agreement and the per-class precision and
recall of the model labels against the human consensus, writing
results/human_validation.json. Until both sheets are completed the paper reports
no human validation figures.
"""
from __future__ import annotations
import csv, json, os, sys
from collections import Counter
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats import krippendorff_alpha_nominal  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "human_validation")
SEED = 20261022
CELLS = [("capability", None, 70), ("other", True, 40), ("other", False, 30), ("risk", True, 50),
         ("risk", False, 40), ("market", None, 40), ("governance", None, 8)]
CLASSES = ["capability", "risk", "market", "governance", "other"]


def build():
    labels = {l["sid"]: l for l in json.load(open(os.path.join(BASE, "data", "rating", "labels.json"))).values()}
    items = {i["sid"]: i for i in json.load(open(os.path.join(BASE, "data", "rating", "items.json")))["items"]}
    rng = np.random.default_rng(SEED)
    chosen = []
    for cls, own, k in CELLS:
        pool = sorted(s for s, l in labels.items() if l["class_majority"] == cls and (own is None or l["own_majority"] is own) and s in items)
        take = min(k, len(pool))
        chosen += list(rng.choice(pool, size=take, replace=False))
    rest = sorted(s for s in labels if s not in set(chosen) and s in items and labels[s]["class_majority"])
    chosen += list(rng.choice(rest, size=300 - len(chosen), replace=False))
    os.makedirs(OUT, exist_ok=True)
    key = []
    for coder in ("A", "B"):
        order = list(rng.permutation(chosen))
        with open(os.path.join(OUT, f"coder_{coder}.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["item", "sentence", "class", "own_use", "notes"])
            for n, sid in enumerate(order, 1):
                w.writerow([f"{coder}{n:03d}", items[sid]["text"], "", "", ""])
                key.append({"coder": coder, "item": f"{coder}{n:03d}", "sid": sid})
    json.dump({"seed": SEED, "cells": CELLS, "n": len(chosen), "key": key},
              open(os.path.join(OUT, "key_do_not_open_before_coding.json"), "w"), indent=1)
    print(f"wrote 2 sheets of {len(chosen)} sentences to {OUT}")


def score():
    keyf = json.load(open(os.path.join(OUT, "key_do_not_open_before_coding.json")))
    sid_of = {k["item"]: k["sid"] for k in keyf["key"]}
    labels = {l["sid"]: l for l in json.load(open(os.path.join(BASE, "data", "rating", "labels.json"))).values()}
    codes = {"A": {}, "B": {}}
    for c in codes:
        for row in csv.DictReader(open(os.path.join(OUT, f"coder_{c}.csv"))):
            cl = row["class"].strip().lower(); ou = row["own_use"].strip().lower()
            if cl not in CLASSES or ou not in ("true", "false"):
                raise SystemExit(f"coder {c} item {row['item']} is incomplete or invalid")
            codes[c][sid_of[row["item"]]] = (cl, ou == "true")
    sids = sorted(set(codes["A"]) & set(codes["B"]))
    hh_class = [[codes["A"][s][0], codes["B"][s][0]] for s in sids]
    hh_own = [[codes["A"][s][1], codes["B"][s][1]] for s in sids]
    agree = [s for s in sids if codes["A"][s] == codes["B"][s]]
    res = {"n": len(sids),
           "human_human": {"class_agreement": float(np.mean([a == b for a, b in hh_class])),
                           "class_alpha": krippendorff_alpha_nominal(hh_class),
                           "own_agreement": float(np.mean([a == b for a, b in hh_own])),
                           "own_alpha": krippendorff_alpha_nominal([[str(a), str(b)] for a, b in hh_own])},
           "n_human_consensus": len(agree)}
    mh_class = [[codes["A"][s][0], labels[s]["class_majority"]] for s in agree]
    mh_own = [[str(codes["A"][s][1]), str(labels[s]["own_majority"])] for s in agree]
    res["model_vs_consensus"] = {"class_agreement": float(np.mean([a == b for a, b in mh_class])),
                                 "class_alpha": krippendorff_alpha_nominal(mh_class),
                                 "own_agreement": float(np.mean([a == b for a, b in mh_own])),
                                 "own_alpha": krippendorff_alpha_nominal(mh_own)}
    pr = {}
    for c in CLASSES:
        tp = sum(1 for h, m in mh_class if h == c and m == c)
        fp = sum(1 for h, m in mh_class if h != c and m == c)
        fn = sum(1 for h, m in mh_class if h == c and m != c)
        pr[c] = {"precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
                 "n_human": tp + fn}
    res["per_class"] = pr
    res["confusion_human_rows_model_cols"] = {h: dict(Counter(m for hh, m in mh_class if hh == h)) for h in CLASSES}
    json.dump(res, open(os.path.join(BASE, "results", "human_validation.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    {"build": build, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
