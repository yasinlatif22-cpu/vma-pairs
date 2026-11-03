import pandas as pd
import pytest

from diagnostics.case_valuation import describe, pe_asof, ttm_asof


def fq():
    q = pd.date_range("2018-03-31", periods=8, freq="QE")
    return pd.DataFrame({"datadate": q, "rdq": q + pd.Timedelta(days=30), "epsfxq": [1, 1, 1, 1, 2, 2, 2, 2.0],
                         "ajexq": [2, 2, 2, 2, 1, 1, 1, 1.0], "saleq": [10, 10, 10, 10, 12, 12, 12, 12.0], "oiadpq": [5, 5, 5, 5, 6, 6, 6, 6.0]})


def test_only_quarters_reported_by_the_date_are_used():
    f = fq()                                  # quarter ending 2019-12-31 is reported 2020-01-30
    before = ttm_asof(f, pd.Timestamp("2020-01-29"))
    after = ttm_asof(f, pd.Timestamp("2020-01-30"))
    assert before["last_quarter"] == pd.Timestamp("2019-09-30") and after["last_quarter"] == pd.Timestamp("2019-12-31")


def test_eps_is_split_adjusted_and_ttm_sums_four_quarters():
    m = ttm_asof(fq(), pd.Timestamp("2019-12-31"))            # last reported quarter ends 2019-09-30
    assert m["eps"] == pytest.approx(0.5 + 2 + 2 + 2) and m["sales"] == 10 + 12 + 12 + 12     # 2018Q4 (split-adjusted) + 2019Q1-Q3
    assert pe_asof(fq(), 50.0, pd.Timestamp("2019-12-31")) == pytest.approx(50.0 / 6.5)


def test_growth_uses_the_prior_four_quarters_and_missing_history_is_handled():
    d = describe(fq(), 50.0, pd.Timestamp("2020-12-31"))
    assert d["sales_growth"] == pytest.approx(48 / 40 - 1)
    assert describe(fq().iloc[:3], 50.0, pd.Timestamp("2020-12-31")) is None
