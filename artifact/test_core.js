const assert = require("assert");
const C = require("./core.js");
const catalog = require("./catalog.min.json");
let n = 0; const t = (name, fn) => { try { fn(); n++; } catch (e) { console.error("FAIL", name, "\n ", e.message); process.exitCode = 1; } };

const spec = (name, o = {}) => ({ name, brand: o.brand ?? "Apple", aliases: [], models: [], ...o });
for (const [title, ok] of [
  ["Apple iPhone 15 Pro 256GB Zwart", true], ["iPhone15 Pro 256 GB", true], ["Apple iPhone 15 Pro (256 GB) – Titanblau", true],
  ["Apple iPhone 15 Pro Max 256GB", false], ["Apple iPhone 15 Plus", false], ["Apple iPhone 15", false],
  ["Hoesje voor iPhone 15 Pro", false], ["Coque iPhone 15 Pro MagSafe", false], ["Screenprotector iPhone 15 Pro", false],
  ["Apple iPhone 15 Pro Reconditionné 256 Go", false], ["Apple iPhone 14 Pro 256GB", false],
  ["iPhone 15 Pro - 256GB - écran 6,1 pouces", true],
]) t("iphone15pro " + title, () => assert.strictEqual(C.judge(spec("iPhone 15 Pro"), title).ok, ok));

t("storage", () => {
  assert(C.judge(spec("iPhone 15 Pro", { storage: 256 }), "iPhone 15 Pro 256GB").ok);
  assert(!C.judge(spec("iPhone 15 Pro", { storage: 256 }), "iPhone 15 Pro 128GB").ok);
  assert(C.judge(spec("iPhone 15 Pro", { storage: 1024 }), "iPhone 15 Pro 1TB").ok);
});
t("refurb", () => {
  const s = "Apple iPhone 15 Pro 256GB Refurbished";
  assert(!C.judge(spec("iPhone 15 Pro"), s).ok);
  const v = C.judge(spec("iPhone 15 Pro", { refurb: true }), s); assert(v.ok && v.cond === "refurbished");
  assert(!C.judge(spec("iPhone 15 Pro"), "Apple iPhone 15 Pro 256GB", "refurbished").ok);
});
for (const [name, title, ok] of [
  ["Galaxy S24", "Samsung Galaxy S24 5G 128GB", true], ["Galaxy S24", "Samsung Galaxy S24 Ultra", false], ["Galaxy S24", "Samsung Galaxy S24+ 256GB", false],
  ["Galaxy S24", "Samsung Galaxy S24 FE", false], ["Pixel 9", "Google Pixel 9 Pro XL", false], ["Pixel 9", "Google Pixel 9a", false], ["Pixel 9", "Google Pixel 9 128GB", true],
  ["iPhone 16", "Apple iPhone 16e", false], ["Galaxy Z Flip6", "Samsung Galaxy Z Flip 6 5G", true], ["Xiaomi 14", "Xiaomi 14T Pro", false],
  ["Redmi Note 13", "Xiaomi Redmi Note 13 Pro+ 5G", false], ["Nothing Phone (2)", "Nothing Phone (2a)", false], ["OnePlus 12", "OnePlus 12R", false], ["Xperia 1 V", "Sony Xperia 1 VI", false],
]) t("variant " + title, () => assert.strictEqual(C.judge({ name, brand: "", aliases: [], models: [] }, title).ok, ok));
t("model number", () => {
  const s = { name: "Galaxy S24 Ultra", brand: "Samsung", models: ["SM-S928B"], aliases: ["S24 Ultra"] };
  assert(C.judge(s, "SM-S928B/DS Titanium Black").ok); assert(C.judge(s, "Samsung S24 Ultra 256GB").ok);
});
t("airpods allow", () => {
  assert(C.judge({ name: "AirPods Pro (2nd generation)", aliases: ["AirPods Pro 2"], allow: ["case", "charging", "magsafe"] }, "Apple AirPods Pro 2 met MagSafe Charging Case (USB-C)").ok);
  assert(!C.judge({ name: "AirPods Pro 2" }, "Hoesje voor AirPods Pro 2").ok);
});
t("parsePrice", () => { for (const [r, w] of [["1.299,00", 1299], ["1,299.00", 1299], ["€ 1.299,-", 1299], ["899.99", 899.99], ["1 099,00", 1099], ["12,5", 12.5], ["1.299", 1299]]) assert.strictEqual(C.parsePrice(r), w, r); });
t("pricesInLine", () => {
  assert.deepStrictEqual(C.pricesInLine("€ 1.099,00"), [1099]);
  assert.deepStrictEqual(C.pricesInLine("1.099,-"), [1099]);
  assert.deepStrictEqual(C.pricesInLine("1 099,00 €"), [1099]);
  assert.deepStrictEqual(C.pricesInLine("€1,099.00"), [1099]);
  assert.deepStrictEqual(C.pricesInLine("vanaf € 39,- per maand"), []);          // instalment
  assert.deepStrictEqual(C.pricesInLine("Bespaar € 100,-"), []);                   // saving, not price
  assert.deepStrictEqual(C.pricesInLine("Gratis verzending vanaf € 25"), []);
});
t("identify", () => {
  assert.strictEqual(C.identify("iphone 15 pro", catalog)[0].display, "Apple iPhone 15 Pro");
  assert.strictEqual(C.identify("galaxy s24 ultra", catalog)[0].name, "Galaxy S24 Ultra");
  assert.strictEqual(C.identify("sm-s928b", catalog)[0].name, "Galaxy S24 Ultra");
  assert.strictEqual(C.identify("iphon 16 pro max", catalog)[0].name, "iPhone 16 Pro Max");
  const c = C.identify("some obscure gadget 3000", catalog); assert.strictEqual(c.at(-1).kind, "custom");
  assert.strictEqual(C.identify("iphone 15", catalog)[0].name, "iPhone 15");
});
t("queries", () => { const q = C.searchQueries({ name: "Galaxy S24 Ultra", brand: "Samsung", aliases: ["Samsung Galaxy S24 Ultra"], models: ["SM-S928B"] }); assert.deepStrictEqual(q, ["Samsung Galaxy S24 Ultra", "Galaxy S24 Ultra", "SM-S928B"]); });

