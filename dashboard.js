const DATA_BASE = "temple_attendance_output/";
const TREND_URL = DATA_BASE + "trend_dashboard.json";

const state = {
  rows: [],
  selectedContinents: [],
  selectedCountries: [],
  excludedGeographies: new Set(),
  manuallyIncludedGeographies: new Set(),
  range: "all"
};

const $ = id => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[c]));
}

function formatRate(value) {
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 3
  });
}

function formatInteger(value) {
  return Number(value).toLocaleString();
}

function formatDate(value) {
  const d = new Date(value + "T00:00:00");
  return d.toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric"
  });
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, undefined, { sensitivity: "base" })
  );
}

function rowKey(row) {
  return `${row.type}|${row.name}`;
}

function geographyLabel(row) {
  return row.type === "state" ? `${row.name}, ${row.country}` : row.name;
}

function latestDate() {
  return state.rows.reduce((max, row) => row.date > max ? row.date : max, "");
}

function getCurrentRows() {
  const latest = latestDate();
  return state.rows.filter(row => row.date === latest);
}

function scopeSelected(row) {
  return state.selectedContinents.includes(row.continent) ||
    state.selectedCountries.includes(row.country);
}

// Broad selections include every eligible geography, except explicit exclusions.
// Manual inclusions allow an individual geography to be selected even when no
// continent or country is selected. Exclusions survive all scope changes.
function selectedKeys() {
  const keys = new Set(state.manuallyIncludedGeographies);
  for (const row of getCurrentRows()) {
    const key = rowKey(row);
    if (scopeSelected(row)) keys.add(key);
  }
  for (const key of state.excludedGeographies) keys.delete(key);
  return [...keys].filter(key => getCurrentRows().some(row => rowKey(row) === key));
}

function renderSelectors() {
  renderContinentMenu();
  renderCountryMenu();
  renderGeoMenu();
}

function renderContinentMenu() {
  const menu = $("continent-menu");
  const continents = uniqueSorted(getCurrentRows().map(row => row.continent));
  const selected = new Set(state.selectedContinents);

  menu.innerHTML = `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="continent">Select all</button>
      <button type="button" data-action="select-none" data-filter="continent">Select none</button>
    </div>
    ${continents.map(continent => `
      <label class="picker-item">
        <input type="checkbox" data-continent="${escapeHtml(continent)}" ${selected.has(continent) ? "checked" : ""}>
        <span>${escapeHtml(continent)}</span>
      </label>`).join("")}
  `;
  updatePickerButton("continent-picker-button", state.selectedContinents, continents, "continents");
}

function renderCountryMenu() {
  const menu = $("country-menu");
  const countries = uniqueSorted(getCurrentRows().map(row => row.country));
  const selected = new Set(state.selectedCountries);

  menu.innerHTML = `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="country">Select all</button>
      <button type="button" data-action="select-none" data-filter="country">Select none</button>
    </div>
    ${countries.map(country => `
      <label class="picker-item">
        <input type="checkbox" data-country="${escapeHtml(country)}" ${selected.has(country) ? "checked" : ""}>
        <span>${escapeHtml(country)}</span>
      </label>`).join("")}
  `;
  updatePickerButton("country-picker-button", state.selectedCountries, countries, "countries");
}

function renderGeoMenu() {
  const menu = $("geo-menu");
  const options = getCurrentRows().sort((a, b) => geographyLabel(a).localeCompare(geographyLabel(b)));
  const selected = new Set(selectedKeys());

  menu.innerHTML = `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="geo">Select all</button>
      <button type="button" data-action="select-none" data-filter="geo">Select none</button>
    </div>
    ${options.map(row => {
      const key = rowKey(row);
      return `<label class="picker-item">
        <input type="checkbox" data-geo-key="${escapeHtml(key)}" ${selected.has(key) ? "checked" : ""}>
        <span>${escapeHtml(geographyLabel(row))}</span>
      </label>`;
    }).join("")}
  `;
  updatePickerButton("geo-picker-button", selectedKeys(), options.map(rowKey), "geographies");
}

function updatePickerButton(buttonId, selected, available, label) {
  const button = $(buttonId);
  if (!available.length) {
    button.textContent = `No ${label} available`;
    return;
  }
  if (selected.length === available.length) {
    button.textContent = `All ${label} selected`;
  } else if (!selected.length) {
    button.textContent = `No ${label} selected`;
  } else {
    button.textContent = `${selected.length} ${label} selected`;
  }
}

