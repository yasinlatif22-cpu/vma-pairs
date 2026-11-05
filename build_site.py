"""Build the research app into build/<name>/ (git-ignored) and, with --serve, open it in your web browser.

  python build_site.py --mode local                    # full research view from your licensed files -> build/local/
  python build_site.py --mode public                   # allow-listed public build, aggregate tier -> build/public/
  python build_site.py --mode public --tier derived    # adds strategy equity and trade outcomes (no prices) -> build/public-derived/
  python build_site.py --docs                          # regenerate docs/CASE_STUDIES.md from docs/case_studies.json
  python build_site.py --mode local --serve            # build, then open it in your web browser at http://127.0.0.1:<port>
  python build_site.py --serve                         # open an existing build (default build/local) without rebuilding

Use --serve rather than double-clicking index.html: macOS opens .html files with whatever app is set for them (sometimes
TextEdit or a preview window, which shows unstyled text because it runs no JavaScript). A localhost address always goes to
the default web browser. The server listens on 127.0.0.1 only and stops with Ctrl+C.

Needs: requirements-viz.txt (plotly, whose bundled plotly.min.js is copied in with its licence header), results_rerun/ from
reproduce.py and results_rerun/scenarios.csv from scenarios.py. Nothing is uploaded or deployed by this script."""
import argparse
import functools
import http.server
import json
import shutil
import webbrowser
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


def serve(folder, port=0):
    folder = Path(folder)
    if not (folder / "index.html").exists():
        raise SystemExit(f"{folder}/index.html not found; build it first, e.g. python build_site.py --mode local --serve")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    handler.log_message = lambda *a, **k: None
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/index.html"
        print(f"serving {folder}/ at {url}  (Ctrl+C to stop)", flush=True)
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("stopped")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["local", "public"])
    ap.add_argument("--tier", choices=["aggregate", "derived"], default="aggregate")
    ap.add_argument("--res", default="results_rerun")
    ap.add_argument("--docs", action="store_true")
    ap.add_argument("--serve", action="store_true", help="open the build in your web browser via a local address")
    ap.add_argument("--port", type=int, default=0, help="port for --serve (default: any free port)")
    a = ap.parse_args(argv)
    name = "local"
    if a.docs:
        data = site_export.build("local", res=a.res)
        Path("docs/CASE_STUDIES.md").write_text(site_export.case_markdown(data["cases"]))
        print("wrote docs/CASE_STUDIES.md")
    if a.mode:
        data = site_export.build(a.mode, a.tier, a.res)
        name = "local" if a.mode == "local" else ("public" if a.tier == "aggregate" else "public-derived")
        out = write_build(data, name)
        size = sum(f.stat().st_size for f in out.iterdir()) / 1e6
        print(f"wrote {out}/ ({size:.1f} MB)" + ("" if a.serve else f"; view it with: python build_site.py --mode {a.mode}{' --tier ' + a.tier if a.mode == 'public' and a.tier != 'aggregate' else ''} --serve"))
        if a.mode == "public":
            import check_public_build
            check_public_build.main([str(out)])
    if a.serve:
        serve(Path("build") / name, a.port)


if __name__ == "__main__":
    main()
