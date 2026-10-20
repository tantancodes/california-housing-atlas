from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_public_boot():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "California Housing Atlas"
    assert app.sidebar.selectbox[0].value == "Public county atlas"


def test_reference_graceful_without_network():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.sidebar.selectbox[0].select("Reference summaries").run()
    assert not app.exception
    assert not app.error
    assert app.warning
    # CI can run without downloaded upstream CSVs; the app gives the fetch command.
    if (ROOT / "data/reference/CRMLSListing_calculated_summary.csv").exists():
        assert len(app.metric) == 2
        assert len(app.dataframe) >= 1


def test_public_filters_change_data():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    if not (ROOT / "data/public/acs_counties.csv").exists():
        return
    app.sidebar.selectbox[1].select(2022).run()
    assert not app.exception and not app.error
    app.sidebar.multiselect[0].set_value(["Alameda"]).run()
    table = app.dataframe[0].value
    assert table.county.tolist() == ["Alameda"]
    assert table.period.tolist() == ["2018–2022"]
    app.sidebar.selectbox[2].select("value_to_income").run()
    assert not app.exception and not app.error
    assert app.metric[0].value == "58"


def test_private_local_dashboard_and_empty_filters(tmp_path, monkeypatch):
    import pandas as pd

    from atlas.pipeline import PipelineConfig, run_pipeline

    inputs = tmp_path / "raw"
    inputs.mkdir()
    pd.DataFrame(
        {
            "PropertyType": ["Residential", "Residential"],
            "ClosePrice": [500000, 800000],
            "CloseDate": ["2024-01-15", "2024-02-15"],
            "LivingArea": [1000, 1600],
            "CountyOrParish": ["Alameda", "Los Angeles"],
            "PropertySubType": ["Condo", "House"],
        }
    ).to_csv(inputs / "CRMLSSold202401.csv", index=False)
    output = tmp_path / "processed"
    run_pipeline(PipelineConfig(inputs, output, "2024-01", "2024-02"))
    monkeypatch.setenv("ATLAS_ENABLE_PRIVATE", "1")
    monkeypatch.setenv("ATLAS_PRIVATE_OUTPUT", str(output))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.sidebar.selectbox[0].select("Local CRMLS analysis").run()
    assert not app.exception and not app.error
    assert app.metric[0].value == "2"
    app.sidebar.multiselect[0].set_value(["Alameda"]).run()
    assert app.metric[0].value == "1"
    app.sidebar.multiselect[1].set_value(["House"]).run()
    assert not app.exception and not app.error
    assert any("No records match" in item.value for item in app.info)
