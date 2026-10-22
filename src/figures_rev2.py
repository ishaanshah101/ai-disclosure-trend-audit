"""Figures added in the second revision, drawn from results/revision2.json.

fig7_counts.png   mean AI sentences per filing by class and era (stacked)
fig8_own_use.png  share of AI-mentioning filings with any own-use sentence and
                  with a substantive own-use sentence, by era
"""
from __future__ import annotations
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from figures import CLASSES, COL, INK, INK2, MUTED, GRID, SURF, style, FIG, BASE  # noqa: F401

R2 = json.load(open(os.path.join(BASE, "results", "revision2.json")))
ERAS = ["2015-2019", "2020-2023", "2024-2026"]
LAB = ["2015 to 2019", "2020 to 2023", "2024 to 2026"]


def fig7_counts():
    r1 = R2["R1_mean_sentences_per_filing"]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    bottom = [0.0] * 3
    for c in CLASSES:
        v = [r1[e][c]["estimate"] for e in ERAS]
        ax.bar(LAB, v, bottom=bottom, color=COL[c], width=0.55, label=c, edgecolor=SURF, linewidth=0.8)
        bottom = [b + x for b, x in zip(bottom, v)]
    for i, e in enumerate(ERAS):
        ax.text(i, bottom[i] + 0.3, f"{r1[e]['all']['estimate']:.1f}", ha="center", color=INK2, fontsize=8)
    ax.set_ylabel("AI sentences per AI-mentioning filing")
    ax.legend(frameon=False, fontsize=8, ncol=5, loc="upper left", bbox_to_anchor=(0, 1.12))
    style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig7_counts.png"), dpi=200)


def fig8_own_use():
    r3 = R2["R3_substantive_own_use"]
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    x = range(3)
    for k, (key, name, col, dx) in enumerate([("own_use_any", "any own-use sentence", "#2a78d6", -0.14),
                                              ("substantive_own_use_any", "substantive own-use sentence", "#eb6834", 0.14)]):
        v = [r3[e][key]["estimate"] * 100 for e in ERAS]
        lo = [v[i] - r3[e][key]["lo"] * 100 for i, e in enumerate(ERAS)]
        hi = [r3[e][key]["hi"] * 100 - v[i] for i, e in enumerate(ERAS)]
        ax.errorbar([i + dx for i in x], v, yerr=[lo, hi], fmt="o", color=col, ms=5, capsize=3, lw=1, label=name)
    ax.set_xticks(list(x)); ax.set_xticklabels(LAB)
    ax.set_ylim(0, 100); ax.set_ylabel("percent of AI-mentioning filings")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    style(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig8_own_use.png"), dpi=200)


if __name__ == "__main__":
    fig7_counts(); fig8_own_use()
