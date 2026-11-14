/* Temple Stats interactive explorer — full geographic membership coverage.
 * Generated files from the daily pipeline:
 *   temple_attendance_output/trend_dashboard.json
 *   temple_attendance_output/trend_references.json
 * No member counts are scraped by the browser.
 */
"use strict";
const DATA_BASE = "temple_attendance_output/";
const TREND_URL = DATA_BASE + "trend_dashboard.json";
const REFERENCE_URL = DATA_BASE + "trend_references.json";

const state = {
  rows: [],
  references: {usa: [], worldwide: []},
  selectedContinents: new Set(),
  excludedCountries: new Set(),
  excludedGeographies: new Set(),
  range: "all"
};
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
}[c]));
const formatRate = value => value === null || !Number.isFinite(Number(value))
  ? "—" : Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 3});
const formatInteger = value => Number.isFinite(Number(value))
  ? Number(value).toLocaleString(undefined, {maximumFractionDigits: 0}) : "—";
const formatDate = value => value ? new Date(value + "T00:00:00").toLocaleDateString(undefined, {
  month: "short", day: "numeric", year: "numeric"
}) : "—";
const uniqueSorted = values => [...new Set(values.filter(Boolean))]
  .sort((a, b) => a.localeCompare(b, undefined, {sensitivity: "base"}));
const rowKey = row => `${row.type}|${row.name}`;
const geographyLabel = row => row.type === "state" ? `${row.name}, ${row.country}` : row.name;

function latestDate() {
  return state.rows.reduce((max, row) => row.date > max ? row.date : max, "");
}
function getCurrentRows() {
  const latest = latestDate();
  return state.rows.filter(row => row.date === latest);
}
function availableContinents() {
  return uniqueSorted(getCurrentRows().map(row => row.continent));
}
function availableCountries() {
  return uniqueSorted(getCurrentRows().filter(row =>
    state.selectedContinents.has(row.continent)).map(row => row.country));
}
function selectedCountries() {
  return availableCountries().filter(name => !state.excludedCountries.has(name));
}
function eligibleRows() {
  const countries = new Set(selectedCountries());
  return getCurrentRows().filter(row => countries.has(row.country));
}
function selectedKeys() {
  return eligibleRows().map(rowKey).filter(key => !state.excludedGeographies.has(key));
}
function selectedHistoryRows() {
  const keys = new Set(selectedKeys());
  return state.rows.filter(row => keys.has(rowKey(row)));
}
function currentSelectedRows() {
  const keys = new Set(selectedKeys());
  return getCurrentRows().filter(row => keys.has(rowKey(row)));
}

function updatePickerButton(buttonId, checked, available, label) {
  const button = $(buttonId);
  button.textContent = !available ? `No ${label} available`
    : !checked ? `No ${label} selected`
    : checked === available ? `All ${label} selected`
    : `${checked} of ${available} ${label}`;
}
function renderContinentMenu() {
  const continents = availableContinents();
  const checked = continents.filter(x => state.selectedContinents.has(x)).length;
  $("continent-menu").innerHTML = `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="continent">Select all</button>
      <button type="button" data-action="select-none" data-filter="continent">Select none</button>
    </div>
    ${continents.map(x => `<label class="picker-item"><input type="checkbox"
       data-continent="${escapeHtml(x)}" ${state.selectedContinents.has(x) ? "checked" : ""}>
       <span>${escapeHtml(x)}</span></label>`).join("")}`;
  updatePickerButton("continent-picker-button", checked, continents.length, "continents");
}
function renderCountryMenu() {
  const countries = availableCountries();
  const checked = countries.filter(x => !state.excludedCountries.has(x)).length;
  $("country-menu").innerHTML = countries.length ? `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="country">Select all</button>
      <button type="button" data-action="select-none" data-filter="country">Select none</button>
    </div>
    ${countries.map(x => `<label class="picker-item"><input type="checkbox"
      data-country="${escapeHtml(x)}" ${state.excludedCountries.has(x) ? "" : "checked"}>
      <span>${escapeHtml(x)}</span></label>`).join("")}`
    : `<p class="picker-empty">Select a continent first.</p>`;
  updatePickerButton("country-picker-button", checked, countries.length, "countries");
}
function renderGeoMenu() {
  const rows = eligibleRows().sort((a, b) =>
    geographyLabel(a).localeCompare(geographyLabel(b)));
  const checked = rows.filter(row => !state.excludedGeographies.has(rowKey(row))).length;
  $("geo-menu").innerHTML = rows.length ? `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="geo">Select all</button>
      <button type="button" data-action="select-none" data-filter="geo">Select none</button>
    </div>
    ${rows.map(row => {
      const key = rowKey(row);
      return `<label class="picker-item"><input type="checkbox"
        data-geo-key="${escapeHtml(key)}"
        ${state.excludedGeographies.has(key) ? "" : "checked"}>
        <span>${escapeHtml(geographyLabel(row))}</span></label>`;
    }).join("")}`
    : `<p class="picker-empty">Select one or more countries first.</p>`;
  updatePickerButton("geo-picker-button", checked, rows.length, "geographies");
}
function renderSelectors() {
  renderContinentMenu();
  renderCountryMenu();
  renderGeoMenu();
}

