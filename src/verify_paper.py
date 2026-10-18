"""Recompute every number quoted in paper/paper.md from the committed data and
exit non-zero on any mismatch.

Each check formats a value from results/analysis.json (or the raw data files)
exactly as the paper quotes it and asserts that the formatted string occurs in
the paper text. Verbatim quotations are checked against the corpus and the
registrant that filed them. Run after src/analyze.py.
"""
from __future__ import annotations
import json, os, re, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(BASE, "results", "analysis.json")))
A = R["agreement"]
PAPER = re.sub(r"\s+", " ", open(os.path.join(BASE, "paper", "paper.md")).read())
CLASSES = ["capability", "risk", "market", "governance", "other"]
checks, failures = 0, []


def ok(label, text):
    global checks
    checks += 1
    if text not in PAPER:
        failures.append(f"{label}: expected '{text}' in paper")


def pct(x, d=1):
    if isinstance(x, dict):
        x = x["estimate"]
    return f"{x * 100:.{d}f}"


def pct_ci(dct, d=1):
    return f"{pct(dct['estimate'], d)} ({pct(dct['lo'], d)}, {pct(dct['hi'], d)})"


def num(x):
    return f"{x:,}"


# ---------------------------------------------------------------- universe
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
ok("2023 raw", f"{pct(U['2023']['raw_share'], 1)} percent in 2023")
ok("2024 raw", f"{pct(U['2024']['raw_share'], 1)} percent in 2024")

# ---------------------------------------------------------------- corpus
C = R["corpus"]
ok("filings", f"{C['filings']} filings from {C['registrants']} distinct registrants")
ok("extracted", f"yielded {num(C['extracted'])} sentences")
ok("candidates", f"found {C['term_audit']['candidates']} candidates: {C['term_audit']['by_screen']['A_name_only']}")
ok("removed", f"confirmed {C['removed_non_ai']} as containing no reference")
ok("corpus n", f"leaving {num(C['sentences'])} corpus sentences in {C['filings_with_sentences']} filings")
ok("median max", f"a median of {C['median_per_filing']} per filing and a maximum of {C['max_per_filing']}")
ok("largest share", f"{pct(C['largest_filer_share'], 1)} percent of the corpus")
ok("disputed either", f"{C['disputed_either']} in all")
ok("unresolved", "leaving five with" if C['unresolved_after_third'] == 5 else f"leaving {C['unresolved_after_third']} with")
for e, v in C["by_era"].items():
    ok(f"era filings {e}", f"| filings, sentences | {C['by_era']['2015-2019']['filings']}, {num(R['composition']['majority']['filing']['era']['2015-2019']['n_sentences'])} |")
spf = C["sentences_per_filing_by_era"]
ok("spf", f"| sentences per filing | {spf['2015-2019']:.1f} | {spf['2020-2023']:.1f} | {spf['2024-2026']:.1f} |")
ok("spf text", f"carried {spf['2015-2019']:.1f} AI sentences in 2015 to 2019 and {spf['2024-2026']:.1f} in 2024 to 2026")

# ---------------------------------------------------------------- agreement
ok("agree n", f"the same class {num(A['class']['n_agree'])} times")
ok("agree pct", f"observed agreement of {pct(A['class']['observed_agreement'])} percent")
ok("alpha", f"Krippendorff alpha of {A['class']['krippendorff_alpha']:.3f}")
ok("own agree", f"agreed {pct(A['own_use']['observed_agreement'])} percent of the time with an alpha of {A['own_use']['krippendorff_alpha']:.3f}")
ok("disagreements", f"Of the {C['disputed_class']} class disagreements, {A['class']['disagreement_pairs']['capability vs other']} are capability")
ok("market vs other", f"and {A['class']['disagreement_pairs']['market vs other']} are market against other")
ok("controls", f"All {A['controls']['n_judgements']} judgements on the {A['controls']['n_controls']} known-answer controls were correct")
ok("controls wilson", f"below {pct(1 - A['controls']['accuracy_wilson'][0])} percent at the Wilson lower limit")
tp = C["third_pass"]
ok("third filler", f"{tp['filler_class_agree']} times on class and {tp['filler_own_agree']} times on own use")
ok("third resolved", f"resolved {tp['disputed_resolved_class']} of the {tp['disputed_n']} disputed")
ok("era cue share", f"{pct(A['era_cue']['share'])} percent of sentences carry such a cue")
ok("era cue agr", f"agreement on them was {pct(A['era_cue']['agreement_with_cue'])} percent against {pct(A['era_cue']['agreement_without'])} percent")
ok("name leak", f"{pct(A['name_leak']['share'])} percent of sentences, with agreement of {pct(A['name_leak']['agreement_with_leak'])} percent against {pct(A['name_leak']['agreement_without'])}")

