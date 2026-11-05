"""Build the research app into build/<name>/ (git-ignored). Open build/<name>/index.html in a browser; no server needed.

  python build_site.py --mode local                    # full research view from your licensed files -> build/local/
  python build_site.py --mode public                   # allow-listed public build, aggregate tier -> build/public/
  python build_site.py --mode public --tier derived    # adds strategy equity and trade outcomes (no prices) -> build/public-derived/
  python build_site.py --docs                          # regenerate docs/CASE_STUDIES.md from docs/case_studies.json

Needs: requirements-viz.txt (plotly, whose bundled plotly.min.js is copied in with its licence header), results_rerun/ from
reproduce.py and results_rerun/scenarios.csv from scenarios.py. Nothing is uploaded or deployed by this script."""
import argparse
import json
import shutil
from pathlib import Path

import plotly

import site_export

WEB = Path(__file__).resolve().parent / "web"


def write_build(data, name):
    out = Path("build") / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in ("index.html", "styles.css", "core.js", "app.js"):
        shutil.copy(WEB / f, out / f)
    shutil.copy(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", out / "plotly.min.js")
    (out / "data.js").write_text("window.DESK_DATA = " + json.dumps(data, separators=(",", ":"), allow_nan=False) + ";\n")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "public"])
    ap.add_argument("--tier", choices=["aggregate", "derived"], default="aggregate")
    ap.add_argument("--res", default="results_rerun")
    ap.add_argument("--docs", action="store_true")
    a = ap.parse_args(argv)
    if a.docs:
        data = site_export.build("local", res=a.res)
        Path("docs/CASE_STUDIES.md").write_text(site_export.case_markdown(data["cases"]))
        print("wrote docs/CASE_STUDIES.md")
    if a.mode:
        data = site_export.build(a.mode, a.tier, a.res)
        name = "local" if a.mode == "local" else ("public" if a.tier == "aggregate" else "public-derived")
        out = write_build(data, name)
        size = sum(f.stat().st_size for f in out.iterdir()) / 1e6
        print(f"wrote {out}/ ({size:.1f} MB); open {out}/index.html")
        if a.mode == "public":
            import check_public_build
            check_public_build.main([str(out)])


if __name__ == "__main__":
    main()
