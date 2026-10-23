"""Run the tutorial, draw one comparison, and build the static Quarto article."""
from pathlib import Path
import argparse
import json
import re
import runpy

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def snippet(name: str) -> str:
    source = (ROOT / "code/tutorial.py").read_text(encoding="utf-8")
    found = re.search(rf"^# START {name}\n(.*?)^# END {name}$",
                      source, flags=re.MULTILINE | re.DOTALL)
    if not found:
        raise ValueError(f"Missing lesson section: {name}")
    return found.group(1).strip()


def markdown_table(headers, rows) -> str:
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(str(x) for x in row) + " |" for row in rows),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerate-data", action="store_true")
    args = parser.parse_args()
    if args.regenerate_data:
        runpy.run_path(str(ROOT / "code/generate_data.py"), run_name="__main__")
    runpy.run_path(str(ROOT / "code/tutorial.py"), run_name="__main__")

    params = json.loads((ROOT / "data/simulation.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "results/validation.json").read_text(encoding="utf-8"))
    estimates = pd.read_csv(ROOT / "results/ige_estimates.csv")
    preview = pd.read_csv(ROOT / "results/match_preview.csv")
    assert estimates.n.eq(params["families"]).all()
    assert params["source_kind"].startswith("simulated")

    fig, ax = plt.subplots(figsize=(8, 4.7))
    fig.patch.set_facecolor("white")
    y = np.array([3, 2, 1, 0])
    palette = ["#DC8840", "#3C8990", "#DC8840", "#3C8990"]
    ax.barh(y, estimates.ige, height=0.54, color=palette)
    labels = ["Child age 25\nSingle year", "Child ages 25–29\nFive-year mean",
              "Child age 40\nSingle year", "Child ages 40–44\nFive-year mean"]
    ax.set_yticks(y, labels, fontsize=10.5)
    ax.tick_params(axis="y", length=0, pad=9)
    ax.set_xlim(0, max(.61, float(estimates.ige.max()) + .12))
    ax.set_xticks(np.arange(0, .61, .1))
    ax.set_xlabel("Estimated intergenerational elasticity (IGE)", fontsize=11)
    ax.axvline(params["model_ige"], color="#2C3E50", linestyle="--", linewidth=1.4)
    ax.text(params["model_ige"] - .015, 3.60, "Model parameter: 0.50",
            color="#2C3E50", fontsize=10, ha="right")
    for ypos, value in zip(y, estimates.ige):
        label_x = (params["model_ige"] + .012
                   if 0 < params["model_ige"] - value < .05 else value + .009)
        ax.text(label_x, ypos, f"{value:.3f}", va="center", fontsize=11,
                color="#243443", fontweight="bold")
    ax.set_ylim(-.55, 3.9)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="#E5E9EC", linewidth=.7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.suptitle("Income timing changes the measured link", x=.035, y=.97,
                 ha="left", fontsize=16, fontweight="bold", color="#243443")
    fig.text(.035, .895, f"Simulation • same {params['families']:,} pairs • one linked parent per child",
             fontsize=10, color="#526575")
    fig.text(.035, .025, "Single-year parent: age 40. Averaged parent: ages 40–44.",
             fontsize=9, color="#526575")
    fig.subplots_adjust(left=.27, right=.97, top=.82, bottom=.16)
    figure_dir = ROOT / "results/figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_dir / "income_timing.png", dpi=200, facecolor="white")
    plt.close(fig)

    values = estimates.ige.to_list()
    result_rows = zip(
        ["25", "25–29", "40", "40–44"],
        ["Single year", "Five-year mean", "Single year", "Five-year mean"],
        [f"{v:.3f}" for v in values],
    )
    replacements = {
        "N": f"{params['families']:,}",
        "ROWS": f"{params['person_years']:,}",
        "TARGET": f"{params['model_ige']:.2f}",
        "BAD_ROWS": f"{audit['family_only_join_rows']:,}",
        "SETUP": snippet("setup") + "\n\n" + snippet("load"),
        **{k.upper(): snippet(k) for k in ["match", "aggregate", "attach", "estimate"]},
        "MATCH_PREVIEW": markdown_table(preview.columns, preview.itertuples(index=False, name=None)),
        "RESULT_TABLE": markdown_table(["Child age(s)", "Income window", "IGE"], result_rows),
        **dict(zip(["YOUNG_ONE", "YOUNG_MEAN", "MID_ONE", "MID_MEAN"],
                   [f"{v:.3f}" for v in values])),
    }
    template = (ROOT / "code/article_template.txt").read_text(encoding="utf-8")
    for key, value in replacements.items():
        token = f"@@{key}@@"
        assert token in template, f"Unused generated value: {key}"
        template = template.replace(token, value)
    assert not re.search(r"@@[A-Z_0-9]+@@", template)
    (ROOT / "blog6.qmd").write_text(template, encoding="utf-8")
    with (ROOT / "results/sessionInfo.txt").open("a", encoding="utf-8") as stream:
        stream.write(f"Matplotlib: {matplotlib.__version__}\n")
    print("Built blog6.qmd and the income-timing figure from executed lesson code.")


if __name__ == "__main__":
    main()
