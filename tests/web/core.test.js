// Unit tests for web/core.js: the decision-time information boundary and scenario lookup. Run: node --test tests/web/
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const C = require(process.env.CORE_JS || path.join(__dirname, "..", "..", "web", "core.js"));

const rows = [
  { i: -2, date: "2019-01-24", phase: "before", net: 0 },
  { i: -1, date: "2019-01-25", phase: "before", net: 0 },
  { i: 0, date: "2019-01-28", phase: "signal", net: 0 },
  { i: 1, date: "2019-01-29", phase: "entry", net: -900 },
  { i: 2, date: "2019-01-30", phase: "hold", net: -4000 },
  { i: 3, date: "2019-01-31", phase: "exit_signal", net: -31000 },
  { i: 4, date: "2019-02-01", phase: "exit", net: -32290 },
  { i: 5, date: "2019-02-04", phase: "after", net: -32290 },
];
const trade = { side: 1, signal_date: "2019-01-28", exit_reason: "z_stop", net_pnl: -32290, max_hold: 34 };
const kase = {
  annotations: [{ date: "2019-01-30", kind: "earnings", label: "Visa results" }, { date: "2019-01-31", kind: "earnings", label: "Mastercard results" }],
  later: [{ date: "2019-01-30", text: "Visa CFO described slowing growth", sources: [] }, { date: "2024-09-24", text: "a lawsuit years later", sources: [] }],
};

test("decision-time rows stop at the cursor; retrospective shows all", () => {
  for (let idx = 0; idx < rows.length; idx++) {
    const vis = C.visibleRows(rows, idx, "decision");
    assert.equal(vis.length, idx + 1);
    assert.ok(vis.every((r) => r.date <= rows[idx].date));
  }
  assert.equal(C.visibleRows(rows, 2, "retro").length, rows.length);
});

test("no event dated after the cursor and no later-information event in decision-time mode", () => {
  const ev = C.buildEvents(trade, rows, kase);
  for (let idx = 0; idx < rows.length; idx++) {
    const vis = C.visibleEvents(ev, idx, "decision");
    assert.ok(vis.every((e) => e.k <= idx && e.date <= rows[idx].date), `leak at idx ${idx}`);
    assert.ok(vis.every((e) => e.category !== "later"));
  }
  // at the signal close the reports have not happened yet: nothing about them is visible
  const atSignal = C.visibleEvents(ev, 2, "decision");
  assert.ok(!atSignal.some((e) => /Visa results|Mastercard results/.test(e.text)));
  // retrospective reveals later information, including events outside the replay window
  const retro = C.visibleEvents(ev, 2, "retro");
  assert.ok(retro.some((e) => e.category === "later" && e.k === -1));
});

test("decision-time labels and frames reveal no outcome", () => {
  const label = C.tradeLabel(trade, "decision");
  assert.ok(!/z.stop|32,290|-|−\$/.test(label.replace(/\d{4}-\d{2}-\d{2}/, "")), label);
  const f = C.frame(rows, trade, 2, "decision");
  assert.equal(f.outcome, null);
  assert.equal(f.colourByOutcome, false);
  assert.ok(f.rows.every((r) => r.net === 0));
  const r = C.frame(rows, trade, 2, "retro");
  assert.equal(r.outcome.net, -32290);
  assert.match(C.tradeLabel(trade, "retro"), /z stop/);
});

test("scenario lookup returns the baseline and labels exploratory selections", () => {
  const grid = [
    { sample: "val", cost_bps: 5, borrow_bps: 30, fill_lag: 1, fill: "open_next", sharpe: 0.47, excess_sharpe_S0: 0.1, excess_sharpe_S1: 0.4 },
    { sample: "val", cost_bps: 10, borrow_bps: 30, fill_lag: 1, fill: "open_next", sharpe: 0.3, excess_sharpe_S0: -0.1, excess_sharpe_S1: 0.2 },
  ];
  const base = C.scenarioView(grid, Object.assign({ sample: "val" }, C.BASELINE));
  assert.equal(base.isBaseline, true);
  assert.equal(base.values.sharpe, 0.47);
  const ex = C.scenarioView(grid, Object.assign({ sample: "val" }, C.BASELINE, { cost_bps: 10 }));
  assert.equal(ex.isBaseline, false);
  assert.ok(Math.abs(ex.delta.sharpe - (0.3 - 0.47)) < 1e-12);
  const fin = C.scenarioView(grid, Object.assign({ sample: "val" }, C.BASELINE, { financing: "S1" }));
  assert.equal(fin.isBaseline, false);
  assert.equal(fin.values.excess_sharpe, 0.4);                       // financing changes only the attribution fields
  assert.equal(fin.values.sharpe, 0.47);
  assert.equal(C.scenarioView(grid, { sample: "val", cost_bps: 99, borrow_bps: 30, fill_lag: 1, fill: "open_next", financing: "S0" }), null);
  assert.equal(C.CONTROL_METHOD.financing, "attribution");
  assert.equal(C.CONTROL_METHOD.cost_bps, "rerun");
});

test("markdown renderer escapes HTML", () => {
  assert.ok(!C.md("<script>x</script>").includes("<script>"));
  assert.match(C.md("[a](https://x.org)"), /href="https:\/\/x.org"/);
});
