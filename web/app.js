/* V/MA Relative Value Desk. Renders the Python export in window.DESK_DATA. All financial numbers come from that export;
   this file only formats, filters and plots them (logic that matters for correctness lives in core.js and is unit-tested). */
(function () {
  "use strict";
  const D = window.DESK_DATA;
  const C = window.DeskCore;
  const F = C.fmt;
  const $ = (s, el = document) => el.querySelector(s);
  const h = (tag, attrs = {}, html = "") => { const e = document.createElement(tag); Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); e.innerHTML = html; return e; };
  const MONO = 'JetBrains Mono, SFMono-Regular, ui-monospace, Menlo, Consolas, monospace';
  const SANS = 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica Neue, Arial, sans-serif';
  const COL = { amber: "#f0a742", cyan: "#4cc3e3", violet: "#b18cf2", pos: "#3dbd84", neg: "#e5584f", grey: "#8b93a3", faint: "#3a4150", line: "#1b2029" };
  const REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const LOCAL = D.meta.mode === "local";
  const CASES = (D.cases && D.cases.cases) || [];
  const caseById = Object.fromEntries(CASES.map((c) => [c.id, c]));
  const state = { mode: "decision", tab: "overview", rendered: {}, replay: null, explorer: Object.assign({ sample: "val+holdout" }, C.BASELINE), metric: "sharpe", show3d: false };

  const CFG = { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"] };
  const AX = { gridcolor: COL.line, zerolinecolor: "#2a303b", linecolor: "#2a303b", tickfont: { family: MONO, size: 11, color: "#8b93a3" }, title: { font: { size: 11, color: "#8b93a3" } } };
  function layout(extra) {
    return Object.assign({
      paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "#0a0c10", font: { family: SANS, color: "#c9cdd6", size: 12 },
      margin: { l: 62, r: 18, t: 28, b: 38 }, showlegend: true, legend: { orientation: "h", y: 1.1, x: 0, font: { size: 11 }, bgcolor: "rgba(0,0,0,0)" },
      hoverlabel: { bgcolor: "#151922", bordercolor: "#2e3542", font: { family: MONO, size: 12, color: "#e7e9ee" } },
      transition: REDUCED ? { duration: 0 } : { duration: 0 },
    }, extra);
  }
  const ax = (extra) => Object.assign({}, AX, extra);
  const plot = (el, data, lay) => Plotly.react(el, data, lay, CFG);

  /* ---------------------------------------------------------------- shell */
  function initShell() {
    const badge = $("#modeBadge");
    badge.textContent = LOCAL ? "Local research mode" : `Public build · ${D.meta.tier}`;
    badge.className = "badge " + (LOCAL ? "local" : "public");
    if (!LOCAL) {
      const b = $("#publicBanner");
      b.hidden = false;
      b.innerHTML = `<strong>Public portfolio build (${D.meta.tier} tier).</strong> Contains no security prices, spread values, fills or holdings. ` +
        (D.meta.tier === "aggregate" ? "Period-level statistics, scenario aggregates, sourced case narratives and a clearly labelled synthetic replay only. " : "Adds the daily strategy equity series and trade outcomes without prices. ") +
        `Publication permissions are unresolved; see <a href="#" data-doc="DATA_PERMISSIONS.md">Data &amp; permissions</a>.`;
    }
    $(".foot").insertAdjacentHTML("beforeend", `<p style="margin:6px 0 0">Wharton Research Data Services (WRDS) was used in preparing this study. This service and the data available thereon constitute valuable intellectual property and trade secrets of WRDS and/or its third-party suppliers. Company facts are cited to their sources.</p>`);
    $("#footMeta").textContent = `build ${D.meta.mode}${LOCAL ? "" : "/" + D.meta.tier} · code ${D.meta.code} · spec ${D.meta.spec_hash} · generated ${D.meta.generated_utc}`;
    document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
    $(".tabs").addEventListener("keydown", (e) => {
      if (!["ArrowRight", "ArrowLeft"].includes(e.key)) return;
      const bs = [...document.querySelectorAll(".tabs button")];
      const i = bs.findIndex((b) => b.dataset.tab === state.tab);
      const n = bs[(i + (e.key === "ArrowRight" ? 1 : bs.length - 1)) % bs.length];
      showTab(n.dataset.tab); n.focus();
    });
    $("#evidenceBtn").addEventListener("click", () => openEvidence());
    $("#scrim").addEventListener("click", closeDrawers);
    document.addEventListener("click", (e) => { const a = e.target.closest("[data-doc]"); if (a) { e.preventDefault(); openEvidence(a.dataset.doc); } });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawers(); });
    const t = (location.hash || "").replace("#", "");
    showTab(["overview", "timeline", "replay", "cases", "explorer"].includes(t) ? t : "overview");
  }

  function showTab(tab) {
    state.tab = tab;
    document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    document.querySelectorAll(".tab").forEach((s) => { s.hidden = s.id !== "tab-" + tab; });
    if (history.replaceState) history.replaceState(null, "", "#" + tab);
    if (!state.rendered[tab]) { ({ overview: renderOverview, timeline: renderTimeline, replay: renderReplay, cases: renderCases, explorer: renderExplorer })[tab](); state.rendered[tab] = true; }
    else document.querySelectorAll(`#tab-${tab} .js-plotly-plot`).forEach((p) => Plotly.Plots.resize(p));
  }

  function setMode(m) {
    state.mode = m;
    document.querySelectorAll(".modeSwitch button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === m)));
    if (state.replay) drawReplay();
    if (state.rendered.cases) renderCaseCards();
    const panel = $("#casePanel");
    if (!panel.hidden && panel.dataset.case) openCase(panel.dataset.case);
    announce(m === "decision" ? "Decision-time view: only information available at the cursor is shown." : "Retrospective view: outcome and later information shown.");
  }
  function modeSwitch() {
    const w = h("div", { class: "modeSwitch", role: "group", "aria-label": "Information view" });
    [["decision", "Decision-time"], ["retro", "Retrospective"]].forEach(([m, t]) => {
      const b = h("button", { "data-mode": m, "aria-pressed": String(state.mode === m), type: "button" }, t);
      b.addEventListener("click", () => setMode(m)); w.appendChild(b);
    });
    return w;
  }
  function announce(t) { $("#live").textContent = t; }

  /* ---------------------------------------------------------------- overview */
  function renderOverview() {
    const s = D.stats, el = $("#tab-overview");
    const vh = s["val+holdout"];
    const scen = D.scenarios || [];
    const sc = (lag, fill) => C.findScenario(scen, { sample: "val+holdout", cost_bps: 5, borrow_bps: 30, fill_lag: lag, fill });
    const close1 = sc(1, "close_next");
    const below = vh.excess.S0.ann < 0;
    el.innerHTML = `
      <div class="panel verdict-panel">
        <h2>Conclusion</h2>
        <p class="lede verdict"><strong>Inconclusive.</strong> A fixed rule traded the Visa/Mastercard spread with next-session execution, costs, borrow and
        dividends. Each period shows a small positive total-equity Sharpe (${F.num(s.dev.sharpe)} development, ${F.num(s.val.sharpe)} validation,
        ${F.num(s.holdout.sharpe)} holdout), but outside the design period the intervals include zero${below ? ", the 2018–25 return trails T-bills as run" : ""}${close1 ? `, and the result depends on filling at the next open (2018–25 Sharpe ${F.num(sc(1, "open_next").sharpe)} at the open vs ${F.num(close1.sharpe)} at the next close)` : ""}.
        This sample does not establish a persistent edge.</p>
        <div class="chips"><span class="chip">total-equity returns, cash earns 0</span><span class="chip">signals at close t, fills at open t+1</span>
        <span class="chip">5 bps per leg per fill · 30 bps/yr borrow</span><span class="chip">spec ${D.meta.spec_hash}</span><span class="chip">holdout spent</span></div>
      </div>
      <div class="panel" style="margin-top:14px"><div class="four">
        <div><h3>What was tested</h3><p>One fixed pair, V and MA. A 252-session OLS log-price hedge refitted every 63 sessions; enter at |z| 2–4 on a
        60-day z-score, exit at 0.5, stop at 4, time stop at three formation half-lives.</p></div>
        <div><h3>How</h3><p>Walk-forward on CRSP daily data: development 2009–17, validation 2018–22, holdout 2023–25, each an independent
        $1M run. Share ledger with costs, borrow and dividends; trade P&amp;L must reconcile to equity or the run fails.</p></div>
        <div><h3>What the evidence says</h3><p>Small positive Sharpe in every period, market beta near zero, ${s.all.trades} trades in 17 years.
        ${below ? "Below T-bills in 2018–25 unless financing terms are favourable." : ""} Results concentrate in a few trades.</p></div>
        <div><h3>What remains uncertain</h3><p>Whether any edge exists; whether full-size opening fills were achievable in March 2020; real borrow and
        cash terms; hindsight in choosing the pair.</p></div></div></div>
      <div class="grid g4" id="sampleCards" style="margin-top:14px"></div>
      <div class="grid g2" style="margin-top:14px">
        <div class="panel"><h2>Sharpe with 95% intervals</h2><div id="forest" class="chart short" role="img" aria-label="Sharpe ratio point estimates with 95 percent block-bootstrap intervals for each sample"></div>
          <p class="small muted">Total-equity daily returns; circular block bootstrap with 21-day blocks. Declining point estimates across periods do not by themselves show a fading edge: the intervals overlap.</p></div>
        <div class="panel"><h2>Against T-bills</h2><div id="excess" class="chart short" role="img" aria-label="Excess Sharpe over T-bills under three financing scenarios"></div>
          <p class="small muted">S0 as run (cash earns nothing); S1 interest on free cash after funding longs and 50% short margin; S2 adds a rebate on short proceeds.
          Holdings are fixed as run; financing never resizes positions. Risk-free source: ${C.esc(D.meta.rf_source)}. Interest on cash neither establishes nor refutes trading skill.</p></div>
      </div>
      <div class="grid g2" style="margin-top:14px">
        <div class="panel"><h2>Execution sensitivity</h2><div id="execChart" class="chart short" role="img" aria-label="Sharpe by fill timing"></div>
          <p class="small muted" id="execText"></p></div>
        <div class="panel"><h2>Concentration and earnings (descriptive)</h2><div id="concTable"></div><p class="small muted" id="earnText"></p></div>
      </div>`;
    const cards = $("#sampleCards");
    [["dev", "Development"], ["val", "Validation"], ["holdout", "Holdout (spent)"], ["val+holdout", "Validation + holdout"]].forEach(([k, name]) => {
      const x = s[k];
      cards.appendChild(h("div", { class: "panel sample-card" }, `
        <h3><span>${name}</span><span class="faint mono">${x.trades} trades</span></h3><div class="dates">${x.start} → ${x.end}</div>
        <div class="kpi"><span class="label">Sharpe, total equity</span><span class="value">${F.num(x.sharpe)}</span>
        <span class="ci">95% [${F.num(x.sharpe_ci[0])}, ${F.num(x.sharpe_ci[1])}] · NW t ${F.num(x.nw_t)}</span></div>
        <div class="mini"><div><span>mean ann. return</span><b>${F.pct(x.mean_ann_ret)}</b></div><div><span>CAGR</span><b>${F.pct(x.cagr)}</b></div>
        <div><span>volatility</span><b>${F.pct(x.vol)}</b></div><div><span>max drawdown</span><b>${F.pct(x.max_dd)}</b></div>
        <div><span>days in a trade</span><b>${F.pct(x.utilization, 0)}</b></div><div><span>excess of T-bills (S0)</span><b>${F.pct(x.excess.S0.ann, 2, true)}</b></div></div>`));
    });
    const order = ["dev", "val", "holdout", "val+holdout", "all"];
    const names = { dev: "dev 2009–17", val: "val 2018–22", holdout: "holdout 2023–25", "val+holdout": "val+holdout", all: "all (incl. dev)" };
    plot($("#forest"), [{
      type: "scatter", mode: "markers", y: order.map((k) => names[k]), x: order.map((k) => s[k].sharpe), marker: { color: COL.amber, size: 9 },
      error_x: { type: "data", symmetric: false, array: order.map((k) => s[k].sharpe_ci[1] - s[k].sharpe), arrayminus: order.map((k) => s[k].sharpe - s[k].sharpe_ci[0]), color: COL.amber, thickness: 1.4, width: 4 },
      hovertemplate: "%{y}: Sharpe %{x:.2f}<extra></extra>", showlegend: false,
    }], layout({ margin: { l: 120, r: 18, t: 10, b: 36 }, xaxis: ax({ title: { text: "annualised Sharpe" }, zeroline: true, zerolinecolor: "#5b6372", zerolinewidth: 1.5 }),
      yaxis: ax({ autorange: "reversed" }) }));
    const sc3 = ["S0", "S1", "S2"], scName = { S0: "S0 as run", S1: "S1 interest", S2: "S2 + rebate" }, scCol = { S0: COL.grey, S1: COL.cyan, S2: COL.violet };
    plot($("#excess"), sc3.map((k) => ({
      type: "bar", name: scName[k], x: ["dev", "val", "holdout", "val+holdout"], y: ["dev", "val", "holdout", "val+holdout"].map((p) => s[p].excess[k].sharpe),
      marker: { color: scCol[k] }, hovertemplate: `%{x} ${scName[k]}: excess Sharpe %{y:.2f}<extra></extra>`,
    })), layout({ barmode: "group", margin: { l: 50, r: 10, t: 30, b: 36 }, yaxis: ax({ title: { text: "excess Sharpe vs T-bills" }, zeroline: true, zerolinecolor: "#5b6372" }), xaxis: ax({}) }));
    const ex = D.execution;
    if (scen.length) {
      const tl = ["t+1 open", "t+1 close", "t+2 open", "t+2 close", "t+3 open", "t+3 close"];
      const rows = tl.map((t) => scen.find((r) => r.sample === "val+holdout" && r.cost_bps === 5 && r.borrow_bps === 30 && r.timing === t));
      plot($("#execChart"), [{ type: "bar", x: tl, y: rows.map((r) => r.sharpe), marker: { color: tl.map((t) => (t === "t+1 open" ? COL.amber : "#3a4150")) },
        hovertemplate: "%{x}: Sharpe %{y:.2f}<extra></extra>", showlegend: false }],
        layout({ margin: { l: 50, r: 10, t: 10, b: 40 }, yaxis: ax({ title: { text: "2018–25 Sharpe (5 bps)" }, zeroline: true, zerolinecolor: "#5b6372" }), xaxis: ax({}) }));
    }
    $("#execText").innerHTML = `Fill timing after the signal close (exploratory engine reruns; amber = frozen specification). In validation the next-open fill
      added ${F.usdk(ex.val.diff, true)} gross over next-close fills on the same ${ex.val.trades} trades; three March 2020 trades account for
      ${F.usdk(ex.val.march2020)} and the other ${ex.val.rest_n} for ${F.usdk(ex.val.rest)}. In development the sign reverses (${F.usdk(ex.dev.diff, true)}).
      This sample does not establish a persistent opening-fill advantage.`;
    const cc = D.concentration;
    $("#concTable").innerHTML = `<div class="table-wrap"><table><thead><tr><th>sample</th><th class="num">trades</th><th class="num">net P&amp;L</th><th class="num">top 3 share of wins</th><th class="num">net excl. top 3</th></tr></thead><tbody>${
      ["dev", "val", "holdout", "all"].map((k) => `<tr><td>${k}</td><td class="num">${cc[k].trades}</td><td class="num">${F.usdk(cc[k].net)}</td><td class="num">${F.pct(cc[k].top3_share_of_wins, 0)}</td><td class="num ${cc[k].net_excl_top3 < 0 ? "neg" : ""}">${F.usdk(cc[k].net_excl_top3)}</td></tr>`).join("")}</tbody></table></div>`;
    const e = D.earnings.either;
    $("#earnText").innerHTML = `Sensitivity diagnostics, not alternative strategies. Earnings (post hoc, exploratory): trades held across a release gap averaged
      ${F.pct(e.mean_exposed, 2, true)} of entry equity (n=${e.n_exposed}) vs ${F.pct(e.mean_not, 2, true)} (n=${e.n_not}); difference ${F.pct(e.diff, 2, true)},
      95% [${F.pct(e.ci[0], 2, true)}, ${F.pct(e.ci[1], 2, true)}]. No earnings rule was added.`;
  }

  /* ---------------------------------------------------------------- timeline */
  function renderTimeline() {
    const el = $("#tab-timeline");
    if (!LOCAL) return renderPublicTimeline(el);
    el.innerHTML = `<div class="split">
      <div class="panel"><div class="toolbar"><h2 style="margin:0">Synchronized research timeline</h2><span class="spacer"></span>
        <button class="btn ghost" id="tlReset">Full history</button></div>
        <div id="tl" class="chart tall" role="img" aria-label="Linked charts of V and MA prices, spread z-score with signals, strategy equity and drawdown"></div>
        <div class="legend-note"><span><i style="background:${COL.amber}"></i>hollow markers on z = signals at the close</span>
        <span><i style="background:${COL.cyan}"></i>filled markers on prices = actual fills at the next open</span>
        <span><i style="background:#2e3542"></i>thin lines = hedge refit (every 63 sessions)</span><span>dashed amber = period reset ($1M)</span>
        <span>ticks at z = −4.8 = report dates (Compustat)</span></div></div>
      <div class="panel"><h2>Trades</h2><div class="toolbar"><div class="seg" role="radiogroup" aria-label="Period filter" id="tlFilter"></div></div>
        <div class="trade-list" id="tlList"></div><div id="tlDetail" style="margin-top:12px"></div></div></div>`;
    const T = D.timeline, dates = T.dates, idx = Object.fromEntries(dates.map((d, i) => [d, i]));
    const zAt = (d) => T.z[idx[d]];
    const trades = D.trades;
    const traces = [
      { x: dates, y: T.v, name: "V (split-adj.)", line: { color: COL.cyan, width: 1.2 }, yaxis: "y", hovertemplate: "V %{y:.2f}<extra></extra>" },
      { x: dates, y: T.ma, name: "MA (split-adj.)", line: { color: COL.violet, width: 1.2 }, yaxis: "y", hovertemplate: "MA %{y:.2f}<extra></extra>" },
      { x: trades.map((t) => t.entry_date), y: trades.map((t) => t.entry_px_v), mode: "markers", name: "entry fill V", yaxis: "y", showlegend: false,
        marker: { symbol: trades.map((t) => (t.side === 1 ? "triangle-up" : "triangle-down")), color: COL.cyan, size: 8, line: { width: 1, color: "#000" } },
        hovertemplate: "entry fill V %{y:.2f} (open)<extra></extra>" },
      { x: trades.map((t) => t.entry_date), y: trades.map((t) => t.entry_px_ma), mode: "markers", name: "entry fill MA", yaxis: "y", showlegend: false,
        marker: { symbol: trades.map((t) => (t.side === 1 ? "triangle-down" : "triangle-up")), color: COL.violet, size: 8, line: { width: 1, color: "#000" } },
        hovertemplate: "entry fill MA %{y:.2f} (open)<extra></extra>" },
      { x: trades.map((t) => t.exit_date), y: trades.map((t) => t.exit_px_v), mode: "markers", name: "exit fills", yaxis: "y",
        marker: { symbol: "square", color: COL.cyan, size: 6, line: { width: 1, color: "#000" } }, hovertemplate: "exit fill V %{y:.2f}<extra></extra>" },
      { x: trades.map((t) => t.exit_date), y: trades.map((t) => t.exit_px_ma), mode: "markers", name: "exit fill MA", yaxis: "y", showlegend: false,
        marker: { symbol: "square", color: COL.violet, size: 6, line: { width: 1, color: "#000" } }, hovertemplate: "exit fill MA %{y:.2f}<extra></extra>" },
      { x: dates, y: T.z, name: "spread z-score", line: { color: "#a9b0bd", width: 1 }, yaxis: "y2", hovertemplate: "z %{y:.2f}<extra></extra>", connectgaps: false },
      { x: trades.map((t) => t.signal_date), y: trades.map((t) => t.z_signal), mode: "markers", name: "entry signal (close)", yaxis: "y2",
        marker: { symbol: "circle-open", color: COL.amber, size: 9, line: { width: 2 } }, text: trades.map((t) => C.tradeLabel(t, "decision")), hovertemplate: "entry signal %{text}<extra></extra>" },
      { x: trades.map((t) => t.exit_signal_date), y: trades.map((t) => zAt(t.exit_signal_date)), mode: "markers", name: "exit signal (close)", yaxis: "y2",
        marker: { symbol: "diamond-open", color: COL.amber, size: 8, line: { width: 1.5 } }, text: trades.map((t) => t.exit_reason), hovertemplate: "exit signal: %{text}<extra></extra>" },
      { x: T.earnings.map((e) => e.date), y: T.earnings.map(() => -4.8), mode: "markers", name: "report dates", yaxis: "y2",
        marker: { symbol: "line-ns-open", color: T.earnings.map((e) => (e.ticker === "V" ? COL.cyan : COL.violet)), size: 9, line: { width: 1.5 } },
        text: T.earnings.map((e) => e.ticker + " results (Compustat report date)"), hovertemplate: "%{text}<extra></extra>" },
    ];
    Object.entries(T.equity).forEach(([p, s], k) => {
      traces.push({ x: s.dates, y: s.equity, name: k === 0 ? "strategy equity ($1M per period)" : p, showlegend: k === 0, legendgroup: "eq", line: { color: COL.amber, width: 1.4 }, yaxis: "y3", hovertemplate: `${p} equity %{y:$,.0f}<extra></extra>` });
      traces.push({ x: s.dates, y: s.drawdown.map((v) => v * 100), name: k === 0 ? "drawdown %" : p, showlegend: k === 0, legendgroup: "dd", fill: "tozeroy", line: { color: COL.neg, width: 1 }, fillcolor: "rgba(229,88,79,.25)", yaxis: "y4", hovertemplate: `${p} drawdown %{y:.1f}%<extra></extra>` });
    });
    const shapes = [];
    T.windows.forEach((w) => shapes.push({ type: "line", xref: "x", yref: "paper", x0: w, x1: w, y0: 0, y1: 1, line: { color: "#1d222c", width: 1 }, layer: "below" }));
    Object.values(D.meta.periods).forEach(([a]) => shapes.push({ type: "line", xref: "x", yref: "paper", x0: a, x1: a, y0: 0, y1: 1, line: { color: "#8a5f22", width: 1, dash: "dash" } }));
    trades.forEach((t) => shapes.push({ type: "rect", xref: "x", yref: "y domain", x0: t.entry_date, x1: t.exit_date, y0: 0, y1: 1, fillcolor: "rgba(240,167,66,.07)", line: { width: 0 }, layer: "below" }));
    const sp = D.meta.spec;
    [[sp.entry_z, COL.amber, "dot"], [-sp.entry_z, COL.amber, "dot"], [sp.exit_z, "#3a4150", "dot"], [-sp.exit_z, "#3a4150", "dot"], [sp.stop_z, COL.neg, "dash"], [-sp.stop_z, COL.neg, "dash"]]
      .forEach(([y, c, d]) => shapes.push({ type: "line", xref: "paper", yref: "y2", x0: 0, x1: 1, y0: y, y1: y, line: { color: c, width: 1, dash: d } }));
    const base = layout({
      height: undefined, hovermode: "x unified", hoversubplots: "axis", margin: { l: 66, r: 18, t: 36, b: 30 }, legend: { orientation: "h", y: 1.05, x: 0, font: { size: 10.5 } },
      xaxis: ax({ type: "date", anchor: "y4", showspikes: true, spikemode: "across", spikethickness: 1, spikecolor: "#5b6372", spikedash: "solid", rangeslider: { visible: false } }),
      yaxis: ax({ domain: [0.66, 1], type: "log", title: { text: "price (log)" } }),
      yaxis2: ax({ domain: [0.36, 0.63], range: [-5.2, 5.2], title: { text: "z" }, zeroline: false }),
      yaxis3: ax({ domain: [0.13, 0.33], title: { text: "equity" }, tickformat: "$.3s" }),
      yaxis4: ax({ domain: [0, 0.11], title: { text: "DD %" } }),
      shapes,
    });
    state.tl = { base, shapes, dates, idx };
    Plotly.newPlot($("#tl"), traces, base, CFG);
    $("#tlReset").addEventListener("click", () => focusRange(null));
    const filt = $("#tlFilter");
    ["all", "dev", "val", "holdout"].forEach((p, i) => {
      const b = h("button", { role: "radio", "aria-checked": String(i === 0), type: "button" }, p);
      b.addEventListener("click", () => { filt.querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", "false")); b.setAttribute("aria-checked", "true"); listTrades(p); });
      filt.appendChild(b);
    });
    listTrades("all");
    selectTrade("2019-01-28");
  }

  function focusRange(t) {
    const { base, shapes, dates, idx } = state.tl;
    if (!t) { Plotly.relayout($("#tl"), { "xaxis.autorange": true, "yaxis.autorange": true, "yaxis3.autorange": true, "yaxis4.autorange": true, shapes }); return; }
    const a = dates[Math.max(0, idx[t.signal_date] - 30)], b = dates[Math.min(dates.length - 1, idx[t.exit_date] + 20)];
    const hl = { type: "rect", xref: "x", yref: "paper", x0: t.signal_date, x1: t.exit_date, y0: 0, y1: 1, fillcolor: "rgba(76,195,227,.08)", line: { color: "rgba(76,195,227,.5)", width: 1 } };
    const ys = [];
    ["v", "ma"].forEach((k) => { for (let i = idx[a]; i <= idx[b]; i++) ys.push(D.timeline[k][i]); });
    const eq = [], dd = [];
    Object.values(D.timeline.equity).forEach((s) => s.dates.forEach((d, i) => { if (d >= a && d <= b) { eq.push(s.equity[i]); dd.push(s.drawdown[i] * 100); } }));
    const upd = { "xaxis.range": [a, b], shapes: shapes.concat([hl]), "yaxis.autorange": false,
      "yaxis.range": [Math.log10(Math.min(...ys) * 0.97), Math.log10(Math.max(...ys) * 1.03)] };
    if (eq.length) { const lo = Math.min(...eq), hi = Math.max(...eq), pad = Math.max((hi - lo) * 0.15, 2000); upd["yaxis3.range"] = [lo - pad, hi + pad]; upd["yaxis4.range"] = [Math.min(-1, Math.min(...dd) * 1.2), 0.5]; }
    Plotly.relayout($("#tl"), upd);
    void base;
  }

  function listTrades(period) {
    const rows = D.trades.filter((t) => period === "all" || t.period === period);
    $("#tlList").innerHTML = `<table><thead><tr><th>signal</th><th>side</th><th>exit</th><th class="num">sess.</th><th class="num">net</th></tr></thead><tbody>${
      rows.map((t) => `<tr class="clickable" tabindex="0" data-id="${t.id}"><td class="mono">${t.signal_date}${caseById[t.id] ? " ★" : ""}</td><td>${t.side === 1 ? "L V" : "S V"}</td>
        <td>${t.exit_reason.replace("_", " ")}</td><td class="num">${t.hold_sessions}</td><td class="num ${t.net_pnl < 0 ? "neg" : "pos"}">${F.usdk(t.net_pnl)}</td></tr>`).join("")}</tbody></table>`;
    $("#tlList").querySelectorAll("tr[data-id]").forEach((r) => {
      r.addEventListener("click", () => selectTrade(r.dataset.id));
      r.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectTrade(r.dataset.id); } });
    });
  }

  function selectTrade(id) {
    const t = D.trades.find((x) => x.id === id);
    if (!t) return;
    $("#tlList").querySelectorAll("tr").forEach((r) => r.classList.toggle("sel", r.dataset.id === id));
    const row = $("#tlList").querySelector(`tr[data-id="${id}"]`);
    if (row) { const list = $("#tlList"); list.scrollTop = row.offsetTop - list.clientHeight / 2; }
    focusRange(t);
    const kase = caseById[id];
    $("#tlDetail").innerHTML = `<h3 style="margin-top:0">${F.side(t.side)} · ${t.period}</h3>
      <div class="facts">
        <div><span>signal (close)</span><b>${t.signal_date}</b></div><div><span>entry fill (open)</span><b>${t.entry_date}</b></div>
        <div><span>exit signal (close)</span><b>${t.exit_signal_date}</b></div><div><span>exit fill</span><b>${t.exit_date}</b></div>
        <div><span>OLS hedge ratio</span><b>${F.num(t.beta)}</b></div><div><span>z at signal</span><b>${F.num(t.z_signal)}</b></div>
        <div><span>formation half-life</span><b>${F.num(t.half_life, 1)} sessions</b></div><div><span>held / max</span><b>${t.hold_sessions} / ${t.max_hold} sessions</b></div>
      </div>
      <div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>leg</th><th class="num">shares</th><th class="num">price</th><th class="num">div.</th><th class="num">costs</th></tr></thead><tbody>
      <tr><td>V</td><td class="num">${F.num(t.qty_v, 0)}</td><td class="num">${F.usd(t.v_price_pnl)}</td><td class="num">${F.usd(t.v_div)}</td><td class="num">${F.usd(-t.v_costs)}</td></tr>
      <tr><td>MA</td><td class="num">${F.num(t.qty_ma, 0)}</td><td class="num">${F.usd(t.ma_price_pnl)}</td><td class="num">${F.usd(t.ma_div)}</td><td class="num">${F.usd(-t.ma_costs)}</td></tr>
      <tr><td colspan="4">borrow fees</td><td class="num">${F.usd(-t.borrow)}</td></tr>
      <tr><td colspan="2"><b>net</b> · ${t.exit_reason.replace("_", " ")}</td><td colspan="3" class="num"><b class="${t.net_pnl < 0 ? "neg" : "pos"}">${F.usd(t.net_pnl)}</b> (${F.pct(t.pnl_pct, 2, true)} of entry equity)</td></tr>
      </tbody></table></div>
      <p class="small muted">Estimated market contribution (past-only betas V ${F.num(t.v_beta)}, MA ${F.num(t.ma_beta)}): V ${F.usd(t.v_market_est)}, MA ${F.usd(t.ma_market_est)}.
      Leg figures are re-derived from the market file and the recorded fills (diagnostics/trade_legs.py) and reconcile to the ledger to the cent.</p>
      <div class="toolbar"><button class="btn primary" id="tlReplay">Replay this trade</button>${kase ? '<button class="btn" id="tlCase">Research notes</button>' : ""}</div>`;
    $("#tlReplay").addEventListener("click", () => { showTab("replay"); loadReplay("real", id); });
    if (kase) $("#tlCase").addEventListener("click", () => openCase(id));
  }

  function renderPublicTimeline(el) {
    if (!D.equity) {
      el.innerHTML = `<div class="notice"><strong>Not in this build.</strong> The synchronized timeline plots V and MA prices, the spread z-score and fills,
        all derived from licensed CRSP data. This public build (aggregate tier) carries period-level results only. The local research mode shows the full timeline;
        the replay tab shows the same mechanics on clearly labelled synthetic data. See <a href="#" data-doc="DATA_PERMISSIONS.md">Data &amp; permissions</a>.</div>`;
      return;
    }
    el.innerHTML = `<div class="panel"><h2>Strategy equity and drawdown</h2><p class="small muted">Prices, spread and fills are omitted from public builds.</p><div id="tlPub" class="chart med"></div></div>`;
    const tr = [];
    Object.entries(D.equity).forEach(([p, s], k) => {
      tr.push({ x: s.dates, y: s.equity, name: k ? p : "equity ($1M per period)", showlegend: !k, line: { color: COL.amber, width: 1.4 }, yaxis: "y" });
      tr.push({ x: s.dates, y: s.drawdown.map((v) => v * 100), name: k ? p : "drawdown %", showlegend: !k, fill: "tozeroy", line: { color: COL.neg, width: 1 }, yaxis: "y2" });
    });
    plot($("#tlPub"), tr, layout({ hovermode: "x unified", xaxis: ax({ type: "date" }), yaxis: ax({ domain: [0.32, 1], tickformat: "$,.0f" }), yaxis2: ax({ domain: [0, 0.26], title: { text: "DD %" } }) }));
  }

  /* ---------------------------------------------------------------- replay */
  function replaySources() {
    if (LOCAL) return D.trades.map((t) => ({ kind: "real", id: t.id, trade: t, rows: D.replays[t.id] }));
    return (D.synthetic.replays || []).map((r) => ({ kind: "synthetic", id: r.trade.id, trade: r.trade, rows: r.rows }));
  }

  function renderReplay() {
    const el = $("#tab-replay");
    const synth = !LOCAL;
    el.innerHTML = `${synth ? `<div class="panel synthetic" style="margin-bottom:14px"><span class="synth-tag">SYNTHETIC</span>
        <p class="small" style="margin:8px 0 0">${C.esc(D.synthetic.label)} Real V/MA trade replays require the licensed price data and are available only in local research mode.</p></div>` : ""}
      <div class="panel ${synth ? "synthetic" : ""}">
        <div class="toolbar"><label class="sr-only" for="rpTrade">Trade</label><select id="rpTrade"></select><span id="rpMode"></span><span class="spacer"></span>
          <div class="transport" role="group" aria-label="Replay controls">
            <button class="btn" id="rpRestart" aria-label="Back to the signal (Home)">⏮</button>
            <button class="btn" id="rpBack" aria-label="Step back (Left arrow)">◀</button>
            <button class="btn primary" id="rpPlay" aria-label="Play (Space)">▶ Play</button>
            <button class="btn" id="rpFwd" aria-label="Step forward (Right arrow)">▶∣</button>
            <label class="small muted" for="rpSpeed">speed</label><select id="rpSpeed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select>
          </div></div>
        <p class="small muted" id="rpModeHelp" style="margin:0 0 8px"></p>
        <div class="replay-grid">
          <div><div id="rpChart" class="chart tall" role="img" aria-label="Replay chart: rebased prices, spread z-score and accumulating P&L up to the cursor"></div>
            <p class="small muted">x-axis: sessions relative to the signal close (0). Keys: Space play/pause, ←/→ step, Home back to the signal. The replay opens at the signal close; step back to see the run-up.</p></div>
          <div><div class="phase" id="rpPhase"></div><div class="table-wrap" style="margin-top:10px"><table class="ledger" id="rpLedger"></table></div>
            <div style="margin-top:10px" id="rpFlags"></div>
            <h3>Events</h3><ul class="events" id="rpEvents"></ul><div id="rpOutcome" style="margin-top:10px"></div></div>
        </div></div>`;
    $("#rpMode").appendChild(modeSwitch());
    const sel = $("#rpTrade");
    sel.addEventListener("change", () => { const [k, id] = sel.value.split("|"); loadReplay(k, id); });
    $("#rpRestart").addEventListener("click", () => stepTo(state.replay.start));
    $("#rpBack").addEventListener("click", () => stepTo(state.replay.idx - 1));
    $("#rpFwd").addEventListener("click", () => stepTo(state.replay.idx + 1));
    $("#rpPlay").addEventListener("click", togglePlay);
    $("#rpSpeed").addEventListener("change", () => { if (state.replay.timer) { togglePlay(); togglePlay(); } });
    document.addEventListener("keydown", (e) => {
      if (state.tab !== "replay" || ["SELECT", "INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
      if (e.key === " ") { e.preventDefault(); togglePlay(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); stepTo(state.replay.idx + 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); stepTo(state.replay.idx - 1); }
      else if (e.key === "Home") { e.preventDefault(); stepTo(state.replay.start); }
    });
    const first = LOCAL ? "2019-01-28" : replaySources()[0].id;
    loadReplay(LOCAL ? "real" : "synthetic", first);
  }

  function fillTradeSelect() {
    const sel = $("#rpTrade");
    const src = replaySources();
    const cases = src.filter((s) => caseById[s.id]), rest = src.filter((s) => !caseById[s.id]);
    const opt = (s) => `<option value="${s.kind}|${s.id}">${s.kind === "synthetic" ? "SYNTHETIC · " + (state.mode === "retro" ? `${s.trade.exit_reason.replace("_", " ")} · ${F.usd(s.trade.net_pnl)}` : F.side(s.trade.side)) + " · " + s.trade.signal_date : C.tradeLabel(s.trade, state.mode) + " · " + s.trade.period}</option>`;
    sel.innerHTML = (cases.length ? `<optgroup label="Case studies">${cases.map(opt).join("")}</optgroup><optgroup label="All trades">${rest.map(opt).join("")}</optgroup>` : src.map(opt).join(""));
    if (state.replay) sel.value = `${state.replay.kind}|${state.replay.id}`;
  }

  function loadReplay(kind, id) {
    stopPlay();
    const s = replaySources().find((x) => x.id === id) || replaySources()[0];
    const kase = caseById[s.id];
    const start = Math.max(0, s.rows.findIndex((x) => x.phase === "signal"));      // open at the decision: the signal close
    state.replay = { kind: s.kind, id: s.id, trade: s.trade, rows: s.rows, idx: start, start, timer: null, events: C.buildEvents(s.trade, s.rows, kase), kase };
    fillTradeSelect();
    drawReplay();
  }

  function stepTo(i) {
    const r = state.replay;
    const n = r.rows.length;
    r.idx = Math.max(0, Math.min(n - 1, i));
    if (r.idx === n - 1) stopPlay();
    drawReplay();
    const cur = r.rows[r.idx];
    announce(`Session ${cur.i >= 0 ? "+" : ""}${cur.i}, ${cur.date}: ${C.PHASE[cur.phase]}`);
  }
  function togglePlay() {
    const r = state.replay;
    if (r.timer) return stopPlay();
    if (r.idx >= r.rows.length - 1) r.idx = r.start;
    const speed = parseFloat($("#rpSpeed").value) || 1;
    r.timer = setInterval(() => stepTo(r.idx + 1), 900 / speed);
    $("#rpPlay").innerHTML = "❚❚ Pause"; $("#rpPlay").setAttribute("aria-label", "Pause (Space)");
  }
  function stopPlay() {
    const r = state.replay;
    if (r && r.timer) { clearInterval(r.timer); r.timer = null; }
    const b = $("#rpPlay"); if (b) { b.innerHTML = "▶ Play"; b.setAttribute("aria-label", "Play (Space)"); }
  }

  function drawReplay() {
    const r = state.replay; if (!r) return;
    fillTradeSelect();
    const t = r.trade, mode = state.mode;
    const fr = C.frame(r.rows, t, r.idx, mode);
    const rows = fr.rows, cur = fr.cur;
    const sig = r.rows.find((x) => x.phase === "signal");
    const v0 = sig.close_v, m0 = sig.close_ma;
    const xs = rows.map((x) => x.i);
    const entryRow = r.rows.find((x) => x.phase === "entry"), exitRow = r.rows.find((x) => x.phase === "exit");
    const seen = (row) => row && (mode === "retro" || row.i <= cur.i);
    const sp = D.meta.spec;
    const traces = [
      { x: xs, y: rows.map((x) => (x.close_v / v0) * 100), name: "V close (100 = signal)", line: { color: COL.cyan, width: 1.6 }, yaxis: "y", hovertemplate: "V %{y:.1f}<extra></extra>" },
      { x: xs, y: rows.map((x) => (x.close_ma / m0) * 100), name: "MA close", line: { color: COL.violet, width: 1.6 }, yaxis: "y", hovertemplate: "MA %{y:.1f}<extra></extra>" },
      { x: xs, y: rows.map((x) => x.z), name: "spread z", line: { color: "#a9b0bd", width: 1.4 }, yaxis: "y2", hovertemplate: "z %{y:.2f}<extra></extra>" },
      { x: xs, y: rows.map((x) => x.net), name: "net P&L to date", line: { color: COL.amber, width: 2 }, yaxis: "y3", hovertemplate: "net %{y:$,.0f}<extra></extra>" },
      { x: xs, y: rows.map((x) => x.pnl_v), name: "V leg", line: { color: COL.cyan, width: 1, dash: "dot" }, yaxis: "y3", hovertemplate: "V leg %{y:$,.0f}<extra></extra>" },
      { x: xs, y: rows.map((x) => x.pnl_ma), name: "MA leg", line: { color: COL.violet, width: 1, dash: "dot" }, yaxis: "y3", hovertemplate: "MA leg %{y:$,.0f}<extra></extra>" },
    ];
    const fills = [];
    if (seen(entryRow)) fills.push([entryRow.i, t.entry_px_v / v0 * 100, t.entry_px_ma / m0 * 100, "entry fill (open)", "triangle-up"]);
    if (seen(exitRow)) fills.push([exitRow.i, t.exit_px_v / v0 * 100, t.exit_px_ma / m0 * 100, "exit fill", "square"]);
    if (fills.length) {
      traces.push({ x: fills.map((f) => f[0]), y: fills.map((f) => f[1]), mode: "markers", name: "fills", yaxis: "y", text: fills.map((f) => f[3]), hovertemplate: "V %{text}<extra></extra>", marker: { symbol: fills.map((f) => f[4]), size: 11, color: COL.cyan, line: { width: 1.5, color: "#fff" } } });
      traces.push({ x: fills.map((f) => f[0]), y: fills.map((f) => f[2]), mode: "markers", name: "MA fills", showlegend: false, yaxis: "y", text: fills.map((f) => f[3]), hovertemplate: "MA %{text}<extra></extra>", marker: { symbol: fills.map((f) => f[4]), size: 11, color: COL.violet, line: { width: 1.5, color: "#fff" } } });
    }
    const sigs = rows.filter((x) => x.phase === "signal" || x.phase === "exit_signal");
    traces.push({ x: sigs.map((x) => x.i), y: sigs.map((x) => x.z), mode: "markers", name: "signals (close)", yaxis: "y2", marker: { symbol: "circle-open", size: 12, color: COL.amber, line: { width: 2 } }, hovertemplate: "signal at close<extra></extra>" });
    const shapes = [];
    [[sp.entry_z, COL.amber, "dot"], [-sp.entry_z, COL.amber, "dot"], [sp.exit_z, "#3a4150", "dot"], [-sp.exit_z, "#3a4150", "dot"], [sp.stop_z, COL.neg, "dash"], [-sp.stop_z, COL.neg, "dash"]]
      .forEach(([y, c, d]) => shapes.push({ type: "line", xref: "paper", yref: "y2", x0: 0, x1: 1, y0: y, y1: y, line: { color: c, width: 1, dash: d } }));
    if (entryRow && seen(entryRow)) {
      const lim = -sp.loss_limit * (t.equity_basis || 1e6);
      shapes.push({ type: "line", xref: "x", yref: "y3", x0: entryRow.i, x1: (mode === "retro" ? r.rows[r.rows.length - 1].i : cur.i) + 0.5, y0: lim, y1: lim, line: { color: COL.neg, width: 1, dash: "dash" } });
      const holdEnd = exitRow && seen(exitRow) ? exitRow.i : cur.i;
      shapes.push({ type: "rect", xref: "x", yref: "paper", x0: entryRow.i, x1: holdEnd, y0: 0, y1: 1, line: { width: 0 }, layer: "below",
        fillcolor: fr.colourByOutcome ? (t.net_pnl < 0 ? "rgba(229,88,79,.10)" : "rgba(61,189,132,.10)") : "rgba(76,195,227,.06)" });
    }
    shapes.push({ type: "line", xref: "x", yref: "paper", x0: cur.i, x1: cur.i, y0: 0, y1: 1, line: { color: "#e7e9ee", width: 1 } });
    const first = r.rows[0].i, last = r.rows[r.rows.length - 1].i;
    const xr = mode === "retro" ? [first - 0.5, last + 0.5] : [first - 0.5, Math.max(cur.i + 3, first + 12) + 0.5];
    const vis = mode === "retro" ? r.rows : rows;
    const pr = vis.flatMap((x) => [x.close_v / v0 * 100, x.close_ma / m0 * 100]).concat(fills.flatMap((f) => [f[1], f[2]]));
    const pn = vis.flatMap((x) => [x.net, x.pnl_v, x.pnl_ma]).concat([-sp.loss_limit * (t.equity_basis || 1e6) * (entryRow && seen(entryRow) ? 1 : 0)]);
    const pad = (a, b, f) => [a - (b - a) * f - 1e-9, b + (b - a) * f + 1e-9];
    plot($("#rpChart"), traces, layout({
      hovermode: "x unified", hoversubplots: "axis", margin: { l: 84, r: 16, t: 34, b: 36 }, legend: { orientation: "h", y: 1.06, x: 0, font: { size: 10.5 } },
      xaxis: ax({ range: xr, anchor: "y3", title: { text: "sessions from the signal close" }, zeroline: false, dtick: 5, showspikes: true, spikemode: "across", spikethickness: 1, spikecolor: "#5b6372" }),
      yaxis: ax({ domain: [0.62, 1], title: { text: "rebased" }, range: pad(Math.min(...pr), Math.max(...pr), 0.08) }),
      yaxis2: ax({ domain: [0.34, 0.58], range: [-5.2, 5.2], title: { text: "z" }, zeroline: false }),
      yaxis3: ax({ domain: [0, 0.3], title: { text: "P&L", standoff: 6 }, tickformat: "$,.0f", range: (() => { const lo = Math.min(0, ...pn), hi = Math.max(0, ...pn); return hi - lo < 2000 ? [lo - 1000, hi + 1000] : pad(lo, hi, 0.12); })() }),
      shapes,
    }));
    // ledger
    const held = cur.phase === "before" || cur.phase === "signal" || cur.phase === "pending" ? "—" : `${cur.held} of ${t.max_hold}`;
    $("#rpPhase").innerHTML = `<span class="mono faint">${cur.date} · session ${cur.i >= 0 ? "+" : ""}${cur.i}</span><br>${fr.phaseText}`;
    const inPos = !["before", "signal", "pending"].includes(cur.phase);
    $("#rpLedger").innerHTML = `<tbody>
      <tr><td>direction</td><td class="num">${F.side(t.side)}</td></tr>
      <tr><td>hedge ratio</td><td class="num">${F.num(t.beta)}</td></tr>
      <tr><td>z (entry ${sp.entry_z}, exit ${sp.exit_z}, stop ${sp.stop_z})</td><td class="num">${F.num(cur.z)}</td></tr>
      <tr><td>sessions held / max</td><td class="num">${held}</td></tr>
      <tr><td>V leg${inPos ? ` (${F.num(t.qty_v, 0)} sh)` : ""}</td><td class="num">${F.usd(cur.pnl_v)}</td></tr>
      <tr><td>MA leg${inPos ? ` (${F.num(t.qty_ma, 0)} sh)` : ""}</td><td class="num">${F.usd(cur.pnl_ma)}</td></tr>
      <tr><td>dividends</td><td class="num">${F.usd(cur.div)}</td></tr>
      <tr><td>transaction costs</td><td class="num">${F.usd(-cur.costs)}</td></tr>
      <tr><td>borrow fees</td><td class="num">${F.usd(-cur.borrow)}</td></tr>
      <tr><td><b>net P&amp;L to date</b></td><td class="num"><b>${F.usd(cur.net)}</b></td></tr>
      <tr><td>MTM vs loss limit (−${F.pct(sp.loss_limit, 0)})</td><td class="num">${inPos ? F.pct(cur.mtm_vs_limit, 2) : "—"}</td></tr></tbody>`;
    const az = Math.abs(cur.z || 0);
    const flags = [
      ["|z| ≥ stop", az >= sp.stop_z], ["in entry band", az >= sp.entry_z && az < sp.stop_z], ["at exit band", inPos && az <= sp.exit_z],
      ["held ≥ max", inPos && cur.held >= t.max_hold], ["MTM ≤ loss limit", inPos && cur.mtm_vs_limit <= -sp.loss_limit],
    ];
    $("#rpFlags").innerHTML = flags.map(([n, on]) => `<span class="flag ${on ? "on" : ""}">${n}</span>`).join(" ");
    const evs = C.visibleEvents(r.events, r.idx, mode);
    $("#rpEvents").innerHTML = evs.map((e) => `<li class="${e.category === "later" ? "later" : ""}"><span class="d">${e.k >= 0 ? `${e.date} · session ${r.rows[e.k].i >= 0 ? "+" : ""}${r.rows[e.k].i}` : `${e.date} · after the replay window`}${e.category === "later" ? " · later information" : ""}</span>${C.esc(e.text)}${
      (e.sources || []).map((s) => ` <a href="${s.url}" target="_blank" rel="noopener noreferrer">[${C.esc(s.title)}]</a>`).join("")}</li>`).join("") || `<li class="muted">No events yet.</li>`;
    const o = $("#rpOutcome");
    if (mode === "retro") {
      o.innerHTML = `<div class="panel" style="padding:10px 12px"><b>Outcome</b> · ${t.exit_reason.replace("_", " ")} after ${t.hold_sessions} sessions · net <b class="${t.net_pnl < 0 ? "neg" : "pos"}">${F.usd(t.net_pnl)}</b>
        ${r.kase ? `<div style="margin-top:6px"><button class="btn" id="rpCase">Research notes</button></div>` : ""}</div>`;
    } else {
      o.innerHTML = `<div class="hidden-in-decision">Decision-time view: the outcome, later developments and outcome colouring are hidden. Step forward to see what
        happened session by session, or switch to Retrospective.${r.kase ? ` <button class="btn" id="rpCase" style="margin-top:6px">Research notes (decision-time)</button>` : ""}</div>`;
    }
    const cb = $("#rpCase"); if (cb) cb.addEventListener("click", () => openCase(r.id));
    $("#rpModeHelp").textContent = mode === "decision"
      ? "Decision-time view: the chart, ledger and events stop at the cursor. Report dates appear only when they occur (pre-announcement was not verified)."
      : "Retrospective view: the full window, outcome colouring, final P&L and later developments are shown.";
  }

  /* ---------------------------------------------------------------- cases */
  function renderCases() {
    const el = $("#tab-cases");
    el.innerHTML = `<div class="panel" style="margin-bottom:14px"><h2>Case studies</h2><p class="small" style="margin:0">${C.esc(D.cases.selection_rule)}</p>
      <div class="toolbar" style="margin-top:10px"><span id="caseMode"></span><span class="small muted">The decision-time view hides outcomes and later information, including which case won or lost.</span></div></div>
      <div class="grid g3" id="caseCards"></div>`;
    $("#caseMode").appendChild(modeSwitch());
    renderCaseCards();
  }
  function renderCaseCards() {
    const el = $("#caseCards"); if (!el) return;
    el.innerHTML = CASES.map((c, n) => {
      const out = c.facts && c.facts.outcome;
      const retro = state.mode === "retro";
      return `<div class="panel"><h3 style="margin-top:0">Case ${n + 1} · signal ${c.id}</h3>
        <p class="mono small faint" style="margin:0">${F.side(c.side)} · ${c.period}${c.depth === "deep" ? " · deepened" : ""}</p>
        ${retro ? `<p style="margin:8px 0 0"><b>${C.esc(c.role)}</b>${out ? ` · net <b class="${out.net_pnl < 0 ? "neg" : "pos"}">${F.usd(out.net_pnl)}</b>` : ""}</p>` : ""}
        <p class="small" style="color:#c9cdd6">${C.esc(c.thesis)}</p>
        <div class="toolbar"><button class="btn primary" data-case="${c.id}">Open research panel</button>${LOCAL ? `<button class="btn" data-replay="${c.id}">Replay</button>` : ""}</div></div>`;
    }).join("");
    el.querySelectorAll("[data-case]").forEach((b) => b.addEventListener("click", () => openCase(b.dataset.case)));
    el.querySelectorAll("[data-replay]").forEach((b) => b.addEventListener("click", () => { showTab("replay"); loadReplay("real", b.dataset.replay); }));
  }

  function srcLink(s) { return s ? `<a href="${s.url}" target="_blank" rel="noopener noreferrer">${C.esc(s.title)}</a>` : ""; }
  function openCase(id) {
    const c = caseById[id]; if (!c) return;
    const p = $("#casePanel");
    p.dataset.case = id;
    const f = c.facts, retro = state.mode === "retro";
    const m = f && f.model, v = f && f.valuation, o = f && f.outcome;
    const decisionFacts = (c.decision_facts || []).slice().sort((a, b) => (a.date < b.date ? -1 : 1)).map((x) => `<li><span class="mono faint">${x.date}</span> ${C.esc(x.text)} <span class="src">(${srcLink(x.source)})</span></li>`).join("");
    p.innerHTML = `<button class="btn ghost close" id="cpClose" aria-label="Close panel">Close</button>
      <h2>Signal ${c.id} · ${F.side(c.side)}</h2><p class="mono small faint">${c.period}${retro ? " · " + C.esc(c.role) : ""}</p>
      <div id="cpMode" style="margin:8px 0"></div>
      <section><h3>Thesis and model state</h3><p>${C.esc(c.thesis)}</p>
        ${m ? `<p class="small mono">OLS log-price hedge ${F.num(m.beta)} · half-life ${F.num(m.half_life, 1)} sessions · Engle–Granger p ${F.num(m.eg_p)} (no cointegration evidence) · z ${F.num(m.z_signal)} · max hold ${m.max_hold} sessions</p>` : ""}
        ${f && f.signal_day ? `<p class="small muted">Signal day: V ${F.pct(f.signal_day.v, 1, true)}, MA ${F.pct(f.signal_day.ma, 1, true)}, market ${F.pct(f.signal_day.market, 1, true)}.</p>` : ""}</section>
      <section><h3>Decision-time facts</h3><ul>${decisionFacts || "<li class='muted'>None sourced beyond the model state.</li>"}</ul></section>
      <section><h3>Valuation and operating facts</h3>
        ${v ? `<p class="small muted">${C.esc(v.label)}</p><div class="table-wrap"><table><thead><tr><th></th><th class="num">V</th><th class="num">MA</th><th class="num">ratio</th></tr></thead><tbody>
          <tr><td>trailing P/E, reported EPS</td><td class="num">${F.num(v.v.pe, 1)}</td><td class="num">${F.num(v.ma.pe, 1)}</td><td class="num">${F.num(v.v.pe / v.ma.pe)}</td></tr>
          ${v.adjusted ? `<tr><td>trailing P/E, company-adjusted EPS (verified)</td><td class="num">${F.num(v.adjusted.v_pe, 1)}</td><td class="num">${F.num(v.adjusted.ma_pe, 1)}</td><td class="num">${F.num(v.adjusted.v_pe / v.adjusted.ma_pe)}</td></tr>` : ""}
          <tr><td>trailing revenue growth</td><td class="num">${F.pct(v.v.growth)}</td><td class="num">${F.pct(v.ma.growth)}</td><td></td></tr>
          <tr><td>operating margin</td><td class="num">${F.pct(v.v.margin)}</td><td class="num">${F.pct(v.ma.margin)}</td><td></td></tr>
          <tr><td>last report used</td><td class="num">${v.v.last_report}</td><td class="num">${v.ma.last_report}</td><td></td></tr></tbody></table></div>
          ${v.adjusted ? `<p class="small muted">${C.esc(v.adjusted.note)}</p>` : ""}` : `<p class="small muted">Computed valuation figures are not included in this build.</p>`}
        <p>${C.esc(c.valuation_reading)}</p><p class="small muted">${C.esc(D.cases.valuation_limits)}</p></section>
      <section><h3>Scheduled events</h3><p>${C.esc(c.scheduled_events)}</p></section>
      <section><h3>Catalyst and competing explanation</h3><p><b>Catalyst.</b> ${C.esc(c.catalyst)}</p><p><b>Competing explanation.</b> ${C.esc(c.competing)}</p></section>
      <section><h3>Invalidating condition</h3><p>${C.esc(c.invalidating)}</p></section>
      ${retro ? `
      <section><h3>Actual leg-level P&amp;L</h3>${o ? `<div class="table-wrap"><table><tbody>
          <tr><td>V price P&amp;L</td><td class="num">${F.usd(o.v_price_pnl)}</td><td>est. market</td><td class="num">${F.usd(o.v_market_est)}</td></tr>
          <tr><td>MA price P&amp;L</td><td class="num">${F.usd(o.ma_price_pnl)}</td><td>est. market</td><td class="num">${F.usd(o.ma_market_est)}</td></tr>
          <tr><td>dividends</td><td class="num">${F.usd(o.dividends)}</td><td>costs</td><td class="num">${F.usd(-o.costs)}</td></tr>
          <tr><td>borrow</td><td class="num">${F.usd(-o.borrow)}</td><td><b>net</b></td><td class="num"><b class="${o.net_pnl < 0 ? "neg" : "pos"}">${F.usd(o.net_pnl)}</b></td></tr></tbody></table></div>
          <p class="small muted">${o.exit_reason.replace("_", " ")} after ${o.hold_sessions} sessions (${o.hold_calendar_days} calendar days). Market estimate: past-only 252-session betas × entry notional × market return over the hold (approximate interval).</p>` : `<p class="small muted">Not included in this build.</p>`}
        <p>${C.esc(c.attribution_reading)}</p></section>
      <section><h3>Subsequent information</h3><ul>${(c.later || []).map((x) => `<li><span class="mono faint">${x.date}</span> ${C.esc(x.text)} ${(x.sources || []).map((s) => `<span class="src">(${srcLink(s)})</span>`).join(" ")}</li>`).join("")}</ul></section>
      <section><h3>What it establishes</h3><p>${C.esc(c.establishes)}</p><h3>What it does not establish</h3><p>${C.esc(c.does_not_establish)}</p></section>`
      : `<section><div class="hidden-in-decision">Outcome, leg-level P&amp;L, later developments and conclusions are hidden in the decision-time view. Switch to Retrospective to reveal them.</div></section>`}
      ${LOCAL ? `<div class="toolbar"><button class="btn primary" id="cpReplay">Replay this trade</button></div>` : ""}`;
    $("#cpMode").appendChild(modeSwitch());
    $("#cpClose").addEventListener("click", closeDrawers);
    const rb = $("#cpReplay"); if (rb) rb.addEventListener("click", () => { closeDrawers(); showTab("replay"); loadReplay("real", id); });
    openDrawer(p);
  }

  /* ---------------------------------------------------------------- explorer */
  const TIMINGS = [[1, "open_next", "t+1 open"], [1, "close_next", "t+1 close"], [2, "open_next", "t+2 open"], [2, "close_next", "t+2 close"], [3, "open_next", "t+3 open"], [3, "close_next", "t+3 close"]];
  const METRICS = { sharpe: ["Sharpe (total equity)", (x) => F.num(x)], excess_sharpe: ["Excess Sharpe vs T-bills", (x) => F.num(x)], mean_ann_ret: ["Mean annual return", (x) => F.pct(x, 2)],
    max_dd: ["Max drawdown (per run)", (x) => F.pct(x, 1)], trades: ["Trades", (x) => String(x)] };
  function renderExplorer() {
    const el = $("#tab-explorer");
    if (!D.scenarios) { el.innerHTML = `<div class="notice">Scenario grid not found: run <code>python scenarios.py</code> before building.</div>`; return; }
    el.innerHTML = `<div class="split ex-split">
      <div class="panel"><h2>Assumptions</h2><div id="exStatus"></div><div id="exControls"></div>
        <button class="btn" id="exReset" style="margin-top:6px">Reset to baseline</button>
        <p class="small muted" style="margin-top:12px">Computed after every period had been evaluated. Descriptive sensitivity only: no cell is selected and the best-looking cell is not a validated optimum.
        Each period is an independent $1M run; pooled samples concatenate daily returns.</p></div>
      <div><div class="panel"><h2>Result</h2><div id="exCards" class="grid g4"></div></div>
        <div class="panel" style="margin-top:14px"><div class="toolbar"><h2 style="margin:0">Cost × fill timing</h2><span class="spacer"></span>
          <label class="small muted" for="exMetric">metric</label><select id="exMetric">${Object.entries(METRICS).map(([k, v]) => `<option value="${k}">${v[0]}</option>`).join("")}</select>
          <button class="btn" id="ex3d" aria-pressed="false">3D surface</button></div>
          <p class="small muted" id="exNote" style="margin:0 0 6px"></p>
          <div id="exChart" class="chart med" role="img" aria-label="Heatmap of the selected metric across transaction cost and fill timing"></div></div></div></div>`;
    const groups = [
      ["sample", "Sample", ["dev", "val", "holdout", "val+holdout"], (x) => x],
      ["cost_bps", "Transaction cost (bps per leg per fill)", [0, 2.5, 5, 7.5, 10, 15, 20], (x) => String(x)],
      ["borrow_bps", "Borrow fee (bps a year on short value)", [0, 30, 100, 300], (x) => String(x)],
      ["timing", "Fill timing after the signal close", TIMINGS.map((t) => t[2]), (x) => x],
      ["financing", "Financing scenario", ["S0", "S1", "S2"], (x) => x],
    ];
    const ctr = $("#exControls");
    groups.forEach(([key, label, opts, lab]) => {
      const method = C.CONTROL_METHOD[key];
      const g = h("div", { class: "control" }, `<div class="lbl"><span>${label}</span><span class="method ${method}">${method === "rerun" ? "engine rerun" : method === "attribution" ? "fixed-holdings attribution" : "sample"}</span></div>`);
      const seg = h("div", { class: "seg", role: "radiogroup", "aria-label": label });
      opts.forEach((o) => {
        const b = h("button", { role: "radio", type: "button", "data-key": key, "data-val": String(o) }, lab(o));
        b.addEventListener("click", () => { setSel(key, o); });
        seg.appendChild(b);
      });
      g.appendChild(seg);
      g.appendChild(h("div", { class: "small muted" }, C.METHOD_TEXT[method]));
      ctr.appendChild(g);
    });
    $("#exReset").addEventListener("click", () => { Object.assign(state.explorer, C.BASELINE); drawExplorer(); });
    $("#exMetric").addEventListener("change", (e) => { state.metric = e.target.value; drawExplorer(); });
    const webgl = (() => { try { const c = document.createElement("canvas"); return !!(c.getContext("webgl") || c.getContext("experimental-webgl")); } catch (e) { return false; } })();
    const b3 = $("#ex3d");
    if (!webgl) { b3.disabled = true; b3.title = "3D needs WebGL; the 2D heatmap shows the same values"; }
    b3.addEventListener("click", () => { state.show3d = !state.show3d; b3.setAttribute("aria-pressed", String(state.show3d)); drawExplorer(); });
    drawExplorer();
  }
  function setSel(key, val) {
    const e = state.explorer;
    if (key === "timing") { const t = TIMINGS.find((x) => x[2] === val); e.fill_lag = t[0]; e.fill = t[1]; }
    else e[key] = val;
    drawExplorer();
  }
  function drawExplorer() {
    const e = state.explorer;
    const timingLabel = TIMINGS.find((t) => t[0] === e.fill_lag && t[1] === e.fill)[2];
    document.querySelectorAll("#exControls button").forEach((b) => {
      const k = b.dataset.key, v = b.dataset.val;
      const cur = k === "timing" ? timingLabel : String(e[k]);
      b.setAttribute("aria-checked", String(cur === v));
    });
    const view = C.scenarioView(D.scenarios, e);
    if (!view) return;
    $("#exStatus").innerHTML = view.isBaseline
      ? `<div class="banner" style="margin:0 0 12px;border-color:#8a5f22;background:#1b150b;color:#ffd79c"><b>PUBLISHED SPECIFICATION</b> · the frozen baseline (spec ${D.meta.spec_hash}).</div>`
      : `<div class="banner" style="margin:0 0 12px"><b>EXPLORATORY SCENARIO</b> · not the published specification. Differences are against the baseline for the same sample.</div>`;
    const v = view.values, b = view.baseline, d = view.delta;
    const card = (label, val, delta, f, note) => `<div class="kpi"><span class="label">${label}</span><span class="value" style="font-size:20px">${f(val)}</span>
      <span class="ci">${view.isBaseline ? "baseline" : `Δ ${delta == null ? "—" : (delta > 0 ? "+" : delta < 0 ? "−" : "") + f(Math.abs(delta)).replace("−", "")}`}${note ? " · " + note : ""}</span></div>`;
    $("#exCards").innerHTML = [
      card("net P&L", v.net_pnl, d.net_pnl, (x) => F.usdk(x)),
      card("mean annual return", v.mean_ann_ret, d.mean_ann_ret, (x) => F.pct(x, 2), "total equity"),
      card("CAGR", v.cagr, d.cagr, (x) => F.pct(x, 2), "total equity"),
      card("Sharpe", v.sharpe, d.sharpe, (x) => F.num(x), "total equity; not risk-free adjusted"),
      card("max drawdown", v.max_dd, d.max_dd, (x) => F.pct(x, 1), "worst single run"),
      card("trades", v.trades, d.trades, (x) => String(Math.round(x))),
      card("days in a trade", v.utilization, d.utilization, (x) => F.pct(x, 0)),
      card(`excess Sharpe vs T-bills (${e.financing})`, v.excess_sharpe, d.excess_sharpe, (x) => F.num(x), "financing attribution"),
    ].join("");
    // grid for chart
    const costs = [0, 2.5, 5, 7.5, 10, 15, 20];
    const metricKey = state.metric === "excess_sharpe" ? "excess_sharpe_" + e.financing : state.metric;
    const z = costs.map((c) => TIMINGS.map(([lag, fill]) => {
      const r = C.findScenario(D.scenarios, { sample: e.sample, cost_bps: c, borrow_bps: e.borrow_bps, fill_lag: lag, fill });
      return r ? r[metricKey] : null;
    }));
    const xl = TIMINGS.map((t) => t[2]);
    const [mname] = METRICS[state.metric];
    $("#exNote").textContent = `${mname}, sample ${e.sample}, borrow ${e.borrow_bps} bps${state.metric === "excess_sharpe" ? ", financing " + e.financing : ""}. Every cell is an engine rerun. Amber frame = published baseline; white frame = current selection. Exploratory.`;
    const bi = [xl.indexOf("t+1 open"), costs.indexOf(5)];
    const si = [xl.indexOf(timingLabel), costs.indexOf(e.cost_bps)];
    const div = $("#exChart");
    if (state.show3d && !$("#ex3d").disabled) {
      Plotly.react(div, [
        { type: "surface", x: xl.map((_, i) => i), y: costs, z, colorscale: [[0, "#1f2b3a"], [0.5, "#3a6f86"], [1, "#f0a742"]], showscale: true,
          colorbar: { title: { text: mname, side: "right" }, tickfont: { family: MONO, size: 10, color: "#8b93a3" }, len: 0.7 }, hovertemplate: "cost %{y} bps<br>timing index %{x}<br>%{z:.3f}<extra></extra>", opacity: 0.95 },
        { type: "scatter3d", mode: "markers+text", x: [bi[0]], y: [5], z: [z[bi[1]][bi[0]]], text: ["baseline"], textfont: { color: "#ffd79c", size: 11 }, marker: { size: 5, color: "#ffd79c" }, hoverinfo: "skip", showlegend: false },
      ], layout({ margin: { l: 0, r: 0, t: 10, b: 0 }, showlegend: false,
        scene: { bgcolor: "#0a0c10", camera: { eye: { x: 1.6, y: -1.6, z: 0.9 } },
          xaxis: { title: { text: "fill timing" }, tickvals: xl.map((_, i) => i), ticktext: xl, color: "#8b93a3", gridcolor: "#1b2029" },
          yaxis: { title: { text: "cost (bps)" }, color: "#8b93a3", gridcolor: "#1b2029" },
          zaxis: { title: { text: mname }, color: "#8b93a3", gridcolor: "#1b2029" } } }), CFG);
    } else {
      const flat = z.flat().filter((x) => x != null);
      const narrow = div.clientWidth < 560;
      const zmid = ["sharpe", "excess_sharpe", "mean_ann_ret"].includes(state.metric) ? 0 : undefined;
      Plotly.react(div, [
        { type: "heatmap", x: xl, y: costs.map(String), z, zmid, colorscale: [[0, "#9c3b35"], [0.5, "#11151c"], [1, "#2a7d58"]], xgap: 2, ygap: 2,
          text: z.map((row) => row.map((x) => (x == null ? "" : METRICS[state.metric][1](x)))), texttemplate: narrow ? "" : "%{text}", textfont: { family: MONO, size: 12, color: "#f2f4f7" },
          hovertemplate: "timing %{x}<br>cost %{y} bps<br>" + mname + " %{text}<extra></extra>", colorbar: { tickfont: { family: MONO, size: 10, color: "#8b93a3" }, thickness: 10 },
          zmin: zmid === 0 ? -Math.max(...flat.map(Math.abs)) : undefined, zmax: zmid === 0 ? Math.max(...flat.map(Math.abs)) : undefined },
        { type: "scatter", mode: "markers", x: [xl[bi[0]]], y: ["5"], marker: { symbol: "square-open", size: 46, color: "#f0a742", line: { width: 3 } }, hovertemplate: "published baseline<extra></extra>", showlegend: false },
        { type: "scatter", mode: "markers", x: [xl[si[0]]], y: [String(e.cost_bps)], marker: { symbol: "square-open-dot", size: 36, color: "#e7e9ee", line: { width: 1.5 } }, hoverinfo: "skip", showlegend: false },
      ], layout({ margin: { l: 56, r: 10, t: 10, b: narrow ? 70 : 40 }, xaxis: ax({ title: { text: narrow ? "" : "fill timing after the signal close" }, type: "category", tickangle: narrow ? -45 : 0 }), yaxis: ax({ title: { text: "cost, bps per leg per fill" }, type: "category" }) }), CFG);
      div.removeAllListeners && div.removeAllListeners("plotly_click");
      div.on("plotly_click", (ev) => { const p = ev.points[0]; if (!p || p.data.type !== "heatmap") return; setSel("cost_bps", parseFloat(p.y)); setSel("timing", p.x); });
    }
  }

  /* ---------------------------------------------------------------- drawers */
  function openDrawer(el) {
    $("#casePanel").hidden = el.id !== "casePanel" ? true : $("#casePanel").hidden;
    el.hidden = false; $("#scrim").hidden = false;
    el.querySelector("button, a") && el.querySelector("button, a").focus({ preventScroll: true });
    if (el.id === "evidence") $("#evidenceBtn").setAttribute("aria-expanded", "true");
  }
  function closeDrawers() {
    ["#casePanel", "#evidence"].forEach((s) => { $(s).hidden = true; });
    $("#scrim").hidden = true; $("#evidenceBtn").setAttribute("aria-expanded", "false");
  }
  function openEvidence(doc) {
    const ev = $("#evidence");
    const docs = D.docs || {};
    const names = { "CONCLUSION.md": "Conclusion", "RESULTS.md": "Results & uncertainty", "METHODOLOGY.md": "Assumptions & definitions", "DATA_PERMISSIONS.md": "Data & permissions",
      "CORRECTIONS.md": "Corrections", "ACCOUNTING_AUDIT.md": "Accounting audit", "PROVENANCE.md": "Provenance", "DATA.md": "Data & reproduction" };
    const keys = Object.keys(names).filter((k) => docs[k]);
    const sel = doc && docs[doc] ? doc : "__build";
    ev.innerHTML = `<button class="btn ghost close" id="evClose" aria-label="Close">Close</button><h2>Evidence &amp; methods</h2>
      <p class="small muted">The full documentation behind every number, rendered from the repository's docs/ folder.</p>
      <div class="doctabs" role="tablist"><button class="btn ${sel === "__build" ? "primary" : ""}" data-ev="__build">This build</button>${keys.map((k) => `<button class="btn ${k === sel ? "primary" : ""}" data-ev="${k}">${names[k]}</button>`).join("")}</div>
      <div class="doc" id="evBody"></div>`;
    const body = $("#evBody");
    if (sel === "__build") {
      const m = D.meta;
      body.innerHTML = `<h3>This build</h3><div class="table-wrap"><table><tbody>
        <tr><td>mode</td><td class="mono">${m.mode}${m.mode === "public" ? " · " + m.tier + " tier" : ""}</td></tr>
        <tr><td>code version</td><td class="mono">${m.code}</td></tr><tr><td>specification hash</td><td class="mono">${m.spec_hash}</td></tr>
        <tr><td>generated (UTC)</td><td class="mono">${m.generated_utc}</td></tr><tr><td>risk-free source</td><td>${C.esc(m.rf_source)}</td></tr>
        <tr><td>periods</td><td class="mono">${Object.entries(m.periods).map(([k, v]) => `${k} ${v[0]} → ${v[1]}`).join("<br>")}</td></tr>
        ${m.input_checksums ? `<tr><td>input files (SHA-256, first 16)</td><td class="mono small">${Object.entries(m.input_checksums).map(([k, v]) => `${k}: ${v}`).join("<br>")}</td></tr>` : ""}
        </tbody></table></div>
        <h3>Reproduce</h3><pre><code>pip install -r requirements.txt -r requirements-viz.txt
python -m pytest
python reproduce.py            # completed evaluations, labelled reproductions (licensed data)
python scenarios.py            # exploratory engine-rerun grid
python build_site.py --mode local --serve    # this app with your licensed files, opened in your browser
python build_site.py --mode public --serve   # allow-listed public build</code></pre>`;
    } else body.innerHTML = C.md(docs[sel]);
    ev.querySelectorAll("[data-ev]").forEach((b) => b.addEventListener("click", () => openEvidence(b.dataset.ev === "__build" ? null : b.dataset.ev)));
    $("#evClose").addEventListener("click", closeDrawers);
    openDrawer(ev);
  }

  const noapp = document.getElementById("noapp");
  if (noapp) noapp.remove();                       // the app is running: drop the fallback notice
  initShell();
})();
