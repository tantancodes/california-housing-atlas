"""Streamlit entrypoint; all analytical logic lives in atlas modules."""

from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from atlas.io import DataError
from atlas.reference import REFERENCE_URL, load_summary, reported_value

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="California Housing Atlas", page_icon="◈", layout="wide")
st.title("California Housing Atlas")
st.caption("Explore housing evidence • compare places • understand the limits")
MODES = ["Public county atlas", "Reference summaries"]
if os.getenv("ATLAS_ENABLE_PRIVATE") == "1":
    MODES.append("Local CRMLS analysis")
mode = st.sidebar.selectbox("Data source", MODES)


def reference_view() -> None:
    st.subheader("Published reference · aggregate evidence")
    st.warning(
        "These are upstream reported statistics, not validated residential market estimates. "
        "The source CSVs include implausible values and do not establish the population or reporting period "
        "for their distributions. County, date and property filters cannot be reconstructed."
    )
    feed = st.sidebar.selectbox("Feed", ["CRMLSListing", "CRMLSSold"])
    path = ROOT / "data/reference" / f"{feed}_calculated_summary.csv"
    if not path.exists():
        st.info("Fetch published summaries locally: python -m atlas.cli reference")
        return
    df = load_summary(path)
    source = reported_value(df, "metadata", "source_rows", "count")
    residential = reported_value(df, "metadata", "filtered_rows", "count")
    a, b = st.columns(2)
    a.metric("Reported source rows", f"{source:,.0f}" if source is not None else "Unavailable")
    b.metric("Reported residential rows", f"{residential:,.0f}" if residential is not None else "Unavailable")
    st.caption(
        "Monthly snapshots may repeat homes. No unique-home or transaction-total interpretation is assumed."
    )
    numeric = df[df.section.eq("numeric_distribution")]
    field = st.selectbox("Reported numeric field", sorted(numeric.item.unique()))
    selected = numeric[numeric.item.eq(field)]
    quantiles = selected[selected.metric.isin(["p10", "p25", "p50", "p75", "p90"])].copy()
    if not quantiles.empty:
        st.plotly_chart(
            px.bar(
                quantiles,
                x="metric",
                y="number",
                title=f"Reported {field} quantiles",
                labels={"metric": "Percentile", "number": field},
            ),
            width="stretch",
        )
    st.dataframe(selected[["item", "metric", "value"]], hide_index=True, width="stretch")
    st.subheader("Reported missingness")
    st.caption(
        "Upstream null percentages appear based on source rows, before the residential filter; "
        "they are not recalculated against the residential count."
    )
    missing = df[(df.section == "null_summary") & (df.metric == "null_percent")].sort_values(
        "number", ascending=False
    )
    st.plotly_chart(
        px.bar(
            missing.head(20),
            x="number",
            y="item",
            orientation="h",
            labels={"number": "Reported missing (%)", "item": "Field"},
        ),
        width="stretch",
    )
    with st.expander("Source and limitations"):
        st.markdown(
            f"[Reference repository]({REFERENCE_URL}) · pinned revision documented in docs/reference-audit.md"
        )
        st.write(
            "No histogram, price-per-square-foot ratio, monthly trend or county breakdown can be recovered "
            "from these summaries. A ratio of medians is not a median of property-level ratios."
        )
        st.dataframe(df.drop(columns="number"), hide_index=True)


