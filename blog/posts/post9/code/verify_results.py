"""Independent checks of labels, chronology, trading windows and portfolio arithmetic."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "results"
raw = pd.read_csv(DATA / "prices.csv", parse_dates=["date"])
manifest = json.loads((DATA / "manifest.json").read_text())
summary = json.loads((OUT / "summary.json").read_text())
for name, meta in manifest["files"].items():
    assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == meta["sha256"]
assert hashlib.sha256((ROOT / "code/original_class_model.R").read_bytes()).hexdigest() == manifest["instructor_script_sha256"]
prices = raw.pivot(index="date", columns="symbol", values="adjusted").sort_index()
pred = pd.read_csv(OUT / "test_predictions.csv.gz", parse_dates=["date", "label_entry", "label_end"])
assert not pred.duplicated(["date", "symbol"]).any()
assert pred.groupby("date").size().eq(95).all()
assert np.isfinite(pred[["target", "original", "improved", "mean", "zero"]]).all().all()
assert pred["mean"].nunique() == 1

# Independently reconstruct every test target and its trading-date endpoints.
di = prices.index.get_indexer(pred.date)
ci = prices.columns.get_indexer(pred.symbol)
assert (prices.index[di+1] == pred.label_entry).all()
assert (prices.index[di+20] == pred.label_end).all()
values = prices.to_numpy()
labels = values[di+20, ci] / values[di+1, ci] - 1
np.testing.assert_allclose(labels, pred.target, rtol=1e-12, atol=1e-14)

# No validation or final training label reaches the next evaluation start.
splits = pd.read_csv(OUT / "split_audit.csv", parse_dates=["train_last_label_end", "validation_first", "validation_last_label_end"])
assert (splits.train_last_label_end < splits.validation_first).all()
assert (splits.loc[splits.split.ne("final_test"), "validation_last_label_end"] < pd.Timestamp("2024-01-01")).all()
cv = pd.read_csv(OUT / "validation_folds.csv")
pooled = cv.groupby("candidate").squared_error_sum.sum()/cv.groupby("candidate").rows.sum()
assert int(pooled.idxmin()) == summary["selected_candidate"]
assert len(cv) == 36

periods = pd.read_csv(OUT / "holding_periods.csv", parse_dates=["signal_date", "entry_date", "exit_date"])
assert (periods.signal_date < periods.entry_date).all()
assert (prices.index[prices.index.get_indexer(periods.signal_date)+1] == periods.entry_date).all()
assert (periods.exit_date.iloc[:-1].to_numpy() == periods.entry_date.iloc[1:].to_numpy()).all()
weights = pd.read_csv(OUT / "portfolio_weights.csv", parse_dates=["signal_date", "entry_date"])
np.testing.assert_allclose(weights.groupby(["strategy", "entry_date"]).weight.sum(), 1., atol=1e-12)
assert (weights.weight > 0).all()
metrics = pd.read_csv(OUT / "investment_metrics.csv")

# A separate holding-period calculation checks each gross daily backtest.
for strategy in ["original", "improved", "equal_weight", "spy"]:
    capital = 100.
    for signal, entry, exit_ in periods.itertuples(index=False, name=None):
        w = weights.loc[weights.strategy.eq(strategy) & weights.entry_date.eq(entry)]
        gross_factors = prices.loc[exit_, w.symbol].to_numpy()/prices.loc[entry, w.symbol].to_numpy()
        capital *= float(np.dot(w.weight, gross_factors))
    saved = metrics.loc[metrics.strategy.eq(strategy) & metrics.cost_bps.eq(0), "terminal_per_100"].iloc[0]
    np.testing.assert_allclose(capital, saved, rtol=1e-11)

# Exact closed-form buy-and-hold with entry and liquidation costs checks net costs.
start, end = periods.entry_date.iloc[0], periods.exit_date.iloc[-1]
for bps in [0, 10, 25]:
    c = bps/10000
    exact = 100*prices.at[end, "SPY"]/prices.at[start, "SPY"]*(1-c)/(1+c)
    saved = metrics.loc[metrics.strategy.eq("spy") & metrics.cost_bps.eq(bps), "terminal_per_100"].iloc[0]
    np.testing.assert_allclose(exact, saved, rtol=1e-12)
for strategy, group in metrics.groupby("strategy"):
    assert group.sort_values("cost_bps").terminal_per_100.diff().dropna().lt(0).all()

wealth = pd.read_csv(OUT / "daily_wealth.csv.gz", parse_dates=["date"])
for (strategy, bps), group in wealth.groupby(["strategy", "cost_bps"]):
    group = group.sort_values("date")
    compounded = 100*np.prod(1+group.daily_return.to_numpy())
    np.testing.assert_allclose(compounded, group.wealth_per_100.iloc[-1], rtol=1e-11)
    assert group.date.min() == start and group.date.max() == end
    assert (group.cost_dollars >= 0).all()

fm = pd.read_csv(OUT / "forecast_metrics.csv").set_index("model")
for name in ["mean", "original", "improved", "zero"]:
    independent_rmse = np.linalg.norm(pred.target-pred[name])/np.sqrt(len(pred))*100
    np.testing.assert_allclose(independent_rmse, fm.at[name, "rmse_percentage_points"], rtol=1e-12)

print(f"PASS: {len(pred):,} real-data labels, {pred.date.nunique()} test dates, all split boundaries,")
print(f"36 validation fits, {len(periods)} completed holding periods, gross portfolio identities,")
print("exact SPY net costs, daily compounding, and forecast-error calculations.")