# ---------------------------------------------------------------- composition
CM = R["composition"]["majority"]["filing"]["era"]
E1, E3 = CM["2015-2019"], CM["2024-2026"]
ok("abstract risk", f"rose from {pct(E1['risk'])} percent in 2015 to 2019 to {pct(E3['risk'])} percent in 2024 to 2026")
ok("abstract cap", f"fell from {pct(E1['capability'])} to {pct(E3['capability'])} percent")
ok("abstract own", f"fell from {pct(E1['own_use'])} to {pct(E3['own_use'])} percent")
for cls in ["capability", "risk", "market", "other", "own_use"]:
    ok(f"table2 {cls}", f"{pct_ci(E1[cls])} | {pct_ci(CM['2020-2023'][cls])} | {pct_ci(E3[cls])} |")
ok("table2 governance", f"| governance | 0.0 | 0.0 | {pct_ci(E3['governance'])} |")
ok("sec52 2015-19", f"{pct(E1['capability'])} percent of its AI sentences to claims about its own AI's capability, {pct(E1['other'])} percent to other, {pct(E1['market'])} percent to the market and {pct(E1['risk'])} percent to risk")
ok("sec52 2024-26", f"devotes {pct(E3['risk'])} percent to risk, {pct(E3['capability'])} percent to capability, {pct(E3['market'])} percent to the market and {pct(E3['other'])} percent to other")
ok("governance late", f"reaches {pct(E3['governance'])} percent")
EC = R["era_contrasts"]["majority"]["filing"]
ok("risk contrast", f"rose by {pct(EC['risk_late_minus_early']['estimate'])} percentage points with a bootstrap interval from {pct(EC['risk_late_minus_early']['lo'])} to {pct(EC['risk_late_minus_early']['hi'])}")
ok("cap contrast", f"fell by {pct(-EC['capability_late_minus_early']['estimate'])} points (interval {pct(-EC['capability_late_minus_early']['hi'])} to {pct(-EC['capability_late_minus_early']['lo'])})")
ok("own contrast", f"a drop of {pct(-EC['own_use_late_minus_early']['estimate'])} points ({pct(-EC['own_use_late_minus_early']['hi'])} to {pct(-EC['own_use_late_minus_early']['lo'])})")
T = R["trend"]["majority"]
ok("spearman risk", f"the yearly risk share is {T['spearman_year_vs_risk_share_filingweighted']['rho']:.3f}")
ok("OR risk", f"rise by a factor of {T['logit_risk_on_year']['odds_ratio_per_year']:.2f} per calendar year")
ok("OR cap", f"fall by a factor of {T['logit_capability_on_year']['odds_ratio_per_year']:.2f}")
ok("OR own", f"fall by {T['logit_own_use_on_year']['odds_ratio_per_year']:.2f}")
CS = R["composition"]["majority"]["sentence"]["era"]
ECS = R["era_contrasts"]["majority"]["sentence"]
ok("sentence risk", f"rises from {pct(CS['2015-2019']['risk'])} to {pct(CS['2024-2026']['risk'])} percent (a change of {pct(ECS['risk_late_minus_early']['estimate'])} points, interval {pct(ECS['risk_late_minus_early']['lo'])} to {pct(ECS['risk_late_minus_early']['hi'])})")
ok("sentence own", f"falls from {pct(CS['2015-2019']['own_use'])} to {pct(CS['2024-2026']['own_use'])} percent ({pct(-ECS['own_use_late_minus_early']['estimate'])} points, {pct(-ECS['own_use_late_minus_early']['hi'])} to {pct(-ECS['own_use_late_minus_early']['lo'])})")
# agreed basis within three points of majority (filing weighted, eras)
CA = R["composition"]["agreed"]["filing"]["era"]
mx = max(abs(CA[e][k]["estimate"] - CM[e][k]["estimate"]) for e in CA for k in CLASSES + ["own_use"])
checks += 1
if mx > 0.04:
    failures.append(f"agreed vs majority era shares differ by {mx:.3f}, paper says within four points")
