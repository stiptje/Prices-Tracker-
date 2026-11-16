"use strict";
/* Prices Tracker front-end – no framework, no build step. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const eur = new Intl.NumberFormat(undefined, { style: "currency", currency: "EUR" });
const fmtTime = iso => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const KIND_DEFAULT_OFF = new Set(["telecom_operator"]);

const S = {
  meta: null, retailers: [], countries: new Set(), kinds: new Set(), shops: new Set(),
  cand: null, storage: null, aliases: [], models: [], queries: [],
  results: new Map(), reports: new Map(), abort: null, total: 0, done: 0, product: null,
};

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), cache: "no-store" } : { cache: "no-store" });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

async function* ndjson(path, body, signal) {
  const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), signal, cache: "no-store" });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  const reader = r.body.getReader(), dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
      if (line) yield JSON.parse(line);
    }
  }
}

/* ============================================================ init */
(async function init() {
  S.meta = await api("/api/meta");
  S.retailers = await api("/api/retailers");
  S.countries = new Set(Object.keys(S.meta.countries));
  S.kinds = new Set(Object.keys(S.meta.kinds).filter(k => !KIND_DEFAULT_OFF.has(k)));
  $("#dbCount").textContent = S.meta.total; $("#demoBanner").hidden = !S.meta.demo;
  renderCountryChips(); renderKinds(); renderShopList(); renderDb(); renderExcluded();
  $$(".tab").forEach(b => b.onclick = () => {
    $$(".tab").forEach(x => x.classList.toggle("active", x === b));
    $("#tab-search").hidden = b.dataset.tab !== "search"; $("#tab-db").hidden = b.dataset.tab !== "db";
  });
  ["optEU", "optRefurb"].forEach(id => $("#" + id).onchange = renderShopList);
  $("#allShops").onclick = () => { visibleShops().forEach(r => S.shops.add(r.id)); renderShopList(true); };
  $("#noShops").onclick = () => { S.shops.clear(); renderShopList(true); };
  $("#idForm").onsubmit = onIdentify;
  $("#cancelBtn").onclick = () => S.abort?.abort();
})();

/* ============================================================ filters */
function renderCountryChips() {
  $("#countryChips").innerHTML = Object.entries(S.meta.countries).map(([c, n]) =>
    `<span class="chipbtn ${S.countries.has(c) ? "on" : ""}" data-c="${c}">${esc(n)} <small>${S.meta.counts[c]} shops</small></span>`).join("");
  $$("#countryChips .chipbtn").forEach(el => el.onclick = () => {
    const c = el.dataset.c; S.countries.has(c) ? S.countries.delete(c) : S.countries.add(c);
    renderCountryChips(); renderShopList();
  });
}
function renderKinds() {
  $("#kindBoxes").innerHTML = Object.entries(S.meta.kinds).map(([k, n]) =>
    `<label class="chk"><input type="checkbox" data-k="${k}" ${S.kinds.has(k) ? "checked" : ""}> ${esc(n)}</label>`).join("");
  $$("#kindBoxes input").forEach(el => el.onchange = () => { el.checked ? S.kinds.add(el.dataset.k) : S.kinds.delete(el.dataset.k); renderShopList(); });
}
function visibleShops() {
  const eu = $("#optEU").checked, refurb = $("#optRefurb").checked;
  return S.retailers.filter(r => S.countries.has(r.country) && S.kinds.has(r.kind)
    && (eu || r.entity_basis === "headquartered") && (refurb || r.condition !== "refurbished"));
}
function renderShopList(keep) {
  const vis = visibleShops();
  if (!keep) { S.shops = new Set(vis.map(r => r.id)); }
  else S.shops = new Set([...S.shops].filter(id => vis.some(r => r.id === id)));
  $("#shopList").innerHTML = vis.map(r =>
    `<label title="${esc(r.website)}"><input type="checkbox" data-id="${r.id}" ${S.shops.has(r.id) ? "checked" : ""}> <span class="cc">${r.country}</span>${esc(r.name)}</label>`).join("");
  $$("#shopList input").forEach(el => el.onchange = () => { el.checked ? S.shops.add(el.dataset.id) : S.shops.delete(el.dataset.id); updSummary(); });
  updSummary();
}
function updSummary() {
  const n = S.shops.size;
  $("#selSummary").textContent = `· ${n} shop${n === 1 ? "" : "s"} selected`;
  const btn = $("#goBtn"); if (btn) btn.disabled = n === 0;
}

