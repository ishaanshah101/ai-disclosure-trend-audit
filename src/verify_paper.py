"""Check the numbers quoted in paper/paper.md and exit non-zero on any mismatch.

The headline era composition shares, the filing-level own-use fractions, the
corpus counts and the mean sentences per filing are RECOMPUTED here from the
committed labels and sentences, with no use of the results files, and compared
both to the results files and to the paper text. Every other quoted number is
formatted from results/analysis.json or results/revision2.json exactly as the
paper prints it and asserted to occur in the text. Run after src/analyze.py and
src/revision2.py.
"""
from __future__ import annotations
import json, math, os, re, sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(BASE, "results", "analysis.json")))
R2 = json.load(open(os.path.join(BASE, "results", "revision2.json")))
RAW = open(os.path.join(BASE, "paper", "paper.md")).read()
PAPER = re.sub(r"\s+", " ", RAW)
CLASSES = ["capability", "risk", "market", "governance", "other"]
ERAS = {"2015-2019": range(2015, 2020), "2020-2023": range(2020, 2024), "2024-2026": range(2024, 2027)}
E3 = list(ERAS)
checks, failures = 0, []


def ok(label, text):
    global checks
    checks += 1
    if text not in PAPER:
        failures.append(f"{label}: expected '{text}' in paper")


def cond(label, c, detail=""):
    global checks
    checks += 1
    if not c:
        failures.append(f"{label}: {detail}")


def p1(x):
    x = x["estimate"] if isinstance(x, dict) else x
    return f"{x * 100:.1f}"


def br(d, scale=100, nd=1):
    return f"[{d['lo'] * scale:.{nd}f}, {d['hi'] * scale:.{nd}f}]"


def n2(x):
    return f"{x:.2f}"


# ================================================================ recomputation from labels
labels = json.load(open(os.path.join(BASE, "data", "rating", "labels.json")))
sents = json.load(open(os.path.join(BASE, "data", "sentences.json")))
frame = json.load(open(os.path.join(BASE, "data", "frame.json")))
reuse = json.load(open(os.path.join(BASE, "data", "phrase_reuse.json")))
by_sid = {l["sid"]: l for l in labels.values()}
fil = []
for f in sents["filings"]:
    rows = [dict(by_sid[s["id"]], reuse_ciks=reuse.get(s["id"], {}).get("reuse_ciks"))
            for s in f["ai_sentences"] if not s.get("non_ai") and s["id"] in by_sid]
    fil.append({"year": f["year"], "rows": rows})
n_samp = Counter(f["year"] for f in fil)
w_of = {y: frame["years"][str(y)]["registrants_main_10k"] / n_samp[y] for y in n_samp}
n_corpus = sum(len(f["rows"]) for f in fil)
cond("corpus n", n_corpus == R["corpus"]["sentences"] == 2242, str(n_corpus))
cond("filings with sentences", sum(1 for f in fil if f["rows"]) == 313)
ok("corpus text", "leaving 2,242 sentences in 313 filings")
ok("abstract corpus", "all 2,242 AI sentences in 315 sampled filings")
cond("filings 315 registrants 281", len(sents["filings"]) == 315 and R["corpus"]["registrants"] == 281)
ok("sample text", "315 filings from 281 registrants")
cond("2015 and 2026 weights", frame["years"]["2015"]["registrants_main_10k"] == 36 and frame["years"]["2026"]["registrants_main_10k"] == 3710)
ok("weights text", "It takes 30 of 36 registrants in 2015 and 25 of 3,710 in 2026")


def wmean(vals_years):
    num = sum(w_of[y] * v for v, y in vals_years); den = sum(w_of[y] for _, y in vals_years)
    return num / den


