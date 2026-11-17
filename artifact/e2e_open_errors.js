// preview_start answers tool_error "could not run on this page" (seen live on bot-protected shops).
//  * ebay.nl never opens           -> reported as "blocked" with the app's words and a manual link, after ONE retry
//  * mediamarkt.nl errors but opens -> read_page shows the page, so it is read anyway
const { chromium } = require("playwright"); const path = require("path"); const { MOCK } = require("./mock_bridge");
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch(), p = await b.newPage({ viewport: { width: 1200, height: 900 } }), errs = []; p.on("pageerror", e => errs.push(e.message));
  await p.addInitScript(`window.__decline = {};`); await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok");
  for (const c of ["BE", "FR", "DE"]) await p.click(`#countryChips [data-c="${c}"]`);
  await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand"); await p.click('#stor [data-s="256"]'); await p.click("#goBtn");
  await p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent) && !S.running, null, { timeout: 90000 });
  const reps = await p.evaluate(() => Object.fromEntries([...S.reports]));
  const e = reps["ebay-nl"];
  ok(e && e.status === "blocked" && /refused to open this shop/.test(e.message) && /could not run on this page/.test(e.message), "ebay.nl: reported as blocked with the app's own words: " + e?.status);
  ok(!Object.values(reps).some(r => r.status === "error" && /could not run/.test(r.message)), "no generic 'could not open the page' errors remain");
  const mm = await p.evaluate(() => [...S.results.values()].filter(r => r.rid === "mediamarkt-nl").map(r => r.price));
  ok(mm.length === 1 && mm[0] === 1119, "mediamarkt.nl: opened despite the error, price read from the active tab: " + JSON.stringify(mm));
  await p.click("#logBox summary");
  const row = await p.$$eval("#logTable tbody tr", t => t.find(r => /eBay/.test(r.innerText))?.innerText.replace(/\s+/g, " "));
  ok(/blocked/.test(row) && /Open shop/.test(row), "the log row offers an 'Open shop' link: " + row?.slice(0, 120));
  ok(errs.length === 0, "no page errors " + JSON.stringify(errs));
  await b.close();
})();
