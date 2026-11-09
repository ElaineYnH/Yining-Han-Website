"""Reproduce Blog 9 from the uploaded Yahoo Finance snapshot, without network access.

Run from post9: python code/build_blog9.py
The forecast target and original features follow original_class_model.R literally.
Common label purging and a shared, daily marked-to-market backtest repair evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
DATA, RESULTS = ROOT / "data", ROOT / "results"
ORIGINAL_FEATURES = [
    "open", "high", "low", "close", "volume", "adjusted", "return", "spy_ret",
    "mom_1m", "mom_3m", "mom_6m", "vol_1m", "ret_5d", "excess_ret",
]
IMPROVED_FEATURES = [
    "return", "spy_ret", "trend_21", "trend_63", "trend_126", "ret5_correct",
    "vol_1m", "relative_21", "relative_63", "relative_126", "vol_ratio",
    "log_volume_ratio", "distance_ma63", "day_range", "intraday_return",
    "spy_trend21", "spy_vol22", "rank_trend21", "rank_trend63",
    "rank_trend126", "rank_vol22",
]
LABELS = {"original": "Class model", "improved": "Revised model",
          "mean": "Training mean", "zero": "Zero return",
          "equal_weight": "Equal-weight 95", "spy": "SPY buy-and-hold"}
COLORS = {"original": "#b75d46", "improved": "#167d8d", "mean": "#89929c",
          "equal_weight": "#9c7a37", "spy": "#33445d"}


def read_inputs():
    manifest = json.loads((DATA / "manifest.json").read_text())
    design = json.loads((DATA / "analysis_design.json").read_text())
    for name, meta in manifest["files"].items():
        if hashlib.sha256((DATA / name).read_bytes()).hexdigest() != meta["sha256"]:
            raise ValueError(f"Snapshot hash mismatch: {name}")
    if hashlib.sha256((DATA / "prices.csv").read_bytes()).hexdigest() != design["data_sha256"]:
        raise ValueError("Analysis design does not match the input snapshot")
    raw = pd.read_csv(DATA / "prices.csv", parse_dates=["date"])
    equities = manifest["equities_from_instructor"]
    expected = set(equities + ["SPY"])
    assert set(raw.symbol) == expected and len(expected) == 96
    assert not raw.duplicated(["symbol", "date"]).any()
    assert not raw.isna().any().any()
    assert (raw[["open", "high", "low", "close", "adjusted"]] > 0).all().all()
    panel = raw.pivot(index="date", columns="symbol", values="adjusted").sort_index()
    assert not panel.isna().any().any()
    return raw, panel, equities, design


def make_features(raw, panel, equities):
    spy = panel["SPY"]
    market = pd.DataFrame({
        "spy_ret": spy.pct_change(fill_method=None),
        "spy_trend21": spy.shift(1) / spy.shift(21) - 1,
        "spy_trend63": spy.shift(1) / spy.shift(63) - 1,
        "spy_trend126": spy.shift(1) / spy.shift(126) - 1,
        "spy_vol22": spy.pct_change(fill_method=None).shift(1).rolling(22).std(ddof=1),
    })
    frames = []
    for symbol in equities:
        s = raw.loc[raw.symbol.eq(symbol)].sort_values("date").set_index("date").copy()
        p = s.adjusted
        s["return"] = p.pct_change(fill_method=None)
        s = s.join(market)
        # Literal classroom ratios are inverse momentum signals; retain them here.
        for lag, name in [(21, "mom_1m"), (63, "mom_3m"), (126, "mom_6m")]:
            s[name] = p.shift(lag) / p.shift(1) - 1
        s["ret_5d"] = p.shift(5) / p.shift(1) - 1
        # R slider .before=21 includes 22 lagged returns, with sample SD.
        s["vol_1m"] = s["return"].shift(1).rolling(22).std(ddof=1)
        s["excess_ret"] = s["return"] - s.spy_ret
        # Signal after t's close; classroom label enters at t+1 close, exits t+20.
        s["target"] = p.shift(-20) / p.shift(-1) - 1
        dates = pd.Series(s.index, index=s.index)
        s["label_entry"] = dates.shift(-1)
        s["label_end"] = dates.shift(-20)
        for lag in [21, 63, 126]:
            s[f"trend_{lag}"] = p.shift(1) / p.shift(lag) - 1
            s[f"relative_{lag}"] = s[f"trend_{lag}"] - s[f"spy_trend{lag}"]
        s["ret5_correct"] = p / p.shift(5) - 1
        s["vol_ratio"] = s["return"].shift(1).rolling(5).std(ddof=1) / s.vol_1m
        s["log_volume_ratio"] = np.log(s.volume / s.volume.shift(1).rolling(22).mean())
        s["distance_ma63"] = p / p.rolling(63).mean() - 1
        s["day_range"] = (s.high - s.low) / s.close
        s["intraday_return"] = s.close / s.open - 1
        frames.append(s.reset_index())
    df = pd.concat(frames, ignore_index=True).sort_values(["date", "symbol"]).reset_index(drop=True)
    # Same-date ranks use only information observed by that date's close.
    for col, name in [("trend_21", "rank_trend21"), ("trend_63", "rank_trend63"),
                      ("trend_126", "rank_trend126"), ("vol_1m", "rank_vol22")]:
        df[name] = df.groupby("date")[col].rank(method="average", pct=True)
    df = df.replace([np.inf, -np.inf], np.nan)
    return df.dropna(subset=list(set(ORIGINAL_FEATURES + IMPROVED_FEATURES)) + ["target", "label_end"]).reset_index(drop=True)


def estimator(parameters):
    return XGBRegressor(
        objective="reg:squarederror", tree_method="hist", n_jobs=1,
        random_state=123, verbosity=0, **parameters,
    )


def fit_models(df, design):
    test_start = pd.Timestamp(design["test_start"])
    train = df.loc[(df.date < test_start) & (df.label_end < test_start)].copy()
    test = df.loc[df.date >= test_start].copy()
    assert train.label_end.max() < test.date.min()
    audit = []
    cv_rows = []
    for candidate, grid_params in enumerate(design["improved_grid"]):
        params = design["improved_common_parameters"] | grid_params
        for fold, (start, end) in enumerate(design["cv_windows"]):
            start, end = pd.Timestamp(start), pd.Timestamp(end)
            tr = df.loc[(df.date < start) & (df.label_end < start)]
            va = df.loc[(df.date >= start) & (df.date < end) & (df.label_end < end)]
            assert len(tr) and len(va)
            assert tr.label_end.max() < va.date.min()
            assert va.label_end.max() < test_start
            if candidate == 0:
                audit.append({"split": f"validation_{fold+1}", "train_rows": len(tr),
                              "train_first": tr.date.min(), "train_last": tr.date.max(),
                              "train_last_label_end": tr.label_end.max(),
                              "validation_first": va.date.min(), "validation_last": va.date.max(),
                              "validation_last_label_end": va.label_end.max(), "validation_rows": len(va)})
            model = estimator(params).fit(tr[IMPROVED_FEATURES], tr.target)
            residual = va.target.to_numpy() - model.predict(va[IMPROVED_FEATURES])
            cv_rows.append({"candidate": candidate, "fold": fold+1, **grid_params,
                            "rows": len(va), "squared_error_sum": float(residual @ residual),
                            "mse": float(np.mean(residual**2))})
        print(f"Validated candidate {candidate+1}/{len(design['improved_grid'])}", flush=True)
    cv = pd.DataFrame(cv_rows)
    totals = cv.groupby("candidate").agg(squared_error_sum=("squared_error_sum", "sum"), rows=("rows", "sum"))
    totals["pooled_mse"] = totals.squared_error_sum / totals.rows
    selected = int(totals.pooled_mse.idxmin())
    best = design["improved_common_parameters"] | design["improved_grid"][selected]
    cv.to_csv(RESULTS / "validation_folds.csv", index=False)
    totals.reset_index().to_csv(RESULTS / "validation_candidates.csv", index=False)
    audit.append({"split": "final_test", "train_rows": len(train),
                  "train_first": train.date.min(), "train_last": train.date.max(),
                  "train_last_label_end": train.label_end.max(),
                  "validation_first": test.date.min(), "validation_last": test.date.max(),
                  "validation_last_label_end": test.label_end.max(), "validation_rows": len(test)})
    pd.DataFrame(audit).to_csv(RESULTS / "split_audit.csv", index=False)
    original = estimator(design["original_parameters"]).fit(train[ORIGINAL_FEATURES], train.target)
    improved = estimator(best).fit(train[IMPROVED_FEATURES], train.target)
    predictions = test[["date", "symbol", "label_entry", "label_end", "target"]].copy()
    # Store float32 engine outputs as float64 columns for lossless CSV round trips.
    predictions["original"] = original.predict(test[ORIGINAL_FEATURES]).astype(np.float64)
    predictions["improved"] = improved.predict(test[IMPROVED_FEATURES]).astype(np.float64)
    predictions["mean"] = float(train.target.mean())
    predictions["zero"] = 0.0
    predictions.to_csv(RESULTS / "test_predictions.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    original.get_booster().save_model(RESULTS / "models/original.ubj")
    improved.get_booster().save_model(RESULTS / "models/improved.ubj")
    print("Selected parameters", best, flush=True)
    return predictions, train, best, selected, audit


def forecast_metrics(pred):
    denominator = float(np.mean((pred.target - pred["mean"])**2))
    rows = []
    by_date = pd.DataFrame(index=pd.DatetimeIndex(sorted(pred.date.unique()), name="date"))
    for name in ["mean", "original", "improved", "zero"]:
        err = pred.target - pred[name]
        mse = float(np.mean(err**2))
        correlations = []
        for _, day in pred.groupby("date", sort=True):
            if day[name].nunique() > 1:
                correlations.append(float(day[name].rank().corr(day.target.rank())))
        rows.append({"model": name, "label": LABELS[name], "n": len(pred), "mse": mse,
                     "rmse_percentage_points": 100*np.sqrt(mse),
                     "mae_percentage_points": 100*float(np.mean(np.abs(err))),
                     "oos_r2_vs_training_mean": 1-mse/denominator,
                     "direction_accuracy": float(((pred[name] > 0) == (pred.target > 0)).mean()),
                     "mean_daily_rank_ic": float(np.mean(correlations)) if correlations else None})
        by_date[name] = (err**2).groupby(pred.date).mean()
    metrics = pd.DataFrame(rows)
    metrics.to_csv(RESULTS / "forecast_metrics.csv", index=False)
    by_date.to_csv(RESULTS / "daily_forecast_losses.csv")
    # Resample dates in blocks, keeping correlated stock forecasts together.
    delta = (by_date.improved - by_date.original).to_numpy()
    block, reps = 20, 2000
    rng = np.random.default_rng(640009)
    draws = []
    for _ in range(reps):
        starts = rng.integers(0, len(delta)-block+1, size=int(np.ceil(len(delta)/block)))
        indices = (starts[:, None] + np.arange(block)).ravel()[:len(delta)]
        draws.append(float(delta[indices].mean()))
    uncertainty = {"improved_minus_original_mse": float(delta.mean()),
                   "block_dates": block, "replications": reps,
                   "descriptive_95_interval": np.quantile(draws, [.025, .975]).tolist()}
    (RESULTS / "forecast_uncertainty.json").write_text(json.dumps(uncertainty, indent=2)+"\n")
    return metrics, uncertainty


def trade_schedule(pred, panel):
    dates = panel.index
    firsts = pd.Series(dates, index=dates).groupby(dates.to_period("M")).first()
    rows = []
    pred_dates = set(pred.date)
    for i in range(len(firsts)-1):
        signal, following = firsts.iloc[i], firsts.iloc[i+1]
        if signal not in pred_dates:
            continue
        entry = dates[dates.get_loc(signal)+1]
        exit_ = dates[dates.get_loc(following)+1]
        rows.append({"signal_date": signal, "entry_date": entry, "exit_date": exit_})
    schedule = pd.DataFrame(rows)
    assert len(schedule)
    assert (schedule.signal_date < schedule.entry_date).all()
    assert (schedule.entry_date < schedule.exit_date).all()
    assert all(schedule.exit_date.iloc[:-1].to_numpy() == schedule.entry_date.iloc[1:].to_numpy())
    schedule.to_csv(RESULTS / "holding_periods.csv", index=False)
    return schedule


def target_weights(pred, schedule, equities):
    universe = equities + ["SPY"]
    weights, records = {}, []
    for name in ["original", "improved", "equal_weight", "spy"]:
        mapping = {}
        for signal, entry, _ in schedule.itertuples(index=False, name=None):
            w = pd.Series(0., index=universe)
            if name in ["original", "improved"]:
                day = pred.loc[pred.date.eq(signal)].sort_values([name, "symbol"], ascending=[False, True]).head(10)
                assert len(day) == 10
                clipped = day[name].clip(lower=0).to_numpy(dtype=np.float64)
                allocation = clipped / clipped.sum() if clipped.sum() > 0 else np.full(10, .1)
                w.loc[day.symbol] = allocation
            elif name == "equal_weight":
                w.loc[equities] = 1/len(equities)
            else:
                w.loc["SPY"] = 1.
            w = w / w.sum()
            assert abs(w.sum()-1.) < 1e-12 and (w >= 0).all()
            mapping[entry] = w.to_numpy()
            for symbol in w.index[w > 0]:
                records.append({"strategy": name, "signal_date": signal, "entry_date": entry,
                                "symbol": symbol, "weight": w[symbol]})
        weights[name] = mapping
    pd.DataFrame(records).to_csv(RESULTS / "portfolio_weights.csv", index=False)
    return weights, universe


def execute_trade(positions, cash, target, cost_rate):
    """Exact self-financing dollar positions with proportional one-way costs."""
    before = float(positions.sum()+cash)
    if target.sum() == 0:  # final liquidation
        cost = cost_rate * float(np.abs(positions).sum())
        return np.zeros_like(positions), before-cost, cost
    lo, hi = 0., before
    for _ in range(60):
        after = (lo+hi)/2
        cost = cost_rate*float(np.abs(target*after-positions).sum())
        if after+cost > before:
            hi = after
        else:
            lo = after
    after = (lo+hi)/2
    result = target*after
    cost = cost_rate*float(np.abs(result-positions).sum())
    assert abs(float(result.sum()) + cost - before) < 1e-7
    return result, 0., cost


def backtest(panel, schedule, weights, universe, cost_bps):
    start, end = schedule.entry_date.iloc[0], schedule.exit_date.iloc[-1]
    prices = panel[universe]
    daily = prices.pct_change(fill_method=None)
    dates = prices.loc[start:end].index
    frames, stats = [], []
    for name, targets in weights.items():
        position = np.zeros(len(universe))
        cash, previous_wealth = 100., 100.
        observations, turnover = [], []
        for i, date in enumerate(dates):
            if i:
                position *= 1+daily.loc[date].to_numpy()
            trade_cost = 0.
            if date == end:
                position, cash, trade_cost = execute_trade(position, cash, np.zeros_like(position), cost_bps/10000)
            elif date in targets:
                # SPY is buy-and-hold; resetting a one-asset weight is a no-op.
                position, cash, trade_cost = execute_trade(position, cash, targets[date], cost_bps/10000)
            wealth = float(position.sum()+cash)
            r = wealth/previous_wealth-1
            observations.append({"date": date, "strategy": name, "cost_bps": cost_bps,
                                 "wealth_per_100": wealth, "daily_return": r, "cost_dollars": trade_cost})
            previous_wealth = wealth
        frame = pd.DataFrame(observations)
        values = frame.wealth_per_100.to_numpy()
        running_high = np.maximum.accumulate(np.r_[100., values])[1:]
        elapsed_years = (end-start).days/365.25
        returns = frame.daily_return
        stats.append({"strategy": name, "label": LABELS[name], "cost_bps": cost_bps,
                      "start": start.date().isoformat(), "end": end.date().isoformat(),
                      "holding_periods": len(schedule), "terminal_per_100": values[-1],
                      "total_return": values[-1]/100-1,
                      "cagr": (values[-1]/100)**(1/elapsed_years)-1,
                      "daily_sharpe_rf_zero": float(returns.mean()/returns.std(ddof=1)*np.sqrt(252)),
                      "max_drawdown": float(np.min(values/running_high-1)),
                      "total_cost_dollars": float(frame.cost_dollars.sum())})
        frames.append(frame)
    return pd.concat(frames, ignore_index=True), pd.DataFrame(stats)


def figures(metrics, wealth):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": "#33445d", "text.color": "#243746",
                         "axes.edgecolor": "#bfc9cc", "savefig.facecolor": "white"})
    for mobile in [False, True]:
        suffix = "_mobile" if mobile else ""
        order = ["mean", "original", "improved"]
        m = metrics.set_index("model").loc[order]
        fig, ax = plt.subplots(figsize=(4.4, 3.8) if mobile else (8.5, 3.5), layout="constrained")
        y = np.arange(3)
        ax.barh(y, m.rmse_percentage_points, color=[COLORS[s] for s in order], height=.56)
        ax.set_yticks(y, [LABELS[s] for s in order]); ax.invert_yaxis()
        ax.set_xlabel("Forecast RMSE (percentage points)")
        maximum = float(m.rmse_percentage_points.max())
        ax.set_xlim(0, maximum*1.2)
        for i, value in enumerate(m.rmse_percentage_points):
            ax.text(value+maximum*.02, i, f"{value:.2f}", va="center", fontsize=11)
        ax.set_title("Does revising the model reduce forecast error?", loc="left", fontsize=12 if mobile else 14, pad=15, wrap=True)
        ax.set_axisbelow(True); ax.xaxis.grid(True, color="#e6ebed"); ax.spines["left"].set_visible(False)
        fig.savefig(RESULTS / f"forecast_error{suffix}.png", dpi=180); plt.close(fig)
        fig, ax = plt.subplots(figsize=(4.4, 4.7) if mobile else (8.5, 4.5), layout="constrained")
        for name in ["original", "improved", "equal_weight", "spy"]:
            day = wealth.loc[(wealth.cost_bps == 10) & wealth.strategy.eq(name)]
            ax.plot(day.date, day.wealth_per_100, color=COLORS[name], label=LABELS[name],
                    linewidth=2.2 if name == "improved" else 1.6,
                    linestyle="--" if name in ["spy", "equal_weight"] else "-")
        ax.axhline(100, color="#c3cdd0", linewidth=.9)
        ax.set_ylabel("Value of initial $100")
        ax.set_xlabel("Execution and holding dates")
        ax.set_title("Forecast improvements face an investment test", loc="left", fontsize=12 if mobile else 14, pad=15, wrap=True)
        ax.yaxis.grid(True, color="#e6ebed"); ax.set_axisbelow(True)
        ax.legend(loc="upper left", fontsize=8.6 if mobile else 10, frameon=False, ncol=1 if mobile else 2)
        import matplotlib.dates as mdates
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        fig.savefig(RESULTS / f"wealth{suffix}.png", dpi=180); plt.close(fig)


def render_article(summary, publication_date=None):
    template = ROOT / "code/article_template.txt"
    if not template.exists():
        return
    path = ROOT / "blog9.qmd"
    if publication_date is None and path.exists():
        match = re.search(r"^date:\s*([0-9-]+)", path.read_text(), re.M)
        if match:
            publication_date = match.group(1)
    if publication_date is None:
        raise ValueError("First build requires --publication-date, verified in America/New_York")
    values = {"publication_date": publication_date}
    fm = {x["model"]: x for x in summary["forecast_metrics"]}
    im = {(x["strategy"], x["cost_bps"]): x for x in summary["investment_metrics"]}
    values.update({"n_test": f"{summary['test_rows']:,}", "test_dates": str(summary["test_dates"]),
                   "first_test": summary["test_first"], "last_test": summary["test_last"],
                   "train_last": summary["train_last"], "holding_periods": str(summary["holding_periods"]),
                   "portfolio_start": summary["portfolio_start"], "portfolio_end": summary["portfolio_end"],
                   "best_depth": str(summary["selected_parameters"]["max_depth"]),
                   "best_trees": str(summary["selected_parameters"]["n_estimators"]),
                   "best_lambda": f"{summary['selected_parameters']['reg_lambda']:g}"})
    for name in ["mean", "original", "improved"]:
        values[f"{name}_rmse"] = f"{fm[name]['rmse_percentage_points']:.2f}"
        values[f"{name}_r2"] = f"{100*fm[name]['oos_r2_vs_training_mean']:.1f}%"
        ic = fm[name]["mean_daily_rank_ic"]
        values[f"{name}_ic"] = "—" if ic is None else f"{ic:.3f}"
    for name in ["original", "improved", "equal_weight", "spy"]:
        row = im[(name, 10)]
        values[f"{name}_wealth"] = f"{row['terminal_per_100']:.2f}"
        values[f"{name}_cagr"] = f"{100*row['cagr']:.1f}%"
        values[f"{name}_drawdown"] = f"{100*row['max_drawdown']:.1f}%"
        values[f"{name}_sharpe"] = f"{row['daily_sharpe_rf_zero']:.2f}"
        values[f"{name}_gross_wealth"] = f"{im[(name,0)]['terminal_per_100']:.2f}"
        values[f"{name}_25bps_wealth"] = f"{im[(name,25)]['terminal_per_100']:.2f}"
    article = template.read_text()
    for key, value in values.items():
        article = article.replace("@@"+key+"@@", str(value))
    if "@@" in article:
        raise ValueError("Unfilled article placeholders")
    path.write_text(article)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publication-date")
    parser.add_argument("--presentation-only", action="store_true", help="Regenerate figures/article from saved verified results")
    args = parser.parse_args()
    if args.presentation_only:
        summary = json.loads((RESULTS / "summary.json").read_text())
        metrics = pd.read_csv(RESULTS / "forecast_metrics.csv")
        wealth = pd.read_csv(RESULTS / "daily_wealth.csv.gz", parse_dates=["date"])
        figures(metrics, wealth)
        render_article(summary, args.publication_date)
        return
    raw, panel, equities, design = read_inputs()
    df = make_features(raw, panel, equities)
    print(f"Feature-complete labeled rows: {len(df):,}", flush=True)
    pred, train, best, selected, audit = fit_models(df, design)
    metrics, uncertainty = forecast_metrics(pred)
    schedule = trade_schedule(pred, panel)
    weights, universe = target_weights(pred, schedule, equities)
    wealths, performances = [], []
    for cost in design["transaction_cost_bps_one_way"]:
        wealth, performance = backtest(panel, schedule, weights, universe, cost)
        wealths.append(wealth); performances.append(performance)
    wealth = pd.concat(wealths, ignore_index=True)
    performance = pd.concat(performances, ignore_index=True)
    wealth.to_csv(RESULTS / "daily_wealth.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    performance.to_csv(RESULTS / "investment_metrics.csv", index=False)
    summary = {
        "source_rows": len(raw), "equities": len(equities), "trading_dates": len(panel),
        "source_first": panel.index.min().date().isoformat(), "source_last": panel.index.max().date().isoformat(),
        "feature_complete_labeled_rows": len(df), "train_rows": len(train), "test_rows": len(pred),
        "train_first": train.date.min().date().isoformat(), "train_last": train.date.max().date().isoformat(),
        "train_last_label_end": train.label_end.max().date().isoformat(),
        "test_first": pred.date.min().date().isoformat(), "test_last": pred.date.max().date().isoformat(),
        "test_dates": pred.date.nunique(), "selected_candidate": selected, "selected_parameters": best,
        "original_features": ORIGINAL_FEATURES, "improved_features": IMPROVED_FEATURES,
        "holding_periods": len(schedule), "portfolio_start": schedule.entry_date.iloc[0].date().isoformat(),
        "portfolio_end": schedule.exit_date.iloc[-1].date().isoformat(),
        "forecast_metrics": json.loads(metrics.to_json(orient="records")),
        "forecast_uncertainty": uncertainty,
        "investment_metrics": json.loads(performance.to_json(orient="records")),
        "versions": {n: importlib.metadata.version(n) for n in ["xgboost", "numpy", "pandas", "matplotlib"]},
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    figures(metrics, wealth)
    render_article(summary, args.publication_date)
    print(metrics.to_string(index=False), flush=True)
    print(performance.loc[performance.cost_bps.eq(10)].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
