// Midterms 2026 Tracker: loads the JSON files in data/ and draws the page.
// No framework, no build step: edit, commit, and GitHub Pages serves it.

// How often an open page re-checks for new data. Faster on election night.
const REFRESH_MINUTES = Date.now() > Date.parse("2026-11-03T23:00:00Z") && Date.now() < Date.parse("2026-11-05T12:00:00Z") ? 2 : 5;

const PARTY_NAME = { D: "Democrat", R: "Republican", I: "Independent", L: "Libertarian" };

// ---------- small helpers ----------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function money(n) {
  if (n == null) return "–";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M";
  if (n >= 1e3) return "$" + Math.round(n / 1e3) + "K";
  return "$" + Math.round(n);
}

function shortDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function ago(iso) {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return hrs < 48 ? `${hrs} hr ago` : shortDate(iso);
}

// Fetch a JSON file, adding ?t=<time> so the browser doesn't reuse an old cached copy.
async function load(name) {
  const res = await fetch(`data/${name}.json?t=${Date.now()}`);
  if (!res.ok) throw new Error(`${name}.json: ${res.status}`);
  return res.json();
}

// ---------- rendering ----------
function splitBar(d, r) {
  return `<div class="split"><span class="d" style="width:${d}%"></span><span class="r" style="width:${r}%"></span></div>
          <div class="split-nums"><span class="d">D ${d}%</span><span class="r">R ${r}%</span></div>`;
}

function renderOverview(fc) {
  const control = fc.control.map((c) => `
    <div class="stat">
      <h3>${esc(c.chamber)} control</h3>
      <p class="sub">${esc(c.status)}</p>
      ${c.forecasts.map((f) => `
        <div class="fc">
          <div class="fc-label"><a href="${esc(f.url)}">${esc(f.source)}</a><span class="src">${[f.note, shortDate(f.as_of)].filter(Boolean).map(esc).join(" · ")}</span></div>
          ${splitBar(f.d, f.r)}
        </div>`).join("")}
    </div>`).join("");

  const gb = fc.generic_ballot;
  const generic = `
    <div class="stat">
      <h3>Generic ballot</h3>
      <p class="sub">"Which party would you vote for in your House race?"</p>
      <div class="big" style="color:var(--${gb.margin.startsWith("D") ? "dem" : "rep"})">${esc(gb.margin)}</div>
      <p class="sub"><a href="${esc(gb.url)}">${esc(gb.source)}</a> polling average · ${shortDate(gb.as_of)}</p>
    </div>`;

  document.getElementById("overview").innerHTML = control + generic;
  document.getElementById("forecast-sources").textContent =
    [...new Set(fc.control.flatMap((c) => c.forecasts.map((f) => f.source)).concat(gb.source))].join(", ");
}

function renderCandidate(c, raceId, moneyData, result) {
  const m = moneyData.candidates?.[`${raceId}|${c.name}`];
  const votes = result?.votes?.[c.name];
  const total = result ? Object.values(result.votes || {}).reduce((a, b) => a + b, 0) : 0;
  const right = votes != null
    ? `<div class="votes"><b>${total ? ((votes / total) * 100).toFixed(1) : "0.0"}%</b><br>${votes.toLocaleString()}</div>`
    : m && m.raised != null
      ? `<div class="money" title="Through ${esc(m.through || "?")}; FEC id ${esc(m.fec_id)}${m.fec_name ? " (" + esc(m.fec_name) + ")" : ""}">
           <b>${money(m.raised)}</b> raised<br>${money(m.cash_on_hand)} on hand</div>`
      : `<div class="money"></div>`;
  const winner = result?.called === c.name ? " winner" : "";
  return `
    <div class="cand${winner}">
      <span class="chip ${esc(c.party)}" title="${esc(PARTY_NAME[c.party] || c.party)}">${esc(c.party)}</span>
      <span><span class="name">${esc(c.name)}</span>${c.incumbent ? '<span class="inc">incumbent</span>' : ""}</span>
      ${right}
    </div>`;
}

