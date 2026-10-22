"""Second-revision analyses, added after an independent referee-style review.

Everything here is computed from files already committed: the labels, the
sentences, the phrase-reuse counts, the calibration and the downloaded 10-K
documents. None of it was preregistered, and the paper labels it exploratory.

  R1  mean AI sentences per filing by class and era (the dilution question)
  R2  decomposition of the added volume by class
  R3  a stricter, "substantive" own-use indicator that ignores own-use carried
      only by risk-class or boilerplate-flagged sentences, and the
      mention-to-assertion ratio on both definitions
  R4  the filing-level own-use rate conditional on the number of AI sentences
  R5  per-sentence calibration error propagated to the filing level by
      simulation
  R6  effective year weights inside each era
  R7  where in the 10-K each AI sentence sits (Item 1, 1A, 1C, 7, other)
  R8  within-firm year-over-year reuse for registrants drawn in more than one year
  R9  a design-weighted logit of risk class on a post-2023 indicator

Writes results/revision2.json.
"""
from __future__ import annotations
import json, os, re, sys
from collections import Counter, defaultdict
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import (load, Vec, boot_idx, mean_boot, YEARS, ERAS, CLASSES, CI,  # noqa: E402
                     FLAG_K, SEED, R, D, era_of)
from fetch_and_extract import to_text, sentences  # noqa: E402

REPS = int(os.environ.get("BOOT_REPS", "10000"))
BASIS = ("class_majority", "own_majority")


def wmean_ci(vals, w, years, reps, seed, mask=None):
    mask = np.ones(len(vals), bool) if mask is None else mask
    idx = boot_idx(years, reps, seed)
    return mean_boot(np.asarray(vals, float), mask, idx, np.asarray(w, float))


# ------------------------------------------------------------- R7 item tags
HEAD_RE = re.compile(r"\b(?:ITEM|Item)\s*(\d{1,2}[A-C]?)\s*[\.\:\-]\s*(?=\(?[A-Z\[])")
XREF_BEFORE = re.compile(r"(?:\bin|\bsee|\bunder|\bof|\band|\bto|\bthis|\bour|Part\s+[IV]+,|described|discussed|refer|\bor|\bthe|,)\s*\"?\s*$", re.I)


def item_of_label(code):
    code = code.upper()
    return {"1": "Item 1 Business", "1A": "Item 1A Risk factors", "1C": "Item 1C Cybersecurity",
            "7": "Item 7 MD&A", "7A": "Item 7 MD&A"}.get(code, "Other items")


def headings(text):
    out = []
    for m in HEAD_RE.finditer(text):
        before = text[max(0, m.start() - 30):m.start()]
        if XREF_BEFORE.search(before):
            continue
        out.append((m.start(), item_of_label(m.group(1))))
    return out


def tag_items(filings_json):
    raw_dir = D("filings")
    out, cover = {}, Counter()
    for f in filings_json:
        path = os.path.join(raw_dir, f"{f['adsh']}_{f['doc']}"[:180])
        if not os.path.exists(path):
            cover["missing_doc"] += len(f["ai_sentences"]); continue
        text = to_text(open(path, "rb").read())
        sents = sentences(text)
        heads = headings(text)
        pos, cur = [], 0
        for s_ in sents:
            k = text.find(s_, cur)
            pos.append(k if k >= 0 else cur)
            if k >= 0:
                cur = k + len(s_)
        hp = [h[0] for h in heads]
        import bisect
        for s in f["ai_sentences"]:
            j = s["idx"]
            if j < len(sents) and sents[j] == s["text"]:
                i = bisect.bisect_right(hp, pos[j]) - 1
                out[s["id"]] = heads[i][1] if i >= 0 else "Front matter"; cover["tagged"] += 1
            else:
                cover["index_mismatch"] += 1
    return out, dict(cover)


