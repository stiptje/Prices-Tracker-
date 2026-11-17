// MOCK of the Claude desktop app's built-in browser bridge (host:claude_browser), modelled on what the real app
// answered in the field: tab ids like "tab-8", `navigate` refused, host calls rate-limited, preview_start sometimes
// "could not run on this page", redirects reported as cancelled "The page changed; retry.".
// It proves the page's logic, not behaviour on real shops.
const MOCK = () => {
  window.__ptOpenGap = 60; window.__ptAnyGap = 5; window.__ptBackoff = 40; window.__ptSettle = 20;     // keep tests fast
  const filler = "Navigatie Winkelwagen Klantenservice Over ons Contact Algemene voorwaarden Privacy Cookies ".repeat(12);
  const pages = (u) => {
    const url = new URL(u), h = url.hostname.replace(/^www\./, ""), p = url.pathname + url.search;
    if (h === "coolblue.nl" && p.startsWith("/zoeken")) return `Coolblue\nZoekresultaten voor ${url.searchParams.get("query")}\n${filler}\nApple iPhone 15 Pro 256GB Zwart\nVandaag nog in huis\n€ 1.199,00\n1.099,-\nGratis verzending\nApple iPhone 15 Pro Max 256GB\n1.299,-\nHoesje voor Apple iPhone 15 Pro\n€ 19,95\nApple iPhone 15 Pro 128GB\n€ 999,00\nApple iPhone 15 Pro 256GB Refurbished\n€ 899,00`;
    if (h === "coolblue.nl" && p.startsWith("/product/")) return `${filler}\nApple iPhone 15 Pro 256GB Zwart\n★★★★★ 4,8 (212)\n€ 1.199,00\n€ 1.089,00\nVandaag besteld, morgen in huis`;
    // JavaScript shop: get_page_text only returns a thin header, the results are only visible in read_page
    if (h === "coolblue.be" && p.includes("/zoeken")) return `Title: Zoeken | Coolblue URL: ${u} Source element: main`;
    if (h === "coolblue.be" && p.includes("/produit/")) return `${filler}\nOppo Find X10 Pro Max 512 Go Gris 5G\n★★★★☆ 4,6 (55)\n€ 55 cashback à la reprise\n€ 55,-\n€ 1.349,00\n€ 1.299,00\nEn stock\nProduits similaires\nOppo Find X10 Pro 256 Go\n€ 899,00`;
    if (h === "cdiscount.com") return window.__cd.consent
      ? `Cdiscount\nRésultats pour iphone 15 pro\n${filler}\nApple iPhone 15 Pro 256 Go\n1 079,00 €\nLivraison offerte`
      : `Cdiscount ${filler}\nCookies et traceurs\nNous utilisons des cookies pour personnaliser votre expérience. Tout accepter / Continuer sans accepter ${filler}`;
    if (h === "alternate.nl") return `Alternate\nZoekresultaten\n${filler}\nApple iPhone 15 Pro 256GB Zwart\n€ 1.049,-\nOp voorraad`;
    if (h === "mediamarkt.nl") return `MediaMarkt\nZoekresultaten\n${filler}\nApple iPhone 15 Pro 256GB Titanium\n€ 1.119,00\nMorgen in huis`;
    if (h === "bol.com") return `bol\nZoekresultaten voor ${url.searchParams.get("searchtext")}\n${filler}\nSamsung Galaxy S24 Ultra 256GB\n€ 899,00`;
    if (h === "amazon.nl") return `Amazon.nl Resultaten voor ${url.searchParams.get("k")}\n${filler}\nApple iPhone 15 Pro (256 GB) - Titanium Blauw\n€1.075,00\nGratis bezorging`;
    return `Pagina niet gevonden ${filler} Pagina niet gevonden ${filler}`;
  };
  const cur = {}; let nextTab = 7, lastOpenAt = 0;
  const text = t => ({ content: [{ type: "text", text: t }] });
  const tid = v => String(v ?? window.__active).replace(/^tab-/, "");
  const err = (code, message) => Object.assign(new Error(message), { code, message });
  window.__calls = []; window.__clicks = []; window.__cd = { consent: false, pcOnce: true }; window.__log = [];
  window.claude = { use: async (n) => {
    if (n === "mcp") return {
      listTools: async () => ({ servers: [{ server: "host:claude_browser", tools: ["preview_start", "navigate", "get_page_text", "read_page", "find", "computer"].map(name => ({ name })) }] }),
      describeTool: async (s, t) => ({ inputSchema: t === "computer" ? { properties: { action: { enum: ["left_click", "screenshot"] }, ref: {}, tabId: {} } } : { properties: { query: {}, tabId: {} } } }),
      callTool: async (srv, tool, input) => {
        window.__calls.push(tool);
        window.__conc = (window.__conc || 0) + 1; window.__maxConc = Math.max(window.__maxConc || 0, window.__conc);
        try {
          await new Promise(r => setTimeout(r, 5));
          if (tool === "navigate") throw err("cancelled", "The Artifact can't navigate that tab (the active one if none was named); open the site with preview_start instead.");
          if (tool === "preview_start") {
            const now = Date.now(); window.__opens = (window.__opens || 0) + 1;
            if (now - lastOpenAt < 40) { window.__rateLimited = (window.__rateLimited || 0) + 1; throw err("rate_limited", "Host tool rate limit exceeded — try again shortly."); }
            if (window.__forceRate === window.__opens) { window.__forceRate = null; window.__rateLimited = (window.__rateLimited || 0) + 1; throw err("rate_limited", "Host tool rate limit exceeded — try again shortly."); }
            lastOpenAt = now;
            const d = window.__decline || {};
            if ((d.at && d.at.includes(window.__opens)) || (d.from && window.__opens >= d.from && !d.off)) throw err("cancelled", "user declined");
            if (/cdiscount/.test(input.url)) { window.__cdNav = (window.__cdNav || 0) + 1; if (window.__cd.pcOnce) { window.__cd.pcOnce = false; throw err("cancelled", "The page changed; retry."); } }
            const TE = () => err("tool_error", "preview_start could not run on this page. Use read_page to check the pane, then retry.");
            if (/ebay\.nl/.test(input.url) || (window.__refuse || []).some(h => input.url.includes(h))) throw TE();   // bot-protected shops: never open
            if (window.__stuckFrom && window.__opens >= window.__stuckFrom && !window.__stuckOff) throw TE();   // the browser pane itself is stuck: nothing opens
            const id = nextTab++; cur[id] = input.url; window.__active = id;
            if (/mediamarkt\.nl/.test(input.url)) throw TE();                                  // error reported, but the page did open
            if (/alternate/.test(input.url)) throw err("cancelled", "The page changed; retry.");                  // redirecting shop: the tab still opens
            return text(`Opened the site in Claude's browser (tabId tab-${id}). Use read_page to see the page.`);
          }
          if (tool === "get_page_text") { const id = tid(input?.tabId); if (/alternate/.test(cur[id]) && (window.__altReads = (window.__altReads || 0) + 1) <= 3) throw err("cancelled", "The page changed; retry."); return text(pages(cur[id])); }
          if (tool === "computer") { window.__clicks.push(input); if (input.ref === "ref_9") window.__cd.consent = true; return text("clicked"); }
          if (tool === "find") return text("");
          if (tool === "read_page") {
            const id = tid(input?.tabId), u = cur[id] || "";
            if (/mediamarkt\.nl/.test(u)) return text(`URL: ${u}\n` + pages(u));
            if (/cdiscount/.test(u) && !window.__cd.consent) return text(`button "Tout accepter" [ref_8]\nbutton "Continuer sans accepter" [ref_9]\nlink "Mentions légales" [ref_3]`);
            if (/coolblue\.be/.test(u) && u.includes("/zoeken")) return text(`- link "Panier" [ref=e3]:\n  - /url: /fr/panier\n- link "Oppo Find X10 Pro Max 512 Go Gris 5G" [ref=e12] [cursor=pointer]:\n  - /url: /fr/produit/986601/oppo-find-x10-pro-max-512-go-gris-5g.html\n- text: 1 299,00 €\n- link "Coque pour Oppo Find X10 Pro" [ref=e15]:\n  - /url: /fr/produit/555/coque.html\n- text: 19,95 €`);
            if (/coolblue\.nl/.test(u) && u.includes("/zoeken")) return text(`link "Apple iPhone 15 Pro 256GB Zwart" https://www.coolblue.nl/product/123/apple-iphone-15-pro.html\nlink "Apple iPhone 15 Pro Max 256GB" https://www.coolblue.nl/product/999/max.html`);
            return text("");
          }
          throw err("bad_request", "unknown tool");
        } finally { window.__conc--; }
      } };
    if (n === "sample") { const f = async () => ({ text: "" }); f.json = async () => []; return f; }
    if (n === "downloads") return { save: async x => { window.__saved = x; return { status: "saved" }; } };
    return null; } };
};
module.exports = { MOCK };