mix = R["sector"]["frame_sector_mix_by_era"]
ok("frame mix", f"were {round(mix['2015-2019']['technology'] * 100)} percent of the frame in 2015 to 2019 and {round(mix['2024-2026']['technology'] * 100)} percent in 2024 to 2026")
S = R["sector"]["majority"]
ok("sector cap", f"capability share is {pct(S['technology']['capability_share_filing']['estimate'])} percent at technology registrants against {pct(S['finance_realestate']['capability_share_filing']['estimate'])} percent in finance and real estate, and the risk share is {pct(S['technology']['risk_share_filing']['estimate'])} percent against {pct(S['finance_realestate']['risk_share_filing']['estimate'])}")
ratio = E3["risk"]["estimate"] / E3["capability"]["estimate"]
checks += 1
if not (3.5 <= ratio < 4.0):
    failures.append(f"risk/capability ratio in 2024-2026 is {ratio:.2f}, paper says nearly four times")

# ---------------------------------------------------------------- filing level
FL = R["filing_level"]["majority"]
ok("own any overall", f"{pct(FL['overall']['own_use_any']['estimate'])} percent do (interval {pct(FL['overall']['own_use_any']['lo'])} to {pct(FL['overall']['own_use_any']['hi'])})")
ok("cap any overall", f"and {pct(FL['overall']['capability_any']['estimate'])} percent make at least one capability claim")
ok("own any eras", f"is {pct(FL['era']['2015-2019']['own_use_any']['estimate'])}, {pct(FL['era']['2020-2023']['own_use_any']['estimate'])} and {pct(FL['era']['2024-2026']['own_use_any']['estimate'])} percent")
ok("abstract eras", f"{pct(FL['era']['2015-2019']['own_use_any']['estimate'])}, {pct(FL['era']['2020-2023']['own_use_any']['estimate'])} and {pct(FL['era']['2024-2026']['own_use_any']['estimate'])} percent across the three eras")
d = FL["own_any_late_minus_early"]
ok("own any diff", f"difference is {pct(-d['estimate'])} points with an interval from {pct(-d['lo'])} points down to {pct(d['hi'])} points up")
ok("spearman own any", f"is negative {abs(T['spearman_year_vs_filing_own_any']['rho']):.2f} with p = {T['spearman_year_vs_filing_own_any']['p']:.2f}")
dc = FL["cap_any_late_minus_early"]
ok("cap any diff", f"from {pct(FL['era']['2015-2019']['capability_any']['estimate'])} to {pct(FL['era']['2024-2026']['capability_any']['estimate'])} percent (interval on the difference {pct(-dc['hi'])} to {pct(-dc['lo'])} points)")
yrs = FL["year"]
lo_y = min(v["own_use_any"]["estimate"] for v in yrs.values()); hi_y = max(v["own_use_any"]["estimate"] for v in yrs.values())
ok("yearly range", f"sit between {int(lo_y * 100)} and {int(hi_y * 100)} percent on {min(v['n_filings'] for v in yrs.values())} to {max(v['n_filings'] for v in yrs.values())} filings")
y25 = yrs["2025"]
ok("2025 own", f"an estimated {pct(y25['corrected_own_use']['estimate'])} percent (interval {pct(y25['corrected_own_use']['lo'])} to {pct(y25['corrected_own_use']['hi'])}) contained an own-use statement")
ok("2025 cap", f"and {pct(y25['corrected_capability']['estimate'])} percent ({pct(y25['corrected_capability']['lo'])} to {pct(y25['corrected_capability']['hi'])}) contained a capability claim")
ok("abstract 2025", f"at {pct(y25['corrected_own_use']['estimate'])} percent in 2025 rather than {pct(U['2025']['raw_share'])}, and the share making a capability claim at {pct(y25['corrected_capability']['estimate'])} percent")
ER = FL["era"]
ok("pooled raw", f"the raw share was {pct(ER['2015-2019']['raw_share_pooled'], 2)}, {pct(ER['2020-2023']['raw_share_pooled'])} and {pct(ER['2024-2026']['raw_share_pooled'])} percent and the own-use share {pct(ER['2015-2019']['corrected_own_use_pooled']['estimate'])}, {pct(ER['2020-2023']['corrected_own_use_pooled']['estimate'])} and {pct(ER['2024-2026']['corrected_own_use_pooled']['estimate'])} percent")
ok("overst eras", f"is {ER['2015-2019']['overstatement_factor']:.2f} (interval {ER['2015-2019']['overstatement_factor_interval'][0]:.2f} to {ER['2015-2019']['overstatement_factor_interval'][1]:.2f}) in 2015 to 2019, {ER['2020-2023']['overstatement_factor']:.2f} ({ER['2020-2023']['overstatement_factor_interval'][0]:.2f} to {ER['2020-2023']['overstatement_factor_interval'][1]:.2f}) in 2020 to 2023 and {ER['2024-2026']['overstatement_factor']:.2f} ({ER['2024-2026']['overstatement_factor_interval'][0]:.2f} to {ER['2024-2026']['overstatement_factor_interval'][1]:.2f}) in 2024 to 2026")
od = FL["overstatement_late_minus_early"]
ok("overst diff", f"by {od['estimate']:.2f}, but the interval on that difference runs from {abs(od['lo']):.2f} down to {od['hi']:.2f} up and {round(od['share_positive'] * 100)} percent of bootstrap replicates are positive")
ok("cap factor", f"the capability factor is {1 / ER['2024-2026']['capability_any']['estimate']:.1f} in 2024 to 2026 against {1 / ER['2015-2019']['capability_any']['estimate']:.1f} in 2015 to 2019")
for y in ["2015", "2018", "2021", "2023", "2024", "2025", "2026"]:
    v = yrs[y]
    ok(f"table3 {y}", f"| {y} | {pct(v['raw_share'], 2)} | {pct_ci(v['corrected_own_use'], 2)} | {pct_ci(v['corrected_capability'], 2)} | {v['n_filings']} |")

