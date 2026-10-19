"""Reproduce maps, tract results, summaries, and the Quarto article offline."""

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results"
FIG = OUT / "figures"
COLORS = {"high_lower": "#b0443e", "high_higher": "#286a8c",
          "low_lower": "#e4bca8", "low_higher": "#c4d9df", "missing": "#e4e6e5"}
LABELS = {"high_lower": "More car-free / lower income", "high_higher": "More car-free / higher income",
          "low_lower": "Less car-free / lower income", "low_higher": "Less car-free / higher income",
          "missing": "Income unavailable or no households"}


def read_inputs():
    sources = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
    for item in sources["sources"]:
        digest = hashlib.sha256((ROOT / item["local_file"]).read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Snapshot checksum differs: {item['local_file']}")
    vehicles = pd.read_csv(RAW / "acsdt5y2024-b08201-philadelphia.dat", sep="|", dtype={"GEO_ID": str})
    income = pd.read_csv(RAW / "acsdt5y2024-b19013-philadelphia.dat", sep="|", dtype={"GEO_ID": str})
    # Preserve the source margins of error, but remove negative missing-value codes.
    joined = vehicles[["GEO_ID", "B08201_E001", "B08201_M001", "B08201_E002", "B08201_M002"]].merge(
        income, on="GEO_ID", how="outer", validate="one_to_one", indicator=True)
    if not joined["_merge"].eq("both").all():
        raise ValueError("ACS tables do not cover the same geographies")
    joined = joined.drop(columns="_merge").rename(columns={
        "B08201_E001": "households", "B08201_M001": "households_moe90",
        "B08201_E002": "no_vehicle_households", "B08201_M002": "no_vehicle_moe90",
        "B19013_E001": "median_household_income", "B19013_M001": "income_moe90"})
    for column in joined.columns.drop("GEO_ID"):
        joined[column] = pd.to_numeric(joined[column], errors="coerce")
        joined.loc[joined[column] < 0, column] = np.nan
    city = joined.loc[joined["GEO_ID"].eq("0500000US42101")].iloc[0]
    tracts = joined.loc[joined["GEO_ID"].str.startswith("1400000US42101")].copy()
    tracts["GEOID"] = tracts["GEO_ID"].str[-11:]
    tracts["no_vehicle_pct"] = 100 * tracts["no_vehicle_households"] / tracts["households"].replace(0, np.nan)
    shape = gpd.read_file(RAW / "philadelphia_tracts_2024.geojson")
    spatial = shape.merge(tracts, on="GEOID", how="outer", validate="one_to_one", indicator=True)
    if len(spatial) != 408 or not spatial["_merge"].eq("both").all():
        raise ValueError("Boundary/statistic join must match all 408 tracts")
    spatial = spatial.drop(columns="_merge").sort_values("GEOID").reset_index(drop=True)
    if not spatial.geometry.is_valid.all():
        raise ValueError("Invalid tract geometry")
    if not np.isclose(spatial["households"].sum(), city["households"]):
        raise ValueError("Tract household counts do not add to the county estimate")
    if not np.isclose(spatial["no_vehicle_households"].sum(), city["no_vehicle_households"]):
        raise ValueError("Tract no-vehicle counts do not add to the county estimate")
    if not spatial["no_vehicle_pct"].dropna().between(0, 100).all():
        raise ValueError("Vehicle shares outside [0,100]")
    return spatial, city, sources


def classify(spatial, city):
    rate = 100 * city["no_vehicle_households"] / city["households"]
    income = city["median_household_income"]
    usable = spatial["no_vehicle_pct"].notna() & spatial["median_household_income"].notna()
    spatial["group"] = "missing"
    for high, prefix in [(True, "high"), (False, "low")]:
        for lower, suffix in [(True, "lower"), (False, "higher")]:
            mask = usable & spatial["no_vehicle_pct"].ge(rate).eq(high) & spatial["median_household_income"].lt(income).eq(lower)
            spatial.loc[mask, "group"] = f"{prefix}_{suffix}"
    rows = []
    for key in LABELS:
        subset = spatial[spatial["group"].eq(key)]
        hh, nv = subset["households"].sum(), subset["no_vehicle_households"].sum()
        rows.append({"group": key, "description": LABELS[key], "tracts": len(subset), "households": int(hh),
                     "no_vehicle_households": int(nv), "no_vehicle_pct": 100*nv/hh if hh else None,
                     "share_city_households_pct": 100*hh/city["households"],
                     "share_city_no_vehicle_pct": 100*nv/city["no_vehicle_households"]})
    return spatial, pd.DataFrame(rows), rate, income


def setup_style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.labelcolor": "#253641", "text.color": "#253641",
                         "axes.edgecolor": "#a7b0b5", "savefig.facecolor": "white"})


