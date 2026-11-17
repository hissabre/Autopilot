/* Autopilot desktop UI — vanilla JS, no build step. */
"use strict";

/* ───────── plumbing ───────── */
const TOKEN = new URLSearchParams(location.search).get("t") || sessionStorage.getItem("t") || "";
sessionStorage.setItem("t", TOKEN);
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
async function api(path, body) {
  const r = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}
const clone = (o) => JSON.parse(JSON.stringify(o));
const getPath = (o, p) => p.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
function setPath(o, p, v) {
  const ks = p.split("."); let a = o;
  ks.slice(0, -1).forEach((k, i) => { if (a[k] == null) a[k] = /^\d+$/.test(ks[i + 1]) ? [] : {}; a = a[k]; });
  a[ks.at(-1)] = v;
}
function ago(iso) {
  if (!iso) return "";
  const d = new Date(iso.includes("T") && !/[Z+]/.test(iso.slice(10)) ? iso : iso);
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
function until(iso) {
  if (!iso) return "";
  const s = (new Date(iso).getTime() - Date.now()) / 1000;
  if (s <= 30) return "any moment";
  if (s < 3600) return `in ${Math.ceil(s / 60)} min`;
  return `in ${Math.floor(s / 3600)} h ${Math.ceil((s % 3600) / 60)} min`;
}
const fmt = (n) => (n ?? 0).toLocaleString();
function toast(msg, err = false) {
  const t = document.createElement("div");
  t.className = "toast" + (err ? " err" : "");
  t.innerHTML = `${icon(err ? "alert" : "check")}<span>${esc(msg)}</span>`;
  $("#toasts").append(t);
  setTimeout(() => { t.style.transition = "opacity .3s"; t.style.opacity = 0; setTimeout(() => t.remove(), 300); }, 3200);
}
function openExternal(url) { api("/api/open", { url }).catch(() => window.open(url, "_blank")); }
document.addEventListener("click", (e) => {
  const a = e.target.closest("a[data-ext]");
  if (a) { e.preventDefault(); openExternal(a.dataset.ext); }
});

/* ───────── icons (lucide-style strokes) ───────── */
const I = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.8c2 .7 3.2 2.5 3.6 5.2"/>',
  inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5.5 5h13L21 13v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-6z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
  pulse: '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  play: '<path d="M7 4.5v15l12-7.5z"/>',
  flask: '<path d="M9 3h6M10 3v6L4.5 18.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3"/><path d="M7.5 15h9"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5v.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3.5 6.5 8.5 6.5 8.5-6.5"/>',
  reply: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5A5.5 5.5 0 0 1 20 14.5V20"/>',
  phone: '<path d="M21 16.5v3a2 2 0 0 1-2.2 2A19.5 19.5 0 0 1 2.5 5.2 2 2 0 0 1 4.5 3h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.5 10.8a16 16 0 0 0 4.7 4.7l1.2-1.2a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
  ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
  dollar: '<path d="M12 2v20M17 6.5C17 4.6 14.8 3.5 12 3.5S7 4.7 7 7s2.2 3.2 5 3.8 5 1.5 5 3.9-2.2 3.8-5 3.8-5-1.1-5-3"/>',
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/>',
  pin: '<path d="M12 21s-7-6-7-11.5a7 7 0 0 1 14 0C19 15 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  wand: '<path d="m15 4 5 5L9 20H4v-5z"/><path d="m13 6 5 5"/>',
  send: '<path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/>',
  folder: '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h4l2 2.5h9A1.5 1.5 0 0 1 21 9v9.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 18.5z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M5.5 7l1 12.5A1.5 1.5 0 0 0 8 21h8a1.5 1.5 0 0 0 1.5-1.5L18.5 7M9 7V4h6v3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  building: '<rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2"/>',
  plug: '<path d="M9 2v5M15 2v5M6 7h12v4a6 6 0 0 1-12 0zM12 17v5"/>',
  map: '<path d="M9 4 3 6.5v13.5l6-2.5 6 2.5 6-2.5V4l-6 2.5z"/><path d="M9 4v13.5M15 6.5V20"/>',
  tag: '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  app: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
};
function icon(n) { return `<i data-i="${n}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${I[n] || ""}</svg></i>`; }
function hydrateIcons(root = document) { $$("i[data-i]:empty", root).forEach((el) => { el.outerHTML = icon(el.dataset.i); }); }

