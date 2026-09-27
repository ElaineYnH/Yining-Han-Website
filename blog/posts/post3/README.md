# Blog Post 3: IPUMS CPS and education

This folder reproduces the three figures in `blog3.qmd`. The public repository
contains the code and a small table of weighted group totals, not IPUMS's
individual-level data. The included `data/cps_education_summary.csv` was
generated from the April 2019, 2020, and 2025 CPS extract. A website build can
render `blog3.qmd` directly from this summary file; the private extract is only
needed to regenerate the summary.

## Obtain the data

1. Register for free access at https://cps.ipums.org/cps/data.shtml.
2. Select the **basic monthly** April samples for 2019, 2020, and 2025
   (`cps2019_04b`, `cps2020_04b`, `cps2025_04b`). Do not select the March ASEC
   supplement instead.
3. Add `YEAR`, `MONTH`, `AGE`, `EDUC`, `EMPSTAT`, and `WTFINL` to a rectangular
   person-level extract. Download both the `.dat.gz` file and its corresponding
   DDI `.xml` codebook into the same private folder. Keep their original
   matching base names.

## Reproduce from the repository root

Install R, Quarto, and the packages `ipumsr`, `ggplot2`, and `scales` if needed:

```r
install.packages(c("ipumsr", "ggplot2", "scales"))
```

To regenerate the summary, run (replace the path with your actual DDI filename):

```bash
Rscript blog/posts/post3/prepare_cps.R "C:/Users/YourName/Downloads/cps_00001.xml"
quarto render blog/posts/post3/blog3.qmd
```

In RStudio, you can also open `prepare_cps.R` and click **Source** (or run
`source("blog/posts/post3/prepare_cps.R")` in the R console). Two file pickers
will open: choose the IPUMS DDI `.xml` first, then choose this folder's
`blog3.qmd`. Do this after unzipping the files into your website repository.
The script places the summary CSV next to `blog3.qmd` in its `data` folder.

The first command reads the private microdata and rewrites
`blog/posts/post3/data/cps_education_summary.csv`. The second produces the
article and three figures in `blog/posts/post3/figures/`. Commit the `.qmd`,
this README, the `.R` script, and the **summary CSV**. Your existing GitHub
Actions build can then render the article without access to the raw data.
Do not commit the extract `.dat.gz`, DDI `.xml`, or an IPUMS API key.

Rates are derived from weighted totals within each April/year/education cell:

- unemployment: unemployed / (employed + unemployed)
- employment-to-population: employed / all adults ages 25–64
- labor-force participation: (employed + unemployed) / all adults ages 25–64

`WTFINL` is already scaled correctly by `ipumsr::read_ipums_micro()`.
See the [IPUMS CPS weight documentation](https://cps.ipums.org/cps-action/variables/WTFINL)
and [terms of use](https://cps.ipums.org/cps/terms.shtml).
