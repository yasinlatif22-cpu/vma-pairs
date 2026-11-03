import pandas as pd
import pytest

from data_io import from_crsp


def test_split_adjustment_and_derived_dividend():
    # 2:1 split on day 3 (cfacpr doubles, raw price halves) and a $1.00 dividend on day 5.
    raw = pd.DataFrame({
        "date": pd.bdate_range("2020-01-06", periods=6), "ticker": "V",
        "prc": [100, 100, 100, 50, 50, 49], "openprc": [100, 100, 100, 50, 50, 49.5],
        "cfacpr": [1, 1, 1, 2, 2, 2],
        "ret": [None, 0.0, 0.0, 0.0, 0.0, -0.02 + 1 / 25 * 1.0 / 2], "retx": [None, 0.0, 0.0, 0.0, 0.0, -0.02]})
    # adjusted close before the split = 100/1; after = 50/2 = 25 -> a jump the adjustment must NOT hide?
    # CRSP's cfacpr is cumulative from the latest date backwards, so a correct file has cfacpr = 2 BEFORE the
    # split and 1 after; build that explicitly.
    raw["cfacpr"] = [2, 2, 2, 1, 1, 1]
    out = from_crsp(raw)
    assert out.close.iloc[2] == pytest.approx(50.0) and out.close.iloc[3] == pytest.approx(50.0)   # continuous
    exp_div = (raw.ret.iloc[5] - raw.retx.iloc[5]) * out.close.iloc[4]
    assert out["div"].iloc[5] == pytest.approx(exp_div) and out["div"].iloc[:5].eq(0).all()
