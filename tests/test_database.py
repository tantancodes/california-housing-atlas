import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from atlas.database import load_public, read_public


def test_postgres_matches_validated_csv(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test database")
    monkeypatch.setenv("DATABASE_URL", url)
    path = Path(__file__).resolve().parents[1] / "data/public/acs_counties.csv"
    source = pd.read_csv(path, dtype={"county_fips": str}).sort_values(["year", "county_fips"])
    first = load_public(path)
    second = load_public(path)
    assert first == second
    assert first["loaded_rows"] == len(source)
    result = read_public()
    assert len(result) == len(source)
    assert np.allclose(result.value_to_income, source.value_to_income, equal_nan=True)
    assert result.county_fips.tolist() == source.county_fips.tolist()
