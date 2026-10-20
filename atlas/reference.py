"""Published aggregate summaries are not property observations."""

from pathlib import Path

import pandas as pd

from atlas.io import DataError, download, provenance

REFERENCE_COMMIT = "09b25175ec828f0dba60f38900ee979d9bc0bbac"
REFERENCE_URL = "https://github.com/Banks027/VisualizationDashBoard"


def fetch_reference(folder: Path) -> None:
    urls, paths = [], []
    for feed in ("CRMLSListing", "CRMLSSold"):
        name = f"{feed}_calculated_summary.csv"
        url = f"https://raw.githubusercontent.com/Banks027/VisualizationDashBoard/{REFERENCE_COMMIT}/{name}"
        path = download(url, folder / name)
        load_summary(path)
        urls.append(url)
        paths.append(path)
    provenance(paths, urls, folder / "provenance.json")


def load_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    required = {"section", "item", "metric", "value"}
    if set(df.columns) != required or df.duplicated(["section", "item", "metric"]).any():
        raise DataError(f"Invalid summary schema or duplicate keys: {path}")
    df["number"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def reported_value(df: pd.DataFrame, section: str, item: str, metric: str) -> float | None:
    values = df.loc[(df.section == section) & (df.item == item) & (df.metric == metric), "number"]
    return float(values.iloc[0]) if len(values) and pd.notna(values.iloc[0]) else None
