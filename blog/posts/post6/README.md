# Blog 6: Matching Parents and Children with SQL

This is a short tutorial using the user's actual PSID public-use extract, J366685.
The published post includes both mother-child and father-child matches. Every
estimate uses the same 606 children, with one record per biological parent-child
relationship (1,212 relationships, 424 unique mothers and 424 unique fathers).

## Install into the existing website

Replace the complete `blog/posts/post6/` folder with this `post6/` folder. Keep a
backup outside `blog/posts/`, if desired. Commit and push the replacement folder.
The supplied `blog6.qmd`, figure and aggregate results are already generated.
Publishing does not require running Python locally, installing Quarto locally,
changing GitHub Actions, or changing another post. The code blocks are ordinary
displayed Python, not executable Quarto cells. `blog/index.qmd` lists the post
automatically. The article uses native MathML for equations.

Publication URL:
https://elaineynh.github.io/Yining-Han-Website/blog/posts/post6/blog6.html

Repository:
https://github.com/ElaineYnH/Yining-Han-Website/tree/main/blog/posts/post6

## What is included

```
post6/
  blog6.qmd                  generated tutorial, five consecutive Python blocks
  README.md                  installation, access and replication instructions
  RUBRIC_CHECK.txt           evidence for the six common and four specific items
  REVISION_NOTES.txt
  requirements.txt
  code/
    prepare_data.py          fixed-width import, roles, years, real-dollar income
    tutorial.py              actual SQL match/aggregation, OLS, bootstrap, figure
    run_analysis.py          one-command replication
    build_post.py            rebuild article from calculated results and code
    article_template.txt
  data/
    cpi.csv                  public BLS annual CPI-U values, not PSID microdata
    variable_manifest.json   exact required variables and wave mapping
    sources.json             source links and extract fingerprint
  results/
    ige_estimates.csv        eight aggregate estimates and confidence intervals
    sample_flow.csv          counts at each selection stage
    preparation_counts.csv   counts by survey/income year
    analysis_summary.json    aggregate sample and estimation facts
    sessionInfo.txt
    validation.json          completed checks and their limits
    figures/income_timing.png
```

PSID raw records, prepared individual tables, identifiers, the SQLite database,
matched income records and bootstrap draws are not included in the publication
folder. A private working directory is used for these files when replicating.

## Data source and access

Data citation: Panel Study of Income Dynamics, public-use dataset. Produced and
distributed by the Survey Research Center, Institute for Social Research,
University of Michigan, Ann Arbor, MI. Downloaded 2026.

- PSID: https://psidonline.isr.umich.edu/
- Data Center: https://simba.isr.umich.edu/
- Official identifiers and file/role guidance:
  https://psidonline.isr.umich.edu/Guide/FAQ.aspx
- Access and reuse conditions: https://simba.isr.umich.edu/U/CondUse.aspx

Each replicator must register for their own PSID access and follow the data
provider's conditions. The source input for the supplied results is the user's
downloaded `J366685.zip`, dated October 25, 2026, containing an ASCII fixed-width
file, Stata import instructions, value labels and a custom PDF codebook. The
extract contains 62,218 individual records and 181 variables. Analysis reads 109
needed variables; unused total-family-income and weight variables remain unused.

Input ZIP SHA-256:
`56fabedbc986cf907ed1b547b310ea7dc2cba0ca74f551a4245626788fa081c9`.

If extracting again, choose the all-individuals domain and select every variable
listed in `data/variable_manifest.json`. Request ASCII data with Stata import
statements and the codebook. The Data Center merges relevant family variables
onto individual records. The importer reads positions from that ZIP's `.do`
file, so it does not assume a particular ordering or filename. Changed releases
or corrections can legitimately change results; the exact fingerprint above
identifies the input used here. No automatic download of PSID records is made.

