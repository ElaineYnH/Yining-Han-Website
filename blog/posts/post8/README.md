# Blog 8: What Can a 53% Poll Really Tell Us?

This is an explicitly labeled statistical simulation for AEDS 6400 Blog Post 8.
There are no empirical survey observations or claims about actual transit support.

## Add to the existing website

Copy this entire `post8` folder to `blog/posts/post8/` in
<https://github.com/ElaineYnH/Yining-Han-Website>.
Commit and push every file in the folder. The article entry is `blog8.qmd`.
The existing blog listing discovers it automatically. No changes to `_quarto.yml`,
`blog/index.qmd`, or the GitHub Actions workflow are required.

All results are precomputed. Rendering this post does not run Python or install
additional R packages. The interactive figure uses local images and plain
JavaScript, works offline, and needs no CDN, API key, or server-side process.

Expected article URL after a successful deployment:
<https://elaineynh.github.io/Yining-Han-Website/blog/posts/post8/blog8.html>

## Reproduce the analysis

Use Python 3.11 or later. From this `post8` directory:

```bash
python -m pip install -r requirements.txt
python code/build_blog8.py
python code/verify_results.py
```

The build takes roughly one minute, depending on hardware, and needs no network
after dependencies are installed. It regenerates the article, data, results,
images, and interactive HTML from the fixed seed. It preserves the date already
in `blog8.qmd`. An explicit `--publication-date YYYY-MM-DD` overrides that date;
use the verified America/New_York publication date, not a computer's default date.

To render the whole website, use the existing GitHub Actions workflow, or run
`quarto render` from the website root in an environment with its existing R
dependencies. A full site render is also needed to verify the blog listing.

## File structure

- `blog8.qmd`: the only new article entry.
- `code/build_blog8.py`: simulation, figures, results, and article generation.
- `code/article_template.txt`: article text with automatically inserted numbers.
- `code/coverage_template.html.txt`: interactive display template.
- `code/verify_results.py`: independent checks against saved draws and binomial theory.
- `code/VERIFICATION.txt`: rubric evidence and actual verification record.
- `data/simulation_design.json`: model, seed, settings, and sample checksum.
- `data/simulated_sample.csv`: 800 generated independent 0/1 responses; the first
  200 form the article's example. The 50/200/800 examples are nested prefixes,
  so they need not have equal observed shares.
- `data/SOURCES.txt`: sources and the boundary between simulation and observation.
- `results/bootstrap_draws.csv`: 20,000 bootstrap statistics for each sample size.
- `results/coverage_trials.csv`: 5,000 new polls per size and all three intervals.
- `results/coverage_summary.csv`: coverage, Monte Carlo standard errors, and width.
- `results/null_draws.csv`: 50,000 new null polls per size.
- `results/test_summary.csv`: tail counts, cutoffs, Monte Carlo and exact p-values.
- `results/summary.json`: full numerical summary used by the article.
- `results/*.png`: desktop and mobile plots.
- `results/coverage_explorer.html`: self-contained logic with local image resources.

Internal notes and templates deliberately use `.txt`, not renderable Markdown,
so they do not become extra blog entries. `README.md` is the standard repository
README, which Quarto excludes from article rendering by default.

## Statistical design

The known population model is independent Bernoulli support with probability
0.55. Seed 640008 generates the original sample. Purpose-specific SeedSequence
streams separate original-sample bootstrapping, coverage experiments, and null
simulation. No seed was selected to obtain a significant result.

The main bootstrap literally samples observed responses with replacement.
Each coverage poll is a new draw from the population. Conditional on that poll's
support count k, the support count in a bootstrap sample is exactly
Binomial(n, k/n). The coverage experiment uses this equivalent count method for
speed, constructing a fresh distribution of 2,000 resamples for every poll.
It does not substitute a Wald interval or repeatedly bootstrap just the first poll.
Percentiles use NumPy's linear quantile method.

The null experiment is separate: its polls are generated at p=0.50. The statistic
is the sample support share, and the two-sided extremeness measure is its absolute
distance from 0.50. Integer counts include boundary ties exactly. Monte Carlo
p-values use (extreme draws + 1)/(draws + 1). Rejection cutoffs are determined
from the independent simulated null distribution at alpha=0.05, without reference
to the observed sample result. Discreteness makes the actual rejection rate
slightly below 5%. Exact binomial calculations are validation checks, not a
replacement for the simulated null distribution.

The explorer changes sample size (50, 200, 800) and confidence (90%, 95%, 99%).
It displays the first 50 intervals in generation order, without selecting hits
or misses; its summary uses all 5,000. It loads fixed precomputed experiments,
so switching controls does not rerun random simulations. Larger samples narrow
intervals; higher confidence levels widen them. Coverage is approximate and is
not asserted for every distribution or bootstrap interval method.