/* ───────── domain vocab ───────── */
const STATUS = {
  found: ["New", ""], no_email: ["No email", ""], enriched: ["Researched", "blue"], site_built: ["Site designed", "blue"],
  deployed: ["Site live", "blue"], contacted: ["Emailed", "violet"], followed_up: ["Followed up", "violet"],
  interested: ["Interested", "lime"], question: ["Asked a question", "amber"], needs_human: ["Needs you", "amber"],
  not_interested: ["Not interested", "red"], unsubscribed: ["Unsubscribed", "red"], bounced: ["Bounced", "red"],
  won: ["Client", "green"], lost: ["Lost", ""],
};
const pill = (s) => { const [l, c] = STATUS[s] || [s, ""]; return `<span class="pill ${c}">${esc(l)}</span>`; };
const FILTERS = [
  ["all", "All", null], ["prospects", "Prospects", ["found", "no_email", "enriched", "site_built", "deployed"]],
  ["emailed", "Emailed", ["contacted", "followed_up"]], ["hot", "Hot", ["interested", "question", "needs_human"]],
  ["won", "Clients", ["won"]], ["closed", "Closed", ["not_interested", "unsubscribed", "bounced", "lost"]],
];
const EV = {
  found: ["Found on Google Maps", "pin"], enriched: ["Public email found", "mail"], skipped: ["Skipped", "x"],
  site_built: ["Website designed", "wand"], deployed: ["Website published", "globe"], emailed: ["First email sent", "send"],
  followed_up: ["Follow-up sent", "send"], reply_in: ["They replied", "reply"], reply_out: ["Auto-reply sent", "send"],
  unsubscribe: ["Unsubscribed", "x"], not_interested: ["Not interested", "x"], bounced: ["Email bounced", "alert"],
  won: ["Became a client", "trophy"], lost: ["Marked lost", "x"], call_started: ["AI call started", "phone"],
  call_done: ["Call summary", "phone"], needs_human: ["Handed over to you", "alert"], handled: ["You handled it", "check"],
  taken_down: ["Demo taken down", "trash"],
};
const evLabel = (k) => (EV[k] || [k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()), k.includes("error") ? "alert" : "spark"]);
const PALETTE = ["#2B2F38", "#7A4E2D", "#2D6A4F", "#6B3FA0", "#9E3D52", "#1F5F8B", "#8A6D1A", "#3F5A3A"];
function avatar(name, big = false) {
  const words = String(name || "?").replace(/[^\p{L}\p{N} ]/gu, "").split(/\s+/).filter((w) => !/^(the|and|le|la|les|de|chez)$/i.test(w));
  const ini = (words[0]?.[0] || "?") + (words[1]?.[0] || "");
  let h = 0; for (const c of String(name)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return `<span class="av" style="background:${PALETTE[h % PALETTE.length]}">${esc(ini.toUpperCase())}</span>`;
}
const stars = (r) => (r ? `<span class="stars">★</span> <b class="num">${Number(r).toFixed(1)}</b>` : "—");
function money(mrr) {
  const e = Object.entries(mrr || {});
  if (!e.length) return "0";
  return e.map(([c, v]) => `${fmt(Math.round(v))} <small style="font-size:14px;color:inherit;opacity:.7">${esc(c)}</small>`).join(" · ");
}

/* ───────── state ───────── */
const S = { view: "overview", state: null, leads: [], filter: "all", q: "", logN: 0, log: [], settings: null, setTab: "business", leadsSig: "" };

/* ───────── sidebar / autopilot ───────── */
function renderPilot() {
  const st = S.state; if (!st) return;
  const r = st.runner, p = $("#pilot");
  p.classList.toggle("on", r.enabled); p.classList.toggle("busy", r.running);
  const sw = $("#pilotSwitch"); sw.setAttribute("aria-checked", String(r.enabled));
  const stepLabel = r.step ? (r.steps.find((s) => s.id === r.step) || {}).label : null;
  $("#pilotStatus").innerHTML = `<span class="dot"></span><span>${r.running ? "Working" : r.enabled ? "Running" : "Paused"}</span>`;
  $("#pilotSub").textContent = r.running ? `${stepLabel || "Starting"}…` : r.enabled ? `Next run ${until(r.next_run)}` :
    r.last_run ? `Last run ${ago(r.last_run)}` : "Switch on to start finding clients";
  $("#runNow").disabled = r.running;
  $("#modePill").hidden = !st.test_mode;
  $("#brandName").textContent = st.brand;
  const n = st.kpis.needs_you; const b = $("#needsBadge"); b.hidden = !n; b.textContent = n;
}
$("#pilotSwitch").onclick = async () => {
  if (!S.state.setup_done) return wizard();
  const on = !S.state.runner.enabled;
  S.state.runner = await api("/api/autopilot", { on });
  renderPilot();
  toast(on ? (S.state.test_mode ? "Autopilot on — test mode, nothing real is sent" : "Autopilot on — it will run every " + S.state.runner.interval_min + " min") : "Autopilot paused");
};
$("#runNow").onclick = async () => {
  if (!S.state.setup_done) return wizard();
  const r = await api("/api/run", {});
  toast(r.started ? "Run started — watch it in Activity" : "A run is already in progress");
  refresh();
};

/* ───────── router ───────── */
$$("#nav a").forEach((a) => (a.onclick = () => go(a.dataset.view)));
function go(view) {
  S.view = view;
  $$("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.view === view));
  render(true);
}
function render(force = false) {
  const m = $("#main");
  const views = { overview: vOverview, leads: vLeads, inbox: vInbox, sites: vSites, activity: vActivity, settings: vSettings };
  if (!force && (S.view === "settings" || S.view === "activity")) return;
  const html = views[S.view]();
  const put = (h) => { m.innerHTML = force ? h : h.replace('class="view"', 'class="view still"'); after(); };
  if (html instanceof Promise) { html.then(put); return; }
  put(html);
  function after() { hydrateIcons(m); try { bind[S.view]?.(); } catch (e) { console.error(e); } if (force) m.scrollTop = 0; }
}

/* ───────── overview ───────── */
function vOverview() {
  const st = S.state; if (!st) return skeleton();
  const k = st.kpis, r = st.runner;
  const max = Math.max(1, ...st.funnel.map((f) => f.n));
  const smax = Math.max(4, ...st.series.map((s) => s.sent));
  const W = 560, H = 170, bw = W / st.series.length;
  const bars = st.series.map((s, i) => {
    const h = Math.max(2, (s.sent / smax) * (H - 26));
    const d = new Date(s.day + "T12:00");
    return `<rect class="b ${i === st.series.length - 1 ? "today" : ""}" x="${i * bw + 5}" y="${H - 18 - h}" width="${bw - 10}" height="${h}" rx="4"><title>${s.sent} sent · ${s.day}</title></rect>` +
      (i % 2 === 1 || i === st.series.length - 1 ? `<text x="${i * bw + bw / 2}" y="${H - 2}" text-anchor="middle">${d.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</text>` : "");
  }).join("");
  const stepIdx = r.steps.findIndex((s) => s.id === r.step);
  return `<section class="view">
    <div class="head"><div><h1>${greeting()}</h1><p>${r.enabled ? "Autopilot is finding clients for you" : "Autopilot is paused"} · ${esc(st.markets.join(" · ") || "no market enabled")}</p></div>
      <div class="actions"><button class="btn" data-go="leads">${icon("users")}All leads</button>
      <button class="btn ${r.enabled ? "" : "btn-lime"}" id="ovToggle">${icon(r.enabled ? "clock" : "play")}${r.enabled ? "Pause autopilot" : "Start autopilot"}</button></div></div>
    ${st.test_mode ? `<div class="banner">${icon("flask")}<div><b>Test mode is on.</b> Businesses, emails and replies are simulated — nothing is sent and nothing costs money.</div><button class="btn btn-sm" data-go="settings" data-tab="connections">Go live</button></div>` : ""}
    <div class="kpis">
      <div class="card kpi hero"><span>${icon("dollar")}Monthly recurring revenue</span><b class="num">${money(k.mrr)}</b><small>${k.clients} paying client${k.clients === 1 ? "" : "s"}</small>
        <svg class="deco" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">${I.trophy}</svg></div>
      <div class="card kpi"><span>${icon("globe")}Demo sites live</span><b class="num">${fmt(k.sites)}</b><small>${fmt(k.prospects)} businesses found</small></div>
      <div class="card kpi"><span>${icon("send")}Emailed</span><b class="num">${fmt(k.contacted)}</b><small>${fmt(k.sent_today)} sent today</small></div>
      <div class="card kpi"><span>${icon("reply")}Reply rate</span><b class="num">${k.reply_rate == null ? "—" : k.reply_rate + "%"}</b><small>of emailed businesses</small></div>
      <div class="card kpi" style="cursor:pointer" data-go="inbox"><span>${icon("inbox")}Needs you</span><b class="num">${fmt(k.needs_you)}</b><small>${k.needs_you ? "Interested leads waiting" : "Nothing waiting"}</small></div>
    </div>
    <div class="card" style="margin-bottom:14px"><div class="card-h"><h3>${r.running ? "Working now" : "Pipeline"}</h3><small>${r.running ? esc((r.steps[stepIdx] || {}).label || "") + "…" : r.enabled ? "Next run " + until(r.next_run) : r.last_run ? "Last run " + ago(r.last_run) : "Not run yet"}</small></div>
      <div class="card-b"><div class="steps">${r.steps.map((s, i) => `<div class="step ${r.running ? (i < stepIdx ? "done" : i === stepIdx ? "now" : "") : r.last_run ? "done" : ""}"><div class="s"></div>${esc(s.label)}</div>`).join("")}</div></div></div>
    <div class="row">
      <div class="card"><div class="card-h"><h3>Conversion funnel</h3><small>all time</small></div><div class="card-b"><div class="funnel">
        ${st.funnel.map((f, i) => `<div class="fn"><label>${esc(f.label)}</label><div class="bar"><div style="width:${(f.n / max) * 100}%">${f.n ? fmt(f.n) : ""}</div></div><span class="pct">${i && st.funnel[i - 1].n ? Math.round((f.n / st.funnel[i - 1].n) * 100) + "%" : ""}</span></div>`).join("")}
      </div></div></div>
      <div class="card"><div class="card-h"><h3>Emails sent</h3><small>last 14 days</small></div><div class="card-b"><svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${bars}</svg></div></div>
    </div>
    <div class="card"><div class="card-h"><h3>Latest activity</h3><button class="btn btn-ghost btn-sm" data-go="activity">Open log ${icon("arrow")}</button></div>
      <div class="card-b">${st.recent.length ? `<div class="feed">${st.recent.map((e) => { const [l, ic] = evLabel(e.kind); return `<a data-lead="${e.id}"><span class="ic">${icon(ic)}</span><span class="t"><b>${esc(e.name || "—")}</b><small>${esc(l)}</small></span><time>${ago(e.at)}</time></a>`; }).join("")}</div>` :
        emptyBlock("spark", "Nothing yet", "Switch on the autopilot, or press “Run once now”, to start.")}</div></div>
  </section>`;
}
function greeting() { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; }
function skeleton() { return `<section class="view"><div class="skeleton" style="height:34px;width:260px;margin-bottom:24px"></div><div class="kpis">${'<div class="skeleton" style="height:110px"></div>'.repeat(5)}</div><div class="skeleton" style="height:280px"></div></section>`; }
function emptyBlock(ic, h, p, cta = "") { return `<div class="empty"><div class="ill">${icon(ic)}</div><h4>${esc(h)}</h4><p>${esc(p)}</p>${cta}</div>`; }

/* ───────── leads ───────── */
async function loadLeads() { S.leads = await api("/api/leads"); }
function filtered() {
  const f = FILTERS.find((x) => x[0] === S.filter)[2];
  const q = S.q.trim().toLowerCase();
  return S.leads.filter((l) => (!f || f.includes(l.status)) && (!q || `${l.name} ${l.category} ${l.email} ${l.address}`.toLowerCase().includes(q)));
}
async function vLeads() {
  await loadLeads();
  const rows = filtered();
  const counts = Object.fromEntries(FILTERS.map(([id, , f]) => [id, f ? S.leads.filter((l) => f.includes(l.status)).length : S.leads.length]));
  return `<section class="view">
    <div class="head"><div><h1>Leads</h1><p>Every business the autopilot has found, and where each one stands</p></div></div>
    <div class="toolbar"><div class="chips">${FILTERS.map(([id, l]) => `<button class="chip ${S.filter === id ? "on" : ""}" data-f="${id}">${l}<em>${counts[id]}</em></button>`).join("")}</div>
      <label class="search">${icon("search")}<input class="input" id="q" placeholder="Search name, email, address" value="${esc(S.q)}"></label></div>
    <div class="card" style="overflow:hidden" id="leadsTable">${leadsTable(rows)}</div>
  </section>`;
}
function leadsTable(rows) {
  return rows.length ? `<table class="t"><thead><tr><th>Business</th><th>Status</th><th>Rating</th><th>Contact</th><th>Market</th><th>Updated</th></tr></thead><tbody>
      ${rows.map((l) => `<tr data-lead="${l.id}"><td><div class="who">${avatar(l.name)}<div><b>${esc(l.name)}</b><small>${esc(l.category || "")}</small></div></div></td>
        <td>${pill(l.status)}${l.call_requested ? ` <span class="pill violet" title="Asked for a call">☎</span>` : ""}</td>
        <td>${stars(l.rating)} <span class="muted">(${fmt(l.reviews)})</span></td><td class="muted">${esc(l.email || l.phone || "—")}</td>
        <td class="muted">${esc(l.market)}</td><td class="muted">${ago(l.updated_at)}</td></tr>`).join("")}</tbody></table>` :
      emptyBlock("users", S.leads.length ? "No matches" : "No leads yet", S.leads.length ? "Try another filter or search." : "Start the autopilot and businesses will appear here.");
}

/* ───────── needs you ───────── */
async function vInbox() {
  await loadLeads();
  const hot = S.leads.filter((l) => ["needs_human", "interested", "question"].includes(l.status));
  const details = await Promise.all(hot.map((l) => api(`/api/leads/${l.id}`)));
  return `<section class="view">
    <div class="head"><div><h1>Needs you</h1><p>Interested businesses. The autopilot already replied with your plans — close the deal here.</p></div></div>
    ${details.length ? `<div class="ny">${details.map((d) => {
      const last = d.events.find((e) => e.kind === "reply_in");
      return `<div class="card nyc">${avatar(d.name)}<div><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><b style="font-size:15px">${esc(d.name)}</b>${pill(d.status)}${d.call_requested ? `<span class="pill violet">☎ wants a call · ${esc(d.call_number || "")}</span>` : ""}</div>
        <small class="muted">${esc(d.category || "")} · ${esc(d.email || "")} · ${esc(d.phone || "")}</small>
        ${last ? `<div class="q">${esc(last.detail)}</div>` : ""}</div>
        <div class="acts"><button class="btn btn-dark btn-sm" data-won="${d.id}">${icon("trophy")}Client won</button>
        <a class="btn btn-sm" data-ext="mailto:${esc(d.email)}?subject=${encodeURIComponent("Re: your website — " + d.name)}">${icon("reply")}Reply</a>
        <button class="btn btn-sm" data-handled="${d.id}">${icon("check")}Handled</button>
        <button class="btn btn-ghost btn-sm" data-lead="${d.id}">Details</button></div></div>`;
    }).join("")}</div>` : `<div class="card">${emptyBlock("inbox", "All clear", "When a business replies with interest, it shows up here.")}</div>`}
  </section>`;
}

/* ───────── sites ───────── */
async function vSites() {
  await loadLeads();
  const sites = S.leads.filter((l) => l.site_slug);
  return `<section class="view">
    <div class="head"><div><h1>Websites</h1><p>${sites.length} demo site${sites.length === 1 ? "" : "s"} designed by the autopilot</p></div></div>
    ${sites.length ? `<div class="gallery">${sites.map((l) => `<div class="card tile" data-lead="${l.id}"><div class="shot"><iframe loading="lazy" tabindex="-1" src="/sites/${encodeURIComponent(l.site_slug)}/"></iframe></div>
      <div class="cap"><div style="min-width:0"><b>${esc(l.name)}</b><br><small class="muted">${esc(l.category || "")}</small></div>${pill(l.status)}</div></div>`).join("")}</div>` :
      `<div class="card">${emptyBlock("globe", "No websites yet", "Each business that qualifies gets its own site here.")}</div>`}
  </section>`;
}

/* ───────── activity ───────── */
function lineClass(m) { return /^[✓🎉]/.test(m) ? "ok" : /^[-×]/.test(m) ? "skip" : /^[✉↻]/.test(m) ? "mail" : /^[←☎]/.test(m) ? "inb" : ""; }
function lineHTML(l) { return `<div class="ln ${l.level}"><time>${esc(l.t)}</time><span class="${lineClass(l.msg)}">${esc(l.msg)}</span></div>`; }
function vActivity() {
  return `<section class="view">
    <div class="head"><div><h1>Activity</h1><p>A live log of everything the autopilot does</p></div>
      <div class="actions"><button class="btn" id="runNow2">${icon("play")}Run once now</button></div></div>
    <div class="console" id="console">${S.log.length ? S.log.map(lineHTML).join("") : `<div class="ln"><time></time><span class="skip">Waiting for the first run…</span></div>`}</div>
  </section>`;
}

/* ───────── drawer (lead detail) ───────── */
async function openLead(id, tab = "overview") {
  const d = await api(`/api/leads/${id}`);
  const dr = $("#drawer");
  const facts = d.facts || {};
  const tabs = { overview: "Overview", site: "Website", timeline: `Timeline (${d.events.length})` };
  const body = {
    overview: `<dl class="kv">
        <dt>Category</dt><dd>${esc(d.category || "—")}</dd><dt>Address</dt><dd>${esc(d.address || "—")}</dd>
        <dt>Phone</dt><dd>${esc(d.phone || "—")}</dd><dt>Email</dt><dd>${esc(d.email || "—")}</dd>
        <dt>Email found on</dt><dd>${d.email_source ? `<a style="color:var(--blue);cursor:pointer" data-ext="${esc(d.email_source)}">${esc(d.email_source)}</a>` : "—"}</dd>
        <dt>Google rating</dt><dd>${stars(d.rating)} · ${fmt(d.reviews)} reviews ${d.maps_url ? `· <a style="color:var(--blue);cursor:pointer" data-ext="${esc(d.maps_url)}">Maps</a>` : ""}</dd>
        <dt>Market</dt><dd>${esc(d.market)} · ${esc(d.currency || "")}</dd>
        ${facts.services?.length ? `<dt>Services</dt><dd>${esc(facts.services.join(", "))}</dd>` : ""}
        ${d.plan ? `<dt>Plan</dt><dd><b>${esc(d.plan)}</b> · ${fmt(d.mrr)} ${esc(d.currency)}/month</dd>` : ""}
        ${d.call_requested ? `<dt>Call</dt><dd>Asked for a call · ${esc(d.call_number || "")}${d.called_at ? " · called " + ago(d.called_at) : ""}</dd>` : ""}
      </dl>`,
    site: d.local_site ? `<div class="preview"><div class="bar"><span></span><span></span><span></span><em>${esc(d.site_url || d.local_site)}</em></div><div class="frame"><iframe src="${esc(d.local_site)}"></iframe></div></div>
        <div style="display:flex;gap:8px;margin-top:12px">${d.site_url && !d.site_url.includes("127.0.0.1") ? `<a class="btn btn-sm" data-ext="${esc(d.site_url)}">${icon("ext")}Open live site</a>` : ""}<a class="btn btn-sm" data-ext="${esc(location.origin + d.local_site)}">${icon("ext")}Open full size</a></div>` :
      emptyBlock("globe", "No website yet", d.status === "no_email" ? "Skipped: no public email, so no site was built." : "It will be designed on the next run."),
    timeline: `<div class="timeline">${d.events.map((e) => {
      const [l] = evLabel(e.kind); const dir = e.kind === "reply_in" ? "in" : ["emailed", "followed_up", "reply_out"].includes(e.kind) ? "out" : "";
      const show = e.detail && (dir || ["skipped", "call_done", "needs_human"].includes(e.kind) || e.kind.includes("error"));
      return `<div class="ev k-${esc(e.kind)}"><h5>${esc(l)}<time>${new Date(e.at).toLocaleString()}</time></h5>${show ? `<div class="msg ${dir}">${esc(e.detail)}</div>` : e.detail && !dir ? `<small class="muted">${esc(e.detail.slice(0, 160))}</small>` : ""}</div>`;
    }).join("")}</div>`,
  };
  const closed = ["won", "lost", "unsubscribed", "bounced", "not_interested"].includes(d.status);
  dr.innerHTML = `<div class="dh"><div class="dh-top">${avatar(d.name, true)}<div style="min-width:0"><h2>${esc(d.name)}</h2><div class="meta">${pill(d.status)} &nbsp;${esc(d.category || "")}</div></div>
      <button class="btn btn-ghost btn-sm close" id="dClose" aria-label="Close">${icon("x")}</button></div>
    <div class="acts">
      ${d.status !== "won" ? `<select class="select" id="dPlan" style="width:auto;height:38px">${d.plans.map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${fmt(p.monthly)} ${esc(d.currency || "")}/mo</option>`).join("")}</select>
        <button class="btn btn-dark" id="dWon">${icon("trophy")}Mark as client</button>` : `<span class="pill green" style="height:38px;padding:0 14px">Client · ${esc(d.plan)}</span>`}
      ${d.email ? `<a class="btn" data-ext="mailto:${esc(d.email)}?subject=${encodeURIComponent("Your website — " + d.name)}">${icon("mail")}Email</a>` : ""}
      ${!closed ? `<button class="btn btn-ghost btn-danger" id="dLost">Lost</button>` : ""}
    </div>
    <div class="tabs">${Object.entries(tabs).map(([k, v]) => `<button data-tab="${k}" class="${k === tab ? "on" : ""}">${v}</button>`).join("")}</div></div>
    <div class="db">${body[tab]}</div>`;
  hydrateIcons(dr);
  setTimeout(() => fitFrames(dr), 30);
  dr.classList.add("on"); $("#scrim").classList.add("on"); dr.setAttribute("aria-hidden", "false");
  $("#dClose").onclick = closeDrawer;
  $$(".tabs button", dr).forEach((b) => (b.onclick = () => openLead(id, b.dataset.tab)));
  $("#dWon") && ($("#dWon").onclick = async () => { await api(`/api/leads/${id}/won`, { plan: $("#dPlan").value }); toast(`${d.name} is now a client 🎉`); openLead(id, tab); refresh(true); });
  $("#dLost") && ($("#dLost").onclick = async () => { await api(`/api/leads/${id}/lost`, {}); toast("Marked as lost"); openLead(id, tab); refresh(true); });
}
function closeDrawer() { $("#drawer").classList.remove("on"); $("#scrim").classList.remove("on"); $("#drawer").setAttribute("aria-hidden", "true"); }
$("#scrim").onclick = closeDrawer;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

/* ───────── settings ───────── */
const SET_TABS = [["business", "Your studio", "building"], ["connections", "Connections", "plug"], ["markets", "Markets", "map"],
  ["plans", "Plans & prices", "tag"], ["limits", "Limits & schedule", "sliders"], ["calls", "AI calls", "phone"], ["app", "App", "app"]];
const CONNS = [
  ["ANTHROPIC_API_KEY", "Claude", "#C96442", "Researches businesses, writes every site and email", "https://console.anthropic.com/settings/keys", true],
  ["GOOGLE_PLACES_API_KEY", "Google Places", "#1A73E8", "Finds businesses on Google Maps (enable “Places API (New)”)", "https://console.cloud.google.com/apis/library/places.googleapis.com", true],
  ["RESEND_API_KEY", "Resend", "#111", "Sends your emails — verify your studio domain first", "https://resend.com/api-keys", true],
  ["NETLIFY_TOKEN", "Netlify", "#05BDBA", "Hosts each demo website on its own link (free)", "https://app.netlify.com/user/applications#personal-access-tokens", true],
  ["IMAP_PASSWORD", "Your mailbox", "#5F6368", "Reads replies. For Gmail use an App Password", "https://myaccount.google.com/apppasswords", false],
  ["VAPI_API_KEY", "Vapi (optional)", "#6B48C8", "AI voice call-backs when a lead asks for a call", "https://dashboard.vapi.ai", false],
];
async function vSettings() {
  if (!S.settings) { const s = await api("/api/settings"); S.settings = s; S.cfg = clone(s.config); S.sec = {}; }
  const t = S.setTab;
  return `<section class="view">
    <div class="head"><div><h1>Settings</h1><p>Saved on this computer · <a style="color:var(--blue);cursor:pointer" id="openData">open data folder</a></p></div>
      <div class="actions"><button class="btn btn-dark" id="saveSet">${icon("check")}Save changes</button></div></div>
    <div class="set"><nav class="subnav">${SET_TABS.map(([id, l, ic]) => `<a data-st="${id}" class="${t === id ? "on" : ""}">${icon(ic)}${l}</a>`).join("")}</nav>
      <div class="sec">${SETS[t]()}</div></div></section>`;
}
const fld = (path, label, hint = "", type = "text", attrs = "") => {
  const v = getPath(S.cfg, path);
  return `<label class="f"><span>${label}</span><input class="input" type="${type}" data-k="${path}" data-t="${type}" value="${esc(Array.isArray(v) ? v.join(", ") : v ?? "")}" ${attrs}>${hint ? `<small>${hint}</small>` : ""}</label>`;
};
const tog = (path, title, sub, light = true) => `<div class="toggle-row"><div><b>${title}</b><small>${sub}</small></div><button class="switch ${light ? "light" : ""}" role="switch" data-sw="${path}" aria-checked="${!!getPath(S.cfg, path)}"><span></span></button></div>`;
const SETS = {
  business: () => `<div class="card"><h3>Your studio</h3><p class="lead">How you appear in emails and on every demo site.</p><div class="grid2">
      ${fld("brand.name", "Studio name", "Shown on demo sites and in emails")}${fld("brand.sender_name", "Your first name", "Emails are signed with this")}
      ${fld("brand.sender_email", "Sending email", "Must be on a domain verified in Resend", "email")}${fld("brand.reply_to", "Reply-to email", "The mailbox replies go to", "email")}
      ${fld("brand.website", "Studio website", "", "url")}${fld("brand.booking_url", "Booking link (optional)", "Calendly or Cal.com link", "url")}
      ${fld("brand.phone", "Phone (optional)")}${fld("brand.whatsapp", "WhatsApp (optional)", "e.g. +22370000000")}</div>
      <div style="margin-top:16px">${fld("brand.postal_address", "Postal address", "Required by anti-spam law (CASL / CAN-SPAM). Included in every email.")}</div></div>`,
  connections: () => `<div class="card"><h3>Connections</h3><p class="lead">Keys are stored only on this computer. Each one has a “Get key” link and a test button.</p>
      ${CONNS.map(([k, name, color, desc, link, req]) => `<div class="conn"><span class="lg" style="background:${color}">${esc(name[0])}</span>
        <div><b><span class="state ${S.settings.secrets[k] ? "ok" : ""}"></span>${esc(name)}${req ? "" : ""}</b><small>${esc(desc)} · <a data-ext="${link}">Get key</a></small></div>
        <div class="ci" style="display:grid;gap:6px">${k === "IMAP_PASSWORD" ? `<input class="input" data-sec="IMAP_USER" placeholder="you@studio.com" value="${esc(S.sec.IMAP_USER ?? S.settings.imap_user)}">` : ""}
          <input class="input" type="password" data-sec="${k}" placeholder="${S.settings.secrets[k] ? "•••••••• saved" : "Paste key"}" value="${esc(S.sec[k] || "")}">
          ${k === "VAPI_API_KEY" ? `<input class="input" data-sec="VAPI_PHONE_NUMBER_ID" placeholder="${S.settings.secrets.VAPI_PHONE_NUMBER_ID ? "Phone number ID saved" : "Vapi phone number ID"}">` : ""}</div>
        <button class="btn btn-sm" data-test="${k}">Test</button></div>`).join("")}
      <div class="grid2" style="margin-top:12px">${fld("inbox.host", "Mail server (IMAP)", "imap.gmail.com for Gmail / Workspace")}${fld("inbox.port", "Port", "", "number")}</div></div>
      <div class="card">${tog("test_mode", "Test mode", "Simulate everything — no real searches, emails or websites. Switch off to go live.")}</div>`,
  markets: () => `<div class="card"><h3>Markets</h3><p class="lead">Where the autopilot looks for businesses. Each run rotates through enabled markets.</p>
      ${S.cfg.markets.map((m, i) => `<div class="mk"><span class="flag">${esc((m.country || "··").toUpperCase())}</span><div>
        <div class="grid3">${fld(`markets.${i}.city`, "City")}<label class="f"><span>Language</span><select class="select" data-k="markets.${i}.language"><option value="en" ${m.language === "en" ? "selected" : ""}>English</option><option value="fr" ${m.language === "fr" ? "selected" : ""}>Français</option></select></label>
        <label class="f"><span>Currency</span><select class="select" data-k="markets.${i}.currency">${["CAD", "USD", "XOF"].map((c) => `<option ${m.currency === c ? "selected" : ""}>${c}</option>`).join("")}</select></label></div>
        <div class="tags" data-tags="markets.${i}.queries">${(m.queries || []).map((q, j) => `<span class="tag">${esc(q)}<button data-rmtag="${j}" aria-label="Remove">×</button></span>`).join("")}<input class="tag-in" placeholder="+ add business type"></div></div>
        <div style="display:flex;gap:8px;align-items:center"><button class="switch light" role="switch" data-sw="markets.${i}.enabled" aria-checked="${!!m.enabled}"><span></span></button><button class="btn btn-ghost btn-sm" data-rmmk="${i}" aria-label="Remove market">${icon("trash")}</button></div></div>`).join("")}
      <button class="btn" id="addMk" style="margin-top:8px">${icon("plus")}Add a market</button></div>`,
  plans: () => `<div class="card"><h3>Plans & prices</h3><p class="lead">Sent automatically to interested businesses. Payment links can be Stripe, Wave, Orange Money…</p><div style="display:grid;gap:14px">
      ${S.cfg.plans.map((p, i) => `<div class="plan-c"><div class="grid2">${fld(`plans.${i}.name.en`, "Name (English)")}${fld(`plans.${i}.name.fr`, "Nom (français)")}</div>
        <div class="grid2"><label class="f"><span>Features (one per line)</span><textarea class="input" rows="4" data-k="plans.${i}.features.en" data-t="lines">${esc((p.features.en || []).join("\n"))}</textarea></label>
        <label class="f"><span>Inclus (une par ligne)</span><textarea class="input" rows="4" data-k="plans.${i}.features.fr" data-t="lines">${esc((p.features.fr || []).join("\n"))}</textarea></label></div>
        <div class="price-grid"><b></b><small class="muted">Setup fee</small><small class="muted">Monthly</small>
          ${["CAD", "USD", "XOF"].map((c) => `<b>${c}</b><input class="input" type="number" data-t="number" data-k="plans.${i}.price.${c}.setup" value="${getPath(p, `price.${c}.setup`) ?? 0}"><input class="input" type="number" data-t="number" data-k="plans.${i}.price.${c}.monthly" value="${getPath(p, `price.${c}.monthly`) ?? 0}">`).join("")}</div>
        <div class="grid3">${["CAD", "USD", "XOF"].map((c) => fld(`plans.${i}.payment_link.${c}`, `Payment link ${c}`, "", "url")).join("")}</div></div>`).join("")}</div></div>`,
  limits: () => `<div class="card"><h3>Schedule</h3><p class="lead">How often the autopilot runs while the app is open (or in the tray).</p><div class="grid3">
      ${fld("interval_min", "Run every (minutes)", "Minimum 15", "number", 'min="15"')}${fld("limits.send_window_local.0", "Send from (hour)", "Local time of each market", "number")}${fld("limits.send_window_local.1", "Send until (hour)", "Mon–Fri only", "number")}</div></div>
    <div class="card"><h3>Email volume</h3><p class="lead">Start slow to protect your sending reputation. The cap grows each day until the maximum.</p><div class="grid3">
      ${fld("limits.warmup_start", "Day-1 cap", "", "number")}${fld("limits.warmup_step", "Increase per day", "", "number")}${fld("limits.max_emails_per_day", "Maximum per day", "", "number")}
      ${fld("limits.followup_after_days", "Follow up after (days)", "", "number")}${fld("limits.max_followups", "Max follow-ups", "", "number")}${fld("limits.takedown_demo_after_days", "Remove unclaimed demos after (days)", "", "number")}</div></div>
    <div class="card"><h3>Who qualifies</h3><p class="lead">Only businesses that customers already like get a website.</p><div class="grid3">
      ${fld("qualify.min_rating", "Minimum Google rating", "", "number", 'step="0.1"')}${fld("qualify.min_reviews", "Minimum reviews", "", "number")}${fld("limits.max_sites_per_run", "Sites per run", "", "number")}</div>
      ${tog("qualify.treat_social_as_no_website", "Facebook-only counts as “no website”", "Businesses that only have a social page still get a site")}</div>`,
  calls: () => `<div class="card"><h3>AI voice calls</h3><p class="lead">The AI only calls businesses that replied and asked for a call or gave a number. Cold AI calls are illegal in the US and restricted in Canada.</p>
      ${tog("voice.enabled", "Call back interested leads", "Needs Vapi key + phone number ID in Connections")}
      <div class="grid2" style="margin-top:12px">${fld("voice.call_window_local.0", "Call from (hour)", "", "number")}${fld("voice.call_window_local.1", "Call until (hour)", "", "number")}</div></div>`,
  app: () => `<div class="card"><h3>App</h3><p class="lead">How Autopilot behaves on this computer.</p>
      ${tog("autopilot_on_launch", "Start the autopilot when the app opens", "Otherwise it waits for you to switch it on")}
      ${tog("keep_running_in_tray", "Keep running in the tray when closed", "Closing the window keeps it working; quit from the tray icon")}
      <div class="toggle-row"><div><b>Launch with Windows</b><small>${S.state?.platform === "Windows" ? "Opens minimised to the tray when you sign in" : "Available on Windows"}</small></div><button class="switch light" role="switch" id="swStartup" aria-checked="${!!S.state?.startup}" ${S.state?.platform === "Windows" ? "" : "disabled"}><span></span></button></div></div>
    <div class="card"><h3>Data</h3><p class="lead">Your leads, sites and settings live in <code>${esc(S.settings.data_dir)}</code></p>
      <div style="display:flex;gap:10px"><button class="btn" id="openData2">${icon("folder")}Open data folder</button>${S.cfg.test_mode ? `<button class="btn btn-danger" id="resetTest">${icon("trash")}Clear test data</button>` : ""}<button class="btn" id="rerunWiz">${icon("wand")}Run setup again</button></div></div>`,
};

/* scale live site previews to whatever width their box has */
function fitFrames(root = document) {
  $$(".shot iframe, .preview .frame iframe", root).forEach((f) => { const w = f.parentElement.clientWidth; f.style.transform = `scale(${w / 1280})`; });
}
window.addEventListener("resize", () => fitFrames());

/* ───────── bindings per view ───────── */
const bind = {
  overview() {
    $$("[data-go]").forEach((b) => (b.onclick = () => { if (b.dataset.tab) S.setTab = b.dataset.tab; go(b.dataset.go); }));
    $$("[data-lead]").forEach((b) => (b.onclick = () => openLead(+b.dataset.lead)));
    const t = $("#ovToggle"); if (t) t.onclick = () => $("#pilotSwitch").click();
  },
  leads() {
    $$("[data-f]").forEach((b) => (b.onclick = () => { S.filter = b.dataset.f; render(true); }));
    $$("[data-lead]").forEach((b) => (b.onclick = () => openLead(+b.dataset.lead)));
    $("#q").oninput = (e) => {
      S.q = e.target.value;
      const t = $("#leadsTable"); t.innerHTML = leadsTable(filtered()); hydrateIcons(t);
      $$("[data-lead]", t).forEach((b) => (b.onclick = () => openLead(+b.dataset.lead)));
    };
  },
  inbox() {
    $$("[data-lead]").forEach((b) => (b.onclick = () => openLead(+b.dataset.lead)));
    $$("[data-won]").forEach((b) => (b.onclick = () => openLead(+b.dataset.won)));
    $$("[data-handled]").forEach((b) => (b.onclick = async () => { await api(`/api/leads/${b.dataset.handled}/handled`, {}); toast("Marked as handled"); refresh(true); render(true); }));
  },
  sites() { $$("[data-lead]").forEach((b) => (b.onclick = () => openLead(+b.dataset.lead, "site"))); fitFrames(); },
  activity() {
    const c = $("#console"); c.scrollTop = c.scrollHeight;
    $("#runNow2").onclick = () => $("#runNow").click();
  },
  settings() {
    const m = $("#main");
    $$("[data-st]").forEach((a) => (a.onclick = () => { S.setTab = a.dataset.st; render(true); }));
    $$("[data-k]", m).forEach((el) => {
      el.addEventListener("input", () => {
        const t = el.dataset.t; let v = el.value;
        if (t === "number") v = v === "" ? 0 : Number(v);
        if (t === "lines") v = v.split("\n").map((s) => s.trim()).filter(Boolean);
        setPath(S.cfg, el.dataset.k, v); S.dirty = true;
      });
    });
    $$("[data-sw]", m).forEach((b) => (b.onclick = () => { const v = b.getAttribute("aria-checked") !== "true"; b.setAttribute("aria-checked", v); setPath(S.cfg, b.dataset.sw, v); S.dirty = true; }));
    $$("[data-sec]", m).forEach((el) => (el.oninput = () => { S.sec[el.dataset.sec] = el.value; S.dirty = true; }));
    $$("[data-test]", m).forEach((b) => (b.onclick = async () => {
      b.disabled = true; b.textContent = "Testing…";
      const k = b.dataset.test;
      const r = await api(`/api/test/${k}`, { value: S.sec[k] || "", user: S.sec.IMAP_USER || "" }).catch(() => ({ ok: false, msg: "Could not reach the service" }));
      b.disabled = false; b.textContent = r.ok ? "✓ Works" : "Test";
      toast(r.ok ? `${k.split("_")[0][0] + k.split("_")[0].slice(1).toLowerCase()}: ${r.msg}` : r.msg, !r.ok);
    }));
    $$("[data-tags]", m).forEach((box) => {
      const p = box.dataset.tags;
      $$("[data-rmtag]", box).forEach((b) => (b.onclick = () => { getPath(S.cfg, p).splice(+b.dataset.rmtag, 1); S.dirty = true; render(true); }));
      const inp = $(".tag-in", box);
      inp.onkeydown = (e) => { if (e.key === "Enter" && inp.value.trim()) { getPath(S.cfg, p).push(inp.value.trim()); S.dirty = true; render(true); setTimeout(() => $(`[data-tags="${p}"] .tag-in`)?.focus(), 20); } };
    });
    $$("[data-rmmk]", m).forEach((b) => (b.onclick = () => { S.cfg.markets.splice(+b.dataset.rmmk, 1); S.dirty = true; render(true); }));
    $("#addMk") && ($("#addMk").onclick = () => { S.cfg.markets.push(newMarket("", "en")); S.dirty = true; render(true); });
    $("#saveSet").onclick = saveSettings;
    ["#openData", "#openData2"].forEach((s) => $(s) && ($(s).onclick = () => api("/api/open", { what: "data" })));
    $("#resetTest") && ($("#resetTest").onclick = async () => { await api("/api/reset-test", {}); toast("Test data cleared"); refresh(true); });
    $("#rerunWiz") && ($("#rerunWiz").onclick = () => wizard());
    $("#swStartup") && ($("#swStartup").onclick = async () => { const r = await api("/api/startup", { on: !S.state.startup }); S.state.startup = r.on; render(true); toast(r.on ? "Autopilot will start with Windows" : "Won't start with Windows"); });
  },
};
async function saveSettings() {
  const secrets = Object.fromEntries(Object.entries(S.sec || {}).filter(([, v]) => v));
  await api("/api/settings", { config: S.cfg, secrets });
  S.dirty = false; S.settings = null; S.sec = {};
  toast("Settings saved");
  await refresh(true); render(true);
}
function newMarket(city, lang) {
  const id = (city || "market").toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + "-" + Math.random().toString(36).slice(2, 5);
  return { id, enabled: true, city, country: "", language: lang, currency: lang === "fr" ? "XOF" : "CAD",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, law: "generic",
    queries: lang === "fr" ? ["salon de coiffure", "restaurant", "boutique", "garage automobile", "pâtisserie"] : ["barber shop", "hair salon", "bakery", "auto repair", "cleaning service", "landscaping"] };
}

/* ───────── onboarding wizard ───────── */
const PRESET = [
  { key: "langley-bc", label: "Langley, BC", sub: "English · CAD", cc: "CA" },
  { key: "bamako", label: "Bamako", sub: "Français · XOF", cc: "ML" },
  { key: "abidjan", label: "Abidjan", sub: "Français · XOF", cc: "CI" },
];
async function wizard() {
  const s = await api("/api/settings");
  const W = { step: 0, mode: s.config.test_mode === false ? "live" : "test", cfg: clone(s.config), sec: {}, picked: new Set(s.config.markets.filter((m) => m.enabled).map((m) => m.id)), custom: "", customLang: "en" };
  const steps = ["Welcome", "Your studio", "Where to look", "Connections", "Ready"];
  const modal = $("#modal"); modal.hidden = false;
  const draw = () => {
    const b = W.cfg.brand;
    const bodies = [
      () => `<h3>Win clients while you sleep</h3><p class="lead">Autopilot finds local businesses without a website, designs one for them, and emails the owner — then follows up and handles replies.</p>
        <div class="flow"><div>${icon("pin")}<b>Find</b><small>Well-reviewed businesses with no website on Google Maps</small></div><div>${icon("wand")}<b>Design</b><small>A polished one-page site, published on its own link</small></div><div>${icon("send")}<b>Pitch</b><small>A personal email, one follow-up, replies answered with your plans</small></div></div>
        <div class="choice" style="margin-top:18px">
          <div class="opt ${W.mode === "test" ? "on" : ""}" data-mode="test"><span class="rd"></span><div><b>Start in test mode (recommended)</b><small>See everything work with simulated businesses. Free, nothing is sent.</small></div></div>
          <div class="opt ${W.mode === "live" ? "on" : ""}" data-mode="live"><span class="rd"></span><div><b>Set up for real</b><small>Connect Claude, Google, email and hosting. About 15 minutes.</small></div></div></div>`,
      () => `<h3>Your studio</h3><p class="lead">This is how you appear on demo sites and in emails. You can change it later.</p>
        <div class="grid2"><label class="f"><span>Studio name</span><input class="input" data-w="brand.name" value="${esc(b.name)}"></label><label class="f"><span>Your first name</span><input class="input" data-w="brand.sender_name" value="${esc(b.sender_name)}"></label></div>
        <label class="f"><span>Studio email</span><input class="input" type="email" data-w="brand.sender_email" value="${esc(b.sender_email)}"><small>Use a separate domain for outreach, not your main business domain.</small></label>
        <label class="f"><span>Postal address</span><input class="input" data-w="brand.postal_address" value="${esc(b.postal_address)}"><small>Required by anti-spam law. Shown at the bottom of every email.</small></label>`,
      () => `<h3>Where should it look?</h3><p class="lead">Pick one or more cities. You can fine-tune business types later in Settings → Markets.</p>
        <div class="mk-pick">${PRESET.map((p) => `<div class="opt ${W.picked.has(p.key) ? "on" : ""}" data-mk="${p.key}"><span class="flag">${p.cc}</span><div><b>${p.label}</b><small>${p.sub}</small></div></div>`).join("")}</div>
        <div class="grid2" style="grid-template-columns:1fr 160px;margin-top:6px"><label class="f"><span>Or add another city</span><input class="input" id="wCity" placeholder="e.g. Surrey, BC, Canada" value="${esc(W.custom)}"></label>
          <label class="f"><span>Language</span><select class="select" id="wLang"><option value="en">English</option><option value="fr" ${W.customLang === "fr" ? "selected" : ""}>Français</option></select></label></div>`,
      () => W.mode === "test" ? `<h3>Connections</h3><p class="lead">Not needed in test mode. When you're ready to go live, add your keys in Settings → Connections.</p>
          <div class="banner" style="margin:0">${icon("flask")}<div>Test mode simulates Google, Claude, email and hosting, so you can try every screen for free.</div></div>` :
        `<h3>Connect your services</h3><p class="lead">The first two are required. You can add the rest later in Settings.</p>
        ${CONNS.slice(0, 4).map(([k, name, color, desc, link]) => `<label class="f"><span>${esc(name)} <a data-ext="${link}" style="color:var(--blue);font-weight:500;cursor:pointer;margin-left:6px">Get key ↗</a></span><input class="input" type="password" data-wsec="${k}" placeholder="${s.secrets[k] ? "•••••••• saved" : "Paste key"}" value="${esc(W.sec[k] || "")}"><small>${esc(desc)}</small></label>`).join("")}`,
      () => `<h3>You're all set</h3><p class="lead">${W.mode === "test" ? "Test mode is on: you'll see simulated businesses, sites, emails and replies." : "Autopilot is ready to find real clients. It starts slowly (5 emails on day one) to protect your email reputation."}</p>
        <div class="flow"><div>${icon("map")}<b>${W.picked.size + (W.custom ? 1 : 0)} market${W.picked.size + (W.custom ? 1 : 0) === 1 ? "" : "s"}</b><small>${esc([...PRESET.filter((p) => W.picked.has(p.key)).map((p) => p.label), W.custom].filter(Boolean).join(", "))}</small></div>
          <div>${icon("clock")}<b>Every ${W.cfg.interval_min || 60} min</b><small>While the app is open or in the tray</small></div>
          <div>${icon("inbox")}<b>You close deals</b><small>Interested leads land in “Needs you”</small></div></div>`,
    ];
    modal.innerHTML = `<div class="wiz"><div class="wiz-l"><img src="/ui/icon.png" alt=""><h2>Set up Autopilot</h2><p>A few quick steps. Everything can be changed later.</p>
        <div class="wsteps">${steps.map((t, i) => `<div class="${i === W.step ? "on" : i < W.step ? "done" : ""}"><span>${i < W.step ? "✓" : i + 1}</span>${t}</div>`).join("")}</div></div>
      <div class="wiz-r"><div class="wiz-body">${bodies[W.step]()}</div>
        <div class="wiz-foot"><button class="btn btn-ghost" id="wBack" ${W.step ? "" : "style='visibility:hidden'"}>Back</button>
          <button class="btn ${W.step === steps.length - 1 ? "btn-lime" : "btn-dark"}" id="wNext">${W.step === steps.length - 1 ? icon("play") + "Start autopilot" : "Continue " + icon("arrow")}</button></div></div></div>`;
    hydrateIcons(modal);
    $$("[data-mode]", modal).forEach((o) => (o.onclick = () => { W.mode = o.dataset.mode; draw(); }));
    $$("[data-mk]", modal).forEach((o) => (o.onclick = () => { W.picked.has(o.dataset.mk) ? W.picked.delete(o.dataset.mk) : W.picked.add(o.dataset.mk); draw(); }));
    $$("[data-w]", modal).forEach((el) => (el.oninput = () => setPath(W.cfg, el.dataset.w, el.value)));
    $$("[data-wsec]", modal).forEach((el) => (el.oninput = () => { W.sec[el.dataset.wsec] = el.value; }));
    $("#wCity") && ($("#wCity").oninput = (e) => (W.custom = e.target.value));
    $("#wLang") && ($("#wLang").onchange = (e) => (W.customLang = e.target.value));
    $("#wBack").onclick = () => { W.step--; draw(); };
    $("#wNext").onclick = async () => {
      if (W.step === 2 && !W.picked.size && !W.custom.trim()) return toast("Pick at least one city", true);
      if (W.step === 3 && W.mode === "live" && !(W.sec.ANTHROPIC_API_KEY || s.secrets.ANTHROPIC_API_KEY) ) return toast("Add your Claude key to go live (or go back and pick test mode)", true);
      if (W.step < steps.length - 1) { W.step++; return draw(); }
      // finish
      W.cfg.markets.forEach((m) => (m.enabled = W.picked.has(m.id)));
      if (W.custom.trim() && !W.cfg.markets.some((m) => m.city === W.custom.trim())) W.cfg.markets.push(newMarket(W.custom.trim(), W.customLang));
      W.cfg.test_mode = W.mode === "test"; W.cfg.setup_done = true;
      await api("/api/settings", { config: W.cfg, secrets: Object.fromEntries(Object.entries(W.sec).filter(([, v]) => v)) });
      modal.hidden = true; S.settings = null;
      await refresh(true);
      await api("/api/autopilot", { on: true });
      await api("/api/run", {});
      toast(W.mode === "test" ? "Autopilot started in test mode" : "Autopilot started — good luck!");
      go("overview");
    };
  };
  draw();
}

/* ───────── polling ───────── */
async function refresh(force = false) {
  try { S.state = await api("/api/state"); } catch { return; }
  renderPilot();
  const sig = JSON.stringify([S.state.kpis, S.state.status_counts, S.state.recent[0]?.at]);
  const changed = sig !== S.leadsSig; S.leadsSig = sig;
  if (S.view === "overview") render();
  else if (force || (changed && ["leads", "inbox", "sites"].includes(S.view) && !$("#drawer").classList.contains("on") && document.activeElement?.id !== "q")) render();
}
async function pollLog() {
  try {
    const lines = await api(`/api/log?since=${S.logN}`);
    if (lines.length) {
      S.logN = lines.at(-1).n; S.log.push(...lines); if (S.log.length > 1500) S.log.splice(0, S.log.length - 1500);
      const c = $("#console");
      if (c && S.view === "activity") {
        const atBottom = c.scrollHeight - c.scrollTop - c.clientHeight < 60;
        if (c.querySelector(".skip") && c.children.length === 1) c.innerHTML = "";
        c.insertAdjacentHTML("beforeend", lines.map(lineHTML).join(""));
        if (atBottom) c.scrollTop = c.scrollHeight;
      }
    }
  } catch {}
}

(async function boot() {
  hydrateIcons();
  try { render(true); } catch (e) { console.error(e); }
  await refresh(true);
  if (!S.state?.setup_done) wizard();
  setInterval(refresh, 2500);
  setInterval(pollLog, 1200);
  window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
})();
