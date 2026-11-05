"""Re-run every completed evaluation listed in evaluations.json as a labelled reproduction (no shell loop needed).

  python reproduce.py                        # all seven, into results_rerun/
  python reproduce.py --out results_check --market data/processed/market.csv

Reproductions never count as fresh evaluations: each output folder carries REPRODUCTION.txt and each EXPERIMENTS.md row
says "reproduction". Needs the licensed market file produced by ingest.py."""
import argparse
import json
import sys

import run_study


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results_rerun")
    ap.add_argument("--market", default="data/processed/market.csv")
    ap.add_argument("--mkt", default="data/processed/mkt.csv")
    a = ap.parse_args(argv)
    if a.out == "results":
        sys.exit("Use a separate output directory for reproductions.")
    runs = json.loads(run_study.MANIFEST.read_text())["evaluations"]
    for e in runs:
        print(f"\n=== reproduction: {e['period']} gate={e['gate']} fill={e['fill']} (first run {e['date']}) ===")
        run_study.main(["--period", e["period"], "--gate", e["gate"], "--fill", e["fill"], "--reproduce",
                        "--out", a.out, "--market", a.market, "--mkt", a.mkt])


if __name__ == "__main__":
    main()
