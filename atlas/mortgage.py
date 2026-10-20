from pathlib import Path

import numpy as np
import pandas as pd

from atlas.io import DataError, download

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"


def fetch_rates(target: Path) -> Path:
    return download(FRED_URL, target)


def monthly_rates(raw: pd.DataFrame) -> pd.DataFrame:
    date_col = next((c for c in ("observation_date", "DATE", "date") if c in raw), None)
    rate_col = next((c for c in ("MORTGAGE30US", "rate_30yr_fixed") if c in raw), None)
    if date_col is None or rate_col is None:
        raise DataError("FRED CSV needs DATE/observation_date and MORTGAGE30US columns")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(raw[date_col], errors="coerce", utc=True),
            "rate_30yr_fixed": pd.to_numeric(raw[rate_col], errors="coerce"),
        }
    )
    frame = frame.dropna().copy()
    if frame.date.duplicated().any():
        raise DataError("Duplicate FRED observation dates")
    frame = frame[np.isfinite(frame.rate_30yr_fixed) & frame.rate_30yr_fixed.gt(0)].copy()
    if frame.empty:
        raise DataError("No valid mortgage observations")
    frame["year_month"] = frame.date.dt.strftime("%Y-%m")
    return frame.groupby("year_month", as_index=False).agg(
        rate_30yr_fixed=("rate_30yr_fixed", "mean"), rate_observations=("rate_30yr_fixed", "size")
    )


def align_rates(records: pd.DataFrame, rates: pd.DataFrame) -> pd.DataFrame:
    if rates.year_month.isna().any() or rates.year_month.duplicated().any():
        raise DataError("Mortgage months must be unique and non-null")
    result = records.merge(rates, on="year_month", how="left", validate="many_to_one")
    result["mortgage_rate_missing_flag"] = result.rate_30yr_fixed.isna()
    return result