/* Numerator and denominator are additive across unique state/country rows.
   Every published-member country receives a row on every complete observation
   date, including zero-activity rows; the backend never duplicates USA as a
   country while also counting the 50 states. */
function makeAggregateSeries(rows, keys) {
  if (!rows.length || !keys.length) return [];
  const selected = new Set(keys);
  const buckets = new Map();
  for (const row of rows) {
    if (!selected.has(rowKey(row))) continue;
    const entry = buckets.get(row.date) || {date: row.date, annualizedSessions: 0,
      members: 0, geographyCount: 0, singleAnchorCount: 0};
    entry.annualizedSessions += Number(row.annualized_endowments || 0);
    entry.members += Number(row.members || 0);
    entry.geographyCount += 1;
    if (row.membership_status === "single_published_anchor") entry.singleAnchorCount++;
    buckets.set(row.date, entry);
  }
  return [...buckets.values()].sort((a, b) => a.date.localeCompare(b.date))
    .filter(row => row.members > 0)
    .map(row => ({...row, rate: row.annualizedSessions / row.members}));
}
/* National/world reference series are produced by the pipeline using actual
   total-population denominators, not the sum of country observations. */
function makeReferenceSeries(kind, fromDate = null) {
  const series = state.references[kind] || [];
  return series.filter(row => !fromDate || row.date >= fromDate);
}

function showEmptyChart(message) {
  Plotly.newPlot("trend-chart", [], {
    margin: {l: 65, r: 20, t: 25, b: 100},
    xaxis: {visible: false}, yaxis: {visible: false},
    annotations: [{text: message, showarrow: false,
      font: {size: 15, color: "#66717d"}}],
    paper_bgcolor: "white", plot_bgcolor: "white", showlegend: false
  }, {responsive: true, displaylogo: false});
}
function trendTrace(rows, name, line, opacity) {
  return {
    x: rows.map(row => row.date), y: rows.map(row => row.rate),
    type: "scatter", mode: "lines", name, line, opacity,
    hovertemplate: name + "<br>%{x|%b %-d, %Y}<br>%{y:.3f} endowments/member<extra></extra>"
  };
}
function renderTrend() {
  const keys = selectedKeys();
  const latest = latestDate();
  let cutoff = null;
  if (state.range !== "all" && latest) {
    const end = new Date(latest + "T00:00:00Z");
    end.setUTCDate(end.getUTCDate() - Number(state.range) + 1);
    cutoff = end.toISOString().slice(0, 10);
  }
  const filteredRows = selectedHistoryRows().filter(row => !cutoff || row.date >= cutoff);
  const aggregate = makeAggregateSeries(filteredRows, keys);
  const usa = makeReferenceSeries("usa", cutoff);
  const worldwide = makeReferenceSeries("worldwide", cutoff);
  const traces = [];
  if (aggregate.length) traces.push(trendTrace(aggregate, "Selected geographies", {width: 3}, 1));
  if (usa.length) traces.push(trendTrace(usa, "United States (reference)", {width: 2, dash: "dash"}, 0.38));
  if (worldwide.length) traces.push(trendTrace(worldwide, "Worldwide (reference)", {width: 2, dash: "dot"}, 0.38));
  if (!traces.length) showEmptyChart(keys.length
    ? "No trend data available for the selected range."
    : "Select geographies to display their aggregate trend.");
  else Plotly.newPlot("trend-chart", traces, {
    margin: {l: 65, r: 20, t: 25, b: 100},
    paper_bgcolor: "white", plot_bgcolor: "white", hovermode: "x unified",
    showlegend: true,
    legend: {orientation: "h", x: 0.5, xanchor: "center", y: -0.28,
      yanchor: "top", font: {size: 12}},
    xaxis: {gridcolor: "#edf0f3", linecolor: "#dfe3e8"},
    yaxis: {title: "Annualized endowments/member", gridcolor: "#edf0f3",
      zeroline: false, rangemode: "tozero"},
    font: {family: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
      color: "#17202a"}
  }, {responsive: true, displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]});

  const currentAggregate = aggregate.find(row => row.date === latest);
  let status = `${keys.length} ${keys.length === 1 ? "geography" : "geographies"} included` +
    ` · Data through ${formatDate(latest)}.`;
  if (currentAggregate) {
    status += ` Aggregate rate: ${formatRate(currentAggregate.rate)}.`;
    if (currentAggregate.singleAnchorCount) {
      status += ` ${currentAggregate.singleAnchorCount} newly reported ` +
        `geographies use their latest published member count pending a second annual report.`;
    }
  } else if (keys.length) status += " No current observations for this selection.";
  if (!usa.length || !worldwide.length) {
    status += " Some national reference observations are unavailable.";
  }
  $("trend-status").textContent = status;
  renderTable(currentSelectedRows());
}

