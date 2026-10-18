
const DATA_BASE = "temple_attendance_output/";
const TREND_URL = DATA_BASE + "trend_dashboard.json";

const state = {
  rows: [],
  selectedContinents: new Set(),
  excludedCountries: new Set(),
  excludedGeographies: new Set(),
  range: "all"
};

const $ = id => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
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
  if (!value) return "—";
  return new Date(value + "T00:00:00").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
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
  return row.type === "state"
    ? `${row.name}, ${row.country}`
    : row.name;
}

function latestDate() {
  return state.rows.reduce(
    (max, row) => row.date > max ? row.date : max,
    ""
  );
}

function getCurrentRows() {
  const latest = latestDate();
  return state.rows.filter(row => row.date === latest);
}

/* =========================================================
   CASCADING FILTER LOGIC

   Continents determine which countries are visible.
   Country exclusions determine which geographies are visible.
   Geography exclusions determine which rows enter the selected
   aggregate. Exclusions persist when their items leave scope.
   ========================================================= */

function availableContinents() {
  return uniqueSorted(getCurrentRows().map(row => row.continent));
}

function availableCountries() {
  return uniqueSorted(
    getCurrentRows()
      .filter(row => state.selectedContinents.has(row.continent))
      .map(row => row.country)
  );
}

function selectedCountries() {
  return availableCountries().filter(country =>
    !state.excludedCountries.has(country)
  );
}

function eligibleRows() {
  const countries = new Set(selectedCountries());

  return getCurrentRows().filter(row =>
    countries.has(row.country)
  );
}

function selectedKeys() {
  return eligibleRows()
    .map(rowKey)
    .filter(key => !state.excludedGeographies.has(key));
}

function selectedHistoryRows() {
  const keys = new Set(selectedKeys());

  return state.rows.filter(row => keys.has(rowKey(row)));
}

function currentSelectedRows() {
  const keys = new Set(selectedKeys());

  return getCurrentRows().filter(row => keys.has(rowKey(row)));
}

/* ---------- Picker button labels ---------- */

function updatePickerButton(buttonId, checkedCount, availableCount, label) {
  const button = $(buttonId);

  if (availableCount === 0) {
    button.textContent = `No ${label} available`;
  } else if (checkedCount === 0) {
    button.textContent = `No ${label} selected`;
  } else if (checkedCount === availableCount) {
    button.textContent = `All ${label} selected`;
  } else {
    button.textContent = `${checkedCount} of ${availableCount} ${label}`;
  }
}

/* ---------- Continents ---------- */

function renderContinentMenu() {
  const continents = availableContinents();
  const checkedCount = continents.filter(continent =>
    state.selectedContinents.has(continent)
  ).length;

  $("continent-menu").innerHTML = `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="continent">Select all</button>
      <button type="button" data-action="select-none" data-filter="continent">Select none</button>
    </div>

    ${continents.map(continent => `
      <label class="picker-item">
        <input
          type="checkbox"
          data-continent="${escapeHtml(continent)}"
          ${state.selectedContinents.has(continent) ? "checked" : ""}>
        <span>${escapeHtml(continent)}</span>
      </label>
    `).join("")}
  `;

  updatePickerButton(
    "continent-picker-button",
    checkedCount,
    continents.length,
    "continents"
  );
}

/* ---------- Countries ---------- */

function renderCountryMenu() {
  const countries = availableCountries();

  const checkedCount = countries.filter(country =>
    !state.excludedCountries.has(country)
  ).length;

  $("country-menu").innerHTML = countries.length ? `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="country">Select all</button>
      <button type="button" data-action="select-none" data-filter="country">Select none</button>
    </div>

    ${countries.map(country => `
      <label class="picker-item">
        <input
          type="checkbox"
          data-country="${escapeHtml(country)}"
          ${state.excludedCountries.has(country) ? "" : "checked"}>
        <span>${escapeHtml(country)}</span>
      </label>
    `).join("")}
  ` : `<p class="picker-empty">Select a continent first.</p>`;

  updatePickerButton(
    "country-picker-button",
    checkedCount,
    countries.length,
    "countries"
  );
}

/* ---------- Geographies ---------- */