function renderChips() {
  const box = $("selection-chips");
  const keys = selectedKeys();
  if (!keys.length) {
    box.innerHTML = `<span class="status">No geographies selected. Choose a continent, country, or individual geography.</span>`;
    return;
  }

  const current = new Map(getCurrentRows().map(row => [rowKey(row), row]));
  box.innerHTML = keys.map(key => {
    const row = current.get(key);
    const label = row ? geographyLabel(row) : key.split("|").slice(1).join("|");
    return `<span class="chip">${escapeHtml(label)}<button type="button" data-remove="${escapeHtml(key)}" aria-label="Remove ${escapeHtml(label)}">×</button></span>`;
  }).join("");
}

function currentSelectedRows() {
  const keys = new Set(selectedKeys());
  const latest = latestDate();
  return state.rows.filter(row => row.date === latest && keys.has(rowKey(row)));
}

function selectedHistoryRows() {
  const keys = new Set(selectedKeys());
  return state.rows.filter(row => keys.has(rowKey(row)));
}

function makeAggregateSeries(rows, keys) {
  if (keys.length < 2) return [];
  const byKeyAndDate = new Map(rows.map(row => [`${rowKey(row)}|${row.date}`, row]));
  const dates = uniqueSorted(rows.map(row => row.date)).filter(date =>
    keys.every(key => byKeyAndDate.has(`${key}|${date}`))
  );

  return dates.map(date => {
    const matching = keys.map(key => byKeyAndDate.get(`${key}|${date}`));
    const annualizedSessions = matching.reduce((sum, row) => sum + Number(row.annualized_endowments || 0), 0);
    const members = matching.reduce((sum, row) => sum + Number(row.members || 0), 0);
    return { date, rate: members ? annualizedSessions / members : null, members, annualizedSessions };
  }).filter(row => row.rate !== null);
}

function renderTrend() {
  const keys = selectedKeys();
  const historyRows = selectedHistoryRows();
  const latest = latestDate();

  if (!keys.length) {
    Plotly.newPlot("trend-chart", [], {
      margin: { l: 60, r: 20, t: 30, b: 50 },
      xaxis: { visible: false }, yaxis: { visible: false },
      annotations: [{ text: "Select one or more geographies to display the trend.", showarrow: false, font: { size: 15, color: "#66717d" } }]
    }, { responsive: true, displaylogo: false });
    $("trend-status").textContent = latest ? `Latest data: ${formatDate(latest)}.` : "No trend data available.";
    renderTable([]);
    return;
  }

  let cutoff = null;
  if (state.range !== "all") {
    const end = new Date(latest + "T00:00:00");
    end.setDate(end.getDate() - Number(state.range) + 1);
    cutoff = end.toISOString().slice(0, 10);
  }

  const traces = [];
  for (const key of keys) {
    const rows = historyRows.filter(row => rowKey(row) === key && (!cutoff || row.date >= cutoff)).sort((a, b) => a.date.localeCompare(b.date));
    if (!rows.length) continue;
    traces.push({
      x: rows.map(row => row.date), y: rows.map(row => row.rate),
      type: "scatter", mode: "lines", name: geographyLabel(rows[0]),
      hovertemplate: `${escapeHtml(geographyLabel(rows[0]))}<br>%{x|%b %-d, %Y}<br>%{y:.3f} endowments/member<extra></extra>`
    });
  }

  const aggregate = makeAggregateSeries(historyRows.filter(row => !cutoff || row.date >= cutoff), keys);
  if (aggregate.length) {
    traces.push({
      x: aggregate.map(row => row.date), y: aggregate.map(row => row.rate),
      type: "scatter", mode: "lines", name: "Selected group (weighted)",
      line: { width: 4, dash: "dash" },
      hovertemplate: "Selected group (weighted)<br>%{x|%b %-d, %Y}<br>%{y:.3f} endowments/member<extra></extra>"
    });
  }

  Plotly.newPlot("trend-chart", traces, {
    margin: { l: 65, r: 20, t: 25, b: 70 },
    paper_bgcolor: "white", plot_bgcolor: "white", hovermode: "x unified",
    legend: { orientation: "h", y: -0.24 },
    xaxis: { gridcolor: "#edf0f3", linecolor: "#dfe3e8" },
    yaxis: { title: "Annualized endowments/member", gridcolor: "#edf0f3", zeroline: false, rangemode: "tozero" },
    font: { family: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", color: "#17202a" }
  }, { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] });

  const weighted = aggregate.find(row => row.date === latest);
  const groupNote = weighted ? ` Weighted selected-group rate: ${formatRate(weighted.rate)}.` : "";
  $("trend-status").textContent = `${keys.length} geography${keys.length === 1 ? "" : "ies"} selected · Data through ${formatDate(latest)}.${groupNote}`;
  renderTable(currentSelectedRows());
}

