# Data sources and definitions

The four CSV files in `raw` were downloaded programmatically from FRED on October 4, 2026. They contain observations from January 1, 2019 through December 31, 2025. The full download URLs and SHA-256 hashes are in `sources.json`. Run `python blog/posts/post4/code/analyze.py --refresh` from the website root to retrieve current versions of the same series.

## Original data

| FRED ID | Original publisher | Series and units | Frequency / adjustment |
|---|---|---|---|
| [MSPUS](https://fred.stlouisfed.org/series/MSPUS) | U.S. Census Bureau and U.S. Department of Housing and Urban Development | Median Sales Price of New Houses Sold for the United States; dollars | Quarterly; not seasonally adjusted |
| [MORTGAGE30US](https://fred.stlouisfed.org/series/MORTGAGE30US) | Freddie Mac | 30-Year Fixed Rate Mortgage Average in the United States; percent | Weekly; not seasonally adjusted |
| [CPIAUCSL](https://fred.stlouisfed.org/series/CPIAUCSL) | U.S. Bureau of Labor Statistics | Consumer Price Index for All Urban Consumers: All Items in U.S. City Average; 1982–1984 = 100 | Monthly; seasonally adjusted |
| [CES0500000003](https://fred.stlouisfed.org/series/CES0500000003) | U.S. Bureau of Labor Statistics | Average Hourly Earnings of All Employees, Total Private; dollars per hour | Monthly; seasonally adjusted |

The CSV header `observation_date` supplies dates; the second column is named with the FRED series ID. FRED represents missing values as `.`. October 2025 CPIAUCSL is missing, consistent with the [BLS explanation of the 2025 government shutdown](https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm). The raw download preserves this missing value. The analysis uses the fixed 2019 Q1–2025 Q3 window, the last complete quarter within 2025, and checks for missing values in that window. No missing values are interpolated and no quarterly CPI mean is formed from an incomplete set of months.

MSPUS concerns new houses sold. It is a transaction median, not a constant-quality house-price index or an existing-home median. The makeup of houses sold can influence changes in the median. Its quarter date marks the quarter, not an individual sale date.

MORTGAGE30US is a benchmark rate for new 30-year fixed borrowing. Freddie Mac changed the Primary Mortgage Market Survey methodology on November 17, 2022, moving to loan-application data. Source note: [Freddie Mac methodology](https://www.freddiemac.com/research/insight/20221103-freddie-macs-newly-enhanced-mortgage-rate-survey). Copyright Freddie Mac. FRED identifies this series as copyrighted data requiring a source citation; Freddie Mac is attributed here and in the article. The three government series are public-domain data; source citations are supplied here and in the article.

CES0500000003 is a gross hourly-earnings average for the private-sector workforce in each month, including overtime and shift premiums. It excludes benefits. Changes can reflect workforce composition as well as changes in an individual's earnings. It does not measure median earnings or household income.

## Quarterly processing

1. Restrict the downloaded dates to January 2019–September 2025 and validate unique, nonmissing observations in this analysis window.
2. Keep the one published MSPUS observation in each quarter.
3. Compute simple arithmetic means of the three monthly CPI and earnings observations within each calendar quarter.
4. Compute the arithmetic mean of all weekly mortgage observations dated in each quarter. These are observation-weighted quarterly means, not a daily average or a loan-volume-weighted rate.
5. Join by quarter and require all four series in all 27 analysis quarters. All four series are truncated at the same 2025 Q3 endpoint. The unused 2025 Q4 observations remain in the raw downloads for transparency.

The original seasonal adjustment status is retained. The code does not apply a new seasonal adjustment. Short quarterly price movements may include seasonality or changing transaction composition.

## Result-column dictionary

The output is `results/housing_quarterly.csv`:

| Column | Definition |
|---|---|
| `quarter` | Calendar quarter, from 2019Q1 through 2025Q3 |
| `price_usd` | Published quarterly median new-home sale price |
| `mortgage_rate_pct` | Quarterly mean of weekly annual mortgage percentages |
| `cpi` | Quarterly mean of monthly CPIAUCSL |
| `hourly_earnings_usd` | Quarterly mean of monthly private-sector hourly earnings |
| `n_MSPUS` | Number of published price observations in the quarter; 1 |
| `n_MORTGAGE30US` | Number of weekly mortgage observations in the quarter |
| `n_CPIAUCSL` | Number of monthly CPI observations in the quarter; 3 |
| `n_CES0500000003` | Number of monthly earnings observations in the quarter; 3 |
| `real_price_index` | `100 * (price_usd / cpi) / (2019Q1 price_usd / 2019Q1 cpi)` |
| `real_earnings_index` | `100 * (hourly_earnings_usd / cpi) / (2019Q1 hourly_earnings_usd / 2019Q1 cpi)` |
| `loan_usd` | `0.8 * price_usd`, assuming a 20% down payment |
| `payment_usd` | Hypothetical monthly principal-and-interest payment on `loan_usd`, using a 360-month term and the quarter's mean rate |
| `fixed_rate_payment_usd` | Same calculation, holding the rate at its 2019Q1 value |
| `payment_hours` | `payment_usd / hourly_earnings_usd` |
| `fixed_rate_hours` | `fixed_rate_payment_usd / hourly_earnings_usd` |

Payments computed at the quarterly average rate are illustrative; they are not the observed mean payment on loans originated during the quarter. The ratio of payment to average hourly earnings is a benchmark work-hours measure, not a measured household payment-to-income ratio.

Both the payment and the earnings denominator are nominal in the same quarter. Deflating both by the same CPI leaves their ratio unchanged. The fixed-rate comparison is an accounting counterfactual that leaves observed prices and earnings unchanged; it does not model an alternative equilibrium.