# ---------------------------------------------------------------- phrase reuse
P = R["phrase_reuse"]; PM = P["majority"]
ok("queried", f"All {num(P['n_queried'])} corpus sentences were queried without error, {pct(P['self_hit_rate'])} percent found their own filing, and {P['n_zero_hits']} returned no hit")
ok("usable", f"leaves {num(P['n_usable'])} sentences in the reuse analysis")
ok("share zero", f"For {pct(P['overall']['share_zero'])} percent of them")
ok("share flagged", f"{'Five' if round(P['overall']['share_flagged'] * 100) == 5 else pct(P['overall']['share_flagged'], 0)} percent are shared with five or more")
ok("max reuse", f"up to a maximum of {P['overall']['max']}")
ok("L8", f"from {pct(P['overall']['share_flagged'])} to {pct(P['L8_sensitivity']['share_flagged'])} percent")
bc = PM["by_class"]
ok("cap reuse", f"Of {bc['capability']['n']} capability sentences, none is shared with five or more other registrants and {pct(bc['capability']['share_zero'])} percent are shared with none")
ok("cap wilson", f"Wilson upper bound of {pct(bc['capability']['share_flagged_wilson'][1])} percent on capability")
ok("risk reuse", f"Of {bc['risk']['n']} risk sentences, {bc['risk']['flagged']}, or {pct(bc['risk']['share_flagged'])} percent (interval {pct(bc['risk']['share_flagged_wilson'][0])} to {pct(bc['risk']['share_flagged_wilson'][1])}), are flagged and {pct(1 - bc['risk']['share_zero'])} percent are shared with at least one")
ok("risk q90", f"90th percentile of {'twelve' if bc['risk']['q90'] == 12 else bc['risk']['q90']} other registrants")
ok("market other flag", f"flagged at {pct(bc['market']['share_flagged'])} and {pct(bc['other']['share_flagged'])} percent")
ok("flag precision risk", f"{pct(PM['flag_precision_for_risk'])} percent of flagged sentences are risk sentences and {pct(PM['flag_recall_for_risk'])} percent of risk sentences are flagged")
ok("auc", f"area under the curve of {PM['auc_flag_predicts_not_own_use']:.2f}")
ok("L8 by class", f"flags {pct(P['L8_sensitivity']['flag_by_class']['risk'])} percent of risk sentences and {pct(P['L8_sensitivity']['flag_by_class']['capability'])} percent of capability sentences")
fe = PM["flagged_share_era"]
ok("flag eras", f"is {pct(fe['2015-2019']['estimate'])} percent in 2015 to 2019, {pct(fe['2020-2023']['estimate'])} percent in 2020 to 2023 and {pct(fe['2024-2026']['estimate'])} percent in 2024 to 2026 (interval {pct(fe['2024-2026']['lo'])} to {pct(fe['2024-2026']['hi'])})")
ok("flag rise", f"a rise of {pct(PM['flagged_share_late_minus_early']['estimate'])} points")
ok("abstract flag", f"rose from zero in 2015 to 2019 to {pct(fe['2024-2026']['estimate'])} percent in 2024 to 2026")
ok("abstract risk flagged", f"{pct(bc['risk']['share_flagged'])} percent of risk sentences are shared with five or more other registrants against none of {bc['capability']['n']} capability sentences")
top = P["top_reused"]
ok("top1", f"generative AI ({top[0]['reuse_ciks']} other registrants)")
ok("top2", f"deficient or biased ({top[1]['reuse_ciks']})")
ok("top3", f"competitors incorporating AI faster ({top[2]['reuse_ciks']})")
ok("top5", f"AI ethics controversy ({top[4]['reuse_ciks']})")
ok("top6", f"AI regulation ({top[5]['reuse_ciks']})")
checks += 1
nonrisk = [t for t in top if t["class"] != "risk"]
if not (len(nonrisk) == 2 and all("collectively" in t["text"] for t in nonrisk) and all(t["class"] == "market" for t in nonrisk)):
    failures.append("top twelve reused: paper says exactly two non-risk sentences, both the 'collectively, AI' definition")
