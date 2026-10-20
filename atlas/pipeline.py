"""Monthly CRMLS files are snapshots/events; row counts are not unique homes."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from atlas.io import DataError
from atlas.mortgage import align_rates

FEEDS = {"CRMLSListing": ("ListPrice", "ListingContractDate"), "CRMLSSold": ("ClosePrice", "CloseDate")}
NUMERIC = [
    "ClosePrice",
    "ListPrice",
    "OriginalListPrice",
    "LivingArea",
    "DaysOnMarket",
    "BedroomsTotal",
    "BathroomsTotalInteger",
    "LotSizeAcres",
    "YearBuilt",
    "Latitude",
    "Longitude",
]
DATES = ["CloseDate", "ListingContractDate", "PurchaseContractDate", "ContractStatusChangeDate"]


@dataclass(frozen=True)
class PipelineConfig:
    input_dir: Path
    output_dir: Path
    start: str = "2024-01"
    end: str | None = None
    boundaries: Path | None = None


def discover(config: PipelineConfig, feed: str) -> list[Path]:
    if feed not in FEEDS:
        raise DataError(f"Unknown feed: {feed}")
    start = pd.Period(config.start, freq="M")
    end = pd.Period(config.end, freq="M") if config.end else pd.Period(date.today(), freq="M") - 1
    if start > end:
        raise DataError("Start month must be no later than end month")
    result = []
    for file in sorted(config.input_dir.glob(f"{feed}*.csv")):
        match = re.fullmatch(rf"{feed}(\d{{4}})(\d{{2}})", file.stem)
        if match and 1 <= int(match[2]) <= 12:
            period = pd.Period(f"{match[1]}-{match[2]}", freq="M")
            if start <= period <= end:
                result.append(file)
    return result


def read_feed(files: list[Path], feed: str) -> tuple[pd.DataFrame, list[dict]]:
    if not files:
        raise DataError(f"No monthly input files for {feed}")
    price, event_date = FEEDS[feed]
    required = {"PropertyType", price, event_date}
    frames, schema = [], []
    baseline: set[str] | None = None
    for file in files:
        try:
            frame = pd.read_csv(file, low_memory=False, dtype=str)
        except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            raise DataError(f"Cannot read {file.name}: {exc}") from exc
        if frame.columns.duplicated().any() or any(re.search(r"\.\d+$", c) for c in frame.columns):
            raise DataError(f"Duplicate or ambiguous headers in {file.name}")
        if missing := required.difference(frame.columns):
            raise DataError(f"{file.name}: missing required columns: {sorted(missing)}")
        columns = set(frame.columns)
        if baseline is None:
            baseline = columns
        schema.append(
            {
                "file": file.name,
                "rows": len(frame),
                "missing_from_first": sorted(baseline - columns),
                "added_since_first": sorted(columns - baseline),
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            }
        )
        # Canonical provenance replaces any source field with these names.
        frame["source_file"] = file.name
        frame["source_row"] = np.arange(2, len(frame) + 2)
        frame["snapshot_month"] = file.stem[-6:-2] + "-" + file.stem[-2:]
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False), schema


def clean_records(raw: pd.DataFrame, feed: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    price, event_date = FEEDS[feed]
    if missing := {"PropertyType", price, event_date}.difference(raw.columns):
        raise DataError(f"Missing required columns: {sorted(missing)}")
    df = raw.loc[raw.PropertyType.str.strip().str.casefold().eq("residential")].copy()
    df = df.replace(r"^\s*$", np.nan, regex=True)
    reports = []
    for col in NUMERIC:
        if col not in df:
            continue
        original = df[col]
        parsed = pd.to_numeric(original, errors="coerce").replace([np.inf, -np.inf], np.nan)
        invalid = parsed.isna()
        if col in {"ClosePrice", "ListPrice", "OriginalListPrice", "LivingArea"}:
            invalid |= parsed.le(0)
        elif col in {"DaysOnMarket", "BedroomsTotal", "BathroomsTotalInteger", "LotSizeAcres"}:
            invalid |= parsed.lt(0)
        elif col == "YearBuilt":
            invalid |= ~parsed.between(1800, date.today().year + 1)
        df[f"{col}_invalid_flag"] = invalid
        reports.append(
            {
                "field": col,
                "kind": "numeric",
                "missing_input": int(original.isna().sum()),
                "invalid_nonmissing": int((original.notna() & invalid).sum()),
            }
        )
        df[col] = parsed.mask(invalid)
    for col in DATES:
        if col not in df:
            continue
        original = df[col]
        parsed = pd.to_datetime(original, errors="coerce", format="mixed", utc=True).dt.tz_localize(None)
        invalid = (
            parsed.isna() | parsed.gt(pd.Timestamp(date.today())) | parsed.lt(pd.Timestamp("1800-01-01"))
        )
        df[f"{col}_invalid_flag"] = invalid
        reports.append(
            {
                "field": col,
                "kind": "date",
                "missing_input": int(original.isna().sum()),
                "invalid_nonmissing": int((original.notna() & invalid).sum()),
            }
        )
        df[col] = parsed.mask(invalid)
    df["SourceFeed"] = feed
    df["MarketPrice"] = df[price]  # never substitute asking prices for missing sold prices
    df["event_date"] = df[event_date]
    df["year_month"] = df.event_date.dt.strftime("%Y-%m")
    df["PricePerSqFt"] = df.MarketPrice / df.get("LivingArea", pd.Series(np.nan, index=df.index))
    df["PriceRatio"] = (
        df["ClosePrice"] / df["OriginalListPrice"]
        if feed == "CRMLSSold" and {"ClosePrice", "OriginalListPrice"} <= set(df)
        else np.nan
    )
    df["negative_timeline_flag"] = False
    for name, first, second in [
        ("ListingToContractDays", "ListingContractDate", "PurchaseContractDate"),
        ("ContractToCloseDays", "PurchaseContractDate", "CloseDate"),
        ("ListingToCloseDays", "ListingContractDate", "CloseDate"),
    ]:
        if {first, second} <= set(df):
            days = (df[second] - df[first]).dt.total_seconds() / 86400
            df["negative_timeline_flag"] |= days.lt(0)
            df[name] = days.mask(days.lt(0))
    lat = df.get("Latitude", pd.Series(np.nan, index=df.index))
    lon = df.get("Longitude", pd.Series(np.nan, index=df.index))
    df["geo_missing_flag"] = lat.isna() | lon.isna()
    df["geo_global_invalid_flag"] = ~(lat.between(-90, 90) & lon.between(-180, 180))
    df["geo_ca_bbox_invalid_flag"] = ~(lat.between(32, 42.1) & lon.between(-124.6, -114.0))
    # A California bounding box is a plausibility check, not polygon membership.
    for col in ["CountyOrParish", "PropertySubType"]:
        if col in df:
            df[col] = df[col].str.strip()
    for col in ["MarketPrice", "LivingArea", "DaysOnMarket"]:
        if col in df:
            q1, q3 = df[col].quantile([0.25, 0.75])
            spread = q3 - q1
            df[f"{col}_iqr_flag"] = df[col].notna() & ~df[col].between(q1 - 1.5 * spread, q3 + 1.5 * spread)
    flags = [c for c in df if c.endswith("_iqr_flag")]
    df["any_iqr_flag"] = df[flags].any(axis=1)
    return df, pd.DataFrame(reports, columns=["field", "kind", "missing_input", "invalid_nonmissing"])


def summarize(df: pd.DataFrame, groups: list[str]) -> pd.DataFrame:
    return (
        df.groupby(groups, dropna=False)
        .agg(
            records=("MarketPrice", "size"),
            valid_prices=("MarketPrice", "count"),
            median_price=("MarketPrice", "median"),
            mean_price=("MarketPrice", "mean"),
            valid_ppsf=("PricePerSqFt", "count"),
            median_ppsf=("PricePerSqFt", "median"),
        )
        .reset_index()
    )


def run_pipeline(config: PipelineConfig, rates: pd.DataFrame | None = None) -> dict:
    # Validate/transform all feeds before creating outputs.
    results = []
    for feed in FEEDS:
        files = discover(config, feed)
        if not files:
            continue
        raw, schema = read_feed(files, feed)
        clean, validation = clean_records(raw, feed)
        if config.boundaries is not None:
            import geopandas as gpd

            from atlas.public import join_counties

            if not {"Latitude", "Longitude"} <= set(clean):
                raise DataError("Spatial joining needs Latitude and Longitude columns")
            clean = join_counties(clean, gpd.read_file(config.boundaries))
        if rates is not None:
            clean = align_rates(clean, rates)
        results.append((feed, raw, clean, validation, schema))
    if not results:
        raise DataError(
            "No matching monthly CRMLS files. Expected CRMLSListingYYYYMM.csv or CRMLSSoldYYYYMM.csv"
        )
    if config.input_dir.resolve() == config.output_dir.resolve():
        raise DataError("Input and output directories must be different")
    config.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "start": config.start,
        "end": config.end or str(pd.Period(date.today(), freq="M") - 1),
        "feeds": {},
        "mortgage_alignment": "calendar-month mean of weekly observations; descriptive only",
    }
    for feed, raw, clean, validation, schema in results:
        out = config.output_dir / feed
        out.mkdir(exist_ok=True)
        clean.to_csv(out / "records.csv", index=False)
        validation.to_csv(out / "validation.csv", index=False)
        raw = raw.replace(r"^\s*$", np.nan, regex=True)
        raw_missing = pd.DataFrame(
            {
                "field": raw.columns,
                "missing_count": raw.isna().sum().values,
                "missing_percent": raw.isna().mean().values * 100,
            }
        )
        raw_missing.to_csv(out / "input_missingness.csv", index=False)
        pd.DataFrame(
            {
                "field": clean.columns,
                "missing_count": clean.isna().sum().values,
                "missing_percent": clean.isna().mean().values * 100,
            }
        ).to_csv(out / "clean_missingness.csv", index=False)
        numeric = clean.select_dtypes(include="number")
        numeric.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]).to_csv(out / "numeric_summary.csv")
        pd.DataFrame({"field": clean.columns, "dtype": clean.dtypes.astype(str).values}).to_csv(
            out / "dtypes.csv", index=False
        )
        clean.loc[clean.geo_ca_bbox_invalid_flag].to_csv(out / "invalid_coordinates.csv", index=False)
        summarize(clean, ["year_month"]).to_csv(out / "monthly.csv", index=False)
        sensitivity = []
        for label, subset in [
            ("all_valid_values", clean),
            ("excluding_iqr_flags", clean[~clean.any_iqr_flag]),
        ]:
            sensitivity.append(
                {
                    "variant": label,
                    "records": len(subset),
                    "valid_prices": int(subset.MarketPrice.count()),
                    "median_price": subset.MarketPrice.median(),
                    "median_ppsf": subset.PricePerSqFt.median(),
                }
            )
        pd.DataFrame(sensitivity).to_csv(out / "iqr_sensitivity.csv", index=False)
        bounds = []
        for field in ["MarketPrice", "LivingArea", "DaysOnMarket"]:
            if field in clean:
                q1, q3 = clean[field].quantile([0.25, 0.75])
                bounds.append(
                    {
                        "field": field,
                        "q1": q1,
                        "q3": q3,
                        "lower": q1 - 1.5 * (q3 - q1),
                        "upper": q3 + 1.5 * (q3 - q1),
                    }
                )
        pd.DataFrame(bounds).to_csv(out / "iqr_bounds.csv", index=False)
        for group in [
            "CountyOrParish",
            "county_fips",
            "PropertySubType",
            "MLSAreaMajor",
            "ListOfficeName",
            "BuyerOfficeName",
        ]:
            if group in clean:
                summarize(clean, [group]).to_csv(out / f"by_{group}.csv", index=False)
        flags = [c for c in clean if c.endswith("_flag")]
        pd.DataFrame({"flag": flags, "count": [int(clean[c].sum()) for c in flags]}).to_csv(
            out / "flags.csv", index=False
        )
        manifest["feeds"][feed] = {
            "input_rows": len(raw),
            "residential_rows": len(clean),
            "files": schema,
            "undated_rows": int(clean.event_date.isna().sum()),
            "mortgage_unmatched": int(clean.get("mortgage_rate_missing_flag", pd.Series(dtype=bool)).sum()),
            "duplicate_snapshot_keys": int(clean.duplicated(["snapshot_month", "ListingKey"]).sum())
            if "ListingKey" in clean
            else None,
        }
    (config.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
