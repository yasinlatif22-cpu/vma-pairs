"""The public-build checker must reject licensed prices, price fields, paths and AI-tool names, and pass a clean bundle."""
import json

import pandas as pd
import pytest

import check_public_build


def _build(tmp_path, data, extra=""):
    d = tmp_path / "build"
    d.mkdir()
    (d / "data.js").write_text("window.DESK_DATA = " + json.dumps(data) + ";\n" + extra)
    (d / "index.html").write_text("<html></html>")
    return d


@pytest.fixture
def market(tmp_path, monkeypatch):
    p = tmp_path / "data" / "processed"
    p.mkdir(parents=True)
    pd.DataFrame({"date": ["2019-01-28"] * 2, "ticker": ["V", "MA"], "open": [134.57, 198.11], "close": [135.99, 200.16], "div": [0, 0]}).to_csv(p / "market.csv", index=False)
    monkeypatch.chdir(tmp_path)


CLEAN = {"meta": {"mode": "public"}, "stats": {"val": {"sharpe": 0.47, "net_pnl": 88874.12}},
         "synthetic": {"label": "SYNTHETIC DATA", "replays": [{"rows": [{"close_v": 135.99}]}]}}


def test_clean_bundle_passes_and_synthetic_prices_are_allowed(tmp_path, market):
    check_public_build.main([str(_build(tmp_path, CLEAN))])


@pytest.mark.parametrize("leak", [
    {"stats": {"val": {"some_value": 135.99}}},                 # a CRSP close hidden in an innocuous field
    {"timeline": {"dates": ["2019-01-28"]}},                    # a forbidden section
    {"trades": [{"entry_px_v": 1.0}]},                          # a forbidden price field
    {"notes": "saved from /Users/someone/Downloads"},            # a private path
    {"notes": "made with Zzplaceholdertool"},                    # a listed tool name (placeholder registered below)
])
def test_leaks_are_rejected(tmp_path, market, monkeypatch, leak):
    import hashlib
    monkeypatch.setattr(check_public_build, "AI_NAME_HASHES",
                        check_public_build.AI_NAME_HASHES | {hashlib.sha256(b"zzplaceholdertool").hexdigest()})
    with pytest.raises(SystemExit):
        check_public_build.main([str(_build(tmp_path, dict(CLEAN, **leak)))])
