import pandas as pd
import pytest

from atlas.io import DataError
from atlas.reference import load_summary, reported_value


def test_aggregate_contract(tmp_path):
    path = tmp_path / "summary.csv"
    path.write_text("section,item,metric,value\nmetadata,source_rows,count,100\n")
    df = load_summary(path)
    assert reported_value(df, "metadata", "source_rows", "count") == 100
    assert reported_value(df, "numeric_distribution", "ClosePrice", "median") is None
    pd.concat([df, df]).drop(columns="number").to_csv(path, index=False)
    with pytest.raises(DataError):
        load_summary(path)
