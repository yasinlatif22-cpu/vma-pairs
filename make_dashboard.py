"""Interactive research dashboard (one self-contained HTML file) built from completed runs.

  python make_dashboard.py [results_dir]        (default results_rerun) -> dashboard/vma_dashboard.html

Descriptive only: no strategy logic, no new tests. The page embeds CRSP-derived prices, so it is written to a git-ignored
folder; do not publish it unless your data licence allows redistribution of derived data. Needs plotly (requirements-viz.txt)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots

from config import DEFAULT
from data_io import load_market
from metrics import perf
from signals import build_signals

BG, PANEL, GRID, TXT = "#000000", "#0d0d0d", "#262626", "#d9d9d9"
AMBER, GREEN, RED, CYAN, MAG, GREY = "#ffa028", "#00d26a", "#ff3b30", "#2bc4ff", "#d96bff", "#8a8a8a"
REASON = {"target": GREEN, "z_stop": RED, "max_hold": AMBER, "window_end": GREY, "end_of_data": CYAN, "loss_limit": MAG}
PERIODS = {"dev": DEFAULT.dev, "val": DEFAULT.val, "holdout": DEFAULT.holdout}
FONT = "Consolas, Menlo, 'DejaVu Sans Mono', monospace"
CFG = {"displaylogo": False, "responsive": True}


def usd(x):
    return f"{'-' if x < 0 else ''}${abs(x):,.0f}"


def style(fig, h, title=None):
    fig.update_layout(height=h, paper_bgcolor=PANEL, plot_bgcolor=BG, font=dict(family=FONT, color=TXT, size=11),
                      margin=dict(l=60, r=30, t=95 if title else 50, b=40), legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, font=dict(size=10)),
                      hoverlabel=dict(bgcolor="#1a1a1a", font=dict(family=FONT, size=11)), title=dict(text=title, x=0.01, y=0.985, yanchor="top", font=dict(color=AMBER, size=13)))
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor="#444", showspikes=True, spikecolor=AMBER, spikethickness=1, spikedash="dot")
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#444", linecolor="#444")
    return fig


def load(res, period, fill="open_next", gate="none"):
    d = Path(res) / f"{period}_{gate}_{fill}"
    daily = pd.read_csv(d / "daily.csv", parse_dates=["date"], index_col="date")
    tr = pd.read_csv(d / "trades.csv", parse_dates=["signal_date", "entry_date", "exit_signal_date", "exit_date"])
    tr["period"] = period
    return daily, tr


def kpi(name, ret, daily_in_trade, ntr):
    p = perf(ret)
    cls = "pos" if p["sharpe"] > 0 else "neg"
    return (f'<div class="kpi"><div class="k">{name}</div><div class="v {cls}">{p["sharpe"]:.2f}</div><div class="s">Sharpe (total equity)</div>'
            f'<div class="r">ann ret {p["ann_ret"]:.2%} &middot; vol {p["ann_vol"]:.2%}<br>max DD {p["max_dd"]:.1%} &middot; trades {ntr}'
            f'{"" if daily_in_trade is None else f" &middot; in trade {daily_in_trade:.0%}"}</div></div>')


def master(close, daily, trades, zs, bench):
    ret = pd.concat([daily[p].ret for p in PERIODS])
    eq = 1e6 * (1 + ret).cumprod()
    bm = 1e6 * (1 + bench.reindex(ret.index).ffill().fillna(0)).cumprod()
    dd = eq / eq.cummax() - 1
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.025, row_heights=[0.34, 0.13, 0.27, 0.26])
    fig.add_trace(go.Scatter(x=eq.index, y=eq, name="Strategy (as run, cash earns 0)", line=dict(color=AMBER, width=1.6)), 1, 1)
    fig.add_trace(go.Scatter(x=bm.index, y=bm, name="T-bill on $1M (FF rf)", line=dict(color=CYAN, width=1.2, dash="dot")), 1, 1)
    fig.add_trace(go.Scatter(x=dd.index, y=dd * 100, name="Drawdown %", fill="tozeroy", line=dict(color=RED, width=1), fillcolor="rgba(255,59,48,.35)"), 2, 1)
    ix = close.loc[eq.index[0]:] / close.loc[eq.index[0]:].iloc[0] * 100
    fig.add_trace(go.Scatter(x=ix.index, y=ix[DEFAULT.y], name="V (indexed)", line=dict(color=CYAN, width=1.2)), 3, 1)
    fig.add_trace(go.Scatter(x=ix.index, y=ix[DEFAULT.x], name="MA (indexed)", line=dict(color=MAG, width=1.2)), 3, 1)
    fig.add_trace(go.Scatter(x=zs.index, y=zs, name="z-score", line=dict(color=GREY, width=1)), 4, 1)
    for y, col in [(DEFAULT.entry_z, AMBER), (-DEFAULT.entry_z, AMBER), (DEFAULT.stop_z, RED), (-DEFAULT.stop_z, RED), (0, "#555")]:
        fig.add_hline(y=y, line=dict(color=col, width=0.7, dash="dot"), row=4, col=1)
    for _, r in trades.iterrows():
        fig.add_vrect(x0=r.entry_date, x1=r.exit_date, row=3, col=1, fillcolor=GREEN if r.net_pnl > 0 else RED, opacity=0.18, line_width=0, layer="below")
    hov = lambda r: (f"{'long V / short MA' if r.side == 1 else 'short V / long MA'}<br>signal {r.signal_date.date()}  exit {r.exit_date.date()}<br>"
                     f"exit: {r.exit_reason}, {r.hold_sessions} sessions<br>net P&L {usd(r.net_pnl)}")
    fig.add_trace(go.Scatter(x=trades.signal_date, y=zs.reindex(trades.signal_date).values, mode="markers", name="entry signal",
                             marker=dict(symbol=np.where(trades.side == 1, "triangle-up", "triangle-down"), size=9, color=CYAN, line=dict(width=0.5, color="#000")),
                             text=[hov(r) for _, r in trades.iterrows()], hoverinfo="text"), 4, 1)
    for k, g in trades.groupby("exit_reason"):
        fig.add_trace(go.Scatter(x=g.exit_signal_date, y=zs.reindex(g.exit_signal_date).values, mode="markers", name=f"exit: {k}",
                                 marker=dict(symbol="circle", size=8, color=REASON.get(k, GREY), line=dict(width=0.5, color="#000")),
                                 text=[hov(r) for _, r in g.iterrows()], hoverinfo="text"), 4, 1)
    for x in (DEFAULT.val[0], DEFAULT.holdout[0]):
        fig.add_vline(x=pd.Timestamp(x).timestamp() * 1000, line=dict(color=AMBER, width=1, dash="dash"))
    fig.add_annotation(x=pd.Timestamp("2009-03-01"), y=1.0, xref="x", yref="y domain", text="DEV 2009-17", showarrow=False, font=dict(color=AMBER, size=10))
    fig.add_annotation(x=pd.Timestamp("2018-03-01"), y=1.0, xref="x", yref="y domain", text="VAL 2018-22", showarrow=False, font=dict(color=AMBER, size=10))
    fig.add_annotation(x=pd.Timestamp("2023-03-01"), y=1.0, xref="x", yref="y domain", text="HOLDOUT 2023-25 (spent)", showarrow=False, font=dict(color=AMBER, size=10))
    style(fig, 900, "EQUITY / DRAWDOWN / V & MA (log) / SPREAD Z-SCORE  |  shared time axis, drag to zoom")
    fig.update_yaxes(title_text="US$", row=1, col=1, tickformat=",.0f")
    fig.update_yaxes(title_text="DD %", row=2, col=1)
    fig.update_yaxes(title_text="indexed, log scale", type="log", tickvals=[100, 200, 500, 1000, 2000, 4000], ticktext=["100", "200", "500", "1000", "2000", "4000"], row=3, col=1)
    fig.update_yaxes(title_text="z", row=4, col=1, range=[-5.5, 5.5])
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.04, bgcolor="#111"), row=4, col=1)
    fig.update_xaxes(rangeselector=dict(buttons=[dict(count=1, label="1Y", step="year", stepmode="backward"), dict(count=3, label="3Y", step="year", stepmode="backward"),
                                                 dict(step="all", label="ALL")], bgcolor="#1a1a1a", activecolor=AMBER, font=dict(color=TXT), x=0.86, y=1.04), row=1, col=1)
    fig.update_layout(hovermode="x unified")
    return fig, ret


def scatter(trades):
    fig = go.Figure()
    for k, g in trades.groupby("exit_reason"):
        fig.add_trace(go.Scatter(x=g.hold_sessions, y=g.net_pnl, mode="markers", name=k,
                                 marker=dict(size=np.clip(abs(g.net_pnl) / 1500, 6, 30), color=REASON.get(k, GREY), opacity=0.8, line=dict(width=0.5, color="#000")),
                                 text=[f"{r.period} {r.signal_date.date()}<br>{'long V' if r.side == 1 else 'short V'}<br>{r.exit_reason}, {r.hold_sessions} sessions ({r.hold_calendar_days} cal. days)<br>net {usd(r.net_pnl)}"
                                       for _, r in g.iterrows()], hoverinfo="text"))
    fig.add_hline(y=0, line=dict(color="#666", width=1))
    style(fig, 420, "EVERY TRADE: NET P&L vs HOLD (sessions); bubble size = |P&L|")
    fig.update_xaxes(title_text="holding period, trading sessions")
    fig.update_yaxes(title_text="net P&L, US$", tickformat=",.0f")
    return fig


def pareto(trades):
    t = trades.sort_values("net_pnl", ascending=False).reset_index(drop=True)
    cp = {"dev": CYAN, "val": AMBER, "holdout": GREEN}
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=t.index + 1, y=t.net_pnl, marker_color=[cp[p] for p in t.period], name="trade net P&L",
                         text=[f"{r.period} {r.signal_date.date()}<br>{usd(r.net_pnl)}" for _, r in t.iterrows()], hoverinfo="text"), secondary_y=False)
    fig.add_trace(go.Scatter(x=t.index + 1, y=t.net_pnl.cumsum(), name="cumulative", line=dict(color=TXT, width=1.5)), secondary_y=True)
    fig.add_vrect(x0=0.5, x1=3.5, fillcolor=AMBER, opacity=0.12, line_width=0, annotation_text="top 3", annotation_font_color=AMBER)
    style(fig, 420, "CONCENTRATION: TRADES RANKED BY NET P&L (cyan dev, amber val, green holdout)")
    fig.update_yaxes(title_text="trade net P&L, US$", tickformat=",.0f", secondary_y=False, range=[-80000, 130000])
    fig.update_yaxes(title_text="cumulative, US$", tickformat=",.0f", secondary_y=True, showgrid=False, range=[-80000 * 8, 130000 * 8])
    fig.update_xaxes(title_text="rank")
    return fig


def fills(res):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.04)
    n = 0
    for p in ("dev", "val"):
        _, a = load(res, p, "open_next")
        _, b = load(res, p, "close_next")
        m = a.merge(b, on="signal_date", suffixes=("_o", "_c"))
        assert len(m) == len(a) == len(b)
        m = m.sort_values("exit_date_o")
        vis = p == "val"
        ca, cb = m.gross_pnl_o.cumsum(), m.gross_pnl_c.cumsum()
        fig.add_trace(go.Scatter(x=m.exit_date_o, y=ca, name="gross P&L, open fill", line=dict(color=AMBER, width=1.6, shape="hv"), visible=vis), 1, 1)
        fig.add_trace(go.Scatter(x=m.exit_date_o, y=cb, name="gross P&L, close fill", line=dict(color=CYAN, width=1.6, shape="hv"), visible=vis), 1, 1)
        fig.add_trace(go.Scatter(x=m.exit_date_o, y=ca - cb, name="open minus close", fill="tozeroy", line=dict(color=GREEN, width=1, shape="hv"),
                                 fillcolor="rgba(0,210,106,.25)", visible=vis), 2, 1)
        n += 3
    _, v = load(res, "val", "open_next")
    s = v[v.signal_date.isin(pd.to_datetime(["2020-03-16", "2020-03-20", "2020-03-25"]))]
    fig.add_vrect(x0=s.entry_date.min(), x1=s.exit_date.max(), fillcolor=RED, opacity=0.2, line_width=0, row=2, col=1,
                  annotation_text="3 March-2020 trades", annotation_font_color=RED, annotation_position="top left")
    vis = lambda k: [i // 3 == k for i in range(6)]
    fig.update_layout(updatemenus=[dict(type="buttons", direction="right", x=1.0, xanchor="right", y=1.0, yanchor="bottom", bgcolor="#1a1a1a", font=dict(color=AMBER),
                                        buttons=[dict(label="VAL 2018-22", method="update", args=[{"visible": vis(1)}]),
                                                 dict(label="DEV 2009-17", method="update", args=[{"visible": vis(0)}])])])
    style(fig, 520, "EXECUTION SENSITIVITY: CUMULATIVE GROSS P&L, OPEN FILL vs CLOSE FILL (same trades, only fill price differs)")
    fig.update_yaxes(tickformat=",.0f", title_text="US$", row=1, col=1)
    fig.update_yaxes(tickformat=",.0f", title_text="open - close", row=2, col=1)
    return fig


def heat(ret):
    m = (1 + ret).groupby([ret.index.year, ret.index.month]).prod() - 1
    t = m.unstack().reindex(columns=range(1, 13)) * 100
    fig = go.Figure(go.Heatmap(z=t.values, x=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], y=t.index.astype(str),
                               colorscale=[[0, RED], [0.5, "#111111"], [1, GREEN]], zmid=0, text=np.round(t.values, 2), texttemplate="%{text}",
                               hovertemplate="%{y} %{x}: %{z:.2f}%<extra></extra>", colorbar=dict(title="%", thickness=10), xgap=2, ygap=2))
    style(fig, 520, "MONTHLY RETURN, % OF TOTAL EQUITY")
    fig.update_yaxes(autorange="reversed", type="category")
    return fig


def rolling(ret, daily):
    it = pd.concat([daily[p].in_trade for p in PERIODS])
    rs = ret.rolling(252).mean() / ret.rolling(252).std() * np.sqrt(252)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=rs.index, y=rs, name="rolling 252d Sharpe", line=dict(color=AMBER, width=1.5)), secondary_y=False)
    fig.add_trace(go.Scatter(x=it.index, y=it.rolling(252).mean() * 100, name="% of days in a trade (252d)", line=dict(color=CYAN, width=1.2, dash="dot")), secondary_y=True)
    fig.add_hline(y=0, line=dict(color="#666", width=1))
    style(fig, 420, "ROLLING 252-DAY SHARPE (total equity) AND UTILISATION; descriptive, intervals include zero")
    fig.update_yaxes(title_text="Sharpe", secondary_y=False)
    fig.update_yaxes(title_text="in trade, %", secondary_y=True, showgrid=False, range=[0, 100])
    return fig


def cases(close, trades, earn):
    spec = [("2019-01-28", "VAL LOSER: long V / short MA"), ("2021-03-19", "VAL WINNER: long V / short MA"), ("2024-11-06", "HOLDOUT WORST: short V / long MA")]
    fig = make_subplots(rows=1, cols=3, subplot_titles=[s[1] for s in spec], horizontal_spacing=0.06)
    for k, (sd, _) in enumerate(spec, 1):
        sd = pd.Timestamp(sd)
        r = trades[trades.signal_date == sd].iloc[0]
        i0, i1 = close.index.get_loc(sd), close.index.get_loc(r.exit_date)
        w = close.iloc[max(i0 - 20, 0): i1 + 6]
        w = w / close.loc[sd] * 100
        fig.add_trace(go.Scatter(x=w.index, y=w[DEFAULT.y], name="V", line=dict(color=CYAN, width=1.6), showlegend=k == 1), 1, k)
        fig.add_trace(go.Scatter(x=w.index, y=w[DEFAULT.x], name="MA", line=dict(color=MAG, width=1.6), showlegend=k == 1), 1, k)
        fig.add_vrect(x0=r.entry_date, x1=r.exit_date, fillcolor=GREEN if r.net_pnl > 0 else RED, opacity=0.15, line_width=0, row=1, col=k)
        for tk, col in (("V", CYAN), ("MA", MAG)):
            for d in earn[(earn.tic == tk) & (earn.rdq >= w.index[0]) & (earn.rdq <= w.index[-1])].rdq:
                fig.add_vline(x=d.timestamp() * 1000, line=dict(color=col, width=1, dash="dot"), row=1, col=k)
        fig.layout.annotations[k - 1].update(text=f"{spec[k-1][1]}<br>signal {sd.date()} · {r.exit_reason} · net {usd(r.net_pnl)}", font=dict(color=AMBER, size=11))
    style(fig, 400, None)
    fig.update_layout(margin=dict(t=70), legend=dict(y=-0.15, yanchor="top"))
    fig.update_yaxes(title_text="signal day = 100", col=1)
    return fig


def main(res="results_rerun"):
    out = Path("dashboard")
    out.mkdir(exist_ok=True)
    _, close, _ = load_market("data/processed/market.csv", [DEFAULT.y, DEFAULT.x])
    daily, trl = {}, []
    for p in PERIODS:
        d, t = load(res, p)
        daily[p] = d
        trl.append(t)
    trades = pd.concat(trl, ignore_index=True)
    zl = []
    for p, (a, b) in PERIODS.items():
        sig, _ = build_signals(close.loc[:b], DEFAULT, close.index.searchsorted(pd.Timestamp(a)))
        zl.append(sig.loc[a:b, "z"])
    zs = pd.concat(zl)
    rf = pd.read_csv("data/raw/rf.csv", parse_dates=["date"]).set_index("date").rf
    earn = pd.read_csv("data/raw/earnings.csv", parse_dates=["rdq"])
    earn["tic"] = earn.gvkey.map({179534: "V", 160225: "MA"})

    f_master, ret = master(close, daily, trades, zs, rf)
    vh = pd.concat([daily["val"].ret, daily["holdout"].ret])
    tiles = "".join([kpi(f"{p.upper()} {PERIODS[p][0][:4]}-{PERIODS[p][1][2:4]}", daily[p].ret, daily[p].in_trade.mean(), int((trades.period == p).sum())) for p in PERIODS]
                    + [kpi("VAL+HOLDOUT 2018-25", vh, None, int(trades.period.isin(["val", "holdout"]).sum()))])
    parts = {k: f.to_html(full_html=False, include_plotlyjs=False, config=CFG, div_id=k) for k, f in {
        "master": f_master, "scatter": scatter(trades), "pareto": pareto(trades), "fills": fills(res), "heat": heat(ret),
        "roll": rolling(ret, daily), "cases": cases(close, trades, earn)}.items()}
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V/MA pairs research monitor</title><style>
body{{background:#000;color:{TXT};font-family:{FONT};margin:0;padding:14px 18px}}
header{{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid {AMBER};padding-bottom:6px;margin-bottom:12px}}
h1{{color:{AMBER};font-size:20px;margin:0;letter-spacing:1px}} .sub{{color:{GREY};font-size:12px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-bottom:12px}}
.kpi{{background:{PANEL};border:1px solid #333;border-left:3px solid {AMBER};padding:8px 12px}}
.k{{color:{AMBER};font-size:12px}} .v{{font-size:30px;font-weight:bold}} .pos{{color:{GREEN}}} .neg{{color:{RED}}} .s,.r{{color:{GREY};font-size:11px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} .full{{grid-column:1/-1}} .p{{background:{PANEL};border:1px solid #333}}
.note{{color:{GREY};font-size:11px;line-height:1.5;margin-top:14px;border-top:1px solid #333;padding-top:8px}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}</style>
<script>{get_plotlyjs()}</script></head><body>
<header><h1>V / MA PAIRS &mdash; RESEARCH MONITOR</h1><div class="sub">CRSP daily 2008-2025 &middot; walk-forward · costs, borrow, dividends modelled &middot; corrected-engine reproductions</div></header>
<div class="kpis">{tiles}</div>
<div class="grid"><div class="p full">{parts['master']}</div>
<div class="p">{parts['scatter']}</div><div class="p">{parts['pareto']}</div>
<div class="p full">{parts['fills']}</div>
<div class="p full">{parts['cases']}</div>
<div class="p">{parts['heat']}</div><div class="p">{parts['roll']}</div></div>
<div class="note">Descriptive monitor of completed evaluations. Holdout (2023-25) was run once and is spent; every 2009-2025 year has been examined. Returns are on
total equity with cash earning nothing, so they are not excess of T-bills; as run, the strategy did not beat T-bills in 2018-2025 (docs/RESULTS.md).
Intervals including zero, one pair, about six trades a year: this does not establish a persistent edge, and the open-fill result in validation leans on three March 2020 trades.
Equity panel: each period is an independent $1M run (capital and risk controls reset), stitched by compounding for display. Source: CRSP (WRDS), Compustat report dates, Fama-French risk-free rate. Derived data: do not redistribute without checking licence terms.</div>
</body></html>"""
    (out / "vma_dashboard.html").write_text(html)
    print("wrote dashboard/vma_dashboard.html", f"({len(html) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:])
