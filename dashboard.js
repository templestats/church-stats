const DATA_BASE = "temple_attendance_output/";
const TREND_URL = DATA_BASE + "trend_dashboard.json";
const URLS_URL = DATA_BASE + "datawrapper_urls.json";

const state = {
  rows: [],
  urls: {},
  selected: [],
  range: "all",
  continent: "",
  country: ""
};

const $ = (id) => document.getElementById(id);

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

function formatDate(value) {
  const d = new Date(value + "T00:00:00");
  return d.toLocaleDateString(undefined, {
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

function getCurrentRows() {
  if (!state.rows.length) return [];
  const latest = state.rows.reduce((max, r) => r.date > max ? r.date : max, "");
  return state.rows.filter(r => r.date === latest);
}

function rowKey(r) {
  return `${r.type}|${r.name}`;
}

function geographyLabel(r) {
  return r.type === "state" ? `${r.name}, ${r.country}` : r.name;
}

function filteredGeographies() {
  return getCurrentRows().filter(r => {
    if (state.continent && r.continent !== state.continent) return false;
    if (state.country && r.country !== state.country) return false;
    return true;
  }).sort((a, b) => geographyLabel(a).localeCompare(geographyLabel(b)));
}

function renderSelectors() {
  const continents = uniqueSorted(state.rows.map(r => r.continent));
  const continentEl = $("continent");
  const countryEl = $("country");

  continentEl.innerHTML = `<option value="">All continents</option>` +
    continents.map(x => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join("");
  continentEl.value = state.continent;

  const countries = uniqueSorted(state.rows
    .filter(r => !state.continent || r.continent === state.continent)
    .map(r => r.country));

  countryEl.innerHTML = `<option value="">All countries</option>` +
    countries.map(x => `<option value="${escapeHtml(x)}">${escapeHtml(x)}</option>`).join("");
  countryEl.value = state.country;

  renderGeoMenu();
}

function renderGeoMenu() {
  const menu = $("geo-menu");
  const options = filteredGeographies();
  const selectedKeys = new Set(state.selected);

  if (!options.length) {
    menu.innerHTML = `<div class="picker-item">No geographies match the current filters.</div>`;
    return;
  }

  menu.innerHTML = options.map(r => {
    const key = rowKey(r);
    return `<label class="picker-item">
      <input type="checkbox" data-geo-key="${escapeHtml(key)}" ${selectedKeys.has(key) ? "checked" : ""}>
      <span>${escapeHtml(geographyLabel(r))}</span>
    </label>`;
  }).join("");
}

function renderChips() {
  const box = $("selection-chips");
  if (!state.selected.length) {
    box.innerHTML = `<span class="status">No geography selected. Choose one or more below.</span>`;
    return;
  }

  box.innerHTML = state.selected.map(key => {
    const r = state.rows.find(x => rowKey(x) === key && x.date === latestDate());
    const label = r ? geographyLabel(r) : key.split("|").slice(1).join("|");
    return `<span class="chip">${escapeHtml(label)}
      <button type="button" data-remove="${escapeHtml(key)}" aria-label="Remove ${escapeHtml(label)}">×</button>
    </span>`;
  }).join("");
}

function latestDate() {
  return state.rows.reduce((max, r) => r.date > max ? r.date : max, "");
}

function renderTrend() {
  const selectedRows = state.rows.filter(r => state.selected.includes(rowKey(r)));
  const latest = latestDate();

  if (!selectedRows.length) {
    Plotly.newPlot("trend-chart", [], {
      margin: { l: 55, r: 20, t: 30, b: 50 },
      xaxis: { visible: false },
      yaxis: { visible: false },
      annotations: [{
        text: "Select one or more geographies to display the trend.",
        showarrow: false,
        font: { size: 15, color: "#66717d" }
      }]
    }, { responsive: true, displaylogo: false });
    $("trend-status").textContent = `Latest data: ${formatDate(latest)}.`;
    renderTable([]);
    return;
  }

  let cutoff = null;
  if (state.range !== "all") {
    const days = Number(state.range);
    const end = new Date(latest + "T00:00:00");
    end.setDate(end.getDate() - days + 1);
    cutoff = end.toISOString().slice(0, 10);
  }

  const traces = [];
  for (const key of state.selected) {
    const rows = selectedRows
      .filter(r => rowKey(r) === key && (!cutoff || r.date >= cutoff))
      .sort((a, b) => a.date.localeCompare(b.date));

    if (!rows.length) continue;

    traces.push({
      x: rows.map(r => r.date),
      y: rows.map(r => r.rate),
      type: "scatter",
      mode: "lines",
      name: geographyLabel(rows[0]),
      hovertemplate: `${escapeHtml(geographyLabel(rows[0]))}<br>%{x|%b %-d, %Y}<br>%{y:.3f} endowments/member<extra></extra>`
    });
  }

  const layout = {
    margin: { l: 65, r: 20, t: 25, b: 55 },
    paper_bgcolor: "white",
    plot_bgcolor: "white",
    hovermode: "x unified",
    legend: { orientation: "h", y: -0.18 },
    xaxis: {
      title: "",
      gridcolor: "#edf0f3",
      linecolor: "#dfe3e8"
    },
    yaxis: {
      title: "Annualized endowments/member",
      gridcolor: "#edf0f3",
      zeroline: false,
      rangemode: "tozero"
    },
    font: { family: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", color: "#17202a" }
  };

  Plotly.newPlot("trend-chart", traces, layout, {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"]
  });

  $("trend-status").textContent =
    `${state.selected.length} geography${state.selected.length === 1 ? "" : "ies"} selected · Data through ${formatDate(latest)}.`;

  renderTable(selectedRows);
}

function renderTable(rows) {
  const body = $("comparison-table").querySelector("tbody");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="6">Select one or more geographies to compare.</td></tr>`;
    return;
  }

  const latest = latestDate();
  const latestByKey = new Map();
  rows.filter(r => r.date === latest).forEach(r => latestByKey.set(rowKey(r), r));

  body.innerHTML = [...latestByKey.values()]
    .sort((a, b) => geographyLabel(a).localeCompare(geographyLabel(b)))
    .map(r => `<tr>
      <td><strong>${escapeHtml(geographyLabel(r))}</strong></td>
      <td>${escapeHtml(r.type)}</td>
      <td>${escapeHtml(r.continent)}</td>
      <td>${escapeHtml(r.country)}</td>
      <td class="rate">${formatRate(r.rate)}</td>
      <td>${escapeHtml(formatDate(r.date))}</td>
    </tr>`).join("");
}

function loadMaps() {
  const world = $("world-map");
  const us = $("us-map");

  if (state.urls.countries) {
    world.innerHTML = `<iframe src="${escapeHtml(state.urls.countries)}" title="Worldwide temple attendance map" loading="lazy"></iframe>`;
  } else {
    world.textContent = "Worldwide map URL unavailable.";
  }

  if (state.urls.us) {
    us.innerHTML = `<iframe src="${escapeHtml(state.urls.us)}" title="U.S. temple attendance map" loading="lazy"></iframe>`;
  } else {
    us.textContent = "U.S. map URL unavailable.";
  }
}

function bindEvents() {
  $("continent").addEventListener("change", e => {
    state.continent = e.target.value;
    state.country = "";
    renderSelectors();
    renderChips();
  });

  $("country").addEventListener("change", e => {
    state.country = e.target.value;
    renderGeoMenu();
  });

  $("geo-picker-button").addEventListener("click", () => {
    const menu = $("geo-menu");
    menu.hidden = !menu.hidden;
  });

  document.addEventListener("click", e => {
    const picker = $("geo-picker");
    if (!picker.contains(e.target)) $("geo-menu").hidden = true;
  });

  $("geo-menu").addEventListener("change", e => {
    if (!e.target.matches("input[data-geo-key]")) return;
    const key = e.target.dataset.geoKey;
    if (e.target.checked) {
      if (!state.selected.includes(key)) state.selected.push(key);
    } else {
      state.selected = state.selected.filter(x => x !== key);
    }
    renderChips();
    renderTrend();
  });

  $("selection-chips").addEventListener("click", e => {
    const key = e.target.dataset.remove;
    if (!key) return;
    state.selected = state.selected.filter(x => x !== key);
    renderGeoMenu();
    renderChips();
    renderTrend();
  });

  $("clear-selection").addEventListener("click", () => {
    state.selected = [];
    renderGeoMenu();
    renderChips();
    renderTrend();
  });

  $("range-buttons").addEventListener("click", e => {
    const range = e.target.dataset.range;
    if (!range) return;
    state.range = range;
    document.querySelectorAll("#range-buttons button").forEach(b =>
      b.classList.toggle("active", b.dataset.range === range)
    );
    renderTrend();
  });
}

async function load() {
  try {
    const [trendResponse, urlsResponse] = await Promise.all([
      fetch(TREND_URL, { cache: "no-store" }),
      fetch(URLS_URL, { cache: "no-store" })
    ]);

    if (!trendResponse.ok) throw new Error(`Trend data returned ${trendResponse.status}`);
    if (!urlsResponse.ok) throw new Error(`Datawrapper URL data returned ${urlsResponse.status}`);

    state.rows = await trendResponse.json();
    state.urls = await urlsResponse.json();

    const latest = latestDate();
    $("freshness").textContent = latest
      ? `Data through ${formatDate(latest)} · ${state.rows.length.toLocaleString()} trend observations`
      : "No trend data available.";

    loadMaps();
    renderSelectors();
    renderChips();
    renderTrend();
  } catch (err) {
    console.error(err);
    $("freshness").textContent = "Unable to load current data.";
    $("trend-status").textContent = `Dashboard error: ${err.message}`;
  }
}

bindEvents();
load();
