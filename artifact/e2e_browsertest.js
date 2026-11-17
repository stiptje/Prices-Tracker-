// Coverage notice, the "Test the browser" button and its verdicts, and works-first ordering.
const { chromium } = require("playwright"); const path = require("path"); const { MOCK } = require("./mock_bridge");
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
const boot = async (b, init, keepAll) => {
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } }); p.errs = []; p.on("pageerror", e => p.errs.push(e.message));
  await p.addInitScript(`window.__decline = {}; ${init || ""}`); await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok");
  if (!keepAll) for (const c of ["BE", "FR", "DE"]) await p.click(`#countryChips [data-c="${c}"]`);
  return p;
};
const search = async p => { await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand"); await p.click('#stor [data-s="256"]'); await p.click("#goBtn"); };
const settled = p => p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent) && !S.running, null, { timeout: 120000 });

(async () => {
  const b = await chromium.launch();

  // ---- 1. shops refuse, neutral sites open
  let p = await boot(b, `window.__refuse = ["boulanger.com", "fnac.com", "amazon.fr", "ldlc.com", "amazon.nl", "alternate.nl", "apple.com"];`);
  await search(p); await settled(p);
  const cov = await p.$eval("#coverage", e => e.innerText.replace(/\s+/g, " "));
  ok(!(await p.$eval("#coverage", e => e.hidden)) && /would not open in the built-in browser/.test(cov), "coverage notice appears when 3+ shops refuse: " + cov.slice(0, 110));
  ok(/Amazon\.nl/.test(cov) && /Paste text/.test(cov), "it names the refused shops and points to Paste text");
  await p.click("#testBrowser"); await p.waitForFunction(() => document.querySelector("#btBox .banner"), null, { timeout: 60000 });
  let rows = await p.evaluate(() => S.browserTest.map(r => [r.host, r.ok]));
  ok(rows.find(r => r[0] === "example.com")[1] && rows.find(r => r[0] === "wikipedia.org")[1] && !rows.find(r => r[0] === "fnac.com")[1], "test table: neutral sites open, fnac.com refused: " + JSON.stringify(rows.slice(0, 4)));
  ok(/the shops .* refuse the embedded browser/.test(await p.$eval("#btBox .banner", e => e.innerText)), "verdict: the shops refuse, not the browser");
  ok(/browserTest/.test(await p.evaluate(() => buildReport())) && await p.evaluate(() => JSON.parse(buildReport()).browserTest.length === 9), "the copied report includes the test results");
  ok(p.errs.length === 0, "no page errors " + JSON.stringify(p.errs)); await p.close();

  // ---- 2. everything refused, even neutral sites -> approval-based reading (hedged)
  p = await boot(b, `window.__refuse = [".com", ".org", ".be", ".nl", ".fr", ".de"];`);
  await search(p); await p.waitForFunction(() => S.reports.size >= 3, null, { timeout: 60000 });
  await p.waitForSelector("#resumeBtn, #coverage .banner", { timeout: 90000 });
  await p.evaluate(() => { S.cancel = true; });
  await p.evaluate(() => { S.running = false; S.queue = []; });
  await p.evaluate(() => runBrowserTest()); await p.waitForFunction(() => document.querySelector("#btBox .banner"), null, { timeout: 60000 });
  const v = await p.$eval("#btBox .banner", e => e.innerText.replace(/\s+/g, " "));
  ok(/only opening websites you have approved/.test(v) || /only opening.*approved/.test(v), "verdict when even neutral sites fail: approval-based, hedged: " + v.slice(0, 120));
  ok(/my reading of the pattern, not something the app states/.test(v), "it says this is an inference");
  await p.close();

  // ---- 3. works-first ordering: shops that opened before are searched first next time
  p = await boot(b, `window.__refuse = ["coolblue.nl", "bol.com", "mediamarkt.nl"];`);
  await search(p); await settled(p);
  const works = await p.evaluate(() => Object.keys(S.works).sort());
  ok(works.includes("amazon-nl") && !works.includes("coolblue-nl"), "shops that opened are remembered as working: " + works.join(","));
  await p.evaluate(() => { window.__refuse = []; window.__urls = []; });
  await p.click("details.more > summary"); await p.check("#optRetryRef"); await p.click("#goBtn"); await settled(p);
  const first = await p.evaluate(() => window.__urls.slice(0, 3).map(u => new URL(u).hostname));
  ok(first.some(h => /amazon\.nl|alternate\.nl/.test(h)) && !/coolblue/.test(first[0]), "second search starts with shops that opened before, not the old first shop: " + first.join(", "));
  ok(p.errs.length === 0, "no page errors " + JSON.stringify(p.errs));
  await b.close();
})();
