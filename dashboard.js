const DATA_BASE = "temple_attendance_output/";
const TREND_URL = DATA_BASE + "trend_dashboard.json";
const URLS_URL = DATA_BASE + "datawrapper_urls.json";

const state = {
  rows: [],
  urls: {},
  selectedContinents: [],
  selectedCountries: [],
  selectedGeographies: [],
  range: "all"
};

const $ = (id) => document.getElementById(id);

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

function latestDate() {
  return state.rows.reduce(
    (max, r) => r.date > max ? r.date : max,
    ""
  );
}

function getCurrentRows() {
  const latest = latestDate();

  if (!latest) {
    return [];
  }

  return state.rows.filter(r => r.date === latest);
}

function rowKey(r) {
  return `${r.type}|${r.name}`;
}

function geographyLabel(r) {
  return r.type === "state"
    ? `${r.name}, ${r.country}`
    : r.name;
}

function getAllContinents() {
  return uniqueSorted(
    state.rows.map(r => r.continent)
  );
}

function getAllCountries() {
  return uniqueSorted(
    state.rows.map(r => r.country)
  );
}

function getCountriesForSelectedContinents() {
  return uniqueSorted(
    state.rows
      .filter(r =>
        state.selectedContinents.includes(r.continent)
      )
      .map(r => r.country)
  );
}

function getAvailableGeographies() {
  return getCurrentRows()
    .filter(r =>
      state.selectedContinents.includes(r.continent) &&
      state.selectedCountries.includes(r.country)
    )
    .sort((a, b) =>
      geographyLabel(a).localeCompare(
        geographyLabel(b),
        undefined,
        { sensitivity: "base" }
      )
    );
}

function getSelectedGeographies() {
  const availableKeys = new Set(
    getAvailableGeographies().map(rowKey)
  );

  return getCurrentRows()
    .filter(r =>
      availableKeys.has(rowKey(r)) &&
      state.selectedGeographies.includes(rowKey(r))
    )
    .sort((a, b) =>
      geographyLabel(a).localeCompare(
        geographyLabel(b),
        undefined,
        { sensitivity: "base" }
      )
    );
}

function updateGeographySelectionAfterFiltersChange() {
  const availableKeys = new Set(
    getAvailableGeographies().map(rowKey)
  );

  state.selectedGeographies =
    state.selectedGeographies.filter(key =>
      availableKeys.has(key)
    );
}

function updateCountrySelectionAfterContinentsChange() {
  const availableCountries = new Set(
    getCountriesForSelectedContinents()
  );

  state.selectedCountries =
    state.selectedCountries.filter(country =>
      availableCountries.has(country)
    );
}

function renderSelectors() {
  renderContinentMenu();
  renderCountryMenu();
  renderGeoMenu();
}

function renderContinentMenu() {
  const menu = $("continent-menu");
  const continents = getAllContinents();
  const selected = new Set(
    state.selectedContinents
  );

  if (!continents.length) {
    menu.innerHTML =
      `<div class="picker-item">No continents available.</div>`;

    updatePickerButton(
      "continent-picker-button",
      [],
      [],
      "continents"
    );

    return;
  }

  menu.innerHTML = `
    <div class="picker-actions">
      <button
        type="button"
        data-action="select-all"
        data-filter="continent"
      >
        Select all
      </button>
      <button
        type="button"
        data-action="select-none"
        data-filter="continent"
      >
        Select none
      </button>
    </div>

    ${continents.map(continent => `
      <label class="picker-item">
        <input
          type="checkbox"
          data-continent="${escapeHtml(continent)}"
          ${selected.has(continent) ? "checked" : ""}
        >
        <span>${escapeHtml(continent)}</span>
      </label>
    `).join("")}
  `;

  updatePickerButton(
    "continent-picker-button",
    state.selectedContinents,
    continents,
    "continents"
  );
}

