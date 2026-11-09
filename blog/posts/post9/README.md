# Blog 9: Better Forecasts, Worse Portfolios

Real-data reanalysis of the AEDS 6400 classroom stock-prediction experiment.
The revised model reduces forecast error relative to the class specification,
but loses to a constant training-mean forecast and produces a worse portfolio
than the class specification. The article reports these results without retuning
on the test sample.

## Add to the existing website

Copy this entire `post9` folder into `blog/posts/post9/` in
<https://github.com/ElaineYnH/Yining-Han-Website>.
The only article entry is `blog9.qmd`. Commit and push every file in this folder.
No changes to `_quarto.yml`, `blog/index.qmd`, or GitHub Actions are required.
The existing listing discovers this post automatically.

All output is precomputed. Publishing runs no Python, trains no models, downloads
no financial data, and installs no additional R packages. The figures are static
desktop/mobile PNGs, with intrinsic image height and no iframe.

Expected URL after a successful deployment:
<https://elaineynh.github.io/Yining-Han-Website/blog/posts/post9/blog9.html>

Submit the published article URL and the GitHub repository URL to the course.
The ZIP itself is a website-ready source package, not evidence of publication.

## Reproduce the analysis

Python 3.12 was used. From this `post9` directory, preferably in a fresh environment:

```bash
python -m pip install -r requirements.txt
python code/build_blog9.py
python code/verify_results.py
```

The full run performs 36 validation fits and two final model fits. It requires no
network after installing dependencies: `data/prices.csv` is the exact uploaded
snapshot and is checked against SHA-256 before use. It regenerates metrics,
predictions, model files, portfolio weights, daily wealth, plots, and the article.
Model binaries are raw XGBoost Boosters (`Booster.load_model`), avoiding sklearn
wrapper serialization differences.

To regenerate presentation only from saved results:

```bash
python code/build_blog9.py --presentation-only
```

The builder preserves the existing article date. To change it deliberately, use
`--publication-date YYYY-MM-DD` after checking the date in America/New_York.
The initial date was checked as 2026-11-08, 22:27 EST, independently of the
client's default timezone. It is not backdated to a course deadline.

To render the article and listing with Quarto, run these from the website root:

```bash
quarto render blog/posts/post9/blog9.qmd
quarto render blog/index.qmd
```

The existing GitHub Actions runs `quarto render` for the whole site, including
its existing R dependencies. This post itself uses no execution engine.

## Data, target, and chronology

- The instructor's 95-equity list plus SPY: 116,832 rows over 1,217 trading dates,
  2022-01-03 through 2026-11-06, with no missing or duplicated observations.
- Real Yahoo Finance data uploaded by the author after downloading via yfinance.
  See `data/SOURCES.txt`, the original `manifest.json`, and coverage audit.
- Exact class target: adjusted[t+20]/adjusted[t+1] - 1, which spans 19 daily
  return intervals. Features are known after signal-day close.
- The 14-feature baseline retains every numeric predictor in the original R recipe,
  including OHLCV and price levels. It is a Python port of the specification,
  not a claim to recreate a historical R run bit-for-bit.
- Final training: 2022-07-06 through 2023-11-30 signals, with labels ending by
  2023-12-29; 33,725 stock-date rows. All labels finish before the test starts.
- Three pre-2024 validation windows select among 12 predeclared revised models.
  Each fold separately purges crossing labels. The test never selects parameters.
- Common final test: 66,120 forecasts across 696 dates, 2024-01-02–2026-10-09.
  Later signals are excluded because their future targets are not yet observed.
- Neither model is updated during the test period. Constant training mean is the
  main forecast benchmark; zero-return metrics are an additional sensitivity.

`code/CLASS_MODEL_AUDIT.txt` documents original ratios, R parameter translation,
the label purge, aligned benchmarks, and corrected annualization in detail.

## Portfolio evaluation

Both models signal on each month's first trading day and execute at the next
session's adjusted close. The top ten predictions receive weights proportional
to nonnegative forecasts, with equal weights if all ten are nonpositive.
Weights drift between monthly executions. Realized holding windows run from one
execution close to the next; their lengths vary and are not substituted for the
fixed-horizon forecast labels.

Only 34 completed holding intervals are used, 2024-01-03–2026-11-03. The next
month's execution is the terminal liquidation date, not an incomplete final
return. Every strategy and benchmark shares the identical daily trading window.
Benchmarks are SPY buy-and-hold and a monthly equal-weight portfolio of all 95
equities, allowing the selected-universe effect to be inspected.

The 0,10,25 basis-point cost cases charge each dollar bought or sold. Initial
entry and terminal liquidation are included. After-cost holdings are solved
self-financing, and daily prices mark positions to market between trades.
There is no tax model, cash interest, leverage, or short selling. Sharpe uses
daily net returns, sqrt(252), and zero risk-free interest; it is not estimated
CAPM alpha. CAGR uses actual elapsed calendar years.

The forecast-loss uncertainty check aggregates each date's 95 stock errors and
resamples 20-date blocks (2,000 draws), retaining cross-sectional dependence and
some dependence from overlapping labels. It is descriptive and conditional on
this universe and window, not a proof of future statistical or investment gains.

## File structure

- `blog9.qmd`: the sole new article.
- `code/build_blog9.py`: training, validation, forecasts, portfolios, figures, text.
- `code/verify_results.py`: independent label, chronology, portfolio and cost checks.
- `code/original_class_model.R`: the instructor's original code, preserved verbatim.
- `code/article_template.txt`: article template; all computed numbers are inserted.
- `code/CLASS_MODEL_AUDIT.txt`: baseline mapping, repairs and scope limits.
- `code/VERIFICATION.txt`: rubric evidence and actual verification record.
- `data/prices.csv`: original real OHLCV and adjusted close snapshot, unchanged.
- `data/manifest.json`, `download_quality.csv`: original download metadata and audit.
- `data/analysis_design.json`: model grid and evaluation choices frozen before fitting.
- `data/classroom_context.json`: aggregated contextual observations from the class sheet.
- `data/SOURCES.txt`: traceable data and methodology sources.
- `results/validation_*.csv`, `split_audit.csv`: model selection and leakage checks.
- `results/test_predictions.csv.gz`: all test targets, endpoints and forecasts.
- `results/forecast_metrics.csv`, `daily_forecast_losses.csv`, `forecast_uncertainty.json`.
- `results/holding_periods.csv`, `portfolio_weights.csv`, `investment_metrics.csv`.
- `results/daily_wealth.csv.gz`, `summary.json`, `models/*.ubj`, `*.png`.

Internal notes and templates use `.txt` so they cannot become extra posts.
`README.md` is Quarto's standard excluded repository README.

## Interpretation limits

A selected list of surviving large companies is not a survivorship-free historical
investment universe. Present-vintage adjusted data can be revised and do not
recreate a point-in-time feed. One 2024–2026 window, correlated stocks, overlapping
forecast targets and a simplified cost model cannot establish a deployable edge.
The class model's realized success does not justify selecting it after observing
this test. Results support the narrower conclusion that reducing forecast error
did not improve this portfolio under the stated design.