The independent price index is BLS CPI-U, U.S. city average, all items, not
seasonally adjusted, series `CUUR0000SA0`, annual average (M13). Included CPI
values cover 1989-2022; the analysis uses the 17 income years 1993-2022 and the
2020 base index 258.811. Sources:

- https://www.bls.gov/cpi/factsheets/purchasing-power-constant-dollars.htm
- https://www.bls.gov/developers/api_signature_v2.htm
- https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0?startyear=2019&endyear=2022&annualaverage=true

## Replicate on Windows with Python

Python 3.11 or newer is recommended. Open a terminal in `post6`. Keep your
downloaded ZIP outside the website repository. With the user's Python 3.11
installation, run the following, changing only the input path:

```powershell
py -3.11 -m pip install -r requirements.txt
py -3.11 code/run_analysis.py --input "C:\Users\YOUR_NAME\Downloads\J366685.zip"
```

`YOUR_NAME` is a placeholder for the actual Windows folder name. Quoted paths
with spaces or Chinese characters are supported. On macOS/Linux use `python3`
instead of `py -3.11`. Stata is not required: `.do` only supplies import positions.

By default the program creates `blog6_psid_work` in your user directory, outside
the website. It contains `psid.sqlite`, `preparation_audit.json` and
`matched_incomes.csv`. The private directory's location can be changed with
`--work-dir`, but the script rejects a location inside the website repository.
Do not commit this working directory or the source ZIP to GitHub.

The command actually imports the data, prepares the SQLite tables, constructs
the links with SQL, calculates eight estimates, runs the 2,000-draw family
bootstrap, saves aggregate results and the figure, and rebuilds `blog6.qmd`.
It does not upload files, publish a website or contact PSID.

To rerun from a previously prepared default database:

```powershell
py -3.11 code/run_analysis.py --reuse-prepared
```

To reproduce only the article's point estimates, first run the full command,
then run its five displayed blocks consecutively. `WORK` defaults to the same
user-directory path. Change it in block 1 if using a custom working directory.
The article-builder reads the actual lesson blocks and result files, so the
article's numerical statements are not manually transcribed.

## Identifiers and income construction

| Quantity | PSID variables or rule |
| --- | --- |
| Individual's original-family identifier and person number | `ER30001`, `ER30002` |
| Recorded biological mother's two identifiers | `ER32009`, `ER32010` |
| Recorded biological father's two identifiers | `ER32016`, `ER32017` |
| Convenient unique individual ID | `id68 * 1000 + pn` |
| Interview-year family, sequence, relationship and birth year | Separate wave variables in the manifest; do not use annual interview ID as a permanent individual ID |
| Reference person's income | That wave's reference-person labor income, only if sequence=1 and relationship=10 |
| Spouse/partner's income | That wave's spouse/partner labor income, only if sequence=2 and relationship is 20 or 22 |

The SQL match uses the recorded parent's family identifier AND person number.
It does not infer biological relationships from sharing a household. Unknown or
never-observed parent numbers are not turned into invented parents. The parent
must have a matching individual record. Mothers and fathers are stacked with
`UNION ALL` and retain an explicit `parent_role`. The tutorial estimates maternal
and paternal slopes separately; it does not sum their incomes or call either
individual's income total family income.

Income observations are limited to current reference persons and spouses/partners
in responding families, because this extract does not contain other household
members' individual labor earnings. A family-level income field attached to a
child's row is never treated as that child's personal earnings unless their role
identifies them as the income's owner.

The 17 survey waves are 1994, 1995, 1996, 1997, and biennial 1999-2023. Each income
variable refers to the preceding calendar/tax year, not the interview year.
Use the latest valid birth year recorded in these waves, excluding 0/9999, and
calculate income-year age as `income_year - birth_year` (age attained that year).
Later reports can correct earlier birth-year reports; the preparation audit
records disagreements. Interview age is not simply reused as income-year age.

