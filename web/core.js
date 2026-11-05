/* Pure logic for the research app: formatting, the decision-time information boundary, scenario lookup and a small
   Markdown renderer. No DOM access, so it runs in the browser and under Node tests (tests/web/core.test.js).
   The app never computes financial results itself: every number comes from the Python export. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.DeskCore = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const MINUS = "−";
  const ok = (x) => x !== null && x !== undefined && Number.isFinite(x);

  const fmt = {
    usd(x, sign = false) {
      if (!ok(x)) return "—";
      const s = Math.round(Math.abs(x)).toLocaleString("en-US");
      return (x < 0 ? MINUS + "$" : sign && x > 0 ? "+$" : "$") + s;
    },
    usdk(x, sign = false) {
      if (!ok(x)) return "—";
      const s = (Math.abs(x) / 1000).toFixed(1) + "k";
      return (x < 0 ? MINUS + "$" : sign && x > 0 ? "+$" : "$") + s;
    },
    pct(x, d = 1, sign = false) {
      if (!ok(x)) return "—";
      const v = (Math.abs(x) * 100).toFixed(d) + "%";
      return x < 0 ? MINUS + v : sign && x > 0 ? "+" + v : v;
    },
    num(x, d = 2, sign = false) {
      if (!ok(x)) return "—";
      const v = Math.abs(x).toFixed(d);
      return x < 0 ? MINUS + v : sign && x > 0 ? "+" + v : v;
    },
    side(s) { return s === 1 ? "long V / short MA" : "short V / long MA"; },
  };

  const PHASE = {
    before: "Before the signal",
    signal: "Signal at the close; order queued for the next open",
    pending: "Order pending",
    entry: "Entry filled at the open",
    hold: "Holding",
    exit_signal: "Exit signal at the close; order queued for the next open",
    exit: "Exit filled",
    after: "After the exit",
  };

  /* ---------------------------------------------------------------- information boundary
     Decision-time mode shows only what was observable at the cursor: rows up to the cursor, events dated on or before the
     cursor that belong to the decision-time record, no outcome-based colouring, no final P&L, no later developments and no
     trade label that reveals the result. Retrospective mode shows everything. */
  function visibleRows(rows, idx, mode) {
    if (mode === "retro") return rows.slice();
    return rows.slice(0, Math.max(0, Math.min(idx, rows.length - 1)) + 1);
  }

  function rowIndexOf(rows, date) {
    // first row on or after `date` (ISO strings compare lexically); -1 if the date is outside the replay window
    if (!date) return -1;
    for (let k = 0; k < rows.length; k++) if (rows[k].date >= date) return rows[k].date === date || k > 0 ? k : -1;
    return -1;
  }

  function buildEvents(trade, rows, kase) {
    const ev = [];
    const at = (phase) => rows.findIndex((r) => r.phase === phase);
    const push = (k, kind, text, category, extra) => { if (k >= 0) ev.push(Object.assign({ k, date: rows[k].date, kind, text, category }, extra || {})); };
    push(at("signal"), "signal", `Signal: |z| crossed the entry band; ${fmt.side(trade.side)} queued for the next open`, "model");
    push(at("entry"), "fill", "Entry filled at the open", "model");
    push(at("exit_signal"), "signal", "Exit signal at the close; order queued", "model");
    const xk = rows.findIndex((r) => r.phase === "exit");
    push(xk, "fill", `Exit filled (${(trade.exit_reason || "").replace("_", " ")})`, "model");
    if (kase) {
      (kase.annotations || []).forEach((a) => push(rowIndexOf(rows, a.date), a.kind, a.label, "dated"));
      (kase.later || []).forEach((l) => {
        const k = rowIndexOf(rows, l.date);
        ev.push({ k, date: l.date, kind: "later", text: l.text, category: "later", sources: l.sources || [] });
      });
    }
    return ev.sort((a, b) => (a.k < 0) - (b.k < 0) || a.k - b.k);
  }

  function visibleEvents(events, idx, mode) {
    if (mode === "retro") return events.slice();
    return events.filter((e) => e.category !== "later" && e.k >= 0 && e.k <= idx);
  }

  function tradeLabel(trade, mode) {
    const base = `${trade.signal_date} · ${fmt.side(trade.side)}`;
    if (mode !== "retro") return base;
    return `${base} · ${(trade.exit_reason || "").replace("_", " ")} · ${fmt.usd(trade.net_pnl)}`;
  }

  function frame(rows, trade, idx, mode) {
    const vis = visibleRows(rows, idx, mode);
    const cur = rows[Math.max(0, Math.min(idx, rows.length - 1))];
    const revealOutcome = mode === "retro";
    return {
      rows: vis,
      cur,
      phaseText: PHASE[cur.phase] || cur.phase,
      maxHold: trade.max_hold,
      outcome: revealOutcome ? { net: trade.net_pnl, exit_reason: trade.exit_reason } : null,
      colourByOutcome: revealOutcome,
    };
  }

  /* ---------------------------------------------------------------- scenarios */
  const BASELINE = { cost_bps: 5, borrow_bps: 30, fill_lag: 1, fill: "open_next", financing: "S0" };
  const CONTROL_METHOD = {
    cost_bps: "rerun", borrow_bps: "rerun", timing: "rerun", sample: "select", financing: "attribution",
  };
  const METHOD_TEXT = {
    rerun: "Selects a precomputed full engine rerun: costs, borrow and fill timing flow through equity, sizing and risk limits.",
    attribution: "Fixed-holdings financing attribution applied to the selected run: interest accrues to cash and never resizes positions.",
    select: "Selects which completed evaluation periods are summarised (independent runs; returns concatenated, not one account).",
  };

  function findScenario(grid, sel) {
    return grid.find((r) => r.sample === sel.sample && r.cost_bps === sel.cost_bps && r.borrow_bps === sel.borrow_bps &&
      r.fill_lag === sel.fill_lag && r.fill === sel.fill) || null;
  }

  function isBaseline(sel) {
    return Object.keys(BASELINE).every((k) => sel[k] === BASELINE[k]);
  }

  function scenarioView(grid, sel) {
    const rec = findScenario(grid, sel);
    const base = findScenario(grid, Object.assign({}, sel, BASELINE));
    if (!rec || !base) return null;
    const fin = sel.financing;
    const pick = (r) => ({
      net_pnl: r.net_pnl, mean_ann_ret: r.mean_ann_ret, cagr: r.cagr, ann_vol: r.ann_vol, sharpe: r.sharpe, max_dd: r.max_dd,
      trades: r.trades, utilization: r.utilization, excess_sharpe: r["excess_sharpe_" + fin], excess_ann: r["excess_ann_" + fin],
      cagr_fin: r["cagr_" + fin], costs: r.costs,
    });
    const a = pick(rec);
    const b = Object.assign(pick(base), { excess_sharpe: base.excess_sharpe_S0, excess_ann: base.excess_ann_S0, cagr_fin: base.cagr_S0 });
    const delta = {};
    Object.keys(a).forEach((k) => { delta[k] = ok(a[k]) && ok(b[k]) ? a[k] - b[k] : null; });
    return { rec, base, values: a, baseline: b, delta, isBaseline: isBaseline(sel) };
  }

  /* ---------------------------------------------------------------- Markdown (subset used in docs/) */
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function inline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, "$1");
  }
  function md(text) {
    const lines = text.replace(/\r/g, "").split("\n");
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const l = lines[i];
      if (/^```/.test(l)) {
        const buf = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) buf.push(esc(lines[i++]));
        i++; out.push(`<pre><code>${buf.join("\n")}</code></pre>`); continue;
      }
      const h = l.match(/^(#{1,4})\s+(.*)$/);
      if (h) { const n = Math.min(h[1].length + 1, 5); out.push(`<h${n}>${inline(h[2])}</h${n}>`); i++; continue; }
      if (/^\|/.test(l)) {
        const rows = [];
        while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
        const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const body = rows.filter((r) => !/^\|[\s|:-]+\|?$/.test(r));
        const head = cells(body[0]).map((c) => `<th>${inline(c)}</th>`).join("");
        const trs = body.slice(1).map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("");
        out.push(`<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${trs}</tbody></table></div>`); continue;
      }
      if (/^\s*[-*]\s+/.test(l) || /^\s*\d+\.\s+/.test(l)) {
        const ordered = /^\s*\d+\.\s+/.test(l);
        const items = [];
        while (i < lines.length && (/^\s*[-*]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]) || (/^\s{2,}\S/.test(lines[i]) && items.length))) {
          if (/^\s{2,}\S/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i])) items[items.length - 1] += " " + lines[i].trim();
          else items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
          i++;
        }
        const tag = ordered ? "ol" : "ul";
        out.push(`<${tag}>${items.map((x) => `<li>${inline(x)}</li>`).join("")}</${tag}>`); continue;
      }
      if (!l.trim()) { i++; continue; }
      const buf = [];
      while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|\||\s*[-*]\s+|\s*\d+\.\s+)/.test(lines[i])) buf.push(lines[i++]);
      out.push(`<p>${inline(buf.join(" "))}</p>`);
    }
    return out.join("\n");
  }

  return { fmt, PHASE, visibleRows, rowIndexOf, buildEvents, visibleEvents, tradeLabel, frame, BASELINE, CONTROL_METHOD, METHOD_TEXT,
           findScenario, isBaseline, scenarioView, md, esc };
});
