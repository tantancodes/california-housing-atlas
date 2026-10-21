"""Map-first exploration of published county estimates, never inferred home sales."""

from __future__ import annotations

import json
import os
from html import escape
from io import StringIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
METRICS = tuple(LABELS)[:3]
SHORT = dict(zip(METRICS, ("Home value", "Household income", "Value / income"), strict=True))
MOE = {"median_home_value": "home_value_moe", "median_household_income": "income_moe"}


def number(value: float, metric: str) -> str:
    """One number vocabulary, including explicit unavailable estimates."""
    if pd.isna(value):
        return "Unavailable"
    return f"{value:.1f}×" if metric == "value_to_income" else f"${value:,.0f}"


def relative_position(current: pd.DataFrame, fips: str, metric: str) -> tuple[int, int] | None:
    """Competition rank (1 is highest), excluding missing estimates and retaining ties."""
    values = current.set_index("county_fips")[metric].dropna()
    if fips not in values.index:
        return None
    return int(values.rank(ascending=False, method="min").loc[fips]), len(values)


def comparison_differences(focus: pd.DataFrame) -> pd.DataFrame:
    """Signed point-estimate differences against the first selected county; no significance claim."""
    if len(focus) < 2:
        return pd.DataFrame(columns=["county", *METRICS])
    result = focus.iloc[1:][["county", *METRICS]].copy()
    for metric in METRICS:
        result[metric] = result[metric] - focus.iloc[0][metric]
    return result


def county_from_selection(points: list[dict], current: pd.DataFrame) -> str | None:
    """Resolve only known FIPS; ignore invalid/empty events instead of clearing selection."""
    lookup = current.set_index("county_fips").county
    for point in reversed(points):
        fips = point.get("location")
        if fips in lookup.index:
            return str(lookup.loc[fips])
    return None


@st.cache_data(show_spinner="Loading published Census estimates…")
def load_public(csv_text: str, geojson_text: str) -> tuple[pd.DataFrame, dict]:
    data = validate_public(pd.read_csv(StringIO(csv_text), dtype={"county_fips": str}))
    return data, json.loads(geojson_text)


def map_figure(current: pd.DataFrame, geo: dict, metric: str, active_fips: str) -> go.Figure:
    """Keep missing counties visible and selected borders independent of the color scale."""
    fig = go.Figure()
    fig.add_choropleth(
        geojson=geo,
        locations=current.county_fips,
        featureidkey="properties.county_fips",
        z=[0] * len(current),
        colorscale=[[0, "#e3e1d9"], [1, "#e3e1d9"]],
        showscale=False,
        text=current.county,
        hovertemplate="<b>%{text}</b><br>Estimate unavailable<extra></extra>",
        marker_line_color="#faf9f5",
        marker_line_width=0.65,
    )
    valid = current.dropna(subset=[metric]).copy()
    if not valid.empty:
        valid["value_label"] = valid[metric].map(lambda value: number(value, metric))
        valid["value_moe_label"] = valid.home_value_moe.map(lambda value: number(value, "median_home_value"))
        valid["income_moe_label"] = valid.income_moe.map(
            lambda value: number(value, "median_household_income")
        )
        layer = px.choropleth(
            valid,
            geojson=geo,
            locations="county_fips",
            featureidkey="properties.county_fips",
            color=metric,
            color_continuous_scale=MAP_SCALE,
            custom_data=["county", "period", "value_label", "value_moe_label", "income_moe_label"],
        )
        layer.update_traces(
            marker_line_color="#faf9f5",
            marker_line_width=0.65,
            hovertemplate=(
                "<b>%{customdata[0]} County</b><br>ACS %{customdata[1]}<br>"
                + SHORT[metric]
                + ": %{customdata[2]}<br>"
                "Home value MOE: ±%{customdata[3]}<br>Income MOE: ±%{customdata[4]}"
                "<extra>90% margins of error</extra>"
            ),
        )
        fig.add_trace(layer.data[0])
    active = current[current.county_fips.eq(active_fips)]
    if not active.empty:
        fig.add_choropleth(
            geojson=geo,
            locations=active.county_fips,
            featureidkey="properties.county_fips",
            z=[0],
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False,
            marker_line_color="#253d37",
            marker_line_width=2.4,
            hoverinfo="skip",
        )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(
        height=610,
        margin=dict(l=0, r=0, t=5, b=65),
        clickmode="event+select",
        dragmode=False,
        coloraxis=dict(
            colorscale=MAP_SCALE,
            colorbar=dict(
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.02,
                len=0.8,
                thickness=10,
                title=dict(text=LABELS[metric], side="bottom"),
                outlinewidth=0,
                tickprefix="" if metric == "value_to_income" else "$",
                ticksuffix="×" if metric == "value_to_income" else "",
                tickformat=".1f" if metric == "value_to_income" else "~s",
            ),
        ),
    )
    return fig


