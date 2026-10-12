"use strict";

// Every value from the data files is rendered with textContent or as an
// attribute set through the DOM API, never through innerHTML: tender titles
// and supplier names are third-party text.

const PAGE_SIZE = 50;
const SEVERITY_ORDER = ["critical", "high", "medium", "low"];
const zar = new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 });
const count = new Intl.NumberFormat("en-ZA");

const el = (id) => document.getElementById(id);
const state = { index: null, rules: new Map(), filtered: [], page: 0, shards: new Map(), trigger: null };

function node(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children) if (c !== null && c !== undefined) n.append(c);
  return n;
}

function money(v) {
  if (v === null || v === undefined || v === "") return "Not published";
  const x = Number(v);
  return Number.isFinite(x) ? zar.format(x) : String(v);
}

function showState(kind, message, action) {
  const box = el("state");
  box.replaceChildren();
  box.className = "state" + (kind === "error" ? " error" : "");
  if (!message) return;
  box.append(node("p", { text: message }));
  if (action) box.append(node("p", {}, action));
}

function severityTag(sev) {
  return node("span", { class: `tag sev-${sev}`, text: sev });
}

async function getJSON(url) {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${url} returned HTTP ${res.status}`);
  return res.json();
}

// ---------- index ----------

async function loadIndex() {
  showState("loading", "Loading scored awards. The index is about 3 MB, so this can take a few seconds on a slow connection.");
  el("table").hidden = true;
  el("pager").hidden = true;
  try {
    const index = await getJSON("data/index.json");
    if (index.schema_version !== 1 || !Array.isArray(index.awards)) {
      throw new Error("data/index.json has an unexpected format");
    }
    state.index = index;
    for (const r of index.rules) state.rules.set(r.id, r);
    renderMeta(index);
    renderRules(index);
    // Read the deep link before applyFilters rewrites the hash.
    const deepLink = new URLSearchParams(location.hash.slice(1)).get("award");
    readFiltersFromHash();
    applyFilters();
    openById(deepLink);
  } catch (err) {
    console.error(err);
    showState(
      "error",
      `Could not load the scored data (${err.message}). Check your connection, then try again. If it keeps failing, the latest deploy may not have finished.`,
      node("button", { type: "button", class: "primary", text: "Try again", onclick: loadIndex }),
    );
  }
}

function renderMeta(index) {
  const when = new Date(index.generated_at);
  const s = index.source || {};
  el("meta").textContent =
    `${count.format(index.summary.awards)} awards scored from ${count.format(s.releases || 0)} contracting processes` +
    ` · ${count.format(s.skipped || 0)} skipped · built ${when.toLocaleString("en-ZA", { dateStyle: "medium", timeStyle: "short" })}`;
  if (s.url && /^https:\/\//.test(s.url)) el("source").href = s.url;
}

function renderRules(index) {
  const box = el("rules");
  const select = el("rule");
  box.replaceChildren();
  select.replaceChildren(node("option", { value: "", text: "Any" }));
  for (const r of index.rules) {
    const fired = index.summary.fired[r.id] || 0;
    const unev = index.summary.not_evaluated[r.id] || 0;
    const all = index.summary.awards;
    const btn = node(
      "button",
      {
        type: "button",
        class: "rule" + (unev === all ? " off" : ""),
        "aria-pressed": "false",
        "data-rule": r.id,
        onclick: () => {
          select.value = select.value === r.id ? "" : r.id;
          applyFilters();
          el("results").focus();
        },
      },
      node("span", { class: "id", text: r.id }),
      node("span", { class: "title", text: r.title }),
      node(
        "span",
        { class: "stats" },
        unev === all ? "not evaluated on this data" : `${count.format(fired)} fired · ${count.format(unev)} not evaluated`,
      ),
    );
    box.append(node("div", { role: "listitem" }, btn));
    select.append(node("option", { value: r.id, text: `${r.id} ${r.title}` }));
  }
}

// ---------- filtering and list ----------

function filters() {
  const minRaw = el("min").value.trim();
  const min = minRaw === "" ? 0 : Math.max(0, Math.min(100, Number.parseInt(minRaw, 10) || 0));
  return { q: el("q").value.trim().toLowerCase().slice(0, 120), rule: el("rule").value, min };
}

function applyFilters() {
  const { q, rule, min } = filters();
  const words = q.split(/\s+/).filter(Boolean);
  state.filtered = state.index.awards.filter((a) => {
    if (a.score < min) return false;
    if (rule && !a.fired.includes(rule)) return false;
    if (words.length) {
      const hay = `${a.title} ${a.buyer} ${a.supplier}`.toLowerCase();
      if (!words.every((w) => hay.includes(w))) return false;
    }
    return true;
  });
  state.page = 0;
  for (const b of document.querySelectorAll(".rule")) {
    b.setAttribute("aria-pressed", String(b.dataset.rule === rule));
  }
  writeFiltersToHash();
  renderList();
}

function renderList() {
  const total = state.filtered.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const start = state.page * PAGE_SIZE;
  const slice = state.filtered.slice(start, start + PAGE_SIZE);

  el("count").textContent = total
    ? `Showing ${count.format(start + 1)}-${count.format(start + slice.length)} of ${count.format(total)} awards`
    : "";

  if (!total) {
    el("table").hidden = true;
    el("pager").hidden = true;
    showState(
      "empty",
      "No awards match these filters. Lower the minimum score, pick a different rule, or clear the search.",
      node("button", { type: "button", class: "ghost", text: "Clear filters", onclick: () => el("filters").reset() }),
    );
    return;
  }
  showState("success", "");

  const rows = slice.map((a) => {
    const flags = node("td");
    if (a.fired.length === 0) flags.append(node("span", { class: "tag st-clear", text: "none" }));
    for (const id of a.fired) {
      const r = state.rules.get(id);
      const tag = node("span", { class: `tag sev-${r ? r.severity : "low"}`, text: id, title: r ? r.title : id });
      flags.append(tag);
    }
    const open = node("button", {
      type: "button",
      class: "open",
      text: a.title || a.ocid,
      onclick: (e) => openDetail(a, e.currentTarget),
    });
    return node(
      "tr",
      {},
      node("td", { class: "num" }, node("span", { class: "score", text: String(a.score) })),
      flags,
      node("td", { class: "title" }, open),
      node("td", { text: a.buyer }),
      node("td", { text: a.supplier }),
      node("td", { class: "num", text: money(a.value) }),
      node("td", { text: a.close_date || "Not published" }),
    );
  });
  el("rows").replaceChildren(...rows);
  el("table").hidden = false;

  el("pager").hidden = pages <= 1;
  el("page").textContent = `Page ${state.page + 1} of ${pages}`;
  el("prev").disabled = state.page === 0;
  el("next").disabled = state.page >= pages - 1;
}

// ---------- detail ----------

async function openDetail(award, trigger) {
  state.trigger = trigger || null;
  const dlg = el("detail");
  el("detail-title").textContent = award.title || award.ocid;
  el("detail-body").replaceChildren(node("p", { role: "status", text: "Loading the rule breakdown." }));
  if (!dlg.open) dlg.showModal();
  history.replaceState(null, "", `#${hashParams({ award: award.id })}`);

  try {
    let shard = state.shards.get(award.shard);
    if (!shard) {
      if (!/^[0-9a-f]{2}$/.test(award.shard)) throw new Error("invalid shard id");
      shard = await getJSON(`data/details/${award.shard}.json`);
      state.shards.set(award.shard, shard);
    }
    const detail = shard[award.id];
    if (!detail) throw new Error("award missing from its detail file");
    renderDetail(award, detail);
  } catch (err) {
    console.error(err);
    el("detail-body").replaceChildren(
      node("p", { text: `Could not load the breakdown (${err.message}).` }),
      node("button", { type: "button", class: "primary", text: "Try again", onclick: () => openDetail(award, trigger) }),
    );
  }
}