function renderGeoMenu() {
  const rows = eligibleRows().sort((a, b) =>
    geographyLabel(a).localeCompare(geographyLabel(b))
  );

  const checkedCount = rows.filter(row =>
    !state.excludedGeographies.has(rowKey(row))
  ).length;

  $("geo-menu").innerHTML = rows.length ? `
    <div class="picker-actions">
      <button type="button" data-action="select-all" data-filter="geo">Select all</button>
      <button type="button" data-action="select-none" data-filter="geo">Select none</button>
    </div>

    ${rows.map(row => {
      const key = rowKey(row);
      const checked = !state.excludedGeographies.has(key);

      return `
        <label class="picker-item">
          <input
            type="checkbox"
            data-geo-key="${escapeHtml(key)}"
            ${checked ? "checked" : ""}>
          <span>${escapeHtml(geographyLabel(row))}</span>
        </label>
      `;
    }).join("")}
  ` : `<p class="picker-empty">Select one or more countries first.</p>`;

  updatePickerButton(
    "geo-picker-button",
    checkedCount,
    rows.length,
    "geographies"
  );
}

function renderSelectors() {
  renderContinentMenu();
  renderCountryMenu();
  renderGeoMenu();
}

/* ---------- Aggregate trend calculation ---------- */

// Calculate a membership-weighted rate for each date where every
// requested geography has an observation.
//
// Aggregate rate = sum(annualized endowment sessions) / sum(members).
function makeAggregateSeries(rows, keys) {
  if (!keys.length) return [];

  const byKeyAndDate = new Map(
    rows.map(row => [`${rowKey(row)}|${row.date}`, row])
  );

  const dates = uniqueSorted(rows.map(row => row.date)).filter(date =>
    keys.every(key => byKeyAndDate.has(`${key}|${date}`))
  );

  return dates.map(date => {
    const matching = keys.map(key =>
      byKeyAndDate.get(`${key}|${date}`)
    );

    const annualizedSessions = matching.reduce(
      (sum, row) => sum + Number(row.annualized_endowments || 0),
      0
    );

    const members = matching.reduce(
      (sum, row) => sum + Number(row.members || 0),
      0
    );

    return {
      date,
      rate: members > 0 ? annualizedSessions / members : null,
      members,
      annualizedSessions
    };
  }).filter(row => row.rate !== null);
}

/* ---------- Persistent reference trends ---------- */

function normalizePlace(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[.,]/g, "")
    .replace(/\s+/g, " ");
}

function isUSCountry(value) {
  return [
    "united states",
    "united states of america",
    "usa",
    "us"
  ].includes(normalizePlace(value));
}

function makeReferenceSeries(kind, rows) {
  // Reference lines are independent of the active filters.
  // Use the latest rows only to determine the geography keys.
  const currentRows = getCurrentRows();

  let referenceKeys;

  if (kind === "worldwide") {
    // Same set of geographies as the initial all-selected view.
    referenceKeys = currentRows.map(rowKey);
  } else if (kind === "usa") {
    // Combine U.S. states into one weighted national rate.
    referenceKeys = currentRows
      .filter(row =>
        normalizePlace(row.type) === "state" &&
        isUSCountry(row.country)
      )
      .map(rowKey);
  } else {
    return [];
  }

  return makeAggregateSeries(rows, referenceKeys);
}

/* ---------- Chart helpers ---------- */

function showEmptyChart(message) {
  Plotly.newPlot("trend-chart", [], {
    margin: { l: 65, r: 20, t: 25, b: 100 },
    xaxis: { visible: false },
    yaxis: { visible: false },
    annotations: [{
      text: message,
      showarrow: false,
      font: { size: 15, color: "#66717d" }
    }],
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    showlegend: false
  }, {
    responsive: true,
    displaylogo: false
  });
}

/* ---------- Three-line trend chart ---------- */