function renderCountryMenu() {
  const menu = $("country-menu");

  const countries =
    getCountriesForSelectedContinents();

  const selected = new Set(
    state.selectedCountries
  );

  if (!countries.length) {
    menu.innerHTML =
      `<div class="picker-item">No countries match the selected continents.</div>`;

    updatePickerButton(
      "country-picker-button",
      [],
      [],
      "countries"
    );

    return;
  }

  menu.innerHTML = `
    <div class="picker-actions">
      <button
        type="button"
        data-action="select-all"
        data-filter="country"
      >
        Select all
      </button>
      <button
        type="button"
        data-action="select-none"
        data-filter="country"
      >
        Select none
      </button>
    </div>

    ${countries.map(country => `
      <label class="picker-item">
        <input
          type="checkbox"
          data-country="${escapeHtml(country)}"
          ${selected.has(country) ? "checked" : ""}
        >
        <span>${escapeHtml(country)}</span>
      </label>
    `).join("")}
  `;

  updatePickerButton(
    "country-picker-button",
    state.selectedCountries,
    countries,
    "countries"
  );
}

function renderGeoMenu() {
  const menu = $("geo-menu");
  const options = getAvailableGeographies();
  const selected = new Set(
    state.selectedGeographies
  );

  if (!options.length) {
    menu.innerHTML =
      `<div class="picker-item">No geographies match the current filters.</div>`;

    updatePickerButton(
      "geo-picker-button",
      [],
      [],
      "geographies"
    );

    return;
  }

  menu.innerHTML = `
    <div class="picker-actions">
      <button
        type="button"
        data-action="select-all"
        data-filter="geo"
      >
        Select all
      </button>
      <button
        type="button"
        data-action="select-none"
        data-filter="geo"
      >
        Select none
      </button>
    </div>

    ${options.map(r => {
      const key = rowKey(r);

      return `
        <label class="picker-item">
          <input
            type="checkbox"
            data-geo-key="${escapeHtml(key)}"
            ${selected.has(key) ? "checked" : ""}
          >
          <span>${escapeHtml(geographyLabel(r))}</span>
        </label>
      `;
    }).join("")}
  `;

  updatePickerButton(
    "geo-picker-button",
    state.selectedGeographies,
    options.map(rowKey),
    "geographies"
  );
}

function updatePickerButton(
  buttonId,
  selected,
  available,
  label
) {
  const button = $(buttonId);

  if (!available.length) {
    button.textContent = `Select ${label}`;
    return;
  }

  if (selected.length === available.length) {
    button.textContent =
      `All ${label} selected`;
  } else if (!selected.length) {
    button.textContent =
      `No ${label} selected`;
  } else {
    button.textContent =
      `${selected.length} ${label} selected`;
  }
}

function getFilteredRowsForTrend() {
  const selectedKeys = new Set(
    state.selectedGeographies
  );

  return state.rows.filter(r =>
    selectedKeys.has(rowKey(r))
  );
}

function getRangeCutoff() {
  if (state.range === "all") {
    return null;
  }

  const days = Number(state.range);

  const end = new Date(
    latestDate() + "T00:00:00"
  );

  end.setDate(
    end.getDate() - days + 1
  );

  return end.toISOString().slice(0, 10);
}

function aggregateRowsByDate(rows) {
  const byDate = new Map();

  for (const row of rows) {
    if (
      !Number.isFinite(Number(row.members)) ||
      !Number.isFinite(Number(row.annualized_endowments))
    ) {
      continue;
    }

    if (!byDate.has(row.date)) {
      byDate.set(row.date, {
        date: row.date,
        members: 0,
        annualizedEndowments: 0
      });
    }

    const aggregate = byDate.get(row.date);

    aggregate.members += Number(row.members);
    aggregate.annualizedEndowments +=
      Number(row.annualized_endowments);
  }

  return [...byDate.values()]
    .sort((a, b) =>
      a.date.localeCompare(b.date)
    )
    .map(row => ({
      date: row.date,
      members: row.members,
      annualizedEndowments:
        row.annualizedEndowments,
      rate:
        row.members > 0
          ? row.annualizedEndowments / row.members
          : null
    }));
}

