"""Census ACS five-year estimates; housing values are not transaction prices."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from atlas.io import DataError, download, provenance

BOUNDARY_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip"
VARIABLES = {
    "B25077_001E": "median_home_value",
    "B25077_001M": "home_value_moe",
    "B19013_001E": "median_household_income",
    "B19013_001M": "income_moe",
}


def normalize_fips(values: pd.Series) -> pd.Series:
    codes = values.astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)
    if not codes.str.fullmatch(r"06\d{3}").fillna(False).all():
        raise DataError("Expected five-digit California county FIPS codes")
    return codes


def parse_acs(payload: list[list[str]], year: int) -> pd.DataFrame:
    if not isinstance(payload, list) or len(payload) < 2:
        raise DataError("Empty or unexpected ACS JSON response")
    frame = pd.DataFrame(payload[1:], columns=payload[0])
    required = {"NAME", "state", "county", *VARIABLES}
    if not required <= set(frame):
        raise DataError(f"ACS response missing {sorted(required - set(frame))}")
    if not frame.state.eq("06").all():
        raise DataError("ACS response includes a non-California state")
    frame["county_fips"] = normalize_fips(frame.state + frame.county)
    if frame.county_fips.duplicated().any():
        raise DataError("Duplicate ACS county estimates")
    frame["county"] = frame.NAME.str.replace(", California", "", regex=False).str.replace(
        " County", "", regex=False
    )
    frame["year"] = int(year)
    for variable, name in VARIABLES.items():
        numeric = pd.to_numeric(frame[variable], errors="coerce")
        frame[name] = numeric.where(np.isfinite(numeric) & numeric.ge(0))
        # Census negative sentinels include suppressed, unavailable and top-coded estimates.
        frame[f"{name}_unavailable"] = frame[name].isna()
    frame["median_home_value"] = frame.median_home_value.where(frame.median_home_value.gt(0))
    frame["median_household_income"] = frame.median_household_income.where(
        frame.median_household_income.gt(0)
    )
    frame["value_to_income"] = frame.median_home_value / frame.median_household_income
    frame["period"] = f"{year - 4}–{year}"
    return frame[["county_fips", "county", "year", "period", *VARIABLES.values(), "value_to_income"]]


def validate_public(frame: pd.DataFrame, require_all_counties: bool = True) -> pd.DataFrame:
    required = {"county_fips", "county", "year", "period", *VARIABLES.values(), "value_to_income"}
    if missing := required - set(frame):
        raise DataError(f"Public data missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["county_fips"] = normalize_fips(frame.county_fips)
    if frame.duplicated(["county_fips", "year"]).any():
        raise DataError("Duplicate public county-year keys")
    if require_all_counties and not frame.groupby("year").county_fips.nunique().eq(58).all():
        raise DataError("Each ACS vintage must cover all 58 California counties")
    for field in VARIABLES.values():
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
        if (frame[field].dropna() < 0).any() or np.isinf(frame[field]).any():
            raise DataError(f"Invalid public estimate: {field}")
    if (frame.median_household_income.dropna() <= 0).any() or (frame.median_home_value.dropna() <= 0).any():
        raise DataError("Estimate denominators and values must be positive")
    expected = frame.median_home_value / frame.median_household_income
    if not np.allclose(frame.value_to_income, expected, equal_nan=True):
        raise DataError("Inconsistent value-to-income ratios")
    return frame


def read_bulk_table(path: Path, table: str) -> pd.DataFrame:
    required = ["GEO_ID", f"{table}_E001", f"{table}_M001"]
    try:
        chunks = pd.read_csv(path, sep="|", dtype=str, usecols=required, chunksize=100_000)
        frames = [chunk[chunk.GEO_ID.str.fullmatch(r"0500000US06\d{3}", na=False)] for chunk in chunks]
        frame = pd.concat(frames, ignore_index=True)
    except (ValueError, pd.errors.ParserError) as exc:
        raise DataError(f"Invalid bulk ACS table {path.name}: {exc}") from exc
    if len(frame) != 58 or frame.GEO_ID.duplicated().any():
        raise DataError(f"Expected 58 unique California counties in {path.name}")
    return frame.rename(columns={f"{table}_E001": f"{table}_001E", f"{table}_M001": f"{table}_001M"})


def fetch_public(years: list[int], output: Path, source: str = "bulk") -> None:
    if not years or any(y < 2022 or y > 2024 for y in years):
        raise DataError("Supported public vintages: 2022, 2023, 2024 (ACS table-based summary files)")
    if source != "bulk":
        raise DataError("Only official credential-free Census bulk files are supported")
    cache = output.parent / "cache"
    paths, urls, frames = [], [], []
    archive = download(BOUNDARY_URL, cache / "county_boundaries.zip")
    boundaries = gpd.read_file(archive)
    if boundaries.crs is None:
        raise DataError("County boundary dataset has no CRS")
    boundaries = boundaries[boundaries.STATEFP.eq("06")].to_crs("EPSG:4326")
    if len(boundaries) != 58 or not boundaries.geometry.is_valid.all():
        raise DataError("Expected 58 valid California county polygons")
    boundaries = boundaries.rename(columns={"GEOID": "county_fips", "NAME": "county"})[
        ["county_fips", "county", "geometry"]
    ]
    names = boundaries.set_index("county_fips").county
    for year in sorted(set(years)):
        tables = []
        for table in ["B19013", "B25077"]:
            url = (
                f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/"
                f"table-based-SF/data/5YRData/acsdt5y{year}-{table.lower()}.dat"
            )
            path = download(url, cache / f"acsdt5y{year}-{table.lower()}.dat")
            tables.append(read_bulk_table(path, table))
            paths.append(path)
            urls.append(url)
        merged = tables[0].merge(tables[1], on="GEO_ID", validate="one_to_one")
        merged["state"] = "06"
        merged["county"] = merged.GEO_ID.str[-3:]
        merged["NAME"] = merged.GEO_ID.str[-5:].map(names) + " County, California"
        if merged.NAME.isna().any():
            raise DataError("Unrecognized county FIPS in bulk ACS file")
        frames.append(parse_acs([merged.columns.tolist(), *merged.values.tolist()], year))
    data = validate_public(pd.concat(frames, ignore_index=True))
    if set(boundaries.county_fips) != set(data.county_fips):
        raise DataError("ACS and boundary county FIPS sets differ")
    output.mkdir(parents=True, exist_ok=True)
    data.to_csv(output / "acs_counties.csv", index=False)
    boundaries.to_file(output / "counties.geojson", driver="GeoJSON")
    paths.extend([archive, output / "acs_counties.csv", output / "counties.geojson"])
    urls.append(BOUNDARY_URL)
    provenance(paths, urls, output / "provenance.json")
    pd.DataFrame({"field": data.columns, "missing_count": data.isna().sum().values}).to_csv(
        output / "quality.csv", index=False
    )


def join_counties(records: pd.DataFrame, boundaries: gpd.GeoDataFrame) -> pd.DataFrame:
    """Assign points with strict within; ambiguous polygon matches fail rather than duplicate rows."""
    if boundaries.crs is None:
        raise DataError("County polygons must declare a CRS")
    if boundaries.county_fips.duplicated().any() or not boundaries.geometry.is_valid.all():
        raise DataError("County polygons must have unique FIPS and valid geometries")
    result = records.reset_index(drop=True).copy()
    lat = pd.to_numeric(result.Latitude, errors="coerce")
    lon = pd.to_numeric(result.Longitude, errors="coerce")
    valid = lat.between(-90, 90) & lon.between(-180, 180)
    points = gpd.GeoDataFrame(
        result.loc[valid, ["Latitude", "Longitude"]],
        geometry=gpd.points_from_xy(lon[valid], lat[valid]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        points, boundaries[["county_fips", "geometry"]].to_crs("EPSG:4326"), how="left", predicate="within"
    )
    if joined.index.duplicated().any():
        raise DataError("Ambiguous county polygon matches; inspect overlapping geometry")
    result["county_fips"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result.loc[joined.index, "county_fips"] = joined.county_fips.astype("string")
    result["county_unmatched_flag"] = result.county_fips.isna()
    return result