Amounts are labor income excluding farm and unincorporated business income, as
defined by each supplied codebook entry. Published imputations are retained;
the extract lacks the extra flags needed to separate every imputed component.
Zeros for eligible reference persons/spouses are retained when forming means.
Unobserved waves and ineligible roles do not become zero-income observations.

Special values are wave-specific. In 1994/1995 the 9,999,999 Latino-sample code
is excluded. In 1996 the documented valid upper amount is 9,999,998. The 1997
reference-person topcode 999,999 is retained, while that wave's spouse variable
has a documented maximum of 999,998. For 1999-2009, documented 9,999,999 topcodes
are retained. From 2011 onward the valid upper amount is 9,999,997. Negative
amounts are outside these selected labor-income variables' documented ranges.
Do not apply a blanket 'all nines are missing' rule across years. The separate
total-family-income fields can contain genuine losses and are not analyzed here.

Convert each observation before averaging:
`real_income = nominal_income * CPI_2020 / CPI_income_year`. Arithmetic means
of these real dollars are formed before taking logs.

## Design, actual results and interpretation

Income windows were chosen using observation coverage before inspecting slopes:
parent ages 35-44, child ages 20-29 and child ages 30-39, each requiring at least
three observed income years. Single observations are nearest ages 40, 25 and 35,
respectively; ties go to the earlier income year. A single observation need not
be exactly at the target age. Nonannual observations are not interpolated.

For each parent type, merge those three summaries, require all anchor/mean
incomes to be positive for logs, then keep children qualifying with BOTH parents.
This holds the same 606 children (birth years 1969-1988) constant across all eight
fits. Parent means contain 3-7 observed years, child twenties means 3-7, and child
thirties means 3-5. There are 424 mothers, 424 fathers and 362 original child
family identifiers in the final sample.

| Parent | Child age window | Single-year IGE | Multi-year IGE |
| --- | --- | ---: | ---: |
| Mother | 20-29 | 0.095 | 0.109 |
| Mother | 30-39 | 0.039 | 0.078 |
| Father | 20-29 | 0.055 | 0.274 |
| Father | 30-39 | 0.118 | 0.323 |

OLS includes an intercept. Confidence intervals are percentile intervals from
2,000 resamples of kinship clusters, seed 20261026. Clusters connect shared
individuals and original family lineages across both parent links; siblings and
related lineages stay together. There are 362 clusters, the largest with six
children. All specifications share the same resampled clusters, allowing paired
intervals for age differences. Paternal averaged later-minus-early IGE is 0.049
(95% interval [-0.021, 0.116]); maternal difference is -0.031 ([-0.081, 0.018]).

These are unweighted descriptive associations in a selected sample with both
parents observed, repeated reference-person/spouse roles and positive anchors.
They are not nationally representative, causal, or known lifetime elasticities.
Differences between maternal and paternal slopes are not a causal ranking of
parents' importance. Age comparisons also change calendar periods. The figure
shows timing/averaging sensitivity; the intervals do not establish a precise
age effect or identify how much of a difference is life-cycle bias.

The life-cycle explanation follows Haider and Solon (2006), *American Economic
Review* 96(4), 1308-1320, https://www.aeaweb.org/articles?id=10.1257/aer.96.4.1308 .
Their paper uses Health and Retirement Study-linked Social Security earnings;
this tutorial is not a replication of their sample or a claim to identify the
unavailable paper discussed in class. The equation shows that age-dependent
loading on lifetime income can change a measured IGE. Averaging parent income
can reduce temporary explanatory-variable noise, while averaging child income
smooths unusual years and can improve precision. Pure classical noise in the
dependent variable does not by itself cause attenuation. Averaging only young
adult years does not remove an age-dependent proxy problem.

## Verification and limits

See `results/validation.json` for completed checks. Source data access remains
required for independent replication; an anonymous visitor can inspect the code,
variable list, CPI, figure and aggregate results without downloading PSID records
from this repository. Local rendering was tested in an isolated copy of the
website. Publication to the user's live GitHub Pages site is a separate action.
