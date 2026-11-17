const { chromium } = require("playwright"); const fs = require("fs"); const path = require("path");
const src = fs.readFileSync(path.join(__dirname, "e2e_mock.js"), "utf8");
const MOCK = src.slice(src.indexOf("const MOCK = () => {") + "const MOCK = ".length, src.indexOf("(async () => {")).trim().replace(/;$/, "");
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
const boot = async (b, decline) => { const p = await b.newPage({ viewport: { width: 1200, height: 900 } }); p.errs = []; p.on("pageerror", e => p.errs.push(e.message));
  await p.addInitScript(`window.__decline = ${JSON.stringify(decline || {})};`); await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok"); return p; };
const search = async p => { await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand"); await p.click('#stor [data-s="256"]'); await p.click("#goBtn"); };
const settled = p => p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent) && !S.running, null, { timeout: 120000 });
(async () => {
  const b = await chromium.launch();
  // ---------- A. normal run + filters
  let p = await boot(b); await search(p); await settled(p);
  let rows = await p.$$eval("#resTable tbody tr", t => t.map(r => r.innerText.replace(/\s+/g, " ")));
  ok(rows.length === 1 && /1\.089|1,089/.test(rows[0]) && /confirmed on product page/.test(rows[0]), "default table shows only the confirmed Coolblue price (1,089), not the listing 1,099 / unconfirmed Amazon: " + rows.length + " row");
  ok(/unconfirmed hidden/.test(await p.$eval("#rfCount", e => e.textContent)), "count line says unconfirmed prices are hidden");
  await p.selectOption("#rfConf", "all");
  rows = await p.$$eval("#resTable tbody tr", t => t.map(r => r.innerText.replace(/\s+/g, " ")));
  ok(rows.length === 3 && rows.filter(x => /Not confirmed: no product-page link/.test(x)).length === 2, "include-unconfirmed shows Amazon and Cdiscount, each with the reason (" + rows.length + " rows)");
  await p.click('#rfCountry [data-c="NL"]');
  ok((await p.$$eval("#resTable tbody tr", t => t.length)) === 1, "deselecting NL leaves only the French shop");
  for (const c of ["BE", "FR", "DE"]) await p.click(`#rfCountry [data-c="${c}"]`);
  ok((await p.$$eval("#resTable tbody tr", t => t.length)) === 0 && !(await p.$eval("#noFilt", e => e.hidden)), "deselecting every country empties the table and says so");
  await p.click("#rfReset");
  ok((await p.$$eval("#resTable tbody tr", t => t.length)) === 1, "Reset filters restores the default view");
  await p.fill("#rfMin", "1100"); ok((await p.$$eval("#resTable tbody tr", t => t.length)) === 0, "min price 1100 hides the 1,089 offer"); await p.fill("#rfMin", "");
  await p.selectOption("#rfConf", "all"); await p.fill("#rfText", "amazon"); ok((await p.$$eval("#resTable tbody tr", t => t.length)) === 1, "text filter 'amazon' leaves one row"); await p.fill("#rfText", "");
  await p.click("#rfCsv"); await p.waitForTimeout(200);
  const saved = await p.evaluate(() => window.__saved); ok(saved && /^prices-.*\.csv$/.test(saved.filename) && saved.data.split("\n").length === 4, "export of shown prices: " + saved?.filename + ", " + saved?.data.split("\n").length + " lines");
  ok(p.errs.length === 0, "no page errors " + JSON.stringify(p.errs));
  await p.screenshot({ path: process.argv[2] || "shot-filters.png", fullPage: true }); await p.close();

  // ---------- B. two refused actions (not consecutive-3): run continues, shops marked not approved, Retry works
  p = await boot(b, { at: [4, 5] }); await search(p); await settled(p);
  const sum = await p.$eval("#logSummary", e => e.textContent);
  ok(/2 not approved/.test(sum), "two refused shops are marked 'not approved': " + sum);
  ok(!(await p.$eval("#haltBox", e => e.hidden)) && /Some shops were not approved/.test(await p.$eval("#haltBox", e => e.innerText)), "banner offers retry without having paused the run");
  ok(/progress/.test("progress") && /^49\/49/.test((await p.$eval("#progress", e => e.textContent))), "all 49 shops were still processed");
  const line = await p.$eval("#haltBox", e => e.innerText.replace(/\s+/g, " ")); ok(/code cancelled|code\s+cancelled/.test(line) && /user declined/.test(line), "banner shows the raw error code + message: " + line.slice(0, 160));
  await p.click("#retryBtn"); await settled(p);
  ok(!/not approved/.test(await p.$eval("#logSummary", e => e.textContent)), "after Retry nothing is 'not approved'"); await p.close();

  // ---------- C. every action refused from #4 on: pauses after 3 in a row, Continue after allowing finishes
  p = await boot(b, { from: 4 }); await search(p);
  await p.waitForSelector("#resumeBtn", { timeout: 60000 });
  ok(/^6\/49|^[3-9]\/49/.test(await p.$eval("#progress", e => e.textContent)), "paused early: " + await p.$eval("#progress", e => e.textContent));
  ok(/Paused/.test(await p.$eval("#haltBox", e => e.innerText)), "banner says Paused");
  await p.evaluate(() => { window.__decline.off = true; }); await p.click("#resumeBtn"); await settled(p);
  ok(/^49\/49/.test(await p.$eval("#progress", e => e.textContent)), "Continue finishes the remaining shops");
  ok((await p.evaluate(() => window.__maxConc)) === 1, "only one browser action at a time"); await p.close();
  await b.close();
})();
