// Cdiscount-like shop: first load fails with "cancelled · The page changed; retry." and shows a cookie wall.
const { chromium } = require("playwright"); const fs = require("fs"); const path = require("path");
const { MOCK } = require("./mock_bridge");
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
const run = async (b, cookies) => {
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } }); const errs = []; p.on("pageerror", e => errs.push(e.message));
  await p.addInitScript(`window.__decline = {};`); await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok");
  for (const c of ["BE", "NL", "DE"]) await p.click(`#countryChips [data-c="${c}"]`);          // France only
  if (!cookies) await p.click("details.more > summary"), await p.uncheck("#optCookies");
  await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand"); await p.click('#stor [data-s="256"]'); await p.click("#goBtn");
  await p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent) && !S.running, null, { timeout: 60000 });
  const rep = await p.evaluate(() => S.reports.get("cdiscount-fr")); const clicks = await p.evaluate(() => window.__clicks); const diag = await p.$eval("#diag", e => e.textContent);
  const cdNav = await p.evaluate(() => window.__cdNav); const halt = await p.$eval("#haltBox", e => e.hidden); const rows = await p.evaluate(() => [...S.results.values()].filter(r => r.rid === "cdiscount-fr").map(r => [r.price, r.confirmed]));
  await p.close(); return { rep, clicks, diag, halt, rows, errs, cdNav };
};
(async () => {
  const b = await chromium.launch();
  let r = await run(b, true);
  ok(r.rep.status !== "declined" && r.rep.status !== "error", "'page changed; retry' is retried, not treated as a refusal (Cdiscount status: " + r.rep.status + ")");
  ok(r.halt, "no 'not approved' banner shown");
  ok(r.cdNav >= 2, "the failed navigation was repeated automatically (" + r.cdNav + " attempts at the Cdiscount page)");
  ok(r.clicks.length === 1 && r.clicks[0].ref === "ref_9" && r.clicks[0].action === "left_click", "clicked exactly one thing: 'Continuer sans accepter' (ref_9), never 'Tout accepter' (ref_8): " + JSON.stringify(r.clicks));
  ok(r.rows.length === 1 && r.rows[0][0] === 1079, "after the essential-only click the Cdiscount price was read: " + JSON.stringify(r.rows));
  ok(r.errs.length === 0, "no page errors");
  r = await run(b, false);
  ok(r.clicks.length === 0, "with the cookie option off nothing is clicked");
  await b.close();
})();
