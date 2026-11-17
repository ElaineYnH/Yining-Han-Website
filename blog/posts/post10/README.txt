Blog 10 — Can Machine Learning Beat Last Week's Bike Demand?
Yining Han | AEDS 6400

PUBLISH WITH THE EXISTING WEBSITE

Copy this entire post10 folder into:
    Yining-Han-Website/blog/posts/post10/

The article entry is blog10.qmd. Keep every subfolder with it. Commit and push
the complete post10 folder. The current blog/index.qmd discovers posts
automatically; no root configuration or GitHub Actions change is required.
This article has no executable R/Python chunks. Its saved figures and results
are rendered by the existing workflow; local R, Quarto, and Python installation
are not needed to publish this supplied version.

Expected article URL after your GitHub Actions deployment succeeds:
https://elaineynh.github.io/Yining-Han-Website/blog/posts/post10/blog10.html

Submit that URL and the repository URL:
https://github.com/ElaineYnH/Yining-Han-Website

FOLDERS

blog10.qmd                  Generated article, ready for Quarto
code/build_blog.py           Full data preparation, tuning, fitting, results,
                            interpretation, figure and article generation
code/article_template.txt   Article template with computed substitutions
code/audit_workflow.py       Independent result and time-order checks
code/VERIFICATION.txt        Rubric evidence and actual validation scope
data/raw/hour.csv            Original UCI hourly observations, unmodified
data/raw/day.csv             Original UCI daily observations, unmodified
data/raw/Readme.txt          Original dataset documentation, unmodified
figures/                     Generated SVG/PNG figures and mobile versions
results/analysis_sample.csv  Timestamped features, target and inclusion sample
results/cv_candidates.csv    Every hyperparameter candidate's validation scores
results/cv_folds.csv         Candidate scores in each chronological fold
results/validation_windows.json  Actual training/validation dates and row counts
results/model_selection.json    Settings and model chosen before test evaluation
results/performance.csv      Validation and final test scores for all four models
results/test_predictions.csv Every test observation and prediction
results/errors_by_hour.csv   Test errors by hour of day
results/grouped_permutation_importance.csv  Group reliance, 20 shuffle repeats
results/summary.json         Computed article values and forecasting design
results/data_audit.json      Coverage, exclusions and raw-file SHA256 hashes
results/environment.json     Executed Python/library versions and random seed
results/independent_audit.json  Independent checks after the actual run

REPRODUCE THE COMPLETE ANALYSIS

Use Python 3.12. From this post10 folder:

    python -m pip install -r requirements.txt
    python code/build_blog.py
    python code/audit_workflow.py

No account, API key, data download, or external service is needed. All inputs
are included. The analysis compares 8 random-forest and 12 gradient-boosting
settings using 3 expanding validation windows, then fits each chosen model on
all development observations. Runtime depends on hardware; the supplied run
took about 3 minutes. Two CPU threads are used by the forest/OpenMP defaults.
Fixed random seed: 640010.

To regenerate only the article and figures from the saved analysis outputs:

    python code/build_blog.py --publication-only

To edit prose while preserving automatic numeric substitutions, edit
code/article_template.txt, then use the publication-only command. Preserve the
article date if you have already set a different actual publication date; the
template is its authoritative source. The initial date was checked against
actual America/New_York time (2026-11-16, EST), rather than the computer's
default time zone. The assignment's exact current deadline was not confirmed.

FORECAST DESIGN AND DATA AVAILABILITY

Forecast origin: end of the previous calendar day. All next-day hourly
predictions use information available by then. Predictor columns are explicitly
allow-listed in build_blog.py. They use calendar information, rentals at t-24h
and t-168h, a previous-seven-day same-hour mean, the previous day's total and
previous-seven-day daily average, previous-day weather, and a calendar trend.
Contemporaneous target-hour weather and the target components casual and
registered are excluded. No future weather forecasts are assumed available.

The hourly grid is regularized only to construct exact calendar lags; missing
observations are never assigned zero. A same-hour mean requires at least four
of the preceding seven daily observations. Complete primary lags and seven
previous daily totals are required. Of 17,379 observed hours, 431 lack required
history, leaving 16,948 observations (14,847 development, 2,101 test). The 731
daily totals are checked against hourly sums for every date.

Validation folds (exclusive right endpoints):
  Train before 2012-01-01; validate [2012-01-01, 2012-04-01).
  Train before 2012-04-01; validate [2012-04-01, 2012-07-01).
  Train before 2012-07-01; validate [2012-07-01, 2012-10-01).

Choose parameters and the model using the lowest pooled validation MAE,
including both simple benchmarks among the available choices. One-hot encoding
is fitted inside each training fold. Gradient boosting's internal random
early-stopping split is disabled. Test: 2012-10-01 through 2012-12-31. Final
models are fixed throughout testing. Historical predictor values update each
day using already observed outcomes, including previous days within the test
quarter. This is a rolling one-day-ahead evaluation, not a single three-month
forecast issued in September. All models are scored on the identical hours.

Simple rules:
  1. Calendar average: training-only mean for hour x working-day status;
     fallback to training-only hour mean if a category is unseen.
  2. Last week, same hour: exact t-168h observed count.

Primary measure: MAE, in rentals/hour. RMSE penalizes large errors. Test bias is
also saved. The peak-period check is fixed to working days at hours 7, 8, 9,
16, 17, 18, and 19. The example graph is fixed to the first full test week,
2012-10-01 through 2012-10-07; it was not selected for a favorable appearance.

INTERPRETATION AND LIMITS

After selection and evaluation, related raw input columns are shuffled jointly
within five groups. A common row permutation within each group preserves its
internal relationships. Mean increases in test MAE describe model reliance.
Whiskers are shuffle standard deviations, not confidence intervals. Shuffling
breaks cross-group relationships and can create unusual combinations; these
are not causal effects. Interpretation is not used to select or modify models.

The retained sample excludes unrecorded hours and observations with unavailable
lags. It measures completed system-wide rentals, not unmet demand, available
inventory, or station-level shortages. Results describe a historical system and
one held-out quarter, not guaranteed current operational performance. The
validation improvement over the weekly rule is modest. Before operational use,
evaluate on recent data and station-level service outcomes.

SOURCES

Hadi Fanaee-T (2013), Bike Sharing, UCI Machine Learning Repository.
https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset
https://doi.org/10.24432/C5W894
Downloaded by the user from the official UCI page and supplied as
bike+sharing+dataset.zip. Source files are preserved byte-for-byte. Current UCI
license: CC BY 4.0; original dataset readme and study citation are included.

Fanaee-T, H. and Gama, J., Event labeling combining ensemble detectors and
background knowledge, Progress in Artificial Intelligence.
https://doi.org/10.1007/s13748-013-0040-3

Algorithm documentation:
https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html
https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html
https://scikit-learn.org/stable/modules/permutation_importance.html

Do not place extra Markdown drafts or internal grading checklists in this
publication folder. Auxiliary documentation here uses .txt to avoid becoming
additional articles in the site's automatic listing.