def make_map(spatial, rate, income):
    projected = spatial.to_crs(26918)  # NAD83 / UTM zone 18N, metres.
    fig, ax = plt.subplots(figsize=(10, 9.8))
    fig.subplots_adjust(left=.02, right=.98, top=.88, bottom=.20)
    for key in LABELS:
        part = projected[projected["group"].eq(key)]
        part.plot(ax=ax, color=COLORS[key], edgecolor="white", linewidth=.30, zorder=2)
    projected.dissolve().boundary.plot(ax=ax, color="#6b777c", linewidth=.65, zorder=3)
    xmin, ymin, xmax, ymax = projected.total_bounds
    ax.set_xlim(xmin-1800, xmax+1800)
    ax.set_ylim(ymin-1800, ymax+1200)
    ax.set_aspect("equal")
    ax.axis("off")
    # Approximate context labels, not neighborhood boundaries or analysis units.
    context = [("Center City", -75.1636, 39.9526, (19, -13)),
               ("West Philadelphia", -75.230, 39.972, (-96, -2)),
               ("North Philadelphia", -75.155, 40.007, (-91, 15)),
               ("Northeast", -75.015, 40.102, (8, 8))]
    points = gpd.GeoSeries(gpd.points_from_xy([x[1] for x in context], [x[2] for x in context]), crs=4326).to_crs(26918)
    for (label, _, _, offset), point in zip(context, points):
        ann = ax.annotate(label, (point.x, point.y), xytext=offset, textcoords="offset points",
                          fontsize=10, weight="medium", zorder=5,
                          arrowprops={"arrowstyle": "-", "color": "#3d4b53", "lw": .7})
        ann.set_path_effects([patheffects.withStroke(linewidth=3, foreground="white")])
    # A 5 km scale bar. The arrow indicates grid north in this local UTM projection.
    sx, sy = xmin+1300, ymin+700
    ax.plot([sx, sx+5000], [sy, sy], color="#253641", linewidth=2.2, zorder=5)
    ax.text(sx+2500, sy+350, "5 km", ha="center", fontsize=9)
    ax.annotate("N", xy=(.945, .90), xytext=(.945, .82), xycoords="axes fraction",
                textcoords="axes fraction", ha="center", weight="bold",
                arrowprops={"arrowstyle": "->", "color": "#253641", "lw": 1.4})
    fig.text(.06, .952, "Car-free households occur in different income settings", fontsize=18, weight="bold")
    fig.text(.06, .915, "Philadelphia census tracts · ACS 2020–2024 estimates", fontsize=12, color="#596a73")
    keys = ["high_lower", "high_higher", "low_lower", "low_higher", "missing"]
    handles = [Patch(facecolor=COLORS[k], edgecolor="white", label=LABELS[k]) for k in keys]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(.055, .066), ncol=2,
               frameon=False, fontsize=10, columnspacing=2.1, handlelength=1.6, labelspacing=.9)
    fig.text(.06, .048, f"City reference values: {rate:.1f}% without a vehicle; median household income ${income:,.0f}.", fontsize=9.5)
    fig.text(.06, .025, "Sources: U.S. Census Bureau, ACS B08201/B19013 and 2024 cartographic boundaries. Projection: EPSG:26918.", fontsize=8.5, color="#596a73")
    fig.savefig(FIG / "car_free_income_map.png", dpi=190)
    plt.close(fig)


