"""Print a provenance record: code version, tested environment, and input checksums (no market data).   python diagnostics/provenance.py"""
import hashlib
import json
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*a):
    try:
        return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unavailable"


def main():
    print("## Code version")
    print(f"- git commit: `{git('rev-parse', 'HEAD')}`; working tree {'clean' if not git('status', '--porcelain') else 'has uncommitted changes'}")
    print(f"- Python {platform.python_version()} on {platform.system()}; " + ", ".join(f"{p} {version(p)}" for p in ("numpy", "pandas", "scipy", "statsmodels", "matplotlib", "pytest")))
    print("\n## Input files (SHA-256; sizes in bytes). The files themselves are licensed and are not in the repository")
    for p in ("data/raw/crsp_daily.csv", "data/raw/mkt_raw.csv", "data/processed/market.csv", "data/processed/mkt.csv", "data/raw/rf.csv",
              "data/raw/earnings.csv", "data/raw/crsp_checks.csv", "data/raw/crsp_distributions.csv", "data/raw/wrds_manifest.json"):
        f = Path(p)
        print(f"- `{p}`: " + (f"{sha(f)} ({f.stat().st_size:,} bytes, last modified (UTC) {__import__('datetime').datetime.fromtimestamp(f.stat().st_mtime, tz=__import__('datetime').timezone.utc).isoformat(timespec='minutes')})" if f.exists() else "not present"))
    log = Path("data/raw/extraction_log.json")
    if log.exists():
        j = json.loads(log.read_text())
        print(f"\n## Auxiliary extraction (extract_aux.py), run {j['run_utc']} UTC; permnos {j['permnos']}")
        for k, v in j["steps"].items():
            print(f"- {k}: " + (f"{v['rows']} rows, {v.get('first')} to {v.get('last')}, sha256 {v['sha256']}\n  query: `{v['query']}`" if "rows" in v else f"FAILED ({v['error']})"))
    man = Path("data/raw/wrds_manifest.json")
    if man.exists():
        m = json.loads(man.read_text())
        print("\n## WRDS schema check (extract_wrds.py --check)")
        print(f"- crsp.dsf_v2 coverage probe (Apple, permno 14593, used only to see how far the table reaches): {m.get('ciz_coverage_probe')}")
        print(f"- missing fields for the CIZ format: {m.get('ciz_missing_fields')}; crsp.dsf (legacy) probe: {m.get('legacy_coverage_probe')}")


if __name__ == "__main__":
    main()