rs = R["composition"]["majority"]["sentence"]["overall"]["risk"]["estimate"] / PM["flagged_share_overall"]["estimate"]
checks += 1
if not (4.5 <= rs <= 5.5):
    failures.append(f"risk share / flagged share is {rs:.2f}, paper says about five times")

# ---------------------------------------------------------------- sector and size
ok("tech own", f"{pct(S['technology']['own_use_any']['estimate'])} percent of technology registrants' AI-mentioning filings state their own use of AI ({S['technology']['own_use_any']['k']} of {S['technology']['n_filings_with_sentences']}; interval {pct(S['technology']['own_use_any']['lo'])} to {pct(S['technology']['own_use_any']['hi'])})")
ok("health own", f"against {pct(S['healthcare']['own_use_any']['estimate'])} percent in healthcare ({S['healthcare']['own_use_any']['k']} of {S['healthcare']['n_filings_with_sentences']})")
ok("finance own", f"{pct(S['finance_realestate']['own_use_any']['estimate'])} percent in finance and real estate ({S['finance_realestate']['own_use_any']['k']} of {S['finance_realestate']['n_filings_with_sentences']})")
ok("other own", f"{pct(S['other']['own_use_any']['estimate'])} percent in everything else ({S['other']['own_use_any']['k']} of {S['other']['n_filings_with_sentences']})")
td = S["tech_minus_rest_own_any"]
ok("tech diff", f"is {pct(td['estimate'])} points with an interval from {pct(td['lo'])} to {pct(td['hi'])}")
Z = R["size"]
ok("size n", f"available for {Z['n_with_assets']} of {C['filings']} filings")
ok("size own", f"({pct(Z['own_use_any_large']['estimate'])} percent above the median of about one billion dollars against {pct(Z['own_use_any_small']['estimate'])} percent below, difference {pct(-Z['large_minus_small_own_any']['estimate'])} points, interval {pct(-Z['large_minus_small_own_any']['lo'])} down to {pct(Z['large_minus_small_own_any']['hi'])} up)")
ok("size risk", f"risk share is {pct(Z['risk_share_filing_large']['estimate'])} percent at larger registrants and {pct(Z['risk_share_filing_small']['estimate'])} percent at smaller ones")
checks += 1
if not (0.9e9 <= Z["median_assets_usd"] <= 1.1e9):
    failures.append(f"median assets {Z['median_assets_usd']:.3e}, paper says about one billion dollars")

# ---------------------------------------------------------------- calibration
K = R["calibration"]; sv = K["survival_by_class"]
ok("dup", "consistent with itself on all ten duplicate controls" if K['duplicates']['n'] == 10 else f"all {K['duplicates']['n']} duplicate controls")
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
checks += 1
if abs(tm["capability"].get("other", 0) - (sv["capability"]["n"] - sv["capability"]["survived"]) / sv["capability"]["n"]) > 1e-9 or sv["capability"]["n"] - sv["capability"]["survived"] != 4:
    failures.append("paper says all four overturned capability calls went to other")
