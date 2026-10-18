"""Report which rating batches still lack a complete output file."""
from __future__ import annotations
import glob, json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RDIR = os.path.join(BASE, "data", "rating")


def main():
    missing, bad, done = [], [], 0
    for r in range(6):
        for path in sorted(glob.glob(os.path.join(RDIR, f"rater_{r}", "batch_*.tsv"))):
            n_in = sum(1 for _ in open(path))
            out = path[:-4] + ".out.jsonl"
            if not os.path.exists(out):
                missing.append((r, os.path.basename(path)))
                continue
            ids_in = [l.split("\t", 1)[0] for l in open(path)]
            try:
                rows = [json.loads(l) for l in open(out) if l.strip()]
            except json.JSONDecodeError:
                bad.append((r, os.path.basename(path), "bad json")); continue
            ids_out = [x.get("id") for x in rows]
            if ids_out != ids_in:
                bad.append((r, os.path.basename(path), f"{len(ids_out)} of {n_in}, order/ids differ"))
            else:
                done += 1
    print(f"complete batches: {done}")
    print("missing:", missing)
    print("bad:", bad)
    if "--json" in sys.argv:
        print(json.dumps({"missing": missing, "bad": bad}))


if __name__ == "__main__":
    main()
