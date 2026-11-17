"""Independently check saved outputs and a future-data leakage invariant."""
from pathlib import Path
import json
import tempfile
import shutil
import numpy as np
import pandas as pd
import build_blog as build


def main():
    root = Path(__file__).resolve().parents[1]
    results = root / "results"
    checks = {}
    pred = pd.read_csv(results / "test_predictions.csv", parse_dates=["timestamp"]).set_index("timestamp")
    scores = pd.read_csv(results / "performance.csv").set_index("model")
    raw = pd.read_csv(root / "data/raw/hour.csv", parse_dates=["dteday"])
    raw["timestamp"] = raw["dteday"] + pd.to_timedelta(raw["hr"], unit="h")
    target = raw.set_index("timestamp")["cnt"]
    assert pred.index.is_unique and pred.index.is_monotonic_increasing
    np.testing.assert_array_equal(pred["observed"], target.reindex(pred.index))
    checks["test_targets_match_unmodified_source"] = True
    np.testing.assert_array_equal(pred["Last week, same hour"], target.reindex(pred.index - pd.Timedelta(days=7)))
    checks["weekly_rule_uses_exact_calendar_lag"] = True
    for name in scores.index:
        e = pred[name].to_numpy() - pred["observed"].to_numpy()
        for metric, value in [("MAE", np.mean(np.abs(e))),
                              ("RMSE", np.sqrt(np.mean(e * e))), ("Bias", np.mean(e))]:
            np.testing.assert_allclose(value, scores.loc[name, "test_" + metric], rtol=1e-12)
    checks["all_test_metrics_recomputed_from_saved_predictions"] = True
    windows = json.loads((results / "validation_windows.json").read_text())
    for window in windows:
        assert pd.Timestamp(window["train_end"]) < pd.Timestamp(window["validation_start"])
        assert pd.Timestamp(window["validation_end"]) < pd.Timestamp("2012-10-01")
    checks["all_validation_windows_precede_test"] = True
    selection = json.loads((results / "model_selection.json").read_text())
    candidates = selection["best_by_model"]
    assert selection["selected_model"] == min(candidates, key=lambda n: candidates[n]["validation_MAE"])
    checks["selected_model_minimizes_validation_MAE"] = True

    original_data = build.DATA
    original, _ = build.load_features()
    origin_target = pd.Timestamp("2012-10-01")
    with tempfile.TemporaryDirectory(prefix="blog10-leakage-check-") as temporary:
        destination = Path(temporary)
        for p in original_data.iterdir():
            if p.is_file(): shutil.copyfile(p, destination / p.name)
        for filename in ["hour.csv", "day.csv"]:
            f = pd.read_csv(destination / filename)
            future = pd.to_datetime(f["dteday"]) >= origin_target
            for column in ["casual", "registered", "cnt"]:
                f.loc[future, column] = 2 * f.loc[future, column]
            for column in ["temp", "atemp", "hum", "windspeed"]:
                f.loc[future, column] = 1 - f.loc[future, column]
            f.to_csv(destination / filename, index=False)
        build.DATA = destination
        changed, _ = build.load_features()
        before = original.loc[original["date"] == origin_target, build.FEATURES]
        after = changed.loc[changed["date"] == origin_target, build.FEATURES]
        pd.testing.assert_frame_equal(before, after, check_exact=False, rtol=1e-14, atol=1e-14)
        build.DATA = original_data
    checks["changing_future_counts_and_weather_does_not_change_day_ahead_inputs"] = True
    assert set(build.FEATURES).isdisjoint(["target", "cnt", "casual", "registered", "temp", "hum", "weathersit"])
    checks["predictor_allow_list_excludes_targets_and_contemporaneous_weather"] = True
    checks["n_test"] = len(pred)
    (results / "independent_audit.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