function getSelectionDescription() {
  const geographyCount =
    state.selectedGeographies.length;

  if (!geographyCount) {
    return "No geographies selected.";
  }

  const allAvailable =
    getAvailableGeographies();

  if (
    allAvailable.length &&
    geographyCount === allAvailable.length
  ) {
    const continentCount =
      state.selectedContinents.length;

    const allContinents =
      getAllContinents();

    const countryCount =
      state.selectedCountries.length;

    const allCountries =
      getCountriesForSelectedContinents();

    if (
      continentCount === allContinents.length &&
      countryCount === allCountries.length
    ) {
      return "All geographies";
    }

    if (continentCount === 1) {
      const continent =
        state.selectedContinents[0];

      if (countryCount === allCountries.length) {
        return continent;
      }
    }

    if (countryCount === 1) {
      return state.selectedCountries[0];
    }
  }

  return `${geographyCount} selected geographies`;
}

function renderTrend() {
  const selectedRows =
    getFilteredRowsForTrend();

  const latest = latestDate();

  if (!selectedRows.length) {
    Plotly.newPlot(
      "trend-chart",
      [],
      {
        margin: {
          l: 55,
          r: 20,
          t: 30,
          b: 50
        },
        xaxis: {
          visible: false
        },
        yaxis: {
          visible: false
        },
        annotations: [{
          text:
            "Select one or more geographies to display the trend.",
          showarrow: false,
          font: {
            size: 15,
            color: "#66717d"
          }
        }]
      },
      {
        responsive: true,
        displaylogo: false
      }
    );

    $("trend-status").textContent =
      latest
        ? `Latest data: ${formatDate(latest)}.`
        : "No trend data available.";

    renderTable([]);

    return;
  }

  const cutoff =
    getRangeCutoff();

  const rowsForChart =
    selectedRows.filter(r =>
      !cutoff || r.date >= cutoff
    );

  const aggregate =
    aggregateRowsByDate(rowsForChart);

  const selectedDescription =
    getSelectionDescription();

  const trace = {
    x: aggregate.map(r => r.date),
    y: aggregate.map(r => r.rate),
    type: "scatter",
    mode: "lines",
    name: selectedDescription,
    line: {
      width: 3
    },
    hovertemplate:
      "%{x|%b %-d, %Y}<br>" +
      "%{y:.3f} endowments/member" +
      "<extra></extra>"
  };

  const layout = {
    margin: {
      l: 65,
      r: 20,
      t: 25,
      b: 55
    },

    paper_bgcolor: "white",
    plot_bgcolor: "white",

    hovermode: "x unified",

    showlegend: false,

    xaxis: {
      title: "",
      gridcolor: "#edf0f3",
      linecolor: "#dfe3e8"
    },

    yaxis: {
      title:
        "Annualized endowments/member",
      gridcolor: "#edf0f3",
      zeroline: false,
      rangemode: "tozero"
    },

    font: {
      family:
        "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
      color: "#17202a"
    }
  };

  Plotly.newPlot(
    "trend-chart",
    [trace],
    layout,
    {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: [
        "lasso2d",
        "select2d"
      ]
    }
  );

  $("trend-status").textContent =
    `${selectedDescription} · ` +
    `${state.selectedGeographies.length.toLocaleString()} geographies aggregated · ` +
    `Data through ${formatDate(latest)}.`;

  renderTable(
    getSelectedGeographies()
  );
}

