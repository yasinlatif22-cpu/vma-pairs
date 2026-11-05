// Browser checks for a built app (local or public). Needs Node with Playwright and a Chromium:  node tests/web/browser_check.js build/local [shots_dir]
// Checks: no console errors on any tab; decision-time boundary in the rendered page; keyboard replay controls; app numbers equal
// the Python export; reduced motion; 2D fallback without WebGL; no horizontal overflow at phone width.
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const dir = path.resolve(process.argv[2] || "build/local");
const shots = process.argv[3];
const url = "file://" + path.join(dir, "index.html");
const raw = fs.readFileSync(path.join(dir, "data.js"), "utf8");
const D = JSON.parse(raw.slice(raw.indexOf("=") + 1).trim().replace(/;$/, ""));
const LOCAL = D.meta.mode === "local";
const fails = [];
const check = (cond, msg) => { if (!cond) fails.push(msg); else console.log("  ok  " + msg); };
const usd = (x) => (x < 0 ? "−$" : "$") + Math.round(Math.abs(x)).toLocaleString("en-US");

async function page(browser, opts = {}) {
  const ctx = await browser.newContext(Object.assign({ viewport: { width: 1440, height: 1000 } }, opts));
  const p = await ctx.newPage();
  p.errors = [];
  p.on("pageerror", (e) => p.errors.push(String(e)));
  p.on("console", (m) => { if (m.type() === "error") p.errors.push(m.text()); });
  await p.goto(url);
  await p.waitForTimeout(1200);
  return p;
}
const tab = async (p, t) => { await p.click(`.tabs button[data-tab="${t}"]`); await p.waitForTimeout(1500); };
const snap = async (p, name) => { if (shots) await p.screenshot({ path: path.join(shots, name), fullPage: true }); };