function renderRace(race, moneyData, fc, results) {
  const result = results.results?.[race.id];
  const odds = fc.races?.odds?.[race.id];
  const leader = odds && race.candidates.find((c) => c.name === odds.leader);
  const color = leader ? `var(--${{ D: "dem", R: "rep", I: "ind", L: "lib" }[leader.party]})` : "var(--muted)";
  const tag = result
    ? result.called ? `<span class="tag called">Called</span>` : `<span class="tag">${result.reporting ?? 0}% in</span>`
    : "";
  return `
    <article class="card">
      <div class="card-head"><h4>${esc(race.title)}</h4>${tag}</div>
      ${race.note ? `<div class="note">${esc(race.note)}</div>` : ""}
      <div class="cands">${race.candidates.map((c) => renderCandidate(c, race.id, moneyData, result)).join("")}</div>
      ${odds && !result ? `
        <div class="odds">${esc(fc.races.source)}: <b>${esc(odds.leader)}</b> ${odds.pct}% to win${odds.note ? ` (${esc(odds.note)})` : ""}
          <div class="bar"><span style="width:${odds.pct}%;background:${color}"></span></div>
        </div>` : ""}
    </article>`;
}

function renderMeasure(m, results) {
  const r = results.results?.[m.id];
  let tally = "";
  if (r?.votes) {
    const y = r.votes.Yes || 0, n = r.votes.No || 0, t = y + n || 1;
    tally = `
      <div class="yn"><span class="y" style="width:${(y / t) * 100}%"></span><span class="n" style="width:${(n / t) * 100}%"></span></div>
      <div class="split-nums"><span style="color:var(--yes)">Yes ${((y / t) * 100).toFixed(1)}%</span><span>No ${((n / t) * 100).toFixed(1)}%</span></div>`;
  }
  const tag = r ? (r.called ? `<span class="tag called">${esc(r.called)}</span>` : `<span class="tag">${r.reporting ?? 0}% in</span>`) : "";
  const body = m.yes
    ? `<dl><dt class="y">YES</dt><dd>${esc(m.yes)}</dd><dt class="n">NO</dt><dd>${esc(m.no)}</dd></dl>`
    : `<p class="summary">${esc(m.summary)}</p>`;
  return `
    <article class="card measure">
      <div class="card-head"><h4>${esc(m.title)}</h4>${tag}</div>
      <div class="topic">${esc(m.topic)}</div>
      ${body}
      ${tally}
    </article>`;
}

// ---------- early voting ----------
const fmt = (n) => (n ?? 0).toLocaleString();

function lineChart(points) {
  // points: [{label, value}] -> a small inline SVG line chart (no chart library needed)
  if (points.length < 2) return "";
  const W = 640, H = 160, P = { l: 8, r: 8, t: 12, b: 22 };
  const max = Math.max(...points.map((p) => p.value)) || 1;
  const x = (i) => P.l + (i / (points.length - 1)) * (W - P.l - P.r);
  const y = (v) => H - P.b - (v / max) * (H - P.t - P.b);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join("");
  const area = `${path}L${x(points.length - 1)},${H - P.b}L${x(0)},${H - P.b}Z`;
  const last = points[points.length - 1];
  return `
    <svg viewBox="0 0 ${W} ${H}" class="chart" role="img" aria-label="Early votes cast over time, now ${fmt(last.value)}">
      <path d="${area}" fill="var(--dem-soft)" opacity=".6"></path>
      <path d="${path}" fill="none" stroke="var(--ink)" stroke-width="2"></path>
      <circle cx="${x(points.length - 1)}" cy="${y(last.value)}" r="4" fill="var(--ink)"></circle>
      <text x="${P.l}" y="${H - 6}" class="axis">${esc(shortDate(points[0].label))}</text>
      <text x="${W - P.r}" y="${H - 6}" class="axis" text-anchor="end">${esc(shortDate(last.label))}</text>
    </svg>`;
}

