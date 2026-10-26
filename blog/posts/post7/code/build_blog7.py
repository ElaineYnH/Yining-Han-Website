#!/usr/bin/env python3
"""Build Blog 7 from the original FRED download, using only Python's standard library.

Run from the post7 folder: python code/build_blog7.py
The script never downloads, invents, interpolates, or forward-fills observations.
Plotly.js is vendored locally so the generated interactive HTML also works offline.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import math
import re
import shutil
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
START = "2019-01-01"
BASE = "2020-01-01"
COMPARISON = "2022-06-01"
PLOTLY_VERSION = "4.1.1"
SERIES = [
    {"id": "CPIAUCSL", "label": "All items", "color": "#2458a6", "dash": "solid"},
    {"id": "CUSR0000SAF11", "label": "Groceries", "color": "#bd5700", "dash": "dash"},
    {"id": "CUSR0000SEHA", "label": "Rent", "color": "#087b67", "dash": "dot"},
    {"id": "CUSR0000SETB01", "label": "Gasoline", "color": "#8145a5", "dash": "dashdot"},
]
IDS = [s["id"] for s in SERIES]


def month_label(value: str, short: bool = False) -> str:
    d = date.fromisoformat(value)
    names = calendar.month_abbr if short else calendar.month_name
    return f"{names[d.month]} {d.year}"


def monthly_grid(first: str, last: str) -> list[str]:
    y, m = map(int, first[:7].split("-"))
    result = []
    while f"{y:04d}-{m:02d}-01" <= last:
        result.append(f"{y:04d}-{m:02d}-01")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return result


def percent_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return 100 * (current / previous - 1)


def read_snapshot(path: Path):
    raw = path.read_bytes()
    records = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not records or set(records[0]) != {"observation_date", *IDS}:
        raise ValueError("Expected observation_date and the four documented FRED series IDs.")
    observations = {}
    for record in records:
        stamp = record["observation_date"]
        parsed = date.fromisoformat(stamp)
        if parsed.day != 1 or stamp in observations:
            raise ValueError(f"Invalid or duplicate monthly date: {stamp}")
        values = {}
        for sid in IDS:
            cell = record[sid].strip()
            value = None if cell in ("", ".", "NA", "NaN") else float(cell)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"Invalid CPI value at {stamp}, {sid}: {cell!r}")
            values[sid] = value
        observations[stamp] = values
    common = [d for d, values in observations.items()
              if d >= BASE and all(values[sid] is not None for sid in IDS)]
    if not common:
        raise ValueError("No common endpoint is available for the four series.")
    end = max(common)
    months = monthly_grid(START, end)
    window = {d: observations.get(d, {sid: None for sid in IDS}) for d in months}
    for baseline in (BASE, COMPARISON):
        if baseline not in window or any(window[baseline][sid] is None for sid in IDS):
            raise ValueError(f"A required comparison month is missing: {baseline}")
    return raw, records, months, window, end


def write_csv(path: Path, records: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def write_json(path: Path, content) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")


def fill_template(path: Path, replacements: dict[str, str]) -> str:
    original = path.read_text(encoding="utf-8")
    def replace(match):
        key = match.group(1)
        if key not in replacements:
            raise KeyError(f"Unfilled template field: {key}")
        return replacements[key]
    return re.sub(r"\{\{([A-Z0-9_]+)\}\}", replace, original)


def make_cover(months, window, end):
    """An exact, data-derived SVG thumbnail for the website's article listing."""
    shown = [d for d in months if d >= BASE]
    values = [percent_change(window[d][s["id"]], window[BASE][s["id"]])
              for d in shown for s in SERIES]
    finite = [v for v in values if v is not None]
    lower = 20 * math.floor(min(0, min(finite)) / 20)
    upper = 20 * math.ceil(max(finite) / 20)
    left, right, top, bottom = 78, 855, 92, 340
    def x(i): return left + (right - left) * i / (len(shown) - 1)
    def y(v): return bottom - (bottom - top) * (v - lower) / (upper - lower)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="920" height="460" viewBox="0 0 920 460" role="img" aria-labelledby="title desc">',
        '<title id="title">Prices since January 2020</title>',
        f'<desc id="desc">Cumulative changes in four BLS price indexes through {escape(month_label(end))}. Missing observations remain gaps.</desc>',
        '<rect width="920" height="460" fill="#ffffff"/>',
        '<g font-family="Arial, sans-serif" fill="#182536">',
        '<text x="78" y="36" font-size="26" font-weight="700">Prices since January 2020</text>',
        f'<text x="78" y="62" font-size="15" fill="#526074">U.S. city average, seasonally adjusted. Through {escape(month_label(end))}.</text>',
    ]
    for tick in range(lower, upper + 1, 20):
        parts.append(f'<line x1="{left}" x2="{right}" y1="{y(tick):.2f}" y2="{y(tick):.2f}" stroke="#dde3e9"/>')
        parts.append(f'<text x="62" y="{y(tick)+5:.2f}" text-anchor="end" font-size="14">{tick}%</text>')
    for yr in (2020, 2022, 2024, 2026):
        stamp = f"{yr}-01-01"
        if stamp in shown:
            xx = x(shown.index(stamp))
            parts.append(f'<text x="{xx:.2f}" y="365" text-anchor="middle" font-size="14">{yr}</text>')
    for s in SERIES:
        commands = []
        previous_missing = True
        for i, d in enumerate(shown):
            value = percent_change(window[d][s["id"]], window[BASE][s["id"]])
            if value is None:
                previous_missing = True
                continue
            commands.append(f'{"M" if previous_missing else "L"}{x(i):.2f},{y(value):.2f}')
            previous_missing = False
        dash = {"solid": "", "dash": ' stroke-dasharray="8 4"',
                "dot": ' stroke-dasharray="2 4"', "dashdot": ' stroke-dasharray="8 4 2 4"'}[s["dash"]]
        parts.append(f'<path d="{" ".join(commands)}" fill="none" stroke="{s["color"]}" stroke-width="3"{dash}/>')
    for i, s in enumerate(SERIES):
        xx = 78 + i * 199
        value = percent_change(window[end][s["id"]], window[BASE][s["id"]])
        parts.append(f'<text x="{xx}" y="408" font-size="16" fill="{s["color"]}" font-weight="700">{escape(s["label"])} {value:+.1f}%</text>')
    parts.append('<text x="78" y="441" font-size="12" fill="#526074">Source: U.S. Bureau of Labor Statistics via FRED. Author calculations.</text></g></svg>')
    (ROOT / "results/cover.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")


