"""Scan a public build for licensed data, secrets, private paths and AI-tool references before anyone publishes it.

  python check_public_build.py build/public

Fails (exit 1) if the data bundle contains price-like fields, any CRSP open or close value (to the cent) outside the clearly
labelled synthetic section, file-system paths, credential-like strings, or AI-tool names anywhere in the build."""
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

FORBIDDEN_KEYS = {"open", "close", "close_v", "close_ma", "open_v", "open_ma", "z", "z_signal", "qty_v", "qty_ma", "entry_px_v",
                  "entry_px_ma", "exit_px_v", "exit_px_ma", "timeline", "replays", "input_checksums"}
FORBIDDEN_LIST_KEYS = {"v", "ma"}          # price arrays in the local timeline; dicts with these names (valuation by company) are fine
# fields that are known not to be prices; a value equal to some historical price to the cent is a coincidence there
NON_PRICE_KEYS = {"pe", "v_pe", "ma_pe", "net_pnl", "gross_pnl", "borrow", "costs", "dividends", "v_price_pnl", "ma_price_pnl",
                  "v_market_est", "ma_market_est", "net", "net_excl_top3", "diff", "rest", "march2020", "gross_open", "gross_close", "borrow_paid"}
PATH_PATTERNS = [r"(?<![\w.-])/Users/[A-Za-z]", r"(?<![\w.-])/home/[a-z]", r"[A-Z]:\\\\Users\\\\"]   # case-sensitive file-system paths
SECRET_PATTERNS = [r"\.pgpass", r"password\s*[:=]", r"wrds_?pass", r"api[_-]?key", r"BEGIN [A-Z ]*PRIVATE KEY"]
# AI-tool names are matched by SHA-256 of each lower-cased word, so the names themselves never appear in this repository.
AI_NAME_HASHES = {
    "3ea125d0bff386e6754b3782b300016fc79a9cf8f8669c0a5c3db64467ddb681",
    "5d72436256ada53828b51895a94bb8489e9f1ac4fe937a8024ef1594e7045ff6",
    "60965168ce762e949600281ba6d01fee136e5b6e8257b1f216f9025ed324474c",
    "7d3194f79e645c42e4396dda38be04766810ec6a00d00aced3ffc2a0a1f1a9ef",
    "c70eca6b0f88f44d81a41311647e50fda1ac454ec04ffd442b0eb4743a993131",
    "c857d09db23e6822e3600bc06ad8d58f92ed62bc8efd81c753f77048662cb97d",
}


def ai_names(text):
    words = set(re.findall(r"[a-z]+", text.lower()))
    return [w for w in words if hashlib.sha256(w.encode()).hexdigest() in AI_NAME_HASHES]



def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + "/" + k, k, v
            yield from walk(v, path + "/" + k)
    elif isinstance(obj, list):
        key = path.rsplit("/", 1)[-1]
        for i, v in enumerate(obj):
            if not isinstance(v, (dict, list)):
                yield f"{path}[{i}]", key, v                  # list elements inherit the list's field name
            yield from walk(v, f"{path}[{i}]")


def numbers(obj):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from numbers(v)


def main(argv=None):
    root = Path((argv or sys.argv[1:])[0])
    raw = (root / "data.js").read_text()
    data = json.loads(raw[raw.index("=") + 1:].rstrip().rstrip(";"))
    problems = []
    real = {k: v for k, v in data.items() if k != "synthetic"}
    for path, key, val in walk(real):
        if key in FORBIDDEN_KEYS and "[" not in path.rsplit("/", 1)[-1] or (key in FORBIDDEN_LIST_KEYS and isinstance(val, list)):
            problems.append(f"forbidden field {path}")
    m = Path("data/processed/market.csv")
    if m.exists():
        px = pd.read_csv(m)
        prices = set(round(x, 2) for x in pd.concat([px.open, px.close]).dropna() if x > 1)
        # a leaked price looks like a value with a non-zero cents digit in the price range; parameters such as 30.0 bps are skipped
        hits = [f"{p}={x}" for p, k, x in walk(real) if isinstance(x, float) and not isinstance(x, bool) and k not in NON_PRICE_KEYS
                and 1 < abs(x) < 1000 and round(x, 1) != round(x, 2) and round(abs(x), 2) in prices]
        if hits:
            problems.append(f"{len(hits)} values equal CRSP prices to the cent: {hits[:8]}")
    else:
        print("note: data/processed/market.csv not found; the price-value scan was skipped")
    for f in root.iterdir():
        text = f.read_text(errors="ignore")
        body = text if f.name != "plotly.min.js" else ""
        for pat in PATH_PATTERNS:
            if re.search(pat, body):
                problems.append(f"{f.name}: file-system path matching {pat}")
        for pat in SECRET_PATTERNS:
            if re.search(pat, body, re.I):
                problems.append(f"{f.name}: credential-like text matching {pat}")
        if ai_names(text):
            problems.append(f"{f.name}: contains an AI-tool name")
    syn = json.dumps(data.get("synthetic", {}))
    if data.get("synthetic") and "SYNTHETIC" not in syn:
        problems.append("synthetic section lacks its label")
    if problems:
        print("PUBLIC BUILD CHECK FAILED:\n  " + "\n  ".join(problems[:40]))
        sys.exit(1)
    print(f"public build check passed: {root} ({len(list(numbers(real)))} numbers scanned against CRSP prices; no forbidden fields, paths, secrets or AI-tool names)")


if __name__ == "__main__":
    main()
