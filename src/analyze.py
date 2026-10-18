"""Every number in the paper, computed from the committed data.

Inputs: data/frame.json, data/denominators.json, data/sentences.json (with the
term-audit flags), data/rating/labels.json (two blind passes, third pass and
majority labels), data/phrase_reuse.json (and the L=8 sensitivity file when
present), data/xbrl_size.json, results/agreement.json and results/calibration.json.
Output: results/analysis.json.

Conventions. Sentence-level composition is reported on two bases: "agreed"
(both blind passes gave the class; the disputed set is shown as a bound) and
"majority" (majority of three). Each basis is reported with two weightings:
"sentence" (every corpus sentence counts once) and "filing" (every filing
counts once, using its within-filing shares), the second because one 2023
registrant contributes a sixth of the corpus. Uncertainty is a percentile
bootstrap over filings, 10,000 replicates, seed 20261018, vectorised over
per-filing count vectors so that every interval uses the full replicate count.
"""
from __future__ import annotations
import json, os, sys
from collections import Counter, defaultdict
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))
from stats import wilson  # noqa: E402

D = lambda *p: os.path.join(BASE, "data", *p)
R = lambda *p: os.path.join(BASE, "results", *p)
CLASSES = ["capability", "risk", "market", "governance", "other"]
CI = {c: i for i, c in enumerate(CLASSES)}
ERAS = {"2015-2019": range(2015, 2020), "2020-2023": range(2020, 2024), "2024-2026": range(2024, 2027)}
YEARS = list(range(2015, 2027))
REPS = int(os.environ.get("BOOT_REPS", "10000"))
SEED = 20261018
FLAG_K = 5


def era_of(y):
    for e, rng in ERAS.items():
        if y in rng:
            return e


# ------------------------------------------------------------------ loading
def load():
    frame = json.load(open(D("frame.json")))
    den = json.load(open(D("denominators.json")))
    sents = json.load(open(D("sentences.json")))
    labels = json.load(open(D("rating", "labels.json")))
    reuse = json.load(open(D("phrase_reuse.json")))
    reuse8 = json.load(open(D("phrase_reuse_L8.json"))) if os.path.exists(D("phrase_reuse_L8.json")) else {}
    size = json.load(open(D("xbrl_size.json"))) if os.path.exists(D("xbrl_size.json")) else {}
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
            r8 = reuse8.get(s["id"], {})
            rows.append({"sid": s["id"], "text": s["text"], "patterns": s["patterns"],
                         "class_agreed": l["class_agreed"], "disputed": l["disputed"],
                         "class_a": l["class_a"], "class_b": l["class_b"], "class_c": l.get("class_c"),
                         "class_majority": l.get("class_majority", l["class_agreed"]),
                         "own_agreed": l["own_agreed"], "own_disputed": l["own_disputed"],
                         "own_majority": l.get("own_majority", l["own_agreed"]),
                         "reuse_ciks": rr.get("reuse_ciks"), "total_hits": rr.get("total_hits"),
                         "self_hit": rr.get("self_hit"), "ciks_censored": rr.get("ciks_censored"),
                         "reuse_error": "error" in rr,
                         "reuse8": r8.get("reuse_ciks"), "hits8": r8.get("total_hits")})
        sz = size.get(f["adsh"], {})
        filings.append({"adsh": f["adsh"], "cik": f["cik"], "name": f["name"], "year": f["year"],
                        "era": era_of(f["year"]), "sector": f["sector"], "sic": f["sic"],
                        "n_extracted": f["n_ai"], "rows": rows, "assets": sz.get("assets")})
    return frame, den, sents, filings, agree, calib


# --------------------------------------------------- per-filing count vectors
class Vec:
    """Per-filing numerators and denominators for every estimand, so that a
    bootstrap replicate is a sum over an index array."""

    def __init__(self, filings):
        n = len(filings)
        self.n = n
        self.year = np.array([f["year"] for f in filings])
        self.era = np.array([f["era"] for f in filings])
        self.sector = np.array([f["sector"] for f in filings])
        self.has_rows = np.array([len(f["rows"]) > 0 for f in filings])
        self.cnt = {}      # (basis) -> array n x 5 class counts among decided rows
        self.dec = {}      # (basis) -> array n decided rows
        self.own_t = {}; self.own_n = {}
        self.any_own = {}; self.any_cap = {}
        for basis in ("agreed", "majority"):
            ck = "class_agreed" if basis == "agreed" else "class_majority"
            ok = "own_agreed" if basis == "agreed" else "own_majority"
            cnt = np.zeros((n, 5)); dec = np.zeros(n); ot = np.zeros(n); on = np.zeros(n)
            ao = np.zeros(n, dtype=bool); ac = np.zeros(n, dtype=bool)
            for i, f in enumerate(filings):
                for r in f["rows"]:
                    c = r[ck]
                    if c is not None:
                        cnt[i, CI[c]] += 1; dec[i] += 1
                        if c == "capability":
                            ac[i] = True
                    o = r[ok]
                    if o is not None:
                        on[i] += 1; ot[i] += bool(o)
                        if o:
                            ao[i] = True
            self.cnt[basis] = cnt; self.dec[basis] = dec; self.own_t[basis] = ot; self.own_n[basis] = on
            self.any_own[basis] = ao; self.any_cap[basis] = ac
        # phrase reuse: usable sentences and flagged counts, by majority class / own-use
        self.ru_use = np.zeros(n); self.ru_flag = np.zeros(n)
        for i, f in enumerate(filings):
            for r in f["rows"]:
                if not r["reuse_error"] and r["reuse_ciks"] is not None and r["total_hits"]:
                    self.ru_use[i] += 1; self.ru_flag[i] += (r["reuse_ciks"] >= FLAG_K)