# ------------------------------------------------------------- main
def main():
    frame, den, sents, filings, agree, calib = load()
    frame_sizes = {y: frame["years"][str(y)]["registrants_main_10k"] for y in YEARS}
    V = Vec(filings, frame_sizes)
    n_samp = Counter(V.year.tolist())
    res = {"note": "exploratory analyses added in the second revision, not preregistered", "reps": REPS}
    ck, ok = BASIS
    has = V.has_rows

    # ---- R6 effective year weights inside each era (share of the era's design weight)
    r6 = {}
    for e, rng in ERAS.items():
        tot = sum(frame_sizes[y] for y in rng)
        r6[e] = {str(y): frame_sizes[y] / tot for y in rng}
    res["R6_year_weights_within_era"] = r6

    # ---- R1 mean sentences per filing by class and era (AI-mentioning filings with >=1 sentence)
    cnt = np.zeros((V.n, 5)); tot = np.zeros(V.n); undecided = np.zeros(V.n)
    for i, f in enumerate(filings):
        for r in f["rows"]:
            tot[i] += 1
            c = r[ck]
            if c is None:
                undecided[i] += 1
            else:
                cnt[i, CI[c]] += 1
    r1 = {}
    for k, (e, rng) in enumerate(ERAS.items()):
        sel = np.where((V.era == e))[0]
        row = {}
        for c in CLASSES:
            row[c] = wmean_ci(cnt[sel, CI[c]], V.w[sel], V.year[sel], REPS, SEED + 10 * k + CI[c])
        row["all"] = wmean_ci(tot[sel], V.w[sel], V.year[sel], REPS, SEED + 10 * k + 7)
        r1[e] = row
    res["R1_mean_sentences_per_filing"] = r1

    # ---- R2 decomposition of the added volume, late era minus early era
    early, late = r1["2015-2019"], r1["2024-2026"]
    added = late["all"]["estimate"] - early["all"]["estimate"]
    res["R2_added_volume"] = {"added_total": added,
                              **{c: {"added": late[c]["estimate"] - early[c]["estimate"],
                                     "share_of_added": (late[c]["estimate"] - early[c]["estimate"]) / added}
                                 for c in CLASSES},
                              "capability_ratio_late_to_early": late["capability"]["estimate"] / early["capability"]["estimate"]}

    # ---- R3 substantive own-use: own-use sentence that is not risk class and not flagged as reused
    any_own = np.zeros(V.n, bool); any_sub = np.zeros(V.n, bool); only_risk = np.zeros(V.n, bool)
    for i, f in enumerate(filings):
        own_rows = [r for r in f["rows"] if r[ok] is True]
        any_own[i] = bool(own_rows)
        sub = [r for r in own_rows if r[ck] != "risk" and not (r["reuse_ciks"] is not None and r["reuse_ciks"] >= FLAG_K)]
        any_sub[i] = bool(sub)
        only_risk[i] = bool(own_rows) and all(r[ck] == "risk" for r in own_rows)
    r3 = {"definition": "a filing counts if at least one sentence is coded own-use (majority of three) and that "
                        "sentence is not risk-factor class and is not shared verbatim with five or more other registrants"}
    for k, (e, rng) in enumerate(ERAS.items()):
        sel = np.where((V.era == e) & has)[0]
        a = wmean_ci(any_own[sel], V.w[sel], V.year[sel], REPS, SEED + 100 + k)
        s = wmean_ci(any_sub[sel], V.w[sel], V.year[sel], REPS, SEED + 100 + k)
        o = wmean_ci(only_risk[sel], V.w[sel], V.year[sel], REPS, SEED + 100 + k)
        r3[e] = {"own_use_any": a, "substantive_own_use_any": s, "own_use_only_in_risk_sentences": o,
                 "ratio_any": 1 / a["estimate"], "ratio_substantive": 1 / s["estimate"],
                 "ratio_any_interval": [1 / a["hi"], 1 / a["lo"]],
                 "ratio_substantive_interval": [1 / s["hi"], 1 / s["lo"]]}
    # contrast late minus early, substantive
    se, sl = np.where((V.era == "2015-2019") & has)[0], np.where((V.era == "2024-2026") & has)[0]
    ia, ib = boot_idx(V.year[sl], REPS, SEED + 150), boot_idx(V.year[se], REPS, SEED + 151)
    def wm(vals, sel, idx):
        w = V.w[sel]; v = vals[sel].astype(float)
        return (w * v)[idx].sum(1) / w[idx].sum(1)
    d = wm(any_sub, sl, ia) - wm(any_sub, se, ib)
    r3["substantive_late_minus_early"] = {"estimate": r3["2024-2026"]["substantive_own_use_any"]["estimate"] - r3["2015-2019"]["substantive_own_use_any"]["estimate"],
                                          "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5))}
    # by year
    r3["by_year"] = {}
    for y in YEARS:
        sel = np.where((V.year == y) & has)[0]
        if len(sel):
            r3["by_year"][str(y)] = {"n": int(len(sel)), "own_use_any": float(any_own[sel].mean()),
                                     "substantive_own_use_any": float(any_sub[sel].mean())}
    res["R3_substantive_own_use"] = r3

    # ---- R4 own-use rate conditional on the number of AI sentences (pooled terciles)
    sel = np.where(has)[0]
    q = np.quantile(tot[sel], [1 / 3, 2 / 3])
    bins = [("1 to %d" % q[0], tot <= q[0]), ("%d to %d" % (q[0] + 1, q[1]), (tot > q[0]) & (tot <= q[1])),
            ("more than %d" % q[1], tot > q[1])]
    r4 = {"tercile_cuts": [float(x) for x in q], "cells": {}}
    for name, m in bins:
        r4["cells"][name] = {}
        for e in ERAS:
            s_ = np.where(m & has & (V.era == e))[0]
            if len(s_) >= 5:
                w = V.w[s_]
                r4["cells"][name][e] = {"n": int(len(s_)),
                                        "own_use_any": float((w * any_own[s_]).sum() / w.sum()),
                                        "substantive_own_use_any": float((w * any_sub[s_]).sum() / w.sum())}
            else:
                r4["cells"][name][e] = {"n": int(len(s_))}
    # per-sentence own-use rate by era (design weighted ratio)
    own_n = np.array([sum(1 for r in f["rows"] if r[ok] is not None) for f in filings], float)
    own_t = np.array([sum(1 for r in f["rows"] if r[ok] is True) for f in filings], float)
    r4["per_sentence_own_use"] = {e: float((V.w * own_t)[V.era == e].sum() / (V.w * own_n)[V.era == e].sum()) for e in ERAS}
    # weighted logit of any own-use on log sentences plus era dummies
    import statsmodels.api as sm
    X = np.column_stack([np.ones(len(sel)), np.log(tot[sel]),
                         (V.era[sel] == "2020-2023").astype(float), (V.era[sel] == "2024-2026").astype(float)])
    wts = V.w[sel] / V.w[sel].mean()
    try:
        mdl = sm.GLM(any_own[sel].astype(float), X, family=sm.families.Binomial(), freq_weights=wts).fit(
            cov_type="cluster", cov_kwds={"groups": np.array([filings[i]["cik"] for i in sel])})
        r4["logit_any_own"] = {"terms": ["const", "log_ai_sentences", "era_2020_2023", "era_2024_2026"],
                               "coef": mdl.params.tolist(), "se": mdl.bse.tolist(), "p": mdl.pvalues.tolist()}
    except Exception as ex:  # pragma: no cover
        r4["logit_any_own"] = {"error": str(ex)}
    res["R4_length_adjustment"] = r4

    # ---- R5 calibration error propagated to filing level by simulation
    ou = calib["own_use"] if "own_use" in calib else None
    rng_ = np.random.default_rng(SEED + 500)
    sims = 4000
    r5 = {"method": "each own-use=True sentence stays True with probability p, each False becomes True with "
                    "probability q, with p and q drawn from Beta posteriors fitted to the blinded calibration "
                    "(true survived %d of %d, false survived %d of %d); filing-level fractions recomputed per draw "
                    "with design weights" % (ou["true_survived"], ou["true_n"], ou["false_survived"], ou["false_n"]),
          "sims": sims}
    rows_own = [np.array([1 if r[ok] is True else 0 for r in f["rows"] if r[ok] is not None], int) for f in filings]
    out_e = {e: [] for e in ERAS}
    for _ in range(sims):
        p = rng_.beta(ou["true_survived"] + 1, ou["true_n"] - ou["true_survived"] + 1)
        qf = 1 - rng_.beta(ou["false_survived"] + 1, ou["false_n"] - ou["false_survived"] + 1)
        flag = np.zeros(V.n, bool)
        for i, ro in enumerate(rows_own):
            if len(ro) == 0:
                continue
            u = rng_.random(len(ro))
            flag[i] = bool(np.any(np.where(ro == 1, u < p, u < qf)))
        for e in ERAS:
            s_ = np.where((V.era == e) & has)[0]
            out_e[e].append(float((V.w[s_] * flag[s_]).sum() / V.w[s_].sum()))
    for e in ERAS:
        a = np.array(out_e[e])
        r5[e] = {"mean": float(a.mean()), "lo": float(np.percentile(a, 2.5)), "hi": float(np.percentile(a, 97.5))}
    res["R5_calibration_propagated_filing_level"] = r5

    # ---- R7 item location
    tags, cover = tag_items(sents["filings"])
    r7 = {"coverage": cover, "by_era": {}}
    for e in ERAS:
        c = Counter(); cc = defaultdict(Counter)
        for f in filings:
            if f["era"] != e:
                continue
            w = frame_sizes[f["year"]] / n_samp[f["year"]]
            for r in f["rows"]:
                it = tags.get(r["sid"])
                if it is None or r[ck] is None:
                    continue
                c[it] += w; cc[it][r[ck]] += w
        T = sum(c.values())
        r7["by_era"][e] = {it: {"share_of_ai_sentences": c[it] / T,
                                "risk_share_within_item": cc[it]["risk"] / c[it] if c[it] else None,
                                "capability_share_within_item": cc[it]["capability"] / c[it] if c[it] else None}
                           for it in sorted(c)}
    # where risk sentences sit, late era
    res["R7_item_location"] = r7

    # ---- R8 within-firm reuse across sampled years
    def grams(t, n=8):
        w = re.findall(r"[a-z0-9]+", t.lower())
        return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}
    by_cik = defaultdict(list)
    for f in filings:
        by_cik[f["cik"]].append(f)
    pairs, carried, total_later = [], 0, 0
    for cik, fs in by_cik.items():
        fs = sorted(fs, key=lambda x: x["year"])
        for a, b in zip(fs, fs[1:]):
            if not a["rows"] or not b["rows"]:
                continue
            prev = set().union(*[grams(r["text"]) for r in a["rows"]])
            k = 0
            for r in b["rows"]:
                g = grams(r["text"])
                if g and len(g & prev) / len(g) >= 0.5:
                    k += 1
            pairs.append({"cik": cik, "years": [a["year"], b["year"]], "later_sentences": len(b["rows"]), "carried": k})
            carried += k; total_later += len(b["rows"])
    res["R8_within_firm_reuse"] = {"rule": "a later-year AI sentence counts as carried over when at least half of its "
                                           "eight-word sequences appear in the same registrant's AI sentences in its earlier sampled filing",
                                   "pairs": len(pairs), "later_sentences": total_later, "carried": carried,
                                   "share_carried": carried / total_later if total_later else None,
                                   "median_gap_years": float(np.median([p["years"][1] - p["years"][0] for p in pairs])) if pairs else None}

    # ---- R9 design-weighted logit of risk class on a post-2023 indicator, clustered by registrant
    import statsmodels.api as sm
    yv, xv, wv, gv = [], [], [], []
    for f in filings:
        w = frame_sizes[f["year"]] / n_samp[f["year"]]
        nr = sum(1 for r in f["rows"] if r[ck] is not None)
        for r in f["rows"]:
            if r[ck] is None:
                continue
            yv.append(r[ck] == "risk"); xv.append([1.0, float(f["year"] >= 2024), float(2020 <= f["year"] <= 2023)])
            wv.append(w / nr); gv.append(f["cik"])  # each filing weighted equally within year
    wv = np.array(wv); wv = wv / wv.mean()
    m9 = sm.GLM(np.array(yv, float), np.array(xv), family=sm.families.Binomial(), freq_weights=wv).fit(
        cov_type="cluster", cov_kwds={"groups": np.array(gv)})
    res["R9_logit_risk_post2023"] = {"terms": ["const", "filed_2024_or_later", "filed_2020_to_2023"],
                                     "coef": m9.params.tolist(), "se": m9.bse.tolist(), "p": m9.pvalues.tolist(),
                                     "odds_ratio_post2023": float(np.exp(m9.params[1])),
                                     "note": "sentence-level, each filing weighted equally within year and years weighted to the frame, standard errors clustered by registrant"}

    json.dump(res, open(R("revision2.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k in ("R2_added_volume", "R8_within_firm_reuse")}, indent=1))
    for e in ERAS:
        print(e, "R1 cap", round(r1[e]["capability"]["estimate"], 2), "risk", round(r1[e]["risk"]["estimate"], 2),
              "all", round(r1[e]["all"]["estimate"], 2), "| R3 any", round(r3[e]["own_use_any"]["estimate"], 3),
              "sub", round(r3[e]["substantive_own_use_any"]["estimate"], 3), "onlyrisk", round(r3[e]["own_use_only_in_risk_sentences"]["estimate"], 3),
              "| R5", round(r5[e]["mean"], 3))
    print("R7 coverage", cover)
    for e in ERAS:
        print(e, {k: round(v["share_of_ai_sentences"], 3) for k, v in r7["by_era"][e].items()})
    print("R4", json.dumps(r4["cells"]), r4["per_sentence_own_use"])
    print("R4 logit", r4.get("logit_any_own"))
    print("R9", res["R9_logit_risk_post2023"]["odds_ratio_post2023"], res["R9_logit_risk_post2023"]["p"])


if __name__ == "__main__":
    main()
