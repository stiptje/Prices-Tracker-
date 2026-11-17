// What the page concludes when the built-in browser refuses pages (modelled on the real log: preview_start tool_error
// on bot-protected shops while other pages open fine).
//  A  four shops refuse, others open      -> they are "blocked", remembered, a control test ran, the run did not pause
//  A2 second search                       -> refused shops are skipped (no browser calls), "retry" checkbox tries them again
//  B  the browser itself is stuck         -> control test fails: pause, shops NOT blamed or remembered, Continue finishes
//  C  paste mode + copyable report
const { chromium } = require("playwright"); const path = require("path"); const { MOCK } = require("./mock_bridge");
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
const boot = async (b, init) => {
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } }); p.errs = []; p.on("pageerror", e => p.errs.push(e.message));
  await p.addInitScript(`window.__decline = {}; ${init || ""}
    Object.defineProperty(navigator, "clipboard", { value: { writeText: async t => { window.__clip = t; } }, configurable: true });`);
  await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok");
  for (const c of ["BE", "FR", "DE"]) await p.click(`#countryChips [data-c="${c}"]`);              // Netherlands only
  return p;
};
const search = async p => { await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand"); await p.click('#stor [data-s="256"]'); await p.click("#goBtn"); };
const settled = p => p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent) && !S.running, null, { timeout: 120000 });
const reports = p => p.evaluate(() => Object.fromEntries([...S.reports].map(([k, v]) => [k, { status: v.status, refused: !!v.refused, msg: v.message }])));

