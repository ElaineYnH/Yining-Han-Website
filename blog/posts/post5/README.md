# Blog 5: Two Sides of Car-Free Philadelphia

Question: Where do high no-vehicle household shares overlap with lower tract incomes in Philadelphia?

The map is the central result. A scatterplot and household counts explain why a no-vehicle map alone cannot identify the same economic circumstances everywhere.

## Folder structure

```text
post5/
  blog5.qmd                         Generated article; no live code execution
  README.md                         These replication instructions
  requirements.txt                  Tested Python dependency versions
  code/
    download_data.py                Optional official-source download
    analyze.py                      Offline analysis, figures and article generation
    article_template.txt            Article prose with generated result placeholders
  data/
    raw/
      acsdt5y2024-b08201-philadelphia.dat
      acsdt5y2024-b19013-philadelphia.dat
      philadelphia_tracts_2024.geojson
    sources.json                     Exact URLs, retrieval time and SHA-256 checksums
    variables.json                   Census variable labels and definitions
    README.md                        Data and geography notes
  results/
    figures/car_free_income_map.png
    figures/income_vehicle_scatter.png
    tract_results.csv                All 408 matched tracts, estimates and 90% MOEs
    group_summary.csv                Household-count-weighted group summaries
    sensitivity.csv                  Rounded-cutoff sensitivity comparison
    summary.json                     Numerical results used in article
```

## Reproduce offline

Python **3.11 or later** is required. Open a terminal in this `post5` folder:

```bash
python -m venv .venv
```

Activate on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or activate on macOS/Linux:

```bash
source .venv/bin/activate
```

Then run:

```bash
python -m pip install -r requirements.txt
python code/analyze.py
```

The script locates files relative to its own location, so an absolute path to the script also works. It uses the included snapshots, verifies their checksums, joins every tract one-to-one, checks that tract household totals equal county estimates, and regenerates both PNGs, all result CSV/JSON files and `blog5.qmd`. It does not need an API key or internet access after package installation. No random sampling is used.

Edit prose in `code/article_template.txt` and rerun the analysis; regenerating will overwrite direct changes to `blog5.qmd`. All printed numbers and the article's table come from the computed results. To make a substantive change to the method, edit `analyze.py` as well.

## Optional: download the official sources again

```bash
python code/download_data.py
python code/analyze.py
```

The first command streams two **national** Census table files, retaining only Philadelphia's 408 tract rows and the county row. It also downloads Pennsylvania boundaries, retains Philadelphia and converts them to GeoJSON. Allow internet access and a few minutes. The public summary files do not require a Census API key. This overwrites the saved inputs and source checksums; later Census revisions can change the results. Keep the delivered snapshots to reproduce this version exactly.

## Definitions and calculation choices

- Geography: Philadelphia County, PA, FIPS `42101`, coterminous with Philadelphia city. Tract GEOIDs remain strings, including any leading zeros. Statistical tracts do not define neighborhood boundaries.
- Period: **2020–2024 ACS five-year estimates**, released as 2024 data. Income is already expressed in **2024 inflation-adjusted dollars**. This is one period, so no further inflation transformation or time-series comparison is made.
- Vehicle measure: `100 × B08201_E002 / B08201_E001`. Universe: households. This measures vehicles **available**, not vehicle ownership or number of transit users.
- Income measure: `B19013_E001`, tract median household income. In API notation these are `B08201_002E`, `B08201_001E` and `B19013_001E`; summary-file column order differs.
- Classify "more car-free" at or above the **countywide** no-vehicle percentage and "lower income" strictly below the **county** median household income. Use unrounded values for classification. "Lower income" is a relative description of a tract, not a Census poverty category or a count of individual low-income households.
- County reference estimates come directly from the county rows. Do **not** average tract percentages or tract medians to estimate city values. Group percentages sum estimated household counts first, then divide. ACS tabulations already include survey weights; applying additional individual sampling weights would be inappropriate.
- Convert negative ACS sentinel codes to missing values. Retain all 408 polygons. Tracts without a usable income or household denominator are gray; do not treat them as zero-income places. Include their no-vehicle households in the city denominator.
- Input and output tables retain Census **90% margins of error (MOEs)**. The maps and classifications use point estimates; this post does not estimate a confidence interval for the ratio or formally test differences. Cutoff sensitivity is not a test of statistical significance.
- Boundaries: Census **2024 cartographic boundary** shapefile at 1:500,000, designed for thematic mapping. Original CRS: NAD83 / `EPSG:4269`. Saved GeoJSON: WGS84 / `EPSG:4326`. Plot CRS: NAD83 / UTM zone 18N, `EPSG:26918`, meters. The map uses a 5 km scale and grid-north arrow; no area or distance-based economic statistic is estimated.
- The four map context labels are approximate locations for orientation, not boundaries used to aggregate data. Polygon colors, point colors, reference lines and group totals use the same classification.
- The scatterplot gives every tract equal dot size. Highlighted examples are generated by explicit rules: the highest-income tract with at least 1,000 households and at least 50% without vehicles, and the highest-no-vehicle tract with at least 1,000 households and income below $30,000. They illustrate heterogeneity, rather than estimate typical households.
- Main limitations: ecological inference, sampling uncertainty, within-tract diversity, cutoff choice, and lack of information on routes, fares, destinations, disability, household preferences or travel times. Co-location is not proof of causality, a service gap, or an optimal intervention.

## Data sources

1. [Census ACS table-based summary-file documentation](https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html).
2. [B08201 vehicle-availability table definitions](https://api.census.gov/data/2024/acs/acs5/groups/B08201.html).
3. [B19013 income table definitions](https://api.census.gov/data/2024/acs/acs5/groups/B19013.html).
4. [2024 Pennsylvania tract boundary ZIP](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_42_tract_500k.zip).
5. [Understanding ACS five-year estimates](https://www.census.gov/programs-surveys/acs/guidance/estimates.html).

Exact table download URLs and the snapshot retrieval date are in `data/sources.json`. The datasets are public U.S. Census Bureau products; no private microdata are included.

## Render within the existing website

From the website repository root:

```bash
quarto render blog/posts/post5/blog5.qmd
```

For deployment, commit the **entire `blog/posts/post5/` folder**. The existing GitHub Actions workflow runs `quarto render`; it only needs the committed article and outputs, so the workflow does not need GIS/Python installation. The existing `blog/index.qmd` listing discovers the post automatically. Keep `blog5.qmd` as the only article entry in this folder. Do not add another `index.qmd`.

Expected published article:

https://elaineynh.github.io/Yining-Han-Website/blog/posts/post5/blog5.html

Corresponding repository:

https://github.com/ElaineYnH/Yining-Han-Website

## Validation of the delivered version

- Official-source downloader run successfully.
- Offline analysis run successfully; all 408 tract matches and both city totals checked.
- Article values and table generated from the saved results.
- Both figures visually inspected after generation.
- Quarto post rendered within a copy of the existing website; article, images, source-code link, data links and blog-listing entry checked.

The files are prepared for the existing GitHub Pages workflow. Publishing still occurs when the repository owner commits and pushes them.