def build(input_path: Path, post_date: str):
    date.fromisoformat(post_date)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "results").mkdir(exist_ok=True)
    source = ROOT / "data/fredgraph.csv"
    if input_path.resolve() != source.resolve():
        shutil.copyfile(input_path, source)
    raw, original, months, window, end = read_snapshot(source)
    if end > post_date:
        raise ValueError("The data endpoint is later than the post date. Check the supplied snapshot.")
    annual = {}
    analysis_rows = []
    for d in months:
        previous_year = f"{int(d[:4]) - 1:04d}{d[4:]}"
        annual[d] = {}
        for s in SERIES:
            sid = s["id"]
            lag = window.get(previous_year, {}).get(sid)
            yoy = percent_change(window[d][sid], lag)
            annual[d][sid] = yoy
            analysis_rows.append({
                "date": d, "series_id": sid, "category": s["label"],
                "price_index": window[d][sid],
                "change_since_jan2020_pct": percent_change(window[d][sid], window[BASE][sid]) if d >= BASE else None,
                "change_since_jun2022_pct": percent_change(window[d][sid], window[COMPARISON][sid]) if d >= COMPARISON else None,
                "annual_inflation_pct": yoy,
            })
    summary = []
    for s in SERIES:
        sid = s["id"]
        peak_value, peak_month = max((annual[d][sid], d) for d in months
                                     if d >= BASE and annual[d][sid] is not None)
        summary.append({
            "series_id": sid, "category": s["label"], "endpoint": end,
            "latest_price_index": window[end][sid],
            "january2020_price_index": window[BASE][sid],
            "june2022_price_index": window[COMPARISON][sid],
            "change_since_jan2020_pct": percent_change(window[end][sid], window[BASE][sid]),
            "change_since_jun2022_pct": percent_change(window[end][sid], window[COMPARISON][sid]),
            "annual_inflation_pct": annual[end][sid],
            "peak_annual_inflation_pct": peak_value, "peak_annual_inflation_month": peak_month,
        })
    write_csv(ROOT / "results/analysis.csv", analysis_rows, list(analysis_rows[0]))
    write_csv(ROOT / "results/summary.csv", summary, list(summary[0]))
    write_json(ROOT / "results/summary.json", {"endpoint": end, "series": summary})
    quality = {
        "input_filename": "data/fredgraph.csv", "input_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_rows": len(original), "analysis_start": START, "analysis_end": end,
        "calendar_months_in_analysis": len(months),
        "complete_months_in_analysis": sum(all(v is not None for v in window[d].values()) for d in months),
        "missing_by_series": {sid: [d for d in months if window[d][sid] is None] for sid in IDS},
        "missing_value_policy": "No imputation or forward-fill. Calendar dates are retained. Rates require both observed endpoints.",
        "units": "Original index: 1982-1984=100. Computed changes: percent.",
        "frequency": "Monthly", "adjustment": "Seasonally adjusted",
        "sources": {sid: f"https://fred.stlouisfed.org/series/{sid}" for sid in IDS},
        "snapshot_provenance": "Original FRED CSV downloaded and uploaded by the author; preserved byte for byte.",
        "post_date": post_date, "plotly_version": PLOTLY_VERSION,
    }
    write_json(ROOT / "results/data_quality.json", quality)
    payload = {
        "dates": [d for d in months if d >= BASE], "endpoint": end,
        "endpointLabel": month_label(end),
        "baseOptions": [d for d in months if BASE <= d < end and all(window[d][sid] is not None for sid in IDS)],
        "series": [{**s,
                    "prices": [window[d][s["id"]] for d in months if d >= BASE],
                    "annual": [annual[d][s["id"]] for d in months if d >= BASE]}
                   for s in SERIES],
    }
    library = (ROOT / f"assets/plotly-{PLOTLY_VERSION}.min.js").read_text(encoding="utf-8")
    if f"plotly.js v{PLOTLY_VERSION}" not in library[:300]:
        raise ValueError("Unexpected Plotly.js asset. Use the documented vendored version.")
    quality["plotly_asset_sha256"] = hashlib.sha256(library.encode()).hexdigest()
    write_json(ROOT / "results/data_quality.json", quality)
    safe_library = re.sub(r"</script", r"<\/script", library, flags=re.IGNORECASE)
    html = fill_template(ROOT / "code/explorer_template.html", {
        "PLOTLY_JS": safe_library,
        "DATA_JSON": json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c"),
    })
    (ROOT / "results/price_explorer.html").write_text(html, encoding="utf-8")
    table_lines = [
        "| Category | Since Jan 2020 | Since Jun 2022 | Annual inflation |",
        "|:--|--:|--:|--:|",
    ]
    for row in summary:
        table_lines.append(f'| {row["category"]} | {row["change_since_jan2020_pct"]:+.1f}% | {row["change_since_jun2022_pct"]:+.1f}% | {row["annual_inflation_pct"]:+.1f}% |')
    names = ["ALL", "FOOD", "RENT", "GAS"]
    fields = {"2020": "change_since_jan2020_pct", "2022": "change_since_jun2022_pct", "YOY": "annual_inflation_pct"}
    replacements = {"POST_DATE": post_date, "END_LONG": month_label(end),
                    "END_SHORT": month_label(end, short=True), "SNAPSHOT_TABLE": "\n".join(table_lines),
                    "ALL_PEAK": f'{summary[0]["peak_annual_inflation_pct"]:.1f}',
                    "ALL_PEAK_DATE": month_label(summary[0]["peak_annual_inflation_month"])}
    for name, row in zip(names, summary):
        for suffix, field in fields.items():
            replacements[f"{name}_{suffix}"] = f"{row[field]:.1f}"
    replacements["GAS_2022_ABS"] = f'{abs(summary[3]["change_since_jun2022_pct"]):.1f}'
    article = fill_template(ROOT / "code/article_template.txt", replacements)
    (ROOT / "blog7.qmd").write_text(article, encoding="utf-8")
    make_cover(months, window, end)
    print(json.dumps({"endpoint": end, "analysis_months": len(months),
                      "missing_by_series": quality["missing_by_series"],
                      "generated": ["blog7.qmd", "results/price_explorer.html", "results/cover.svg",
                                    "results/analysis.csv", "results/summary.csv", "results/summary.json", "results/data_quality.json"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/fredgraph.csv")
    parser.add_argument("--post-date", default="2026-10-27", help="Explicit publication date; never inferred from a deadline.")
    args = parser.parse_args()
    build(args.input, args.post_date)