/* ============================================================ identify → confirm */
async function onIdentify(e) {
  e.preventDefault();
  const q = $("#q").value.trim(); if (!q) return;
  $("#candidates").innerHTML = `<p class="muted">Identifying…</p>`; $("#confirm").hidden = true;
  let data;
  try { data = await api("/api/identify", { query: q }); }
  catch (err) { $("#candidates").innerHTML = `<p class="chip bad">${esc(err.message)}</p>`; return; }
  const c = data.candidates;
  $("#candidates").innerHTML = `<p class="hint">Which one do you mean? ${data.llm_used ? "(includes AI-suggested candidates)" : ""}</p><div class="cands">` +
    c.map((x, i) => `<div class="cand" data-i="${i}"><div><b>${esc(x.display)}</b>
      <span class="meta">${[x.category !== "custom" ? x.category : "", x.year || "", x.kind === "llm" ? "AI suggestion – please verify" : ""].filter(Boolean).join(" · ")}
      ${x.model_numbers?.length ? "· model no. " + esc(x.model_numbers.join(", ")) : ""}</span></div>
      <span class="conf">${x.kind === "custom" ? "exactly as typed" : Math.round(x.confidence * 100) + "% match"}</span></div>`).join("") + `</div>`;
  $$(".cand").forEach(el => el.onclick = () => selectCandidate(c[+el.dataset.i], el));
  if (c.length && c[0].kind === "catalog" && c[0].confidence >= 0.99) $$(".cand")[0].click();   // exact hit → pre-select, still needs confirm
}

function selectCandidate(c, el) {
  $$(".cand").forEach(x => x.classList.toggle("sel", x === el));
  S.cand = c; S.storage = null;
  S.aliases = [...(c.aliases || [])]; S.models = [...(c.model_numbers || [])];
  renderConfirm();
}

function currentProduct() {
  const c = S.cand;
  return { name: c.name, brand: c.brand || "", aliases: S.aliases, model_numbers: S.models, allow_words: c.allow_words || [] };
}
function previewQueries() {
  const p = currentProduct(), out = [], seen = new Set();
  const add = s => { const k = s.toLowerCase().replace(/\s+/g, " ").trim(); if (k && !seen.has(k)) { seen.add(k); out.push(s.trim()); } };
  if (p.brand && !p.name.toLowerCase().startsWith(p.brand.toLowerCase())) add(`${p.brand} ${p.name}`);
  add(p.name); p.aliases.forEach(add); p.model_numbers.forEach(add);
  return out.slice(0, 4);
}
function renderConfirm() {
  const c = S.cand, box = $("#confirm");
  box.hidden = false; box.className = "confirm";
  const st = (c.storage_gb || []);
  box.innerHTML = `
    <h3>Confirm: ${esc(c.display)}</h3>
    <p class="hint">I will search for this exact model — not its Pro/Max/Plus/Ultra siblings, and not cases or accessories.</p>
    ${st.length ? `<div><b>Storage</b> <span class="hint">(optional)</span><div class="row" id="stor" style="margin:6px 0">
      <span class="pick on" data-s="">Any</span>${st.map(s => `<span class="pick" data-s="${s}">${s >= 1024 ? s / 1024 + " TB" : s + " GB"}</span>`).join("")}</div></div>` : ""}
    <div><b>Alternate names I will also search</b>
      <div class="chips" id="aliasChips"></div>
      <form class="row" id="aliasForm"><input type="text" id="aliasIn" placeholder="add an alternate name or model number…"><button class="small">Add</button></form></div>
    <div><b>Search strings (in this order, first hit wins)</b><div class="qlist" id="qprev"></div>
      <label class="chk"><input type="checkbox" id="allAliases"> Try every alternate name at every shop (slower, finds more)</label></div>
    <div class="row" style="margin-top:10px"><button class="primary" id="goBtn">Confirm &amp; search live</button>
      <span class="muted" id="goHint"></span></div>`;
  $$("#stor .pick").forEach(el => el.onclick = () => {
    $$("#stor .pick").forEach(x => x.classList.toggle("on", x === el)); S.storage = el.dataset.s ? +el.dataset.s : null; });
  $("#aliasForm").onsubmit = e => { e.preventDefault(); const v = $("#aliasIn").value.trim(); if (v) { S.aliases.push(v); $("#aliasIn").value = ""; drawAliases(); } };
  $("#goBtn").onclick = startSearch;
  drawAliases(); updSummary();
}
function drawAliases() {
  const all = [...S.aliases.map((a, i) => ["a", i, a]), ...S.models.map((a, i) => ["m", i, a])];
  $("#aliasChips").innerHTML = all.length ? all.map(([t, i, a]) => `<span class="chip">${esc(a)}${t === "m" ? " <small>model no.</small>" : ""}<button data-t="${t}" data-i="${i}" title="remove">×</button></span>`).join("") : `<span class="muted">none</span>`;
  $$("#aliasChips button").forEach(b => b.onclick = () => { (b.dataset.t === "a" ? S.aliases : S.models).splice(+b.dataset.i, 1); drawAliases(); });
  $("#qprev").innerHTML = previewQueries().map((q, i) => `${i + 1}. ${esc(q)}`).join("<br>");
}

