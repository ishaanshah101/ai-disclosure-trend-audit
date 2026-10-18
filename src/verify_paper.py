"""Check every number quoted in paper/paper.md and exit non-zero on any mismatch.

Two kinds of check. The headline estimates (design-weighted, filing-weighted era
composition on the majority basis, the filing-level own-use and capability
fractions by era, and the corpus counts) are RECOMPUTED here from the committed
labels in data/rating/labels.json, data/sentences.json and data/frame.json, with no
use of results/analysis.json, and compared both to analysis.json and to the paper.
Every other quoted number is formatted from results/analysis.json (or the raw data
files) exactly as the paper quotes it and asserted to occur in the paper text.
Verbatim quotations are checked against the corpus and the registrant that filed
them, and the companion study's figures are read from data/companion_values.json.
Run after src/analyze.py.
"""
from __future__ import annotations
import json, os, re, sys
from collections import Counter, defaultdict
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))
from stats import wilson  # noqa: E402

R = json.load(open(os.path.join(BASE, "results", "analysis.json")))
A = R["agreement"]
PAPER = re.sub(r"\s+", " ", open(os.path.join(BASE, "paper", "paper.md")).read())
CLASSES = ["capability", "risk", "market", "governance", "other"]
ERAS = {"2015-2019": range(2015, 2020), "2020-2023": range(2020, 2024), "2024-2026": range(2024, 2027)}
checks, failures = 0, []


def ok(label, text):
    global checks
    checks += 1
    if text not in PAPER:
        failures.append(f"{label}: expected '{text}' in paper")


def cond(label, condition, detail=""):
    global checks
    checks += 1
    if not condition:
        failures.append(f"{label}: {detail}")


def pct(x, d=1):
    if isinstance(x, dict):
        x = x["estimate"]
    return f"{x * 100:.{d}f}"


def pct_ci(dct, d=1):
    return f"{pct(dct['estimate'], d)} ({pct(dct['lo'], d)}, {pct(dct['hi'], d)})"


def num(x):
    return f"{x:,}"


# ================================================================ recomputation from labels
labels = json.load(open(os.path.join(BASE, "data", "rating", "labels.json")))
sents = json.load(open(os.path.join(BASE, "data", "sentences.json")))
frame = json.load(open(os.path.join(BASE, "data", "frame.json")))
by_sid = {l["sid"]: l for l in labels.values()}
fil = []
for f in sents["filings"]:
    rows = [by_sid[s["id"]] for s in f["ai_sentences"] if not s.get("non_ai") and s["id"] in by_sid]
    fil.append({"year": f["year"], "name": f["name"], "rows": rows})
n_corpus = sum(len(f["rows"]) for f in fil)
n_with = sum(1 for f in fil if f["rows"])
n_samp = Counter(f["year"] for f in fil)
w_of = {y: frame["years"][str(y)]["registrants_main_10k"] / n_samp[y] for y in n_samp}
cond("recompute corpus n", n_corpus == R["corpus"]["sentences"] == 2242, f"{n_corpus}")
cond("recompute filings with sentences", n_with == R["corpus"]["filings_with_sentences"] == 313, f"{n_with}")
ok("corpus n", f"leaving {num(n_corpus)} corpus sentences in {n_with} filings")

def era_share(era, key, cls=None):
    """design-weighted mean over filings of the within-filing share (majority basis)."""
    num_, den_ = 0.0, 0.0
    for f in fil:
        if f["year"] not in ERAS[era]:
            continue
        if key == "class":
            dec = [r for r in f["rows"] if r["class_majority"] is not None]
            if not dec:
                continue
            sh = sum(1 for r in dec if r["class_majority"] == cls) / len(dec)
        else:
            dec = [r for r in f["rows"] if r["own_majority"] is not None]
            if not dec:
                continue
            sh = sum(1 for r in dec if r["own_majority"]) / len(dec)
        num_ += w_of[f["year"]] * sh; den_ += w_of[f["year"]]
    return num_ / den_

CM = R["composition"]["majority"]["filing"]["era"]
for e in ERAS:
    for cls in CLASSES:
        v = era_share(e, "class", cls)
        cond(f"recompute {e} {cls}", abs(v - CM[e][cls]["estimate"]) < 1e-9, f"{v} vs {CM[e][cls]['estimate']}")
        if cls == "governance" and e != "2024-2026":
            ok(f"table2 governance {e}", "| governance | 0.0 | 0.0 |")
        else:
            ok(f"table2 {e} {cls}", f"{pct_ci(CM[e][cls])} |")
    v = era_share(e, "own")
    cond(f"recompute {e} own", abs(v - CM[e]["own_use"]["estimate"]) < 1e-9, f"{v}")
    ok(f"table2 {e} own", f"{pct_ci(CM[e]['own_use'])} |")
    nf = sum(1 for f in fil if f["year"] in ERAS[e] and any(r["class_majority"] is not None for r in f["rows"]))
    ns = sum(1 for f in fil if f["year"] in ERAS[e] for r in f["rows"] if r["class_majority"] is not None)
    cond(f"recompute n {e}", nf == CM[e]["n_filings"] and ns == CM[e]["n_sentences"], f"{nf},{ns}")
ok("table2 counts", f"| filings, sentences | {CM['2015-2019']['n_filings']}, {num(CM['2015-2019']['n_sentences'])} | {CM['2020-2023']['n_filings']}, {num(CM['2020-2023']['n_sentences'])} | {CM['2024-2026']['n_filings']}, {num(CM['2024-2026']['n_sentences'])} |")
cond("table2 sentences sum", sum(CM[e]["n_sentences"] for e in ERAS) == 2237 and R["corpus"]["unresolved_after_third"] == 5)

# filing-level own-use-any and capability-any by era: k of n, unweighted and weighted
FL = R["filing_level"]["majority"]
for e in ERAS:
    sel = [f for f in fil if f["year"] in ERAS[e] and f["rows"]]
    k_o = sum(1 for f in sel if any(r["own_majority"] is True for r in f["rows"]))
    k_c = sum(1 for f in sel if any(r["class_majority"] == "capability" for r in f["rows"]))
    wsum = sum(w_of[f["year"]] for f in sel)
    wo = sum(w_of[f["year"]] for f in sel if any(r["own_majority"] is True for r in f["rows"])) / wsum
    wc = sum(w_of[f["year"]] for f in sel if any(r["class_majority"] == "capability" for r in f["rows"])) / wsum
    E = FL["era"][e]
    cond(f"recompute own-any {e}", k_o == E["own_use_any"]["k"] and len(sel) == E["n_filings"] and abs(wo - E["own_use_any"]["estimate"]) < 1e-9, f"{k_o}/{len(sel)} {wo}")
    cond(f"recompute cap-any {e}", k_c == E["capability_any"]["k"] and abs(wc - E["capability_any"]["estimate"]) < 1e-9, f"{k_c} {wc}")
