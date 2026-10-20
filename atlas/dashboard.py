"""Public-data product view. County-year estimates never masquerade as home sales."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from atlas.public import validate_public

LABELS = {
    "median_home_value": "Median owner-occupied home value (USD)",
    "median_household_income": "Median household income (USD/year)",
    "value_to_income": "Home value / household income (×)",
    "year": "ACS ending year",
    "county": "County",
}


@st.cache_data
def load_public(csv_text: str, geojson_text: str) -> tuple[pd.DataFrame, dict]:
    from io import StringIO

    data = validate_public(pd.read_csv(StringIO(csv_text), dtype={"county_fips": str}))
    return data, json.loads(geojson_text)


def public_view(root: Path) -> None:
    folder = root / "data/public"
    st.subheader("California county affordability explorer")
    st.caption("Public Census ACS estimates · all 58 counties · no private MLS feed")
    if not (folder / "acs_counties.csv").exists():
        st.info("Download the reproducible public dataset: python -m atlas.cli public")
        return
    data, geo = load_public(
        (folder / "acs_counties.csv").read_text(), (folder / "counties.geojson").read_text()
    )
    if os.getenv("ATLAS_PUBLIC_BACKEND") == "postgres":
        from atlas.database import read_public

        data = read_public()
    years = sorted(data.year.unique())
    year = st.sidebar.selectbox("ACS ending year", years, index=len(years) - 1)
    selected = st.sidebar.multiselect(
        "Compare counties",
        sorted(data.county.unique()),
        default=[c for c in ["Alameda", "Los Angeles", "San Francisco"] if c in set(data.county)],
    )
    metric = st.sidebar.selectbox("Map indicator", list(LABELS)[:3], format_func=LABELS.get)
    current = data[data.year.eq(year)].copy()
    st.info(
        f"{year - 4}–{year} five-year estimates. Home values describe owner-occupied housing, not listing or "
        "sale prices. The value-to-income ratio compares two county medians from different populations; "
        "it is a descriptive indicator, not a household mortgage affordability calculation."
    )
    a, b, c = st.columns(3)
    a.metric("Counties", str(len(current)))
    b.metric("County median home value", f"${current.median_home_value.median():,.0f}")
    c.metric("Median county value/income", f"{current.value_to_income.median():.1f}×")
    st.caption("Overview metrics are unweighted medians across counties, not California statewide medians.")
    map_fig = px.choropleth(
        current,
        geojson=geo,
        locations="county_fips",
        featureidkey="properties.county_fips",
        color=metric,
        hover_name="county",
        color_continuous_scale="Viridis",
        labels=LABELS,
        hover_data={"county_fips": False, "home_value_moe": ":,.0f", "income_moe": ":,.0f"},
    )
    map_fig.update_geos(fitbounds="locations", visible=False)
    map_fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=510, clickmode="event+select")
    event = st.plotly_chart(
        map_fig,
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        key=f"county_map_{year}_{metric}",
    )
    clicked = [p.get("location") for p in event.selection.points if p.get("location")]
    # Map selection takes precedence; sidebar comparison remains useful on keyboard/mobile.
    focus = current[current.county_fips.isin(clicked)] if clicked else current[current.county.isin(selected)]
    if focus.empty:
        focus = current
    st.caption(
        "Select counties on the map to update linked charts, or use the keyboard-accessible county selector."
    )
    focus_names = focus.county.tolist()
    st.subheader("County comparisons")
    st.plotly_chart(
        px.bar(
            focus.sort_values(metric),
            x="county",
            y=metric,
            labels=LABELS,
            color="county",
            color_discrete_sequence=px.colors.qualitative.Safe,
        ),
        width="stretch",
    )
    history = data[data.county.isin(focus_names)]
    if len(years) > 1:
        st.subheader("Change across ACS periods")
        st.plotly_chart(
            px.line(
                history,
                x="year",
                y=metric,
                color="county",
                markers=True,
                labels=LABELS,
                color_discrete_sequence=px.colors.qualitative.Safe,
            ).update_xaxes(dtick=1, tickformat="d"),
            width="stretch",
        )
        st.caption(
            "Nominal dollars. Lines connect published five-year estimates, not monthly observations. "
            "Adjacent ACS five-year vintages overlap; changes are not independent annual measurements."
        )
    st.subheader("Income and housing values")
    st.plotly_chart(
        px.scatter(
            current,
            x="median_household_income",
            y="median_home_value",
            hover_name="county",
            color="value_to_income",
            color_continuous_scale="Viridis",
            labels=LABELS,
        ),
        width="stretch",
    )
    st.caption("Observational association only. This chart does not establish causation.")
    st.dataframe(
        focus[["county", "period", *list(LABELS)[:3], "home_value_moe", "income_moe"]],
        hide_index=True,
        width="stretch",
    )
    st.download_button(
        "Download selected public county estimates (CSV)",
        focus.to_csv(index=False),
        file_name=f"california_counties_acs_{year}.csv",
        mime="text/csv",
    )
    rates_path = root / "data/cache/mortgage_monthly.csv"
    if rates_path.exists():
        rates = pd.read_csv(rates_path)
        st.subheader("US mortgage-rate context")
        st.plotly_chart(
            px.line(
                rates,
                x="year_month",
                y="rate_30yr_fixed",
                labels={"year_month": "Month", "rate_30yr_fixed": "30-year fixed mortgage rate (%)"},
            ),
            width="stretch",
        )
        st.caption(
            "Freddie Mac via FRED, MORTGAGE30US. Calendar-month mean of available weekly observations; "
            "a national benchmark. ACS five-year estimates are not aligned to individual months."
        )
    with st.expander("Sources, data quality and methodology", expanded=False):
        st.markdown(
            "[ACS 5-year data](https://www.census.gov/data/developers/data-sets/acs-5year.html) · "
            "[Census cartographic boundaries](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html)"
        )
        st.write(
            "B25077_001E: median owner-occupied home value; B19013_001E: median household income. "
            "M variables are published 90% margins of error. Negative Census sentinel values are unavailable, "
            "including top-coded estimates; they are not interpreted as dollars. Ratio uncertainty is not estimated. "
            "Polygons are generalized 2023 boundaries in EPSG:4326; they are appropriate for display, "
            "not parcel or boundary adjudication. No property-level price distribution, sales count or "
            "monthly market trend can be inferred from ACS county aggregates."
        )
        if (folder / "quality.csv").exists():
            st.dataframe(pd.read_csv(folder / "quality.csv"), hide_index=True)
        if (folder / "provenance.json").exists():
            st.json(json.loads((folder / "provenance.json").read_text()))