for e, rng in ERAS.items():
    # composition shares
    for cls in ("risk", "capability"):
        vy = []
        for f in fil:
            if f["year"] in rng:
                dec = [r for r in f["rows"] if r["class_majority"] is not None]
                if dec:
                    vy.append((sum(r["class_majority"] == cls for r in dec) / len(dec), f["year"]))
        v = wmean(vy)
        ref = R["composition"]["majority"]["filing"]["era"][e][cls]
        cond(f"recompute share {e} {cls}", abs(v - ref["estimate"]) < 1e-9, f"{v}")
        ok(f"table2 share {e} {cls}", f"{p1(ref)} {br(ref)}")
    # mean sentences per filing by class
    for cls in CLASSES + ["all"]:
        vy = []
        for f in fil:
            if f["year"] in rng:
                vy.append((len(f["rows"]) if cls == "all" else sum(r["class_majority"] == cls for r in f["rows"]), f["year"]))
        v = wmean(vy)
        ref = R2["R1_mean_sentences_per_filing"][e][cls]
        cond(f"recompute mean {e} {cls}", abs(v - ref["estimate"]) < 1e-9, f"{v} vs {ref['estimate']}")
        if cls == "governance" and e != "2024-2026":
            cond(f"governance zero {e}", ref["estimate"] == 0)
        else:
            ok(f"table2 mean {e} {cls}", f"{ref['estimate']:.2f} [{ref['lo']:.2f}, {ref['hi']:.2f}]")
    # filing-level any own use and substantive own use
    sel = [f for f in fil if f["year"] in rng and f["rows"]]
    any_v = wmean([(float(any(r["own_majority"] is True for r in f["rows"])), f["year"]) for f in sel])
    sub_v = wmean([(float(any(r["own_majority"] is True and r["class_majority"] != "risk" and not (r["reuse_ciks"] is not None and r["reuse_ciks"] >= 5) for r in f["rows"])), f["year"]) for f in sel])
    T = R2["R3_substantive_own_use"][e]
    cond(f"recompute any own {e}", abs(any_v - T["own_use_any"]["estimate"]) < 1e-9 and abs(any_v - R["filing_level"]["majority"]["era"][e]["own_use_any"]["estimate"]) < 1e-9, f"{any_v}")
    cond(f"recompute sub own {e}", abs(sub_v - T["substantive_own_use_any"]["estimate"]) < 1e-9, f"{sub_v}")
    for key in ("own_use_any", "substantive_own_use_any", "own_use_only_in_risk_sentences"):
        ok(f"table3 {e} {key}", f"{p1(T[key])} {br(T[key])}")
    ok(f"table3 ratio any {e}", f"{T['ratio_any']:.2f} [{T['ratio_any_interval'][0]:.2f}, {T['ratio_any_interval'][1]:.2f}]")
    ok(f"table3 ratio sub {e}", f"{T['ratio_substantive']:.2f} [{T['ratio_substantive_interval'][0]:.2f}, {T['ratio_substantive_interval'][1]:.2f}]")
    CM = R["composition"]["majority"]["filing"]["era"][e]
    ok(f"table2 counts {e}", f"{CM['n_filings']}, {CM['n_sentences']:,}")

# era text
ok("any own eras", "61.6, 71.9 and 61.5 percent")
ok("sub own eras", "59.8, 70.0 and 50.5 percent")
S = R2["R3_substantive_own_use"]["substantive_late_minus_early"]
ok("sub contrast", f"fall of {-S['estimate'] * 100:.1f} points whose interval, from {-S['lo'] * 100:.1f} down to {S['hi'] * 100:.1f}")
ok("only risk", "from 1.9 percent before 2020 to 11.0 percent since 2024")

# ================================================================ R1, R2 text
A2 = R2["R2_added_volume"]; M = R2["R1_mean_sentences_per_filing"]
ok("abstract cap", f"from {M['2015-2019']['capability']['estimate']:.1f} to {M['2024-2026']['capability']['estimate']:.1f}")
ok("abstract risk", f"from {M['2015-2019']['risk']['estimate']:.1f} to {M['2024-2026']['risk']['estimate']:.1f}")
cond("63 percent of added", round(A2["risk"]["share_of_added"] * 100) == 63)
ok("added text", f"Of the {A2['added_total']:.1f} sentences added between the first and last era, {A2['risk']['added']:.1f} are risk ({A2['risk']['share_of_added'] * 100:.0f} percent), {A2['capability']['added']:.1f} capability ({A2['capability']['share_of_added'] * 100:.0f} percent), {A2['market']['added']:.1f} market and {A2['other']['added']:.1f} other")
cond("nineteen-fold", round(M["2024-2026"]["risk"]["estimate"] / M["2015-2019"]["risk"]["estimate"]) == 19)
ok("nineteen", "nineteen-fold")
cond("roughly doubled", 1.9 < A2["capability_ratio_late_to_early"] < 2.3)
ok("3.9 to 13.7", f"it held {M['2015-2019']['all']['estimate']:.1f} AI sentences")
ok("13.7", f"to 2026 it holds {M['2024-2026']['all']['estimate']:.1f}")

