"""Term-list false-positive screen, extended from the companion study.

The companion found that the letters AI inside an entity name produce
sentences with no reference to artificial intelligence. Four registrants in
this sample carry AI in their own names (C3.ai, Spectral AI, SES AI, and
Artificial Intelligence Technology Solutions), and one of them contributes
448 extracted sentences. Two mechanical screens find the candidates:

  A. name-only: once the registrant's own name is removed from the sentence
     (the same redaction the raters see), no AI term remains at all.
  B. entity-suffix: every standalone-abbreviation match is immediately
     followed by a corporate suffix (Inc, LP, LLC, Corp, Ltd, Fund, Holdings)
     or sits inside a comma-and-dash list of entity names.

Candidates are read blind to the study's hypotheses with the question "does
this sentence refer to artificial intelligence as a technology, other than
through a name?", and the verdicts are recorded in
data/term_audit_verdicts.json. `--apply` marks confirmed non-AI sentences so
that every later script can exclude them from every denominator.
"""
from __future__ import annotations
import argparse, json, os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))
from fetch_and_extract import AI_RE_CI, AI_RE_CS          # noqa: E402
from build_rating_sets import name_variants, redact       # noqa: E402

SENT = os.path.join(BASE, "data", "sentences.json")
CAND = os.path.join(BASE, "data", "term_audit_candidates.json")
VERD = os.path.join(BASE, "data", "term_audit_verdicts.json")
ABBREV_ONLY = {r"\bAI\b", r"\bAI-"}
SUFFIX = re.compile(r"\bAI\b[,.]?\s*(?:Inc\b|Inc\.|L\.?P\.?\b|LLC\b|Ltd\b|Corp\b|Corp\.|Fund\b|Holdings\b|Co\.|Company\b)")
LISTCTX = re.compile(r"[-–]\s*AI\b\s*,")      # 'CCG Investment Fund - AI, LP'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="merge verdicts into sentences.json")
    a = ap.parse_args()
    d = json.load(open(SENT))
    cands = []
    total = sum(f["n_ai"] for f in d["filings"])
    for f in d["filings"]:
        variants, ticker = name_variants(f.get("name"))
        for s in f["ai_sentences"]:
            red, _ = redact(s["text"], variants, ticker)
            screen = None
            if not (AI_RE_CI.search(red) or AI_RE_CS.search(red)):
                screen = "A_name_only"
            elif set(s["patterns"]) <= ABBREV_ONLY:
                occ = len(re.findall(r"\bAI\b", s["text"]))
                suf = len(SUFFIX.findall(s["text"])) + len(LISTCTX.findall(s["text"]))
                if occ and suf >= occ:
                    screen = "B_entity_suffix"
            if screen:
                cands.append({"id": s["id"], "adsh": f["adsh"], "registrant": f["name"],
                              "screen": screen, "text": s["text"], "redacted": red})
    if not a.apply:
        json.dump({"n_sentences": total, "n_candidates": len(cands),
                   "by_screen": {k: sum(1 for c in cands if c["screen"] == k)
                                 for k in ("A_name_only", "B_entity_suffix")},
                   "candidates": cands}, open(CAND, "w"), indent=1)
        print(f"{len(cands)} of {total} sentences are candidates -> {CAND}")
        print({k: sum(1 for c in cands if c["screen"] == k) for k in ("A_name_only", "B_entity_suffix")})
        return
    verd = json.load(open(VERD))
    non_ai = {v["id"] for v in verd["verdicts"] if v["non_ai"]}
    n = 0
    for f in d["filings"]:
        for s in f["ai_sentences"]:
            s["non_ai"] = s["id"] in non_ai
            n += s["non_ai"]
        f["n_ai_corrected"] = sum(1 for s in f["ai_sentences"] if not s["non_ai"])
    d["term_audit"] = {"candidates": len(cands), "removed": n,
                       "by_screen": {k: sum(1 for c in cands if c["screen"] == k)
                                     for k in ("A_name_only", "B_entity_suffix")}}
    json.dump(d, open(SENT, "w"), indent=1)
    print(f"marked {n} sentences non_ai in {SENT}")


if __name__ == "__main__":
    main()
