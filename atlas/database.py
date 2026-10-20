"""Optional PostgreSQL adapter. The public dashboard also works without a service."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd

from atlas.io import DataError
from atlas.public import validate_public

ROOT = Path(__file__).resolve().parents[1]


def load_public(path: Path) -> dict[str, int]:
    import psycopg

    url = os.getenv("DATABASE_URL")
    if not url:
        raise DataError("Set DATABASE_URL before loading PostgreSQL")
    frame = validate_public(pd.read_csv(path, dtype={"county_fips": str}))
    columns = [
        "county_fips",
        "county",
        "year",
        "period",
        "median_home_value",
        "home_value_moe",
        "median_household_income",
        "income_moe",
    ]
    rows = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in frame[columns].itertuples(index=False, name=None)
    ]
    try:
        with psycopg.connect(url, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(2481501)")
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS atlas_migrations "
                    "(version text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz DEFAULT now())"
                )
                for migration in sorted((ROOT / "sql/migrations").glob("*.sql")):
                    digest = hashlib.sha256(migration.read_bytes()).hexdigest()
                    cursor.execute("SELECT sha256 FROM atlas_migrations WHERE version=%s", (migration.name,))
                    existing = cursor.fetchone()
                    if existing and existing[0] != digest:
                        raise DataError(f"Applied migration changed: {migration.name}")
                    if not existing:
                        cursor.execute(migration.read_text())
                        cursor.execute(
                            "INSERT INTO atlas_migrations (version, sha256) VALUES (%s,%s)",
                            (migration.name, digest),
                        )
                cursor.executemany(
                    """
                    INSERT INTO county_estimates
                    (county_fips, county, year, period, median_home_value, home_value_moe,
                     median_household_income, income_moe) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (county_fips, year) DO UPDATE SET
                    county=excluded.county, period=excluded.period, median_home_value=excluded.median_home_value,
                    home_value_moe=excluded.home_value_moe, median_household_income=excluded.median_household_income,
                    income_moe=excluded.income_moe
                """,
                    rows,
                )
                cursor.execute("SELECT count(*) FROM county_affordability")
                stored = cursor.fetchone()[0]
    except psycopg.Error as exc:
        # Avoid echoing DSN/password-containing connection messages.
        raise DataError(
            f"PostgreSQL operation failed ({type(exc).__name__}); check service, credentials and schema"
        ) from None
    return {"loaded_rows": len(rows), "stored_rows": stored}


def read_public() -> pd.DataFrame:
    import psycopg

    url = os.getenv("DATABASE_URL")
    if not url:
        raise DataError("Set DATABASE_URL to read PostgreSQL")
    try:
        with psycopg.connect(url, connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT county_fips, county, year, period, median_home_value, home_value_moe, "
                    "median_household_income, income_moe, value_to_income "
                    "FROM county_affordability ORDER BY year, county_fips"
                )
                columns = [description.name for description in cursor.description]
                frame = pd.DataFrame(cursor.fetchall(), columns=columns)
    except psycopg.Error as exc:
        raise DataError(
            f"PostgreSQL read failed ({type(exc).__name__}); check the service and run migrations"
        ) from None
    # PostgreSQL NUMERIC uses Decimal; normalize at the analytical boundary.
    frame["value_to_income"] = pd.to_numeric(frame.value_to_income)
    return validate_public(frame)
