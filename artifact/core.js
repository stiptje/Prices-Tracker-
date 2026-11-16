/* Prices Tracker core – pure logic, no DOM, no network. Inlined into the artifact by build_artifact.py
   and unit-tested in Node (artifact/test_core.js). Mirrors pricetracker/matcher.py + catalog.py. */

const strip = s => String(s ?? "").normalize("NFKD").replace(/[̀-ͯ]/g, "");

function normalize(text) {
  if (!text) return "";
  let s = strip(text).toLowerCase().replace(/ß/g, "ss").replace(/\+/g, " plus ");
  s = s.replace(/[^a-z0-9]+/g, " ");
  s = s.replace(/(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])/g, " ");
  return s.split(/\s+/).filter(Boolean).join(" ");
}
const tokens = t => { const n = normalize(t); return n ? n.split(" ") : []; };
function findSeq(hay, needle) {
  const n = needle.length;
  if (!n || n > hay.length) return -1;
  outer: for (let i = 0; i <= hay.length - n; i++) {
    for (let j = 0; j < n; j++) if (hay[i + j] !== needle[j]) continue outer;
    return i;
  }
  return -1;
}

/* ------------------------------------------------------------------ prices */
function parsePrice(raw) {
  if (raw == null) return null;
  if (typeof raw === "number") return raw >= 0 ? raw : null;
  let s = String(raw).replace(/[.,]-+\s*$/, "").replace(/[^\d,.]/g, "").replace(/^[.,]+|[.,]+$/g, "");
  if (!s) return null;
  if (s.includes(",") && s.includes(".")) {
    s = s.lastIndexOf(",") > s.lastIndexOf(".") ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
  } else if (s.includes(",")) {
    const i = s.lastIndexOf(","), tail = s.slice(i + 1);
    s = (tail.length === 1 || tail.length === 2) ? s.slice(0, i).replace(/,/g, "") + "." + tail : s.replace(/,/g, "");
  } else if (s.includes(".")) {
    const i = s.lastIndexOf("."), head = s.slice(0, i), tail = s.slice(i + 1);
    if ((tail.length === 3 && /^\d{1,3}(\.\d{3})*$/.test(head)) || s.split(".").length > 2) s = s.replace(/\./g, "");
  }
  const v = parseFloat(s);
  return Number.isFinite(v) && v >= 0 ? v : null;
}

const NUM = String.raw`\d{1,3}(?:,\d{3})+\.\d{1,2}|\d{1,3}(?:[.\u00a0\u202f ]\d{3})*(?:[.,]\d{1,2}|[.,]-+)?|\d+(?:[.,]\d{1,2}|[.,]-+)?`;
const PRICE_RE = new RegExp(String.raw`(?:€|EUR)\s*(${NUM})|(${NUM})\s*(?:€|EUR)(?![A-Za-z])|(?<![\d.,])(\d{1,3}(?:\.\d{3})*,-+)`, "g");
const NOT_CURRENT = /\b(per\s*(maand|mnd|month|mois)|\/\s*(mnd|maand|mois|mo|monat|month)|par mois|pro monat|monatlich|maandelijks|mtl\.?|x\s*\d+\s*(€|mois)|\d+\s*x\s*(€|\d)|vanaf|ab\s*\d|dès|des|from|bespaar|economisez|ersparnis|sparen|save|korting|remise|rabatt|adviesprijs|uvp|statt|was|avant|ancien|verzend|livraison|versand|shipping|gratis|offert)\b/i;

/** All EUR amounts in a line (current-price candidates only unless `all`). */
function pricesInLine(line, all = false) {
  if (!all && NOT_CURRENT.test(strip(line))) return [];
  const out = [];
  for (const m of line.matchAll(PRICE_RE)) {
    const v = parsePrice(m[1] || m[2] || m[3]);
    if (v != null && v >= 5 && v < 20000) out.push(v);
  }
  return out;
}

/* ------------------------------------------------------------------ matcher */
const VARIANT = new Set("pro max plus ultra mini fe lite edge neo air xl fold flip se e t s r x gt turbo note go play prime core power active classic slim spro ce c a i v k".split(" "));
const ACC = new Set(("case cases cover covers bumper screenprotector protector protectors tempered charger cable adapter adaptor holder mount lanyard powerbank sleeve wallet pouch stylus dock magsafe replacement repair tripod gimbal headphones " +
  "hoes hoesje hoesjes beschermglas beschermfolie oplader kabel houder telefoonhoesje reparatie coque etui housse chargeur protege rechange reparation cordon " +
  "hulle huelle schutzhulle schutzfolie panzerglas ladegerat ladekabel halterung displayschutz tasche ersatzteil armband ersatz reparatur").split(" "));
