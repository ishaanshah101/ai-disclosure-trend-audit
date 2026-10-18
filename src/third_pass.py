"""Build and merge the third pass.

Every sentence on which the two blind passes disagree on class or on own_use
is rated a third time by a different model tier, blind to both prior verdicts
and to the fact of disagreement. To keep selection from revealing
disagreement, an equal number of agreed sentences is drawn at random and mixed
in under fresh display identifiers.

  python src/third_pass.py --build   # writes data/rating/third/batch_*.tsv
  python src/third_pass.py --merge   # reads batch_*.out.jsonl, writes labels

Majority-of-three labels are written back into data/rating/labels.json as
class_majority and own_majority. A sentence that still has three different
class verdicts keeps class_majority = None.
"""
from __future__ import annotations
import argparse, glob, json, os, random, sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RDIR = os.path.join(BASE, "data", "rating")
TDIR = os.path.join(RDIR, "third")
SEED = 20261018
BATCH = 50


def build():
    items = {it["did"]: it for it in json.load(open(os.path.join(RDIR, "items.json")))["items"]}
    labels = json.load(open(os.path.join(RDIR, "labels.json")))
    disputed = [d for d, l in labels.items() if l["disputed"] or l["own_disputed"]]
    agreed = [d for d, l in labels.items() if not (l["disputed"] or l["own_disputed"])]
    rng = random.Random(SEED)
    fillers = rng.sample(sorted(agreed), min(len(disputed), len(agreed)))
    pool = [(d, "disputed") for d in disputed] + [(d, "filler") for d in fillers]
    rng.shuffle(pool)
    os.makedirs(TDIR, exist_ok=True)
    key = []
    for k, (d, kind) in enumerate(pool):
        tid = f"t{k + 1:05d}"
        key.append({"tid": tid, "did": d, "kind": kind})
    json.dump({"seed": SEED, "n_disputed": len(disputed), "n_filler": len(fillers), "key": key},
              open(os.path.join(TDIR, "key.json"), "w"), indent=1)
    for j in range(0, len(key), BATCH):
        with open(os.path.join(TDIR, f"batch_{j // BATCH:02d}.tsv"), "w") as fh:
            for row in key[j:j + BATCH]:
                fh.write(f"{row['tid']}\t{items[row['did']]['text']}\n")
    print(f"third pass: {len(disputed)} disputed + {len(fillers)} fillers = {len(key)} items "
          f"in {(len(key) + BATCH - 1) // BATCH} batches")


def merge():
    labels = json.load(open(os.path.join(RDIR, "labels.json")))
    key = {r["tid"]: r for r in json.load(open(os.path.join(TDIR, "key.json")))["key"]}
    third = {}
    for path in sorted(glob.glob(os.path.join(TDIR, "batch_*.out.jsonl"))):
        for line in open(path):
            line = line.strip()
            if line:
                j = json.loads(line)
                third[j["id"]] = j
    missing = [t for t in key if t not in third]
    if missing:
        print(f"{len(missing)} third-pass items missing, e.g. {missing[:5]}")
        sys.exit(1)
    stats = Counter()
    for tid, row in key.items():
        d = row["did"]
        j = third[tid]
        l = labels[d]
        l["class_c"] = j["class"]
        l["own_c"] = j["own_use"]
        votes = Counter([l["class_a"], l["class_b"], j["class"]])
        top, n = votes.most_common(1)[0]
        l["class_majority"] = top if n >= 2 else None
        ov = Counter([l["own_a"], l["own_b"], j["own_use"]])
        l["own_majority"] = ov.most_common(1)[0][0]
        if row["kind"] == "filler":
            stats["filler_class_agree"] += (j["class"] == l["class_agreed"])
            stats["filler_own_agree"] += (j["own_use"] == l["own_agreed"])
            stats["filler_n"] += 1
        else:
            stats["disputed_n"] += 1
            stats["disputed_resolved_class"] += (l["class_majority"] is not None)
    for d, l in labels.items():
        if "class_majority" not in l:
            l["class_majority"] = l["class_agreed"]
            l["own_majority"] = l["own_agreed"]
            l["class_c"] = None
            l["own_c"] = None
    json.dump(labels, open(os.path.join(RDIR, "labels.json"), "w"), indent=1)
    json.dump(dict(stats), open(os.path.join(TDIR, "merge_stats.json"), "w"), indent=1)
    print(dict(stats))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    if a.build:
        build()
    if a.merge:
        merge()
