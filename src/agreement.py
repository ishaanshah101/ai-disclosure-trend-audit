"""Inter-pass agreement, known-answer control accuracy, and blinding-leak audit.

Reads the two blind passes per sentence, computes observed agreement,
Krippendorff's alpha (nominal) for class and for own_use, positive specific
agreement per class, the disagreement pairs, accuracy on the 30 known-answer
controls, and agreement on sentences that carry an era cue or a residual
registrant-name token. Writes results/agreement.json and marks each corpus
item as agreed or disputed in data/rating/labels.json.
"""
from __future__ import annotations
import json, os, re, sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))
from stats import krippendorff_alpha_nominal, observed_agreement, positive_specific_agreement, wilson  # noqa
from build_rating_sets import name_variants  # noqa

RDIR = os.path.join(BASE, "data", "rating")
SENT = os.path.join(BASE, "data", "sentences.json")
OUT = os.path.join(BASE, "results", "agreement.json")
LABELS = os.path.join(RDIR, "labels.json")
CLASSES = ["capability", "risk", "market", "governance", "other"]
ERA_CUE = re.compile(r"generative|large language model|\bLLMs?\b|ChatGPT|\bGenAI\b|foundation model|"
                     r"OpenAI|Copilot|\bGPT\b|agentic|\bAI agents?\b", re.I)
GENERIC = {"inc", "corp", "corporation", "company", "holdings", "group", "international", "limited",
           "ltd", "technologies", "technology", "systems", "solutions", "services", "global", "health",
           "energy", "financial", "capital", "partners", "trust", "bancorp", "america", "american",
           "united", "national", "general", "first", "digital", "data", "software", "medical",
           "therapeutics", "pharmaceuticals", "industries", "resources", "communications", "networks",
           "sciences", "bank", "realty", "properties", "income", "fund", "investment", "acquisition"}


def main():
    items = {it["did"]: it for it in json.load(open(os.path.join(RDIR, "items.json")))["items"]}
    ratings = json.load(open(os.path.join(RDIR, "all_ratings.json")))
    ckey = {c["did"]: c["class"] for c in json.load(open(os.path.join(RDIR, "controls_key.json")))}
    sents = json.load(open(SENT))
    non_ai = {s["id"] for f in sents["filings"] for s in f["ai_sentences"] if s.get("non_ai")}
    names = {f["adsh"]: f.get("name") for f in sents["filings"]}

    pairs_class, pairs_own, units_class, units_own = [], [], [], []
    labels = {}
    dis_pairs = Counter()
    era_pairs, plain_pairs, leak_pairs, noleak_pairs = [], [], [], []
    n_era = n_leak = 0
    ctrl_right = Counter(); ctrl_total = Counter(); ctrl_conf = Counter()
    for did, rec in ratings.items():
        it = items[did]
        js = list(rec["judgements"].values())
        if len(js) != 2:
            continue
        a, b = js
        if did in ckey:
            for j in js:
                ctrl_total[ckey[did]] += 1
                ctrl_right[ckey[did]] += (j["class"] == ckey[did])
                ctrl_conf[(ckey[did], j["class"])] += 1
            continue
        if it["sid"] in non_ai:
            continue
        pairs_class.append((a["class"], b["class"]))
        pairs_own.append((a["own_use"], b["own_use"]))
        units_class.append([a["class"], b["class"]])
        units_own.append([a["own_use"], b["own_use"]])
        agreed = a["class"] == b["class"]
        if not agreed:
            dis_pairs[tuple(sorted((a["class"], b["class"])))] += 1
        labels[did] = {"sid": it["sid"], "adsh": it["adsh"], "year": it["year"],
                       "class_a": a["class"], "class_b": b["class"],
                       "class_agreed": a["class"] if agreed else None, "disputed": not agreed,
                       "own_a": a["own_use"], "own_b": b["own_use"],
                       "own_agreed": a["own_use"] if a["own_use"] == b["own_use"] else None,
                       "own_disputed": a["own_use"] != b["own_use"]}
        era = bool(ERA_CUE.search(it["text"]))
        n_era += era
        (era_pairs if era else plain_pairs).append((a["class"], b["class"]))
        # residual name leak: a distinctive registrant-name token survives in the shown text
        variants, _ = name_variants(names.get(it["adsh"]))
        toks = {t.lower() for v in variants for t in re.findall(r"[A-Za-z]{4,}", v)} - GENERIC
        shown = set(t.lower() for t in re.findall(r"[A-Za-z]{4,}", it["text"]))
        leak = bool(toks & shown)
        n_leak += leak
        (leak_pairs if leak else noleak_pairs).append((a["class"], b["class"]))

    n = len(pairs_class)
    res = {
        "n_corpus_rated": n,
        "n_removed_non_ai": len(non_ai),
        "class": {
            "observed_agreement": observed_agreement(pairs_class),
            "n_agree": sum(1 for a, b in pairs_class if a == b),
            "krippendorff_alpha": krippendorff_alpha_nominal(units_class),
            "positive_specific_agreement": {c: positive_specific_agreement(pairs_class, c) for c in CLASSES},
            "disagreement_pairs": {" vs ".join(k): v for k, v in dis_pairs.most_common()},
            "agreed_counts": dict(Counter(a for a, b in pairs_class if a == b)),
        },
        "own_use": {
            "observed_agreement": observed_agreement(pairs_own),
            "n_agree": sum(1 for a, b in pairs_own if a == b),
            "krippendorff_alpha": krippendorff_alpha_nominal(units_own),
            "agreed_true": sum(1 for a, b in pairs_own if a and b),
            "agreed_false": sum(1 for a, b in pairs_own if (not a) and (not b)),
        },
        "controls": {
            "n_controls": len(ckey), "n_judgements": sum(ctrl_total.values()),
            "accuracy": sum(ctrl_right.values()) / max(1, sum(ctrl_total.values())),
            "accuracy_wilson": wilson(sum(ctrl_right.values()), sum(ctrl_total.values())),
            "by_class": {c: {"right": ctrl_right[c], "total": ctrl_total[c]} for c in CLASSES},
            "confusion": {f"{k[0]}->{k[1]}": v for k, v in sorted(ctrl_conf.items())},
        },
        "era_cue": {"n_sentences": n_era, "share": n_era / n if n else None,
                    "agreement_with_cue": observed_agreement(era_pairs),
                    "agreement_without": observed_agreement(plain_pairs)},
        "name_leak": {"n_sentences": n_leak, "share": n_leak / n if n else None,
                      "agreement_with_leak": observed_agreement(leak_pairs),
                      "agreement_without": observed_agreement(noleak_pairs)},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w"), indent=1)
    json.dump(labels, open(LABELS, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "class"}, indent=1)[:1500])
    print("class agreement:", res["class"]["observed_agreement"], "alpha:", res["class"]["krippendorff_alpha"])
    print("disagreement pairs:", res["class"]["disagreement_pairs"])


if __name__ == "__main__":
    main()
