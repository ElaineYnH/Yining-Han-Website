# Blog Post 3: IPUMS CPS and education

This revision connects the existing three figures into one economic story:
the unemployment shock eased, employment rebounded, and a large education
gap in jobholding remained. The final figure locates most of the 2025 gap in
nonparticipation rather than in unemployment. This is an accounting result,
not an estimate of the causal effect of education.

The original `data/cps_education_summary.csv`, `prepare_cps.R`, education
groups, and three plot specifications are retained. This revision uses the
saved weighted summary; it does not claim to have rerun the private IPUMS
microdata extract. No individual-level records are republished.

## Install and publish

Replace only `blog/posts/post3/` with the `post3` folder in this ZIP. Commit
and push that folder using the existing website workflow. The supplied
`blog3.qmd` already contains its numbers, and the three PNGs are included.
The existing GitHub Actions build can render it without R or the private
extract. Other post folders and website settings do not need replacement.

The article path remains `blog/posts/post3/blog3.html`.

## Reproduce from the saved summary

Install R and these packages if needed:

```r
install.packages(c("ggplot2", "scales"))
```

From the website repository root, run:

```bash
Rscript blog/posts/post3/code/build_from_summary.R
quarto render blog/posts/post3/blog3.qmd
```

The R script runs offline. It rebuilds the original three plots in `figures/`,
fills the numeric values in `code/article_template.txt` to produce `blog3.qmd`,
and writes `results/decomposition_2025.csv`, `results/story_numbers.csv`, and
`results/sessionInfo.txt`. It verifies rates against the weighted totals and
checks that the two nonemployment components add to the employment gap.
It does not overwrite the input summary. The Quarto command requires Quarto.

## Regenerate the summary from IPUMS (optional)

This step is needed only to rebuild the weighted summary from the original
microdata. It is not needed to install or publish the supplied revision.

1. Register for free access at https://cps.ipums.org/cps/data.shtml.
2. Select the **basic monthly** April samples for 2019, 2020, and 2025:
   `cps2019_04b`, `cps2020_04b`, and `cps2025_04b`. Do not substitute the March
   ASEC supplement.
3. Add `YEAR`, `MONTH`, `AGE`, `EDUC`, `EMPSTAT`, and `WTFINL` to a rectangular
   person-level extract. Download the `.dat.gz` file and its matching DDI
   `.xml` codebook into one private folder, retaining their matching names.
4. Install `ipumsr` with `install.packages("ipumsr")`.
5. From the website repository root, run (replace the DDI path):

```bash
Rscript blog/posts/post3/prepare_cps.R "C:/Users/YourName/Downloads/cps_00001.xml"
Rscript blog/posts/post3/code/build_from_summary.R
quarto render blog/posts/post3/blog3.qmd
```

In RStudio, `prepare_cps.R` can also be sourced. Its file pickers ask for the
DDI `.xml` and the installed `blog3.qmd`. It writes the summary into the
article's `data/` folder. Then run the build script as above. If you change
the samples or article's claims, update the template and its checks too.

Commit the code, article, summary, figures, and results. Keep the `.dat.gz`,
DDI `.xml`, and any IPUMS API key outside the public repository.

## Definitions and calculation

The sample is adults ages 25–64 in April of each year. All numerators and
denominators use the basic monthly person weight `WTFINL`, correctly scaled
by `ipumsr::read_ipums_micro()`. See the
[IPUMS weight documentation](https://cps.ipums.org/cps-action/variables/WTFINL)
and [terms of use](https://cps.ipums.org/cps/terms.shtml).

- Unemployment rate = unemployed / (employed + unemployed).
- Employment-to-population ratio = employed / group population.
- Participation rate = (employed + unemployed) / group population.
- Figure 3 uses unemployed / population and outside labor force / population.
  Both shares have the same denominator, unlike the unemployment rate.

For the bachelor's-plus and less-than-high-school groups in April 2025:

```
employment gap = nonparticipation gap + unemployed/population gap
24.8448 percentage points = 22.8837 + 1.9611
nonparticipation fraction of gap = 22.8837 / 24.8448 = 92.1%
```

CSV columns ending in `_share` use proportions (0–1).
`story_numbers.csv` reports percentages and percentage points, as labeled.
The article rounds the components to 22.9 and 2.0 points; these rounded
figures sum to 24.9 rather than the unrounded gap's rounded value of 24.8.

These are three repeated cross sections, not an individual panel or a
seasonally adjusted series. Differences are descriptive point estimates;
the post does not claim statistical significance or a causal education effect.
The saved summary does not distinguish reasons for nonparticipation. See the
[BLS definitions](https://www.bls.gov/cps/cps_htgm.htm) and the
[2020 classification caveat](https://www.bls.gov/blog/2020/update-on-the-misclassification-that-affected-the-unemployment-rate.htm).