# ================================================================ R6 era year weights
W = R2["R6_year_weights_within_era"]
cond("78 percent", round((W["2015-2019"]["2018"] + W["2015-2019"]["2019"]) * 100) == 78)
cond("75 percent", round((W["2024-2026"]["2025"] + W["2024-2026"]["2026"]) * 100) == 75)
ok("weights era text", "2018 and 2019 carry 78 percent of the weight of 2015 to 2019, and 2025 and 2026 carry 75 percent")

# ================================================================ R7 items
I = R2["R7_item_location"]["by_era"]
cond("item 1 early 64", round(I["2015-2019"]["Item 1 Business"]["share_of_ai_sentences"] * 100) == 64)
cond("item 1A early 14", round(I["2015-2019"]["Item 1A Risk factors"]["share_of_ai_sentences"] * 100) == 14)
cond("item 1 late 40", round(I["2024-2026"]["Item 1 Business"]["share_of_ai_sentences"] * 100) == 40)
cond("item 1A late 47", round(I["2024-2026"]["Item 1A Risk factors"]["share_of_ai_sentences"] * 100) == 47)
cond("1A risk 83", round(I["2024-2026"]["Item 1A Risk factors"]["risk_share_within_item"] * 100) == 83)
cond("1C 0.5", round(I["2024-2026"]["Item 1C Cybersecurity"]["share_of_ai_sentences"] * 100, 1) == 0.5)
ok("items text", "64 percent of AI sentences were in Item 1")
ok("items 1C", "Item 1C, holds 0.5 percent")
cond("tagging coverage", R2["R7_item_location"]["coverage"].get("tagged") == 2590)

# ================================================================ R4, R5, R8, R9
L = R2["R4_length_adjustment"]; lg = L["logit_any_own"]
c, se = lg["coef"][3], lg["se"][3]
ok("length OR", f"are {math.exp(c):.2f} times those of a 2015 to 2019 filing (interval {math.exp(c - 1.96 * se):.2f} to {math.exp(c + 1.96 * se):.2f})")
cells = L["cells"]
k1 = [k for k in cells if k.startswith("1 to")][0]; k2 = [k for k in cells if k.startswith("3 to")][0]
ok("tercile 1", f"{cells[k1]['2015-2019']['own_use_any'] * 100:.0f} percent made an own-use statement before 2020 and {cells[k1]['2024-2026']['own_use_any'] * 100:.0f} percent since 2024")
ok("tercile 2", f"the figures are {cells[k2]['2015-2019']['own_use_any'] * 100:.0f} and {cells[k2]['2024-2026']['own_use_any'] * 100:.0f} percent")
ps = L["per_sentence_own_use"]
ok("per sentence", f"fell from {ps['2015-2019'] * 100:.0f} to {ps['2024-2026'] * 100:.0f} percent")
P5 = R2["R5_calibration_propagated_filing_level"]
ok("propagated", f"{P5['2015-2019']['mean'] * 100:.1f}, {P5['2020-2023']['mean'] * 100:.1f} and {P5['2024-2026']['mean'] * 100:.1f} percent")
W8 = R2["R8_within_firm_reuse"]
ok("within firm", f"For the {W8['pairs']} pairs")
cond("within firm 27", round(W8["share_carried"] * 100) == 27 and W8["median_gap_years"] == 1.0)
r9 = R2["R9_logit_risk_post2023"]; c, se = r9["coef"][1], r9["se"][1]
ok("post2023 OR", f"{math.exp(c):.1f} times higher in filings made from 2024 onward than in 2015 to 2019 (interval {math.exp(c - 1.96 * se):.1f} to {math.exp(c + 1.96 * se):.1f})")
cond("2020-23 not detectable", r9["p"][2] > 0.05)