const WEAK_ACC = new Set("screen glass film skin lens battery stand strap support verre trempe ecran scherm schutz folie bescherming charging housse display".split(" "));
const FOR = new Set("voor pour fur for compatible compatibel kompatibel geschikt compatibles kompatible fits fit passend adapte avec mit with met ersatz und".split(" "));
const REFURB = new Set("refurbished refurb renewed reconditionne reconditionnee reconditionnes gebraucht aufbereitet generaluberholt tweedehands gerenoveerd refurbed preowned occasion used".split(" "));
const REFURB_PH = [["second", "hand"], ["remis", "a", "neuf"], ["pre", "owned"], ["tres", "bon", "etat"], ["comme", "neuf"]];

function parseStorage(norm) {
  const out = new Set();
  for (const m of norm.matchAll(/\b(\d{1,4}) ?(gb|go|tb|to)\b/g)) out.add(+m[1] * (m[2] === "tb" || m[2] === "to" ? 1024 : 1));
  return out;
}

function nameSeqs(spec) {
  const names = [spec.name, ...(spec.aliases || [])];
  if (spec.brand) names.push(`${spec.brand} ${spec.name}`);
  const seen = new Set(), out = [];
  for (const n of names) { const t = tokens(n); const k = t.join(" "); if (t.length && !seen.has(k)) { seen.add(k); out.push(t); } }
  return out.sort((a, b) => b.length - a.length);
}

function judge(spec, title, retailerCond = "new") {
  const toks = tokens(title);
  if (!toks.length) return { ok: false, reason: "empty" };
  const norm = toks.join(" ");
  for (const ex of spec.exclude || []) { const et = tokens(ex); if (et.length && findSeq(toks, et) >= 0) return { ok: false, reason: "excluded term" }; }
  let pos = -1, matched = null, viaNum = false;
  for (const s of nameSeqs(spec)) { const i = findSeq(toks, s); if (i >= 0) { pos = i; matched = s; break; } }
  if (pos < 0) for (const m of spec.models || []) { const s = tokens(m); const i = s.length ? findSeq(toks, s) : -1; if (i >= 0) { pos = i; matched = s; viaNum = true; break; } }
  if (pos < 0) return { ok: false, reason: "model not in title" };
  const end = pos + matched.length, own = new Set(tokens(spec.name));
  if (!viaNum && end < toks.length) {
    const nxt = toks[end];
    if (VARIANT.has(nxt) && nxt !== matched[matched.length - 1]) {
      if (nxt.length > 1 || (end > 0 && /^\d+$/.test(toks[end - 1]))) return { ok: false, reason: `different variant (${nxt})` };
    }
  }
  if (toks.slice(Math.max(0, pos - 4), pos).some(t => FOR.has(t))) return { ok: false, reason: "accessory (for <model>)" };
  const allow = new Set((spec.allow || []).flatMap(tokens));
  const bad = toks.find(t => ACC.has(t) && !own.has(t) && !allow.has(t));
  if (bad) return { ok: false, reason: `accessory word ${bad}` };
  const near = [...toks.slice(Math.max(0, pos - 2), pos), ...toks.slice(end, end + 1)];
  const weak = near.find(t => WEAK_ACC.has(t) && !own.has(t) && !allow.has(t));
  if (weak) return { ok: false, reason: `accessory word ${weak}` };
  let cond = retailerCond === "refurbished" ? "refurbished" : "new";
  if (cond === "new" && (toks.some(t => REFURB.has(t)) || REFURB_PH.some(p => findSeq(toks, p) >= 0))) cond = "refurbished";
  if (cond === "refurbished" && !spec.refurb) return { ok: false, reason: "refurbished (not requested)" };
  const sizes = parseStorage(norm);
  let storage = null;
  if (spec.storage) {
    if (sizes.size && !sizes.has(spec.storage)) return { ok: false, reason: `other storage` };
    if (sizes.has(spec.storage)) storage = spec.storage;
  } else if (sizes.size) storage = Math.max(...sizes);
  return { ok: true, reason: "match", cond, storage };
}