function renderTrend() {
  const keys = selectedKeys();
  const selectedRows = selectedHistoryRows();
  const latest = latestDate();

  let cutoff = null;

  if (state.range !== "all" && latest) {
    const end = new Date(latest + "T00:00:00");
    end.setDate(end.getDate() - Number(state.range) + 1);
    cutoff = end.toISOString().slice(0, 10);
  }

  const inRange = row => !cutoff || row.date >= cutoff;

  const filteredSelectedRows = selectedRows.filter(inRange);
  const filteredAllRows = state.rows.filter(inRange);

  const aggregate = makeAggregateSeries(filteredSelectedRows, keys);
  const usa = makeReferenceSeries("usa", filteredAllRows);
  const worldwide = makeReferenceSeries("worldwide", filteredAllRows);

  const traces = [];

  if (aggregate.length) {
    traces.push({
      x: aggregate.map(row => row.date),
      y: aggregate.map(row => row.rate),
      type: "scatter",
      mode: "lines",
      name: "Selected geographies",
      line: { width: 3 },
      opacity: 1,
      hovertemplate:
        "Selected geographies<br>" +
        "%{x|%b %-d, %Y}<br>" +
        "%{y:.3f} endowments/member<extra></extra>"
    });
  }

  if (usa.length) {
    traces.push({
      x: usa.map(row => row.date),
      y: usa.map(row => row.rate),
      type: "scatter",
      mode: "lines",
      name: "United States (reference)",
      line: { width: 2, dash: "dash" },
      opacity: 0.38,
      hovertemplate:
        "United States (reference)<br>" +
        "%{x|%b %-d, %Y}<br>" +
        "%{y:.3f} endowments/member<extra></extra>"
    });
  }

  if (worldwide.length) {
    traces.push({
      x: worldwide.map(row => row.date),
      y: worldwide.map(row => row.rate),
      type: "scatter",
      mode: "lines",
      name: "Worldwide (reference)",
      line: { width: 2, dash: "dot" },
      opacity: 0.38,
      hovertemplate:
        "Worldwide (reference)<br>" +
        "%{x|%b %-d, %Y}<br>" +
        "%{y:.3f} endowments/member<extra></extra>"
    });
  }

  if (!traces.length) {
    showEmptyChart(
      keys.length
        ? "No trend data available for the selected range."
        : "Select geographies to display their aggregate trend."
    );
  } else {
    Plotly.newPlot("trend-chart", traces, {
      margin: { l: 65, r: 20, t: 25, b: 100 },
      paper_bgcolor: "white",
      plot_bgcolor: "white",
      hovermode: "x unified",
      showlegend: true,
      legend: {
        orientation: "h",
        x: 0.5,
        xanchor: "center",
        y: -0.28,
        yanchor: "top",
        font: { size: 12 }
      },
      xaxis: {
        gridcolor: "#edf0f3",
        linecolor: "#dfe3e8"
      },
      yaxis: {
        title: "Annualized endowments/member",
        gridcolor: "#edf0f3",
        zeroline: false,
        rangemode: "tozero"
      },
      font: {
        family: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
        color: "#17202a"
      }
    }, {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"]
    });
  }

  const latestAggregate = aggregate.find(row => row.date === latest);

  let status =
    `${keys.length} geography${keys.length === 1 ? "" : "ies"} included` +
    ` · Data through ${formatDate(latest)}.`;

  if (latestAggregate) {
    status += ` Aggregate rate: ${formatRate(latestAggregate.rate)}.`;
  } else if (keys.length) {
    status +=
      " The latest date does not have complete data for every selected geography.";
  } else {
    status += " No selected geographies.";
  }

  if (!usa.length) {
    status += " USA reference data could not be calculated from the available state rows.";
  }

  if (!worldwide.length) {
    status += " Worldwide reference data could not be calculated.";
  }

  $("trend-status").textContent = status;
  renderTable(currentSelectedRows());
}

/* ---------- Comparison table ---------- */

function renderTable(rows) {
  const body = $("comparison-table").querySelector("tbody");

  if (!rows.length) {
    body.innerHTML = `
      <tr><td colspan="7">Select one or more geographies to compare.</td></tr>
    `;
    return;
  }

  const sorted = [...rows].sort((a, b) =>
    geographyLabel(a).localeCompare(geographyLabel(b))
  );

  const totalMembers = sorted.reduce(
    (sum, row) => sum + Number(row.members || 0), 0
  );

  const totalSessions = sorted.reduce(
    (sum, row) => sum + Number(row.annualized_endowments || 0), 0
  );

  const totalRate = totalMembers ? totalSessions / totalMembers : 0;
  const date = sorted[0].date;

  const aggregateRow = `
    <tr class="aggregate-row">
      <td><strong>Selected group (weighted)</strong></td>
      <td>aggregate</td><td>—</td><td>—</td>
      <td class="rate">${formatRate(totalRate)}</td>
      <td>${formatInteger(totalMembers)}</td>
      <td>${escapeHtml(formatDate(date))}</td>
    </tr>
  `;

  body.innerHTML = aggregateRow + sorted.map(row => `
    <tr>
      <td><strong>${escapeHtml(geographyLabel(row))}</strong></td>
      <td>${escapeHtml(row.type)}</td>
      <td>${escapeHtml(row.continent)}</td>
      <td>${escapeHtml(row.country)}</td>
      <td class="rate">${formatRate(row.rate)}</td>
      <td>${formatInteger(row.members)}</td>
      <td>${escapeHtml(formatDate(row.date))}</td>
    </tr>
  `).join("");
}

/* ---------- Dropdown open/close ---------- */

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

function refreshAll() {
  renderSelectors();
  renderTrend();
}

/* ---------- Continent selection ---------- */

function selectAllContinents() {
  state.selectedContinents = new Set(availableContinents());
  refreshAll();
}