/* ============================================================ live search */
async function startSearch() {
  if (!S.cand || !S.shops.size) return;
  S.results.clear(); S.reports.clear(); S.done = 0; S.total = S.shops.size;
  S.product = currentProduct();
  const body = {
    product: S.product, storage_gb: S.storage, allow_refurbished: $("#optRefurb").checked,
    countries: [...S.countries], retailer_ids: [...S.shops], include_eu_subsidiaries: $("#optEU").checked,
    all_aliases: $("#allAliases").checked, include_unverified: $("#optUnver").checked, queries: previewQueries(),
  };
  S.body = body;
  $("#resultsCard").hidden = false; $("#resultsCard").scrollIntoView({ behavior: "smooth" });
  $("#resTitle").textContent = `· ${S.cand.display}${S.storage ? " " + S.storage + " GB" : ""}`;
  $("#goBtn").disabled = true; $("#cancelBtn").hidden = false; $("#noRes").hidden = true;
  $("#logTable tbody").innerHTML = ""; $("#resTable tbody").innerHTML = "";
  S.abort = new AbortController(); setProgress();
  try {
    for await (const ev of ndjson("/api/search", body, S.abort.signal)) onEvent(ev);
  } catch (err) {
    if (err.name !== "AbortError") { $("#noRes").hidden = false; $("#noRes").textContent = "Search failed: " + err.message; }
  } finally {
    $("#goBtn").disabled = false; $("#cancelBtn").hidden = true; finish();
  }
}

function onEvent(ev) {
  if (ev.type === "result") { S.results.set(ev.result.retailer_id + "|" + ev.result.url, ev.result); renderResults(); }
  else if (ev.type === "retailer_done") { S.reports.set(ev.retailer_id, ev.report); S.done++; setProgress(); renderLog(); }
  else if (ev.type === "note") { /* discovery notes – shown implicitly in the log */ }
}
function setProgress() {
  $("#progress").textContent = `${S.done}/${S.total} shops answered · ${S.results.size} price${S.results.size === 1 ? "" : "s"}`;
  $("#bar").style.width = (S.total ? 100 * S.done / S.total : 0) + "%";
}
function finish() {
  setProgress();
  if (!S.results.size) {
    $("#noRes").hidden = false;
    const blocked = [...S.reports.values()].filter(r => ["blocked", "timeout", "unreachable"].includes(r.status)).length;
    $("#noRes").textContent = `No verified price found at ${S.total} shop(s).` + (blocked ? ` ${blocked} could not be reached or blocked automated access – see the log below.` : "");
    $("#logBox").open = true;
  }
}