def boot_idx(n, reps, seed):
    rng = np.random.default_rng(seed)
    return rng.integers(0, n, size=(reps, n))


def ratio_boot(num, den, idx):
    """num, den: arrays over filings. returns point, lo, hi of sum(num)/sum(den)."""
    pt = num.sum() / den.sum() if den.sum() else np.nan
    N = num[idx].sum(axis=1); Dn = den[idx].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = N / Dn
    return {"estimate": float(pt), "lo": float(np.nanpercentile(d, 2.5)), "hi": float(np.nanpercentile(d, 97.5))}


def mean_boot(vals, mask, idx):
    """mean of vals over filings where mask is True (nan elsewhere)."""
    v = np.where(mask, vals, np.nan)
    pt = np.nanmean(v) if mask.any() else np.nan
    with np.errstate(invalid="ignore"):
        d = np.nanmean(v[idx], axis=1)
    return {"estimate": float(pt), "lo": float(np.nanpercentile(d, 2.5)), "hi": float(np.nanpercentile(d, 97.5))}


def diff_boot(fnA, fnB, nA, nB, reps, seed):
    """fnX(idx_array) -> array of replicate statistics for group X."""
    ia = boot_idx(nA, reps, seed); ib = boot_idx(nB, reps, seed + 1)
    a = fnA(ia); b = fnB(ib)
    d = a - b
    pa = fnA(np.arange(nA)[None, :])[0]; pb = fnB(np.arange(nB)[None, :])[0]
    return {"estimate": float(pa - pb), "lo": float(np.nanpercentile(d, 2.5)), "hi": float(np.nanpercentile(d, 97.5)),
            "share_positive": float(np.nanmean(d > 0))}


def sub(V, mask):
    """index array of filings satisfying mask."""
    return np.where(mask)[0]


def class_share_sentence(V, basis, cls, sel):
    return V.cnt[basis][sel, CI[cls]], V.dec[basis][sel]


def class_share_filing(V, basis, cls, sel):
    with np.errstate(invalid="ignore", divide="ignore"):
        sh = V.cnt[basis][sel, CI[cls]] / V.dec[basis][sel]
    return sh, V.dec[basis][sel] > 0


def own_share_sentence(V, basis, sel):
    return V.own_t[basis][sel], V.own_n[basis][sel]


def own_share_filing(V, basis, sel):
    with np.errstate(invalid="ignore", divide="ignore"):
        sh = V.own_t[basis][sel] / V.own_n[basis][sel]
    return sh, V.own_n[basis][sel] > 0


def composition_block(V, basis, weighting, sel, reps, seed):
    idx = boot_idx(len(sel), reps, seed)
    out = {}
    for cls in CLASSES:
        if weighting == "sentence":
            num, den = class_share_sentence(V, basis, cls, sel)
            out[cls] = ratio_boot(num, den, idx)
        else:
            sh, m = class_share_filing(V, basis, cls, sel)
            out[cls] = mean_boot(sh, m, idx)
    if weighting == "sentence":
        num, den = own_share_sentence(V, basis, sel)
        out["own_use"] = ratio_boot(num, den, idx)
    else:
        sh, m = own_share_filing(V, basis, sel)
        out["own_use"] = mean_boot(sh, m, idx)
    out["n_filings"] = int(len(sel)); out["n_sentences"] = int(V.dec[basis][sel].sum())
    return out


def stat_fn_class(V, basis, weighting, cls, sel):
    """returns a function idx -> replicate statistics (array)."""
    if weighting == "sentence":
        num, den = class_share_sentence(V, basis, cls, sel)
        def fn(idx):
            with np.errstate(invalid="ignore", divide="ignore"):
                return num[idx].sum(axis=1) / den[idx].sum(axis=1)
    else:
        sh, m = class_share_filing(V, basis, cls, sel)
        v = np.where(m, sh, np.nan)
        def fn(idx):
            with np.errstate(invalid="ignore"):
                return np.nanmean(v[idx], axis=1)
    return fn


def stat_fn_own(V, basis, weighting, sel):
    if weighting == "sentence":
        num, den = own_share_sentence(V, basis, sel)
        def fn(idx):
            with np.errstate(invalid="ignore", divide="ignore"):
                return num[idx].sum(axis=1) / den[idx].sum(axis=1)
    else:
        sh, m = own_share_filing(V, basis, sel)
        v = np.where(m, sh, np.nan)
        def fn(idx):
            with np.errstate(invalid="ignore"):
                return np.nanmean(v[idx], axis=1)
    return fn


