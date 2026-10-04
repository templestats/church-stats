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
  }[c]);
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
    a.localeCompare(b, undefined, {
      sensitivity: "base"
    })
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

  return state.rows.filter(
    r => r.date === latest
  );
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

/*
 * Countries shown in the country picker are controlled
 * by the currently selected continents.
 *
 * Importantly, changing continents does NOT erase
 * country selections. Countries outside the current
 * continent filter simply become inactive.
 */
function getAvailableCountries() {
  return uniqueSorted(
    state.rows
      .filter(r =>
        state.selectedContinents.includes(r.continent)
      )
      .map(r => r.country)
  );
}

/*
 * All current geographies, before applying the
 * continent/country filters.
 *
 * This is what lets geography selections persist
 * while becoming temporarily inactive.
 */
function getAllCurrentGeographies() {
  return getCurrentRows().sort((a, b) =>
    geographyLabel(a).localeCompare(
      geographyLabel(b),
      undefined,
      { sensitivity: "base" }
    )
  );
}

/*
 * A geography is ACTIVE when it passes the continent
 * and country filters.
 *
 * It is still CHECKED if the user selected it previously,
 * even if it is currently inactive.
 */
function isGeographyActive(r) {
  return (
    state.selectedContinents.includes(r.continent) &&
    state.selectedCountries.includes(r.country)
  );
}

function getActiveSelectedGeographies() {
  return getAllCurrentGeographies().filter(r =>
    isGeographyActive(r) &&
    state.selectedGeographies.includes(rowKey(r))
  );
}