def _map_selected(key: str, current: pd.DataFrame) -> None:
    state = st.session_state.get(key, {})
    county = county_from_selection(state.get("selection", {}).get("points", []), current)
    if county:
        st.session_state["atlas_county"] = county


def _add_county(county: str) -> None:
    selected = st.session_state["atlas_compare"]
    if county not in selected and len(selected) < 3:
        st.session_state["atlas_compare"] = [*selected, county]


def _heading(letter: str, title: str, anchor: str) -> None:
    st.html(f'<div id="{anchor}" class="atlas-anchor"></div>')
    section(letter, title)


def _table(focus: pd.DataFrame) -> None:
    st.dataframe(
        focus[["county", "period", *METRICS, "home_value_moe", "income_moe"]],
        hide_index=True,
        width="stretch",
        column_config={
            "county": "County",
            "period": "ACS period",
            "median_home_value": st.column_config.NumberColumn("Home value", format="$%,.0f"),
            "median_household_income": st.column_config.NumberColumn("Household income", format="$%,.0f"),
            "value_to_income": st.column_config.NumberColumn("Value / income", format="%.1f×"),
            "home_value_moe": st.column_config.NumberColumn("Home value MOE (±)", format="$%,.0f"),
            "income_moe": st.column_config.NumberColumn("Income MOE (±)", format="$%,.0f"),
        },
    )


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
    if data.empty:
        st.info("No published estimates are available. Refresh the public dataset to explore the atlas.")
        return
    years = sorted(data.year.unique())
    year = st.sidebar.selectbox(
        "ACS ending year",
        years,
        index=len(years) - 1,
        key="atlas_year",
        help="Each vintage summarizes five years, not a single calendar year.",
    )
    counties = sorted(data.county.unique())
    selected = st.sidebar.multiselect(
        "Compare counties",
        counties,
        default=[c for c in ["Alameda", "Los Angeles", "San Francisco"] if c in counties],
        max_selections=3,
        key="atlas_compare",
        help="Choose two or three counties. The map selection stays independent.",
    )
    metric = st.sidebar.selectbox("Map indicator", METRICS, format_func=SHORT.get, key="atlas_metric")
    current = data[data.year.eq(year)].copy()
    if current.empty:
        st.info("No estimates for this vintage.")
        return
    current_names = sorted(current.county.unique())
    if st.session_state.get("atlas_county") not in current_names:
        st.session_state["atlas_county"] = (
            "Los Angeles" if "Los Angeles" in current_names else current_names[0]
        )
    active = current[current.county.eq(st.session_state["atlas_county"])].iloc[0]
    focus = current.set_index("county").reindex([c for c in selected if c in current_names]).reset_index()
    period = f"{year - 4}–{year}"
    st.html(
        f'<div class="atlas-period"><span>ACS {period}</span><span>US Census Bureau · Five-year estimates</span></div>'
    )
    st.html(
        '<nav class="atlas-nav" aria-label="Atlas sections">'
        '<a href="#big-picture">01 The big picture</a><a href="#county">02 A closer look</a>'
        '<a href="#compare">03 Compare</a><a href="#changes">04 Across time</a>'
        '<a href="#about">05 About the data</a></nav>'
    )
    a, b, c = st.columns(3)
    a.metric("California counties", str(len(current)))
    b.metric("Median of county home values", number(current.median_home_value.median(), "median_home_value"))
    c.metric(
        "Median of county value / income ratios", number(current.value_to_income.median(), "value_to_income")
    )
    st.caption(
        "Each county counts equally. These are unweighted medians of county estimates, not statewide estimates or sale prices."
    )

    _heading("01", "The big picture", "big-picture")
    st.subheader("One state. Many housing realities.")
    st.write(f"Explore {SHORT[metric].lower()} across California. Select a county to take a closer look.")
    with st.container(border=True, key="atlas_map_panel"):
        map_key = f"county_map_{year}_{metric}"
        chart(
            map_figure(current, geo, metric, active.county_fips),
            width="stretch",
            key=map_key,
            alt=f"California county map of {SHORT[metric].lower()}, ACS {period}. County estimates are available in the comparison CSV.",
            on_select=lambda: _map_selected(map_key, current),
            selection_mode="points",
        )
        st.caption(
            f"Outlined: {active['county']} County · Gray: unavailable · Select a county on the map or use the accessible county selector below."
        )
    valid = current.dropna(subset=[metric])
    if not valid.empty:
        low, high = valid.loc[valid[metric].idxmin()], valid.loc[valid[metric].idxmax()]
        st.html(
            f'<p class="atlas-insight">Across {len(valid)} counties with estimates, {escape(SHORT[metric].lower())} '
            f"ranges from <strong>{number(low[metric], metric)}</strong> in {escape(low['county'])} "
            f"to <strong>{number(high[metric], metric)}</strong> in {escape(high['county'])}. "
            "These are point estimates; sampling uncertainty applies.</p>"
        )
    else:
        st.info("This indicator is unavailable for all counties in this vintage.")

    _heading("02", "Explore a county", "county")
    selector, action = st.columns([2, 1], vertical_alignment="bottom")
    selector.selectbox("County in focus", current_names, key="atlas_county")
    if active["county"] not in selected and len(selected) < 3:
        action.button("Add to comparison", on_click=_add_county, args=(active["county"],), width="stretch")
    elif active["county"] not in selected:
        action.caption("Comparison full. Remove a county in the sidebar to add this one.")
    else:
        action.caption("Included in your comparison ↓")
    with st.container(border=True, key="atlas_detail_panel"):
        st.subheader(f"{active['county']} County")
        st.caption(
            f"ACS {period} · FIPS {active.county_fips} · Rank 1 is the highest point estimate; ties share a rank."
        )
        for col, field in zip(st.columns(3), METRICS, strict=True):
            with col:
                st.metric(SHORT[field], number(active[field], field))
                if field in MOE:
                    moe = active[MOE[field]]
                    st.caption(f"90% MOE: ±{number(moe, field)}" if pd.notna(moe) else "90% MOE unavailable")
                else:
                    st.caption("Ratio uncertainty not estimated")
                rank = relative_position(current, active.county_fips, field)
                st.caption(
                    f"Rank {rank[0]} of {rank[1]} counties with estimates"
                    if rank
                    else "No rank: estimate unavailable"
                )
        st.caption(
            "Home value covers owner-occupied homes. Income covers all households. Their ratio is context, not a mortgage affordability measure."
        )

    _heading("03", "Compare counties", "compare")
    st.subheader("Put places in perspective.")
    st.write(
        "Choose two or three counties in the sidebar. Compare the same ACS period, with published uncertainty visible."
    )
    if len(focus) < 2:
        st.info(
            "Select two or three counties for side-by-side comparisons. A single selection can still be explored and downloaded below."
        )
    if not focus.empty:
        for col, field in zip(st.columns(3), METRICS, strict=True):
            with col:
                st.markdown(f"**{SHORT[field]}**")
                comparison = px.bar(
                    focus,
                    x=field,
                    y="county",
                    orientation="h",
                    labels=LABELS,
                    error_x=MOE.get(field),
                    color_discrete_sequence=[PALETTE[0]],
                )
                maximum = current[field].max()
                if field in MOE:
                    maximum = (current[field] + current[MOE[field]].fillna(0)).max()
                comparison.update_layout(
                    height=240, showlegend=False, bargap=0.65, margin=dict(l=0, r=16, t=10, b=30)
                )
                comparison.update_yaxes(
                    title=None, categoryorder="array", categoryarray=focus.county.tolist()[::-1]
                )
                comparison.update_xaxes(
                    title=None,
                    range=[0, maximum * 1.06 if pd.notna(maximum) and maximum > 0 else 1],
                    tickprefix="" if field == "value_to_income" else "$",
                    ticksuffix="×" if field == "value_to_income" else "",
                    showgrid=True,
                )
                comparison.update_traces(
                    hovertemplate=(
                        "%{y}<br>"
                        + ("%{x:.1f}×" if field == "value_to_income" else "$%{x:,.0f}")
                        + "<extra>"
                        + SHORT[field]
                        + "</extra>"
                    )
                )
                chart(
                    comparison,
                    width="stretch",
                    alt=f"{SHORT[field]} comparison for {', '.join(focus.county)}. Published 90% margins of error appear as whiskers where available.",
                )
        st.caption(
            "Bars start at zero and use the full California range for each indicator. Whiskers show published 90% MOEs; no ratio MOE is calculated."
        )
    _table(focus)
    differences = comparison_differences(focus)
    if not differences.empty:
        baseline = focus.iloc[0]["county"]
        with st.expander(f"Point-estimate differences from {baseline}"):
            for _, row in differences.iterrows():
                parts = []
                for field in METRICS:
                    value = row[field]
                    text = (
                        "unavailable"
                        if pd.isna(value)
                        else (f"{value:+.1f}×" if field == "value_to_income" else f"{value:+,.0f} USD")
                    )
                    parts.append(f"{SHORT[field].lower()}: {text}")
                st.write(f"{row['county']} minus {baseline} — " + "; ".join(parts))
            st.caption(
                "Descriptive differences only. A difference in point estimates is not evidence of statistical significance."
            )
    st.download_button(
        "Download comparison CSV ↓",
        focus.to_csv(index=False),
        file_name=f"california_comparison_acs_{year}.csv",
        mime="text/csv",
        disabled=focus.empty,
    )

    _heading("04", "Explore changes", "changes")
    st.subheader("Different vintages. Overlapping years.")
    st.caption(
        f"Showing {SHORT[metric].lower()} for your comparison counties; if none are selected, showing the county in focus."
    )
    history_names = focus.county.tolist() or [active["county"]]
    history = data[data.county.isin(history_names)].sort_values(["county", "year"])
    trend_col, relationship_col = st.columns([1.3, 1], gap="large")
    with trend_col:
        if len(years) > 1:
            trend = px.line(
                history,
                x="year",
                y=metric,
                color="county",
                markers=True,
                labels=LABELS,
                color_discrete_sequence=PALETTE,
                custom_data=["period"],
            )
            trend.update_xaxes(tickvals=years, ticktext=[f"{y - 4}–{y}" for y in years], title=None)
            trend.update_yaxes(
                tickprefix="" if metric == "value_to_income" else "$",
                ticksuffix="×" if metric == "value_to_income" else "",
            )
            trend.update_traces(
                line_width=2.5,
                marker_size=7,
                connectgaps=False,
                hovertemplate=(
                    "ACS %{customdata[0]}<br>"
                    + ("%{y:.1f}×" if metric == "value_to_income" else "$%{y:,.0f}")
                    + "<extra>%{fullData.name}</extra>"
                ),
            )
            trend.update_layout(height=360, legend=dict(y=-0.25))
            chart(
                trend,
                width="stretch",
                alt=f"{SHORT[metric]} across overlapping ACS five-year vintages for {', '.join(history_names)}. Not independent annual changes.",
            )
        else:
            st.info("Only one ACS vintage is available; a change cannot be shown.")
        st.caption(
            "Adjacent five-year vintages share four years of observations. Lines connect estimates, not independent annual changes. Dollars are nominal and reflect each vintage’s dollar year."
        )
    with relationship_col:
        relationship = px.scatter(
            current,
            x="median_household_income",
            y="median_home_value",
            hover_name="county",
            labels=LABELS,
            color_discrete_sequence=["#7d8b82"],
        )
        relationship.update_traces(marker=dict(size=8, line=dict(width=1, color="#fff")))
        relationship.add_scatter(
            x=[active.median_household_income],
            y=[active.median_home_value],
            mode="markers",
            marker=dict(size=13, color=PALETTE[0], line=dict(color="#253d37", width=2)),
            name=active["county"],
            text=[active["county"]],
            hovertemplate="%{text}<br>Income: $%{x:,.0f}<br>Home value: $%{y:,.0f}<extra></extra>",
        )
        relationship.update_layout(height=360, showlegend=False)
        relationship.update_xaxes(title="Household income (USD/year)", tickprefix="$")
        relationship.update_yaxes(title="Home value (USD)", tickprefix="$")
        chart(
            relationship,
            width="stretch",
            alt="County household income versus owner-occupied home value. Each dot is one county; association is not causation.",
        )
        st.caption(
            "Each dot is a county; the outlined dot is your county in focus. Association does not establish causation."
        )

    _heading("05", "About the data", "about")
    st.subheader("Public evidence. Clear limits.")
    st.write(
        f"US Census Bureau ACS five-year estimates, {', '.join(f'{y - 4}–{y}' for y in years)}. All {len(current)} California counties; no private listings or inferred property records."
    )
    st.download_button(
        "Download all county vintages ↓",
        data.to_csv(index=False),
        file_name="california_acs_county_estimates.csv",
        mime="text/csv",
        type="primary",
    )
    with st.expander("Definitions, uncertainty & responsible interpretation", expanded=True):
        st.markdown(
            "- **Home value:** B25077_001E, median value of owner-occupied housing units. Not a sale-price statistic.\n"
            "- **Household income:** B19013_001E, median income across all households, in the vintage’s inflation-adjusted dollars.\n"
            "- **Value / income:** home-value median divided by household-income median, two different populations. It does not measure a specific household’s borrowing capacity.\n"
            "- **Uncertainty:** M variables are published 90% margins of error. Ratios, ranks and descriptive differences have no calculated uncertainty; overlapping intervals alone are not a significance test.\n"
            "- **Missing values:** negative Census sentinels, including top-coded estimates, are unavailable. Gray map areas and gaps do not mean zero.\n"
            "- **Geography:** generalized 2023 county polygons in EPSG:4326, joined by five-digit FIPS. This public view displays boundaries; optional CRMLS processing performs point-in-polygon joins.\n"
            "- **Scope:** county aggregates cannot establish property distributions, sales counts or monthly market trends."
        )
    with st.expander("Sources, licensing & reproducibility"):
        st.markdown(
            "[ACS five-year data](https://www.census.gov/data/developers/data-sets/acs-5year.html) · "
            "[Census cartographic boundaries](https://www.census.gov/geographies/mapping-files/time-series/geo/carto-boundary-file.html) · "
            "[US government data licensing](https://resources.data.gov/open-licenses/)"
        )
        st.write(
            "Census federal data are public domain. The bundled snapshot is reproducible with `python -m atlas.cli public`; provenance records source URLs, retrieval time and SHA-256 checksums."
        )
        if (folder / "quality.csv").exists():
            st.dataframe(pd.read_csv(folder / "quality.csv"), hide_index=True)
        if (folder / "provenance.json").exists():
            st.json(json.loads((folder / "provenance.json").read_text()))
    rates_path = root / "data/cache/mortgage_monthly.csv"
    if rates_path.exists():
        with st.expander("Optional national mortgage-rate context"):
            rates = pd.read_csv(rates_path)
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
                "Freddie Mac via FRED, MORTGAGE30US. Calendar-month mean of available weekly observations; a national benchmark. ACS five-year estimates are not aligned to individual months."
            )
    st.html(
        '<footer class="atlas-footer"><span>California Housing Atlas</span><span>Built for a closer look.</span></footer>'
    )