ok("own any eras", f"is {pct(FL['era']['2015-2019']['own_use_any'])}, {pct(FL['era']['2020-2023']['own_use_any'])} and {pct(FL['era']['2024-2026']['own_use_any'])} percent")
ok("abstract eras", f"{pct(FL['era']['2015-2019']['own_use_any'])}, {pct(FL['era']['2020-2023']['own_use_any'])} and {pct(FL['era']['2024-2026']['own_use_any'])} percent across the three eras")

# corpus-level counts quoted in the conclusion
n_cap = sum(1 for f in fil for r in f["rows"] if r["class_majority"] == "capability")
n_use_nocap = sum(1 for f in fil for r in f["rows"] if r["own_majority"] is True and r["class_majority"] != "capability")
f_cap = sum(1 for f in fil if any(r["class_majority"] == "capability" for r in f["rows"]))
f_use_nocap = sum(1 for f in fil if f["rows"] and any(r["own_majority"] is True for r in f["rows"]) and not any(r["class_majority"] == "capability" for r in f["rows"]))
f_use = sum(1 for f in fil if any(r["own_majority"] is True for r in f["rows"]))
cond("recompute use-without-capability", n_use_nocap == R["corpus"]["sentences_use_without_capability"] and f_use_nocap == R["corpus"]["filings_use_without_capability"])
cond("use filings arithmetic", f_use - f_cap == f_use_nocap, f"{f_use} {f_cap} {f_use_nocap}")
ok("conclusion counts", f"{n_cap} sentences against {n_use_nocap} and {f_cap} filings against {f_use_nocap}, but the {f_use_nocap} filings")
cond("capability leads", n_cap > n_use_nocap and f_cap > f_use_nocap)
# unweighted overall fractions quoted in 5.3
cond("unweighted overall", abs(f_use / n_with - FL["overall"]["own_use_any_unweighted"]) < 1e-9 and abs(f_cap / n_with - FL["overall"]["capability_any_unweighted"]) < 1e-9)
ok("overall unweighted", f"(the unweighted sample fractions are {pct(FL['overall']['own_use_any_unweighted'])} and {pct(FL['overall']['capability_any_unweighted'])} percent)")
# design weight facts quoted in 3.2
cond("weights 2015", frame["years"]["2015"]["registrants_main_10k"] == 36 and n_samp[2015] == 30)
cond("weights 2026", frame["years"]["2026"]["registrants_main_10k"] == 3710 and n_samp[2026] == 25)
ok("3.2 weights", "It takes 30 of the 36 registrants in the 2015 frame and 25 of the 3,710 in the 2026 frame")
early = sum(n_samp[y] for y in (2015, 2016, 2017)); era1 = sum(n_samp[y] for y in range(2015, 2020))
fr_early = sum(frame["years"][str(y)]["registrants_main_10k"] for y in (2015, 2016, 2017)); fr_era1 = sum(frame["years"][str(y)]["registrants_main_10k"] for y in range(2015, 2020))
cond("two thirds / quarter", 0.6 < early / era1 < 0.67 and fr_early / fr_era1 < 0.25, f"{early/era1:.3f} {fr_early/fr_era1:.3f}")
tot = sum(frame["years"][str(y)]["registrants_main_10k"] for y in range(2015, 2027))
late = sum(frame["years"][str(y)]["registrants_main_10k"] for y in range(2024, 2027))
cond("two thirds of frame is 2024-2026", 0.64 < late / tot < 0.70, f"{late/tot:.3f}")
cond("design weights in analysis", all(abs(R["design_weights"][str(y)] - w_of[y]) < 1e-9 for y in n_samp))
cond("estimand label", "design-weighted" in R.get("estimand", ""))

# ================================================================ universe
U = R["universe"]
ok("raw share 2015", f"{pct(U['2015']['raw_share'], 2)} percent in 2015")
ok("raw share 2025", f"{pct(U['2025']['raw_share'], 1)} percent in 2025")
ok("raw share 2026", f"{pct(U['2026']['raw_share'], 1)} percent of the filings made in 2026")
ok("growth", f"a {round(R['raw_share_growth_2015_2025']):d}-fold increase")
for y in range(2015, 2027):
    u = U[str(y)]
    label = f"{y} to 18 Oct" if y == 2026 else str(y)
    ok(f"table1 {y}", f"| {label} | {num(u['frame'])} | {num(u['all_10k'])} | {pct(u['raw_share'], 2)}% |")
ok("frame total", f"{num(R['frame_total_filings'])} filings out of {num(R['all_10k_total'])} 10-Ks")
ok("2025 restricted frame", f"{num(U['2025']['frame'])} original filings from {num(U['2025']['registrants'])} registrants")
cond("3,324 raw hits", frame["years"]["2025"]["reported_total_hits"] == 3324); ok("3,324 text", "turns 3,324 raw hits")
ok("2023 raw", f"{pct(U['2023']['raw_share'], 1)} percent in 2023")
ok("2024 raw", f"{pct(U['2024']['raw_share'], 1)} percent in 2024")
cond("one in two hundred", 0.004 < U["2015"]["raw_share"] < 0.0055); ok("intro 2015", "fewer than one filing in two hundred")
cond("nearly one in two", 0.45 < U["2025"]["raw_share"] < 0.5); ok("intro 2025", "nearly one in two did in 2025")
cond("three in five", 0.58 < U["2026"]["raw_share"] < 0.62); ok("intro 2026", "three in five have so far in 2026")

# ================================================================ corpus
C = R["corpus"]
ok("filings", f"{C['filings']} filings from {C['registrants']} distinct registrants")
sample = json.load(open(os.path.join(BASE, "data", "sample_filings.json")))
srows = sample["filings"] if isinstance(sample, dict) and "filings" in sample else sample
if isinstance(srows, list):
    ciks = Counter(r["cik"] for r in srows)
    cond("29 multi-year", sum(1 for v in ciks.values() if v > 1) == 29 and len(ciks) == 281, f"{len(ciks)} {sum(1 for v in ciks.values() if v > 1)}")
    cond("30/25 allocation", all(Counter(r["year"] for r in srows)[y] == (30 if y <= 2017 else 25) for y in range(2015, 2027)))
