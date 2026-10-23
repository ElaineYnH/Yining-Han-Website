# Blog 2 revision: remote-work signals in Python.org advertisements

This post asks whether a single remote-work field provides a dependable job-search
shortlist. It compares a remote-work mention in the title/location with the
separate telecommuting field on each advertisement's detail page. It studies
advertised statements, not actual employer eligibility or the whole labor market.

## Put this revision on the website

Replace only `blog/posts/post2/` in the existing website project with this `post2`
folder. Keep the article filename `blog2.qmd`. Commit and push all files in this
folder. There is no need to run R first: the figure, data, and generated article
are already included. The `.qmd` has no executable code chunks.

The existing GitHub Actions workflow can render the saved results. No changes to
the website configuration, blog index, or deployment workflow are required.

Published article URL after deployment:
<https://elaineynh.github.io/Yining-Han-Website/blog/posts/post2/blog2.html>

Repository:
<https://github.com/ElaineYnH/Yining-Han-Website>

Source folder:
<https://github.com/ElaineYnH/Yining-Han-Website/tree/main/blog/posts/post2>

This package has not been pushed or deployed by the assistant.

## Files

- `blog2.qmd`: generated article; original publication date retained, revision dated 2026-10-23.
- `code/scrape.R`: explicit, low-frequency network refresh with `rvest` and `httr2`.
- `code/parse.R`: shared HTML extraction, field validation, and duplicate handling.
- `code/analyze.R`: offline parsing, analysis, chart, case table, review queue, and article generation.
- `code/article_template.txt`: editable article prose with programmatically filled results.
- `data/raw/index_01.html`: factual listing-card HTML extracted from the source index.
- `data/raw/details/`: the original Restrictions heading/list fragments for retained entries.
- `data/raw/robots.txt`: the robots policy inspected during the saved refresh.
- `data/manifest.json`: source URLs, per-request UTC timestamps, and collection details.
- `data/listing_snapshot.csv`: extracted listing fields, role keys, and duplicate decisions.
- `results/roles_classified.csv`: retained entries and derived signals.
- `results/signal_counts.csv` and `results/summary.json`: numerical results.
- `results/review_queue.csv`: discovery candidates with the next verification step.
- `results/cases.txt`: the programmatically generated example table.
- `results/figures/remote_signals.png`: the published figure.
- `results/sessionInfo.txt`: the R environment used for the saved analysis.
- `RUBRIC_CHECK.txt`: evidence for the ten grading criteria and validation scope.

## Reproduce the saved snapshot offline

Install R and the following packages if needed:

```r
install.packages(c("rvest", "httr2", "jsonlite"))
```

From the website repository root, run:

```bash
Rscript blog/posts/post2/code/analyze.R
```

The script resolves paths relative to itself, so calling it by an absolute path
from another working directory also works. It reads only the saved local HTML
and manifest. It writes the CSV/JSON results, figure, case table, and `blog2.qmd`.
It makes no network requests. Edit `code/article_template.txt`, then rerun
`analyze.R` to update the article; direct edits to the generated `.qmd` will be
overwritten on regeneration.

The saved run used R 4.3.3, rvest 1.0.3, httr2 1.0.0, jsonlite 1.8.8, and xml2
1.3.6. Full dependencies are listed in `results/sessionInfo.txt`.

Optional Quarto checks from the website root:

```bash
quarto render blog/posts/post2/blog2.qmd
quarto render blog/index.qmd
```

## Refresh the live data separately

Only refresh deliberately; each refresh visits the live site again:

```bash
Rscript blog/posts/post2/code/scrape.R --refresh
Rscript blog/posts/post2/code/analyze.R
```

The snapshot was collected on **2026-10-23 UTC**, from 00:15:39 to 00:16:08 UTC.
It contains 19 posting cards and 17 retained employer-title combinations from
15 employers. The run made 19 sequential requests: robots.txt, one listing
page, and 17 detail pages, with a 1.5-second pause before every request.

Sources:

- Board: <https://www.python.org/jobs/>
- Policy: <https://www.python.org/robots.txt>
- Every retained detail URL is in `results/roles_classified.csv`.

The scraper uses a descriptive user agent and checks the general robots rules.
The saved policy does not disallow `/jobs/`. It stops on access errors or
unrecognized page structure. It does not bypass logins, CAPTCHAs, paywalls, or
other controls, and does not visit employer application pages. A future robots
policy or schema change requires review.

The stored HTML consists of extracted factual cards and Restrictions fields;
whole pages, full job descriptions, personal contact names, and email addresses
are not republished. The fragments preserve the source field markup and allow
the extraction and classification steps to be rerun offline.

Live advertisements can change or disappear. The saved snapshot, rather than a
future scrape, reproduces the published numbers. A refresh also requires
editorial review of the article's examples and interpretation; it is not a
promise that the same conclusions will hold. The script stops if the example
telecommuting fields change.

## Definitions and cleaning

1. Read every visible posting card, recording title, employer, location, date,
   job types, ID, and URL. Remove repeated IDs if pagination repeats a card.
2. Normalize whitespace and company/title case for duplicate keys. For identical
   company-title keys, retain the newest visible posting; ID breaks a date tie.
   The three Evaboot entries become one. This is a transparent counting unit,
   not proof that distinct ads were the same underlying vacancy.
3. Read the retained detail pages' Restrictions list. Require exactly one
   literal telecommuting field: `Telecommuting is OK` or `No telecommuting`.
4. A remote-text signal means the **title or location only** matches the words
   remote, telecommuting, or work from home. Full descriptions are not searched
   for this measure. A missing short-field mention is not evidence of on-site work.
5. Classify the overlap of the two signals. An explicit conflict is remote text
   paired with `No telecommuting` (six entries). A positive flag with no remote
   text (two entries) adds information; it is not an explicit contradiction.
6. Put either-signal entries in the discovery queue. Flag only the six explicit
   conflicts for clarification; country, hours, and engagement eligibility must
   still be checked for every candidate.

Main results: 11 remote-text entries; seven positive flags; five in both groups;
six text/negative-flag conflicts; two positive-flag/no-text entries; four with
neither positive signal. The union contains 13 advertisements to investigate,
not 13 verified remote opportunities.

The CSV preserves misspellings and repeated location wording where these appear
in the source. The article's example table shortens repeated geographic labels
without changing the stated condition. Dates on retained ads range from
2026-07-24 to 2026-10-20. The board is small and self-selected; no industry-wide
percentages, causal claims, or guarantees of current hiring are inferred.
