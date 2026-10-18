"""Every number in the paper, computed from the committed data.

Inputs: data/frame.json, data/denominators.json, data/sentences.json (with the
term-audit flags), data/rating/labels.json (two blind passes, third pass and
majority labels), data/phrase_reuse.json, results/agreement.json and, when
present, results/calibration.json. Output: results/analysis.json.

Conventions. Sentence-level composition is reported on two bases: "agreed"
(both blind passes gave the class; the disputed set is shown as a bound) and
"majority" (majority of three). Each basis is reported with two weightings:
"sentence" (every corpus sentence counts once) and "filing" (every filing
counts once, using its within-filing shares), the second because one 2023
registrant contributes a sixth of the corpus. Uncertainty is a percentile
bootstrap over filings, 10,000 replicates, seed 20261018.
"""
from __future__ import annotations
import json, os, sys
from collections import Counter, defaultdict
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))
from stats import wilson, cluster_bootstrap  # noqa: E402

D = lambda *p: os.path.join(BASE, "data", *p)
R = lambda *p: os.path.join(BASE, "results", *p)
CLASSES = ["capability", "risk", "market", "governance", "other"]
ERAS = {"2015-2019": range(2015, 2020), "2020-2023": range(2020, 2024), "2024-2026": range(2024, 2027)}
REPS = int(os.environ.get("BOOT_REPS", "10000"))
SEED = 20261018
FLAG_K = 5


def era_of(y):
    for e, rng in ERAS.items():
        if y in rng:
            return e
    return None


def load():
    frame = json.load(open(D("frame.json")))
    den = json.load(open(D("denominators.json")))
    sents = json.load(open(D("sentences.json")))
    labels = json.load(open(D("rating", "labels.json")))
    reuse = json.load(open(D("phrase_reuse.json"))) if os.path.exists(D("phrase_reuse.json")) else {}
    agree = json.load(open(R("agreement.json")))
    calib = json.load(open(R("calibration.json"))) if os.path.exists(R("calibration.json")) else None
    by_sid = {l["sid"]: l for l in labels.values()}
    filings = []
    for f in sents["filings"]:
        rows = []
        for s in f["ai_sentences"]:
            if s.get("non_ai"):
                continue
            l = by_sid.get(s["id"])
            if l is None:
                continue
            rr = reuse.get(s["id"], {})
            rows.append({"sid": s["id"], "text": s["text"], "patterns": s["patterns"],
                         "class_agreed": l["class_agreed"], "disputed": l["disputed"],
                         "class_a": l["class_a"], "class_b": l["class_b"],
                         "class_majority": l.get("class_majority", l["class_agreed"]),
                         "own_agreed": l["own_agreed"], "own_disputed": l["own_disputed"],
                         "own_majority": l.get("own_majority", l["own_agreed"]),
                         "reuse_ciks": rr.get("reuse_ciks"), "total_hits": rr.get("total_hits"),
                         "self_hit": rr.get("self_hit"), "ciks_censored": rr.get("ciks_censored"),
                         "reuse_error": "error" in rr})
        filings.append({"adsh": f["adsh"], "cik": f["cik"], "name": f["name"], "year": f["year"],
                        "era": era_of(f["year"]), "sector": f["sector"], "sic": f["sic"],
                        "n_extracted": f["n_ai"], "rows": rows})
    return frame, den, sents, filings, agree, calib


# ---------------------------------------------------------------- composition
def comp_sentence(fs, basis, cls):
    """share of sentences in class cls on the given basis (ignores undecided)."""
    key = "class_agreed" if basis == "agreed" else "class_majority"
    rows = [r for f in fs for r in f["rows"] if r[key] is not None]
    return sum(1 for r in rows if r[key] == cls) / len(rows) if rows else np.nan


def comp_filing(fs, basis, cls):
    key = "class_agreed" if basis == "agreed" else "class_majority"
    vals = []
    for f in fs:
        rows = [r for r in f["rows"] if r[key] is not None]
        if rows:
            vals.append(sum(1 for r in rows if r[key] == cls) / len(rows))
    return float(np.mean(vals)) if vals else np.nan


