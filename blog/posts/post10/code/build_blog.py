"""Reproduce Blog 10 from the unmodified UCI files. Run from any directory.

Forecast origin: the end of the preceding calendar day. Each day's 24 hourly
forecasts use calendar information and observations through the previous day.
Models remain fixed throughout the final rolling-origin test period.
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from pathlib import Path
import hashlib
import json
import platform
import time
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.model_selection import ParameterGrid
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
SEED = 640010
TEST_START = pd.Timestamp("2012-10-01")
FOLDS = [
    ("2012-01-01", "2012-04-01"),
    ("2012-04-01", "2012-07-01"),
    ("2012-07-01", "2012-10-01"),
]
FEATURES = [
    "hour", "weekday", "month", "holiday", "workingday",
    "rentals_24h_ago", "rentals_168h_ago", "same_hour_mean_7days",
    "previous_day_total", "previous_7day_mean_total",
    "previous_day_temp", "previous_day_humidity", "previous_day_wind",
    "previous_day_weather", "days_since_start",
]
CATEGORICAL = ["hour", "weekday", "month", "previous_day_weather"]
GROUPS = {
    "Recent rentals": ["rentals_24h_ago", "rentals_168h_ago", "same_hour_mean_7days",
                       "previous_day_total", "previous_7day_mean_total"],
    "Hour of day": ["hour"],
    "Calendar": ["weekday", "month", "holiday", "workingday"],
    "Previous-day weather": ["previous_day_temp", "previous_day_humidity",
                             "previous_day_wind", "previous_day_weather"],
    "Time trend": ["days_since_start"],
}
GRIDS = {
    "Random forest": {
        "n_estimators": [200], "max_depth": [12, None],
        "min_samples_leaf": [2, 8], "max_features": [0.7, 1.0],
    },
    "Gradient boosting": {
        "max_iter": [250], "learning_rate": [0.05, 0.10],
        "max_leaf_nodes": [15, 31], "l2_regularization": [0.0, 5.0, 20.0],
    },
}
BASELINES = ["Calendar average", "Last week, same hour"]
COLORS = {"Calendar average": "#b5bdc8", "Last week, same hour": "#667b8e",
          "Random forest": "#28a28c", "Gradient boosting": "#d16a45"}


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def metrics(y, prediction):
    error = np.asarray(prediction) - np.asarray(y)
    return {"MAE": float(np.abs(error).mean()),
            "RMSE": float(np.sqrt(np.mean(error ** 2))),
            "Bias": float(error.mean())}


def load_features():
    h = pd.read_csv(DATA / "hour.csv", parse_dates=["dteday"])
    d = pd.read_csv(DATA / "day.csv", parse_dates=["dteday"])
    assert len(h) == 17379 and len(d) == 731
    assert not h.isna().any().any() and not d.isna().any().any()
    assert not h.duplicated(["dteday", "hr"]).any()
    assert not d.duplicated("dteday").any()
    assert (h["casual"] + h["registered"] == h["cnt"]).all()
    assert (d["casual"] + d["registered"] == d["cnt"]).all()
    h["timestamp"] = h["dteday"] + pd.to_timedelta(h["hr"], unit="h")
    h = h.sort_values("timestamp").set_index("timestamp")
    d = d.sort_values("dteday").set_index("dteday")
    hourly_daily = h.groupby("dteday")["cnt"].sum()
    assert (hourly_daily.reindex(d.index) == d["cnt"]).all()

    # A regular timestamp grid makes these calendar lags, even across missing
    # hours. Missing observations stay missing; they never become invented zeros.
    grid = pd.date_range(h.index.min(), h.index.max(), freq="h")
    counts = h["cnt"].reindex(grid)
    lag_matrix = pd.concat([counts.shift(24 * k) for k in range(1, 8)], axis=1)
    hourly_history = pd.DataFrame({
        "rentals_24h_ago": counts.shift(24),
        "rentals_168h_ago": counts.shift(168),
        "same_hour_mean_7days": lag_matrix.mean(axis=1).where(lag_matrix.count(axis=1) >= 4),
    })
    x = pd.DataFrame(index=h.index)
    x["date"] = h["dteday"]
    x["target"] = h["cnt"]
    for output, source in [("hour", "hr"), ("weekday", "weekday"),
                           ("month", "mnth"), ("holiday", "holiday"),
                           ("workingday", "workingday")]:
        x[output] = h[source]
    x = x.join(hourly_history)
    day_predictors = pd.DataFrame(index=d.index)
    day_predictors["previous_day_total"] = d["cnt"].shift(1)
    day_predictors["previous_7day_mean_total"] = d["cnt"].shift(1).rolling(7).mean()
    for output, source in [("previous_day_temp", "temp"),
                           ("previous_day_humidity", "hum"),
                           ("previous_day_wind", "windspeed"),
                           ("previous_day_weather", "weathersit")]:
        day_predictors[output] = d[source].shift(1)
    for column in day_predictors:
        x[column] = x["date"].map(day_predictors[column])
    x["days_since_start"] = (x["date"] - pd.Timestamp("2011-01-01")).dt.days
    missing_features = x[FEATURES].isna().any(axis=1)
    audit = {
        "raw_hourly_rows": len(h), "raw_daily_rows": len(d),
        "first_timestamp": str(h.index.min()), "last_timestamp": str(h.index.max()),
        "unrecorded_hours_in_calendar_grid": int(len(grid) - len(h)),
        "rows_excluded_for_unavailable_history": int(missing_features.sum()),
        "rows_retained": int((~missing_features).sum()),
        "excluded_by_year": x.loc[missing_features].groupby(x.loc[missing_features, "date"].dt.year).size().to_dict(),
        "target_components_excluded": ["casual", "registered"],
        "contemporaneous_weather_excluded": ["temp", "atemp", "hum", "windspeed", "weathersit"],
        "hourly_daily_count_totals_match": True,
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(DATA.iterdir()) if p.is_file()},
    }
    x = x.loc[~missing_features].copy()
    assert x.index.is_monotonic_increasing and not x[FEATURES].isna().any().any()
    return x, audit


def pipeline(name, parameters):
    preprocessing = ColumnTransformer([
        ("calendar", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL)
    ], remainder="passthrough")
    if name == "Random forest":
        model = RandomForestRegressor(random_state=SEED, n_jobs=2, **parameters)
    elif name == "Gradient boosting":
        # No random internal validation split: model size is tuned exclusively
        # using the expanding chronological validation folds defined above.
        model = HistGradientBoostingRegressor(random_state=SEED, early_stopping=False,
                                              **parameters)
    else:
        raise ValueError(name)
    return Pipeline([("preprocess", preprocessing), ("model", model)])


def baseline_predict(name, training, validation):
    if name == "Last week, same hour":
        return validation["rentals_168h_ago"].to_numpy()
    means = training.groupby(["hour", "workingday"])["target"].mean()
    keys = pd.MultiIndex.from_frame(validation[["hour", "workingday"]])
    prediction = means.reindex(keys).to_numpy()
    fallback = validation["hour"].map(training.groupby("hour")["target"].mean()).to_numpy()
    return np.where(np.isnan(prediction), fallback, prediction)


def tune(development):
    folds = []
    fold_manifest = []
    for start, end in FOLDS:
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        tr = development.loc[development["date"] < start]
        va = development.loc[(development["date"] >= start) & (development["date"] < end)]
        assert tr.index.max() < va.index.min() and va.index.max() < TEST_START
        folds.append((tr, va))
        fold_manifest.append({"train_start": str(tr.index.min()), "train_end": str(tr.index.max()),
                              "validation_start": str(va.index.min()), "validation_end": str(va.index.max()),
                              "n_train": len(tr), "n_validation": len(va)})
    rows, fold_rows, best = [], [], {}
    for name in BASELINES + list(GRIDS):
        choices = list(ParameterGrid(GRIDS[name])) if name in GRIDS else [{}]
        for candidate_id, parameters in enumerate(choices):
            all_y, all_p = [], []
            for k, (tr, va) in enumerate(folds, 1):
                if name in BASELINES:
                    p = baseline_predict(name, tr, va)
                else:
                    estimator = pipeline(name, parameters)
                    estimator.fit(tr[FEATURES], tr["target"])
                    p = estimator.predict(va[FEATURES])
                p = np.maximum(p, 0)
                all_y.extend(va["target"].to_numpy())
                all_p.extend(p)
                fold_rows.append({"model": name, "candidate": candidate_id, "fold": k,
                                  "n": len(va), **metrics(va["target"], p)})
            scores = metrics(all_y, all_p)
            rows.append({"model": name, "candidate": candidate_id,
                         "parameters": json.dumps(parameters, sort_keys=True),
                         "n_validation": len(all_y), **scores})
            print(f"CV {name}: {candidate_id + 1}/{len(choices)}, MAE={scores['MAE']:.3f}", flush=True)
        own = [r for r in rows if r["model"] == name]
        best[name] = min(own, key=lambda r: (r["MAE"], r["candidate"]))
    pd.DataFrame(rows).to_csv(RESULTS / "cv_candidates.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(RESULTS / "cv_folds.csv", index=False)
    write_json(RESULTS / "validation_windows.json", fold_manifest)
    # This file is written before test labels are evaluated.
    selected = min(best, key=lambda name: best[name]["MAE"])
    selection = {"selection_rule": "Lowest pooled chronological validation MAE across all four models",
                 "selected_model": selected,
                 "best_by_model": {name: {"parameters": json.loads(row["parameters"]),
                                           "validation_MAE": row["MAE"],
                                           "validation_RMSE": row["RMSE"]}
                                   for name, row in best.items()}}
    write_json(RESULTS / "model_selection.json", selection)
    return selection


def grouped_permutation(estimator, test, baseline_mae):
    """Post-selection description; never used to change models or predictors.

    A shared permutation preserves within-group dependence, e.g. between lags.
    Across-group dependence is broken, so the interpretation is model reliance,
    not a causal effect or a formal confidence interval.
    """
    rng = np.random.default_rng(SEED)
    records = []
    for group, columns in GROUPS.items():
        values = []
        for repeat in range(20):
            p = rng.permutation(len(test))
            shuffled = test[FEATURES].copy()
            shuffled.loc[:, columns] = test.iloc[p][columns].to_numpy()
            predicted = np.maximum(estimator.predict(shuffled), 0)
            values.append(metrics(test["target"], predicted)["MAE"] - baseline_mae)
        records.append({"group": group, "columns": ";".join(columns),
                        "increase_in_MAE": float(np.mean(values)),
                        "repeat_SD": float(np.std(values, ddof=1)),
                        "repeats": len(values)})
    importance = pd.DataFrame(records).sort_values("increase_in_MAE", ascending=False)
    importance.to_csv(RESULTS / "grouped_permutation_importance.csv", index=False)
    return importance


def make_figures(test, predictions, comparison, importance, selected):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "axes.labelcolor": "#243344",
                         "text.color": "#243344", "figure.facecolor": "white",
                         "axes.facecolor": "white", "svg.fonttype": "none"})
    def save(fig, name):
        fig.savefig(FIGURES / f"{name}.svg", bbox_inches="tight", facecolor="white")
        fig.savefig(FIGURES / f"{name}.png", dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(9.2, 4.0), layout="constrained")
    names = comparison["model"].tolist()
    values = comparison["test_MAE"].to_numpy()
    bars = ax.barh(names[::-1], values[::-1], color=[COLORS[n] for n in names[::-1]], height=.58)
    ax.bar_label(bars, labels=[f"{v:.1f}" for v in values[::-1]], padding=7, fontsize=11)
    ax.set_xlim(0, values.max() * 1.18)
    ax.set_xlabel("Mean absolute error (rentals per recorded hour; lower is better)")
    ax.set_title("Can a model beat last week's demand?", loc="left", pad=18)
    ax.grid(axis="x", color="#e6e9ec", zorder=0)
    ax.set_axisbelow(True)
    save(fig, "model_comparison")

    mobile_labels = {"Calendar average": "Calendar\naverage", "Last week, same hour": "Last week,\nsame hour",
                     "Random forest": "Random\nforest", "Gradient boosting": "Gradient\nboosting"}
    fig, ax = plt.subplots(figsize=(5.1, 4.3), layout="constrained")
    bars = ax.barh([mobile_labels[n] for n in names[::-1]], values[::-1],
                   color=[COLORS[n] for n in names[::-1]], height=.6)
    ax.bar_label(bars, labels=[f"{v:.1f}" for v in values[::-1]], padding=5)
    ax.set_xlim(0, values.max() * 1.28)
    ax.set_xlabel("Mean absolute error\n(rentals/hour; lower is better)")
    ax.set_title("Forecast error on later data", loc="left", fontsize=13, pad=15)
    ax.grid(axis="x", color="#e6e9ec")
    ax.set_axisbelow(True)
    save(fig, "model_comparison_mobile")

    # An ex ante fixed date range avoids choosing a flattering example after
    # inspecting predictions. It is the first full Monday-Sunday test week.
    start, end = pd.Timestamp("2012-10-01"), pd.Timestamp("2012-10-08")
    example = test.loc[(test["date"] >= start) & (test["date"] < end)].copy()
    fig, ax = plt.subplots(figsize=(10.0, 4.3), layout="constrained")
    ax.plot(example.index, example["target"], color="#23364c", lw=1.6, label="Observed rentals")
    ax.plot(example.index, predictions[selected].reindex(example.index),
            color=COLORS.get(selected, "#d16a45"), lw=1.5, label=selected)
    ax.plot(example.index, predictions["Last week, same hour"].reindex(example.index),
            color="#9ba7b1", lw=.9, ls="--", label="Last week, same hour", alpha=.9)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%b %d"))
    ax.set_ylabel("Rentals per recorded hour")
    ax.set_title("The first full test week: October 1-7, 2012", loc="left", pad=16)
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, 1.0), fontsize=9)
    ax.set_ylim(0, max(example["target"].max(), predictions[selected].reindex(example.index).max()) * 1.19)
    ax.grid(axis="y", color="#e6e9ec")
    save(fig, "first_test_week")

    fig, axes = plt.subplots(2, 1, figsize=(5.1, 6.5), sharey=True, layout="constrained")
    for ax, left, right in zip(axes, ["2012-10-01", "2012-10-04"], ["2012-10-04", "2012-10-08"]):
        mask = (example.index >= left) & (example.index < right)
        local = example.loc[mask]
        ax.plot(local.index, local["target"], color="#23364c", lw=1.4, label="Observed")
        ax.plot(local.index, predictions[selected].reindex(local.index),
                color=COLORS.get(selected, "#d16a45"), lw=1.3, label=selected)
        ax.plot(local.index, predictions["Last week, same hour"].reindex(local.index),
                color="#9ba7b1", lw=.9, ls="--", label="Last week")
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d"))
        ax.set_ylabel("Rentals/hour")
        ax.set_ylim(0, example["target"].max() * 1.2)
        ax.grid(axis="y", color="#e6e9ec")
    axes[0].set_title("First full test week\nOctober 1-7, 2012", loc="left", fontsize=13, pad=16)
    axes[0].legend(frameon=False, loc="upper left", fontsize=8.5)
    save(fig, "first_test_week_mobile")

    fig, ax = plt.subplots(figsize=(9.2, 3.8), layout="constrained")
    plot = importance.iloc[::-1]
    ax.barh(plot["group"], plot["increase_in_MAE"], color="#28a28c", height=.55)
    ax.errorbar(plot["increase_in_MAE"], np.arange(len(plot)), xerr=plot["repeat_SD"],
                fmt="none", ecolor="#243344", capsize=3, lw=1)
    ax.axvline(0, color="#aab4bf", lw=.8)
    ax.set_xlabel("Increase in test MAE after shuffling a group (rentals/hour)")
    ax.set_title("Which information does the selected model rely on?", loc="left", pad=17)
    ax.grid(axis="x", color="#e6e9ec")
    ax.set_axisbelow(True)
    save(fig, "feature_importance")

    fig, ax = plt.subplots(figsize=(5.1, 4.2), layout="constrained")
    mobile_groups = {"Recent rentals": "Recent\nrentals", "Hour of day": "Hour of day",
                     "Calendar": "Calendar", "Previous-day weather": "Previous-day\nweather", "Time trend": "Time trend"}
    ax.barh([mobile_groups[g] for g in plot["group"]], plot["increase_in_MAE"], color="#28a28c", height=.55)
    ax.errorbar(plot["increase_in_MAE"], np.arange(len(plot)), xerr=plot["repeat_SD"],
                fmt="none", ecolor="#243344", capsize=3, lw=1)
    ax.axvline(0, color="#aab4bf", lw=.8)
    ax.set_xlabel("Increase in MAE after shuffling\n(rentals/hour)")
    ax.set_title("Which inputs matter to the model?", loc="left", fontsize=12.5, pad=15)
    ax.grid(axis="x", color="#e6e9ec")
    ax.set_axisbelow(True)
    save(fig, "feature_importance_mobile")


def write_article(summary, comparison, importance):
    template = (ROOT / "code" / "article_template.txt").read_text(encoding="utf-8")
    from string import Template
    replacements = {k: str(v) for k, v in summary["article_values"].items()}
    saved_predictions = pd.read_csv(RESULTS / "test_predictions.csv", parse_dates=["timestamp"])
    sunday = saved_predictions.loc[saved_predictions["timestamp"].dt.normalize() == pd.Timestamp("2012-10-07")]
    replacements["sunday_observed"] = f"{sunday['observed'].mean():.0f}"
    replacements["sunday_predicted"] = f"{sunday[summary['selected_model']].mean():.0f}"
    rows = ["| Model | Validation MAE | Test MAE | Test RMSE |",
            "|:--|--:|--:|--:|"]
    for _, row in comparison.iterrows():
        rows.append(f"| {row['model']} | {row['validation_MAE']:.1f} | {row['test_MAE']:.1f} | {row['test_RMSE']:.1f} |")
    replacements["performance_table"] = "\n".join(rows)
    article = Template(template).substitute(replacements)
    (ROOT / "blog10.qmd").write_text(article, encoding="utf-8")


def main():
    tic = time.perf_counter()
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    frame, audit = load_features()
    development = frame.loc[frame["date"] < TEST_START].copy()
    test = frame.loc[frame["date"] >= TEST_START].copy()
    audit.update({"development_rows": len(development), "test_rows": len(test),
                  "development_first": str(development.index.min()),
                  "development_last": str(development.index.max()),
                  "test_first": str(test.index.min()), "test_last": str(test.index.max())})
    write_json(RESULTS / "data_audit.json", audit)
    frame.to_csv(RESULTS / "analysis_sample.csv", index_label="timestamp")
    print("Sample:", audit, flush=True)
    selection = tune(development)
    selected = selection["selected_model"]
    print("Selected using validation only:", selected, flush=True)
    fitted, predictions, rows = {}, {}, []
    for name in BASELINES + list(GRIDS):
        chosen = selection["best_by_model"][name]
        if name in BASELINES:
            p = baseline_predict(name, development, test)
        else:
            fitted[name] = pipeline(name, chosen["parameters"])
            fitted[name].fit(development[FEATURES], development["target"])
            p = fitted[name].predict(test[FEATURES])
        p = np.maximum(p, 0)
        predictions[name] = pd.Series(p, index=test.index)
        result = metrics(test["target"], p)
        rows.append({"model": name, "validation_MAE": chosen["validation_MAE"],
                     "validation_RMSE": chosen["validation_RMSE"],
                     **{"test_" + k: v for k, v in result.items()},
                     "n_test": len(test), "selected_before_test": name == selected})
    comparison = pd.DataFrame(rows)
    comparison.to_csv(RESULTS / "performance.csv", index=False)
    prediction_file = pd.DataFrame({"observed": test["target"], **predictions})
    prediction_file.to_csv(RESULTS / "test_predictions.csv", index_label="timestamp")
    print(comparison.to_string(index=False), flush=True)
    # Even in the unlikely event that a simple rule wins, interpret the best ML
    # algorithm and clearly distinguish it from the selected rule in the summary.
    best_ml = min(GRIDS, key=lambda n: selection["best_by_model"][n]["validation_MAE"])
    interpreted = selected if selected in fitted else best_ml
    interpreted_mae = float(comparison.set_index("model").loc[interpreted, "test_MAE"])
    importance = grouped_permutation(fitted[interpreted], test, interpreted_mae)
    per_hour = pd.DataFrame({"hour": test["hour"], "observed": test["target"],
                             "chosen": predictions[selected],
                             "weekly": predictions["Last week, same hour"]})
    per_hour["chosen_absolute_error"] = np.abs(per_hour["chosen"] - per_hour["observed"])
    per_hour["weekly_absolute_error"] = np.abs(per_hour["weekly"] - per_hour["observed"])
    per_hour.groupby("hour").agg(n=("observed", "size"),
                                 observed_mean=("observed", "mean"),
                                 selected_MAE=("chosen_absolute_error", "mean"),
                                 weekly_MAE=("weekly_absolute_error", "mean")).to_csv(RESULTS / "errors_by_hour.csv")
    peak = test["workingday"].eq(1) & test["hour"].isin([7, 8, 9, 16, 17, 18, 19])
    peak_mae = metrics(test.loc[peak, "target"], predictions[selected].loc[peak])["MAE"]
    peak_weekly = metrics(test.loc[peak, "target"], predictions["Last week, same hour"].loc[peak])["MAE"]
    selected_metrics = comparison.set_index("model").loc[selected]
    weekly_mae = float(comparison.set_index("model").loc["Last week, same hour", "test_MAE"])
    improvement = 100 * (1 - selected_metrics["test_MAE"] / weekly_mae)
    vals = {
        "selected": selected, "n_test": f"{len(test):,}", "n_development": f"{len(development):,}",
        "n_retained": f"{len(frame):,}", "n_excluded": f"{audit['rows_excluded_for_unavailable_history']:,}",
        "n_unrecorded": str(audit["unrecorded_hours_in_calendar_grid"]),
        "chosen_mae": f"{selected_metrics['test_MAE']:.1f}",
        "chosen_rmse": f"{selected_metrics['test_RMSE']:.1f}",
        "weekly_mae": f"{weekly_mae:.1f}", "improvement": f"{improvement:.0f}",
        "peak_mae": f"{peak_mae:.1f}", "peak_weekly_mae": f"{peak_weekly:.1f}",
        "top_group": str(importance.iloc[0]["group"]).lower(),
        "top_importance": f"{importance.iloc[0]['increase_in_MAE']:.1f}",
        "interpreted": interpreted,
    }
    summary = {"forecast_origin": "End of previous calendar day; all 24 next-day hourly forecasts",
               "test_design": "Fixed models; history updated daily using only already observed rentals/weather",
               "test_start": "2012-10-01", "test_end": "2012-12-31",
               "selected_model": selected, "interpreted_model": interpreted,
               "MAE_reduction_vs_weekly_percent": float(improvement),
               "workingday_peak_hours": [7, 8, 9, 16, 17, 18, 19],
               "peak_hour_MAE": float(peak_mae), "peak_hour_weekly_MAE": float(peak_weekly),
               "peak_hour_n": int(peak.sum()), "article_values": vals}
    write_json(RESULTS / "summary.json", summary)
    environment = {"python": platform.python_version(), "numpy": np.__version__,
                   "pandas": pd.__version__, "scikit-learn": sklearn.__version__,
                   "matplotlib": matplotlib.__version__, "seed": SEED}
    write_json(RESULTS / "environment.json", environment)
    make_figures(test, predictions, comparison, importance, selected)
    if (ROOT / "code" / "article_template.txt").exists():
        write_article(summary, comparison, importance)
    print("Importance:\n", importance.to_string(index=False), flush=True)
    print("Article values:", vals, flush=True)
    print(f"Finished in {time.perf_counter() - tic:.1f} seconds", flush=True)


def refresh_publication():
    """Rebuild figures and prose from saved results, without fitting models."""
    frame = pd.read_csv(RESULTS / "analysis_sample.csv", parse_dates=["timestamp", "date"]).set_index("timestamp")
    test = frame.loc[frame["date"] >= TEST_START]
    predictions = pd.read_csv(RESULTS / "test_predictions.csv", parse_dates=["timestamp"]).set_index("timestamp")
    comparison = pd.read_csv(RESULTS / "performance.csv")
    importance = pd.read_csv(RESULTS / "grouped_permutation_importance.csv")
    summary = json.loads((RESULTS / "summary.json").read_text())
    make_figures(test, predictions, comparison, importance, summary["selected_model"])
    write_article(summary, comparison, importance)
    print("Rebuilt publication from verified saved analysis outputs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-only", action="store_true",
                        help="Rebuild article and figures from saved results; skip model fitting.")
    args = parser.parse_args()
    if args.publication_only:
        refresh_publication()
    else:
        main()
