"""Public-data product view. County-year estimates never masquerade as home sales."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from atlas.public import validate_public
from atlas.style import MAP_SCALE, PALETTE, chart, section

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
    metric = st.sidebar.selectbox(
        "Map indicator",
        list(LABELS)[:3],
        format_func={
            "median_home_value": "Home value",
            "median_household_income": "Household income",
            "value_to_income": "Value / income",
        }.get,
    )
    current = data[data.year.eq(year)].copy()
    st.markdown(
        f'<div class="atlas-period"><span>ACS {year - 4}–{year}</span>'
        "<span>58 counties</span><span>US Census Bureau · Five-year estimates</span></div>",
        unsafe_allow_html=True,
    )
    a, b, c = st.columns(3)
    a.metric("Counties", str(len(current)))
    b.metric("County median home value", f"${current.median_home_value.median():,.0f}")
    c.metric("Median county value/income", f"{current.value_to_income.median():.1f}×")
    st.caption(
        "Unweighted county medians, not statewide estimates. Home values describe owner-occupied housing, not sale prices."
    )
    left, right = st.columns([1.4, 1], gap="medium")
    with left, st.container(border=True, key="geography"):
        section("01", "The geography of housing")
        st.subheader("Explore California")
        map_fig = px.choropleth(
            current,
            geojson=geo,
            locations="county_fips",
            featureidkey="properties.county_fips",
            color=metric,
            hover_name="county",
            color_continuous_scale=MAP_SCALE,
            labels=LABELS,
            hover_data={"county_fips": False, "home_value_moe": ":,.0f", "income_moe": ":,.0f"},
        )
        map_fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
        map_fig.update_traces(marker_line_color="#ffffff", marker_line_width=0.65)
        map_fig.update_layout(
            margin=dict(l=0, r=0, t=5, b=30),
            height=440,
            clickmode="event+select",
            coloraxis_colorbar=dict(
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.03,
                len=0.8,
                thickness=8,
                title=dict(text=LABELS[metric], side="bottom"),
                tickfont=dict(size=10),
                outlinewidth=0,
            ),
        )
        event = chart(
            map_fig,
            width="stretch",
            on_select="rerun",
            selection_mode="points",
            key=f"county_map_{year}_{metric}",
        )
        st.caption("Select a county on the map. Use the sidebar to compare several places.")
    clicked = [p.get("location") for p in event.selection.points if p.get("location")]
    focus = current[current.county_fips.isin(clicked)] if clicked else current[current.county.isin(selected)]
    if focus.empty:
        focus = current
    focus_names = focus.county.tolist()
    with right, st.container(border=True, key="comparison"):
        section("02", "Places in perspective")
        st.subheader("County comparisons")
        st.caption(f"{len(focus)} selected · {year - 4}–{year}")
        comparison = px.bar(
            focus.sort_values(metric),
            y="county",
            x=metric,
            orientation="h",
            labels=LABELS,
            color="county",
            color_discrete_sequence=PALETTE,
        )
        comparison.update_layout(
            height=397, showlegend=False, bargap=0.55, margin=dict(l=0, r=20, t=20, b=40)
        )
        comparison.update_yaxes(title=None, showgrid=False)
        comparison.update_xaxes(showgrid=True, gridcolor="#edf0e9")
        chart(comparison, width="stretch")
        st.caption("Each bar represents a county estimate. Sampling uncertainty varies by county.")
    history = data[data.county.isin(focus_names)]
    trend_col, relationship_col = st.columns(2, gap="medium")
    with trend_col, st.container(border=True, key="history"):
        section("03", "Across time")
        st.subheader("Change across ACS periods")
        if len(years) > 1:
            trend = px.line(
                history,
                x="year",
                y=metric,
                color="county",
                markers=True,
                labels=LABELS,
                color_discrete_sequence=PALETTE,
            )
            trend.update_xaxes(dtick=1, tickformat="d", title=None)
            trend.update_traces(line_width=2.5, marker_size=7)
            trend.update_layout(height=330)
            chart(trend, width="stretch")
        st.caption(
            "Nominal dollars. Five-year vintages overlap; lines do not represent independent annual changes."
        )
    with relationship_col, st.container(border=True, key="relationship"):
        section("04", "The bigger picture")
        st.subheader("Income and housing values")
        relationship = px.scatter(
            current,
            x="median_household_income",
            y="median_home_value",
            hover_name="county",
            color="value_to_income",
            color_continuous_scale=MAP_SCALE,
            labels=LABELS,
        )
        relationship.update_traces(marker=dict(size=8, line=dict(width=1, color="#fff")))
        relationship.update_layout(height=330, coloraxis_showscale=False)
        chart(relationship, width="stretch")
        st.caption("All 58 counties. Observational association only; this does not establish causation.")
    section("05", "Behind the charts")
    st.subheader("The selected data")
    st.caption(
        "Value/income compares two medians from different populations; it is not a household mortgage affordability calculation."
    )
    st.dataframe(
        focus[["county", "period", *list(LABELS)[:3], "home_value_moe", "income_moe"]],
        hide_index=True,
        width="stretch",
        column_config={
            "county": "County",
            "period": "ACS period",
            "median_home_value": st.column_config.NumberColumn("Home value", format="$%,.0f"),
            "median_household_income": st.column_config.NumberColumn("Household income", format="$%,.0f"),
            "value_to_income": st.column_config.NumberColumn("Value / income", format="%.1f×"),
            "home_value_moe": st.column_config.NumberColumn("Home value MOE", format="$%,.0f"),
            "income_moe": st.column_config.NumberColumn("Income MOE", format="$%,.0f"),
        },
    )
    st.download_button(
        "Download selected data ↓",
        focus.to_csv(index=False),
        file_name=f"california_counties_acs_{year}.csv",
        mime="text/csv",
    )
    rates_path = root / "data/cache/mortgage_monthly.csv"
    if rates_path.exists():
        rates = pd.read_csv(rates_path)
        st.subheader("US mortgage-rate context")
        chart(
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
