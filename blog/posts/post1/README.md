# Blog 1: Lagrange multipliers through a lunch-budget puzzle

This revision explains why an optimal affordable bundle can still have positive
marginal benefits. A single two-panel figure connects the best allocation to
equal marginal gains per dollar. The multiplier then measures the local benefit
of a larger budget.

## Files

- `blog1-260906.qmd`: the article, retaining its original website filename and URL.
- `code/build.py`: calculates the model, checks the optimum and multiplier,
  writes numerical outputs, draws the figure, and generates the article.
- `code/article_template.txt`: article text with tokens filled by the script.
- `data/model.json`: complete illustrative assumptions and date metadata.
- `results/summary.json`: numerical results, the local approximation, and the
  exact finite budget change.
- `results/example_allocations.csv`: the allocations discussed in the article.
- `results/spending_curve.csv`: all 601 evaluated full-budget allocations.
- `results/figures/budget_and_marginal_returns.png`: the published figure.
- `requirements.txt`: the Python package versions used to generate the outputs.

## Reproduce the model and figure

Use Python 3.11 or later. From the website repository root:

```bash
python -m pip install -r blog/posts/post1/requirements.txt
python blog/posts/post1/code/build.py
```

The script also works when called with an absolute path from another directory.
It makes no network requests and requires no private files or API keys.
It overwrites the generated `.qmd`, figure, CSV files, and summary JSON with
deterministic results from the saved assumptions and template. Edit the template
if changing the article text, then rerun the script.

The inputs are assumptions for a teaching example. There is **no external
dataset**: the $12 budget, prices, and utility score are not empirical estimates.
Food and drink portions are nonnegative and divisible. The utility function is
`U(x,y)=x*y`, subject to `2*x+y<=12`.

At the optimum, spending on each good is $6, so `x=3`, `y=6`, and utility is 18.
Both marginal gains per dollar equal 3. With a $13 budget the optimal score is
21.125, a finite gain of 3.125. The multiplier's local approximation is 3.

The analytical check uses expenditure `s` on food:
`U(s)=s*(12-s)/2`, whose second derivative is -1 on `[0,12]`.
The unique global maximum is at `s=6`; the endpoints give zero.
For a general positive budget `I`, `V(I)=I^2/8`, so `V'(12)=3`.

## Render and publish

The figure and results are already saved. The `.qmd` contains no executable
Python or R chunks, so the existing GitHub Actions render step does not need
Python or new packages for this revision. No edits to `_quarto.yml`,
`blog/index.qmd`, or the workflow are needed.

For an optional local check with Quarto installed, run from the website root:

```bash
quarto render blog/posts/post1/blog1-260906.qmd
quarto render blog/index.qmd
```

After copying this folder into the existing project, commit and push all files
in `blog/posts/post1/`. GitHub Actions can render and deploy the site as before.
Do not keep a second revised `.qmd` beside the original: that would create a
duplicate blog entry. The rendered `docs/` files are build outputs, not required
inputs in the revision package.

Article URL after deployment:
<https://elaineynh.github.io/Yining-Han-Website/blog/posts/post1/blog1-260906.html>

Source directory after the update:
<https://github.com/ElaineYnH/Yining-Han-Website/tree/main/blog/posts/post1>

## Mathematical reference

OpenStax, *Calculus Volume 3*, section 4.8, “Lagrange Multipliers”:
<https://openstax.org/books/calculus-volume-3/pages/4-8-lagrange-multipliers>.
The numerical example, figure, and explanation in this folder are an original
illustration. The source is provided for the standard mathematical formulation.
