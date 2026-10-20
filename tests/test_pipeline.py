import numpy as np
import pandas as pd
import pytest

from atlas.io import DataError
from atlas.mortgage import align_rates, monthly_rates
from atlas.pipeline import PipelineConfig, clean_records, discover, read_feed, run_pipeline, summarize


@pytest.fixture
def raw():
    # Deliberately synthetic unit-test cases only; never shipped as dashboard observations.
    return pd.DataFrame(
        {
            "PropertyType": [" Residential ", "Residential", "Residential", "Land"],
            "ClosePrice": ["500000", "-1", "inf", "300"],
            "ListPrice": ["550000", "600000", "400000", "300"],
            "LivingArea": ["1000", "0", "bad", "1"],
            "OriginalListPrice": ["500000", "0", "300000", "200"],
            "DaysOnMarket": ["0", "-2", "bad", "1"],
            "CloseDate": ["2024-01-15", "bad", "2024-03-01", "2024-01-01"],
            "ListingContractDate": ["2024-01-01", "2024-01-01", "2024-04-01", "2024-01-01"],
            "Latitude": ["37", "0", "bad", "37"],
            "Longitude": ["-122", "0", "-122", "-122"],
        }
    )


def test_clean_metrics_are_feed_specific(raw):
    sold, validation = clean_records(raw, "CRMLSSold")
    listing, _ = clean_records(raw, "CRMLSListing")
    assert len(sold) == 3
    assert sold.MarketPrice.tolist()[0] == 500000
    assert sold.MarketPrice.isna().sum() == 2  # no sold-to-asking-price fallback
    assert listing.MarketPrice.tolist() == [550000, 600000, 400000]
    assert sold.PricePerSqFt.iloc[0] == 500
    assert sold.PricePerSqFt.isna().sum() == 2
    assert listing.PricePerSqFt.iloc[0] == 550
    assert sold.PriceRatio.iloc[0] == 1
    assert sold.PriceRatio.isna().sum() == 2
    assert sold.DaysOnMarket.iloc[0] == 0
    assert sold.DaysOnMarket.isna().sum() == 2
    assert sold.geo_ca_bbox_invalid_flag.tolist() == [False, True, True]
    assert sold.negative_timeline_flag.tolist() == [False, False, True]
    assert validation.loc[validation.field.eq("CloseDate"), "invalid_nonmissing"].iloc[0] == 1
    assert not np.isinf(sold.select_dtypes("number")).any().any()


def test_rates_preserve_missing_months(raw):
    rates = monthly_rates(
        pd.DataFrame({"DATE": ["2024-01-04", "2024-01-11", "2024-02-01"], "MORTGAGE30US": [6, 8, "."]})
    )
    assert rates.rate_30yr_fixed.iloc[0] == 7
    assert rates.rate_observations.iloc[0] == 2
    clean, _ = clean_records(raw, "CRMLSSold")
    joined = align_rates(clean, rates)
    assert len(joined) == len(clean)
    assert joined.mortgage_rate_missing_flag.sum() == 2
    with pytest.raises(DataError, match="unique"):
        align_rates(clean, pd.concat([rates, rates]))


def test_schema_and_discovery(tmp_path, raw):
    raw.to_csv(tmp_path / "CRMLSSold202401.csv", index=False)
    raw.to_csv(tmp_path / "CRMLSSold202413.csv", index=False)
    config = PipelineConfig(tmp_path, tmp_path / "out", "2024-01", "2024-02")
    assert len(discover(config, "CRMLSSold")) == 1
    bad = tmp_path / "CRMLSSold202402.csv"
    pd.DataFrame({"PropertyType": ["Residential"]}).to_csv(bad, index=False)
    with pytest.raises(DataError, match="missing required"):
        read_feed(discover(config, "CRMLSSold"), "CRMLSSold")
    with pytest.raises(DataError):
        run_pipeline(config)
    assert not config.output_dir.exists()


def test_reproducible_outputs(tmp_path, raw):
    raw.to_csv(tmp_path / "CRMLSSold202401.csv", index=False)
    config = PipelineConfig(tmp_path, tmp_path / "out", "2024-01", "2024-01")
    report = run_pipeline(config)
    assert report["feeds"]["CRMLSSold"]["input_rows"] == 4
    assert report["feeds"]["CRMLSSold"]["residential_rows"] == 3
    before = {p.name: p.read_bytes() for p in (config.output_dir / "CRMLSSold").glob("*.csv")}
    run_pipeline(config)
    assert before == {p.name: p.read_bytes() for p in (config.output_dir / "CRMLSSold").glob("*.csv")}
    df = pd.read_csv(config.output_dir / "CRMLSSold/monthly.csv")
    assert df.records.sum() == 3
    assert df.valid_prices.sum() == 1


def test_empty_residential_input(raw):
    frame, _ = clean_records(raw[raw.PropertyType.eq("Land")], "CRMLSSold")
    assert frame.empty
    assert summarize(frame, ["year_month"]).empty


def test_iqr_does_not_remove_observations(raw):
    frame, _ = clean_records(raw, "CRMLSSold")
    assert len(frame) == 3
    assert "any_iqr_flag" in frame