function retailerOf(id) { return S.retailers.find(r => r.id === id); }
function renderResults() {
  const rows = [...S.results.values()].sort((a, b) => (b.verified - a.verified) || a.price - b.price);
  $("#resTable tbody").innerHTML = rows.map((r, i) => `
    <tr class="${i === 0 && r.verified ? "best" : ""}" data-k="${esc(r.retailer_id + "|" + r.url)}">
      <td>${i + 1}</td>
      <td class="num"><span class="price">${eur.format(r.price)}</span><br>${r.verified ? '<span class="badge live">verified live</span>' : '<span class="badge unver">listing only</span>'}</td>
      <td><span class="cc">${r.country}</span><b>${esc(r.retailer)}</b>${r.entity_basis !== "headquartered" ? '<br><span class="muted small">EU storefront</span>' : ""}${r.seller ? `<br><span class="muted small">seller: ${esc(r.seller)}</span>` : ""}</td>
      <td>${esc(r.title)}</td>
      <td><span class="chip ${r.condition === "new" ? "good" : "warn"}">${esc(r.condition)}</span></td>
      <td>${esc(r.availability || "–")}</td>
      <td class="muted small"><span class="t" data-t="${esc(r.fetched_at)}">${fmtTime(r.fetched_at)}</span><br><span class="age" data-t="${esc(r.fetched_at)}"></span></td>
      <td><a class="btn small" href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Open ↗</a>
          <button class="small recheck" data-i="${i}">Re-check</button></td></tr>`).join("");
  const arr = rows;
  $$(".recheck").forEach(b => b.onclick = () => recheck(arr[+b.dataset.i], b));
  tickAges();
}
function tickAges() {
  const now = Date.now();
  $$(".age").forEach(el => { const s = Math.max(0, Math.round((now - new Date(el.dataset.t)) / 1000)); el.textContent = s < 90 ? `${s}s ago` : `${Math.round(s / 60)} min ago`; });
}
setInterval(tickAges, 1000);

async function recheck(r, btn) {
  btn.disabled = true; btn.textContent = "…";
  try {
    const out = await api("/api/recheck", { retailer_id: r.retailer_id, url: r.url, product: S.product, storage_gb: S.body.storage_gb, allow_refurbished: S.body.allow_refurbished });
    if (out.ok) {
      const old = r.price; S.results.set(r.retailer_id + "|" + r.url, out.result); renderResults();
      if (old !== out.result.price) alert(`Price changed: ${eur.format(old)} → ${eur.format(out.result.price)}`);
    } else { alert("Could not re-check: " + out.error); btn.disabled = false; btn.textContent = "Re-check"; }
  } catch (e) { alert(e.message); btn.disabled = false; btn.textContent = "Re-check"; }
}

const STATUS_LABEL = { ok: "price found", no_match: "no exact match", blocked: "blocked (bot protection)", timeout: "timed out", unreachable: "unreachable", error: "error", skipped: "stopped" };
function renderLog() {
  const rows = [...S.reports.values()].sort((a, b) => (a.status === "ok" ? 0 : 1) - (b.status === "ok" ? 0 : 1) || a.retailer_id.localeCompare(b.retailer_id));
  $("#logTable tbody").innerHTML = rows.map(rep => { const r = retailerOf(rep.retailer_id) || {};
    return `<tr><td>${esc(r.name || rep.retailer_id)}</td><td>${esc(r.country || "")}</td><td class="st ${rep.status}">${STATUS_LABEL[rep.status] || rep.status}</td>
      <td class="small">${esc(rep.message)}${rep.queries?.length ? `<br><span class="muted">searched: ${esc(rep.queries.join(" | "))}</span>` : ""}</td><td class="num muted small">${(rep.elapsed_ms / 1000).toFixed(1)}s</td></tr>`; }).join("");
  const c = {}; S.reports.forEach(r => c[r.status] = (c[r.status] || 0) + 1);
  $("#logSummary").textContent = "· " + Object.entries(c).map(([k, v]) => `${v} ${STATUS_LABEL[k] || k}`).join(", ");
}