ok("29 text", "29 of which were drawn in more than one year")
ok("seed", "seed 20261018"); cond("seed value", R["seed"] == 20261018); cond("reps", R["reps"] == 10000); ok("reps text", "10,000 replicates")
ok("extracted", f"yielded {num(C['extracted'])} sentences")
ok("candidates", f"found {C['term_audit']['candidates']} candidates: {C['term_audit']['by_screen']['A_name_only']}")
ok("removed", f"confirmed {C['removed_non_ai']} as containing no reference")
cond("448 C3.ai", any(f["name"].lower().startswith("c3") and len(f2["ai_sentences"]) == 448 for f, f2 in zip(fil, sents["filings"])), "448")
ok("448 text", "contributed 448 extracted sentences")
cond("kept nine", C["term_audit"]["candidates"] - C["removed_non_ai"] == 9); ok("nine text", "kept nine")
ok("median max", f"a median of {C['median_per_filing']} per filing and a maximum of {C['max_per_filing']}")
ok("largest share", f"{pct(C['largest_filer_share'], 1)} percent of the corpus")
cond("one fourteenth", 1 / 15 < C["largest_filer_share"] < 1 / 14); ok("fourteenth text", "one fourteenth of the corpus")
cond("aromatase three", len(C["aromatase_sentences"]) == 3); ok("aromatase text", "three sentences in two filings")
ok("disputed either", f"{C['disputed_either']} in all")
ok("unresolved", "leaving five with" if C['unresolved_after_third'] == 5 else f"leaving {C['unresolved_after_third']} with")
spf = C["sentences_per_filing_by_era_weighted"]; med = C["sentences_per_filing_by_era_median"]
ok("spf mean row", f"| mean sentences per filing | {spf['2015-2019']:.1f} | {spf['2020-2023']:.1f} | {spf['2024-2026']:.1f} |")
ok("spf median row", f"| median sentences per filing | {med['2015-2019']:.0f} | {med['2020-2023']:.0f} | {med['2024-2026']:.0f} |")
ok("spf excl", f"falls to {C['sentences_per_filing_by_era_excl_largest']['2020-2023']:.1f} without the C3.ai filing")
ok("spf text", f"carried {spf['2015-2019']:.1f} AI sentences on average in 2015 to 2019 and {spf['2024-2026']:.1f} in 2024 to 2026, with medians of {med['2015-2019']:.0f} and {med['2024-2026']:.0f}")

# ================================================================ agreement
ok("agree n", f"the same class {num(A['class']['n_agree'])} times")
ok("agree pct", f"observed agreement of {pct(A['class']['observed_agreement'])} percent")
ok("alpha", f"Krippendorff alpha of {A['class']['krippendorff_alpha']:.3f}")
ok("own agree", f"agreed {pct(A['own_use']['observed_agreement'])} percent of the time with an alpha of {A['own_use']['krippendorff_alpha']:.3f}")
ok("disagreements", f"Of the {C['disputed_class']} class disagreements, {A['class']['disagreement_pairs']['capability vs other']} are capability")
ok("market vs other", f"and {A['class']['disagreement_pairs']['market vs other']} are market against other")
ok("controls", f"All {A['controls']['n_judgements']} judgements on the {A['controls']['n_controls']} known-answer controls were correct")
lo30 = wilson(A["controls"]["n_controls"], A["controls"]["n_controls"])[0]
ok("controls wilson n=30", f"the Wilson lower limit on accuracy is {pct(lo30)} percent, so the error rate on sentences with a fixed answer is below {pct(1 - lo30)} percent")
tp = C["third_pass"]
ok("third filler", f"{tp['filler_class_agree']} times on class and {tp['filler_own_agree']} times on own use")
ok("third resolved", f"resolved {tp['disputed_resolved_class']} of the {tp['disputed_n']} disputed")
ok("era cue share", f"{pct(A['era_cue']['share'])} percent of sentences carry such a cue")
ok("era cue agr", f"agreement on them was {pct(A['era_cue']['agreement_with_cue'])} percent against {pct(A['era_cue']['agreement_without'])} percent")
ok("name leak", f"{pct(A['name_leak']['share'])} percent of sentences, with agreement of {pct(A['name_leak']['agreement_with_leak'])} percent against {pct(A['name_leak']['agreement_without'])}")
comp = json.load(open(os.path.join(BASE, "data", "companion_values.json")))
ok("companion agreement", f"against {pct(comp['observed_agreement'])} percent and {comp['krippendorff_alpha']:.3f} in the companion")
ok("six identities", "two of six rater identities by cycling the fifteen rater pairs"); ok("batches", "batches of fifty")
ok("130 displays", "for all 130 displays"); cond("130", R["calibration"]["n_displays"] == 130 and R["calibration"]["n_units"] == 120)

# ================================================================ composition text
E1, E2, E3 = CM["2015-2019"], CM["2020-2023"], CM["2024-2026"]
ok("abstract risk", f"rose from {pct(E1['risk'])} percent in 2015 to 2019 to {pct(E3['risk'])} percent in 2024 to 2026")
ok("abstract cap", f"fell from {pct(E1['capability'])} to {pct(E3['capability'])} percent")
ok("abstract own", f"fell from {pct(E1['own_use'])} to {pct(E3['own_use'])} percent")
ok("sec52 2015-19", f"devoted {pct(E1['capability'])} percent of its AI sentences to claims about its own AI's capability, {pct(E1['other'])} percent to other, {pct(E1['market'])} percent to the market and {pct(E1['risk'])} percent to risk")
ok("sec52 2024-26", f"devotes {pct(E3['risk'])} percent to risk, {pct(E3['capability'])} percent to capability, {pct(E3['market'])} percent to the market and {pct(E3['other'])} percent to other")
ok("governance late", f"reaches {pct(E3['governance'])} percent")
EC = R["era_contrasts"]["majority"]["filing"]
ok("risk contrast", f"rose by {pct(EC['risk_late_minus_early']['estimate'])} percentage points with a bootstrap interval from {pct(EC['risk_late_minus_early']['lo'])} to {pct(EC['risk_late_minus_early']['hi'])}")
ok("abstract contrast", f"a change of {pct(EC['risk_late_minus_early']['estimate'])} percentage points with a bootstrap interval from {pct(EC['risk_late_minus_early']['lo'])} to {pct(EC['risk_late_minus_early']['hi'])}")
ok("cap contrast", f"fell by {pct(-EC['capability_late_minus_early']['estimate'])} points (interval {pct(-EC['capability_late_minus_early']['hi'])} to {pct(-EC['capability_late_minus_early']['lo'])})")
ok("own contrast", f"a drop of {pct(-EC['own_use_late_minus_early']['estimate'])} points ({pct(-EC['own_use_late_minus_early']['hi'])} to {pct(-EC['own_use_late_minus_early']['lo'])})")
T = R["trend"]["majority"]
ok("spearman risk", f"the yearly risk share is {T['spearman_year_vs_risk_share_filingweighted']['rho']:.3f}")
for name, verb in (("logit_risk_on_year", "rise by a factor of"), ("logit_capability_on_year", "fall by a factor of"), ("logit_own_use_on_year", "fall by")):
    t = T[name]
    ok(f"OR {name}", f"{verb} {t['odds_ratio_per_year']:.2f}")
    ok(f"OR interval {name}", f"{t['odds_ratio_lo']:.2f} to {t['odds_ratio_hi']:.2f})")