CAL = R["calibrated"]["filing"]
ok("cal cap", f"capability share from {pct(E1['capability'])} to {pct(CAL['2015-2019']['capability']['estimate'])} percent in the first era and from {pct(E3['capability'])} to {pct(CAL['2024-2026']['capability']['estimate'])} in the last")
ok("cal own", f"own-use share from {pct(E1['own_use'])} to {pct(CAL['2015-2019']['own_use']['estimate'])} and from {pct(E3['own_use'])} to {pct(CAL['2024-2026']['own_use']['estimate'])}")
ok("cal risk", f"from {pct(E1['risk'])} to {pct(CAL['2015-2019']['risk']['estimate'])} and from {pct(E3['risk'])} to {pct(CAL['2024-2026']['risk']['estimate'])}")
ok("cal contrasts", f"are {pct(R['calibrated']['risk_late_minus_early_filing'])} points for risk, {pct(-R['calibrated']['capability_late_minus_early_filing'])} points for capability and {pct(-R['calibrated']['own_use_late_minus_early_filing'])} points for own use")

# ---------------------------------------------------------------- replication
RP = R["replication_2025"]
ok("rep risk", f"risk share of {pct(RP['risk_sentence_agreed']['estimate'])} percent (interval {pct(RP['risk_sentence_agreed']['lo'])} to {pct(RP['risk_sentence_agreed']['hi'])})")
ok("rep cap", f"capability share of {pct(RP['capability_sentence_agreed']['estimate'])} percent ({pct(RP['capability_sentence_agreed']['lo'])} to {pct(RP['capability_sentence_agreed']['hi'])})")
ok("rep companion", f"gave {pct(RP['companion']['risk'])} and {pct(RP['companion']['capability'])}")
ok("rep filing", f"risk share here is {pct(RP['risk_filing_majority']['estimate'])} percent and the capability share {pct(RP['capability_filing_majority']['estimate'])} percent")
checks += 1
if not (RP["risk_sentence_agreed"]["lo"] <= 0.605 <= RP["risk_sentence_agreed"]["hi"] and RP["capability_sentence_agreed"]["lo"] <= 0.122 <= RP["capability_sentence_agreed"]["hi"]):
    failures.append("paper says the companion's values lie inside both replication intervals")

# ---------------------------------------------------------------- predictions
PR = R["predictions"]
ok("p3", f"{PR['3_under_60pct_filings_own_use_late']['k']} of {FL['era']['2024-2026']['n_filings']} did, {pct(PR['3_under_60pct_filings_own_use_late']['estimate'])} percent, with a Wilson interval from {pct(PR['3_under_60pct_filings_own_use_late']['wilson'][0])} to {pct(PR['3_under_60pct_filings_own_use_late']['wilson'][1])}")
ok("p6", f"{PR['6_overstatement_grows']['late']:.2f} against {PR['6_overstatement_grows']['early']:.2f}")
checks += 1
exp = {"1_risk_share_higher_late": True, "2_own_use_share_lower_late": True, "3_under_60pct_filings_own_use_late": False, "5_flagged_share_rises": True, "7_tech_higher_own_use": True}
for k, v in exp.items():
    if PR[k]["holds_point"] != v:
        failures.append(f"prediction {k} outcome changed")
if PR["4_risk_reuse_vs_capability"]["median_criterion_decidable"] or not PR["4_risk_reuse_vs_capability"]["holds_flag_2x"]:
    failures.append("prediction 4 outcome changed")
if not PR["6_overstatement_grows"]["holds_point"] or PR["6_overstatement_grows"]["interval_excludes_zero"]:
    failures.append("prediction 6 outcome changed")
if PR["falsification_triggered"]:
    failures.append("falsification condition triggered")

# ---------------------------------------------------------------- BTOS
B = json.load(open(os.path.join(BASE, "data", "btos", "btos_ai_use.json")))
latest = sorted(B["q7_yes"]["national"], reverse=True)[0]
ok("btos cycle", f"collected from 21 September to 4 October 2026")
checks += 1
if B["dates"][latest] != ("2026-09-21", "2026-10-04") and list(B["dates"][latest]) != ["2026-09-21", "2026-10-04"]:
    failures.append(f"BTOS latest cycle dates {B['dates'][latest]}")
ok("btos national", f"national rate was {B['q7_yes']['national'][latest].rstrip('%')} percent")
ok("btos info", f"Information sector's rate was {B['q7_yes']['sector_51'][latest].rstrip('%')} percent")
ok("btos corrected 2026", f"corrected own-use share of {pct(yrs['2026']['corrected_own_use']['estimate'])} percent")

# ---------------------------------------------------------------- verbatim quotations
sents = json.load(open(os.path.join(BASE, "data", "sentences.json")))
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

# ---------------------------------------------------------------- report
print(f"{checks} checks, {len(failures)} failures")
for f in failures:
    print("  FAIL", f)
sys.exit(1 if failures else 0)