def make_scatter(spatial, rate, income):
    valid = spatial[~spatial["group"].eq("missing")].copy()
    fig, ax = plt.subplots(figsize=(9.6, 6.8))
    fig.subplots_adjust(left=.10, right=.97, top=.83, bottom=.19)
    for k in ["low_higher", "low_lower", "high_higher", "high_lower"]:
        part = valid[valid["group"].eq(k)]
        ax.scatter(part["median_household_income"], part["no_vehicle_pct"], s=32, c=COLORS[k],
                   alpha=.78, edgecolors="white", linewidths=.35, zorder=3)
    ax.axhline(rate, ls="--", color="#576872", lw=1)
    ax.axvline(income, ls="--", color="#576872", lw=1)
    ax.text(income+1800, 82, f"City median: ${income:,.0f}", fontsize=9, rotation=90, va="top")
    ax.text(233000, rate+1.4, f"City no-vehicle share: {rate:.1f}%", fontsize=9, ha="right")
    # Two examples selected by transparent rules, not hand-entered statistics.
    richer = valid[(valid["no_vehicle_pct"] >= 50) & (valid["households"] >= 1000)].nlargest(1, "median_household_income").iloc[0]
    lower = valid[(valid["median_household_income"] < 30000) & (valid["households"] >= 1000)].nlargest(1, "no_vehicle_pct").iloc[0]
    for row, offset in [(richer, (10, -24)), (lower, (16, 5))]:
        ax.scatter(row["median_household_income"], row["no_vehicle_pct"], s=95,
                   facecolors="none", edgecolors="#253641", linewidths=1.2, zorder=4)
        label = f"Tract {row['NAME']}\n${row['median_household_income']:,.0f}; {row['no_vehicle_pct']:.1f}%"
        ax.annotate(label, (row["median_household_income"], row["no_vehicle_pct"]), xytext=offset,
                    textcoords="offset points", fontsize=9, zorder=5,
                    bbox={"boxstyle": "round,pad=.25", "fc": "white", "ec": "none", "alpha": .9})
    ax.set(xlim=(0, 240000), ylim=(0, 90), xlabel="Tract median household income (2024 dollars)",
           ylabel="Households with no vehicle available (%)")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x/1000:,.0f}k"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e8ecee", zorder=0)
    fig.text(.10, .94, "A similar no-vehicle share can accompany very different incomes", fontsize=15, weight="bold")
    fig.text(.10, .895, f"One dot per tract with usable data (n = {len(valid)}); colors match the map", fontsize=11, color="#596a73")
    fig.text(.10, .085, "Dashed lines are citywide reference values. Every tract has equal dot size; these are area-level comparisons.", fontsize=9)
    fig.text(.10, .048, "Source: U.S. Census Bureau, ACS 2020–2024, tables B08201 and B19013. No causal effect is estimated.", fontsize=9, color="#596a73")
    fig.savefig(FIG / "income_vehicle_scatter.png", dpi=190)
    plt.close(fig)
    return richer, lower


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    setup_style()
    spatial, city, sources = read_inputs()
    spatial, groups, rate, income = classify(spatial, city)
    make_map(spatial, rate, income)
    richer, lower = make_scatter(spatial, rate, income)
    spatial.drop(columns="geometry").to_csv(OUT / "tract_results.csv", index=False, float_format="%.8f")
    groups.to_csv(OUT / "group_summary.csv", index=False, float_format="%.8f")
    # Sensitivity is descriptive: a second, rounded rule is not a significance test.
    sensitivity = []
    for rate_cut, income_cut, label in [(rate, income, "City references"), (30.0, 60000.0, "Rounded references")]:
        sub = spatial[(spatial["no_vehicle_pct"] >= rate_cut) & (spatial["median_household_income"] < income_cut)]
        sensitivity.append({"rule": label, "no_vehicle_pct_cutoff": rate_cut, "income_cutoff": income_cut,
                            "tracts": len(sub), "no_vehicle_households": int(sub["no_vehicle_households"].sum()),
                            "share_city_no_vehicle_pct": 100*sub["no_vehicle_households"].sum()/city["no_vehicle_households"]})
    pd.DataFrame(sensitivity).to_csv(OUT / "sensitivity.csv", index=False, float_format="%.8f")
    priority = groups.set_index("group").loc["high_lower"]
    higher = groups.set_index("group").loc["high_higher"]
    missing = groups.set_index("group").loc["missing"]
    values = {"tracts": len(spatial), "usable": int((spatial["group"] != "missing").sum()),
              "city_households": int(city["households"]), "city_no_vehicle": int(city["no_vehicle_households"]),
              "city_rate": float(rate), "city_income": int(income),
              "priority_tracts": int(priority["tracts"]), "priority_no_vehicle": int(priority["no_vehicle_households"]),
              "priority_city_hh_share": float(priority["share_city_households_pct"]),
              "priority_city_no_vehicle_share": float(priority["share_city_no_vehicle_pct"]),
              "higher_tracts": int(higher["tracts"]), "higher_no_vehicle": int(higher["no_vehicle_households"]),
              "missing_tracts": int(missing["tracts"]), "missing_no_vehicle": int(missing["no_vehicle_households"]),
              "missing_city_no_vehicle_share": float(missing["share_city_no_vehicle_pct"]),
              "zero_household_tracts": int(spatial["households"].eq(0).sum()),
              "richer_tract": str(richer["NAME"]), "richer_income": int(richer["median_household_income"]),
              "richer_rate": float(richer["no_vehicle_pct"]), "lower_tract": str(lower["NAME"]),
              "lower_income": int(lower["median_household_income"]), "lower_rate": float(lower["no_vehicle_pct"]),
              "rounded_tracts": sensitivity[1]["tracts"], "rounded_no_vehicle_share": sensitivity[1]["share_city_no_vehicle_pct"],
              "retrieved_date": sources["retrieved_utc"][:10], "map_crs": "EPSG:26918"}
    (OUT / "summary.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    tokens = {k: (f"{v:,.0f}" if isinstance(v, int) else f"{v:.1f}" if isinstance(v, float) else str(v))
              for k, v in values.items()}
    # The table is generated from the same aggregated results used in the text.
    table = ["| Tract setting | Tracts | No-vehicle households | Share of city's no-vehicle households |",
             "|---|---:|---:|---:|"]
    for _, row in groups.iterrows():
        table.append(f"| {row['description']} | {int(row['tracts'])} | {int(row['no_vehicle_households']):,} | {row['share_city_no_vehicle_pct']:.1f}% |")
    tokens["group_table"] = "\n".join(table)
    article = (ROOT / "code/article_template.txt").read_text(encoding="utf-8")
    for key, value in tokens.items():
        article = article.replace(f"@@{key}@@", value)
    if "@@" in article:
        raise ValueError("Unfilled article placeholder")
    (ROOT / "blog5.qmd").write_text(article, encoding="utf-8")
    print(json.dumps(values, indent=2))
    print("All 408 joins and city totals checked; figures, tables and blog5.qmd generated.")


if __name__ == "__main__":
    main()