CS = R["composition"]["majority"]["sentence"]["era"]; ECS = R["era_contrasts"]["majority"]["sentence"]
ok("sentence risk", f"rises from {pct(CS['2015-2019']['risk'])} to {pct(CS['2024-2026']['risk'])} percent (a change of {pct(ECS['risk_late_minus_early']['estimate'])} points, interval {pct(ECS['risk_late_minus_early']['lo'])} to {pct(ECS['risk_late_minus_early']['hi'])})")
ok("sentence own", f"falls from {pct(CS['2015-2019']['own_use'])} to {pct(CS['2024-2026']['own_use'])} percent ({pct(-ECS['own_use_late_minus_early']['estimate'])} points, interval {pct(ECS['own_use_late_minus_early']['hi'])} up to {pct(-ECS['own_use_late_minus_early']['lo'])} down")
cond("sentence own includes zero", ECS["own_use_late_minus_early"]["hi"] > 0 and ECS["own_use_late_minus_early"]["lo"] < 0)
CA = R["composition"]["agreed"]["filing"]["era"]
mx = max(abs(CA[e][k]["estimate"] - CM[e][k]["estimate"]) for e in CA for k in CLASSES + ["own_use"])
cond("agreed within four points", mx <= 0.04, f"{mx:.3f}")
mix = R["sector"]["frame_sector_mix_by_era"]
ok("frame mix", f"were {round(mix['2015-2019']['technology'] * 100)} percent of the frame in 2015 to 2019 and {round(mix['2024-2026']['technology'] * 100)} percent in 2024 to 2026")
S = R["sector"]["majority"]
ok("sector cap", f"capability share is {pct(S['technology']['capability_share_filing']['estimate'])} percent at technology registrants against {pct(S['finance_realestate']['capability_share_filing']['estimate'])} percent in finance and real estate, and the risk share is {pct(S['technology']['risk_share_filing']['estimate'])} percent against {pct(S['finance_realestate']['risk_share_filing']['estimate'])}")
ratio = E3["risk"]["estimate"] / E3["capability"]["estimate"]
cond("four to one", 3.6 <= ratio <= 4.4, f"{ratio:.2f}")
ok("6.1 shares", f"{pct(E3['risk'], 0)} percent of the AI sentences are risk language and {pct(E3['capability'], 0)} percent are capability claims, a ratio of four to one")
ok("6.1 sentence shares", f"the shares are {pct(CS['2024-2026']['risk'], 0)} and {pct(CS['2024-2026']['capability'], 0)} percent")
ok("6.1 own shares", f"{pct(E3['own_use'], 0)} and {pct(CS['2024-2026']['own_use'], 0)} percent")
cond("own > cap both bases", E3["own_use"]["estimate"] > E3["capability"]["estimate"] and CS["2024-2026"]["own_use"]["estimate"] > CS["2024-2026"]["capability"]["estimate"])
cond("about half of volume", 0.44 <= CS["2024-2026"]["risk"]["estimate"] <= 0.52)
ok("6.2 63 percent", f"{pct(E3['risk'], 0)} percent of a filing's AI sentences are now risk factors")
ok("intro fractions", "two fifths of its AI sentences describing what its own AI did and one in eight describing risk")
cond("two fifths / one in eight", 0.37 < E1["capability"]["estimate"] < 0.43 and 0.11 < E1["risk"]["estimate"] < 0.135)
cond("one sixth / two thirds", 0.14 < E3["capability"]["estimate"] < 0.19 and 0.60 < E3["risk"]["estimate"] < 0.67)
ok("conclusion shares", f"rose from twelve percent to sixty-three percent, the share that claims a capability fell from two fifths to one sixth, and the share that states any use by the filer fell from {pct(E1['own_use'], 0)} to {pct(E3['own_use'], 0)} percent")
cond("twelve / sixty-three", round(E1["risk"]["estimate"] * 100) == 12 and round(E3["risk"]["estimate"] * 100) == 63)