def stat_fn_any(V, key, basis, sel):
    flags = (V.any_own if key == "own" else V.any_cap)[basis][sel].astype(float)
    has = V.has_rows[sel]
    v = np.where(has, flags, np.nan)
    def fn(idx):
        with np.errstate(invalid="ignore"):
            return np.nanmean(v[idx], axis=1)
    return fn


def any_boot(V, key, basis, sel, reps, seed):
    fn = stat_fn_any(V, key, basis, sel)
    idx = boot_idx(len(sel), reps, seed)
    d = fn(idx); pt = fn(np.arange(len(sel))[None, :])[0]
    return {"estimate": float(pt), "lo": float(np.nanpercentile(d, 2.5)), "hi": float(np.nanpercentile(d, 97.5))}


# ------------------------------------------------------------------- main
def main():
    frame, den, sents, filings, agree, calib = load()
    V = Vec(filings)
    ALL = np.arange(V.n)
    out = {"seed": SEED, "reps": REPS}

    # ---- universe
    uni = {}
    for y in YEARS:
        fy = frame["years"][str(y)]
        n = den["years"][str(y)]["total_10k"]
        uni[str(y)] = {"hits": fy["reported_total_hits"], "filings_any_doc": fy["filings_any_doc"],
                       "frame": fy["filings_main_10k"], "registrants": fy["registrants_main_10k"],
                       "all_10k": n, "raw_share": fy["filings_main_10k"] / n}
    out["universe"] = uni
    out["raw_share_growth_2015_2025"] = uni["2025"]["raw_share"] / uni["2015"]["raw_share"]
    out["frame_total_filings"] = sum(uni[str(y)]["frame"] for y in YEARS)
    out["all_10k_total"] = sum(uni[str(y)]["all_10k"] for y in YEARS)

    # ---- corpus
    n_extracted = sum(f["n_extracted"] for f in filings)
    n_corpus = sum(len(f["rows"]) for f in filings)
    per_f = sorted(len(f["rows"]) for f in filings)
    largest = max(filings, key=lambda f: len(f["rows"]))
    out["corpus"] = {
        "filings": len(filings), "registrants": len({f["cik"] for f in filings}),
        "extracted": n_extracted, "removed_non_ai": sents["term_audit"]["removed"],
        "term_audit": sents["term_audit"], "sentences": n_corpus,
        "filings_with_sentences": sum(1 for n in per_f if n),
        "filings_zero_after_audit": sum(1 for n in per_f if n == 0),
        "median_per_filing": per_f[len(per_f) // 2], "max_per_filing": per_f[-1],
        "largest_filer_share": max(per_f) / n_corpus, "largest_filer": largest["name"], "largest_filer_year": largest["year"],
        "by_year": {str(y): {"filings": int((V.year == y).sum()), "sentences": int(sum(len(f["rows"]) for f in filings if f["year"] == y))} for y in YEARS},
        "by_era": {e: {"filings": int((V.era == e).sum()), "sentences": int(sum(len(f["rows"]) for f in filings if f["era"] == e))} for e in ERAS},
        "by_sector": dict(Counter(f["sector"] for f in filings)),
        "pattern_counts": dict(Counter(p for f in filings for r in f["rows"] for p in r["patterns"])),
        "disputed_class": sum(1 for f in filings for r in f["rows"] if r["disputed"]),
        "disputed_own": sum(1 for f in filings for r in f["rows"] if r["own_disputed"]),
        "disputed_either": sum(1 for f in filings for r in f["rows"] if r["disputed"] or r["own_disputed"]),
        "unresolved_after_third": sum(1 for f in filings for r in f["rows"] if r["class_majority"] is None),
        "third_pass": json.load(open(D("rating", "third", "merge_stats.json"))) if os.path.exists(D("rating", "third", "merge_stats.json")) else None,
        "sentences_per_filing_by_era": {e: float(np.mean([len(f["rows"]) for f in filings if f["era"] == e])) for e in ERAS},
    }
    out["agreement"] = agree

    # ---- composition
    comp = {}
    for basis in ("agreed", "majority"):
        comp[basis] = {}
        for weighting in ("sentence", "filing"):
            block = {"overall": composition_block(V, basis, weighting, ALL, REPS, SEED), "era": {}, "year": {}}
            for e in ERAS:
                block["era"][e] = composition_block(V, basis, weighting, sub(V, V.era == e), REPS, SEED)
            for y in YEARS:
                block["year"][str(y)] = composition_block(V, basis, weighting, sub(V, V.year == y), REPS, SEED)
            comp[basis][weighting] = block
    rows_all = [r for f in filings for r in f["rows"]]
    n_all = len(rows_all)
    bound = {}
    for cls in CLASSES:
        lo = sum(1 for r in rows_all if r["class_agreed"] == cls) / n_all
        hi = sum(1 for r in rows_all if r["class_agreed"] == cls or (r["disputed"] and cls in (r["class_a"], r["class_b"]))) / n_all
        bound[cls] = {"lo": lo, "hi": hi}
    comp["agreed"]["sentence"]["disputed_bound_overall"] = bound
    comp["agreed_counts_overall"] = dict(Counter(r["class_agreed"] for r in rows_all if r["class_agreed"]))
    comp["majority_counts_overall"] = dict(Counter(r["class_majority"] for r in rows_all if r["class_majority"]))
    comp["majority_counts_by_era"] = {e: dict(Counter(r["class_majority"] for f in filings if f["era"] == e for r in f["rows"] if r["class_majority"])) for e in ERAS}
    comp["own_majority_counts_by_era"] = {e: dict(Counter(str(r["own_majority"]) for f in filings if f["era"] == e for r in f["rows"] if r["own_majority"] is not None)) for e in ERAS}
    out["composition"] = comp

    # ---- era contrasts
    A = sub(V, V.era == "2015-2019"); C = sub(V, V.era == "2024-2026")
    contrasts = {}
    for basis in ("agreed", "majority"):
        contrasts[basis] = {}
        for weighting in ("sentence", "filing"):
            contrasts[basis][weighting] = {
                "risk_late_minus_early": diff_boot(stat_fn_class(V, basis, weighting, "risk", C), stat_fn_class(V, basis, weighting, "risk", A), len(C), len(A), REPS, SEED),
                "capability_late_minus_early": diff_boot(stat_fn_class(V, basis, weighting, "capability", C), stat_fn_class(V, basis, weighting, "capability", A), len(C), len(A), REPS, SEED),
                "other_late_minus_early": diff_boot(stat_fn_class(V, basis, weighting, "other", C), stat_fn_class(V, basis, weighting, "other", A), len(C), len(A), REPS, SEED),
                "own_use_late_minus_early": diff_boot(stat_fn_own(V, basis, weighting, C), stat_fn_own(V, basis, weighting, A), len(C), len(A), REPS, SEED),
            }
    out["era_contrasts"] = contrasts

    # ---- filing level and corrected adoption trend
    fl = {}
    for basis in ("agreed", "majority"):
        fl[basis] = {"year": {}, "era": {}, "overall": {}}
        fl[basis]["overall"]["own_use_any"] = any_boot(V, "own", basis, ALL, REPS, SEED)
        fl[basis]["overall"]["capability_any"] = any_boot(V, "cap", basis, ALL, REPS, SEED)
        fl[basis]["overall"]["n_filings"] = int(V.has_rows.sum())
        for e, rng in ERAS.items():
            sel = sub(V, V.era == e)
            p = any_boot(V, "own", basis, sel, REPS, SEED)
            fr = sum(uni[str(y)]["frame"] for y in rng); al = sum(uni[str(y)]["all_10k"] for y in rng)
            k_o = int(V.any_own[basis][sel].sum()); n_f = int(V.has_rows[sel].sum())
            fl[basis]["era"][e] = {"own_use_any": {**p, "wilson": wilson(k_o, n_f), "k": k_o},
                                   "capability_any": {**any_boot(V, "cap", basis, sel, REPS, SEED), "k": int(V.any_cap[basis][sel].sum())},
                                   "n_filings": n_f, "raw_share_pooled": fr / al,
                                   "corrected_own_use_pooled": {"estimate": fr / al * p["estimate"], "lo": fr / al * p["lo"], "hi": fr / al * p["hi"]},
                                   "overstatement_factor": 1 / p["estimate"] if p["estimate"] else None,
                                   "overstatement_factor_interval": [1 / p["hi"] if p["hi"] else None, 1 / p["lo"] if p["lo"] else None]}
        for y in YEARS:
            sel = sub(V, V.year == y)
            n_f = int(V.has_rows[sel].sum()); k_o = int(V.any_own[basis][sel].sum()); k_c = int(V.any_cap[basis][sel].sum())
            bo = any_boot(V, "own", basis, sel, REPS, SEED); bc = any_boot(V, "cap", basis, sel, REPS, SEED)
            raw = uni[str(y)]["raw_share"]
            fl[basis]["year"][str(y)] = {
                "n_filings": n_f, "own_use_any_k": k_o, "capability_any_k": k_c,
                "own_use_any": {**bo, "wilson": wilson(k_o, n_f)}, "capability_any": {**bc, "wilson": wilson(k_c, n_f)},
                "raw_share": raw,
                "corrected_own_use": {"estimate": raw * bo["estimate"], "lo": raw * bo["lo"], "hi": raw * bo["hi"]},
                "corrected_capability": {"estimate": raw * bc["estimate"], "lo": raw * bc["lo"], "hi": raw * bc["hi"]},
                "overstatement_factor": (1 / bo["estimate"]) if bo["estimate"] else None}
        fnC = stat_fn_any(V, "own", basis, C); fnA = stat_fn_any(V, "own", basis, A)
        fl[basis]["own_any_late_minus_early"] = diff_boot(fnC, fnA, len(C), len(A), REPS, SEED)
        fl[basis]["overstatement_late_minus_early"] = diff_boot(lambda i: 1 / fnC(i), lambda i: 1 / fnA(i), len(C), len(A), REPS, SEED)
        fnCc = stat_fn_any(V, "cap", basis, C); fnAc = stat_fn_any(V, "cap", basis, A)
        fl[basis]["cap_any_late_minus_early"] = diff_boot(fnCc, fnAc, len(C), len(A), REPS, SEED)
    out["filing_level"] = fl

    # ---- trend tests
    from scipy.stats import spearmanr
    trend = {}
    for basis in ("agreed", "majority"):
        own_y = [fl[basis]["year"][str(y)]["own_use_any"]["estimate"] for y in YEARS]
        risk_y = [comp[basis]["filing"]["year"][str(y)]["risk"]["estimate"] for y in YEARS]
        owns_y = [comp[basis]["filing"]["year"][str(y)]["own_use"]["estimate"] for y in YEARS]
        cap_y = [comp[basis]["filing"]["year"][str(y)]["capability"]["estimate"] for y in YEARS]
        trend[basis] = {k: {"rho": float(spearmanr(YEARS, v)[0]), "p": float(spearmanr(YEARS, v)[1])} for k, v in
                        [("spearman_year_vs_filing_own_any", own_y), ("spearman_year_vs_risk_share_filingweighted", risk_y),
                         ("spearman_year_vs_own_share_filingweighted", owns_y), ("spearman_year_vs_capability_share_filingweighted", cap_y)]}
        try:
            import statsmodels.api as sm
            ok = "own_agreed" if basis == "agreed" else "own_majority"
            ck = "class_agreed" if basis == "agreed" else "class_majority"
            for name, pick in (("logit_own_use_on_year", lambda r: None if r[ok] is None else int(bool(r[ok]))),
                               ("logit_risk_on_year", lambda r: None if r[ck] is None else int(r[ck] == "risk")),
                               ("logit_capability_on_year", lambda r: None if r[ck] is None else int(r[ck] == "capability"))):
                yv, xv, gv = [], [], []
                for i, f in enumerate(filings):
                    for r in f["rows"]:
                        v = pick(r)
                        if v is None:
                            continue
                        yv.append(v); xv.append(f["year"] - 2015); gv.append(i)
                X = sm.add_constant(np.array(xv, dtype=float))
                m = sm.Logit(np.array(yv), X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": np.array(gv)})
                trend[basis][name] = {"coef_per_year": float(m.params[1]), "se_cluster": float(m.bse[1]), "p": float(m.pvalues[1]),
                                      "odds_ratio_per_year": float(np.exp(m.params[1])), "n": len(yv)}
        except Exception as e:
            trend[basis]["logit_error"] = str(e)
    out["trend"] = trend

    # ---- phrase reuse
    pr = {}
    rows_r = [r for f in filings for r in f["rows"] if not r["reuse_error"] and r["reuse_ciks"] is not None]
    pr["n_queried"] = len(rows_r)
    pr["n_errors"] = sum(1 for f in filings for r in f["rows"] if r["reuse_error"])
    pr["n_zero_hits"] = sum(1 for r in rows_r if r["total_hits"] == 0)
    pr["self_hit_rate"] = float(np.mean([bool(r["self_hit"]) for r in rows_r]))
    pr["n_censored"] = sum(1 for r in rows_r if r["ciks_censored"])
    usable = [r for r in rows_r if r["total_hits"]]
    pr["n_usable"] = len(usable)
    ru_all = np.array([r["reuse_ciks"] for r in usable])
    pr["overall"] = {"share_zero": float(np.mean(ru_all == 0)), "share_flagged": float(np.mean(ru_all >= FLAG_K)),
                     "share_ge30": float(np.mean(ru_all >= 30)), "max": int(ru_all.max()), "mean": float(ru_all.mean()),
                     "median": float(np.median(ru_all))}
    u8 = [r for r in rows_r if r["hits8"]]
    if u8:
        r8 = np.array([r["reuse8"] for r in u8])
        pr["L8_sensitivity"] = {"n": len(u8), "share_zero": float(np.mean(r8 == 0)), "share_flagged": float(np.mean(r8 >= FLAG_K)),
                                "share_ge30": float(np.mean(r8 >= 30)), "max": int(r8.max())}
        for basis in ("majority",):
            ck = "class_majority"
            pr["L8_sensitivity"]["flag_by_class"] = {c: float(np.mean([r["reuse8"] >= FLAG_K for r in u8 if r[ck] == c])) for c in CLASSES if any(r[ck] == c for r in u8)}
    for basis in ("agreed", "majority"):
        ck = "class_agreed" if basis == "agreed" else "class_majority"
        ok = "own_agreed" if basis == "agreed" else "own_majority"
        byc = {}
        for cls in CLASSES:
            v = np.array([r["reuse_ciks"] for r in usable if r[ck] == cls])
            if len(v):
                k = int((v >= FLAG_K).sum())
                byc[cls] = {"n": int(len(v)), "flagged": k, "median": float(np.median(v)), "mean": float(v.mean()),
                            "share_zero": float(np.mean(v == 0)), "share_flagged": k / len(v), "share_flagged_wilson": wilson(k, len(v)),
                            "q75": float(np.percentile(v, 75)), "q90": float(np.percentile(v, 90)), "max": int(v.max())}
        own_t = np.array([r["reuse_ciks"] for r in usable if r[ok] is True]); own_f = np.array([r["reuse_ciks"] for r in usable if r[ok] is False])
        d = {"by_class": byc,
             "own_use_true": {"n": int(len(own_t)), "median": float(np.median(own_t)), "share_flagged": float(np.mean(own_t >= FLAG_K)), "share_zero": float(np.mean(own_t == 0))},
             "own_use_false": {"n": int(len(own_f)), "median": float(np.median(own_f)), "share_flagged": float(np.mean(own_f >= FLAG_K)), "share_zero": float(np.mean(own_f == 0))}}
        y = np.array([0 if r[ok] else 1 for r in usable if r[ok] is not None]); s = np.array([r["reuse_ciks"] for r in usable if r[ok] is not None], dtype=float)
        pos, neg = s[y == 1], s[y == 0]
        d["auc_flag_predicts_not_own_use"] = float((np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :])) / (len(pos) * len(neg)))
        thr = {}
        for k in (1, 2, 3, 5, 10, 20):
            pred = s >= k
            tp = int(np.sum(pred & (y == 1))); fp = int(np.sum(pred & (y == 0))); fn = int(np.sum((~pred) & (y == 1)))
            thr[str(k)] = {"precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None, "flagged_share": float(np.mean(pred))}
        d["thresholds"] = thr
        # risk flagged share vs capability flagged share (classifier of class)
        yr = np.array([1 if r[ck] == "risk" else 0 for r in usable if r[ck] is not None]); sr = np.array([r["reuse_ciks"] for r in usable if r[ck] is not None], dtype=float)
        pos, neg = sr[yr == 1], sr[yr == 0]
        d["auc_flag_predicts_risk"] = float((np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :])) / (len(pos) * len(neg)))
        pred = sr >= FLAG_K
        d["flag_precision_for_risk"] = float(np.sum(pred & (yr == 1)) / pred.sum()) if pred.sum() else None
        d["flag_recall_for_risk"] = float(np.sum(pred & (yr == 1)) / (yr == 1).sum())
        idx = boot_idx(V.n, REPS, SEED)
        d["flagged_share_overall"] = ratio_boot(V.ru_flag, V.ru_use, idx)
        d["flagged_share_era"] = {}
        for e in ERAS:
            sel = sub(V, V.era == e)
            d["flagged_share_era"][e] = ratio_boot(V.ru_flag[sel], V.ru_use[sel], boot_idx(len(sel), REPS, SEED))
        def fflag(sel):
            num, den = V.ru_flag[sel], V.ru_use[sel]
            def fn(i):
                with np.errstate(invalid="ignore", divide="ignore"):
                    return num[i].sum(axis=1) / den[i].sum(axis=1)
            return fn
        d["flagged_share_late_minus_early"] = diff_boot(fflag(C), fflag(A), len(C), len(A), REPS, SEED)
        pr[basis] = d
    # the most reused phrases
    top = sorted([r for r in usable], key=lambda r: -r["reuse_ciks"])[:12]
    pr["top_reused"] = [{"sid": r["sid"], "reuse_ciks": r["reuse_ciks"], "class": r["class_majority"], "own_use": r["own_majority"], "text": r["text"][:300]} for r in top]
    out["phrase_reuse"] = pr

    # ---- sector
    sec = {}
    for basis in ("agreed", "majority"):
        sec[basis] = {}
        for st in ("technology", "healthcare", "finance_realestate", "other"):
            sel = sub(V, V.sector == st)
            idx = boot_idx(len(sel), REPS, SEED)
            sh, m = own_share_filing(V, basis, sel); shc, mc = class_share_filing(V, basis, "capability", sel); shr, mr = class_share_filing(V, basis, "risk", sel)
            sec[basis][st] = {"n_filings": int(len(sel)), "n_filings_with_sentences": int(V.has_rows[sel].sum()),
                              "n_sentences": int(V.dec[basis][sel].sum()),
                              "own_use_any": {**any_boot(V, "own", basis, sel, REPS, SEED), "k": int(V.any_own[basis][sel].sum())},
                              "own_use_share_filing": mean_boot(sh, m, idx),
                              "capability_share_filing": mean_boot(shc, mc, idx), "risk_share_filing": mean_boot(shr, mr, idx)}
        T = sub(V, V.sector == "technology"); Rst = sub(V, V.sector != "technology")
        sec[basis]["tech_minus_rest_own_any"] = diff_boot(stat_fn_any(V, "own", basis, T), stat_fn_any(V, "own", basis, Rst), len(T), len(Rst), REPS, SEED)
        sec[basis]["tech_minus_rest_own_share"] = diff_boot(stat_fn_own(V, basis, "filing", T), stat_fn_own(V, basis, "filing", Rst), len(T), len(Rst), REPS, SEED)
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

    # ---- size (exploratory)
    assets = np.array([f["assets"] if f["assets"] is not None else np.nan for f in filings], dtype=float)
    have = ~np.isnan(assets)
    if have.sum() > 10:
        med = np.nanmedian(assets)
        big = sub(V, have & (assets >= med)); small = sub(V, have & (assets < med))
        out["size"] = {"n_with_assets": int(have.sum()), "median_assets_usd": float(med),
                       "own_use_any_large": any_boot(V, "own", "majority", big, REPS, SEED),
                       "own_use_any_small": any_boot(V, "own", "majority", small, REPS, SEED),
                       "risk_share_filing_large": mean_boot(*class_share_filing(V, "majority", "risk", big), boot_idx(len(big), REPS, SEED)),
                       "risk_share_filing_small": mean_boot(*class_share_filing(V, "majority", "risk", small), boot_idx(len(small), REPS, SEED)),
                       "large_minus_small_own_any": diff_boot(stat_fn_any(V, "own", "majority", big), stat_fn_any(V, "own", "majority", small), len(big), len(small), REPS, SEED)}

    # ---- replication of the companion's 2025 composition
    sel25 = sub(V, V.year == 2025)
    idx25 = boot_idx(len(sel25), REPS, SEED)
    out["replication_2025"] = {
        "n_filings": int(len(sel25)), "n_sentences": int(sum(len(f["rows"]) for f in filings if f["year"] == 2025)),
        "risk_sentence_agreed": ratio_boot(*class_share_sentence(V, "agreed", "risk", sel25), idx25),
        "capability_sentence_agreed": ratio_boot(*class_share_sentence(V, "agreed", "capability", sel25), idx25),
        "risk_sentence_majority": ratio_boot(*class_share_sentence(V, "majority", "risk", sel25), idx25),
        "capability_sentence_majority": ratio_boot(*class_share_sentence(V, "majority", "capability", sel25), idx25),
        "risk_filing_majority": mean_boot(*class_share_filing(V, "majority", "risk", sel25), idx25),
        "capability_filing_majority": mean_boot(*class_share_filing(V, "majority", "capability", sel25), idx25),
        "companion": {"risk": 0.605, "capability": 0.122, "n_sentences": 598, "n_filings": 59},
    }

    # ---- calibration-corrected composition (forward transfer, joint bootstrap)
    if calib:
        out["calibration"] = calib
        key = json.load(open(D("calibration", "key.json")))
        rev = {}
        for line in open(D("calibration", "reviewer.jsonl")):
            line = line.strip()
            if line:
                j = json.loads(line); rev[j["cid"]] = j
        units = defaultdict(list); own_units = {True: [], False: []}
        for k in key:
            if k["rep"] != 0:
                continue
            units[k["class_majority"]].append(rev[k["cid"]]["class"])
            own_units[k["own_majority"]].append(rev[k["cid"]]["own_use"])
        cls_units = {c: np.array([CI[x] for x in units.get(c, [])], dtype=int) for c in CLASSES}
        ou = {t: np.array(own_units[t], dtype=bool) for t in (True, False)}

        def T_from(cu):
            T = np.eye(5)
            for i, c in enumerate(CLASSES):
                arr = cu[c]
                if len(arr):
                    T[i] = np.bincount(arr, minlength=5) / len(arr)
            return T

        def own_rates(o):
            return (o[True].mean() if len(o[True]) else 1.0, (~o[False]).mean() if len(o[False]) else 1.0)

        rng = np.random.default_rng(SEED)
        T0 = T_from(cls_units); st0, sf0 = own_rates(ou)
        cal = {"transfer_matrix": {c: {j: float(T0[i, k]) for k, j in enumerate(CLASSES)} for i, c in enumerate(CLASSES)},
               "own_use_survival": {"true": float(st0), "false": float(sf0)}, "n_units": {c: int(len(cls_units[c])) for c in CLASSES}}
        nrep = min(REPS, 10000)
        for weighting in ("sentence", "filing"):
            cal[weighting] = {}
            for scope, sel in [("overall", ALL)] + [(e, sub(V, V.era == e)) for e in ERAS]:
                idx = boot_idx(len(sel), nrep, SEED)
                # raw shares per replicate (nrep x 5) and own share (nrep)
                if weighting == "sentence":
                    cnt = V.cnt["majority"][sel]; dec = V.dec["majority"][sel]
                    with np.errstate(invalid="ignore", divide="ignore"):
                        raw = cnt[idx].sum(axis=1) / dec[idx].sum(axis=1)[:, None]
                        raw0 = cnt.sum(axis=0) / dec.sum()
                        own = V.own_t["majority"][sel][idx].sum(axis=1) / V.own_n["majority"][sel][idx].sum(axis=1)
                        own0 = V.own_t["majority"][sel].sum() / V.own_n["majority"][sel].sum()
                else:
                    with np.errstate(invalid="ignore", divide="ignore"):
                        shares = V.cnt["majority"][sel] / V.dec["majority"][sel][:, None]
                        osh = V.own_t["majority"][sel] / V.own_n["majority"][sel]
                        raw = np.nanmean(shares[idx], axis=1); raw0 = np.nanmean(shares, axis=0)
                        own = np.nanmean(osh[idx], axis=1); own0 = np.nanmean(osh)
                # resample calibration units per replicate
                Ts = np.empty((nrep, 5, 5)); sts = np.empty(nrep); sfs = np.empty(nrep)
                for r in range(nrep):
                    cu = {c: (rng.choice(cls_units[c], len(cls_units[c]), replace=True) if len(cls_units[c]) else cls_units[c]) for c in CLASSES}
                    Ts[r] = T_from(cu)
                    o = {t: (rng.choice(ou[t], len(ou[t]), replace=True) if len(ou[t]) else ou[t]) for t in (True, False)}
                    sts[r], sfs[r] = own_rates(o)
                corr = np.einsum("ri,rij->rj", np.nan_to_num(raw), Ts)
                corr0 = np.nan_to_num(raw0) @ T0
                own_c = own * sts + (1 - own) * (1 - sfs); own_c0 = own0 * st0 + (1 - own0) * (1 - sf0)
                block = {c: {"estimate": float(corr0[k]), "lo": float(np.nanpercentile(corr[:, k], 2.5)), "hi": float(np.nanpercentile(corr[:, k], 97.5))} for k, c in enumerate(CLASSES)}
                block["own_use"] = {"estimate": float(own_c0), "lo": float(np.nanpercentile(own_c, 2.5)), "hi": float(np.nanpercentile(own_c, 97.5))}
                block["uncorrected"] = {c: float(raw0[k]) for k, c in enumerate(CLASSES)}
                block["uncorrected"]["own_use"] = float(own0)
                cal[weighting][scope] = block
        cal["risk_late_minus_early_filing"] = cal["filing"]["2024-2026"]["risk"]["estimate"] - cal["filing"]["2015-2019"]["risk"]["estimate"]
        cal["capability_late_minus_early_filing"] = cal["filing"]["2024-2026"]["capability"]["estimate"] - cal["filing"]["2015-2019"]["capability"]["estimate"]
        cal["own_use_late_minus_early_filing"] = cal["filing"]["2024-2026"]["own_use"]["estimate"] - cal["filing"]["2015-2019"]["own_use"]["estimate"]
        out["calibrated"] = cal

    # ---- predictions
    P = {}
    cs = contrasts["majority"]["filing"]
    P["1_risk_share_higher_late"] = {"holds_point": cs["risk_late_minus_early"]["estimate"] > 0, "interval_excludes_zero": cs["risk_late_minus_early"]["lo"] > 0, **cs["risk_late_minus_early"]}
    P["2_own_use_share_lower_late"] = {"holds_point": cs["own_use_late_minus_early"]["estimate"] < 0, "interval_excludes_zero": cs["own_use_late_minus_early"]["hi"] < 0, **cs["own_use_late_minus_early"]}
    late = fl["majority"]["era"]["2024-2026"]["own_use_any"]
    P["3_under_60pct_filings_own_use_late"] = {"holds_point": late["estimate"] < 0.60, "interval_below": late["hi"] < 0.60, **{k: late[k] for k in ("estimate", "lo", "hi", "wilson", "k")}}
    b = pr["majority"]["by_class"]
    ratio = (b["risk"]["median"] / b["capability"]["median"]) if b["capability"]["median"] else None
    P["4_risk_reuse_vs_capability"] = {"median_risk": b["risk"]["median"], "median_capability": b["capability"]["median"],
                                       "median_ratio": ratio, "median_criterion_decidable": ratio is not None, "holds_median_3x": (ratio >= 3) if ratio is not None else None,
                                       "flag_risk": b["risk"]["share_flagged"], "flag_capability": b["capability"]["share_flagged"],
                                       "holds_flag_2x": b["risk"]["share_flagged"] >= 2 * b["capability"]["share_flagged"] and b["risk"]["share_flagged"] > 0}
    fe = pr["majority"]["flagged_share_late_minus_early"]
    P["5_flagged_share_rises"] = {"holds_point": fe["estimate"] > 0, "interval_excludes_zero": fe["lo"] > 0, **fe}
    oe = fl["majority"]["overstatement_late_minus_early"]
    P["6_overstatement_grows"] = {"holds_point": oe["estimate"] > 0, "interval_excludes_zero": oe["lo"] > 0, **oe,
                                  "early": fl["majority"]["era"]["2015-2019"]["overstatement_factor"], "late": fl["majority"]["era"]["2024-2026"]["overstatement_factor"]}
    td = sec["majority"]["tech_minus_rest_own_any"]
    P["7_tech_higher_own_use"] = {"holds_point": td["estimate"] > 0, "interval_excludes_zero": td["lo"] > 0, **td}
    rd = cs["risk_late_minus_early"]["estimate"]
    P["falsification_triggered"] = bool(abs(rd) < 0.05 and oe["estimate"] <= 0)
    out["predictions"] = P

    os.makedirs(R(), exist_ok=True)
    json.dump(out, open(R("analysis.json"), "w"), indent=1, default=float)
    print("-> results/analysis.json")
    print("predictions:", json.dumps({k: (v.get("holds_point", v.get("holds_flag_2x")) if isinstance(v, dict) else v) for k, v in P.items()}))


if __name__ == "__main__":
    main()