(async () => {
  const browser = await chromium.launch();
  const p = await page(browser);
  console.log(`${D.meta.mode} build: ${dir}`);
  for (const t of ["overview", "timeline", "replay", "cases", "explorer"]) { await tab(p, t); await snap(p, `${D.meta.mode}_${t}.png`); }
  check(p.errors.length === 0, `no console errors on any tab (${p.errors.slice(0, 3).join(" | ")})`);
  check((await p.$("#noapp")) === null, "the fallback notice is removed once the app runs");
  const nojs = await browser.newContext({ javaScriptEnabled: false });
  const pj = await nojs.newPage(); await pj.goto(url);
  check((await pj.isVisible("#noapp")) && (await pj.textContent("#noapp")).includes("--serve"), "without JavaScript the page explains how to open it");
  await nojs.close();

  // numbers shown equal the Python export
  await tab(p, "overview");
  const ov = await p.textContent("#sampleCards");
  check(ov.includes(D.stats["val+holdout"].sharpe.toFixed(2)) && ov.includes(D.stats.holdout.sharpe.toFixed(2)), "overview Sharpe values equal the export");

  // replay: decision-time boundary and keyboard controls
  await tab(p, "replay");
  const firstId = LOCAL ? "2019-01-28" : D.synthetic.replays[0].trade.id;
  const tr = LOCAL ? D.trades.find((t) => t.id === firstId) : D.synthetic.replays[0].trade;
  const rows = LOCAL ? D.replays[firstId] : D.synthetic.replays[0].rows;
  const atStart = await p.textContent("#tab-replay");
  const opts = await p.$$eval("#rpTrade option", (o) => o.map((x) => x.textContent).join(" | "));
  check(!atStart.includes(usd(tr.net_pnl)), "decision-time view at the signal does not show the final P&L");
  check(!/z stop|max hold|target|loss limit/.test(opts) || !LOCAL, "decision-time trade list carries no outcome labels");
  check((await p.textContent("#rpPhase")).includes("Signal at the close"), "replay opens at the signal close");
  check(!(await p.textContent("#rpEvents")).includes("later information"), "no later information before the outcome");
  await p.click("#tab-replay h2, #rpPhase"); // move focus off the select
  const exitIdx = rows.findIndex((r) => r.phase === "exit"), sigIdx = rows.findIndex((r) => r.phase === "signal");
  for (let k = sigIdx; k < exitIdx; k++) await p.keyboard.press("ArrowRight");
  await p.waitForTimeout(400);
  const atExit = await p.textContent("#rpLedger");
  check(atExit.includes(usd(tr.net_pnl)), `stepping to the exit shows the ledger net ${usd(tr.net_pnl)}, equal to the trade's net P&L`);
  check((await p.textContent("#rpPhase")).includes("Exit filled"), "phase at the exit row is the exit fill");
  await p.keyboard.press("Home"); await p.waitForTimeout(300);
  check((await p.textContent("#rpPhase")).includes("Signal at the close"), "Home returns to the signal");
  await p.keyboard.press(" "); await p.waitForTimeout(1200);
  check((await p.textContent("#rpPlay")).includes("Pause"), "Space starts playback");
  await p.keyboard.press(" "); await p.waitForTimeout(200);
  check((await p.textContent("#rpPlay")).includes("Play"), "Space pauses playback");
  await p.click('#rpMode button[data-mode="retro"]'); await p.waitForTimeout(500);
  check((await p.textContent("#rpOutcome")).includes(usd(tr.net_pnl)), "retrospective view reveals the outcome");
  await snap(p, `${D.meta.mode}_replay_retro.png`);
  await p.click('#rpMode button[data-mode="decision"]');
  if (!LOCAL) check((await p.textContent("#tab-replay")).includes("SYNTHETIC"), "public replay is labelled synthetic");

  // case panel boundary
  await tab(p, "cases");
  const cardsDecision = await p.textContent("#caseCards");
  check(!/loser|winner|worst/i.test(cardsDecision), "case cards hide win/loss in decision-time view");
  await p.click('#caseCards [data-case]'); await p.waitForTimeout(600);
  const panelD = await p.textContent("#casePanel");
  check(panelD.includes("Invalidating condition") && !panelD.includes("Subsequent information"), "case panel shows decision-time sections only");
  await snap(p, `${D.meta.mode}_case_decision.png`);
  await p.click('#cpMode button[data-mode="retro"]'); await p.waitForTimeout(600);
  const panelR = await p.textContent("#casePanel");
  check(panelR.includes("Subsequent information") && panelR.includes("What it does not establish"), "retrospective case panel reveals outcome sections");
  await snap(p, `${D.meta.mode}_case_retro.png`);
  await p.keyboard.press("Escape"); await p.click('#caseMode button[data-mode="decision"]').catch(() => {});

  // explorer: baseline label and an exploratory selection
  await tab(p, "explorer");
  check((await p.textContent("#exStatus")).includes("PUBLISHED SPECIFICATION"), "explorer starts at the published baseline");
  await p.click('#exControls button[data-key="cost_bps"][data-val="10"]'); await p.waitForTimeout(500);
  const st = await p.textContent("#exStatus");
  const rec = D.scenarios.find((r) => r.sample === "val+holdout" && r.cost_bps === 10 && r.borrow_bps === 30 && r.fill_lag === 1 && r.fill === "open_next");
  check(st.includes("EXPLORATORY SCENARIO") && (await p.textContent("#exCards")).includes(rec.sharpe.toFixed(2)), "an exploratory selection is labelled and shows the engine-rerun value");
  await p.click("#ex3d"); await p.waitForTimeout(1500);
  check(await p.$("#exChart .gl-container, #exChart canvas") !== null, "3D surface renders when WebGL is available");
  await snap(p, `${D.meta.mode}_explorer_3d.png`);
  await p.click("#exReset");
  check((await p.textContent("#exStatus")).includes("PUBLISHED SPECIFICATION"), "reset returns to the baseline");

  // reduced motion and no WebGL
  const p2 = await page(browser, { reducedMotion: "reduce" });
  await tab(p2, "replay"); await tab(p2, "explorer");
  check(p2.errors.length === 0, "reduced-motion load has no errors");
  await browser.close();
  const nogl = await chromium.launch({ args: ["--disable-webgl", "--disable-3d-apis"] });
  const p3 = await page(nogl);
  await tab(p3, "explorer");
  check(await p3.$eval("#ex3d", (b) => b.disabled), "3D control is disabled without WebGL; the 2D heatmap remains");
  check(await p3.$("#exChart .heatmaplayer, #exChart .hm") !== null || (await p3.$$("#exChart .trace")).length > 0, "2D heatmap renders without WebGL");
  await nogl.close();

  // phone width
  const mb = await chromium.launch();
  const p4 = await page(mb, { viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  for (const t of ["overview", "timeline", "replay", "explorer"]) {
    await tab(p4, t);
    const over = await p4.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    check(over <= 1, `no horizontal page scroll at 390px on ${t} (overflow ${over}px)`);
  }
  await snap(p4, `${D.meta.mode}_mobile_replay.png`);
  await mb.close();
  console.log(fails.length ? `\n${fails.length} FAILED:\n  ` + fails.join("\n  ") : "\nall browser checks passed");
  process.exit(fails.length ? 1 : 0);
})();