/* ============================================================ database tab */
function renderExcluded() {
  $("#excluded").innerHTML = S.meta.excluded.map(e => `<span class="chip bad" title="${esc(e.reason)}">${esc(e.name)}</span>`).join("");
  const m = (k) => S.retailers.filter(r => r.status === k).length;
  $("#dbNote").innerHTML = `${S.meta.total} storefronts. Verified online: <b>${m("online")}</b> · bot-protected: <b>${m("blocked")}</b> · unreachable: <b>${m("unreachable")}</b> · not yet verified: <b>${m("unverified")}</b>. ` +
    `“Verify” checks each homepage and search URL live from <i>your</i> machine and stores the result.`;
  const cs = $("#dbCountry"), ks = $("#dbKind");
  if (cs.options.length === 1) {
    Object.entries(S.meta.countries).forEach(([c, n]) => cs.add(new Option(n, c)));
    Object.entries(S.meta.kinds).forEach(([k, n]) => ks.add(new Option(n, k)));
    ["dbFilter", "dbCountry", "dbKind", "dbStatus"].forEach(id => $("#" + id).oninput = renderDb);
    $("#verifyBtn").onclick = runVerify;
  }
}
function dbRows() {
  const t = $("#dbFilter").value.toLowerCase(), c = $("#dbCountry").value, k = $("#dbKind").value, s = $("#dbStatus").value;
  return S.retailers.filter(r => (!c || r.country === c) && (!k || r.kind === k) && (!s || r.status === s)
    && (!t || [r.name, r.domain, r.group, r.website].join(" ").toLowerCase().includes(t)));
}
function renderDb() {
  const rows = dbRows();
  $("#dbTable tbody").innerHTML = rows.map(r => `<tr id="db-${r.id}">
    <td><b>${esc(r.name)}</b>${r.group ? `<br><span class="muted small">${esc(r.group)}</span>` : ""}</td><td>${r.country}</td>
    <td>${esc(S.meta.kinds[r.kind])}${r.condition === "refurbished" ? '<br><span class="chip warn">refurbished</span>' : ""}</td>
    <td><a href="${esc(r.website)}" target="_blank" rel="noopener noreferrer">${esc(r.domain)}</a></td>
    <td>${esc(r.hq_country)}<br><span class="muted small">${r.entity_basis === "headquartered" ? "headquartered in Europe" : "EU entity / storefront"}</span></td>
    <td class="small">${r.search_url ? `<code>${esc(r.search_url)}</code><br><span class="muted">${esc(r.search_confidence)}</span>` : '<span class="muted">auto-discover on first use</span>'}</td>
    <td class="st ${r.status}">${esc(r.status)}${r.http_status ? `<br><span class="muted small">HTTP ${r.http_status}</span>` : ""}</td>
    <td class="muted small">${r.last_checked ? new Date(r.last_checked).toLocaleString() : "never"}</td></tr>`).join("");
}
async function runVerify() {
  const ids = dbRows().map(r => r.id); if (!ids.length) return;
  if (ids.length > 40 && !confirm(`Verify ${ids.length} shops live? This sends one or two requests to each shop.`)) return;
  const prog = $("#verifyProg"); let n = 0; $("#verifyBtn").disabled = true; prog.textContent = "Verifying…";
  try {
    for await (const ev of ndjson("/api/verify", { retailer_ids: ids, discover: $("#verifyDiscover").checked, write: true })) {
      if (ev.type === "verified") { n++; prog.textContent = `Verifying… ${n}/${ids.length}`; }
    }
  } catch (e) { prog.textContent = "Verification failed: " + e.message; $("#verifyBtn").disabled = false; return; }
  S.retailers = await api("/api/retailers"); renderDb(); renderExcluded();
  prog.textContent = `Verified ${n} shops.`; $("#verifyBtn").disabled = false;
}