# ================================================================ filing level
ok("own any overall", f"{pct(FL['overall']['own_use_any']['estimate'])} percent do (interval {pct(FL['overall']['own_use_any']['lo'])} to {pct(FL['overall']['own_use_any']['hi'])})")
ok("cap any overall", f"and {pct(FL['overall']['capability_any']['estimate'])} percent make at least one capability claim")
d = FL["own_any_late_minus_early"]
ok("own any diff", f"difference is {pct(-d['estimate'])} points with an interval from {pct(-d['lo'])} points down to {pct(d['hi'])} points up")
ok("spearman own any", f"is negative {abs(T['spearman_year_vs_filing_own_any']['rho']):.2f} with p = {T['spearman_year_vs_filing_own_any']['p']:.2f}")
dc = FL["cap_any_late_minus_early"]
ok("cap any diff", f"from {pct(FL['era']['2015-2019']['capability_any']['estimate'])} to {pct(FL['era']['2024-2026']['capability_any']['estimate'])} percent, but the interval on the difference runs from {pct(-dc['lo'])} points down to {pct(dc['hi'])} points up")
cond("cap any includes zero", dc["hi"] > 0 > dc["lo"])
yrs = FL["year"]
lo_y = min(v["own_use_any"]["estimate"] for v in yrs.values()); hi_y = max(v["own_use_any"]["estimate"] for v in yrs.values())
ok("yearly range", f"sit between {int(lo_y * 100)} and {int(hi_y * 100)} percent on {min(v['n_filings'] for v in yrs.values())} to {max(v['n_filings'] for v in yrs.values())} filings")
los = [v["own_use_any"]["wilson"][0] for v in yrs.values()]; his = [v["own_use_any"]["wilson"][1] for v in yrs.values()]
cond("wilson overlap", max(los) <= min(his)); ok("overlap text", "Wilson intervals all overlap")
widths = [100 * (v["own_use_any"]["wilson"][1] - v["own_use_any"]["wilson"][0]) for v in yrs.values()]
import math
ok("widths", f"between {math.floor(min(widths))} and {math.ceil(max(widths))} points wide")
cond("three in five", 0.56 < FL["overall"]["own_use_any"]["estimate"] < 0.68 and all(0.56 < FL["era"][e]["own_use_any"]["estimate"] < 0.76 for e in ERAS))
y25 = yrs["2025"]
ok("2025 own", f"an estimated {pct(y25['corrected_own_use']['estimate'])} percent (interval {pct(y25['corrected_own_use']['lo'])} to {pct(y25['corrected_own_use']['hi'])}) contained an own-use statement")
ok("2025 cap", f"and {pct(y25['corrected_capability']['estimate'])} percent ({pct(y25['corrected_capability']['lo'])} to {pct(y25['corrected_capability']['hi'])}) contained a capability claim")
ok("2025 k", f"uses the 2025 draw's own fraction, {y25['own_use_any_k']} of {y25['n_filings']} filings, which is the lowest of the twelve years")
cond("2025 lowest", min(yrs, key=lambda y: yrs[y]["own_use_any"]["estimate"]) == "2025")
y26 = yrs["2026"]
ok("abstract 2025/2026", f"at {pct(y25['corrected_own_use']['estimate'])} percent in 2025 (interval {pct(y25['corrected_own_use']['lo'])} to {pct(y25['corrected_own_use']['hi'])}), the year with the lowest sampled fraction, and at {pct(y26['corrected_own_use']['estimate'])} percent ({pct(y26['corrected_own_use']['lo'])} to {pct(y26['corrected_own_use']['hi'])}) in 2026, against raw shares of {pct(U['2025']['raw_share'])} and {pct(U['2026']['raw_share'])}")
ER = FL["era"]
ok("pooled raw", f"the raw share was {pct(ER['2015-2019']['raw_share_pooled'], 2)}, {pct(ER['2020-2023']['raw_share_pooled'])} and {pct(ER['2024-2026']['raw_share_pooled'])} percent and the own-use share {pct(ER['2015-2019']['corrected_own_use_pooled']['estimate'])}, {pct(ER['2020-2023']['corrected_own_use_pooled']['estimate'])} and {pct(ER['2024-2026']['corrected_own_use_pooled']['estimate'])} percent")
ok("overst eras", f"is {ER['2015-2019']['overstatement_factor']:.2f} (interval {ER['2015-2019']['overstatement_factor_interval'][0]:.2f} to {ER['2015-2019']['overstatement_factor_interval'][1]:.2f}) in 2015 to 2019, {ER['2020-2023']['overstatement_factor']:.2f} ({ER['2020-2023']['overstatement_factor_interval'][0]:.2f} to {ER['2020-2023']['overstatement_factor_interval'][1]:.2f}) in 2020 to 2023 and {ER['2024-2026']['overstatement_factor']:.2f} ({ER['2024-2026']['overstatement_factor_interval'][0]:.2f} to {ER['2024-2026']['overstatement_factor_interval'][1]:.2f}) in 2024 to 2026")
od = FL["overstatement_late_minus_early"]
ok("overst diff", f"runs from {abs(od['lo']):.2f} down to {od['hi']:.2f} up and {round(od['share_positive'] * 100)} percent of bootstrap replicates are positive")
cond("equal to second decimal", round(ER["2024-2026"]["overstatement_factor"], 2) - round(ER["2015-2019"]["overstatement_factor"], 2) <= 0.01)
facs = [ER[e]["overstatement_factor"] for e in ERAS]
cond("factor 1.4 to 1.6", 1.35 <= min(facs) and max(facs) <= 1.65, f"{facs}")
span = (min(ER[e]["overstatement_factor_interval"][0] for e in ERAS), max(ER[e]["overstatement_factor_interval"][1] for e in ERAS))
ok("span", f"era intervals that together span {span[0]:.2f} to {span[1]:.2f}")
ok("cap factor", f"the capability factor is {1 / ER['2024-2026']['capability_any']['estimate']:.1f} in 2024 to 2026 against {1 / ER['2015-2019']['capability_any']['estimate']:.1f} in 2015 to 2019")
for y in ["2015", "2018", "2021", "2023", "2024", "2025", "2026"]:
    v = yrs[y]
    ok(f"table3 {y}", f"| {y} | {pct(v['raw_share'], 2)} | {pct_ci(v['corrected_own_use'], 2)} | {pct_ci(v['corrected_capability'], 2)} | {v['n_filings']} |")
K = R["calibration"]
cond("own false survival < true", K["own_use"]["false_rate"] < K["own_use"]["true_rate"])

# ================================================================ phrase reuse
P = R["phrase_reuse"]; PM = P["majority"]
ok("queried", f"All {num(P['n_queried'])} corpus sentences were queried without error, {pct(P['self_hit_rate'])} percent found their own filing, and {P['n_zero_hits']} returned no hit")
ok("usable", f"leaves {num(P['n_usable'])} sentences in the reuse analysis")
ok("share zero", f"For {pct(P['overall']['share_zero'])} percent of them")
ok("share flagged", f"{'Five' if round(P['overall']['share_flagged'] * 100) == 5 else pct(P['overall']['share_flagged'], 0)} percent are shared with five or more")
cond("one percent ge30", 0.5 <= P["overall"]["share_ge30"] * 100 < 1.5); ok("ge30 text", "one percent with thirty or more")
ok("max reuse", f"up to a maximum of {P['overall']['max']}")
ok("L8", f"from {pct(P['overall']['share_flagged'])} to {pct(P['L8_sensitivity']['share_flagged'])} percent")
cond("85 percent", round(P["overall"]["share_zero"] * 100) == 85); ok("85 text", "85 percent of twelve-word AI phrases are unique to their filer")
bc = PM["by_class"]
ok("cap reuse", f"Of {bc['capability']['n']} capability sentences, none is shared with five or more other registrants and {pct(bc['capability']['share_zero'])} percent are shared with none")
ok("cap wilson", f"Wilson upper bound of {pct(bc['capability']['share_flagged_wilson'][1])} percent on capability")
ok("risk reuse", f"Of {bc['risk']['n']} risk sentences, {bc['risk']['flagged']}, or {pct(bc['risk']['share_flagged'])} percent (interval {pct(bc['risk']['share_flagged_wilson'][0])} to {pct(bc['risk']['share_flagged_wilson'][1])}), are flagged and {pct(1 - bc['risk']['share_zero'])} percent are shared with at least one")
ok("risk q90", f"90th percentile of {'twelve' if bc['risk']['q90'] == 12 else bc['risk']['q90']} other registrants")
ok("market other flag", f"flagged at {pct(bc['market']['share_flagged'])} and {pct(bc['other']['share_flagged'])} percent")
ok("flag precision risk", f"{pct(PM['flag_precision_for_risk'])} percent of flagged sentences are risk sentences and {pct(PM['flag_recall_for_risk'])} percent of risk sentences are flagged")
ok("auc", f"area under the curve of {PM['auc_flag_predicts_not_own_use']:.2f}")
t5 = PM["thresholds"]["5"]
ok("own-use precision recall", f"{pct(t5['precision'])} percent of flagged sentences are not own-use statements and {pct(t5['recall'])} percent of non-own-use sentences are flagged")
ok("L8 by class", f"flags {pct(P['L8_sensitivity']['flag_by_class']['risk'])} percent of risk sentences and {pct(P['L8_sensitivity']['flag_by_class']['capability'])} percent of capability sentences")
fe = PM["flagged_share_era_filingweighted"]; fd = PM["flagged_share_late_minus_early_filingweighted"]; fds = PM["flagged_share_late_minus_early"]
ok("flag eras", f"is {pct(fe['2015-2019']['estimate'])} percent in 2015 to 2019, {pct(fe['2020-2023']['estimate'])} percent in 2020 to 2023 and {pct(fe['2024-2026']['estimate'])} percent in 2024 to 2026 (interval {pct(fe['2024-2026']['lo'])} to {pct(fe['2024-2026']['hi'])})")
ok("flag rise", f"a rise of {pct(fd['estimate'])} points (interval {pct(fd['lo'])} to {pct(fd['hi'])}), and weighting sentences equally the rise is {pct(fds['estimate'])} points ({pct(fds['lo'])} to {pct(fds['hi'])})")
ok("abstract flag", f"rose from zero in 2015 to 2019 to {pct(fe['2024-2026']['estimate'])} percent in 2024 to 2026")
cond("flag era1 zero", fe["2015-2019"]["estimate"] == 0.0)
ok("abstract risk flagged", f"{pct(bc['risk']['share_flagged'])} percent of risk sentences are shared with five or more other registrants against none of {bc['capability']['n']} capability sentences")
top = P["top_reused"]
ok("top1", f"generative AI ({top[0]['reuse_ciks']} other registrants)")
ok("top2", f"deficient or biased ({top[1]['reuse_ciks']})")
ok("top3", f"competitors incorporating AI faster ({top[2]['reuse_ciks']})")
ok("top5", f"AI ethics controversy ({top[4]['reuse_ciks']})")
ok("top6", f"AI regulation ({top[5]['reuse_ciks']})")
nonrisk = [t for t in top if t["class"] != "risk"]
cond("top twelve non-risk", len(nonrisk) == 2 and all("collectively" in t["text"] for t in nonrisk) and all(t["class"] == "market" for t in nonrisk))
rs = R["composition"]["majority"]["sentence"]["overall"]["risk"]["estimate"] / PM["flagged_share_overall"]["estimate"]
cond("about five times", 4.3 <= rs <= 5.7, f"{rs:.2f}"); ok("five times text", "about five times as much risk language")
cond("less than a fifth", PM["flag_recall_for_risk"] < 0.2); cond("96 precision", round(PM["flag_precision_for_risk"] * 100) == 96); ok("96 text", "risk factor with 96 percent precision")