function renderTable(rows) {
  const body = $("comparison-table").querySelector("tbody");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7">Select one or more geographies to compare.</td></tr>`;
    return;
  }
  const sorted = [...rows].sort((a, b) => geographyLabel(a).localeCompare(geographyLabel(b)));
  const members = sorted.reduce((sum, row) => sum + Number(row.members || 0), 0);
  const sessions = sorted.reduce((sum, row) => sum + Number(row.annualized_endowments || 0), 0);
  const rate = members ? sessions / members : null;
  const date = sorted[0].date;
  body.innerHTML = `<tr class="aggregate-row">
    <td><strong>Selected group (weighted)</strong></td><td>aggregate</td>
    <td>—</td><td>—</td><td class="rate">${formatRate(rate)}</td>
    <td>${formatInteger(members)}</td><td>${escapeHtml(formatDate(date))}</td></tr>` +
    sorted.map(row => `<tr>
      <td><strong>${escapeHtml(geographyLabel(row))}</strong></td>
      <td>${escapeHtml(row.type)}</td><td>${escapeHtml(row.continent)}</td>
      <td>${escapeHtml(row.country)}</td>
      <td class="rate">${formatRate(row.rate)}</td>
      <td>${formatInteger(row.members)}</td>
      <td>${escapeHtml(formatDate(row.date))}</td>
    </tr>`).join("");
}
function toggleMenu(buttonId, menuId) {
  const menu = $(menuId); menu.hidden = !menu.hidden;
  $(buttonId).setAttribute("aria-expanded", String(!menu.hidden));
}
function closeMenu(buttonId, menuId) {
  $(menuId).hidden = true;
  $(buttonId).setAttribute("aria-expanded", "false");
}
function refreshAll() { renderSelectors(); renderTrend(); }
function selectAllContinents() {
  state.selectedContinents = new Set(availableContinents()); refreshAll();
}
function selectNoContinents() { state.selectedContinents.clear(); refreshAll(); }
function selectAllCountries() {
  for (const name of availableCountries()) state.excludedCountries.delete(name);
  refreshAll();
}
function selectNoCountries() {
  for (const name of availableCountries()) state.excludedCountries.add(name);
  refreshAll();
}
function selectAllGeographies() {
  for (const row of eligibleRows()) state.excludedGeographies.delete(rowKey(row));
  refreshAll();
}
function selectNoGeographies() {
  for (const row of eligibleRows()) state.excludedGeographies.add(rowKey(row));
  refreshAll();
}