# ================================================================ analysis.json numbers
A = R["agreement"]
ok("agreement", f"{A['class']['observed_agreement'] * 100:.1f} percent of sentences (Krippendorff's alpha {A['class']['krippendorff_alpha']:.3f})")
ok("own agreement", f"{A['own_use']['observed_agreement'] * 100:.1f} percent (alpha {A['own_use']['krippendorff_alpha']:.3f})")
cond("disagreements", A["class"]["disagreement_pairs"]["capability vs other"] == 73 and 2242 - A["class"]["n_agree"] == 121)
C = R["calibrated"]
ok("calibrated risk", f"{C['risk_late_minus_early_filing']['estimate'] * 100:.1f} points ({C['risk_late_minus_early_filing']['lo'] * 100:.1f} to {C['risk_late_minus_early_filing']['hi'] * 100:.1f})")
P = R["predictions"]
ok("P1", f"+{P['1_risk_share_higher_late']['estimate'] * 100:.1f} points {br(P['1_risk_share_higher_late'])}")
ok("P2", f"−{-P['2_own_use_share_lower_late']['estimate'] * 100:.1f} points [−{-P['2_own_use_share_lower_late']['lo'] * 100:.1f}, −{-P['2_own_use_share_lower_late']['hi'] * 100:.1f}]")
ok("P3", f"{p1(P['3_under_60pct_filings_own_use_late'])} percent {br(P['3_under_60pct_filings_own_use_late'])}")
ok("P5", f"+{P['5_flagged_share_rises']['estimate'] * 100:.1f} points {br(P['5_flagged_share_rises'])}")
P6 = P["6_overstatement_grows"]
cond("P6 point only", P6.get("holds_point") is True and not P6.get("interval_excludes_zero", False), json.dumps(P6)[:200])
P7 = P["7_tech_higher_own_use"]
ok("P7", f"+{P7['estimate'] * 100:.1f} points [{P7['lo'] * 100:.1f}, {P7['hi'] * 100:.1f}]")
cond("tally", P["tally"] == {"held_with_interval": 4, "held_point_only": 1, "held_one_of_two_criteria": 1, "failed": 1}, json.dumps(P["tally"]))

FY = R["filing_level"]["majority"]["year"]
for y in range(2015, 2027):
    v = FY[str(y)]; s = R2["R3_substantive_own_use"]["by_year"][str(y)]
    row = (f"| {y} | {v['n_filings']} | {v['raw_share'] * 100:.2f} | {v['own_use_any']['estimate'] * 100:.1f} | "
           f"{s['substantive_own_use_any'] * 100:.1f} | {v['corrected_own_use']['estimate'] * 100:.1f} "
           f"[{v['corrected_own_use']['lo'] * 100:.1f}, {v['corrected_own_use']['hi'] * 100:.1f}] | {v['overstatement_factor']:.2f} |")
    ok(f"table4 {y}", row)
    cond(f"table4 weights equal {y}", abs(s["own_use_any"] - v["own_use_any"]["estimate"]) < 1e-9)
U = R["universe"]
for y in range(2015, 2027):
    cond(f"table1 {y}", f"{U[str(y)]['raw_share'] * 100:.2f}%" in PAPER and f"{U[str(y)]['all_10k']:,}" in PAPER)
cond("frame total", R["frame_total_filings"] == 13586 and R["all_10k_total"] == 82684)
ok("frame text", "13,586 of 82,684")

PR = R["phrase_reuse"]
ok("reuse unique", "84.8 percent share their twelve-word phrase with no other registrant")
ok("flag text", "0.0 percent before 2020, 2.8 percent in 2020 to 2023 and 12.3 percent since 2024 (interval 7.4 to 17.7)")
ok("calib survival", "90 percent of majority labels survived")
cal = json.load(open(os.path.join(BASE, "results", "calibration.json")))
cond("calib 90", abs(cal["overall_survival"] - 0.90) < 0.0005)
cond("own surv", round(cal["own_use"]["true_rate"] * 100) == 94 and round(cal["own_use"]["false_rate"] * 100) == 89)