function renderEarlyVote(ev, races) {
  const el = document.getElementById("early");
  if (!ev) { el.innerHTML = ""; return; }
  // States we care about: every Senate race on the page, plus Missouri.
  const tracked = new Set(["MO", ...races.sections.find((s) => s.id === "senate").races.map((r) => r.id.slice(0, 2).toUpperCase())]);
  const rows = [...tracked].map((ab) => ({ ab, ...(ev.states[ab] || {}) }))
    .sort((a, b) => (b.voted_all / b.turn_2022 || 0) - (a.voted_all / a.turn_2022 || 0));
  const history = Object.entries(ev.history).map(([label, h]) => ({ label, value: h.total }));

  el.innerHTML = `
    <h2>Early voting</h2>
    <p class="blurb">Ballots already cast by mail or in person, from states that report them. The share compares against each state's <em>total</em> 2022 midterm turnout, so 50% means half as many people have already voted as voted in all of 2022.</p>
    <div class="ev-grid">
      <div class="stat">
        <h3>Ballots cast nationally</h3>
        <div class="big">${fmt(ev.total)}</div>
        <p class="sub">${Object.keys(ev.states).length} states reporting. The line rises partly as more states start reporting.</p>
        ${lineChart(history)}
      </div>
      <div class="stat">
        <h3>States we're watching</h3>
        <table class="ev-table">
          <thead><tr><th>State</th><th class="num">Cast</th><th>vs. 2022 turnout</th></tr></thead>
          <tbody>${rows.map((r) => {
            const pct = r.turn_2022 ? Math.round((r.voted_all / r.turn_2022) * 100) : null;
            return `<tr${r.ab === "AK" ? ' class="hl"' : ""}>
              <td>${esc(r.name || r.ab)}${r.notes ? ` <span class="note info" title="${esc(r.notes)}">ⓘ</span>` : ""}</td>
              <td class="num">${r.voted_all ? fmt(r.voted_all) : "–"}</td>
              <td>${pct != null && r.voted_all ? `<div class="mini"><span style="width:${Math.min(pct, 100)}%"></span></div><span class="pct">${pct}%</span>` : '<span class="note">not reported</span>'}</td>
            </tr>`; }).join("")}
          </tbody>
        </table>
        <p class="sub">States count and report differently; hover ⓘ for UF's notes on a state.</p>
      </div>
    </div>
    <p class="footnote">Source: <a href="${esc(ev.source_url)}">University of Florida Election Lab</a> (CC BY-NC-ND 4.0), updated ${ago(ev.updated)}.</p>`;
}

function renderSections(races, moneyData, fc, results) {
  document.getElementById("tabs").innerHTML =
    `<a href="#overview">Overview</a><a href="#early">Early voting</a>` +
    races.sections.map((s) => `<a href="#${s.id}">${esc(s.title.split(":")[0])}</a>`).join("");

  document.getElementById("sections").innerHTML = races.sections.map((s) => `
    <section class="section" id="${s.id}">
      <h2>${esc(s.title)}</h2>
      ${s.blurb ? `<p class="blurb">${esc(s.blurb)}</p>` : ""}
      ${s.races?.length ? `<div class="grid">${s.races.map((r) => renderRace(r, moneyData, fc, results)).join("")}</div>` : ""}
      ${s.measures?.length ? `
        ${s.races?.length ? `<h3 class="subhead">Ballot questions</h3>` : ""}
        <div class="grid">${s.measures.map((m) => renderMeasure(m, results)).join("")}</div>` : ""}
      ${s.footnote ? `<p class="footnote">${esc(s.footnote)}</p>` : ""}
    </section>`).join("");
}

// ---------- live results straight from civicAPI ----------
// data/results.json is refreshed by a GitHub Action, but GitHub's timer can run late on a
// busy night. civicAPI allows browsers to call it directly, so the page also asks it for
// the latest numbers and lays them over the saved copy. Same matching rules as
// scripts/fetch_results.py.
const CIVIC = "https://civicapi.org/api/v2";
const CIVIC_DOCS = { senate: 87528, house: 87524 };
const REHEARSAL = new URLSearchParams(location.search).has("rehearsal"); // ?rehearsal shows civicAPI test elections
const LIVE_FROM = Date.parse("2026-11-03T23:00:00Z"); // 6pm Central: first polls close

async function civic(id) {
  try {
    const res = await fetch(`${CIVIC}/race/${id}`);
    if (!res.ok) return null;
    const doc = await res.json();
    if (doc.test_data && !REHEARSAL) return null; // never show test data as real
    if (!REHEARSAL && !String(doc.election_date || "").startsWith("2026-11-03")) return null;
    return doc;
  } catch { return null; }
}

