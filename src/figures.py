"""Figures for the paper, drawn from results/analysis.json and the data files.

Palette and mark conventions follow a validated categorical order (blue,
orange, aqua, yellow, magenta) assigned to the five classes in fixed order,
thin marks, hairline grid, text in ink tokens rather than series colours.
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(BASE, "results", "analysis.json")))
FIG = os.path.join(BASE, "figures")
os.makedirs(FIG, exist_ok=True)
CLASSES = ["capability", "risk", "market", "governance", "other"]
COL = {"capability": "#2a78d6", "risk": "#eb6834", "market": "#1baf7a", "governance": "#eda100", "other": "#e87ba4"}
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
YEARS = list(range(2015, 2027))
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c3c2b7",
                     "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "savefig.facecolor": SURF})


def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def fig1_trend():
    fl = R["filing_level"]["majority"]["year"]
    raw = [R["universe"][str(y)]["raw_share"] * 100 for y in YEARS]
    own = [fl[str(y)]["corrected_own_use"]["estimate"] * 100 for y in YEARS]
    own_lo = [fl[str(y)]["corrected_own_use"]["lo"] * 100 for y in YEARS]
    own_hi = [fl[str(y)]["corrected_own_use"]["hi"] * 100 for y in YEARS]
    cap = [fl[str(y)]["corrected_capability"]["estimate"] * 100 for y in YEARS]
    cap_lo = [fl[str(y)]["corrected_capability"]["lo"] * 100 for y in YEARS]
    cap_hi = [fl[str(y)]["corrected_capability"]["hi"] * 100 for y in YEARS]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    style(ax)
    ax.plot(YEARS, raw, color=INK, lw=2, marker="o", ms=4, label="mentions \"artificial intelligence\" (any sentence)")
    ax.fill_between(YEARS, own_lo, own_hi, color=COL["other"], alpha=0.18, lw=0)
    ax.plot(YEARS, own, color=COL["other"], lw=2, marker="o", ms=4, label="contains at least one own-use sentence")
    ax.fill_between(YEARS, cap_lo, cap_hi, color=COL["capability"], alpha=0.18, lw=0)
    ax.plot(YEARS, cap, color=COL["capability"], lw=2, marker="o", ms=4, label="contains at least one capability claim")
    ax.set_ylabel("share of all 10-K filings, percent")
    ax.set_xticks(YEARS)
    ax.set_xticklabels([str(y) if y < 2026 else "2026*" for y in YEARS])
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    for y, v in ((2025, raw[-2]), (2025, own[-2]), (2025, cap[-2])):
        ax.annotate(f"{v:.1f}", (y, v), textcoords="offset points", xytext=(6, 0), fontsize=8, color=INK2, va="center")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig1_trend.png"), dpi=200)
    plt.close(fig)


def fig2_composition():
    comp = R["composition"]["majority"]["filing"]["era"]
    eras = list(comp.keys())
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    style(ax)
    x = np.arange(len(eras))
    bottom = np.zeros(len(eras))
    for cls in CLASSES:
        vals = np.array([comp[e][cls]["estimate"] * 100 for e in eras])
        ax.bar(x, vals, bottom=bottom, color=COL[cls], width=0.55, edgecolor=SURF, linewidth=2, label=cls)
        for i, v in enumerate(vals):
            if v >= 6:
                ax.text(x[i], bottom[i] + v / 2, f"{v:.0f}", ha="center", va="center", fontsize=8, color=SURF if cls in ("capability", "risk") else INK)
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels([f"{e}\n{comp[e]['n_filings']} filings, {comp[e]['n_sentences']} sentences" for e in eras], fontsize=8)
    ax.set_ylabel("share of a filing's AI sentences, percent\n(filings weighted equally)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.12), fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig2_composition.png"), dpi=200)
    plt.close(fig)


def fig3_reuse():
    sents = json.load(open(os.path.join(BASE, "data", "sentences.json")))
    labels = json.load(open(os.path.join(BASE, "data", "rating", "labels.json")))
    reuse = json.load(open(os.path.join(BASE, "data", "phrase_reuse.json")))
    by_sid = {l["sid"]: l for l in labels.values()}
    vals = {c: [] for c in CLASSES}
    for f in sents["filings"]:
        for s in f["ai_sentences"]:
            if s.get("non_ai"):
                continue
            l = by_sid.get(s["id"]); r = reuse.get(s["id"], {})
            if not l or l.get("class_majority") is None or "error" in r or not r.get("total_hits"):
                continue
            vals[l["class_majority"]].append(r["reuse_ciks"])
    ks = [0, 1, 2, 3, 5, 10, 20, 50, 100, 200]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    style(ax)
    for cls in CLASSES:
        v = np.array(vals[cls])
        if not len(v):
            continue
        share = [np.mean(v >= k) * 100 for k in ks]
        ax.plot(range(len(ks)), share, color=COL[cls], lw=2, marker="o", ms=4, label=f"{cls} (n={len(v)})")
        ax.annotate(cls, (len(ks) - 1, share[-1]), textcoords="offset points", xytext=(5, 0), fontsize=8, color=INK2, va="center")
    ax.axvline(ks.index(5), color=GRID, lw=1, ls="--")
    ax.text(ks.index(5) + 0.1, 95, "preregistered flag (5)", fontsize=8, color=MUTED)
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([str(k) for k in ks])
    ax.set_xlabel("k: number of other registrants that have filed the same 12-word phrase")
    ax.set_ylabel("share of sentences with reuse ≥ k, percent")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig3_reuse.png"), dpi=200)
    plt.close(fig)


def fig4_overstatement():
    fl = R["filing_level"]["majority"]["year"]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    style(ax)
    p = [fl[str(y)]["own_use_any"]["estimate"] * 100 for y in YEARS]
    lo = [fl[str(y)]["own_use_any"]["wilson"][0] * 100 for y in YEARS]
    hi = [fl[str(y)]["own_use_any"]["wilson"][1] * 100 for y in YEARS]
    ax.errorbar(YEARS, p, yerr=[np.array(p) - np.array(lo), np.array(hi) - np.array(p)], fmt="o", color=COL["other"],
                ecolor="#c3c2b7", elinewidth=1, capsize=0, ms=5)
    ax.set_ylim(0, 100)
    ax.set_xticks(YEARS)
    ax.set_xticklabels([str(y) if y < 2026 else "2026*" for y in YEARS])
    ax.set_ylabel("share of AI-mentioning filings with\nat least one own-use sentence, percent")
    for y, v, n in zip(YEARS, p, [fl[str(y)]["n_filings"] for y in YEARS]):
        ax.annotate(f"{v:.0f}", (y, v), textcoords="offset points", xytext=(0, 9), fontsize=7.5, color=INK2, ha="center")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig4_own_use_by_year.png"), dpi=200)
    plt.close(fig)


def fig5_calibration():
    if "calibration" not in R:
        return
    t = R["calibration"]["transfer_matrix"]
    M = np.array([[t[i].get(j, 0.0) if t[i] else 0.0 for j in CLASSES] for i in CLASSES])
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    im = ax.imshow(M, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("blue", ["#f6f9fe", "#0d366b"]), vmin=0, vmax=1)
    ax.set_xticks(range(5)); ax.set_xticklabels(CLASSES, rotation=30, ha="right")
    ax.set_yticks(range(5)); ax.set_yticklabels(CLASSES)
    ax.set_xlabel("blinded reviewer said"); ax.set_ylabel("majority of three passes said")
    for i in range(5):
        for j in range(5):
            n = R["calibration"]["survival_by_class"][CLASSES[i]]["n"]
            ax.text(j, i, f"{M[i, j]*100:.0f}%" if n else "", ha="center", va="center", fontsize=8,
                    color=SURF if M[i, j] > 0.55 else INK)
    ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig5_calibration.png"), dpi=200)
    plt.close(fig)


def fig6_sector():
    sec = R["sector"]["majority"]
    names = {"technology": "technology", "healthcare": "healthcare", "finance_realestate": "finance and real estate", "other": "everything else"}
    keys = ["technology", "healthcare", "finance_realestate", "other"]
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    style(ax)
    ax.grid(axis="x", color=GRID, linewidth=0.6); ax.grid(axis="y", visible=False)
    for i, k in enumerate(keys):
        e = sec[k]["own_use_any"]
        ax.plot([e["lo"] * 100, e["hi"] * 100], [i, i], color="#c3c2b7", lw=2)
        ax.plot(e["estimate"] * 100, i, "o", color=COL["other"], ms=7)
        ax.annotate(f"{e['estimate']*100:.0f}%  (n={sec[k]['n_filings']})", (e["hi"] * 100, i), textcoords="offset points", xytext=(6, 0), fontsize=8, va="center", color=INK2)
    ax.set_yticks(range(len(keys))); ax.set_yticklabels([names[k] for k in keys])
    ax.set_xlim(0, 100)
    ax.set_xlabel("share of AI-mentioning filings with at least one own-use sentence, percent, with 95% bootstrap interval")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig6_sector.png"), dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    fig1_trend(); fig2_composition(); fig3_reuse(); fig4_overstatement(); fig5_calibration(); fig6_sector()
    print("figures ->", FIG)
