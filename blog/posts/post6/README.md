# Blog 6: Matching Parents and Children with SQL

A short, self-contained SQL-with-Python tutorial for AEDS 6400. It teaches
relationship matching, SELECT/JOIN, GROUP BY and aggregation, a log-log IGE
regression, and the separate roles of income averaging and observation age.

## Install in the existing website

Copy the entire `post6` folder into `blog/posts/`, so the article is:

```
blog/posts/post6/blog6.qmd
```

Commit and push **the whole post6 folder**, including its data, code, results,
README, and requirements. No other post, index, website setting, or workflow
needs replacement. The existing blog listing discovers the new article.
The article and figure are already generated; publication does not require
you to run Python locally or download external data.

After the existing GitHub Actions deployment completes, the article URL is:

https://elaineynh.github.io/Yining-Han-Website/blog/posts/post6/blog6.html

Repository source:

https://github.com/ElaineYnH/Yining-Han-Website/tree/main/blog/posts/post6

Submit the published article URL and corresponding GitHub repository URL in
the Blog 6 Canvas assignment. The latest reviewed announcement moved Blog 6
to Friday, October 23; it did not specify a time. Check the current Canvas
assignment for the exact deadline and time zone rather than using the older
syllabus date.

## Follow the lesson

Use Python 3.11 or later. From the installed `post6` folder:

```bash
python -m pip install -r requirements.txt
python code/tutorial.py
```

The article's five Python blocks can instead be copied in order into the same
Python session, with the working directory set to `post6`. Its database lives
in memory, so no separate SQLite installation or server is required.
`code/tutorial.py` finds its own folder when run as a script and can also be
launched from the repository root:

```bash
python blog/posts/post6/code/tutorial.py
```

The script executes the SQL matching and aggregation, computes all four
estimates on the same 1,000 pairs, validates the keys and calculations, and
saves the resulting CSV files. It uses only NumPy, pandas, and Python's
standard library. Matplotlib is needed for the full rebuild below.

## Rebuild the article and figure

From `post6`:

```bash
python code/build_post.py
```

This reruns the lesson, creates `results/figures/income_timing.png`, and fills
the actual code and results into `code/article_template.txt` to regenerate
`blog6.qmd`. To regenerate the two input CSVs from the fixed seed as well:

```bash
python code/build_post.py --regenerate-data
```

Optional local rendering, from the website repository root with Quarto installed:

```bash
quarto render blog/posts/post6/blog6.qmd
quarto render blog/index.qmd
```

The article uses static Python code fences, not executable Quarto chunks.
GitHub Actions only renders the saved article and copies the supplied files.

## Files and schema

- `code/generate_data.py`: the complete simulation, fixed seed 20261023.
- `code/tutorial.py`: the actual Python/SQL lesson, with sections used verbatim
  in the article. No hidden helper is required to run the published blocks.
- `code/build_post.py`: analysis, figure, and article rebuild.
- `data/people.csv`: 2,000 people; `person_id` (unique), `family_id` (origin
  family), `birth_year`, and `parent_id` (blank for the designated parents).
- `data/earnings.csv`: 15,000 person-years; `person_id`, `year`, `age`, and
  `income`. The pair `(person_id, year)` is unique.
- `data/simulation.json`: data origin, all model parameters, units, and seed.
- `results/matched_incomes.csv`: 1,000 matched pairs and six income measures.
- `results/ige_estimates.csv`: estimates, measure definitions, and sample sizes.
- `results/match_preview.csv`: the article's first three identifier matches.
- `results/validation.json`: executed key, sample, and calculation checks.
- `results/sessionInfo.txt`: actual software versions used for the rebuild.
- `results/figures/income_timing.png`: the single comparison figure.
- `RUBRIC_CHECK.txt`: the ten rubric criteria, evidence, and validation scope.

Income columns in the matched file:

| Column | Person | Age(s) | Calculation |
| --- | --- | --- | --- |
| p1 | Designated parent | 40 | Single-year income |
| p5 | Designated parent | 40–44 | Arithmetic mean of income levels |
| c25 | Child | 25 | Single-year income |
| c25_5 | Child | 25–29 | Arithmetic mean of income levels |
| c40 | Child | 40 | Single-year income |
| c40_5 | Child | 40–44 | Arithmetic mean of income levels |

Logarithms are applied after constructing each measure. The IGE is the
unstandardized slope, with an intercept, in a regression of log child income
on log parent income. It is not a correlation, inheritance share, or causal
effect.

## Simulation assumptions and interpretation

These are newly generated teaching records, not PSID, CPS, or any other
survey. One parent and one child belong to each origin family. IDs are
stable, and `parent_id` explicitly encodes the relationship; a current
household ID is not used to infer parentage. Parents were born in 1950 and
children in 1980, keeping observation ages and dates fixed across families.

Let `P` be the parent's stable log-income component and `C` the child's:

```
P ~ Normal(0, 0.65^2)
C = 0.50 * P + u,       u ~ Normal(0, 0.40^2), independent of P
parent log income at ages 40–44 = 10.6 + P + e
child log income at ages 25–29 = 10.8 - 0.6 + 0.5 * C + e
child log income at ages 40–44 = 10.8 + C + e
e ~ Normal(0, 0.50^2), independent across people, years, P, and u
```

The generating permanent-income elasticity is 0.50. The latent slope within
this particular finite sample is approximately 0.536, recorded exactly in
`simulation.json`; 0.50 is not a slope forced onto the realized sample.
Annual incomes are exponentiated and rounded to cents. No values are zero or
missing. All values are already in constant teaching dollars, with no price
index conversion required.

The early-career coefficient 0.5 makes future high earners' income gaps
smaller when young. This deliberately illustrates life-cycle measurement
bias; a common downward shift alone would not change a log-log slope.
Independent transitory shocks also make single-year parental income a noisy
regressor. Averaging reduces that noise but does not eliminate the
age-dependent compression. The simulation is an illustration, not an
empirical calibration, national estimate, or universal prediction of bias.
No survey weights or population inference are claimed.

Observed estimates from the supplied seed are 0.135 (young single-year),
0.242 (young five-year), 0.334 (midcareer single-year), and 0.474 (midcareer
five-year). The analysis generates these values and the article's tables;
they are not hand-entered in the article source template.

With a real panel, first establish the survey's permanent person identifiers
and verified parental links. Define the selected parent's earnings versus
family income, convert nominal incomes to comparable prices, address zeros
before taking logs, and decide how to treat missing years and sample
selection. Shared household IDs alone do not establish the relationship.
If changing the teaching sample or windows, update the sample-size check,
simulation metadata, article assumptions, and interpretation accordingly.

## References

- Haider, Steven, and Gary Solon. 2006. “Life-Cycle Variation in the Association
  between Current and Lifetime Earnings.” American Economic Review 96(4):
  1308–1320. https://doi.org/10.1257/aer.96.4.1308
  Accessible abstract: https://hrs.isr.umich.edu/publications/biblio/7078
  The tutorial illustrates the proxy-measurement concept; it does not
  reproduce the paper's restricted Social Security data or empirical results.
- Python sqlite3 documentation: https://docs.python.org/3/library/sqlite3.html
- SQLite SELECT, JOIN, GROUP BY, and HAVING:
  https://sqlite.org/lang_select.html