function renderDetail(award, detail) {
  const facts = node("dl", { class: "facts" });
  const add = (k, v) => facts.append(node("dt", { text: k }), node("dd", { text: v }));
  add("Buyer", award.buyer);
  add("Supplier", award.supplier);
  add("Category", award.category || "Not published");
  add("Award value", money(award.value));
  add("Tender closed", award.close_date || "Not published");
  add("OCDS id", award.ocid);

  const level = detail.level === "none" ? "below flag level" : detail.level;
  const scoreline = node(
    "div",
    { class: "scoreline" },
    node("span", { class: "big", text: String(detail.score) }),
    node("span", { text: `of 100 · ${level}` }),
    node("span", {
      text: `${Math.round(detail.coverage * 100)}% of rules could be evaluated` +
        (detail.uncapped_score > detail.score ? ` · uncapped ${detail.uncapped_score}` : ""),
    }),
  );

  const list = node("ul", { class: "breakdown" });
  for (const r of detail.breakdown) list.append(ruleItem(r, award));

  el("detail-body").replaceChildren(facts, scoreline, node("h3", { class: "sr-only", text: "Rule breakdown" }), list);
}

function ruleItem(r, award) {
  const status = !r.evaluated
    ? node("span", { class: "tag st-unevaluated", text: "not evaluated" })
    : r.fired
      ? severityTag(r.severity)
      : node("span", { class: "tag st-clear", text: "clear" });
  const li = node(
    "li",
    { class: r.fired ? "fired" : "" },
    node(
      "div",
      { class: "row" },
      node("span", { class: "rid", text: r.rule_id }),
      node("span", { class: "rtitle", text: r.title }),
      status,
      node("span", { class: "pts", text: r.fired ? `+${r.points}` : "0" }),
    ),
  );

  const ev = node("dl", { class: "evidence" });
  for (const [k, v] of Object.entries(r.evidence || {})) {
    if (k === "comparables") continue;
    ev.append(node("dt", { text: k.replaceAll("_", " ") }), node("dd", { text: formatValue(k, v) }));
  }
  if (ev.childElementCount) li.append(ev);

  if (r.fired && Array.isArray(r.evidence?.comparables)) li.append(priceChart(r.evidence, award));
  return li;
}

