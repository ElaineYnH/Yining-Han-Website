from pathlib import Path
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SERIES = ["MSPUS", "MORTGAGE30US", "CPIAUCSL", "CES0500000003"]
START, END = "2019-01-01", "2025-12-31"
ANALYSIS_END = "2025-09-30"
QUARTERS = pd.period_range("2019Q1", "2025Q3", freq="Q")
BLUE, ORANGE = "#245B87", "#B65F26"


def refresh_data():
    records = []
    for series in SERIES:
        url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
               f"&cosd={START}&coed={END}")
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (course replication)"})
        with urlopen(request, timeout=60) as response:
            content = response.read()
        if not content.startswith(b"observation_date,"):
            raise ValueError(f"FRED returned an unexpected response for {series}.")
        path = ROOT / "data" / "raw" / f"{series}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        records.append({
            "series_id": series, "url": url,
            "file": f"data/raw/{series}.csv",
            "retrieved_on": datetime.now(timezone.utc).date().isoformat(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        })
    (ROOT / "data" / "sources.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8")


def load_quarterly():
    records = json.loads((ROOT / "data" / "sources.json").read_text())
    if {record["series_id"] for record in records} != set(SERIES):
        raise ValueError("The source manifest must contain the four specified series.")
    quarterly = {}
    counts = {}
    for series in SERIES:
        record = next(item for item in records if item["series_id"] == series)
        path = ROOT / record["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"The saved {series} snapshot differs from sources.json.")
        raw = pd.read_csv(path, na_values=["."], parse_dates=["observation_date"])
        # October 2025 CPI is missing, so stop at the last complete 2025 quarter.
        raw = raw.loc[raw["observation_date"].between(START, ANALYSIS_END)].copy()
        if raw["observation_date"].duplicated().any() or raw[series].isna().any():
            raise ValueError(f"Duplicate dates or missing observations in {series}.")
        raw[series] = pd.to_numeric(raw[series], errors="raise")
        raw["quarter"] = raw["observation_date"].dt.to_period("Q")
        grouped = raw.groupby("quarter")[series]
        quarterly[series] = grouped.mean().reindex(QUARTERS)
        counts[series] = grouped.count().reindex(QUARTERS)
        if series == "MSPUS" and not counts[series].eq(1).all():
            raise ValueError("Each quarter must contain one published new-home median.")
        if series in ["CPIAUCSL", "CES0500000003"] and not counts[series].eq(3).all():
            raise ValueError(f"Each quarter needs three monthly observations of {series}.")
        if series == "MORTGAGE30US" and not counts[series].between(12, 14).all():
            raise ValueError("Each quarter needs a complete set of weekly mortgage rates.")
    frame = pd.DataFrame(quarterly).rename(columns={
        "MSPUS": "price_usd", "MORTGAGE30US": "mortgage_rate_pct",
        "CPIAUCSL": "cpi", "CES0500000003": "hourly_earnings_usd",
    })
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("The four series must cover all 27 analysis quarters.")
    if not (frame > 0).all().all():
        raise ValueError("Prices, earnings, CPI, and mortgage rates must be positive.")
    for series in SERIES:
        frame[f"n_{series}"] = counts[series].astype(int)
    return frame, records


def monthly_payment(principal, annual_rate_pct):
    monthly_rate = np.asarray(annual_rate_pct, dtype=float) / 1200
    factor = monthly_rate / (-np.expm1(-360 * np.log1p(monthly_rate)))
    return np.asarray(principal, dtype=float) * factor


def transform(frame):
    frame = frame.copy()
    first = frame.iloc[0]
    frame["real_price_index"] = (
        100 * (frame.price_usd / frame.cpi) / (first.price_usd / first.cpi))
    frame["real_earnings_index"] = (
        100 * (frame.hourly_earnings_usd / frame.cpi)
        / (first.hourly_earnings_usd / first.cpi))
    frame["loan_usd"] = 0.8 * frame.price_usd
    frame["payment_usd"] = monthly_payment(frame.loan_usd, frame.mortgage_rate_pct)
    frame["fixed_rate_payment_usd"] = monthly_payment(
        frame.loan_usd, first.mortgage_rate_pct)
    frame["payment_hours"] = frame.payment_usd / frame.hourly_earnings_usd
    frame["fixed_rate_hours"] = frame.fixed_rate_payment_usd / frame.hourly_earnings_usd
    return frame


def base_plot(ylabel, title):
    figure, axis = plt.subplots(figsize=(8.6, 4.9))
    axis.set_title(title, loc="left", fontsize=15, fontweight="bold", pad=16)
    axis.set_ylabel(ylabel, labelpad=10)
    axis.set_xlabel("Quarter", labelpad=8)
    axis.grid(axis="y", color="#DCE2E7", linewidth=0.7)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#A7AFB7")
    axis.tick_params(axis="both", length=0, pad=7)
    ticks = [i for i, quarter in enumerate(QUARTERS) if quarter.quarter == 1]
    axis.set_xticks(ticks, [str(QUARTERS[i].year) for i in ticks])
    axis.set_xlim(-0.4, len(QUARTERS) + 1.6)
    return figure, axis


def save_plot(figure, filename):
    figure.tight_layout()
    figure.savefig(ROOT / "results" / "figures" / filename,
                   dpi=200, facecolor="white", metadata={"Software": "matplotlib"})
    plt.close(figure)


def make_figures(frame):
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.labelcolor": "#293642", "text.color": "#293642",
        "xtick.color": "#475562", "ytick.color": "#475562",
        "legend.frameon": False,
    })
    x = np.arange(len(frame))
    latest = frame.iloc[-1]
    figure, axis = base_plot("Real index (2019 Q1 = 100)",
                            "Real new-home prices and earnings moved closer again")
    axis.plot(x, frame.real_price_index, color=BLUE, linewidth=2.4,
              label="Median new-home price")
    axis.plot(x, frame.real_earnings_index, color=ORANGE, linewidth=2.4,
              label="Average hourly earnings")
    axis.axhline(100, color="#808D99", linewidth=1, linestyle=":")
    axis.set_ylim(88, 129)
    axis.yaxis.set_major_locator(MultipleLocator(10))
    axis.scatter([x[-1]] * 2, [latest.real_price_index, latest.real_earnings_index],
                 color=[BLUE, ORANGE], s=26, zorder=3)
    axis.annotate(f"{latest.real_price_index:.1f}",
                  (x[-1], latest.real_price_index), xytext=(9, -15),
                  textcoords="offset points", color=BLUE, fontsize=10)
    axis.annotate(f"{latest.real_earnings_index:.1f}",
                  (x[-1], latest.real_earnings_index), xytext=(9, 7),
                  textcoords="offset points", color=ORANGE, fontsize=10)
    axis.legend(loc="upper left")
    save_plot(figure, "real_prices_earnings.png")

    figure, axis = base_plot("30-year mortgage rate (%)",
                            "New borrowers faced a much higher interest rate")
    axis.plot(x, frame.mortgage_rate_pct, color=BLUE, linewidth=2.4)
    baseline = frame.mortgage_rate_pct.iloc[0]
    axis.axhline(baseline, color="#808D99", linewidth=1, linestyle=":",
                label=f"2019 Q1 rate: {baseline:.2f}%")
    for idx, offset in [(frame.mortgage_rate_pct.idxmin(), (12, -18)),
                        (frame.mortgage_rate_pct.idxmax(), (-14, 12)),
                        (frame.index[-1], (8, -15))]:
        position = frame.index.get_loc(idx)
        value = frame.loc[idx, "mortgage_rate_pct"]
        axis.scatter(position, value, color=BLUE, s=30, zorder=3)
        axis.annotate(f"{idx.year} Q{idx.quarter}: {value:.2f}%", (position, value),
                      xytext=offset, textcoords="offset points", fontsize=10,
                      ha="right" if idx == frame.mortgage_rate_pct.idxmax() else "left")
    axis.set_xlim(-0.4, len(QUARTERS) + 4.2)
    axis.set_ylim(0, 8.7)
    axis.yaxis.set_major_locator(MultipleLocator(1))
    axis.legend(loc="upper left")
    save_plot(figure, "mortgage_rates.png")

    figure, axis = base_plot("Hours of gross earnings for one monthly payment",
                            "Financing costs kept the payment burden above 2019")
    axis.fill_between(x, frame.fixed_rate_hours, frame.payment_hours,
                      color="#B9CFDE", alpha=0.45)
    axis.plot(x, frame.payment_hours, color=BLUE, linewidth=2.4,
              label="At each quarter's mortgage rate")
    axis.plot(x, frame.fixed_rate_hours, color=ORANGE, linewidth=2.4,
              label=f"Same prices and earnings, rate held at {baseline:.2f}%")
    axis.axhline(frame.payment_hours.iloc[0], color="#808D99", linewidth=1, linestyle=":")
    axis.scatter([x[-1]] * 2, [latest.payment_hours, latest.fixed_rate_hours],
                 color=[BLUE, ORANGE], s=26, zorder=3)
    for value, color in [(latest.payment_hours, BLUE), (latest.fixed_rate_hours, ORANGE)]:
        axis.annotate(f"{value:.1f} h", (x[-1], value), xytext=(9, 0),
                      textcoords="offset points", color=color, fontsize=10, va="center")
    axis.set_xlim(-0.4, len(QUARTERS) + 2.3)
    axis.set_ylim(30, 79)
    axis.yaxis.set_major_locator(MultipleLocator(10))
    axis.legend(loc="upper left", fontsize=9.5)
    save_plot(figure, "payment_hours.png")