# ================================================================ sector and size
ok("tech own", f"{pct(S['technology']['own_use_any']['estimate'])} percent of technology registrants' AI-mentioning filings state their own use of AI ({S['technology']['own_use_any']['k']} of {S['technology']['n_filings_with_sentences']} in the sample, interval {pct(S['technology']['own_use_any']['lo'])} to {pct(S['technology']['own_use_any']['hi'])})")
ok("health own", f"against {pct(S['healthcare']['own_use_any']['estimate'])} percent in healthcare ({S['healthcare']['own_use_any']['k']} of {S['healthcare']['n_filings_with_sentences']})")
ok("finance own", f"{pct(S['finance_realestate']['own_use_any']['estimate'])} percent in finance and real estate ({S['finance_realestate']['own_use_any']['k']} of {S['finance_realestate']['n_filings_with_sentences']})")
ok("other own", f"{pct(S['other']['own_use_any']['estimate'])} percent in everything else ({S['other']['own_use_any']['k']} of {S['other']['n_filings_with_sentences']})")
ok("sector unweighted", f"The unweighted sample fractions are {pct(S['technology']['own_use_any']['unweighted'])}, {pct(S['healthcare']['own_use_any']['unweighted'])}, {pct(S['finance_realestate']['own_use_any']['unweighted'])} and {pct(S['other']['own_use_any']['unweighted'])} percent")
ok("finance interval", f"its interval of {pct(S['finance_realestate']['own_use_any']['lo'])} to {pct(S['finance_realestate']['own_use_any']['hi'])}")
td = S["tech_minus_rest_own_any"]
ok("tech diff", f"is {pct(td['estimate'])} points with an interval from {pct(td['lo'])} to {pct(td['hi'])}")
RU = json.load(open(os.path.join(BASE, "results", "analysis_unweighted.json")))
tdu = RU["sector"]["majority"]["tech_minus_rest_own_any"]
ok("tech diff unweighted", f"({pct(tdu['estimate'])} points, {pct(tdu['lo'])} to {pct(tdu['hi'])}, unweighted)")
cond("unweighted file label", "pooled sample" in RU.get("estimand", ""))
for k in ("technology", "healthcare", "finance_realestate", "other"):
    cond(f"unweighted sector {k}", abs(RU["sector"]["majority"][k]["own_use_any"]["estimate"] - S[k]["own_use_any"]["unweighted"]) < 1e-9)
Z = R["size"]
ok("size n", f"available for {Z['n_with_assets']} of {C['filings']} filings")
ok("size own", f"({pct(Z['own_use_any_large']['estimate'])} percent above the median of about one billion dollars against {pct(Z['own_use_any_small']['estimate'])} percent below, difference {pct(-Z['large_minus_small_own_any']['estimate'])} points, interval {pct(-Z['large_minus_small_own_any']['lo'])} down to {pct(Z['large_minus_small_own_any']['hi'])} up)")
ok("size risk", f"risk share is {pct(Z['risk_share_filing_large']['estimate'])} percent at larger registrants (interval {pct(Z['risk_share_filing_large']['lo'])} to {pct(Z['risk_share_filing_large']['hi'])}) and {pct(Z['risk_share_filing_small']['estimate'])} percent at smaller ones ({pct(Z['risk_share_filing_small']['lo'])} to {pct(Z['risk_share_filing_small']['hi'])}), a difference of {pct(Z['large_minus_small_risk_share']['estimate'])} points ({pct(Z['large_minus_small_risk_share']['lo'])} to {pct(Z['large_minus_small_risk_share']['hi'])})")
cond("median assets", 0.9e9 <= Z["median_assets_usd"] <= 1.1e9)

