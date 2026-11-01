"""Generate every Blog 8 result from explicitly simulated Bernoulli surveys.

Run from any directory: python code/build_blog8.py
The existing article date is preserved. No network access is required.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[1]
SEED = 640008
P_TRUE = 0.55
P_NULL = 0.50
SIZES = (50, 200, 800)
LEVELS = (90, 95, 99)
B_MAIN = 20_000
M_COVERAGE = 5_000
B_COVERAGE = 2_000
R_NULL = 50_000
DISPLAY_INTERVALS = 50
TEAL, RED, NAVY, PURPLE = "#18847b", "#c44b36", "#243746", "#7956a5"


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rng_for(n, purpose):
    return np.random.default_rng(np.random.SeedSequence([SEED, n, purpose]))


def bootstrap_means(sample, rng, repetitions):
    """Literal nonparametric resampling of the observed 0/1 responses."""
    values = np.empty(repetitions)
    for start in range(0, repetitions, 500):
        size = min(500, repetitions - start)
        values[start:start + size] = rng.choice(
            sample, size=(size, len(sample)), replace=True
        ).mean(axis=1)
    return values


def coverage_experiment(n):
    """New poll each row, then a NEW bootstrap distribution for that poll.

    For 0/1 data, the number of ones in a bootstrap resample is exactly
    Binomial(n, k/n). This count representation is equivalent to resampling
    the n observations with replacement and is much faster for 10m resamples.
    It is not a normal/Wald approximation and does not reuse the first poll.
    """
    rng = rng_for(n, 2)
    counts = rng.binomial(n, P_TRUE, size=M_COVERAGE)
    intervals = {level: np.empty((M_COVERAGE, 2)) for level in LEVELS}
    probabilities = [.005, .025, .05, .95, .975, .995]
    for start in range(0, M_COVERAGE, 100):
        stop = min(start + 100, M_COVERAGE)
        resample_means = rng.binomial(
            n, counts[start:stop, None] / n,
            size=(stop - start, B_COVERAGE),
        ) / n
        q = np.quantile(resample_means, probabilities, axis=1, method="linear")
        for level, low, high in [(90, 2, 3), (95, 1, 4), (99, 0, 5)]:
            intervals[level][start:stop, :] = np.column_stack([q[low], q[high]])
    rows = []
    metrics = {}
    for level in LEVELS:
        ci = intervals[level]
        hit = (ci[:, 0] <= P_TRUE) & (P_TRUE <= ci[:, 1])
        rate = float(hit.mean())
        metrics[level] = {
            "n": n, "confidence": level, "covered": int(hit.sum()),
            "polls": M_COVERAGE, "coverage": rate,
            "mcse": float(np.sqrt(rate * (1 - rate) / M_COVERAGE)),
            "mean_width_pp": float(100 * (ci[:, 1] - ci[:, 0]).mean()),
        }
    for i in range(M_COVERAGE):
        row = {"poll": i + 1, "n": n, "supporters": int(counts[i]),
               "sample_share": counts[i] / n}
        for level in LEVELS:
            lo, hi = intervals[level][i]
            row.update({f"lower_{level}": lo, f"upper_{level}": hi,
                        f"covers_{level}": int(lo <= P_TRUE <= hi)})
        rows.append(row)
    return rows, intervals, metrics


def null_experiment(n, observed_k):
    rng = rng_for(n, 3)
    counts = rng.binomial(n, P_NULL, size=R_NULL)
    histogram = np.bincount(counts, minlength=n + 1)
    distance = np.abs(2 * np.arange(n + 1) - n)
    # Integer distances include ties exactly, without floating-point tolerances.
    tail_counts = np.array([
        histogram[distance >= d].sum() for d in distance
    ])
    p_values = (1 + tail_counts) / (R_NULL + 1)
    right_candidates = np.flatnonzero(
        (np.arange(n + 1) > n / 2) & (p_values <= .05)
    )
    critical_right = int(right_candidates[0])
    critical_left = n - critical_right
    observed_tail = int(np.count_nonzero(
        np.abs(2 * counts - n) >= abs(2 * observed_k - n)
    ))
    extreme = abs(observed_k - n / 2)
    exact_p = float(min(1, 2 * binom.sf(n / 2 + extreme - 1, n, .5)))
    rejection = (counts <= critical_left) | (counts >= critical_right)
    metrics = {
        "n": n, "null_share": P_NULL, "null_simulations": R_NULL,
        "observed_supporters": int(observed_k),
        "observed_share": observed_k / n,
        "null_tail_count": observed_tail,
        "simulated_p_value": (observed_tail + 1) / (R_NULL + 1),
        "exact_binomial_p_value": exact_p,
        "critical_left": critical_left, "critical_right": critical_right,
        "simulated_rejection_rate": float(rejection.mean()),
        "exact_rejection_rate": float(2 * binom.cdf(critical_left, n, .5)),
    }
    return counts, histogram, metrics


def set_style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.labelcolor": NAVY, "text.color": NAVY,
        "xtick.color": NAVY, "ytick.color": NAVY,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#bdc8cb", "axes.titleweight": "bold",
        "savefig.facecolor": "white",
    })


def bootstrap_figure(values, estimate, ci, mobile=False):
    fig, ax = plt.subplots(figsize=(4.2, 3.8) if mobile else (8.6, 4.2))
    counts = np.bincount(np.rint(values * 200).astype(int), minlength=201)
    x = np.arange(201) / 200
    colors = [TEAL if ci[0] <= a <= ci[1] else "#c3cbce" for a in x]
    ax.bar(x, counts / len(values), width=.0046, color=colors)
    ax.axvline(estimate, color=NAVY, ls="--", lw=1.6,
               label=f"Observed sample: {estimate:.0%}")
    ax.axvspan(*ci, color=TEAL, alpha=.055)
    ax.set(xlim=(.36, .70), xlabel="Bootstrap support share",
           ylabel="Share of resamples", title="20,000 bootstrap resamples" if mobile else "One sample, 20,000 resamples")
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    if mobile:
        ax.text(.98, .92, f"Sample: {estimate:.0%}", ha="right", va="top",
                transform=ax.transAxes, fontsize=10)
    else:
        ax.legend(frameon=False, fontsize=10, loc="upper right")
    ax.text(.02, .92, f"95% interval\n{ci[0]:.1%} to {ci[1]:.1%}",
            transform=ax.transAxes, color=TEAL, fontsize=10, va="top")
    ax.grid(axis="y", color="#e7eded", lw=.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path = ROOT / "results" / ("bootstrap_mobile.png" if mobile else "bootstrap.png")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def coverage_figure(n, level, intervals, metric, mobile=False):
    fig, ax = plt.subplots(figsize=(4.2, 5.0) if mobile else (8.6, 4.8))
    ci = intervals[:DISPLAY_INTERVALS]
    contains = (ci[:, 0] <= P_TRUE) & (P_TRUE <= ci[:, 1])
    y = np.arange(1, DISPLAY_INTERVALS + 1)
    colors = np.where(contains, TEAL, RED)
    ax.hlines(y, ci[:, 0], ci[:, 1], color=colors, linewidth=1.8)
    ax.axvline(P_TRUE, color=NAVY, lw=1.6, ls="--")
    ax.set(xlim=(.05, .95), ylim=(DISPLAY_INTERVALS + 1, 0),
           xlabel="Support share", ylabel="Simulated poll number",
           title=f"{level}% intervals | n = {n}\nPopulation truth: 55%")
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xticks([.1, .3, .55, .7, .9] if mobile else np.arange(.1, 1, .1))
    ax.set_yticks([1, 10, 20, 30, 40, 50])
    ax.grid(axis="x", color="#e7eded", lw=.6)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.1)
    suffix = "_mobile" if mobile else ""
    fig.savefig(ROOT / "results" / f"coverage_n{n}_c{level}{suffix}.png", dpi=160)
    plt.close(fig)


def null_figure(histogram, metric, mobile=False):
    fig, axes = plt.subplots(2, 1, sharex=True,
                             figsize=(4.2, 6.5) if mobile else (8.6, 6.4))
    n = metric["n"]
    k = np.arange(n + 1)
    x = k / n
    mass = histogram / R_NULL
    reject = (k <= metric["critical_left"]) | (k >= metric["critical_right"])
    tail = np.abs(2 * k - n) >= abs(2 * metric["observed_supporters"] - n)
    for ax, mask, color in [(axes[0], reject, RED), (axes[1], tail, PURPLE)]:
        ax.bar(x, mass, width=.0046, color=np.where(mask, color, "#d3dadd"))
        ax.axvline(.5, color=NAVY, ls="--", lw=1)
        ax.set_ylabel("Share of null polls")
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.grid(axis="y", color="#e7eded", lw=.6)
        ax.set_axisbelow(True)
    axes[0].set_title("Predefined 5% rejection regions", fontsize=12)
    for critical in [metric["critical_left"] / n, metric["critical_right"] / n]:
        axes[0].axvline(critical, color=RED, lw=1, ls=":")
    axes[0].text(.03, .94,
        f"Reject at ≤{metric['critical_left']/n:.1%}\nor ≥{metric['critical_right']/n:.1%}",
        va="top", transform=axes[0].transAxes, fontsize=10, color=RED)
    axes[1].set_title("P-value: equally or more\nextreme null polls" if mobile else
                      "P-value: tails at least as far from 50%", fontsize=12)
    axes[1].axvline(metric["observed_share"], color=PURPLE, lw=1.8)
    axes[1].text(.03, .94,
        f"Observed: {metric['observed_share']:.0%}\np ≈ {metric['simulated_p_value']:.3f}",
        va="top", transform=axes[1].transAxes, fontsize=10, color=PURPLE)
    nonzero = np.flatnonzero(histogram)
    axes[1].set(xlim=(min(.35, (nonzero.min() - 1) / n),
                            max(.65, (nonzero.max() + 1) / n)),
                xlabel="Support share under H₀\n(population support = 50%)" if mobile else
                       "Support share under H₀: population support = 50%")
    axes[1].xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    axes[1].set_xticks([.35, .5, .65] if mobile else [.35, .4, .45, .5, .55, .6, .65])
    fig.tight_layout(pad=1.1, h_pad=1.7)
    fig.savefig(ROOT / "results" / ("null_test_mobile.png" if mobile else "null_test.png"),
                dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-date", help="Explicit YYYY-MM-DD; otherwise preserve the article date")
    args = parser.parse_args()
    article = ROOT / "blog8.qmd"
    if args.publication_date:
        date = args.publication_date
    elif article.exists() and (match := re.search(r"(?m)^date:\s*(\d{4}-\d{2}-\d{2})", article.read_text())):
        date = match[1]
    else:
        parser.error("For the first build, supply --publication-date with the verified America/New_York date")
    for folder in ["data", "results"]:
        (ROOT / folder).mkdir(exist_ok=True)
    set_style()
    original = np.random.default_rng(SEED).binomial(1, P_TRUE, max(SIZES))
    write_csv(ROOT / "data" / "simulated_sample.csv", ["respondent", "support"],
              [{"respondent": i + 1, "support": int(x)} for i, x in enumerate(original)])
    all_coverage, all_boot, all_null = [], [], []
    summary = {"simulation_only": True, "seed": SEED, "true_support": P_TRUE,
               "bootstrap_draws_main": B_MAIN, "bootstrap_draws_per_coverage_poll": B_COVERAGE,
               "coverage_polls": M_COVERAGE, "null_polls": R_NULL, "samples": {}}
    ui = {}
    coverage_summary = []
    for n in SIZES:
        sample = original[:n]
        k = int(sample.sum())
        boot = bootstrap_means(sample, rng_for(n, 1), B_MAIN)
        lo, hi = np.quantile(boot, [.025, .975], method="linear")
        all_boot.extend({"n": n, "resample": i + 1, "supporters": int(round(v * n)),
                         "bootstrap_share": float(v)} for i, v in enumerate(boot))
        rows, intervals, metrics = coverage_experiment(n)
        all_coverage.extend(rows)
        coverage_summary.extend(metrics.values())
        ui[str(n)] = {str(level): metrics[level] for level in LEVELS}
        for level in LEVELS:
            for mobile in (False, True):
                coverage_figure(n, level, intervals[level], metrics[level], mobile)
        null_counts, histogram, test = null_experiment(n, k)
        all_null.extend({"n": n, "poll": i + 1, "supporters": int(value)}
                        for i, value in enumerate(null_counts))
        summary["samples"][str(n)] = {"supporters": k, "estimate": k / n,
            "bootstrap_ci_95": [float(lo), float(hi)], "coverage": metrics, "test": test}
        if n == 200:
            for mobile in (False, True):
                bootstrap_figure(boot, k / n, (lo, hi), mobile)
                null_figure(histogram, test, mobile)
        print(f"n={n}: sample={k/n:.1%}; CI=({lo:.1%}, {hi:.1%}); "
              f"coverage={metrics[95]['coverage']:.2%}; p={test['simulated_p_value']:.4f}")
    write_csv(ROOT / "results" / "bootstrap_draws.csv", list(all_boot[0]), all_boot)
    write_csv(ROOT / "results" / "coverage_trials.csv", list(all_coverage[0]), all_coverage)
    write_csv(ROOT / "results" / "coverage_summary.csv", list(coverage_summary[0]), coverage_summary)
    write_csv(ROOT / "results" / "null_draws.csv", list(all_null[0]), all_null)
    write_csv(ROOT / "results" / "test_summary.csv", list(summary["samples"]["200"]["test"]),
              [summary["samples"][str(n)]["test"] for n in SIZES])
    (ROOT / "results" / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    html = (ROOT / "code" / "coverage_template.html.txt").read_text(encoding="utf-8")
    html = html.replace("{{METRICS}}", json.dumps(ui)).replace("{{SHOWN}}", str(DISPLAY_INTERVALS))
    (ROOT / "results" / "coverage_explorer.html").write_text(html, encoding="utf-8")
    base = summary["samples"]["200"]
    coverage = base["coverage"][95]
    test = base["test"]
    context = {
        "DATE": date, "K": str(base["supporters"]), "ESTIMATE": f"{base['estimate']:.0%}",
        "CI_LOW": f"{base['bootstrap_ci_95'][0]:.1%}",
        "CI_HIGH": f"{base['bootstrap_ci_95'][1]:.1%}",
        "COVERED": f"{coverage['covered']:,}", "MISSED": f"{M_COVERAGE - coverage['covered']:,}",
        "COVERAGE": f"{coverage['coverage']:.1%}", "MCSE": f"{coverage['mcse']*100:.2f}",
        "WIDTH_50": f"{ui['50']['95']['mean_width_pp']:.1f}",
        "WIDTH_800": f"{ui['800']['95']['mean_width_pp']:.1f}",
        "P_VALUE": f"{test['simulated_p_value']:.3f}",
        "TAIL_COUNT": f"{test['null_tail_count']:,}",
        "EXACT_P": f"{test['exact_binomial_p_value']:.3f}",
        "LEFT": f"{test['critical_left']/200:.1%}",
        "RIGHT": f"{test['critical_right']/200:.1%}",
        "TEST_SIZE": f"{test['simulated_rejection_rate']:.1%}",
    }
    text = (ROOT / "code" / "article_template.txt").read_text(encoding="utf-8")
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", value)
    if re.search(r"\{\{[A-Z_]+\}\}", text):
        raise RuntimeError("Unreplaced article template placeholder")
    article.write_text(text, encoding="utf-8")
    settings = {"simulation_only": True, "model": "independent Bernoulli responses",
                "true_population_support": P_TRUE, "null_population_support": P_NULL,
                "seed": SEED, "sample_sizes": SIZES, "confidence_levels": LEVELS,
                "main_bootstraps": B_MAIN, "coverage_polls_per_size": M_COVERAGE,
                "bootstraps_per_coverage_poll": B_COVERAGE, "null_polls_per_size": R_NULL,
                "displayed_intervals": DISPLAY_INTERVALS,
                "quantile_method": "numpy.quantile(method='linear')",
                "sample_sha256": hashlib.sha256((ROOT / "data" / "simulated_sample.csv").read_bytes()).hexdigest(),
                "numpy": np.__version__, "matplotlib": matplotlib.__version__}
    (ROOT / "data" / "simulation_design.json").write_text(json.dumps(settings, indent=2) + "\n")


if __name__ == "__main__":
    main()