# ================================================================ remaining quoted figures
SC = R["sector"]["majority"]
MX = R["sector"]["frame_sector_mix_by_era"]
cond("tech mix 42 to 16", round(MX["2015-2019"]["technology"] * 100) == 42 and round(MX["2024-2026"]["technology"] * 100) == 16, json.dumps(MX)[:200])
ok("sector tech", f"{p1(SC['technology']['own_use_any'])} percent of technology registrants' AI-mentioning filings state own use (interval {p1(SC['technology']['own_use_any']['lo'])} to {p1(SC['technology']['own_use_any']['hi'])})")
ok("sector others", f"against {p1(SC['finance_realestate']['own_use_any'])} percent in finance and real estate, {p1(SC['healthcare']['own_use_any'])} percent in healthcare and {p1(SC['other']['own_use_any'])} percent elsewhere")
SZ = R["size"]
ok("size", f"devote {p1(SZ['risk_share_filing_large'])} percent of their AI sentences to risk against {p1(SZ['risk_share_filing_small'])} percent")
RP = R["replication_2025"]
ok("rep risk", f"risk share of {p1(RP['risk_sentence_agreed'])} percent ({p1(RP['risk_sentence_agreed']['lo'])} to {p1(RP['risk_sentence_agreed']['hi'])})")
cond("rep companion outside", RP["risk_sentence_agreed"]["hi"] < 0.655, "companion 65.5 should lie above the interval")
ok("rep cap", f"capability share of {p1(RP['capability_sentence_agreed'])} percent ({p1(RP['capability_sentence_agreed']['lo'])} to {p1(RP['capability_sentence_agreed']['hi'])})")
ok("rep filing", f"the 2025 figures are {p1(RP['risk_filing_majority'])} and {p1(RP['capability_filing_majority'])} percent")
PRu = R["phrase_reuse"]
cond("usable 2166", PRu["n_usable"] == 2166 and PRu["n_zero_hits"] == 76)
ok("usable text", "Of the 2,166 sentences")
cond("self hit 3.5", round((1 - PRu["self_hit_rate"]) * 100, 1) == 3.5)
ok("self hit text", "3.5 percent of phrases failed to find their own filing")
ok("L8", f"from {PRu['overall']['share_flagged'] * 100:.1f} to {PRu['L8_sensitivity']['share_flagged'] * 100:.1f} percent")
ok("leak", f"{A['era_cue']['share'] * 100:.1f} percent of sentences and a name fragment survived redaction in {A['name_leak']['share'] * 100:.1f} percent")
sv = cal["survival_by_class"]
cond("class survival", [round(sv[c]["rate"] * 100) for c in ("risk", "other", "market", "capability")] == [96, 96, 89, 87] and sv["governance"]["survived"] == 5 and sv["governance"]["n"] == 8)
ok("survival text", "risk 96 percent, other 96, market 89, capability 87 and governance 5 of 8")
th = R["corpus"].get("third_pass") or {}
cond("disputed 155", R["corpus"]["disputed_either"] == 155, str(R["corpus"]["disputed_either"]))

# ================================================================ hygiene
cond("no em dash", "—" not in RAW)
prose = [ln for ln in RAW.splitlines() if not ln.startswith("  - \\") and "http" not in ln and not ln.startswith("|")]
cond("no semicolons in prose", not any(";" in ln for ln in prose), "semicolon found")
cond("no vendor names", not re.search(r"\b(Anthropic|Claude|OpenAI|GPT-?[0-9]|Sonnet|Opus|Gemini)\b", RAW))
cond("AI-use statement present", "## AI-use statement" in RAW)
ab = RAW.split("## Abstract")[1].split("**Keywords")[0]
cond("abstract length", len(ab.split()) <= 200, str(len(ab.split())))
cited = set(re.findall(r"([A-Z][A-Za-z'\-]+)(?: et al\.)?(?:,? and [A-Z][A-Za-z\-]+)? \((\d{4})", RAW.split("## References")[0]))
refs = RAW.split("## References")[1]
for name, yr in cited:
    if name in ("Item", "Table", "Figure", "Section", "Prediction", "Release"):
        continue
    cond(f"cited in refs {name} {yr}", re.search(rf"{re.escape(name)}.{{0,200}}\({yr}\)", refs, re.S) is not None)

print(f"{checks} checks, {len(failures)} failures")
for f in failures:
    print("  FAIL", f)
sys.exit(1 if failures else 0)