# ================================================================ calibration
sv = K["survival_by_class"]
cond("duplicates consistent", K["duplicates"]["n"] == 10 and K["duplicates"]["class_consistent"] == 10 and K["duplicates"]["own_consistent"] == 10)
ok("dup", "consistent with itself on all ten duplicate controls")
ok("survival overall", f"Of {K['n_units']} majority verdicts, {sum(s['survived'] for s in sv.values())} survived review, {pct(K['overall_survival'])} percent")
ok("surv risk", f"{pct(sv['risk']['rate'])} percent of risk calls ({sv['risk']['survived']} of {sv['risk']['n']})")
ok("surv other", f"{pct(sv['other']['rate'])} percent of other ({sv['other']['survived']} of {sv['other']['n']})")
ok("surv market", f"{pct(sv['market']['rate'])} percent of market ({sv['market']['survived']} of {sv['market']['n']})")
ok("surv cap", f"{pct(sv['capability']['rate'])} percent of capability ({sv['capability']['survived']} of {sv['capability']['n']})")
ok("surv gov", f"{pct(sv['governance']['rate'])} percent of governance ({sv['governance']['survived']} of {sv['governance']['n']})")
ok("own surv", f"survived at {pct(K['own_use']['true_rate'])} percent when true and {pct(K['own_use']['false_rate'])} percent when false")
se = K["survival_by_era"]
ok("surv era", f"Survival was {pct(se['2015-2019']['rate'])} percent in the first era, {pct(se['2020-2023']['rate'])} in the second and {pct(se['2024-2026']['rate'])} in the third")
tm = K["transfer_matrix"]
cond("four capability to other", abs(tm["capability"].get("other", 0) - (sv["capability"]["n"] - sv["capability"]["survived"]) / sv["capability"]["n"]) < 1e-9 and sv["capability"]["n"] - sv["capability"]["survived"] == 4)
n_gov = sum(1 for f in fil for r in f["rows"] if r["class_majority"] == "governance")
ok("governance count", f"the smallest class at {n_gov} of {num(sum(CM[e]['n_sentences'] for e in ERAS))} resolved sentences")
CAL = R["calibrated"]["filing"]
ok("cal cap", f"capability share from {pct(E1['capability'])} to {pct(CAL['2015-2019']['capability']['estimate'])} percent (interval {pct(CAL['2015-2019']['capability']['lo'])} to {pct(CAL['2015-2019']['capability']['hi'])}) in the first era and from {pct(E3['capability'])} to {pct(CAL['2024-2026']['capability']['estimate'])} ({pct(CAL['2024-2026']['capability']['lo'])} to {pct(CAL['2024-2026']['capability']['hi'])}) in the last")
ok("cal own", f"own-use share from {pct(E1['own_use'])} to {pct(CAL['2015-2019']['own_use']['estimate'])} ({pct(CAL['2015-2019']['own_use']['lo'])} to {pct(CAL['2015-2019']['own_use']['hi'])}) and from {pct(E3['own_use'])} to {pct(CAL['2024-2026']['own_use']['estimate'])} ({pct(CAL['2024-2026']['own_use']['lo'])} to {pct(CAL['2024-2026']['own_use']['hi'])})")
ok("cal risk", f"from {pct(E1['risk'])} to {pct(CAL['2015-2019']['risk']['estimate'])} ({pct(CAL['2015-2019']['risk']['lo'])} to {pct(CAL['2015-2019']['risk']['hi'])}) and from {pct(E3['risk'])} to {pct(CAL['2024-2026']['risk']['estimate'])} ({pct(CAL['2024-2026']['risk']['lo'])} to {pct(CAL['2024-2026']['risk']['hi'])})")
cc = R["calibrated"]
ok("cal contrasts", f"are {pct(cc['risk_late_minus_early_filing'])} points for risk (interval {pct(cc['risk_late_minus_early_filing']['lo'])} to {pct(cc['risk_late_minus_early_filing']['hi'])}), {pct(-cc['capability_late_minus_early_filing']['estimate'])} points for capability ({pct(-cc['capability_late_minus_early_filing']['hi'])} to {pct(-cc['capability_late_minus_early_filing']['lo'])}) and {pct(-cc['own_use_late_minus_early_filing']['estimate'])} points for own use ({pct(-cc['own_use_late_minus_early_filing']['hi'])} to {pct(-cc['own_use_late_minus_early_filing']['lo'])})")
cond("cal contrasts exclude zero", cc["risk_late_minus_early_filing"]["lo"] > 0 and cc["capability_late_minus_early_filing"]["hi"] < 0 and cc["own_use_late_minus_early_filing"]["hi"] < 0)

# ================================================================ replication
RP = R["replication_2025"]
ok("rep risk", f"risk share of {pct(RP['risk_sentence_agreed']['estimate'])} percent (interval {pct(RP['risk_sentence_agreed']['lo'])} to {pct(RP['risk_sentence_agreed']['hi'])})")
ok("rep cap", f"capability share of {pct(RP['capability_sentence_agreed']['estimate'])} percent ({pct(RP['capability_sentence_agreed']['lo'])} to {pct(RP['capability_sentence_agreed']['hi'])})")
ok("rep companion", f"The companion's {comp['n_filings']} filings with corpus sentences gave {pct(comp['agreed_basis']['risk'])} and {pct(comp['agreed_basis']['capability'])} percent on the same agreed basis before calibration and {pct(comp['calibrated']['risk'])} and {pct(comp['calibrated']['capability'])} after it")
ok("rep filing", f"risk share here is {pct(RP['risk_filing_majority']['estimate'])} percent and the capability share {pct(RP['capability_filing_majority']['estimate'])} percent")
cond("companion inside intervals", RP["risk_sentence_agreed"]["lo"] <= comp["calibrated"]["risk"] <= RP["risk_sentence_agreed"]["hi"] and RP["capability_sentence_agreed"]["lo"] <= comp["calibrated"]["capability"] <= RP["capability_sentence_agreed"]["hi"])
cond("about twice", 1.7 <= RP["capability_sentence_agreed"]["estimate"] / comp["calibrated"]["capability"] <= 2.5)
ok("19 of 59", f"the companion's finding that {comp['filings_with_capability_claim']} of {comp['n_filings']} filings contained a capability claim")
ok("13 percent transfer", f"a {round(tm['capability']['other'] * 100)} percent transfer out of capability and the companion reported as {round(comp['capability_transfer_out'] * 100)} percent too")
ok("companion 60 reports", "60 annual reports filed in 2025")
ok("rep thin", f"25 of {num(U['2025']['registrants'])} registrants")