function getActiveGeographyKeys() {
  return new Set(
    getActiveSelectedGeographies().map(rowKey)
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
      >Select all</button>

      <button
        type="button"
        data-action="select-none"
        data-filter="continent"
      >Select none</button>
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
  const countries = getAllCountries();

  const selected = new Set(
    state.selectedCountries
  );

  if (!countries.length) {
    menu.innerHTML =
      `<div class="picker-item">No countries available.</div>`;

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
      >Select all</button>

      <button
        type="button"
        data-action="select-none"
        data-filter="country"
      >Select none</button>
    </div>

    ${countries.map(country => {
      const active =
        state.selectedContinents.length > 0 &&
        state.rows.some(r =>
          r.country === country &&
          state.selectedContinents.includes(r.continent)
        );

      return `
        <label
          class="picker-item${active ? "" : " picker-item-inactive"}"
        >
          <input
            type="checkbox"
            data-country="${escapeHtml(country)}"
            ${selected.has(country) ? "checked" : ""}
            ${active ? "" : "disabled"}
          >
          <span>${escapeHtml(country)}</span>
        </label>
      `;
    }).join("")}
  `;

  updatePickerButton(
    "country-picker-button",
    state.selectedCountries.filter(
      c => countries.includes(c)
    ),
    countries,
    "countries"
  );
}

function renderGeoMenu() {
  const menu = $("geo-menu");

  const options =
    getAllCurrentGeographies();

  const selected = new Set(
    state.selectedGeographies
  );

  if (!options.length) {
    menu.innerHTML =
      `<div class="picker-item">No geographies available.</div>`;

    updatePickerButton(
      "geo-picker-button",
      [],
      [],
      "geographies"
    );

    return;
  }

  const activeKeys =
    getActiveGeographyKeys();

  menu.innerHTML = `
    <div class="picker-actions">
      <button
        type="button"
        data-action="select-all"
        data-filter="geo"
      >Select all</button>

      <button
        type="button"
        data-action="select-none"
        data-filter="geo"
      >Select none</button>
    </div>

    ${options.map(r => {
      const key = rowKey(r);
      const checked = selected.has(key);
      const active = activeKeys.has(key) || !checked
        ? isGeographyActive(r)
        : isGeographyActive(r);

      return `
        <label
          class="picker-item${active ? "" : " picker-item-inactive"}"
        >
          <input
            type="checkbox"
            data-geo-key="${escapeHtml(key)}"
            ${checked ? "checked" : ""}
            ${active ? "" : "disabled"}
          >
          <span>${escapeHtml(geographyLabel(r))}</span>
        </label>
      `;
    }).join("")}
  `;

  /*
   * The button describes the number of CHECKED
   * geographies among all available geographies,
   * not merely the active ones.
   */
  updatePickerButton(
    "geo-picker-button",
    state.selectedGeographies.filter(
      key => options.some(r => rowKey(r) === key)
    ),
    options.map(rowKey),
    "geographies"
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

/*
 * Aggregate the selected geographies mathematically.
 *
 * We DO NOT average the individual rates.
 *
 * Correct calculation:
 *
 *   sum(annualized endowments)
 *   --------------------------
 *       sum(members)
 *
 * This produces the combined annualized
 * endowments/member rate.
 */
function aggregateRowsByDate(rows) {
  const byDate = new Map();

  for (const row of rows) {
    const members =
      Number(row.members);

    const annualizedEndowments =
      Number(row.annualized_endowments);

    if (
      !Number.isFinite(members) ||
      !Number.isFinite(annualizedEndowments)
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

    const aggregate =
      byDate.get(row.date);

    aggregate.members += members;
    aggregate.annualizedEndowments +=
      annualizedEndowments;
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
          ? row.annualizedEndowments /
            row.members
          : null
    }));
}

function getSelectionDescription() {
  const active =
    getActiveSelectedGeographies();

  if (!active.length) {
    return "No geographies selected";
  }

  const allCurrent =
    getAllCurrentGeographies();

  /*
   * If all currently active geographies are checked,
   * give the user a useful description based on the
   * higher-level filters.
   */
  const activeKeys =
    new Set(active.map(rowKey));

  const allActive =
    allCurrent.filter(isGeographyActive);

  const allActiveKeys =
    new Set(allActive.map(rowKey));

  const everythingActiveIsSelected =
    activeKeys.size === allActiveKeys.size &&
    [...allActiveKeys].every(key =>
      activeKeys.has(key)
    );

  if (everythingActiveIsSelected) {
    const allContinents =
      getAllContinents();

    const allCountries =
      getAllCountries();

    if (
      state.selectedContinents.length ===
        allContinents.length &&
      state.selectedCountries.length ===
        allCountries.length
    ) {
      return "All geographies";
    }

    if (
      state.selectedContinents.length === 1 &&
      state.selectedCountries.length ===
        getAllCountries().filter(country =>
          state.rows.some(r =>
            r.country === country &&
            r.continent ===
              state.selectedContinents[0]
          )
        ).length
    ) {
      return state.selectedContinents[0];
    }

    if (
      state.selectedCountries.length === 1
    ) {
      return state.selectedCountries[0];
    }
  }

  return `${active.length} selected geographies`;
}

function renderTrend() {
  const activeSelected =
    getActiveSelectedGeographies();

  const latest =
    latestDate();

  if (!activeSelected.length) {
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
            "Select one or more active geographies to display the trend.",
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

  const selectedKeys =
    new Set(
      activeSelected.map(rowKey)
    );

  const selectedRows =
    state.rows.filter(r =>
      selectedKeys.has(rowKey(r))
    );

  const cutoff =
    getRangeCutoff();

  const rowsForChart =
    selectedRows.filter(r =>
      !cutoff || r.date >= cutoff
    );

  const aggregate =
    aggregateRowsByDate(rowsForChart);

  const description =
    getSelectionDescription();

  const trace = {
    x: aggregate.map(r => r.date),

    y: aggregate.map(r => r.rate),

    type: "scatter",

    mode: "lines",

    name: description,

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
    `${description} · ` +
    `${activeSelected.length.toLocaleString()} geographies aggregated · ` +
    `Data through ${formatDate(latest)}.`;

  renderTable(activeSelected);
}

function renderTable(rows) {
  const body =
    $("comparison-table")
      .querySelector("tbody");

  if (!rows.length) {
    body.innerHTML =
      `<tr>
        <td colspan="6">
          Select one or more active geographies to compare.
        </td>
      </tr>`;

    return;
  }

  const latest =
    latestDate();

  const latestByKey =
    new Map();

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
              ${escapeHtml(
                geographyLabel(r)
              )}
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
            ${escapeHtml(
              formatDate(r.date)
            )}
          </td>
        </tr>
      `)
      .join("");
}

function loadMaps() {
  const world =
    $("world-map");

  const us =
    $("us-map");

  if (state.urls.countries) {
    world.innerHTML = `
      <iframe
        src="${escapeHtml(
          state.urls.countries
        )}"
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
        src="${escapeHtml(
          state.urls.us
        )}"
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

  /*
   * Do NOT modify countries or geographies.
   *
   * They retain their previous checked state.
   */
  renderSelectors();
  renderTrend();
}

function selectNoneContinents() {
  /*
   * Do NOT modify countries or geographies.
   *
   * Everything simply becomes inactive because no
   * continent is currently in scope.
   */
  state.selectedContinents = [];

  renderSelectors();
  renderTrend();
}

function selectAllCountries() {
  /*
   * Select all countries globally.
   * Continent filtering still determines which
   * countries are currently active.
   */
  state.selectedCountries =
    getAllCountries();

  renderSelectors();
  renderTrend();
}

function selectNoneCountries() {
  /*
   * Do NOT modify continent or geography selections.
   */
  state.selectedCountries = [];

  renderSelectors();
  renderTrend();
}

function selectAllGeographies() {
  /*
   * Select every geography, including those that
   * are currently inactive because of other filters.
   *
   * This means changing the continent filter later
   * will automatically reveal those geographies.
   */
  state.selectedGeographies =
    getAllCurrentGeographies()
      .map(rowKey);

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
    if (
      !$("continent-picker")
        .contains(e.target)
    ) {
      $("continent-menu").hidden = true;
    }

    if (
      !$("country-picker")
        .contains(e.target)
    ) {
      $("country-menu").hidden = true;
    }

    if (
      !$("geo-picker")
        .contains(e.target)
    ) {
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
     * Initial state:
     *
     * - Every continent checked
     * - Every country checked
     * - Every geography checked
     *
     * These remain independent after initialization.
     */
    state.selectedContinents =
      getAllContinents();

    state.selectedCountries =
      getAllCountries();

    state.selectedGeographies =
      getAllCurrentGeographies()
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