def local_view() -> None:
    from atlas.pipeline import summarize

    st.subheader("Authorized local CRMLS records")
    st.info(
        "Private local mode. Keep this mode disabled on public deployments. No property-level download is exposed."
    )
    folder = Path(os.getenv("ATLAS_PRIVATE_OUTPUT", ROOT / "data/processed"))
    manifest_path = folder / "manifest.json"
    available = list(json.loads(manifest_path.read_text())["feeds"]) if manifest_path.exists() else []
    if not available:
        st.info("Run python -m atlas.cli process --input /path/to/authorized/files first.")
        return
    feed = st.sidebar.selectbox("Feed", sorted(available))
    df = pd.read_csv(folder / feed / "records.csv", low_memory=False)
    df["event_date"] = pd.to_datetime(df.event_date, errors="coerce")
    initial = len(df)
    dated = df.event_date.dropna()
    choices = {
        col: sorted(df[col].dropna().unique()) for col in ["CountyOrParish", "PropertySubType"] if col in df
    }
    for col, label in [("CountyOrParish", "County"), ("PropertySubType", "Property subtype")]:
        if col in df:
            selected = st.sidebar.multiselect(label, choices[col])
            if selected:
                df = df[df[col].isin(selected)]
    if len(dated):
        bounds = st.sidebar.date_input(
            "Event-date range",
            value=(dated.min().date(), dated.max().date()),
            min_value=dated.min().date(),
            max_value=dated.max().date(),
        )
        if len(bounds) == 2:
            df = df[
                df.event_date.between(
                    pd.Timestamp(bounds[0]), pd.Timestamp(bounds[1] + timedelta(days=1)), inclusive="left"
                )
            ]
    if st.sidebar.checkbox("Exclude IQR outliers (sensitivity only)", value=False):
        df = df[~df.any_iqr_flag]
    st.caption(
        f"{len(df):,} filtered records from {initial:,}. Undated records excluded when a date range is active."
    )
    st.caption("Asking prices" if feed == "CRMLSListing" else "Recorded close prices")
    if df.empty:
        st.info("No records match these filters.")
        return
    a, b, c = st.columns(3)
    a.metric("Records", f"{len(df):,}")
    prices = df.MarketPrice.dropna()
    b.metric("Median price", f"${prices.median():,.0f}" if len(prices) else "Unavailable")
    c.metric("Valid price observations", f"{len(prices):,}")
    st.plotly_chart(
        px.histogram(df, x="MarketPrice", nbins=50, labels={"MarketPrice": "Price (USD)"}), width="stretch"
    )
    st.plotly_chart(px.box(df, x="MarketPrice", labels={"MarketPrice": "Price (USD)"}), width="stretch")
    monthly = summarize(df, ["year_month"]).dropna(subset=["year_month"])
    st.plotly_chart(
        px.line(
            monthly,
            x="year_month",
            y="median_price",
            markers=True,
            labels={"year_month": "Event month", "median_price": "Median price (USD)"},
        ),
        width="stretch",
    )
    if "CountyOrParish" in df:
        st.dataframe(summarize(df, ["CountyOrParish"]), hide_index=True)
    if "rate_30yr_fixed" in df:
        rate = df.groupby("year_month", as_index=False).rate_30yr_fixed.first()
        st.plotly_chart(
            px.line(
                rate,
                x="year_month",
                y="rate_30yr_fixed",
                labels={"year_month": "Month", "rate_30yr_fixed": "US 30-year rate (%)"},
            ),
            width="stretch",
        )
        st.caption(
            "Monthly mean of available weekly FRED observations. Descriptive alignment; "
            "not the rate available at the transaction date and not a causal estimate."
        )
    with st.expander("Data quality and methodology", expanded=True):
        st.caption("Quality reports cover the complete processed feed before dashboard filters.")
        st.dataframe(pd.read_csv(folder / feed / "flags.csv"), hide_index=True)
        st.dataframe(pd.read_csv(folder / feed / "iqr_sensitivity.csv"), hide_index=True)
        st.dataframe(pd.read_csv(folder / feed / "validation.csv"), hide_index=True)
        st.json(json.loads((folder / "manifest.json").read_text()))
        st.write(
            "Invalid values excluded per metric; IQR outliers flagged and retained. Record counts may include "
            "repeated snapshots. Geographic checks are bounding-box plausibility only unless spatially joined."
        )


try:
    if mode == "Reference summaries":
        reference_view()
    elif mode == "Local CRMLS analysis":
        local_view()
    else:
        from atlas.dashboard import public_view

        public_view(ROOT)
except (OSError, ValueError, DataError, KeyError) as exc:
    st.error(f"Unable to load data: {exc}")
    st.info("Check the documented ingestion command and source schema. No fallback statistics are generated.")