function bindEvents() {
  for (const [button, menu] of [
    ["continent-picker-button", "continent-menu"],
    ["country-picker-button", "country-menu"],
    ["geo-picker-button", "geo-menu"]
  ]) $(button).addEventListener("click", () => toggleMenu(button, menu));
  document.addEventListener("click", event => {
    for (const [container, button, menu] of [
      ["continent-picker", "continent-picker-button", "continent-menu"],
      ["country-picker", "country-picker-button", "country-menu"],
      ["geo-picker", "geo-picker-button", "geo-menu"]
    ]) if (!$(container).contains(event.target)) closeMenu(button, menu);
  });
  const actions = {
    continent: {"select-all": selectAllContinents, "select-none": selectNoContinents},
    country: {"select-all": selectAllCountries, "select-none": selectNoCountries},
    geo: {"select-all": selectAllGeographies, "select-none": selectNoGeographies}
  };
  for (const filter of ["continent", "country", "geo"]) {
    const menu = $(`${filter}-menu`);
    menu.addEventListener("click", event => {
      const action = event.target.dataset.action;
      if (actions[filter][action]) {
        event.preventDefault(); actions[filter][action]();
      }
    });
  }
  $("continent-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-continent]")) return;
    const value = event.target.dataset.continent;
    if (event.target.checked) state.selectedContinents.add(value);
    else state.selectedContinents.delete(value);
    refreshAll();
  });
  $("country-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-country]")) return;
    const value = event.target.dataset.country;
    if (event.target.checked) state.excludedCountries.delete(value);
    else state.excludedCountries.add(value);
    refreshAll();
  });
  $("geo-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-geo-key]")) return;
    const key = event.target.dataset.geoKey;
    if (event.target.checked) state.excludedGeographies.delete(key);
    else state.excludedGeographies.add(key);
    refreshAll();
  });
  $("clear-selection").textContent = "Reset filters";
  $("clear-selection").addEventListener("click", () => {
    state.selectedContinents = new Set(availableContinents());
    state.excludedCountries.clear(); state.excludedGeographies.clear(); refreshAll();
  });
  $("range-buttons").addEventListener("click", event => {
    const button = event.target.closest("button[data-range]");
    if (!button) return;
    state.range = button.dataset.range;
    document.querySelectorAll("#range-buttons button").forEach(item => {
      const active = item.dataset.range === state.range;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    renderTrend();
  });
}

async function load() {
  try {
    const responses = await Promise.all([fetch(TREND_URL, {cache: "no-store"}),
      fetch(REFERENCE_URL, {cache: "no-store"})]);
    if (!responses.every(response => response.ok))
      throw new Error("Trend or full-population reference data is unavailable. Run the updated daily pipeline.");
    const [rows, references] = await Promise.all(responses.map(response => response.json()));
    if (!Array.isArray(rows) || !rows.length ||
        !references || !Array.isArray(references.usa) ||
        !Array.isArray(references.worldwide) || !references.usa.length ||
        !references.worldwide.length) {
      throw new Error("Daily trend or reference data is incomplete; refusing to publish misleading aggregates.");
    }
    const dates = new Set(rows.map(row => row.date));
    if (!references.usa.every(row => dates.has(row.date)) ||
        !references.worldwide.every(row => dates.has(row.date)))
      throw new Error("Reference and country data use different date ranges.");
    state.rows = rows;
    state.references = references;
    state.selectedContinents = new Set(availableContinents());
    state.excludedCountries.clear(); state.excludedGeographies.clear();
    const latest = latestDate();
    $("freshness").textContent = `Data through ${formatDate(latest)} · ` +
      `${new Set(rows.map(rowKey)).size} geographies tracked`;
    refreshAll();
  } catch (error) {
    console.error(error);
    $("freshness").textContent = "Unable to load current data.";
    $("trend-status").textContent = `Dashboard error: ${error.message}`;
    $("comparison-table").querySelector("tbody").innerHTML =
      `<tr><td colspan="7">Unable to load comparison data.</td></tr>`;
  }
}

// Allow offline pure-function regression tests without loading the DOM.
if (typeof module !== "undefined" && module.exports) {
  module.exports = {state, rowKey, makeAggregateSeries, makeReferenceSeries,
    availableContinents, availableCountries, selectedCountries, eligibleRows,
    selectedKeys, formatInteger};
}
if (typeof document !== "undefined") { bindEvents(); load(); }