function selectNoContinents() {
  state.selectedContinents.clear();
  refreshAll();
}

/* ---------- Country selection ---------- */

function selectAllCountries() {
  for (const country of availableCountries()) {
    state.excludedCountries.delete(country);
  }
  refreshAll();
}

function selectNoCountries() {
  for (const country of availableCountries()) {
    state.excludedCountries.add(country);
  }
  refreshAll();
}

/* ---------- Geography selection ---------- */

function selectAllGeographies() {
  for (const row of eligibleRows()) {
    state.excludedGeographies.delete(rowKey(row));
  }
  refreshAll();
}

function selectNoGeographies() {
  for (const row of eligibleRows()) {
    state.excludedGeographies.add(rowKey(row));
  }
  refreshAll();
}

/* ---------- Events ---------- */

function bindEvents() {
  $("continent-picker-button").addEventListener("click", () =>
    toggleMenu("continent-picker-button", "continent-menu")
  );

  $("country-picker-button").addEventListener("click", () =>
    toggleMenu("country-picker-button", "country-menu")
  );

  $("geo-picker-button").addEventListener("click", () =>
    toggleMenu("geo-picker-button", "geo-menu")
  );

  document.addEventListener("click", event => {
    for (const [container, button, menu] of [
      ["continent-picker", "continent-picker-button", "continent-menu"],
      ["country-picker", "country-picker-button", "country-menu"],
      ["geo-picker", "geo-picker-button", "geo-menu"]
    ]) {
      if (!$(container).contains(event.target)) {
        closeMenu(button, menu);
      }
    }
  });

  /* Continent checkboxes */

  $("continent-menu").addEventListener("click", event => {
    const action = event.target.dataset.action;

    if (action === "select-all") {
      event.preventDefault();
      selectAllContinents();
    }

    if (action === "select-none") {
      event.preventDefault();
      selectNoContinents();
    }
  });

  $("continent-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-continent]")) return;

    const continent = event.target.dataset.continent;

    if (event.target.checked) {
      state.selectedContinents.add(continent);
    } else {
      state.selectedContinents.delete(continent);
    }

    refreshAll();
  });

  /* Country checkboxes */

  $("country-menu").addEventListener("click", event => {
    const action = event.target.dataset.action;

    if (action === "select-all") {
      event.preventDefault();
      selectAllCountries();
    }

    if (action === "select-none") {
      event.preventDefault();
      selectNoCountries();
    }
  });

  $("country-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-country]")) return;

    const country = event.target.dataset.country;

    if (event.target.checked) {
      state.excludedCountries.delete(country);
    } else {
      state.excludedCountries.add(country);
    }

    refreshAll();
  });

  /* Geography checkboxes */

  $("geo-menu").addEventListener("click", event => {
    const action = event.target.dataset.action;

    if (action === "select-all") {
      event.preventDefault();
      selectAllGeographies();
    }

    if (action === "select-none") {
      event.preventDefault();
      selectNoGeographies();
    }
  });

  $("geo-menu").addEventListener("change", event => {
    if (!event.target.matches("input[data-geo-key]")) return;

    const key = event.target.dataset.geoKey;

    if (event.target.checked) {
      state.excludedGeographies.delete(key);
    } else {
      state.excludedGeographies.add(key);
    }

    refreshAll();
  });

  /* Reset filters */

  $("clear-selection").textContent = "Reset filters";

  $("clear-selection").addEventListener("click", () => {
    state.selectedContinents = new Set(availableContinents());
    state.excludedCountries.clear();
    state.excludedGeographies.clear();
    refreshAll();
  });

  /* Date range */

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

/* ---------- Load data ---------- */

async function load() {
  try {
    const response = await fetch(TREND_URL, {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`Trend data returned ${response.status}`);
    }

    state.rows = await response.json();

    if (!Array.isArray(state.rows) || !state.rows.length) {
      throw new Error("Trend data is empty or invalid.");
    }

    state.selectedContinents = new Set(availableContinents());
    state.excludedCountries.clear();
    state.excludedGeographies.clear();

    const latest = latestDate();

    $("freshness").textContent = latest
      ? `Data through ${formatDate(latest)} · ${state.rows.length.toLocaleString()} trend observations`
      : "No trend data available.";

    refreshAll();
  } catch (error) {
    console.error(error);

    $("freshness").textContent = "Unable to load current data.";
    $("trend-status").textContent = `Dashboard error: ${error.message}`;

    $("comparison-table").querySelector("tbody").innerHTML = `
      <tr><td colspan="7">Unable to load comparison data.</td></tr>
    `;
  }
}

bindEvents();
load();
