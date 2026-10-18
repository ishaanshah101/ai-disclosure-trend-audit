"""Statistical helpers with self-checks: Wilson intervals, a filing-clustered
percentile bootstrap, Krippendorff's alpha for nominal data, and the forward
transfer correction used for calibration.

Run `python src/stats.py` to execute the self-checks.
"""
from __future__ import annotations
import math
from collections import Counter, defaultdict
import numpy as np

Z95 = 1.959963984540054


def wilson(k, n, z=Z95):
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = 0.0 if k == 0 else max(0.0, centre - half)
    hi = 1.0 if k == n else min(1.0, centre + half)
    return (lo, hi)


def cluster_bootstrap(groups, stat, reps=10000, seed=20261018, ci=(2.5, 97.5)):
    """Percentile bootstrap resampling whole clusters (filings).

    groups: list of cluster objects (any type). stat: function taking a list of
    clusters and returning a float or a 1-d array. Returns (point, lo, hi) where
    point is stat(groups) and lo/hi are percentiles of the bootstrap distribution.
    """
    rng = np.random.default_rng(seed)
    n = len(groups)
    point = np.asarray(stat(groups), dtype=float)
    draws = np.empty((reps,) + point.shape)
    idx = np.arange(n)
    for r in range(reps):
        pick = rng.choice(idx, size=n, replace=True)
        draws[r] = stat([groups[i] for i in pick])
    lo = np.nanpercentile(draws, ci[0], axis=0)
    hi = np.nanpercentile(draws, ci[1], axis=0)
    return point, lo, hi, draws


def krippendorff_alpha_nominal(units):
    """units: list of lists of category labels (one inner list per unit, the
    labels assigned by the coders who rated that unit). Units with fewer than
    two labels are ignored. Standard nominal alpha (Krippendorff 2004)."""
    units = [u for u in units if len(u) >= 2]
    if not units:
        return float("nan")
    # observed coincidence matrix
    o = defaultdict(float)
    n_total = 0.0
    for u in units:
        m = len(u)
        n_total += m
        for i, a in enumerate(u):
            for j, b in enumerate(u):
                if i != j:
                    o[(a, b)] += 1.0 / (m - 1)
    cats = sorted({c for u in units for c in u})
    n_c = {c: sum(o[(c, k)] for k in cats) for c in cats}
    Do = sum(o[(a, b)] for a in cats for b in cats if a != b)
    De = sum(n_c[a] * n_c[b] for a in cats for b in cats if a != b) / (n_total - 1)
    if De == 0:
        return float("nan")
    return 1 - Do / De


def observed_agreement(pairs):
    """pairs: list of (label_a, label_b)."""
    if not pairs:
        return float("nan")
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def positive_specific_agreement(pairs, cat):
    """Dice-style agreement for one category: 2*both / (a_has + b_has)."""
    both = sum(1 for a, b in pairs if a == cat and b == cat)
    a_has = sum(1 for a, _ in pairs if a == cat)
    b_has = sum(1 for _, b in pairs if b == cat)
    return 2 * both / (a_has + b_has) if (a_has + b_has) else float("nan")


def forward_transfer(counts, transfer):
    """counts: {class: n} from the automated passes. transfer: {class_i: {class_j:
    fraction}} measured in calibration, rows summing to 1. Returns corrected
    counts {class_j: sum_i counts[i] * transfer[i][j]}. Mass is conserved."""
    out = Counter()
    for i, n in counts.items():
        row = transfer.get(i)
        if not row:
            out[i] += n
            continue
        for j, frac in row.items():
            out[j] += n * frac
    return dict(out)


def _selfcheck():
    # Wilson: two published worked values (Newcombe 1998, Table I rows for 81/263 and 15/148)
    lo, hi = wilson(81, 263)
    assert abs(lo - 0.2553) < 5e-4 and abs(hi - 0.3662) < 5e-4, (lo, hi)
    lo, hi = wilson(15, 148)
    assert abs(lo - 0.0624) < 5e-4 and abs(hi - 0.1605) < 5e-4, (lo, hi)
    lo, hi = wilson(0, 75)
    assert lo == 0.0 and abs(hi - 0.0489) < 5e-4, (lo, hi)
    # Krippendorff alpha, nominal: a ten-unit two-coder example with one disagreement,
    # checked against the reference package (listed in requirements.txt). The value
    # is asserted here so that a change to the implementation fails loudly.
    ex = [[1, 1], [2, 2], [3, 3], [3, 3], [2, 2], [1, 3], [4, 4], [1, 1], [2, 2], [4, 4]]
    a = krippendorff_alpha_nominal(ex)
    assert abs(a - 0.8725) < 5e-4, a
    try:
        import krippendorff as kd  # cross-check against the reference package
        arr = np.array(ex, dtype=float).T
        ref = kd.alpha(reliability_data=arr, level_of_measurement="nominal")
        assert abs(a - ref) < 1e-9, (a, ref)
    except ImportError:
        print("warning: krippendorff package not installed, reference cross-check skipped")
    assert krippendorff_alpha_nominal([["a", "a"], ["b", "b"], ["c", "c"]]) == 1.0
    # forward transfer conserves mass
    c = {"risk": 100, "capability": 20}
    t = {"risk": {"risk": 0.9, "other": 0.1}, "capability": {"capability": 0.8, "other": 0.2}}
    out = forward_transfer(c, t)
    assert abs(sum(out.values()) - 120) < 1e-9 and abs(out["other"] - 14) < 1e-9, out
    # bootstrap returns point estimate at index 0
    g = [[1, 0], [1, 1], [0, 0], [1]]
    pt, lo, hi, _ = cluster_bootstrap(g, lambda gs: sum(sum(x) for x in gs) / sum(len(x) for x in gs), reps=200)
    assert abs(pt - 4 / 7) < 1e-12 and lo <= pt <= hi
    print("stats.py self-checks passed")


if __name__ == "__main__":
    _selfcheck()
