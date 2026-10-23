"""Reproduce the illustrative model, figure, numerical results, and Quarto post.

Run from any directory: python path/to/post1/code/build.py
No network access, empirical data, or Quarto installation is required here.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MultipleLocator

ROOT = Path(__file__).resolve().parents[1]
PARAMS = json.loads((ROOT / "data/model.json").read_text(encoding="utf-8"))
PX = float(PARAMS["price_food_dollars"])
PY = float(PARAMS["price_drink_dollars"])
BUDGET = float(PARAMS["budget_dollars"])
NEW_BUDGET = float(PARAMS["comparison_budget_dollars"])
TRANSFER = float(PARAMS["transfer_to_food_dollars"])


def allocation(food_spend: float, budget: float = BUDGET) -> dict[str, float]:
    """Utility and marginal utility per dollar at a full-budget allocation."""
    x = food_spend / PX
    y = (budget - food_spend) / PY
    return {
        "budget_dollars": budget,
        "food_spend_dollars": food_spend,
        "drink_spend_dollars": budget - food_spend,
        "food_portions": x,
        "drink_portions": y,
        "satisfaction_score": x * y,
        "food_marginal_score_per_dollar": y / PX,
        "drink_marginal_score_per_dollar": x / PY,
    }


def optimum(budget: float) -> dict[str, float]:
    """For U=xy and positive prices, each good receives half of expenditure."""
    return allocation(budget / 2, budget)


def write_csv(path: Path, rows: list[dict[str, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def number(value: float) -> str:
    return f"{value:g}"


def main() -> None:
    if not (PX > 0 and PY > 0 and BUDGET > 0 and NEW_BUDGET > 0):
        raise ValueError("Prices and budgets must be positive.")
    # The text template teaches this particular example; do not silently reuse
    # its narrative after changing the economic assumptions.
    if (PX, PY, BUDGET, NEW_BUDGET, TRANSFER) != (2, 1, 12, 13, 2):
        raise ValueError("If changing assumptions, revise article_template.txt too.")

    results = ROOT / "results"
    figures = results / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    initial = allocation(float(PARAMS["initial_food_portions"]) * PX)
    best = optimum(BUDGET)
    second_switch = allocation(initial["food_spend_dollars"] + 2 * TRANSFER)
    richer = optimum(NEW_BUDGET)
    multiplier = BUDGET / (2 * PX * PY)
    exact_gain = richer["satisfaction_score"] - best["satisfaction_score"]
    curve = [allocation(BUDGET * i / 600) for i in range(601)]

    # Verify feasibility, the actual maximum over the full feasible segment,
    # and the difference between a derivative and a finite budget increase.
    assert abs(PX * best["food_portions"] + PY * best["drink_portions"] - BUDGET) < 1e-12
    assert best["food_marginal_score_per_dollar"] == multiplier
    assert best["drink_marginal_score_per_dollar"] == multiplier
    assert all(row["satisfaction_score"] <= best["satisfaction_score"] + 1e-12 for row in curve)
    assert best["satisfaction_score"] > initial["satisfaction_score"]
    assert second_switch["satisfaction_score"] == initial["satisfaction_score"]
    # Along the budget, U(s)=s(B-s)/(px*py); second derivative is negative.
    assert -2 / (PX * PY) < 0
    increment = NEW_BUDGET - BUDGET
    assert abs(exact_gain - (multiplier * increment + increment**2 / (4 * PX * PY))) < 1e-12

    summary = {
        "data_status": "Illustrative assumptions, not empirical observations.",
        "initial": initial,
        "optimum": best,
        "second_switch": second_switch,
        "larger_budget_optimum": richer,
        "lagrange_multiplier_score_per_dollar": multiplier,
        "exact_score_gain": exact_gain,
        "linear_approximation_to_gain": multiplier * increment,
        "finite_change_minus_linear_approximation": exact_gain - multiplier * increment,
        "maximization_check": "U(s)=s(B-s)/(px*py), with negative second derivative on 0<=s<=B.",
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(results / "spending_curve.csv", curve)
    write_csv(results / "example_allocations.csv", [initial, best, second_switch, richer])

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.labelsize": 11,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#A8ADB4",
        "text.color": "#1F2933",
        "axes.labelcolor": "#1F2933",
        "xtick.color": "#4B5563",
        "ytick.color": "#4B5563",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })
    blue, orange, grey = "#1D5C83", "#AE4B1E", "#6B7280"
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(7.3, 7.5), sharex=True,
                                      gridspec_kw={"height_ratios": [1.1, 1]})
    fig.subplots_adjust(left=0.12, right=0.97, top=0.94, bottom=0.11, hspace=0.47)
    spending = [row["food_spend_dollars"] for row in curve]
    scores = [row["satisfaction_score"] for row in curve]
    top.plot(spending, scores, color=blue, linewidth=2.8)
    top.set_title("A. The highest score uses $6 for each good", loc="left", pad=13)
    top.set_ylabel("Satisfaction score (points)")
    top.set_ylim(0, 23)
    top.yaxis.set_major_locator(MultipleLocator(6))
    top.vlines(best["food_spend_dollars"], 0, best["satisfaction_score"], color=grey,
               linewidth=1, linestyle=(0, (3, 3)), zorder=0)
    for row, xytext, label in [
        (initial, (2.4, 19.5), "2 food, 8 drink\n16 points"),
        (best, (6, 20.3), "3 food, 6 drink\n18 points"),
        (second_switch, (9.6, 19.5), "4 food, 4 drink\n16 points"),
    ]:
        xx, yy = row["food_spend_dollars"], row["satisfaction_score"]
        top.scatter([xx], [yy], s=48, facecolors=blue, edgecolors="white", zorder=3)
        top.annotate(label, xy=(xx, yy), xytext=xytext, ha="center", va="center", fontsize=10,
                     arrowprops={"arrowstyle": "-", "color": grey, "linewidth": 0.8})
    top.grid(axis="y", color="#E7E9EC", linewidth=0.7, zorder=0)
    top.set_axisbelow(True)

    food_returns = [row["food_marginal_score_per_dollar"] for row in curve]
    drink_returns = [row["drink_marginal_score_per_dollar"] for row in curve]
    bottom.plot(spending, food_returns, color=blue, linewidth=2.8)
    bottom.plot(spending, drink_returns, color=orange, linewidth=2.8, linestyle=(0, (5, 2)))
    bottom.set_title("B. At that point, both uses of a dollar have the same return", loc="left", pad=13)
    bottom.set_ylabel("Marginal score per dollar")
    bottom.set_xlabel("Dollars spent on food (the rest of $12 buys drinks)", labelpad=10)
    bottom.set_xlim(0, BUDGET)
    bottom.set_ylim(0, 6.4)
    bottom.xaxis.set_major_locator(MultipleLocator(2))
    bottom.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    bottom.yaxis.set_major_locator(MultipleLocator(1))
    bottom.axvline(best["food_spend_dollars"], color=grey, linewidth=1, linestyle=(0, (3, 3)), zorder=0)
    bottom.scatter([best["food_spend_dollars"]], [multiplier], color="#1F2933", s=46, zorder=3)
    bottom.annotate("Both return 3 points per dollar", xy=(6, 3), xytext=(6, 4.2),
                    ha="center", va="center", fontsize=10,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 2},
                    arrowprops={"arrowstyle": "-", "color": grey, "linewidth": 0.8})
    bottom.text(9.15, 5.22, "Drinks", color=orange, fontsize=11, fontweight="bold")
    bottom.text(9.15, 0.72, "Food", color=blue, fontsize=11, fontweight="bold")
    bottom.grid(axis="y", color="#E7E9EC", linewidth=0.7, zorder=0)
    bottom.set_axisbelow(True)
    fig.savefig(figures / "budget_and_marginal_returns.png", dpi=200)
    plt.close(fig)

    values = {
        "ORIGINAL_DATE": PARAMS["original_publication_date"],
        "REVISION_DATE": PARAMS["revision_date"],
        "BUDGET": BUDGET, "NEW_BUDGET": NEW_BUDGET,
        "PX": PX, "PY": PY, "TRANSFER": TRANSFER,
        "INITIAL_X": initial["food_portions"], "INITIAL_Y": initial["drink_portions"],
        "INITIAL_U": initial["satisfaction_score"],
        "INITIAL_FOOD_RETURN": initial["food_marginal_score_per_dollar"],
        "INITIAL_DRINK_RETURN": initial["drink_marginal_score_per_dollar"],
        "OPT_X": best["food_portions"], "OPT_Y": best["drink_portions"],
        "OPT_U": best["satisfaction_score"], "AFTER_U": second_switch["satisfaction_score"],
        "NEW_U": richer["satisfaction_score"], "GAIN": exact_gain,
        "LAMBDA": multiplier,
        "X_DENOM": 2 * PX, "Y_DENOM": 2 * PY, "V_DENOM": 4 * PX * PY,
    }
    article = (ROOT / "code/article_template.txt").read_text(encoding="utf-8")
    for key, value in values.items():
        article = article.replace(f"@@{key}@@", value if isinstance(value, str) else number(value))
    if "@@" in article:
        raise ValueError("Unfilled article template token.")
    (ROOT / "blog1-260906.qmd").write_text(article, encoding="utf-8")
    print(json.dumps({"optimum": best, "lambda": multiplier, "exact_extra_dollar_gain": exact_gain}, indent=2))


if __name__ == "__main__":
    main()
