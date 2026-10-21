"""Product interactions and statistical presentation contracts."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from atlas.dashboard import (
    METRICS,
    comparison_differences,
    county_from_selection,
    load_public,
    map_figure,
    number,
    relative_position,
)

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    folder = ROOT / "data/public"
    return load_public((folder / "acs_counties.csv").read_text(), (folder / "counties.geojson").read_text())


def test_county_rank_retains_ties_and_excludes_missing():
    frame = pd.DataFrame(
        {
            "county_fips": ["06001", "06003", "06005", "06007"],
            "median_home_value": [100, 100, 50, float("nan")],
        }
    )
    assert relative_position(frame, "06003", "median_home_value") == (1, 3)
    assert relative_position(frame, "06005", "median_home_value") == (3, 3)
    assert relative_position(frame, "06007", "median_home_value") is None
    assert number(float("nan"), "median_home_value") == "Unavailable"


def test_comparison_differences_match_published_estimates_and_keep_missing():
    data, _ = snapshot()
    focus = data[data.year.eq(2024)].set_index("county").loc[["Alameda", "Los Angeles"]].reset_index()
    diff = comparison_differences(focus).iloc[0]
    assert diff["county"] == "Los Angeles"
    assert diff.median_home_value == -255900
    assert diff.median_household_income == -39255
    assert diff.value_to_income == pytest.approx(0.830953834480628)
    focus.loc[focus.index[1], "median_home_value"] = float("nan")
    assert pd.isna(comparison_differences(focus).iloc[0].median_home_value)
    assert comparison_differences(focus.iloc[:1]).empty


def test_map_uses_fips_selection_and_preserves_missing_county_geometry():
    data, geo = snapshot()
    current = data[data.year.eq(2024)].copy()
    assert county_from_selection([{"location": "06001"}], current) == "Alameda"
    assert county_from_selection([{"location": "99999"}], current) is None
    assert county_from_selection([], current) is None
    current.loc[current.county_fips.eq("06001"), "median_home_value"] = float("nan")
    fig = map_figure(current, geo, "median_home_value", "06001")
    assert len(fig.data[0].locations) == 58  # Neutral base covers unavailable estimates.
    assert "06001" not in fig.data[1].locations
    assert list(fig.data[2].locations) == ["06001"]  # Focus outline survives missing metric.
    current.loc[:, "median_home_value"] = float("nan")
    fig = map_figure(current, geo, "median_home_value", "06001")
    assert len(fig.data) == 2  # All missing: neutral map and outline; no invented values.


def test_focus_persists_across_indicator_and_vintage_without_replacing_comparison():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.selectbox(key="atlas_county").select("San Diego").run()
    app.sidebar.selectbox(key="atlas_metric").select("value_to_income").run()
    app.sidebar.selectbox(key="atlas_year").select(2022).run()
    assert not app.exception and not app.error
    assert app.selectbox(key="atlas_county").value == "San Diego"
    assert app.metric[3].value == "$725,200"
    assert app.dataframe[0].value.county.tolist() == ["Alameda", "Los Angeles", "San Francisco"]
    app.sidebar.multiselect(key="atlas_compare").set_value([]).run()
    assert not app.exception and not app.error
    assert app.dataframe[0].value.empty
    assert any("Select two or three counties" in item.value for item in app.info)
    app.button[0].click().run()  # Explicit Add to comparison.
    assert not app.exception and not app.error
    assert app.dataframe[0].value.county.tolist() == ["San Diego"]
    assert app.selectbox(key="atlas_county").value == "San Diego"


def test_bundled_ratio_is_exactly_supported_by_two_estimates():
    data, _ = snapshot()
    assert len(data) == 174
    for field in METRICS:
        assert data[field].notna().all()
    expected = data.median_home_value / data.median_household_income
    assert (data.value_to_income - expected).abs().max() < 1e-12