function renderTable(rows) {
  const body = $("comparison-table").querySelector("tbody");
  const keys = selectedKeys();
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="7">Select one or more geographies to compare.</td></tr>`;
    return;
  }

  const sorted = [...rows].sort((a, b) => geographyLabel(a).localeCompare(geographyLabel(b)));
  const totalMembers = sorted.reduce((sum, row) => sum + Number(row.members || 0), 0);
  const totalAnnualized = sorted.reduce((sum, row) => sum + Number(row.annualized_endowments || 0), 0);
  const totalRate = totalMembers ? totalAnnualized / totalMembers : 0;
  const first = sorted[0];
  const aggregateRow = keys.length > 1 ? `<tr class="aggregate-row">
    <td><strong>Selected group (weighted)</strong></td><td>aggregate</td><td>—</td><td>—</td>
    <td class="rate">${formatRate(totalRate)}</td><td>${formatInteger(totalMembers)}</td><td>${escapeHtml(formatDate(first.date))}</td>
  </tr>` : "";

  body.innerHTML = aggregateRow + sorted.map(row => `<tr>
    <td><strong>${escapeHtml(geographyLabel(row))}</strong></td>
    <td>${escapeHtml(row.type)}</td><td>${escapeHtml(row.continent)}</td><td>${escapeHtml(row.country)}</td>
    <td class="rate">${formatRate(row.rate)}</td><td>${formatInteger(row.members)}</td><td>${escapeHtml(formatDate(row.date))}</td>
  </tr>`).join("");
}

function toggleMenu(buttonId, menuId) {
  const menu = $(menuId);
  const button = $(buttonId);
  menu.hidden = !menu.hidden;
  button.setAttribute("aria-expanded", String(!menu.hidden));
}

function closeMenu(buttonId, menuId) {
  $(menuId).hidden = true;
  $(buttonId).setAttribute("aria-expanded", "false");
}

function addScopeGeographies(rows) {
  // Broad selections include eligible geographies, but never erase an explicit
  // individual exclusion. A geography exclusion is cleared only when the user
  // explicitly checks that geography (or uses Select all in the geography menu).
  // The parameter is retained to make the call sites self-documenting.
  void rows;
}

function excludeScopeGeographies(rows) {
  for (const row of rows) {
    const key = rowKey(row);
    state.excludedGeographies.add(key);
    state.manuallyIncludedGeographies.delete(key);
  }
}

function selectAllContinents() {
  state.selectedContinents = uniqueSorted(getCurrentRows().map(row => row.continent));
  addScopeGeographies(getCurrentRows().filter(row => state.selectedContinents.includes(row.continent)));
  refreshAll();
}

function selectNoneContinents() {
  const rows = getCurrentRows().filter(row => state.selectedContinents.includes(row.continent));
  state.selectedContinents = [];
  excludeScopeGeographies(rows.filter(row => !state.selectedCountries.includes(row.country)));
  refreshAll();
}

function selectAllCountries() {
  state.selectedCountries = uniqueSorted(getCurrentRows().map(row => row.country));
  addScopeGeographies(getCurrentRows().filter(row => state.selectedCountries.includes(row.country)));
  refreshAll();
}

function selectNoneCountries() {
  const rows = getCurrentRows().filter(row => state.selectedCountries.includes(row.country));
  state.selectedCountries = [];
  excludeScopeGeographies(rows.filter(row => !state.selectedContinents.includes(row.continent)));
  refreshAll();
}

function selectAllGeographies() {
  state.excludedGeographies.clear();
  state.manuallyIncludedGeographies = new Set(getCurrentRows().map(rowKey));
  refreshAll();
}

function selectNoneGeographies() {
  state.excludedGeographies = new Set(getCurrentRows().map(rowKey));
  state.manuallyIncludedGeographies.clear();
  refreshAll();
}

function refreshAll() {
  renderSelectors();
  renderChips();
  renderTrend();
}

function bindEvents() {
  $("continent-picker-button").addEventListener("click", () => toggleMenu("continent-picker-button", "continent-menu"));
  $("country-picker-button").addEventListener("click", () => toggleMenu("country-picker-button", "country-menu"));
  $("geo-picker-button").addEventListener("click", () => toggleMenu("geo-picker-button", "geo-menu"));

  document.addEventListener("click", event => {
    for (const [containerId, buttonId, menuId] of [
      ["continent-picker", "continent-picker-button", "continent-menu"],
      ["country-picker", "country-picker-button", "country-menu"],
      ["geo-picker", "geo-picker-button", "geo-menu"]
    ]) {
      if (!$(containerId).contains(event.target)) closeMenu(buttonId, menuId);
    }
  });

  $("continent-menu").addEventListener("click", event => {
    const action = event.target.dataset.action;
    if (action === "select-all") { event.preventDefault(); selectAllContinents(); }
    if (action === "select-none") { event.preventDefault(); selectNoneContinents(); }
  });
  $("continent-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-continent]")) return;
    const continent = event.target.dataset.continent;
    const rows = getCurrentRows().filter(row => row.continent === continent);
    if (event.target.checked) {
      if (!state.selectedContinents.includes(continent)) state.selectedContinents.push(continent);
      addScopeGeographies(rows);
    } else {
      state.selectedContinents = state.selectedContinents.filter(value => value !== continent);
      excludeScopeGeographies(rows.filter(row => !state.selectedCountries.includes(row.country)));
    }
    refreshAll();
  });

  $("country-menu").addEventListener("click", event => {
    const action = event.target.dataset.action;
    if (action === "select-all") { event.preventDefault(); selectAllCountries(); }
    if (action === "select-none") { event.preventDefault(); selectNoneCountries(); }
  });
  $("country-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-country]")) return;
    const country = event.target.dataset.country;
    const rows = getCurrentRows().filter(row => row.country === country);
    if (event.target.checked) {
      if (!state.selectedCountries.includes(country)) state.selectedCountries.push(country);
      addScopeGeographies(rows);
    } else {
      state.selectedCountries = state.selectedCountries.filter(value => value !== country);
      excludeScopeGeographies(rows.filter(row => !state.selectedContinents.includes(row.continent)));
    }
    refreshAll();
  });

  $("geo-menu").addEventListener("click", event => {
    const action = event.target.dataset.action;
    if (action === "select-all") { event.preventDefault(); selectAllGeographies(); }
    if (action === "select-none") { event.preventDefault(); selectNoneGeographies(); }
  });
  $("geo-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-geo-key]")) return;
    const key = event.target.dataset.geoKey;
    if (event.target.checked) {
      state.excludedGeographies.delete(key);
      state.manuallyIncludedGeographies.add(key);
    } else {
      state.excludedGeographies.add(key);
      state.manuallyIncludedGeographies.delete(key);
    }
    refreshAll();
  });

  $("selection-chips").addEventListener("click", event => {
    const key = event.target.dataset.remove;
    if (!key) return;
    state.excludedGeographies.add(key);
    state.manuallyIncludedGeographies.delete(key);
    refreshAll();
  });

  $("clear-selection").addEventListener("click", () => {
    state.selectedContinents = [];
    state.selectedCountries = [];
    state.excludedGeographies = new Set(getCurrentRows().map(rowKey));
    state.manuallyIncludedGeographies.clear();
    refreshAll();
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
    const response = await fetch(TREND_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`Trend data returned ${response.status}`);
    state.rows = await response.json();
    if (!Array.isArray(state.rows) || !state.rows.length) throw new Error("Trend data is empty or invalid.");

    const continents = uniqueSorted(getCurrentRows().map(row => row.continent));
    state.selectedContinents = continents;
    state.selectedCountries = [];
    state.excludedGeographies.clear();
    state.manuallyIncludedGeographies.clear();

    const latest = latestDate();
    $("freshness").textContent = latest
      ? `Data through ${formatDate(latest)} · ${state.rows.length.toLocaleString()} trend observations`
      : "No trend data available.";

    refreshAll();
  } catch (error) {
    console.error(error);
    $("freshness").textContent = "Unable to load current data.";
    $("trend-status").textContent = `Dashboard error: ${error.message}`;
    $("comparison-table").querySelector("tbody").innerHTML = `<tr><td colspan="7">Unable to load comparison data.</td></tr>`;
  }
}

bindEvents();
load();
