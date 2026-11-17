// Reproduces the real app's behaviour seen in the field:
//  * `navigate` is refused ("The Artifact can't navigate that tab ... use preview_start") and reported as code "cancelled";
//  * an Alternate-like shop answers every load with "The page changed; retry." although the page does open.
const { chromium } = require("playwright"); const fs = require("fs"); const path = require("path");
const src = fs.readFileSync(path.join(__dirname, "e2e_mock.js"), "utf8");
const MOCK = src.slice(src.indexOf("const MOCK = () => {") + "const MOCK = ".length, src.indexOf("(async () => {")).trim().replace(/;$/, "");
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch(), p = await b.newPage({ viewport: { width: 1200, height: 900 } }), errs = []; p.on("pageerror", e => errs.push(e.message));
  await p.addInitScript(`window.__decline = {};`); await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok");
  for (const c of ["BE", "FR", "DE"]) await p.click(`#countryChips [data-c="${c}"]`);              // Netherlands only
  await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand"); await p.click('#stor [data-s="256"]'); await p.click("#goBtn");
  await p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent) && !S.running, null, { timeout: 90000 });
  const calls = await p.evaluate(() => window.__calls), reps = await p.evaluate(() => Object.fromEntries([...S.reports]));
  ok(!calls.includes("navigate"), "the page never calls navigate (only preview_start opens pages): " + [...new Set(calls)].join(", "));
  ok(!Object.values(reps).some(r => /redirecting|not approved|declined/.test(r.message + r.status)), "no shop is reported as redirecting / not approved");
  const alt = reps["alternate-nl"], row = await p.evaluate(() => [...S.results.values()].filter(r => r.rid === "alternate-nl").map(r => r.price));
  ok(alt && alt.status !== "error" && row[0] === 1049, "redirecting Alternate-like shop: page read after it settled, price 1049 (status " + alt?.status + ")");
  ok(/tabs? opened/.test(await p.$eval("#progress", e => e.textContent)), "progress shows the tab counter: " + await p.$eval("#progress", e => e.textContent));
  ok(errs.length === 0, "no page errors " + JSON.stringify(errs));
  await b.close();
})();