t("loose free-text match (the Coolblue 'oppo x10' case)", () => {
  const L = (o = {}) => ({ name: "oppo x10", brand: "Oppo", loose: true, aliases: [], models: [], ...o });
  assert(C.judge(L(), "Oppo Find X10 Pro Max 512 Go Gris 5G").ok);
  assert(C.judge(L({ storage: 512 }), "Oppo Find X10 Pro Max 512 Go Gris 5G").ok);
  assert(!C.judge(L({ storage: 256 }), "Oppo Find X10 Pro Max 512 Go Gris 5G").ok);
  assert(!C.judge(L(), "Hoesje voor Oppo Find X10 Pro").ok);
  assert(!C.judge(L(), "Oppo A10 128GB").ok);
  assert(!C.judge(L(), "Samsung Galaxy S24 Ultra").ok);
  assert(!C.judge(L(), "Oppo Find X10 Pro Max Refurbished").ok);
});
t("splitStorage", () => {
  assert.deepStrictEqual(C.splitStorage("oppo x10 512 gb"), { name: "oppo x10", storage: 512 });
  assert.deepStrictEqual(C.splitStorage("iphone 15 pro 1TB black"), { name: "iphone 15 pro black", storage: 1024 });
  assert.deepStrictEqual(C.splitStorage("oppo x10"), { name: "oppo x10", storage: null });
});
t("cleanStructure", () => {
  const raw = `- link "Oppo Find X10 Pro Max 512 Go Gris 5G" [ref=e12] [cursor=pointer]:\n  - /url: /fr/produit/986601/oppo.html\n- text: 1 299,00 €\nbutton "Ajouter au panier" [ref_5]`;
  const out = C.cleanStructure(raw).split("\n");
  assert.deepStrictEqual(out, ["Oppo Find X10 Pro Max 512 Go Gris 5G", "text: 1 299,00 €".replace(/^text: /, ""), "Ajouter au panier"].map(x => x));
});
t("shopBrand", () => { assert.strictEqual(C.shopBrand({ id: "apple-nl", kind: "brand_store" }), "apple"); assert.strictEqual(C.shopBrand({ id: "coolblue-nl", kind: "online_electronics" }), ""); });
const PAGE = `Coolblue
Zoekresultaten voor iphone 15 pro
Filters
Apple iPhone 15 Pro 256GB Zwart
Vandaag nog in huis
€ 1.199,00
1.089,-
Gratis verzending
Apple iPhone 15 Pro Max 256GB
1.299,-
Hoesje voor Apple iPhone 15 Pro
€ 19,95
Apple iPhone 15 Pro 128GB
€ 999,00
Apple iPhone 15 Pro 256GB Blauw
vanaf € 45,- per maand
€ 1.099,00
Apple iPhone 15 Pro 256GB Refurbished
€ 899,00`;
t("listingsFromText", () => {
  const out = C.listingsFromText(PAGE, spec("iPhone 15 Pro", { storage: 256 }));
  assert.deepStrictEqual(out.map(o => [o.title, o.price]), [["Apple iPhone 15 Pro 256GB Zwart", 1089], ["Apple iPhone 15 Pro 256GB Blauw", 1099]]);
});
t("listing without storage is flagged, not trusted", () => {
  const out = C.listingsFromText("Apple iPhone 15 Pro Zwart\n€ 1.049,00", spec("iPhone 15 Pro", { storage: 256 }));
  assert.strictEqual(out.length, 1); assert.strictEqual(out[0].storageOk, false);
  assert.strictEqual(C.listingsFromText("Apple iPhone 15 Pro 256GB\n€ 1.049,00", spec("iPhone 15 Pro", { storage: 256 }))[0].storageOk, true);
});
t("storageStated / outliers", () => {
  assert(C.storageStated({ storage: 256 }, "Apple iPhone 15 Pro 256GB")); assert(!C.storageStated({ storage: 256 }, "Apple iPhone 15 Pro", "https://x/iphone-15-pro"));
  assert(C.storageStated({ storage: 256 }, "x", "https://shop/iphone-15-pro-256gb.html")); assert(C.storageStated({}, "anything"));
  const f = C.flagOutliers([1000, 1050, 1100, 300]); assert(f(300) && !f(1000));
});
t("relative product links", () => {
  const raw = `link "Apple iPhone 15 Pro 256GB Zwart" href="/product/123/apple-iphone-15-pro.html"`;
  assert.strictEqual(C.urlForTitle(raw, "Apple iPhone 15 Pro 256GB Zwart", "coolblue.nl", "https://www.coolblue.nl"), "https://www.coolblue.nl/product/123/apple-iphone-15-pro.html");
});
t("product link is the one AFTER the title, never the cart link before it", () => {
  const raw = `- link "Panier" [ref=e3]:\n  - /url: /fr/panier\n- link "Oppo Find X10 Pro Max 512 Go Gris 5G" [ref=e12]:\n  - /url: /fr/produit/986601/oppo-find-x10-pro-max-512-go-gris-5g.html\n- link "Connexion":\n  - /url: /fr/login`;
  assert.strictEqual(C.urlForTitle(raw, "Oppo Find X10 Pro Max 512 Go Gris 5G", "coolblue.be", "https://www.coolblue.be"), "https://www.coolblue.be/fr/produit/986601/oppo-find-x10-pro-max-512-go-gris-5g.html");
});
t("urlForTitle", () => {
  const raw = `link "Apple iPhone 15 Pro 256GB Zwart" href=https://www.coolblue.nl/product/123/apple-iphone-15-pro.html\nlink "Apple iPhone 15 Pro Max" https://www.coolblue.nl/product/999/max.html`;
  assert.strictEqual(C.urlForTitle(raw, "Apple iPhone 15 Pro 256GB Zwart", "coolblue.nl"), "https://www.coolblue.nl/product/123/apple-iphone-15-pro.html");
});
t("productText", () => {
  const r = C.priceFromProductText("Menu\nApple iPhone 15 Pro 256GB Zwart\n★★★★★ 4,8\n€ 1.199,00\n€ 1.089,00\nVandaag besteld", spec("iPhone 15 Pro", { storage: 256 }));
  assert.strictEqual(r.price, 1089);
});
t("blocked", () => { assert(C.looksBlocked("Please complete the captcha")); assert(!C.looksBlocked("x".repeat(7000) + "captcha")); });
t("expand", () => { assert.strictEqual(C.expandTemplate("https://x/s?q={q}", "iPhone 15 Pro"), "https://x/s?q=iPhone+15+Pro"); assert.strictEqual(C.expandTemplate("https://x/{q_dash}.html", "iPhone 15 Pro"), "https://x/iphone-15-pro.html"); });
console.log(n + " core tests passed");