function renderTable(rows) {
  const body =
    $("comparison-table").querySelector("tbody");

  if (!rows.length) {
    body.innerHTML =
      `<tr>
        <td colspan="6">
          Select one or more geographies to compare.
        </td>
      </tr>`;

    return;
  }

  const latest = latestDate();

  const latestByKey = new Map();

  rows
    .filter(r => r.date === latest)
    .forEach(r =>
      latestByKey.set(rowKey(r), r)
    );

  body.innerHTML =
    [...latestByKey.values()]
      .sort((a, b) =>
        geographyLabel(a).localeCompare(
          geographyLabel(b)
        )
      )
      .map(r => `
        <tr>
          <td>
            <strong>
              ${escapeHtml(geographyLabel(r))}
            </strong>
          </td>

          <td>
            ${escapeHtml(r.type)}
          </td>

          <td>
            ${escapeHtml(r.continent)}
          </td>

          <td>
            ${escapeHtml(r.country)}
          </td>

          <td class="rate">
            ${formatRate(r.rate)}
          </td>

          <td>
            ${escapeHtml(formatDate(r.date))}
          </td>
        </tr>
      `)
      .join("");
}

function loadMaps() {
  const world = $("world-map");
  const us = $("us-map");

  if (state.urls.countries) {
    world.innerHTML = `
      <iframe
        src="${escapeHtml(state.urls.countries)}"
        title="Worldwide temple attendance map"
        loading="lazy"
      ></iframe>
    `;
  } else {
    world.textContent =
      "Worldwide map URL unavailable.";
  }

  if (state.urls.us) {
    us.innerHTML = `
      <iframe
        src="${escapeHtml(state.urls.us)}"
        title="U.S. temple attendance map"
        loading="lazy"
      ></iframe>
    `;
  } else {
    us.textContent =
      "U.S. map URL unavailable.";
  }
}

function selectAllContinents() {
  state.selectedContinents =
    getAllContinents();

  state.selectedCountries =
    getCountriesForSelectedContinents();

  state.selectedGeographies =
    getAvailableGeographies().map(rowKey);

  renderSelectors();
  renderTrend();
}

function selectNoneContinents() {
  state.selectedContinents = [];
  state.selectedCountries = [];
  state.selectedGeographies = [];

  renderSelectors();
  renderTrend();
}

function selectAllCountries() {
  state.selectedCountries =
    getCountriesForSelectedContinents();

  state.selectedGeographies =
    getAvailableGeographies().map(rowKey);

  renderSelectors();
  renderTrend();
}

function selectNoneCountries() {
  state.selectedCountries = [];
  state.selectedGeographies = [];

  renderSelectors();
  renderTrend();
}

function selectAllGeographies() {
  state.selectedGeographies =
    getAvailableGeographies().map(rowKey);

  renderGeoMenu();
  renderTrend();
}

function selectNoneGeographies() {
  state.selectedGeographies = [];

  renderGeoMenu();
  renderTrend();
}