def own_sentence(fs, basis):
    key = "own_agreed" if basis == "agreed" else "own_majority"
    rows = [r for f in fs for r in f["rows"] if r[key] is not None]
    return sum(1 for r in rows if r[key]) / len(rows) if rows else np.nan


def own_filing(fs, basis):
    key = "own_agreed" if basis == "agreed" else "own_majority"
    vals = []
    for f in fs:
        rows = [r for r in f["rows"] if r[key] is not None]
        if rows:
            vals.append(sum(1 for r in rows if r[key]) / len(rows))
    return float(np.mean(vals)) if vals else np.nan


def any_flag(fs, key, value=True, cls=None):
    """share of filings (with at least one corpus sentence) having at least one
    sentence with rows[key] == value (or class == cls)."""
    n = k = 0
    for f in fs:
        if not f["rows"]:
            continue
        n += 1
        if cls is not None:
            k += any(r[key] == cls for r in f["rows"])
        else:
            k += any(r[key] is value for r in f["rows"])
    return k / n if n else np.nan


def boot(fs, fn, reps=REPS):
    pt, lo, hi, _ = cluster_bootstrap(fs, fn, reps=reps, seed=SEED)
    return {"estimate": float(pt), "lo": float(lo), "hi": float(hi)}


def boot_diff(fa, fb, fn, reps=REPS):
    """bootstrap of fn(A) - fn(B), resampling A and B independently."""
    rng = np.random.default_rng(SEED)
    a, b = np.arange(len(fa)), np.arange(len(fb))
    draws = np.empty(reps)
    for r in range(reps):
        ia = rng.choice(a, len(a), replace=True)
        ib = rng.choice(b, len(b), replace=True)
        draws[r] = fn([fa[i] for i in ia]) - fn([fb[i] for i in ib])
    return {"estimate": float(fn(fa) - fn(fb)), "lo": float(np.nanpercentile(draws, 2.5)),
            "hi": float(np.nanpercentile(draws, 97.5)),
            "share_positive": float(np.nanmean(draws > 0))}


