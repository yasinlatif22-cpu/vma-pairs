"""Fresh-clone reproduction workflow: the committed manifest, labelled reproductions, CLI validation, ingestion folders."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

import reproduce
import run_study
from data_io import synthetic_market


@pytest.fixture
def clone(tmp_path, monkeypatch):
    """A working directory with no results/ and no lock files, a copy of the manifest, and a synthetic market file spanning
    the real evaluation dates (the CRSP file is licensed and absent from a fresh clone)."""
    man = tmp_path / "evaluations.json"
    shutil.copy(run_study.MANIFEST, man)
    monkeypatch.setattr(run_study, "MANIFEST", man)
    long, mkt = synthetic_market(seed=4, n=1300, start="2021-01-04")
    long.to_csv(tmp_path / "market.csv", index=False)
    mkt.reset_index().rename(columns={"index": "date"}).to_csv(tmp_path / "mkt.csv", index=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _args(*extra):
    return ["--market", "market.csv", "--mkt", "mkt.csv", *extra]


def test_spent_holdout_reproduces_in_a_fresh_clone_and_is_labelled(clone):
    run_study.main(_args("--period", "holdout", "--reproduce", "--out", "results_rerun"))
    out = clone / "results_rerun" / "holdout_none_open_next"
    assert (out / "REPRODUCTION.txt").read_text().count("Not a fresh test") == 1
    assert "REPRODUCTION, not a fresh evaluation" in (out / "summary.txt").read_text()
    assert not (clone / "results").exists()


def test_recorded_evaluations_cannot_be_rerun_as_fresh(clone):
    with pytest.raises(SystemExit, match="already evaluated"):
        run_study.main(_args("--period", "holdout", "--confirm", "26be1bbf6e29"))
    with pytest.raises(SystemExit, match="already evaluated"):
        run_study.main(_args("--period", "val"))


def test_unlisted_variant_cannot_be_reproduced_and_a_first_run_is_recorded(clone):
    with pytest.raises(SystemExit, match="nothing to reproduce"):
        run_study.main(_args("--period", "holdout", "--gate", "coint", "--reproduce", "--out", "rr"))
    with pytest.raises(SystemExit, match="--confirm"):
        run_study.main(_args("--period", "holdout", "--gate", "coint"))
    run_study.main(_args("--period", "holdout", "--gate", "coint", "--confirm", "a8e20fc3bc42"))
    recs = json.loads(run_study.MANIFEST.read_text())["evaluations"]
    assert any(e["period"] == "holdout" and e["gate"] == "coint" for e in recs)
    with pytest.raises(SystemExit, match="already evaluated"):
        run_study.main(_args("--period", "holdout", "--gate", "coint", "--confirm", "a8e20fc3bc42"))


@pytest.mark.parametrize("bad", [["--gate", "cointegration"], ["--fill", "open"]])
def test_invalid_variant_values_are_rejected(clone, bad):
    with pytest.raises(SystemExit) as e:
        run_study.main(_args("--period", "val", *bad))
    assert e.value.code == 2


def test_runner_reproduces_every_manifest_entry_as_a_reproduction(monkeypatch):
    calls = []
    monkeypatch.setattr(run_study, "main", lambda argv: calls.append(argv))
    reproduce.main([])
    recs = json.loads(Path(run_study.MANIFEST).read_text())["evaluations"]
    assert len(calls) == len(recs) == 7 and all("--reproduce" in c and "results_rerun" in c for c in calls)


def test_ingest_creates_its_output_folders(tmp_path, monkeypatch):
    import ingest
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    d = pd.bdate_range("2020-01-02", periods=5)
    rows = [dict(date=x, ticker=t, prc=100.0, openprc=99.0, ret=0.0, retx=0.0, cfacpr=1.0) for x in d for t in ("V", "MA")]
    pd.DataFrame(rows).to_csv(raw / "crsp_daily.csv", index=False)
    pd.DataFrame({"date": d, "mkt_ret": 0.0}).to_csv(raw / "mkt_raw.csv", index=False)
    monkeypatch.chdir(tmp_path)
    ingest.main()
    assert (tmp_path / "data" / "processed" / "market.csv").exists() and (tmp_path / "data" / "processed" / "mkt.csv").exists()
