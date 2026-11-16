// Mocked bridge refuses the 4th browser action ("cancelled"). Expect: pause banner, no error spam, Continue finishes the rest, never >1 action at once.
const { chromium } = require("playwright"); const fs = require("fs"); const path = require("path");
const src = fs.readFileSync(path.join(__dirname, "e2e_mock.js"), "utf8");
const MOCK = src.slice(src.indexOf("const MOCK = () => {") + "const MOCK = ".length, src.indexOf("(async () => {")).trim().replace(/;$/, "");
(async () => {
  const b = await chromium.launch(), p = await b.newPage({ viewport: { width: 1200, height: 900 } }), errs = [];
  p.on("pageerror", e => errs.push(e.message));
  await p.addInitScript("window.__declineAt = 4;"); await p.addInitScript(`(${MOCK})()`);
  await p.goto("file://" + path.join(__dirname, "prices-tracker.html")); await p.waitForSelector("#bridge.ok");
  console.log("selected by default (NL+BE+FR+DE, known search URL only):", await p.$eval("#selSummary", e => e.textContent));
  await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button"); await p.waitForSelector("#candList .cand"); await p.click("#goBtn");
  await p.waitForSelector("#haltBox .banner", { timeout: 60000 });
  console.log("PAUSED:", (await p.$eval("#haltBox", e => e.innerText.replace(/\s+/g, " "))).slice(0, 230));
  console.log("errors in log so far:", (await p.$$eval("#logTable tbody tr .st.error", e => e.length)));
  console.log("progress while paused:", await p.$eval("#progress", e => e.textContent));
  await p.click("#resumeBtn");
  await p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent), null, { timeout: 120000 });
  console.log("after Continue:", await p.$eval("#progress", e => e.textContent), "| banner hidden:", await p.$eval("#haltBox", e => e.hidden));
  console.log("status counts:", await p.$eval("#logSummary", e => e.textContent));
  console.log("max concurrent browser actions:", await p.evaluate(() => window.__maxConc));
  console.log("page errors:", errs); await b.close();
})();
