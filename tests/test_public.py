import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Polygon

from atlas.io import DataError
from atlas.public import VARIABLES, join_counties, normalize_fips, parse_acs, read_bulk_table, validate_public


def test_census_sentinels_and_ratio():
    rows = [
        ["NAME", "state", "county", *VARIABLES],
        ["Alameda County, California", "06", "001", "500000", "2000", "100000", "1000"],
        ["Alpine County, California", "06", "003", "-666666666", "-222222222", "0", "200"],
    ]
    df = parse_acs(rows, 2023)
    assert df.county_fips.tolist() == ["06001", "06003"]
    assert df.value_to_income.iloc[0] == 5
    assert pd.isna(df.value_to_income.iloc[1])
    assert df.period.iloc[0] == "2019–2023"
    validate_public(df, require_all_counties=False)
    with pytest.raises(DataError, match="58"):
        validate_public(df)
    duplicate = pd.concat([df, df])
    with pytest.raises(DataError, match="Duplicate"):
        validate_public(duplicate, require_all_counties=False)
    bad = df.copy()
    bad.loc[0, "value_to_income"] = 99
    with pytest.raises(DataError, match="ratios"):
        validate_public(bad, require_all_counties=False)


def test_fips_validation():
    assert normalize_fips(pd.Series([6001, "06003"])).tolist() == ["06001", "06003"]
    for bad in ["12001", "0600x", None]:
        with pytest.raises(DataError):
            normalize_fips(pd.Series([bad]))


def test_spatial_join_keeps_unmatched_and_checks_crs():
    polygon = Polygon([(-123, 36), (-121, 36), (-121, 38), (-123, 38)])
    boundaries = gpd.GeoDataFrame({"county_fips": ["06001"]}, geometry=[polygon], crs="EPSG:4326")
    records = pd.DataFrame({"Latitude": [37, 0, None], "Longitude": [-122, 0, -122]})
    joined = join_counties(records, boundaries.to_crs("EPSG:3857"))
    assert len(joined) == 3
    assert joined.county_fips.iloc[0] == "06001"
    assert joined.county_unmatched_flag.tolist() == [False, True, True]
    with pytest.raises(DataError, match="CRS"):
        join_counties(records, boundaries.set_crs(None, allow_override=True))
    overlap = gpd.GeoDataFrame(
        {"county_fips": ["06001", "06003"]}, geometry=[polygon, polygon], crs="EPSG:4326"
    )
    with pytest.raises(DataError, match="Ambiguous"):
        join_counties(records, overlap)


def test_bulk_invalid_contract(tmp_path):
    path = tmp_path / "bad.dat"
    path.write_text("GEO_ID|WRONG\n0500000US06001|1\n")
    with pytest.raises(DataError, match="Invalid bulk"):
        read_bulk_table(path, "B25077")


def test_bundled_public_snapshot():
    from pathlib import Path

    folder = Path(__file__).resolve().parents[1] / "data/public"
    if not (folder / "acs_counties.csv").exists():
        pytest.skip("Public snapshot has not been fetched")
    df = validate_public(pd.read_csv(folder / "acs_counties.csv", dtype={"county_fips": str}))
    boundaries = gpd.read_file(folder / "counties.geojson")
    assert len(boundaries) == 58
    assert boundaries.crs.to_epsg() == 4326
    assert set(df.county_fips) == set(boundaries.county_fips)
