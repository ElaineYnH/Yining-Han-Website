"""The complete lesson. Run from any directory with Python 3.11 or later.

The START/END markers let build_post.py insert the actual working code into
the article. Every printed estimate is also saved to a CSV.
"""
# START setup
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

ROOT = Path.cwd()  # Run the lesson cells from the downloaded post6 folder.
# END setup

# The command-line script also works when launched from the repository root.
if "__file__" in globals():
    ROOT = Path(__file__).resolve().parents[1]

# START load
con = sqlite3.connect(":memory:")
people = pd.read_csv(ROOT / "data/people.csv", dtype={"parent_id": "Int64"})
earnings = pd.read_csv(ROOT / "data/earnings.csv")
people.to_sql("people", con, index=False)
earnings.to_sql("earnings", con, index=False)
assert people.person_id.is_unique
assert not earnings.duplicated(["person_id", "year"]).any()
assert earnings.income.gt(0).all()
# END load

age_check = earnings.merge(people[["person_id", "birth_year"]],
                           on="person_id", validate="many_to_one")
assert (age_check["year"] - age_check.birth_year == age_check.age).all()

# START match
sample = pd.read_sql_query("""
SELECT c.family_id, c.person_id AS child_id,
       p.person_id AS parent_id
FROM people AS c
JOIN people AS p
  ON c.parent_id = p.person_id
 AND c.family_id = p.family_id
ORDER BY child_id
""", con)
assert len(sample) == sample.child_id.nunique() == 1000
# END match

expected = (people.loc[people.parent_id.notna(),
                       ["family_id", "person_id", "parent_id"]]
            .rename(columns={"person_id": "child_id"})
            .sort_values("child_id").reset_index(drop=True))
pd.testing.assert_frame_equal(sample, expected, check_dtype=False)
family_only_count = con.execute("""
SELECT COUNT(*) FROM people AS c
JOIN people AS p ON c.family_id = p.family_id
""").fetchone()[0]
assert family_only_count == 4 * len(sample)

# START aggregate
def mean_income(lo, hi):
    out = pd.read_sql_query("""
    SELECT person_id, AVG(income) AS income
    FROM earnings
    WHERE age BETWEEN ? AND ?
    GROUP BY person_id
    HAVING COUNT(*) = ?
    """, con, params=(lo, hi, hi - lo + 1))
    return out.set_index("person_id")["income"]
# END aggregate

# START attach
windows = {
    "p1": ("parent_id", 40, 40),
    "p5": ("parent_id", 40, 44),
    "c25": ("child_id", 25, 25),
    "c25_5": ("child_id", 25, 29),
    "c40": ("child_id", 40, 40),
    "c40_5": ("child_id", 40, 44),
}
for name, (person, lo, hi) in windows.items():
    sample[name] = sample[person].map(mean_income(lo, hi))
assert sample[list(windows)].notna().all().all()
# END attach

# Independently cross-check a SQL aggregation with pandas.
midlife = earnings.loc[earnings.age.between(40, 44)]
manual = midlife.groupby("person_id").income.mean().sort_index()
np.testing.assert_allclose(mean_income(40, 44).sort_index(), manual,
                           rtol=1e-12, atol=1e-8)

# START estimate
def ige(parent, child):
    # polyfit returns the slope and intercept of the log-log regression.
    return np.polyfit(np.log(parent), np.log(child), 1)[0]

cases = [
    ("Child age 25: one year", "p1", "c25"),
    ("Child ages 25-29: five-year mean", "p5", "c25_5"),
    ("Child age 40: one year", "p1", "c40"),
    ("Child ages 40-44: five-year mean", "p5", "c40_5"),
]
estimates = pd.DataFrame([
    {"measure": label, "ige": ige(sample[p], sample[c]), "n": len(sample)}
    for label, p, c in cases
])
print(estimates.round(3).to_string(index=False))
# END estimate

# A common income-level shift changes the intercept, not the slope. The
# simulated life-cycle effect comes from different income growth by type.
assert abs(ige(sample.p1, sample.c40 * np.exp(-0.6)) -
           ige(sample.p1, sample.c40)) < 1e-12

import json
import platform
import sys

out = ROOT / "results"
out.mkdir(parents=True, exist_ok=True)
sample.to_csv(out / "matched_incomes.csv", index=False, float_format="%.12g")
estimates.to_csv(out / "ige_estimates.csv", index=False, float_format="%.12g")
sample[["family_id", "child_id", "parent_id"]].head(3).to_csv(
    out / "match_preview.csv", index=False)
(out / "validation.json").write_text(json.dumps({
    "people": len(people), "person_years": len(earnings),
    "matched_pairs": len(sample), "unique_children": sample.child_id.nunique(),
    "family_only_join_rows": family_only_count,
    "same_pairs_in_all_four_estimates": True,
    "duplicate_person_years": 0, "missing_income_measures": 0,
    "nonpositive_annual_incomes": 0,
    "sql_parent_child_links_match_input": True,
    "sql_mean_matches_independent_pandas_check": True,
    "common_income_level_shift_preserves_slope": True,
}, indent=2) + "\n", encoding="utf-8")
(out / "sessionInfo.txt").write_text(
    f"Python: {sys.version}\nPlatform: {platform.system()}\n"
    f"NumPy: {np.__version__}\npandas: {pd.__version__}\n"
    f"SQLite: {sqlite3.sqlite_version}\n", encoding="utf-8")
con.close()
