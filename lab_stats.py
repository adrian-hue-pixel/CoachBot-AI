"""Paired Prompt Lab summaries and reproducible evaluation statistics."""

from collections import defaultdict
from itertools import combinations
from math import sqrt
import re
from statistics import NormalDist
import unicodedata

import numpy as np

from lab_data import CRITERIA, RATINGS, TEMPERATURES

BOOTSTRAP_SAMPLES = 5000
BOOTSTRAP_SEED = 103
PLANNING_ALPHA = 0.05
PLANNING_POWER = 0.8


def prompt_groups(observations):
    """Keep separate models and modules out of the same paired experiment."""
    groups = defaultdict(list)
    for row in observations:
        if row["experiment"] == "prompt" and row["temperature"] == 0.3 and row["repeat"] == 1:
            groups[(row["model"], row["module"])].append(row)
    return dict(groups)


def paired_differences(rows, criterion):
    by_fixture = defaultdict(dict)
    for row in rows:
        if row["version"] in ("V1", "V3") and row[criterion] is not None:
            by_fixture[row["fixture"]][row["version"]] = row[criterion]
    return np.array([by_fixture[fixture]["V3"] - by_fixture[fixture]["V1"]
                     for fixture in sorted(by_fixture) if len(by_fixture[fixture]) == 2], dtype=float)


def bootstrap_ci(differences):
    if len(differences) < 2:
        return None
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.choice(differences, size=(BOOTSTRAP_SAMPLES, len(differences)), replace=True)
    lower, upper = np.quantile(draws.mean(axis=1), [0.025, 0.975])
    return float(lower), float(upper)


def rank_biserial(differences):
    if not len(differences):
        return None
    nonzero = differences[differences != 0]
    if not len(nonzero):
        return 0.0
    absolute = np.abs(nonzero)
    ranks = np.array([1 + np.count_nonzero(absolute < item) + (np.count_nonzero(absolute == item) - 1) / 2
                      for item in absolute])
    return float(np.dot(ranks, np.sign(nonzero)) / ranks.sum())


def wilcoxon_result(differences):
    if len(differences) < 2:
        return None, None, "Insufficient pairs"
    try:
        from scipy.stats import wilcoxon

        if not np.any(differences):
            return 0.0, 1.0, "All paired differences were zero"
        result = wilcoxon(differences, zero_method="wilcox", alternative="two-sided", method="auto")
        if not np.isfinite(result.pvalue):
            return None, None, "Wilcoxon unavailable"
        return float(result.statistic), float(result.pvalue), ""
    except Exception:
        return None, None, "Wilcoxon unavailable"


def holm_adjust(pvalues):
    """Treat unavailable comparisons as p=1 in the prespecified family."""
    valid = sorted((value, key) for key, value in pvalues.items() if value is not None)
    adjusted = dict.fromkeys(pvalues)
    maximum = 0.0
    for rank, (value, key) in enumerate(valid):
        maximum = max(maximum, min(1.0, (len(pvalues) - rank) * value))
        adjusted[key] = maximum
    return adjusted


def paired_summary(rows):
    output = []
    for criterion in CRITERIA:
        diffs = paired_differences(rows, criterion)
        interval = bootstrap_ci(diffs)
        statistic, pvalue, notice = wilcoxon_result(diffs)
        output.append({
            "criterion": criterion, "n": len(diffs), "mean_difference": float(diffs.mean()) if len(diffs) else None,
            "lower": interval[0] if interval else None, "upper": interval[1] if interval else None,
            "rank_biserial": rank_biserial(diffs), "wilcoxon_w": statistic, "p": pvalue, "notice": notice,
        })
    adjusted = holm_adjust({row["criterion"]: row["p"] for row in output})
    for row in output:
        row["holm_p"] = adjusted[row["criterion"]]
    return output


def minimum_detectable_difference(differences):
    """Estimate a two-sided paired-test MDE in the units of the observed differences."""
    n = len(differences)
    if n < 2:
        return None, None, "Insufficient pairs"
    sd = float(np.std(differences, ddof=1))
    if not sd or not np.isfinite(sd):
        return sd, None, "Observed SD cannot support planning"
    try:
        from scipy.optimize import brentq
        from scipy.stats import nct, t

        df = n - 1
        critical = t.ppf(1 - PLANNING_ALPHA / 2, df)

        def power_gap(noncentrality):
            # The opposite tail is bounded by Φ(−noncentrality), under 1.3e−12 at 7.
            # Skip its numerical CDF there because some SciPy builds return NaN in this tail.
            lower = nct.cdf(-critical, df, noncentrality) if noncentrality < 7 else 0.0
            return lower + nct.sf(critical, df, noncentrality) - PLANNING_POWER

        threshold = brentq(power_gap, 0, 4 * critical + 10)
        return sd, float(threshold * sd / sqrt(n)), "Paired t approximation"
    except (ImportError, ArithmeticError, RuntimeError, ValueError):
        normal = NormalDist()
        threshold = normal.inv_cdf(1 - PLANNING_ALPHA / 2) + normal.inv_cdf(PLANNING_POWER)
        return sd, threshold * sd / sqrt(n), "Normal approximation"


def power_summary(rows):
    output = []
    for criterion in CRITERIA:
        differences = paired_differences(rows, criterion)
        sd, mde, method = minimum_detectable_difference(differences)
        output.append({"criterion": criterion, "n": len(differences), "sd": sd, "mde": mde, "method": method})
    return output


def quadratic_kappa(pairs):
    if len(pairs) < 2:
        return None
    counts = np.zeros((5, 5))
    for a, b in pairs:
        counts[a - 1, b - 1] += 1
    observed = counts / counts.sum()
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0))
    weights = np.subtract.outer(np.arange(5), np.arange(5)) ** 2 / 16
    denominator = np.sum(weights * expected)
    return float(1 - np.sum(weights * observed) / denominator) if denominator else None


def rater_summary(human, other):
    common = sorted(human.keys() & other.keys())
    output = []
    for criterion in RATINGS:
        pairs = [(human[id_][criterion], other[id_][criterion]) for id_ in common
                 if human[id_][criterion] is not None and other[id_][criterion] is not None]
        output.append({
            "criterion": criterion, "n": len(pairs), "kappa": quadratic_kappa(pairs),
            "mae": float(np.mean([abs(a - b) for a, b in pairs])) if pairs else None,
            "bias": float(np.mean([b - a for a, b in pairs])) if pairs else None,
        })
    return output


def _tokens(text):
    return set(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold()))


def temperature_summary(observations, packets):
    groups = defaultdict(list)
    for row in observations:
        if row["experiment"] == "temperature":
            groups[(row["model"], row["fixture"], row["module"], row["version"], row["top_p"])].append(row)
    result = []
    for (model, fixture, module, version, top_p), group in sorted(groups.items()):
        for temp in TEMPERATURES:
            repeats = [row for row in group if row["temperature"] == temp]
            tokens = [_tokens(packets[row["response_id"]][1]) for row in repeats if row["response_id"] in packets]
            scores = [len(a & b) / len(a | b) for a, b in combinations(tokens, 2) if a | b]
            for criterion in CRITERIA:
                values = [row[criterion] for row in repeats if row[criterion] is not None]
                result.append({
                    "model": model, "fixture": fixture, "module": module, "version": version, "top_p": top_p,
                    "temperature": temp, "criterion": criterion, "scored_n": len(values),
                    "score_sd": float(np.std(values, ddof=1)) if len(values) >= 2 else None,
                    "packets_n": len(tokens), "jaccard_pairs": len(scores),
                    "jaccard_mean": float(np.mean(scores)) if scores else None,
                })
    return result
