// The user's real case: typed "oppo x10 512 gb"; Coolblue.be has "Oppo Find X10 Pro Max 512 Go Gris 5G".
// get_page_text returns only a thin header (results live in read_page); the app also rate-limits and sometimes fails once.
const { chromium } = require("playwright"); const path = require("path"); const { MOCK } = require("./mock_bridge");
const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) process.exitCode = 1; };
(async () => {
  const b = await chromium.launch(), p = await b.newPage({ viewport: { width: 1200, height: 900 } }), errs = []; p.on("pageerror", e => errs.push(e.message));
  await p.addInitScript(`window.__decline = {}; window.__forceRate = 3;`); await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok");
  for (const c of ["FR", "NL", "DE"]) await p.click(`#countryChips [data-c="${c}"]`);                   // Belgium only
  await p.fill("#q", "oppo x10 512 gb"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand");
  await p.click("#candList .cand"); await p.waitForSelector("#goBtn");
  const hint = await p.$eval("#confirm", e => e.innerText.replace(/\s+/g, " "));
  ok(/every listing that contains all your words/.test(hint) && /512 GB/.test(hint), "free-text flow explains the loose match and takes 512 GB from the text");
  ok(/oppo x10 512 gb/i.test(await p.$eval("#aliasChips", e => e.innerText)), "the full typed text stays as an alternate search string");
  await p.click("#goBtn");
  await p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent) && !S.running, null, { timeout: 90000 });
  const rows = await p.evaluate(() => [...S.results.values()].map(r => ({ shop: r.rid, price: r.price, title: r.title, confirmed: r.confirmed, why: r.why })));
  const cb = rows.filter(r => r.shop === "coolblue-be");
  ok(cb.length === 1 && cb[0].price === 1299 && cb[0].confirmed && /X10 Pro Max/.test(cb[0].title), "Coolblue.be: 'Oppo Find X10 Pro Max 512 Go' found via read_page and confirmed on its product page at 1299 (the €55 side amounts ignored): " + JSON.stringify(cb));
  ok(!rows.some(r => /Coque/.test(r.title)), "the accessory 'Coque pour Oppo Find X10 Pro' is not offered");
  const reps = await p.evaluate(() => Object.fromEntries([...S.reports].map(([k, v]) => [k, v.status])));
  ok(reps["apple-be"] === "skipped" && reps["samsung-be"] === "skipped", "Apple/Samsung brand stores are skipped for an Oppo search");
  ok(!Object.values(reps).includes("error"), "no shop ended in an error: " + JSON.stringify(Object.entries(reps).filter(([, v]) => v === "error")));
  ok((await p.evaluate(() => window.__rateLimited)) >= 1, "a rate_limited answer happened (" + await p.evaluate(() => window.__rateLimited) + ") and was waited out, not reported as an error");
  ok(await p.evaluate(() => !window.__calls.includes("navigate")), "navigate is never used");
  ok(errs.length === 0, "no page errors " + JSON.stringify(errs));
  await p.screenshot({ path: process.argv[2] || "shot-coolblue.png", fullPage: true }); await b.close();
})();