// Same rules as pick() in scripts/fetch_results.py: exact name first, then last name only if
// nobody else in the race shares it (Alaska has "Dan Sullivan" AND "Daniel J. Jr. Sullivan").
const norm = (s) => s.toLowerCase().replace(/[“”"]/g, "").split(/\s+/).filter(Boolean).join(" ");
function pick(ours, civicNames, cname) {
  const exact = ours.find((c) => norm(c.name) === norm(cname));
  if (exact) return exact.name;
  for (const c of ours) {
    const last = c.name.split(" ").pop().toLowerCase();
    if (!cname.toLowerCase().includes(last)) continue;
    const sharing = civicNames.filter((n) => n.toLowerCase().includes(last));
    const exactElsewhere = civicNames.some((n) => norm(n) === norm(c.name));
    if (sharing.length === 1 && !exactElsewhere) return c.name;
  }
  return null;
}

function civicMatch(ours, civicCands, reporting) {
  const votes = {}; let called = null;
  const names = (civicCands || []).map((c) => c.name || "");
  for (const cc of civicCands || []) {
    const key = cc.name === "Yes" || cc.name === "No" ? cc.name : pick(ours, names, cc.name || "") || "Other";
    votes[key] = (votes[key] || 0) + (cc.votes || 0);
    if (cc.winner) called = { Yes: "Passed", No: "Failed" }[cc.name] || (key === "Other" ? cc.name : key);
  }
  if (!votes.Other) delete votes.Other;
  return { reporting: reporting || 0, called, votes };
}

async function liveResults(races) {
  if (Date.now() < LIVE_FROM && !REHEARSAL) return {};
  const items = races.sections.flatMap((s) => [...(s.races || []), ...(s.measures || [])]).filter((i) => i.civic);
  const ids = new Set(items.flatMap((i) => i.civic.races || []));
  const [senate, house, ...singles] = await Promise.all(
    [CIVIC_DOCS.senate, CIVIC_DOCS.house, ...ids].map(civic));
  const docs = { senate, house };
  const byId = Object.fromEntries([...ids].map((id, n) => [id, singles[n]]));

  const out = {};
  for (const item of items) {
    const cands = item.candidates || [];
    let r = null;
    if (item.civic.doc) {
      const region = docs[item.civic.doc]?.region_results?.[item.civic.region];
      if (region) r = civicMatch(cands, region.candidates, region.percent_reporting);
    } else {
      for (const id of item.civic.races) {
        const d = byId[id]; if (!d) continue;
        const m = civicMatch(cands, d.candidates, d.percent_reporting);
        const sum = (x) => Object.values(x.votes).reduce((a, b) => a + b, 0);
        if (!r || sum(m) > sum(r)) r = m;
      }
    }
    if (r && (r.called || Object.values(r.votes).some((v) => v > 0))) out[item.id] = r;
  }
  return out;
}

// ---------- main ----------
async function refresh() {
  const status = document.getElementById("status");
  try {
    const [races, moneyData, fc, results, ev] = await Promise.all([
      load("races"),
      load("money").catch(() => ({ candidates: {} })), // page still works before the first FEC run
      load("forecasts"),
      load("results"),
      load("early_vote").catch(() => null),
    ]);
    renderEarlyVote(ev, races);
    // Live numbers win over the saved copy, except hand-entered local results civicAPI doesn't have.
    const live = await liveResults(races);
    const liveCount = Object.keys(live).length;
    if (liveCount) results.results = { ...results.results, ...live };

    renderOverview(fc);
    renderSections(races, moneyData, fc, results);
    const resultsNote = liveCount
      ? `Live results from <a href="https://civicapi.org">civicAPI</a>, checked ${new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`
      : results.updated ? `Results updated ${ago(results.updated)}` : "Results start after polls close Nov. 3";
    status.innerHTML =
      `<span class="dot"></span>${REHEARSAL ? "<b>REHEARSAL (test data)</b> · " : ""}${resultsNote}` +
      ` · Money updated ${ago(moneyData.updated)}` +
      ` · Page re-checks every ${REFRESH_MINUTES} min`;
  } catch (err) {
    console.error(err);
    status.innerHTML = `<span class="error">Couldn't load data: ${esc(err.message)}</span>`;
  }
}

refresh();
setInterval(refresh, REFRESH_MINUTES * 60 * 1000);