function searchQueries(spec, limit = 4) {
  const c = [];
  if (spec.brand && !spec.name.toLowerCase().startsWith(spec.brand.toLowerCase())) c.push(`${spec.brand} ${spec.name}`);
  c.push(spec.name, ...(spec.aliases || []), ...(spec.models || []));
  const seen = new Set(), out = [];
  for (const q of c) { const k = tokens(q).join(" "); if (k && !seen.has(k)) { seen.add(k); out.push(q.trim()); } }
  return out.slice(0, limit);
}

/* ------------------------------------------------------------------ identification */
function ratio(a, b) {              // Ratcliff/Obershelp-ish via LCS-free bigram Dice – cheap & typo tolerant
  if (a === b) return 1; if (a.length < 2 || b.length < 2) return 0;
  const bg = s => { const m = new Map(); for (let i = 0; i < s.length - 1; i++) { const g = s.slice(i, i + 2); m.set(g, (m.get(g) || 0) + 1); } return m; };
  const A = bg(a), B = bg(b); let hit = 0;
  for (const [g, n] of A) hit += Math.min(n, B.get(g) || 0);
  return (2 * hit) / (a.length + b.length - 2);
}
const BRANDS = new Set("apple samsung google xiaomi redmi poco oneplus nothing motorola fairphone sony honor oppo asus huawei realme lg nokia hmd".split(" "));

function identify(query, catalog, limit = 6) {
  const qn = normalize(query), qt = qn.split(" ").filter(Boolean);
  if (!qt.length) return [];
  const qset = new Set(qt), scored = [];
  for (const p of catalog) {
    const display = p.b && !p.n.toLowerCase().startsWith(p.b.toLowerCase()) ? `${p.b} ${p.n}` : p.n;
    let best = 0;
    for (const nm of [p.n, display, ...(p.a || []), ...(p.m || [])]) {
      const nt = tokens(nm); if (!nt.length) continue;
      const nset = new Set(nt); let inter = 0; for (const t of qset) if (nset.has(t)) inter++;
      if (!inter) continue;
      const prec = inter / nset.size, rec = inter / qset.size, f1 = 2 * prec * rec / (prec + rec);
      const qn_ = [...qset].filter(t => /^\d+$/.test(t)), nn_ = [...nset].filter(t => /^\d+$/.test(t));
      let mult = 1;
      if (qn_.length && nn_.length && !qn_.some(x => nn_.includes(x))) mult = 0.4; else if (qn_.length && !nn_.length) mult = 0.7;
      const r = ratio(qn, nt.join(" "));
      best = Math.max(best, f1 * mult, r * 0.92 * mult);
      if (qn.includes(nt.join(" "))) best = Math.max(best, 0.55 + 0.4 * (nt.length / Math.max(qt.length, 1)));
    }
    if (best >= 0.5) scored.push([best, p, display]);
  }
  scored.sort((x, y) => y[0] - x[0] || (y[1].y || 0) - (x[1].y || 0) || x[1].n.length - y[1].n.length);
  const out = scored.slice(0, limit).map(([s, p, display]) => ({
    kind: "catalog", id: p.id, confidence: Math.round(s * 100) / 100, display, brand: p.b || "", name: p.n, year: p.y || null,
    category: p.c || "smartphone", storage: p.s || [], aliases: p.a || [], models: p.m || [], allow: p.w || [],
  }));
  const brand = qt.find(t => BRANDS.has(t)) || "";
  out.push({ kind: "custom", id: "custom", confidence: 0, display: `Search exactly: “${query.trim()}”`, brand: brand ? brand[0].toUpperCase() + brand.slice(1) : "",
    name: query.trim(), year: null, category: "custom", storage: [], aliases: [], models: [], allow: [] });
  return out;
}

/* ------------------------------------------------------------------ reading a shop page (text) */
const BLOCK = /(captcha|are you a robot|robot check|unusual traffic|access denied|request blocked|just a moment|verifying you are human|pardon our interruption|bot detection|ihre anfrage wurde blockiert|vous avez été bloqué|attention required|enable javascript and cookies)/i;
const looksBlocked = text => (text || "").length < 6000 && BLOCK.test(text || "");

const PRICE_ONLY = new RegExp(String.raw`^\W{0,3}(?:€|EUR)?\s*(?:${NUM})\s*(?:€|EUR)?\W{0,3}$`);
/** A struck-through old price and the current price often sit on adjacent price-only lines. */
function withSecondPrice(prices, lines, next, snippet) {
  if (prices.length !== 1) return prices;
  for (let k = next; k < Math.min(lines.length, next + 2); k++) {
    if (!PRICE_ONLY.test(lines[k])) break;
    const p = pricesInLine(lines[k]);
    if (p.length) { snippet.push(lines[k]); return [prices[0], p[0]]; }
  }
  return prices;
}

