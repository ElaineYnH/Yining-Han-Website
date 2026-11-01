"""Check saved Blog 8 outputs without regenerating their simulation streams."""
from pathlib import Path
import json
import numpy as np
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[1]


def read_csv(name):
    return np.genfromtxt(ROOT / name, delimiter=",", names=True)


def main():
    summary = json.loads((ROOT / "results/summary.json").read_text())
    original = read_csv("data/simulated_sample.csv")
    boots = read_csv("results/bootstrap_draws.csv")
    coverage = read_csv("results/coverage_trials.csv")
    null = read_csv("results/null_draws.csv")
    assert summary["simulation_only"] is True
    assert len(original) == 800
    assert np.isin(original["support"], [0, 1]).all()
    for n in [50, 200, 800]:
        base = summary["samples"][str(n)]
        assert int(original["support"][:n].sum()) == base["supporters"]
        subset = boots[boots["n"] == n]
        assert len(subset) == 20_000
        assert np.allclose(subset["bootstrap_share"], subset["supporters"] / n)
        assert np.allclose(np.quantile(subset["bootstrap_share"], [.025, .975]),
                           base["bootstrap_ci_95"])
        trials = coverage[coverage["n"] == n]
        assert len(trials) == 5_000
        for confidence in [90, 95, 99]:
            lo, hi = trials[f"lower_{confidence}"], trials[f"upper_{confidence}"]
            hits = (lo <= .55) & (.55 <= hi)
            metric = base["coverage"][str(confidence)]
            assert np.array_equal(hits, trials[f"covers_{confidence}"].astype(bool))
            assert int(hits.sum()) == metric["covered"]
            assert np.isclose(hits.mean(), metric["coverage"])
            assert np.isclose(100 * (hi - lo).mean(), metric["mean_width_pp"])
        # Exact infinite-bootstrap coverage in this Bernoulli model is a useful
        # independent check; finite resampling and outer simulation add noise.
        k = np.arange(n + 1)
        exact_lower = binom.ppf(.025, n, k / n) / n
        exact_upper = binom.ppf(.975, n, k / n) / n
        exact_hit = (exact_lower <= .55) & (.55 <= exact_upper)
        theoretical_coverage = binom.pmf(k[exact_hit], n, .55).sum()
        assert abs(base["coverage"]["95"]["coverage"] - theoretical_coverage) < .02
        counts = null[null["n"] == n]["supporters"].astype(int)
        assert len(counts) == 50_000
        test = base["test"]
        distance = abs(2 * base["supporters"] - n)
        tail = int(np.count_nonzero(np.abs(2 * counts - n) >= distance))
        assert tail == test["null_tail_count"]
        assert np.isclose((tail + 1) / 50_001, test["simulated_p_value"])
        exact_p = float(min(1, 2 * binom.sf(max(base["supporters"], n - base["supporters"]) - 1, n, .5)))
        assert np.isclose(exact_p, test["exact_binomial_p_value"])
        se = np.sqrt(exact_p * (1 - exact_p) / 50_000)
        assert abs(test["simulated_p_value"] - exact_p) < 5 * se + 1 / 50_001
        reject = (counts <= test["critical_left"]) | (counts >= test["critical_right"])
        assert np.isclose(reject.mean(), test["simulated_rejection_rate"])
        assert reject.mean() <= .05
        assert test["critical_left"] + test["critical_right"] == n
        print(f"n={n}: saved draws verified; 95% coverage {base['coverage']['95']['coverage']:.4f}; "
              f"infinite-bootstrap binomial check {theoretical_coverage:.4f}; exact p={exact_p:.6f}")
    widths = [summary["samples"][str(n)]["coverage"]["95"]["mean_width_pp"] for n in [50, 200, 800]]
    assert widths[0] > widths[1] > widths[2]
    for n in [50, 200, 800]:
        metrics = summary["samples"][str(n)]["coverage"]
        assert metrics["90"]["mean_width_pp"] < metrics["95"]["mean_width_pp"] < metrics["99"]["mean_width_pp"]
        assert metrics["90"]["coverage"] <= metrics["95"]["coverage"] <= metrics["99"]["coverage"]
    assert "{{" not in (ROOT / "blog8.qmd").read_text()
    print("All independent numerical checks passed.")


if __name__ == "__main__":
    main()
