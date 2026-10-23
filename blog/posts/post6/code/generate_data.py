"""Create a reproducible, explicitly simulated longitudinal teaching panel.

There is one linked parent and one adult child per origin family. These are
not survey records or estimates of the U.S. income distribution.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd


def generate(root: Path) -> None:
    seed, n, beta = 20261023, 1000, 0.5
    rng = np.random.default_rng(seed)
    parent_status = rng.normal(0, 0.65, n)
    child_status = beta * parent_status + rng.normal(0, 0.40, n)
    people, earnings = [], []

    for j in range(n):
        family = j + 1
        parent_id, child_id = 10000 + family, 20000 + family
        people.extend([
            (parent_id, family, 1950, None),
            (child_id, family, 1980, parent_id),
        ])
        # All values are in constant teaching dollars; no deflation is needed.
        # Independent annual log shocks create transitory income variation.
        for age in range(40, 45):
            log_income = 10.6 + parent_status[j] + rng.normal(0, 0.50)
            earnings.append((parent_id, 1950 + age, age,
                             round(float(np.exp(log_income)), 2)))
        for age in list(range(25, 30)) + list(range(40, 45)):
            # Different long-run types have different career growth: early
            # income gaps are compressed, not simply shifted down equally.
            loading, age_level = (0.5, -0.6) if age < 30 else (1.0, 0.0)
            log_income = (10.8 + age_level + loading * child_status[j]
                          + rng.normal(0, 0.50))
            earnings.append((child_id, 1980 + age, age,
                             round(float(np.exp(log_income)), 2)))

    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    persons = pd.DataFrame(people, columns=[
        "person_id", "family_id", "birth_year", "parent_id"])
    persons["parent_id"] = persons["parent_id"].astype("Int64")
    persons.to_csv(data / "people.csv", index=False)
    pd.DataFrame(earnings, columns=["person_id", "year", "age", "income"]).to_csv(
        data / "earnings.csv", index=False)
    metadata = {
        "source_kind": "simulated teaching data; not survey observations",
        "created_for": "AEDS 6400 Blog Post 6 tutorial",
        "created_on": "2026-10-23",
        "seed": seed,
        "families": n,
        "people": 2 * n,
        "person_years": 15 * n,
        "model_ige": beta,
        "finite_sample_latent_log_slope": float(np.polyfit(
            parent_status, child_status, 1)[0]),
        "parent_log_status_sd": 0.65,
        "child_log_status_residual_sd": 0.40,
        "annual_log_shock_sd": 0.50,
        "parent_birth_year": 1950,
        "child_birth_year": 1980,
        "parent_ages": [40, 41, 42, 43, 44],
        "child_ages": [25, 26, 27, 28, 29, 40, 41, 42, 43, 44],
        "child_status_loading_ages_25_29": 0.5,
        "child_status_loading_ages_40_44": 1.0,
        "price_units": "constant teaching dollars (simulated)",
        "missing_and_zero_incomes": "none, by construction",
        "family_id_definition": "stable origin-family identifier, not a current household ID",
        "parent_id_definition": "explicit link to the one designated parent's person_id",
        "annual_shocks": "independent across people and years",
        "scope": "illustration of SQL matching and measurement choices, not a calibrated economic model",
    }
    (data / "simulation.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {2*n:,} people and {15*n:,} person-years (seed {seed}).")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1])