(async () => {
  const b = await chromium.launch();

  // ---------------- A: site-specific refusals
  let p = await boot(b, `window.__refuse = ["amazon.nl", "alternate.nl", "apple.com"];`);
  await search(p); await settled(p);
  let rp = await reports(p); const refused = ["amazon-nl", "alternate-nl", "apple-nl", "ebay-nl"];
  ok(refused.every(id => rp[id].status === "blocked" && rp[id].refused), "the four refusing shops are reported as blocked: " + refused.map(id => rp[id].status).join(","));
  ok(["coolblue-nl", "mediamarkt-nl"].every(id => !rp[id].refused && rp[id].status !== "blocked"), "shops that open are unaffected");
  ok(await p.$eval("#haltBox", e => e.hidden), "the run did not pause (the control test showed the browser works)");
  ok(await p.evaluate(() => S.controlOk === true && diag.some(d => /control test/.test(d) && /browser works/.test(d))), "a control test re-opened a known-good page and passed");
  const stored = await p.evaluate(() => Object.keys(JSON.parse(localStorage.getItem("pt.refused") || "{}")).sort());
  ok(JSON.stringify(stored) === JSON.stringify(refused.slice().sort()), "the four refusals are remembered: " + stored.join(","));
  ok(/Remembered/.test(rp["amazon-nl"].msg), "the log row says it is remembered");
  const callsA = await p.evaluate(() => window.__calls.length);

  // ---------------- C: paste mode + report on this same page
  await p.click("#logBox summary");
  await p.click('#logTable .paste[data-id="ebay-nl"]'); await p.waitForSelector("#pasteText");
  await p.fill("#pasteText", "eBay\nZoekresultaten\nApple iPhone 15 Pro 256GB Zwart\n€ 1.079,00\nApple iPhone 15 Pro Max 256GB\n€ 1.299,00\nHoesje voor iPhone 15 Pro\n€ 9,95");
  await p.click("#pasteGo"); await p.waitForTimeout(100);
  let rows = await p.evaluate(() => [...S.results.values()].filter(r => r.rid === "ebay-nl").map(r => [r.price, r.confirmed, r.pasted]));
  ok(rows.length === 1 && rows[0][0] === 1079 && rows[0][1] === false && rows[0][2] === true, "pasted search page: only the exact model (1079), marked unconfirmed/pasted: " + JSON.stringify(rows));
  await p.click('#logTable .paste[data-id="amazon-nl"]'); await p.waitForSelector("#pasteKind");
  await p.selectOption("#pasteKind", "product"); await p.fill("#pasteUrl", "https://www.amazon.nl/dp/B0TEST");
  await p.fill("#pasteText", "Amazon.nl\nApple iPhone 15 Pro (256 GB) - Titanium Blauw\n★★★★☆ 4,6\n€ 55 cashback\n€ 1.199,00\n€ 1.075,00\nOp voorraad");
  await p.click("#pasteGo"); await p.waitForTimeout(100);
  rows = await p.evaluate(() => [...S.results.values()].filter(r => r.rid === "amazon-nl").map(r => [r.price, r.confirmed, r.url]));
  ok(rows.length === 1 && rows[0][0] === 1075 && rows[0][1] === true && /B0TEST/.test(rows[0][2]), "pasted product page: 1075 confirmed (the €55 side amount ignored): " + JSON.stringify(rows));
  await p.selectOption("#rfConf", "all");
  ok((await p.$$eval("#resTable tbody tr", t => t.length)) >= 3, "pasted prices appear in the filtered table");
  await p.click("#copyReport"); await p.waitForTimeout(100);
  const clip = await p.evaluate(() => window.__clip), rep = clip ? JSON.parse(clip) : null;
  ok(rep && rep.shops.length >= 8 && rep.opens.length > 5 && rep.calls.length > 5 && rep.tabsOpened > 5, "the copied report holds every shop, the open log and the call history (" + rep?.shops.length + " shops, " + rep?.opens.length + " opens)");

  // ---------------- A2: second search skips remembered refusals
  await p.click("#goBtn"); await settled(p);
  rp = await reports(p);
  ok(refused.every(id => rp[id].status === "skipped" && /not tried again for 7 days/.test(rp[id].msg)), "second search: refused shops are skipped without touching the browser");
  const refusedNames = await p.$$eval("#shopList label", l => l.filter(x => /refused before/.test(x.textContent)).length);
  ok(refusedNames === 4, "the shop list marks them 'refused before' (" + refusedNames + ")");
  await p.click("details.more > summary"); await p.check("#optRetryRef"); await p.click("#goBtn"); await settled(p);
  rp = await reports(p); ok(refused.every(id => rp[id].status === "blocked"), "with 'Retry shops the browser refused before' they are tried again");
  ok(p.errs.length === 0, "no page errors " + JSON.stringify(p.errs)); await p.close();

  // ---------------- B: the browser itself gets stuck
  p = await boot(b, `window.__stuckFrom = 4;`);
  await search(p); await p.waitForSelector("#resumeBtn", { timeout: 60000 });
  ok(/Paused: the built-in browser stopped opening pages/.test(await p.$eval("#haltBox", e => e.innerText)), "banner explains the browser itself is stuck");
  ok(await p.evaluate(() => diag.some(d => /control test/.test(d) && /FAILED/.test(d))), "the control test failed, which is what proves it");
  ok(await p.evaluate(() => Object.keys(JSON.parse(localStorage.getItem("pt.refused") || "{}")).length === 0), "no shop was remembered as blocked");
  ok(await p.evaluate(() => ![...S.reports.values()].some(r => r.status === "blocked")), "no shop is reported as blocked");
  await p.evaluate(() => { window.__stuckOff = true; }); await p.click("#resumeBtn"); await settled(p);
  rp = await reports(p);
  ok(Object.entries(rp).filter(([, r]) => r.refused).map(([k]) => k).join() === "ebay-nl", "after Continue only eBay (which the mock always refuses) is blocked; the shops that were put back are read normally: " + Object.entries(rp).filter(([, r]) => r.refused).map(([k]) => k).join());
  ok(/^8\/8/.test(await p.$eval("#progress", e => e.textContent)), "all shops done: " + await p.$eval("#progress", e => e.textContent));
  ok(p.errs.length === 0, "no page errors " + JSON.stringify(p.errs));
  await b.close();
})();