# ================================================================ predictions
PR = R["predictions"]
p3 = PR["3_under_60pct_filings_own_use_late"]
ok("p3", f"{p3['k']} of {FL['era']['2024-2026']['n_filings']} did, {pct(p3['unweighted'])} percent, with a Wilson interval from {pct(p3['wilson_unweighted'][0])} to {pct(p3['wilson_unweighted'][1])}")
cond("p3 failed", not p3["holds_point"] and p3["unweighted"] >= 0.60)
ok("p1", f"held by {round(PR['1_risk_share_higher_late']['estimate'] * 100)} points")
cond("p1 interval", PR["1_risk_share_higher_late"]["interval_excludes_zero"] and PR["1_and_2_sentence_weighted"]["risk_interval_excludes_zero"])
ok("p2", f"held by {round(-PR['2_own_use_share_lower_late']['estimate'] * 100)} points")
cond("p2 intervals", PR["2_own_use_share_lower_late"]["interval_excludes_zero"] and not PR["1_and_2_sentence_weighted"]["own_use_interval_excludes_zero"])
p4 = PR["4_risk_reuse_vs_capability"]
cond("p4", (not p4["median_criterion_decidable"]) and p4["holds_flag_2x"] and p4["conjunction_holds"] is False)
ok("p4 text", f"held at {pct(p4['flag_risk'])} percent against zero")
ok("p5", f"held by {pct(PR['5_flagged_share_rises']['estimate'])} points filing-weighted and {pct(PR['5_flagged_share_rises']['sentence_weighted']['estimate'])} sentence-weighted")
cond("p5 intervals", PR["5_flagged_share_rises"]["interval_excludes_zero"] and PR["5_flagged_share_rises"]["sentence_weighted"]["lo"] > 0)
p6 = PR["6_overstatement_grows"]
ok("p6", f"the factors are {p6['late']:.2f} and {p6['early']:.2f}, a difference with an interval from {abs(p6['lo']):.2f} below zero to {p6['hi']:.2f} above")
cond("p6 not supported", abs(p6["estimate"]) < 0.02 and not p6["interval_excludes_zero"])
p6u = RU["predictions"]["6_overstatement_grows"]
ok("p6 unweighted", f"Unweighted, the same comparison was {p6u['late']:.2f} against {p6u['early']:.2f}")
ok("p7", f"held by {round(PR['7_tech_higher_own_use']['estimate'] * 100)} points ({round(tdu['estimate'] * 100)} unweighted)")
cond("p7 interval", PR["7_tech_higher_own_use"]["interval_excludes_zero"])
tally = PR["tally"]
cond("tally", tally == {"held_with_interval": 4, "held_point_only": 1, "held_one_of_two_criteria": 1, "failed": 1}, str(tally))
ok("tally text", "four held with intervals clear of zero, one held on one of two criteria, one not supported, and one failed")
ok("abstract tally", "four held with intervals clear of zero, one held on one of its two criteria with the other undecidable, one was not supported, and one failed")
cond("falsification", not PR["falsification_triggered"])
ok("p1 sentence", f"held by {round(PR['1_risk_share_higher_late']['estimate'] * 100)} points with an interval well away from zero")
ok("falsification text", f"because the risk share moved by {round(PR['1_risk_share_higher_late']['estimate'] * 100)} points even though the overstatement did not grow")

# ================================================================ SEC timing
ST = R["sec_action_timing_2024"]
ok("sec split", f"{ST['n_before']} of the {ST['n_before'] + ST['n_after']} sampled 2024 filings were made before that date with a filing-weighted risk share already at {pct(ST['risk_share_filing_before'])} percent, against {pct(ST['risk_share_filing_after'])} percent for the {'six' if ST['n_after'] == 6 else ST['n_after']} made after it")
ok("sec diff", f"difference {round(-ST['after_minus_before']['estimate'] * 100)} points with an interval from {round(-ST['after_minus_before']['lo'] * 100)} down to {round(ST['after_minus_before']['hi'] * 100)} up")

# ================================================================ BTOS
B = json.load(open(os.path.join(BASE, "data", "btos", "btos_ai_use.json")))
latest = sorted(B["q7_yes"]["national"], reverse=True)[0]
ok("btos cycle", "collected from 21 September to 4 October 2026")
cond("btos dates", list(B["dates"][latest]) == ["2026-09-21", "2026-10-04"], str(B["dates"][latest]))
ok("btos national", f"national rate was {B['q7_yes']['national'][latest].rstrip('%')} percent")
ok("btos info", f"Information sector's rate was {B['q7_yes']['sector_51'][latest].rstrip('%')} percent")
sect = {k: float(v[latest].rstrip("%")) for k, v in B["q7_yes"].items() if k.startswith("sector_") and latest in v}
cond("information highest", max(sect, key=sect.get) == "sector_51", str(max(sect, key=sect.get)))
ok("btos corrected 2026", f"corrected own-use share of {pct(yrs['2026']['corrected_own_use']['estimate'])} percent")
cond("2026 between national and information", float(B["q7_yes"]["national"][latest].rstrip("%")) < yrs["2026"]["corrected_own_use"]["estimate"] * 100 < float(B["q7_yes"]["sector_51"][latest].rstrip("%")))

# ================================================================ verbatim quotations
corpus = {}
for f in sents["filings"]:
    for s in f["ai_sentences"]:
        corpus.setdefault(s["text"], []).append((f["name"], f["year"], s["id"]))
quotes = [
    ("ICAD", 2015, "SecondLook detects and identifies suspicious masses and micro-calcifications utilizing image processing, pattern recognition and artificial intelligence techniques."),
    ("CORVEL", 2015, "CorVel's artificial intelligence engine includes over sixty million individual rules, which creates a comprehensive review process that is more efficient than traditional manual bill review processes."),
    ("Olema", 2026, "If we are unable to use generative AI, it could make our business less efficient and result in competitive disadvantages."),
]
reuse = json.load(open(os.path.join(BASE, "data", "phrase_reuse.json")))
for who, yr, q in quotes:
    checks += 1
    if q not in corpus:
        failures.append(f"quotation not in corpus: {q[:50]}")
        continue
    hits = corpus[q]
    if not any(who.lower() in name.lower() and y == yr for name, y, _ in hits):
        failures.append(f"quotation attributed to {who} {yr} but corpus says {hits}")
    if q.rstrip(".") not in PAPER:
        failures.append(f"quotation not in paper: {q[:50]}")
    if who == "Olema" and max(reuse[sid]["reuse_ciks"] for _, _, sid in hits) != top[0]["reuse_ciks"]:
        failures.append("Olema sentence is not the most reused")
ok("olema reuse", f"appears in the 10-Ks of {top[0]['reuse_ciks']} other registrants")

# ================================================================ document hygiene
cond("no em dash", "—" not in PAPER)
prose = [ln for ln in open(os.path.join(BASE, "paper", "paper.md")) if not ln.startswith("  - \\") and "http" not in ln]
cond("no semicolons in prose", not any(";" in ln for ln in prose), "semicolon found")
ok("six amendments", "its six amendments")
cond("no vendor names", not re.search(r"\b(Anthropic|Claude|OpenAI|GPT-?[0-9]|Sonnet|Opus|Gemini)\b", PAPER))

# ================================================================ report
print(f"{checks} checks, {len(failures)} failures")
for f in failures:
    print("  FAIL", f)
sys.exit(1 if failures else 0)
