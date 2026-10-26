# Blog 7: rubric evidence and verification

This records evidence against the official six common criteria and four Plotly criteria. It does not predict a grade.

| Criterion | Evidence in this package |
| --- | --- |
| 1. Question and motivation | The opening asks which daily expenses became cheaper and whether the comparison date changes the answer. |
| 2. Clear explanation | The article explains the two views, baseline controls, index meaning, and formulas in plain language. |
| 3. Interpretation and takeaway | The discussion distinguishes slower inflation from lower prices and quantifies how the gasoline conclusion changes with the baseline. |
| 4. Data and presentation | Four individual FRED/BLS sources are identified. The period, seasonal adjustment, units, and missing observations are documented. A labeled interactive chart and compact endpoint table present the evidence. |
| 5. Repository organization | `code/`, `data/`, `results/`, and `assets/` have documented roles. `README.md` gives publishing and replication steps. |
| 6. Reproducibility and coding | The standard-library Python builder reads the preserved CSV and generates the results, numerical article fields, chart data, and thumbnail. The raw file's SHA-256 checksum is retained. |
| 7. Substantive Plotly visualization | Plotly.js charts monthly changes in actual consumer price indexes to answer the article's question. |
| 8. Working and usable interaction | Browser checks cover the measure toggle, baseline shortcuts and selector, category controls, updated cards, hover labels, offline use, and a narrow mobile display. |
| 9. Value beyond one static graph | Rebasing changes the actual calculated series, including the sign of gasoline's endpoint change. The annual view reveals fluctuations hidden by two endpoints, and category filters support focused comparisons. |
| 10. Discussion of revealed patterns | The article interprets grocery and rent increases under both baselines, the gasoline sign reversal, and the distinction between current annual inflation and accumulated price changes. |

## Checks actually performed

- The input CSV is byte-identical to the uploaded `fredgraph.csv`.
- The analysis preserves 93 monthly dates from January 2019 to September 2026 and contains 372 category-month rows. The three missing October 2025 observations remain absent; observed gasoline is retained.
- Twelve endpoint calculations were independently checked with decimal arithmetic against the original indexes.
- The Python builder executed successfully. The article contains no unresolved numerical template fields.
- Quarto 1.10.19 rendered the article and blog listing using the existing website's public `_quarto.yml`, stylesheet, and listing configuration. The listing contains one Blog 7 entry.
- Chromium 151.0.7922.34 exercised eight sets of interactive checks, including offline loading, both comparison views, arbitrary baselines, category selection, data gaps, and rendered hover values.
- Desktop and mobile screenshots were visually reviewed. At a 390px outer viewport, the embedded chart resizes to its full content height and the article has no horizontal page overflow.
- Local HTTP checks returned 200 for the article's standalone chart, README, Python builder, original CSV, and results CSV links. The standalone-chart link opens in a separate tab.

The article is about 690 words including headings and replication links, excluding its table and embedded HTML code.

## Scope of verification

Only this new article and its listing integration were rendered. The full collection of previous posts was not rebuilt or re-executed. Publishing to the user's GitHub repository and the resulting live GitHub Pages deployment have not been performed. The article date is explicitly October 27, 2026; the current assignment deadline has not been independently confirmed.
