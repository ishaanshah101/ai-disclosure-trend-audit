"""Schema-check every rater output line and assemble all judgements.

Each rater pass writes one JSONL file per batch to data/rating/rater_<r>/
batch_<j>.out.jsonl. This script checks that every assigned display id was
rated exactly once by each of its two assigned raters, that every class is
legal and every own_use is boolean, and writes data/rating/all_ratings.json.
It exits non-zero on any problem so that a dropped batch cannot go unnoticed.
"""
from __future__ import annotations
import glob, json, os, sys
from collections import Counter, defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RDIR = os.path.join(BASE, "data", "rating")
CLASSES = {"capability", "risk", "market", "governance", "other"}


def load_outputs(r):
    out = {}
    problems = []
    for path in sorted(glob.glob(os.path.join(RDIR, f"rater_{r}", "batch_*.out.jsonl"))):
        for ln, line in enumerate(open(path), 1):
            line = line.strip()
            if not line:
                continue
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                problems.append(f"rater {r} {os.path.basename(path)}:{ln} not JSON: {line[:80]}")
                continue
            did = j.get("id")
            if did in out:
                problems.append(f"rater {r} duplicate judgement for {did}")
                continue
            if j.get("class") not in CLASSES:
                problems.append(f"rater {r} illegal class for {did}: {j.get('class')!r}")
            if not isinstance(j.get("own_use"), bool):
                problems.append(f"rater {r} own_use not boolean for {did}: {j.get('own_use')!r}")
            if set(j.keys()) - {"id", "class", "own_use"}:
                problems.append(f"rater {r} extra keys for {did}: {sorted(set(j.keys()) - {'id','class','own_use'})}")
            out[did] = {"class": j.get("class"), "own_use": j.get("own_use")}
    return out, problems


def main():
    items = json.load(open(os.path.join(RDIR, "items.json")))["items"]
    problems = []
    outputs = {}
    for r in range(6):
        outputs[r], p = load_outputs(r)
        problems += p
    ratings = {}
    for it in items:
        did = it["did"]
        rec = {"did": did, "sid": it["sid"], "adsh": it["adsh"], "year": it["year"],
               "raters": it["raters"], "judgements": {}}
        for r in it["raters"]:
            if did not in outputs[r]:
                problems.append(f"rater {r} missing judgement for {did}")
            else:
                rec["judgements"][str(r)] = outputs[r][did]
        ratings[did] = rec
    assigned = {(it["did"], r) for it in items for r in it["raters"]}
    for r in range(6):
        for did in outputs[r]:
            if (did, r) not in assigned:
                problems.append(f"rater {r} rated unassigned id {did}")
    n_j = sum(len(v["judgements"]) for v in ratings.values())
    print(f"items {len(items)}, judgements {n_j}, expected {2 * len(items)}")
    print("per rater:", {r: len(outputs[r]) for r in range(6)})
    if problems:
        print(f"{len(problems)} problems:")
        for p in problems[:50]:
            print("  ", p)
        sys.exit(1)
    json.dump(ratings, open(os.path.join(RDIR, "all_ratings.json"), "w"), indent=1)
    print("schema check passed ->", os.path.join(RDIR, "all_ratings.json"))


if __name__ == "__main__":
    main()