function bindEvents() {
  $("continent-picker-button")
    .addEventListener("click", () => {
      const menu =
        $("continent-menu");

      menu.hidden = !menu.hidden;
    });

  $("country-picker-button")
    .addEventListener("click", () => {
      const menu =
        $("country-menu");

      menu.hidden = !menu.hidden;
    });

  $("geo-picker-button")
    .addEventListener("click", () => {
      const menu =
        $("geo-menu");

      menu.hidden = !menu.hidden;
    });

  document.addEventListener("click", e => {
    if (!$("continent-picker").contains(e.target)) {
      $("continent-menu").hidden = true;
    }

    if (!$("country-picker").contains(e.target)) {
      $("country-menu").hidden = true;
    }

    if (!$("geo-picker").contains(e.target)) {
      $("geo-menu").hidden = true;
    }
  });

  $("continent-menu")
    .addEventListener("click", e => {
      const action =
        e.target.dataset.action;

      if (action === "select-all") {
        e.preventDefault();
        selectAllContinents();
        return;
      }

      if (action === "select-none") {
        e.preventDefault();
        selectNoneContinents();
      }
    });

  $("continent-menu")
    .addEventListener("change", e => {
      if (
        !e.target.matches(
          "input[data-continent]"
        )
      ) {
        return;
      }

      const continent =
        e.target.dataset.continent;

      if (e.target.checked) {
        if (
          !state.selectedContinents
            .includes(continent)
        ) {
          state.selectedContinents.push(
            continent
          );
        }
      } else {
        state.selectedContinents =
          state.selectedContinents.filter(
            x => x !== continent
          );
      }

      updateCountrySelectionAfterContinentsChange();
      updateGeographySelectionAfterFiltersChange();

      renderSelectors();
      renderTrend();
    });

  $("country-menu")
    .addEventListener("click", e => {
      const action =
        e.target.dataset.action;

      if (action === "select-all") {
        e.preventDefault();
        selectAllCountries();
        return;
      }

      if (action === "select-none") {
        e.preventDefault();
        selectNoneCountries();
      }
    });

  $("country-menu")
    .addEventListener("change", e => {
      if (
        !e.target.matches(
          "input[data-country]"
        )
      ) {
        return;
      }

      const country =
        e.target.dataset.country;

      if (e.target.checked) {
        if (
          !state.selectedCountries
            .includes(country)
        ) {
          state.selectedCountries.push(
            country
          );
        }
      } else {
        state.selectedCountries =
          state.selectedCountries.filter(
            x => x !== country
          );
      }

      updateGeographySelectionAfterFiltersChange();

      renderSelectors();
      renderTrend();
    });

  $("geo-menu")
    .addEventListener("click", e => {
      const action =
        e.target.dataset.action;

      if (action === "select-all") {
        e.preventDefault();
        selectAllGeographies();
        return;
      }

      if (action === "select-none") {
        e.preventDefault();
        selectNoneGeographies();
      }
    });

  $("geo-menu")
    .addEventListener("change", e => {
      if (
        !e.target.matches(
          "input[data-geo-key]"
        )
      ) {
        return;
      }

      const key =
        e.target.dataset.geoKey;

      if (e.target.checked) {
        if (
          !state.selectedGeographies
            .includes(key)
        ) {
          state.selectedGeographies.push(
            key
          );
        }
      } else {
        state.selectedGeographies =
          state.selectedGeographies.filter(
            x => x !== key
          );
      }

      renderGeoMenu();
      renderTrend();
    });

  $("range-buttons")
    .addEventListener("click", e => {
      const range =
        e.target.dataset.range;

      if (!range) {
        return;
      }

      state.range = range;

      document
        .querySelectorAll(
          "#range-buttons button"
        )
        .forEach(button => {
          button.classList.toggle(
            "active",
            button.dataset.range === range
          );
        });

      renderTrend();
    });
}

async function load() {
  try {
    const [
      trendResponse,
      urlsResponse
    ] = await Promise.all([
      fetch(
        TREND_URL,
        { cache: "no-store" }
      ),
      fetch(
        URLS_URL,
        { cache: "no-store" }
      )
    ]);

    if (!trendResponse.ok) {
      throw new Error(
        `Trend data returned ${trendResponse.status}`
      );
    }

    if (!urlsResponse.ok) {
      throw new Error(
        `Datawrapper URL data returned ${urlsResponse.status}`
      );
    }

    state.rows =
      await trendResponse.json();

    state.urls =
      await urlsResponse.json();

    /*
     * Default state:
     * everything is selected.
     */
    state.selectedContinents =
      getAllContinents();

    state.selectedCountries =
      getCountriesForSelectedContinents();

    state.selectedGeographies =
      getAvailableGeographies()
        .map(rowKey);

    const latest =
      latestDate();

    $("freshness").textContent =
      latest
        ? `Data through ${formatDate(latest)} · ` +
          `${state.rows.length.toLocaleString()} trend observations`
        : "No trend data available.";

    loadMaps();
    renderSelectors();
    renderTrend();

  } catch (err) {
    console.error(err);

    $("freshness").textContent =
      "Unable to load current data.";

    $("trend-status").textContent =
      `Dashboard error: ${err.message}`;
  }
}

bindEvents();
load();