function formatValue(key, v) {
  if (v === null || v === undefined) return "none";
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "object") return JSON.stringify(v);
  if (key === "percent_vs_median") return `${v > 0 ? "+" : ""}${count.format(v)}%`;
  if (key === "award_value" || key === "comparable_median") return money(v);
  return String(v);
}

function priceChart(evidence, award) {
  const rows = [
    { label: "This award", value: Number(evidence.award_value), cls: "this" },
    { label: `Median of ${evidence.comparable_count} comparable awards`, value: Number(evidence.comparable_median), cls: "median" },
    ...evidence.comparables.map((c) => ({
      label: `${c.buyer_name || "Unknown buyer"} · ${c.close_date || ""}`,
      value: Number(c.award_value),
      cls: "",
    })),
  ].filter((r) => Number.isFinite(r.value) && r.value > 0);
  // Log scale: values in one category routinely span three orders of magnitude.
  const logs = rows.map((r) => Math.log10(r.value));
  const lo = Math.min(...logs) - 0.1;
  const hi = Math.max(...logs);
  const span = Math.max(hi - lo, 0.001);

  const fig = node("figure", { class: "chart" });
  fig.append(node("h3", { text: "Award value against recent comparable awards (log scale)" }));
  for (const r of rows) {
    const pct = Math.max(2, ((Math.log10(r.value) - lo) / span) * 100);
    const fill = node("div", { class: "fill" });
    fill.style.width = `${pct.toFixed(1)}%`;
    fig.append(
      node(
        "div",
        { class: `bar ${r.cls}`.trim() },
        node("span", { class: "label", text: r.label, title: r.label }),
        node("div", { class: "track", "aria-hidden": "true" }, fill),
        node("span", { class: "v", text: money(r.value) }),
      ),
    );
  }
  return fig;
}

function closeDetail() {
  const dlg = el("detail");
  if (dlg.open) dlg.close();
}

// ---------- URL state ----------

function hashParams(extra = {}) {
  const { q, rule, min } = filters();
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (rule) p.set("rule", rule);
  if (min) p.set("min", String(min));
  for (const [k, v] of Object.entries(extra)) p.set(k, v);
  return p.toString();
}

function writeFiltersToHash() {
  const h = hashParams();
  history.replaceState(null, "", h ? `#${h}` : location.pathname);
}

function readFiltersFromHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  el("q").value = (p.get("q") || "").slice(0, 120);
  const rule = p.get("rule") || "";
  el("rule").value = state.rules.has(rule) ? rule : "";
  const min = Number.parseInt(p.get("min") || "0", 10);
  el("min").value = Number.isFinite(min) ? String(Math.max(0, Math.min(100, min))) : "0";
}

function openById(id) {
  if (!id) return;
  const award = state.index.awards.find((a) => a.id === id);
  if (award) openDetail(award, null);
}

// ---------- wiring ----------

document.addEventListener("DOMContentLoaded", () => {
  let timer;
  el("q").addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(applyFilters, 200);
  });
  el("rule").addEventListener("change", applyFilters);
  el("min").addEventListener("change", applyFilters);
  el("filters").addEventListener("submit", (e) => {
    e.preventDefault();
    applyFilters();
  });
  el("filters").addEventListener("reset", () => setTimeout(applyFilters, 0));
  el("prev").addEventListener("click", () => { state.page -= 1; renderList(); el("results").focus(); });
  el("next").addEventListener("click", () => { state.page += 1; renderList(); el("results").focus(); });
  el("close").addEventListener("click", closeDetail);
  el("detail").addEventListener("click", (e) => { if (e.target === e.currentTarget) closeDetail(); });
  el("detail").addEventListener("close", () => {
    writeFiltersToHash();
    if (state.trigger && document.contains(state.trigger)) state.trigger.focus();
    state.trigger = null;
  });
  loadIndex();
});