def write_outputs(frame, records):
    first, latest = frame.iloc[0], frame.iloc[-1]
    peak = frame.loc[frame.price_usd.idxmax()]
    low_rate = frame.loc[frame.mortgage_rate_pct.idxmin()]
    high_rate = frame.loc[frame.mortgage_rate_pct.idxmax()]
    context = {
        "price_start": f"${first.price_usd:,.0f}",
        "price_peak": f"${peak.price_usd:,.0f}",
        "price_latest": f"${latest.price_usd:,.0f}",
        "price_decline": f"{100 * (1 - latest.price_usd / peak.price_usd):.1f}",
        "peak_quarter": f"{peak.name.year} Q{peak.name.quarter}",
        "latest_quarter": f"{latest.name.year} Q{latest.name.quarter}",
        "real_price_latest": f"{latest.real_price_index:.1f}",
        "real_earnings_latest": f"{latest.real_earnings_index:.1f}",
        "rate_start": f"{first.mortgage_rate_pct:.2f}",
        "rate_low": f"{low_rate.mortgage_rate_pct:.2f}",
        "rate_low_quarter": f"{low_rate.name.year} Q{low_rate.name.quarter}",
        "rate_high": f"{high_rate.mortgage_rate_pct:.2f}",
        "rate_high_quarter": f"{high_rate.name.year} Q{high_rate.name.quarter}",
        "rate_latest": f"{latest.mortgage_rate_pct:.2f}",
        "payment_start": f"${first.payment_usd:,.0f}",
        "payment_latest": f"${latest.payment_usd:,.0f}",
        "hours_start": f"{first.payment_hours:.1f}",
        "hours_latest": f"{latest.payment_hours:.1f}",
        "hours_change": f"{100 * (latest.payment_hours / first.payment_hours - 1):.1f}",
        "hours_fixed_latest": f"{latest.fixed_rate_hours:.1f}",
        "hours_rate_gap": f"{latest.payment_hours - latest.fixed_rate_hours:.1f}",
        "retrieved_on": ", ".join(sorted({record["retrieved_on"] for record in records})),
    }
    frame.rename_axis("quarter").to_csv(ROOT / "results" / "housing_quarterly.csv",
                                        float_format="%.10f")
    summary = {"display_values": context, "latest_quarter": str(latest.name),
               "latest": {key: float(value) for key, value in latest.items()},
               "baseline": {key: float(value) for key, value in first.items()}}
    (ROOT / "results" / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    template = (ROOT / "code" / "article_template.txt").read_text(encoding="utf-8")
    article = re.sub(r"\{\{([a-z_]+)\}\}", lambda match: context[match.group(1)], template)
    if "{{" in article:
        raise ValueError("The article still contains an unfilled placeholder.")
    (ROOT / "blog4.qmd").write_text(article, encoding="utf-8")
    print(f"Generated three figures and the article from {len(frame)} complete quarters.")
    print(f"Latest payment: {context['payment_latest']}; hours: {context['hours_latest']}.")


def main():
    parser = argparse.ArgumentParser(description="Reproduce Blog 4 from saved FRED snapshots.")
    parser.add_argument("--refresh", action="store_true",
                        help="Download current FRED vintages before rebuilding all outputs.")
    args = parser.parse_args()
    if args.refresh:
        refresh_data()
    (ROOT / "results" / "figures").mkdir(parents=True, exist_ok=True)
    frame, records = load_quarterly()
    frame = transform(frame)
    make_figures(frame)
    write_outputs(frame, records)


if __name__ == "__main__":
    main()