def main():
    frame, den, sents, filings, agree, calib = load()
    out = {"seed": SEED, "reps": REPS}

    # ---- universe
    uni = {}
    for y in range(2015, 2027):
        fy = frame["years"][str(y)]
        n = den["years"][str(y)]["total_10k"]
        uni[str(y)] = {"hits": fy["reported_total_hits"], "filings_any_doc": fy["filings_any_doc"],
                       "frame": fy["filings_main_10k"], "registrants": fy["registrants_main_10k"],
                       "all_10k": n, "raw_share": fy["filings_main_10k"] / n}
    out["universe"] = uni
    out["raw_share_growth"] = uni["2025"]["raw_share"] / uni["2015"]["raw_share"]

    # ---- corpus
    n_extracted = sum(f["n_extracted"] for f in filings)
    n_removed = sents["term_audit"]["removed"]
    n_corpus = sum(len(f["rows"]) for f in filings)
    per_f = sorted(len(f["rows"]) for f in filings)
    out["corpus"] = {
        "filings": len(filings), "registrants": len({f["cik"] for f in filings}),
        "extracted": n_extracted, "removed_non_ai": n_removed,
        "term_audit": sents["term_audit"], "sentences": n_corpus,
        "filings_with_sentences": sum(1 for n in per_f if n),
        "filings_zero_after_audit": sum(1 for n in per_f if n == 0),
        "median_per_filing": per_f[len(per_f) // 2], "max_per_filing": per_f[-1],
        "largest_filer_share": max(per_f) / n_corpus,
        "largest_filer": max(filings, key=lambda f: len(f["rows"]))["name"],
        "by_year": {str(y): {"filings": sum(1 for f in filings if f["year"] == y),
                             "sentences": sum(len(f["rows"]) for f in filings if f["year"] == y)}
                    for y in range(2015, 2027)},
        "by_sector": dict(Counter(f["sector"] for f in filings)),
        "pattern_counts": dict(Counter(p for f in filings for r in f["rows"] for p in r["patterns"])),
    }
    n_disp = sum(1 for f in filings for r in f["rows"] if r["disputed"])
    n_und = sum(1 for f in filings for r in f["rows"] if r["class_majority"] is None)
    out["corpus"]["disputed_class"] = n_disp
    out["corpus"]["unresolved_after_third"] = n_und
    out["corpus"]["disputed_own"] = sum(1 for f in filings for r in f["rows"] if r["own_disputed"])
    out["agreement"] = agree

    # ---- composition: overall, by era, by year
    comp = {}
    for basis in ("agreed", "majority"):
        comp[basis] = {}
        for weighting, fn_c, fn_o in (("sentence", comp_sentence, own_sentence),
                                      ("filing", comp_filing, own_filing)):
            block = {"overall": {}, "era": {}, "year": {}}
            for cls in CLASSES:
                block["overall"][cls] = boot(filings, lambda fs, c=cls: fn_c(fs, basis, c))
            block["overall"]["own_use"] = boot(filings, lambda fs: fn_o(fs, basis))
            for e in ERAS:
                fe = [f for f in filings if f["era"] == e]
                block["era"][e] = {cls: boot(fe, lambda fs, c=cls: fn_c(fs, basis, c)) for cls in CLASSES}
                block["era"][e]["own_use"] = boot(fe, lambda fs: fn_o(fs, basis))
                block["era"][e]["n_filings"] = len(fe)
                block["era"][e]["n_sentences"] = sum(len(f["rows"]) for f in fe)
            for y in range(2015, 2027):
                fy = [f for f in filings if f["year"] == y]
                block["year"][str(y)] = {cls: boot(fy, lambda fs, c=cls: fn_c(fs, basis, c), reps=2000)
                                         for cls in CLASSES}
                block["year"][str(y)]["own_use"] = boot(fy, lambda fs: fn_o(fs, basis), reps=2000)
            comp[basis][weighting] = block
    # disputed bound on the agreed basis (sentence weighting): class share if all
    # disputed sentences involving that class were assigned to it, and if none were
    rows_all = [r for f in filings for r in f["rows"]]
    n_all = len(rows_all)
    bound = {}
    for cls in CLASSES:
        lo = sum(1 for r in rows_all if r["class_agreed"] == cls) / n_all
        hi = sum(1 for r in rows_all if r["class_agreed"] == cls or
                 (r["disputed"] and cls in (r["class_a"], r["class_b"]))) / n_all
        bound[cls] = {"lo": lo, "hi": hi}
    comp["agreed"]["sentence"]["disputed_bound_overall"] = bound
    comp["agreed_counts_overall"] = dict(Counter(r["class_agreed"] for r in rows_all if r["class_agreed"]))
    comp["majority_counts_overall"] = dict(Counter(r["class_majority"] for r in rows_all if r["class_majority"]))
    out["composition"] = comp

    # ---- era contrasts (predictions 1, 2)
    fA = [f for f in filings if f["era"] == "2015-2019"]
    fC = [f for f in filings if f["era"] == "2024-2026"]
    contrasts = {}
    for basis in ("agreed", "majority"):
        contrasts[basis] = {}
        for weighting, fn_c, fn_o in (("sentence", comp_sentence, own_sentence), ("filing", comp_filing, own_filing)):
            contrasts[basis][weighting] = {
                "risk_late_minus_early": boot_diff(fC, fA, lambda fs: fn_c(fs, basis, "risk")),
                "capability_late_minus_early": boot_diff(fC, fA, lambda fs: fn_c(fs, basis, "capability")),
                "own_use_late_minus_early": boot_diff(fC, fA, lambda fs: fn_o(fs, basis)),
            }
    out["era_contrasts"] = contrasts

    # ---- filing-level own-use / capability presence, corrected adoption trend
    fl = {}
    for basis in ("agreed", "majority"):
        okey = "own_agreed" if basis == "agreed" else "own_majority"
        ckey = "class_agreed" if basis == "agreed" else "class_majority"
        fl[basis] = {"year": {}, "era": {}, "overall": {}}
        fl[basis]["overall"]["own_use_any"] = boot(filings, lambda fs: any_flag(fs, okey))
        fl[basis]["overall"]["capability_any"] = boot(filings, lambda fs: any_flag(fs, ckey, cls="capability"))
        for e in ERAS:
            fe = [f for f in filings if f["era"] == e]
            fl[basis]["era"][e] = {"own_use_any": boot(fe, lambda fs: any_flag(fs, okey)),
                                   "capability_any": boot(fe, lambda fs: any_flag(fs, ckey, cls="capability")),
                                   "n_filings": sum(1 for f in fe if f["rows"])}
        for y in range(2015, 2027):
            fy = [f for f in filings if f["year"] == y]
            n_f = sum(1 for f in fy if f["rows"])
            k_o = sum(1 for f in fy if f["rows"] and any(r[okey] is True for r in f["rows"]))
            k_c = sum(1 for f in fy if f["rows"] and any(r[ckey] == "capability" for r in f["rows"]))
            bo = boot(fy, lambda fs: any_flag(fs, okey), reps=2000)
            bc = boot(fy, lambda fs: any_flag(fs, ckey, cls="capability"), reps=2000)
            raw = uni[str(y)]["raw_share"]
            fl[basis]["year"][str(y)] = {
                "n_filings": n_f, "own_use_any_k": k_o, "capability_any_k": k_c,
                "own_use_any": {**bo, "wilson": wilson(k_o, n_f)},
                "capability_any": {**bc, "wilson": wilson(k_c, n_f)},
                "raw_share": raw,
                "corrected_own_use": {"estimate": raw * bo["estimate"], "lo": raw * bo["lo"], "hi": raw * bo["hi"]},
                "corrected_capability": {"estimate": raw * bc["estimate"], "lo": raw * bc["lo"], "hi": raw * bc["hi"]},
                "overstatement_factor": (1 / bo["estimate"]) if bo["estimate"] else None,
            }
        # era-level overstatement: pooled filings in era, raw share pooled over era years
        for e, rng in ERAS.items():
            fr = sum(uni[str(y)]["frame"] for y in rng)
            al = sum(uni[str(y)]["all_10k"] for y in rng)
            p = fl[basis]["era"][e]["own_use_any"]
            fl[basis]["era"][e]["raw_share_pooled"] = fr / al
            fl[basis]["era"][e]["corrected_own_use_pooled"] = {"estimate": fr / al * p["estimate"],
                                                               "lo": fr / al * p["lo"], "hi": fr / al * p["hi"]}
            fl[basis]["era"][e]["overstatement_factor"] = 1 / p["estimate"] if p["estimate"] else None
            fl[basis]["era"][e]["overstatement_factor_interval"] = [1 / p["hi"] if p["hi"] else None,
                                                                    1 / p["lo"] if p["lo"] else None]
        fl[basis]["overstatement_late_minus_early"] = boot_diff(
            fC, fA, lambda fs: 1 / any_flag(fs, okey) if any_flag(fs, okey) else np.nan)
        fl[basis]["own_any_late_minus_early"] = boot_diff(fC, fA, lambda fs: any_flag(fs, okey))
    out["filing_level"] = fl

    # ---- trend tests
    from scipy.stats import spearmanr
    trend = {}
    for basis in ("agreed", "majority"):
        okey = "own_agreed" if basis == "agreed" else "own_majority"
        ckey = "class_agreed" if basis == "agreed" else "class_majority"
        ys = list(range(2015, 2027))
        own_y = [fl[basis]["year"][str(y)]["own_use_any"]["estimate"] for y in ys]
        risk_y = [comp[basis]["filing"]["year"][str(y)]["risk"]["estimate"] for y in ys]
        owns_y = [comp[basis]["filing"]["year"][str(y)]["own_use"]["estimate"] for y in ys]
        rho_o, p_o = spearmanr(ys, own_y)
        rho_r, p_r = spearmanr(ys, risk_y)
        rho_s, p_s = spearmanr(ys, owns_y)
        trend[basis] = {"spearman_year_vs_filing_own_any": {"rho": float(rho_o), "p": float(p_o)},
                        "spearman_year_vs_risk_share_filingweighted": {"rho": float(rho_r), "p": float(p_r)},
                        "spearman_year_vs_own_share_filingweighted": {"rho": float(rho_s), "p": float(p_s)}}
        # sentence-level logistic regression, SE clustered by filing
        try:
            import statsmodels.api as sm
            yv, xv, gv = [], [], []
            for i, f in enumerate(filings):
                for r in f["rows"]:
                    if r[okey] is None:
                        continue
                    yv.append(1 if r[okey] else 0); xv.append(f["year"] - 2015); gv.append(i)
            X = sm.add_constant(np.array(xv, dtype=float))
            m = sm.Logit(np.array(yv), X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": np.array(gv)})
            trend[basis]["logit_own_use_on_year"] = {"coef_per_year": float(m.params[1]),
                                                     "se_cluster": float(m.bse[1]), "p": float(m.pvalues[1]),
                                                     "odds_ratio_per_year": float(np.exp(m.params[1])),
                                                     "n": len(yv)}
            yv, xv, gv = [], [], []
            for i, f in enumerate(filings):
                for r in f["rows"]:
                    if r[ckey] is None:
                        continue
                    yv.append(1 if r[ckey] == "risk" else 0); xv.append(f["year"] - 2015); gv.append(i)
            X = sm.add_constant(np.array(xv, dtype=float))
            m = sm.Logit(np.array(yv), X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": np.array(gv)})
            trend[basis]["logit_risk_on_year"] = {"coef_per_year": float(m.params[1]),
                                                  "se_cluster": float(m.bse[1]), "p": float(m.pvalues[1]),
                                                  "odds_ratio_per_year": float(np.exp(m.params[1])), "n": len(yv)}
        except Exception as e:
            trend[basis]["logit_error"] = str(e)
    out["trend"] = trend

    # ---- phrase reuse
    pr = {}
    rows_r = [r for f in filings for r in f["rows"] if not r["reuse_error"] and r["reuse_ciks"] is not None]
    pr["n_queried"] = sum(1 for f in filings for r in f["rows"] if r["total_hits"] is not None or r["reuse_error"])
    pr["n_errors"] = sum(1 for f in filings for r in f["rows"] if r["reuse_error"])
    pr["n_zero_hits"] = sum(1 for r in rows_r if r["total_hits"] == 0)
    pr["self_hit_rate"] = float(np.mean([bool(r["self_hit"]) for r in rows_r])) if rows_r else None
    pr["n_censored"] = sum(1 for r in rows_r if r["ciks_censored"])
    usable = [r for r in rows_r if r["total_hits"] and r["total_hits"] > 0]
    pr["n_usable"] = len(usable)
    for basis in ("agreed", "majority"):
        ckey = "class_agreed" if basis == "agreed" else "class_majority"
        okey = "own_agreed" if basis == "agreed" else "own_majority"
        byc = {}
        for cls in CLASSES:
            v = [r["reuse_ciks"] for r in usable if r[ckey] == cls]
            if v:
                byc[cls] = {"n": len(v), "median": float(np.median(v)), "mean": float(np.mean(v)),
                            "share_zero": float(np.mean([x == 0 for x in v])),
                            "share_flagged": float(np.mean([x >= FLAG_K for x in v])),
                            "q75": float(np.percentile(v, 75)), "q90": float(np.percentile(v, 90))}
        own_t = [r["reuse_ciks"] for r in usable if r[okey] is True]
        own_f = [r["reuse_ciks"] for r in usable if r[okey] is False]
        d = {"by_class": byc,
             "own_use_true": {"n": len(own_t), "median": float(np.median(own_t)) if own_t else None,
                              "share_flagged": float(np.mean([x >= FLAG_K for x in own_t])) if own_t else None},
             "own_use_false": {"n": len(own_f), "median": float(np.median(own_f)) if own_f else None,
                               "share_flagged": float(np.mean([x >= FLAG_K for x in own_f])) if own_f else None}}
        # classifier: flag (reuse >= k) predicts "not own use"
        y = np.array([0 if r[okey] else 1 for r in usable if r[okey] is not None])
        s = np.array([r["reuse_ciks"] for r in usable if r[okey] is not None], dtype=float)
        if len(y) and y.min() != y.max():
            from sklearn.metrics import roc_auc_score  # type: ignore
            auc = float(roc_auc_score(y, s))
        else:
            auc = None
        if auc is None and len(y):
            # rank-based AUC without sklearn
            pos, neg = s[y == 1], s[y == 0]
            if len(pos) and len(neg):
                auc = float((np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :])) / (len(pos) * len(neg)))
        d["auc_flag_predicts_not_own_use"] = auc
        thr = {}
        for k in (1, 2, 3, 5, 10, 20):
            pred = s >= k
            tp = int(np.sum(pred & (y == 1))); fp = int(np.sum(pred & (y == 0))); fn = int(np.sum((~pred) & (y == 1)))
            thr[str(k)] = {"precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
                           "flagged_share": float(np.mean(pred))}
        d["thresholds"] = thr
        # era trend of flagged share (sentence-weighted, bootstrapped by filing)
        def flagged_share(fs):
            v = [r["reuse_ciks"] >= FLAG_K for f in fs for r in f["rows"]
                 if not r["reuse_error"] and r["reuse_ciks"] is not None and r["total_hits"]]
            return float(np.mean(v)) if v else np.nan
        d["flagged_share_era"] = {e: boot([f for f in filings if f["era"] == e], flagged_share) for e in ERAS}
        d["flagged_share_late_minus_early"] = boot_diff(fC, fA, flagged_share)
        d["flagged_share_overall"] = boot(filings, flagged_share)
        pr[basis] = d
    out["phrase_reuse"] = pr

    # ---- sector
    sec = {}
    for basis in ("agreed", "majority"):
        okey = "own_agreed" if basis == "agreed" else "own_majority"
        ckey = "class_agreed" if basis == "agreed" else "class_majority"
        sec[basis] = {}
        for st in ("technology", "healthcare", "finance_realestate", "other"):
            fs = [f for f in filings if f["sector"] == st]
            sec[basis][st] = {"n_filings": len(fs), "n_sentences": sum(len(f["rows"]) for f in fs),
                              "own_use_any": boot(fs, lambda x: any_flag(x, okey)),
                              "own_use_share_filing": boot(fs, lambda x: own_filing(x, basis)),
                              "capability_share_filing": boot(fs, lambda x: comp_filing(x, basis, "capability")),
                              "risk_share_filing": boot(fs, lambda x: comp_filing(x, basis, "risk"))}
        tech = [f for f in filings if f["sector"] == "technology"]
        rest = [f for f in filings if f["sector"] != "technology"]
        sec[basis]["tech_minus_rest_own_any"] = boot_diff(tech, rest, lambda x: any_flag(x, okey))
        sec[basis]["tech_minus_rest_own_share"] = boot_diff(tech, rest, lambda x: own_filing(x, basis))
    # sector mix of the frame per era (from the enumeration, not the sample)
    from sample_filings import sector as sector_of
    mix = {}
    for e, rng in ERAS.items():
        c = Counter()
        for y in rng:
            for r in frame["years"][str(y)]["rows"]:
                if r["main_matched"] and not r["is_amendment"]:
                    c[sector_of(r["sic"])] += 1
        tot = sum(c.values())
        mix[e] = {k: v / tot for k, v in c.items()}
    sec["frame_sector_mix_by_era"] = mix
    out["sector"] = sec

    # ---- replication of the companion's 2025 composition
    f25 = [f for f in filings if f["year"] == 2025]
    out["replication_2025"] = {
        "n_filings": len(f25), "n_sentences": sum(len(f["rows"]) for f in f25),
        "risk_sentence_agreed": boot(f25, lambda fs: comp_sentence(fs, "agreed", "risk")),
        "capability_sentence_agreed": boot(f25, lambda fs: comp_sentence(fs, "agreed", "capability")),
        "risk_sentence_majority": boot(f25, lambda fs: comp_sentence(fs, "majority", "risk")),
        "capability_sentence_majority": boot(f25, lambda fs: comp_sentence(fs, "majority", "capability")),
        "companion": {"risk": 0.605, "capability": 0.122, "n_sentences": 598, "n_filings": 59},
    }

    # ---- predictions
    P = {}
    cs = contrasts["majority"]["filing"]
    P["1_risk_share_higher_late"] = {"holds_point": cs["risk_late_minus_early"]["estimate"] > 0,
                                     "interval_excludes_zero": cs["risk_late_minus_early"]["lo"] > 0,
                                     **cs["risk_late_minus_early"]}
    P["2_own_use_share_lower_late"] = {"holds_point": cs["own_use_late_minus_early"]["estimate"] < 0,
                                       "interval_excludes_zero": cs["own_use_late_minus_early"]["hi"] < 0,
                                       **cs["own_use_late_minus_early"]}
    late = fl["majority"]["era"]["2024-2026"]["own_use_any"]
    P["3_under_60pct_filings_own_use_late"] = {"holds_point": late["estimate"] < 0.60,
                                               "interval_below": late["hi"] < 0.60, **late}
    b = pr["majority"]["by_class"]
    if "risk" in b and "capability" in b:
        ratio = (b["risk"]["median"] / b["capability"]["median"]) if b["capability"]["median"] else float("inf")
        P["4_risk_reuse_vs_capability"] = {"median_risk": b["risk"]["median"], "median_capability": b["capability"]["median"],
                                           "median_ratio": ratio, "holds_median_3x": ratio >= 3,
                                           "flag_risk": b["risk"]["share_flagged"], "flag_capability": b["capability"]["share_flagged"],
                                           "holds_flag_2x": b["risk"]["share_flagged"] >= 2 * b["capability"]["share_flagged"]}
    fe = pr["majority"]["flagged_share_late_minus_early"]
    P["5_flagged_share_rises"] = {"holds_point": fe["estimate"] > 0, "interval_excludes_zero": fe["lo"] > 0, **fe}
    oe = fl["majority"]["overstatement_late_minus_early"]
    P["6_overstatement_grows"] = {"holds_point": oe["estimate"] > 0, "interval_excludes_zero": oe["lo"] > 0, **oe,
                                  "early": fl["majority"]["era"]["2015-2019"]["overstatement_factor"],
                                  "late": fl["majority"]["era"]["2024-2026"]["overstatement_factor"]}
    td = sec["majority"]["tech_minus_rest_own_any"]
    P["7_tech_higher_own_use"] = {"holds_point": td["estimate"] > 0, "interval_excludes_zero": td["lo"] > 0, **td}
    # falsification condition: stable composition and no growth in overstatement
    rd = contrasts["majority"]["filing"]["risk_late_minus_early"]["estimate"]
    P["falsification_triggered"] = bool(abs(rd) < 0.05 and oe["estimate"] <= 0)
    out["predictions"] = P
    if calib:
        out["calibration"] = calib

    os.makedirs(R(), exist_ok=True)
    json.dump(out, open(R("analysis.json"), "w"), indent=1, default=float)
    print("-> results/analysis.json")
    print("predictions:", json.dumps({k: (v.get("holds_point") if isinstance(v, dict) else v) for k, v in P.items()}))


if __name__ == "__main__":
    main()
