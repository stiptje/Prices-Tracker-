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