/** Listings in the visible text of a search-results page: a title line that matches the model + the nearby current price. */
function listingsFromText(text, spec, retailerCond = "new") {
  const lines = String(text || "").split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  const fam = tokens(spec.name).find(t => !/^\d+$/.test(t) && t.length > 2) || "";
  const out = [], seen = new Set();
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.length > 240 || line.length < 6) continue;
    const v = judge(spec, line, retailerCond);
    if (!v.ok) continue;
    let prices = pricesInLine(line);
    const snippet = [line];
    let j = i + 1;
    for (; j <= i + 7 && j < lines.length && !prices.length; j++) {
      if (fam && tokens(lines[j]).includes(fam)) break;                 // next product starts
      snippet.push(lines[j]);
      prices = pricesInLine(lines[j]);
    }
    prices = withSecondPrice(prices, lines, j, snippet);
    if (!prices.length) continue;
    // a struck-through old price + current price sit together: the lower of the first two is the current one
    const price = prices.length > 1 && prices[1] / prices[0] > 0.5 && prices[1] < prices[0] ? prices[1] : prices[0];
    const key = tokens(line).join(" ") + "|" + price;
    if (seen.has(key)) continue; seen.add(key);
    out.push({ title: line, price, cond: v.cond, storage: v.storage, evidence: snippet.join(" ⏎ ").slice(0, 260) });
  }
  return out;
}

function urlsFrom(raw, domain) {
  const found = [];
  for (const m of String(raw || "").matchAll(/https?:\/\/[^\s"'<>)\]]+/g)) {
    let u = m[0].replace(/[.,;]+$/, "");
    try { const h = new URL(u).hostname; if (h === domain || h.endsWith("." + domain)) found.push({ url: u, at: m.index }); } catch { /* skip */ }
  }
  return found;
}
/** nearest URL to where `title` occurs in `raw` (read_page / find output) */
function urlForTitle(raw, title, domain) {
  const urls = urlsFrom(raw, domain); if (!urls.length) return null;
  const at = String(raw).indexOf(title.slice(0, 30));
  if (at < 0) return null;
  let best = null, bd = 600;
  for (const u of urls) { const d = Math.abs(u.at - at); if (d < bd) { bd = d; best = u.url; } }
  return best;
}

/** price on a product page's text: first valid current price within the first lines after the model title */
function priceFromProductText(text, spec) {
  const lines = String(text || "").split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  for (let i = 0; i < Math.min(lines.length, 80); i++) {
    if (judge(spec, lines[i], "new").ok || judge({ ...spec, refurb: true }, lines[i], "new").ok) {
      for (let j = i; j < Math.min(lines.length, i + 25); j++) {
        let p = pricesInLine(lines[j]);
        if (p.length) { const sn = lines.slice(i, j + 1); p = withSecondPrice(p, lines, j + 1, sn);
          return { price: p.length > 1 && p[1] < p[0] && p[1] / p[0] > 0.5 ? p[1] : p[0], title: lines[i], evidence: sn.join(" ⏎ ").slice(0, 260) }; }
      }
    }
  }
  return null;
}

function expandTemplate(tpl, q) {
  const dash = tokens(q).join("-") || encodeURIComponent(q);
  return tpl.replace("{q_path}", encodeURIComponent(q)).replace("{q_dash}", dash).replace("{q}", encodeURIComponent(q).replace(/%20/g, "+"));
}
const GUESS_PATTERNS = { BE: ["/zoeken?q={q}", "/search?q={q}", "/recherche?q={q}"], NL: ["/zoeken?q={q}", "/search?q={q}", "/zoeken?query={q}"],
  FR: ["/recherche?q={q}", "/search?q={q}", "/catalogsearch/result/?q={q}"], DE: ["/suche?q={q}", "/search?q={q}", "/catalogsearch/result/?q={q}"] };

if (typeof module !== "undefined") module.exports = { normalize, tokens, parsePrice, pricesInLine, judge, searchQueries, identify, listingsFromText, urlForTitle, urlsFrom, priceFromProductText, expandTemplate, looksBlocked, GUESS_PATTERNS };
