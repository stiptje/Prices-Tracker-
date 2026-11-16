// Drives artifact/prices-tracker.html in Chromium with a MOCK of the Claude desktop browser bridge.
// Verifies the UI + engine flow; it does not (and cannot) prove behaviour against real shops.
const { chromium } = require("playwright");
const path = require("path");
const MOCK = () => {
  const pages = (u) => {
    const url = new URL(u), h = url.hostname.replace(/^www\./, ""), p = url.pathname + url.search;
    const filler = "Navigatie Winkelwagen Klantenservice Over ons Contact Algemene voorwaarden Privacy Cookies ".repeat(12);
    if (h === "coolblue.nl" && p.startsWith("/zoeken")) return `Coolblue\nZoekresultaten voor ${url.searchParams.get("query")}\n${filler}\nApple iPhone 15 Pro 256GB Zwart\nVandaag nog in huis\n€ 1.199,00\n1.099,-\nGratis verzending\nApple iPhone 15 Pro Max 256GB\n1.299,-\nHoesje voor Apple iPhone 15 Pro\n€ 19,95\nApple iPhone 15 Pro 128GB\n€ 999,00\nApple iPhone 15 Pro 256GB Refurbished\n€ 899,00`;
    if (h === "coolblue.nl" && p.startsWith("/product/")) return `${filler}\nApple iPhone 15 Pro 256GB Zwart\n★★★★★ 4,8 (212)\n€ 1.199,00\n€ 1.089,00\nVandaag besteld, morgen in huis`;
    if (h === "mediamarkt.nl") return "Please complete the captcha to continue";
    if (h === "bol.com") return `bol\nZoekresultaten voor ${url.searchParams.get("searchtext")}\n${filler}\nSamsung Galaxy S24 Ultra 256GB\n€ 899,00`;
    if (h === "amazon.nl") return `Amazon.nl Resultaten voor ${url.searchParams.get("k")}\n${filler}\nApple iPhone 15 Pro (256 GB) - Titanium Blauw\n€1.075,00\nGratis bezorging`;
    return `Pagina niet gevonden ${filler} Pagina niet gevonden ${filler}`;
  };
  const cur = {}; let nextTab = 7;
  const text = t => ({ content: [{ type: "text", text: t }] });
  window.__calls = [];
  window.claude = { use: async (n) => {
    if (n === "mcp") return {
      listTools: async () => ({ servers: [{ server: "host:claude_browser", tools: ["preview_start", "navigate", "get_page_text", "read_page", "tabs_context"].map(name => ({ name })) }] }),
      callTool: async (srv, tool, input) => {
        window.__calls.push(tool);
        window.__conc = (window.__conc || 0) + 1; window.__maxConc = Math.max(window.__maxConc || 0, window.__conc);
        try { await new Promise(r => setTimeout(r, 5));
        if (tool === "navigate" || tool === "preview_start") { window.__opens = (window.__opens || 0) + 1;
          const d = window.__decline || {};
          if ((d.at && d.at.includes(window.__opens)) || (d.from && window.__opens >= d.from && !d.off)) throw Object.assign(new Error("user declined"), { code: "cancelled" }); }
        if (tool === "preview_start") { const id = nextTab++; cur[id] = input.url; return { payload: { tabId: id, url: input.url }, content: [{ type: "text", text: "opened" }] }; }
        if (tool === "navigate") { cur[input.tabId] = input.url; return text("navigated"); }
        if (tool === "get_page_text") return text(pages(cur[input.tabId]));
        if (tool === "read_page") return text(cur[input.tabId].includes("/zoeken") && cur[input.tabId].includes("coolblue") ? `link "Apple iPhone 15 Pro 256GB Zwart" https://www.coolblue.nl/product/123/apple-iphone-15-pro.html\nlink "Apple iPhone 15 Pro Max 256GB" https://www.coolblue.nl/product/999/max.html` : "");
        throw Object.assign(new Error("unknown tool"), { code: "bad_request" });
        } finally { window.__conc--; }
      } };
    if (n === "sample") { const f = async () => ({ text: "" }); f.json = async () => []; return f; }
    if (n === "downloads") return { save: async x => { window.__saved = x; return { status: "saved" }; } };
    return null; } };
};
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 900 } });
  const errs = []; p.on("pageerror", e => errs.push("pageerror: " + e.message)); p.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  await p.addInitScript(MOCK);
  await p.goto("file://" + path.resolve(__dirname, "prices-tracker.html"));
  await p.waitForSelector("#bridge.ok", { timeout: 5000 });
  console.log("bridge pill:", await p.$eval("#bridge", e => e.textContent));
  for (const c of ["BE", "FR", "DE"]) await p.click(`#countryChips [data-c="${c}"]`);            // only NL
  await p.fill("#q", "iphone 15 pro"); await p.click("#idForm button");
  await p.waitForSelector("#candList .cand");
  console.log("preselected:", await p.$$eval('.cand[aria-pressed="true"] b', e => e.map(x => x.textContent)));
  await p.click('#stor [data-s="256"]');
  await p.click("#goBtn");
  await p.waitForFunction(() => /^(\d+)\/\1 shops read/.test(document.querySelector("#progress").textContent), null, { timeout: 120000 });
  await p.waitForTimeout(300);
  console.log("progress:", await p.$eval("#progress", e => e.textContent));
  console.log("RESULTS:"); (await p.$$eval("#resTable tbody tr", t => t.map(r => r.innerText.replace(/\s+/g, " ").slice(0, 170)))).forEach(x => console.log("  ", x));
  await p.click("#logBox summary");
  const log = await p.$$eval("#logTable tbody tr", t => t.map(r => r.innerText.replace(/\s+/g, " ").slice(0, 120)));
  console.log("LOG sample:"); log.slice(0, 6).forEach(x => console.log("  ", x));
  console.log("log status counts:", await p.$eval("#logSummary", e => e.textContent));
  console.log("tool calls:", Object.entries((await p.evaluate(() => window.__calls)).reduce((a, t) => (a[t] = (a[t] || 0) + 1, a), {})));
  await p.screenshot({ path: process.argv[2] || "shot-artifact.png", fullPage: true });
  // dark + phone
  await p.emulateMedia({ colorScheme: "dark" }); await p.setViewportSize({ width: 390, height: 844 });
  await p.screenshot({ path: (process.argv[2] || "shot-artifact.png").replace(".png", "-phone-dark.png"), fullPage: false });
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  console.log("horizontal overflow at 390px:", overflow);
  // csv
  await p.click('.tab[data-tab="db"]'); await p.click("#csvBtn"); await p.waitForTimeout(200);
  console.log("csv saved:", await p.evaluate(() => window.__saved?.filename + " " + window.__saved?.data.split("\n").length + " lines"));
  console.log("errors:", errs); await b.close();
})();
