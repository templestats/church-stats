from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import pycountry
import requests
from bs4 import BeautifulSoup


# ============================================================
# SOURCE URLS
# ============================================================

CHURCH_BASE = (
    "https://www.churchofjesuschrist.org/learn/facts-statistics/"
)

NEWSROOM_BASE = (
    "https://newsroom.churchofjesuschrist.org/"
    "facts-and-statistics/state/"
)

GEOGRAPHY_INDEX_URL = (
    "https://newsroom.churchofjesuschrist.org/"
    "facts-and-statistics/state/california"
)

UK_COUNTRY_BASE = (
    "https://news-uk.churchofjesuschrist.org/"
    "facts-and-statistics/country/"
)

TRACKER_URL = (
    "https://fullerconsideration.com/TempleTracker/"
)

TRACKER_HISTORY_URL = (
    "https://fullerconsideration.com/TempleTracker/endowments.php"
)

WORLD_STATS_URL = CHURCH_BASE + "?lang=eng"

WEEKS_PER_YEAR = 52

# Membership figures from the UK-English country pages are treated
# as 2025 figures based on validation against the other country source.
MEMBERSHIP_YEAR = "2025"

# Increment whenever the cache format or source logic changes.
MEMBERSHIP_CACHE_VERSION = "4"

ELIGIBLE_CHILDREN_OF_RECORD = 94_006
ELIGIBLE_CONVERTS = 385_490


# ============================================================
# DATAWRAPPER
# ============================================================

DATAWRAPPER_API_BASE = "https://api.datawrapper.de/v3"

# Datawrapper credentials and chart IDs are intentionally read
# from environment variables rather than stored in source code.
#
# DATAWRAPPER_TOKEN
# DATAWRAPPER_US_CHART_ID
# DATAWRAPPER_COUNTRIES_CHART_ID
# DATAWRAPPER_HISTORICAL_CHART_ID


# ============================================================
# U.S. STATES
# ============================================================

STATES = [
    ("Alabama", "AL"),
    ("Alaska", "AK"),
    ("Arizona", "AZ"),
    ("Arkansas", "AR"),
    ("California", "CA"),
    ("Colorado", "CO"),
    ("Connecticut", "CT"),
    ("Delaware", "DE"),
    ("Florida", "FL"),
    ("Georgia", "GA"),
    ("Hawaii", "HI"),
    ("Idaho", "ID"),
    ("Illinois", "IL"),
    ("Indiana", "IN"),
    ("Iowa", "IA"),
    ("Kansas", "KS"),
    ("Kentucky", "KY"),
    ("Louisiana", "LA"),
    ("Maine", "ME"),
    ("Maryland", "MD"),
    ("Massachusetts", "MA"),
    ("Michigan", "MI"),
    ("Minnesota", "MN"),
    ("Mississippi", "MS"),
    ("Missouri", "MO"),
    ("Montana", "MT"),
    ("Nebraska", "NE"),
    ("Nevada", "NV"),
    ("New Hampshire", "NH"),
    ("New Jersey", "NJ"),
    ("New Mexico", "NM"),
    ("New York", "NY"),
    ("North Carolina", "NC"),
    ("North Dakota", "ND"),
    ("Ohio", "OH"),
    ("Oklahoma", "OK"),
    ("Oregon", "OR"),
    ("Pennsylvania", "PA"),
    ("Rhode Island", "RI"),
    ("South Carolina", "SC"),
    ("South Dakota", "SD"),
    ("Tennessee", "TN"),
    ("Texas", "TX"),
    ("Utah", "UT"),
    ("Vermont", "VT"),
    ("Virginia", "VA"),
    ("Washington", "WA"),
    ("West Virginia", "WV"),
    ("Wisconsin", "WI"),
    ("Wyoming", "WY"),
]


# ============================================================
# TEMPLE LOCATION OVERRIDES
# ============================================================

TEMPLE_LOCATION_OVERRIDES = {
    "Calgary Alberta Temple": ("country", "Canada"),
    "London England Temple": ("country", "United Kingdom"),
    "Vancouver British Columbia Temple": ("country", "Canada"),
    "Montreal Quebec Temple": ("country", "Canada"),
    "Washington D.C. Temple": ("state", "Maryland"),
    "Hong Kong China Temple": ("country", "Hong Kong"),
    "Provo City Center Temple": ("state", "Utah"),
    "Cardston Alberta Temple": ("country", "Canada"),
    "Papeete Tahiti Temple": ("country", "French Polynesia"),
    "Preston England Temple": ("country", "United Kingdom"),
    "Lima Peru Los Olivos Temple": ("country", "Peru"),
    "Edmonton Alberta Temple": ("country", "Canada"),
    "Toronto Ontario Temple": ("country", "Canada"),
    "Winnipeg Manitoba Temple": ("country", "Canada"),
    "Halifax Nova Scotia Temple": ("country", "Canada"),
    "Regina Saskatchewan Temple": ("country", "Canada"),
    "Praia Cape Verde Temple": ("country", "Cape Verde"),
}


# ============================================================
# COUNTRY NAME / ISO OVERRIDES
# ============================================================

COUNTRY_OVERRIDES = {
    "Korea": ("South Korea", "KOR"),
    "South Korea": ("South Korea", "KOR"),
    "Taiwan": ("Taiwan", "TWN"),
    "Hong Kong": ("Hong Kong", "HKG"),
    "Ivory Coast": ("Ivory Coast", "CIV"),
    "Cote d'Ivoire": ("Ivory Coast", "CIV"),
    "Russia": ("Russia", "RUS"),
    "Czech Republic": ("Czech Republic", "CZE"),
    "Moldova": ("Moldova", "MDA"),
    "Vietnam": ("Vietnam", "VNM"),
    "Bolivia": ("Bolivia", "BOL"),
    "Venezuela": ("Venezuela", "VEN"),
    "Iran": ("Iran", "IRN"),
    "Syria": ("Syria", "SYR"),
    "Laos": ("Laos", "LAO"),
    "Tanzania": ("Tanzania", "TZA"),
    "Turkey": ("Turkey", "TUR"),
    "Congo": ("Congo", "COG"),
    "Democratic Republic of the Congo": (
        "Democratic Republic of the Congo",
        "COD",
    ),
    "Republic of the Congo": (
        "Republic of the Congo",
        "COG",
    ),
    "Puerto Rico": ("Puerto Rico", "PRI"),
    "Guam": ("Guam", "GUM"),
    "American Samoa": ("American Samoa", "ASM"),
    "Canada": ("Canada", "CAN"),
    "French Polynesia": ("French Polynesia", "PYF"),
    "United Kingdom": ("United Kingdom", "GBR"),
    "Peru": ("Peru", "PER"),
    "Cape Verde": ("Cape Verde", "CPV"),
}


# ============================================================
# CONTINENT MAPPING
# ============================================================

COUNTRY_CONTINENTS = {
    "Australia": "Oceania",
    "Brazil": "South America",
    "Canada": "North America",
    "Cape Verde": "Africa",
    "Chile": "South America",
    "Colombia": "South America",
    "Costa Rica": "North America",
    "Czech Republic": "Europe",
    "Democratic Republic of the Congo": "Africa",
    "Denmark": "Europe",
    "Dominican Republic": "North America",
    "Ecuador": "South America",
    "El Salvador": "North America",
    "England": "Europe",
    "Fiji": "Oceania",
    "Finland": "Europe",
    "France": "Europe",
    "French Polynesia": "Oceania",
    "Germany": "Europe",
    "Ghana": "Africa",
    "Guam": "Oceania",
    "Guatemala": "North America",
    "Haiti": "North America",
    "Hong Kong": "Asia",
    "Hungary": "Europe",
    "India": "Asia",
    "Indonesia": "Asia",
    "Ireland": "Europe",
    "Ivory Coast": "Africa",
    "Japan": "Asia",
    "Kenya": "Africa",
    "Kiribati": "Oceania",
    "Madagascar": "Africa",
    "Mexico": "North America",
    "Netherlands": "Europe",
    "New Zealand": "Oceania",
    "Nigeria": "Africa",
    "Panama": "North America",
    "Peru": "South America",
    "Philippines": "Asia",
    "Portugal": "Europe",
    "Puerto Rico": "North America",
    "Russia": "Europe",
    "Samoa": "Oceania",
    "Singapore": "Asia",
    "South Africa": "Africa",
    "South Korea": "Asia",
    "Spain": "Europe",
    "Sweden": "Europe",
    "Switzerland": "Europe",
    "Taiwan": "Asia",
    "Thailand": "Asia",
    "Tonga": "Oceania",
    "Ukraine": "Europe",
    "United Kingdom": "Europe",
    "United States": "North America",
    "Uruguay": "South America",
    "Vanuatu": "Oceania",
    "Venezuela": "South America",
    "Vietnam": "Asia",
    "Zambia": "Africa",
    "Zimbabwe": "Africa",
}


# ============================================================
# UK COUNTRY URL SLUG OVERRIDES
# ============================================================

COUNTRY_SLUG_OVERRIDES = {
    "Cape Verde": "cape-verde",
    "Ivory Coast": "cote-d-ivoire",
    "Cote d'Ivoire": "cote-d-ivoire",
    "Czech Republic": "czech-republic",
    "Democratic Republic of the Congo":
        "democratic-republic-of-the-congo",
    "Republic of the Congo": "republic-of-the-congo",
    "French Polynesia": "french-polynesia",
    "Hong Kong": "hong-kong",
    "South Korea": "south-korea",
    "United Kingdom": "united-kingdom",
    "United States": "united-states",
}


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass(frozen=True)
class Temple:
    name: str
    endowments: int
    living: int


@dataclass(frozen=True)
class DailyActivity:
    activity_date: date
    temple: str
    endowments: int
    living: int


@dataclass(frozen=True)
class Geography:
    scope: str
    name: str
    slug: str
    iso3: str = ""


@dataclass(frozen=True)
class MembershipPage:
    scope: str
    name: str
    url: str


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value: str) -> str:
    """Normalize whitespace in visible page text."""
    return re.sub(r"\s+", " ", value).strip()


def clean_url(value: str) -> str:
    """
    Return a plain URL.

    Defensive handling for accidental Markdown-style URLs.
    """
    value = str(value).strip()

    match = re.fullmatch(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        value,
    )

    if match:
        return match.group(2)

    return value


def normalize_name(value: str) -> str:
    """Normalize names for matching."""
    value = unicodedata.normalize("NFKD", value)

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )

    value = value.casefold()
    value = value.replace("&", "and")

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return clean_text(value)


def parse_count(value: str) -> int:
    """Convert a formatted numeric string into an integer."""
    digits = re.sub(
        r"[^0-9]",
        "",
        value,
    )

    if not digits:
        raise ValueError(
            f"Expected a numeric count, found {value!r}"
        )

    return int(digits)


def page_soup(
    session: requests.Session,
    url: str,
) -> BeautifulSoup:
    """Fetch a page and return parsed HTML."""
    url = clean_url(url)

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            f"Invalid URL scheme: {url!r}"
        )

    if not parsed.netloc:
        raise ValueError(
            f"Invalid URL: {url!r}"
        )

    response = session.get(
        url,
        timeout=40,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            )
        },
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser",
    )


# ============================================================
# FULLER CONSIDERATION TEMPLE DATA
# ============================================================

def parse_activity_date(value: str) -> date:
    """Parse the date formats used by Fuller Consideration."""
    value = clean_text(value)

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ValueError(
        f"Could not parse Fuller Consideration date: {value!r}"
    )


def scrape_full_history(
    session: requests.Session,
) -> list[DailyActivity]:
    """
    Scrape all dated temple activity from Fuller Consideration's
    endowments.php raw-data table.
    """
    soup = page_soup(
        session,
        TRACKER_HISTORY_URL,
    )

    found: dict[tuple[date, str], DailyActivity] = {}

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all(
                ["th", "td"],
                recursive=False,
            )

            if len(cells) < 8:
                continue

            values = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in cells
            ]

            if not date_pattern.fullmatch(values[0]):
                continue

            try:
                activity_date = parse_activity_date(
                    values[0]
                )

                name = clean_text(
                    cells[1].get_text(
                        " ",
                        strip=True,
                    )
                )

                if not name:
                    continue

                if name.endswith("*") or values[1].endswith("*"):
                    continue

                # Fuller columns:
                # Date, Temple, Weekday, Sessions, Capacity,
                # Endowments, Utilization, Living, Proxy, Male,
                # Female, Living Male, Living Female
                endowments = parse_count(values[5])
                living = parse_count(values[7])

            except (IndexError, ValueError):
                continue

            record = DailyActivity(
                activity_date=activity_date,
                temple=name,
                endowments=endowments,
                living=living,
            )

            key = (
                activity_date,
                name,
            )

            prior = found.get(key)

            if prior is not None and (
                prior.endowments != record.endowments
                or prior.living != record.living
            ):
                raise RuntimeError(
                    "Fuller Consideration returned conflicting rows for "
                    f"{name} on {activity_date}."
                )

            found[key] = record

    if not found:
        raise RuntimeError(
            "Could not find dated temple rows on "
            "Fuller Consideration's endowments.php."
        )

    return sorted(
        found.values(),
        key=lambda row: (
            row.activity_date,
            row.temple,
        ),
    )


# ============================================================
# GEOGRAPHY HELPERS
# ============================================================

def slugify(name: str) -> str:
    """Create a URL-style slug."""
    text = name.casefold()
    text = text.replace("&", "and")

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text,
    )

    return text.strip("-")


def country_url_slug(name: str) -> str:
    if name in COUNTRY_SLUG_OVERRIDES:
        return COUNTRY_SLUG_OVERRIDES[name]

    return slugify(name)


def country_iso3(name: str) -> str:
    """Return ISO-3 code for a country name."""
    if name in COUNTRY_OVERRIDES:
        return COUNTRY_OVERRIDES[name][1]

    target = normalize_name(name)

    for country in pycountry.countries:
        candidates = {
            normalize_name(country.name),
            normalize_name(
                getattr(
                    country,
                    "common_name",
                    "",
                )
            ),
            normalize_name(
                getattr(
                    country,
                    "official_name",
                    "",
                )
            ),
        }

        if target in candidates:
            return country.alpha_3

    return ""


def locate_temple(
    temple_name: str,
) -> Geography | None:
    """
    Determine the physical state/country where a temple is located.

    The physical location is used rather than the geography the temple
    serves.
    """
    if temple_name in TEMPLE_LOCATION_OVERRIDES:
        scope, location_name = (
            TEMPLE_LOCATION_OVERRIDES[temple_name]
        )

        if scope == "state":
            return Geography(
                scope="state",
                name=location_name,
                slug=slugify(location_name),
            )

        display_name, iso3 = (
            COUNTRY_OVERRIDES.get(
                location_name,
                (
                    location_name,
                    country_iso3(location_name),
                ),
            )
        )

        return Geography(
            scope="country",
            name=display_name,
            slug=slugify(display_name),
            iso3=iso3,
        )

    normalized = clean_text(
        temple_name.removesuffix(" Temple").rstrip("* ")
    ).casefold()

    # Check states first.
    for state_name, _ in sorted(
        STATES,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if normalized.endswith(state_name.casefold()):
            return Geography(
                scope="state",
                name=state_name,
                slug=slugify(state_name),
            )

    # Then countries.
    possible_countries: list[
        tuple[str, str, str]
    ] = []

    for country in pycountry.countries:
        possible_countries.append(
            (
                country.name,
                getattr(
                    country,
                    "common_name",
                    "",
                ),
                country.alpha_3,
            )
        )

        official_name = getattr(
            country,
            "official_name",
            "",
        )

        if official_name:
            possible_countries.append(
                (
                    official_name,
                    getattr(
                        country,
                        "common_name",
                        "",
                    ),
                    country.alpha_3,
                )
            )

    for override_name, (
        display_name,
        iso3,
    ) in COUNTRY_OVERRIDES.items():
        possible_countries.append(
            (
                override_name,
                display_name,
                iso3,
            )
        )

    possible_countries.sort(
        key=lambda item: len(item[0]),
        reverse=True,
    )

    seen: set[tuple[str, str]] = set()

    for candidate, display_name, iso3 in possible_countries:
        key = (
            candidate,
            iso3,
        )

        if key in seen:
            continue

        seen.add(key)

        if normalized.endswith(candidate.casefold()):
            if not display_name:
                display_name = candidate

            return Geography(
                scope="country",
                name=display_name,
                slug=slugify(display_name),
                iso3=iso3,
            )

    return None


# ============================================================
# MEMBERSHIP PAGE DISCOVERY
# ============================================================

def discover_state_membership_pages(
    session: requests.Session,
) -> dict[
    tuple[str, str],
    MembershipPage,
]:
    """
    Discover U.S. state pages from the Church's state index.
    """
    soup = page_soup(
        session,
        GEOGRAPHY_INDEX_URL,
    )

    discovered: dict[
        tuple[str, str],
        MembershipPage,
    ] = {}

    for link in soup.find_all(
        "a",
        href=True,
    ):
        label = clean_text(
            link.get_text(
                " ",
                strip=True,
            )
        )

        href = clean_url(
            link.get("href", "")
        )

        if not label or not href:
            continue

        absolute_url = urljoin(
            GEOGRAPHY_INDEX_URL,
            href,
        )

        parsed = urlparse(
            absolute_url
        )

        path = parsed.path.rstrip("/")

        if "/facts-and-statistics/state/" not in path:
            continue

        state_name = next(
            (
                state
                for state, _ in STATES
                if normalize_name(state)
                == normalize_name(label)
            ),
            None,
        )

        if not state_name:
            continue

        discovered[
            (
                "state",
                state_name,
            )
        ] = MembershipPage(
            scope="state",
            name=state_name,
            url=absolute_url,
        )

    return discovered


def build_membership_page_map(
    session: requests.Session,
    geographies: list[Geography],
) -> dict[
    tuple[str, str],
    MembershipPage,
]:
    """
    Build membership source pages.

    States:
        Discover from the Church state index.

    Countries:
        Use the UK-English Church country site directly.
    """
    state_pages = (
        discover_state_membership_pages(
            session
        )
    )

    result: dict[
        tuple[str, str],
        MembershipPage,
    ] = {}

    missing_states: list[str] = []

    for geography in geographies:
        key = (
            geography.scope,
            geography.name,
        )

        if geography.scope == "state":
            page = state_pages.get(key)

            if page is None:
                missing_states.append(
                    geography.name
                )
                continue

            result[key] = page

        elif geography.scope == "country":
            slug = country_url_slug(
                geography.name
            )

            url = (
                UK_COUNTRY_BASE
                + slug
            )

            result[key] = MembershipPage(
                scope="country",
                name=geography.name,
                url=url,
            )

    if missing_states:
        raise RuntimeError(
            "Could not resolve these U.S. state membership pages:\n  - "
            + "\n  - ".join(
                missing_states
            )
        )

    return result


# ============================================================
# MEMBERSHIP SCRAPING
# ============================================================

def scrape_membership(
    session: requests.Session,
    page: MembershipPage,
) -> tuple[int, str, str]:
    """
    Read the geography-specific membership count.
    """
    soup = page_soup(
        session,
        page.url,
    )

    text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    )

    worldwide_marker = re.search(
        r"\bWorldwide\s+Statistics\b",
        text,
        re.IGNORECASE,
    )

    if worldwide_marker:
        geography_text = text[
            :worldwide_marker.start()
        ]
    else:
        geography_text = text

    count: int | None = None

    match = re.search(
        r"([0-9][0-9,\u202f]*)\s+"
        r"Total\s+Church\s+Membership\b",
        geography_text,
        re.IGNORECASE,
    )

    if match:
        count = parse_count(
            match.group(1)
        )

    if count is None:
        match = re.search(
            r"Church\s+Membership\b\s+"
            r"([0-9][0-9,\u202f]*)",
            geography_text,
            re.IGNORECASE,
        )

        if match:
            count = parse_count(
                match.group(1)
            )

    if count is None:
        raise ValueError(
            "Could not find geography-specific Church Membership "
            f"on {page.url}"
        )

    if count < 1_000:
        raise ValueError(
            f"Suspicious Church Membership value "
            f"{count:,} on {page.url}. "
            "Refusing to cache it."
        )

    updated_match = re.search(
        r"Last Updated On\s+"
        r"([\w ,\u00a0]+\d{4})",
        geography_text,
        re.IGNORECASE,
    )

    updated = (
        updated_match.group(1).strip()
        if updated_match
        else ""
    )

    return (
        count,
        updated,
        page.url,
    )


def scrape_world_membership(
    session: requests.Session,
) -> int:
    """Read worldwide membership from the Church statistics page."""
    text = clean_text(
        page_soup(
            session,
            WORLD_STATS_URL,
        ).get_text(
            " ",
            strip=True,
        )
    )

    match = re.search(
        r"Total\s+Church\s+Membership\s+"
        r"([\d,\u202f]+)",
        text,
        re.IGNORECASE,
    )

    if not match:
        match = re.search(
            r"([\d,\u202f]+)\s+"
            r"Total\s+Church\s+Membership",
            text,
            re.IGNORECASE,
        )

    if not match:
        raise ValueError(
            "Could not read worldwide membership from "
            "the Church statistics page."
        )

    count = parse_count(
        match.group(1)
    )

    if count < 1_000_000:
        raise ValueError(
            f"Suspicious worldwide membership value "
            f"{count:,}. Refusing to use it."
        )

    return count


# ============================================================
# MEMBERSHIP CACHE
# ============================================================

def read_membership_cache(
    path: Path,
) -> dict[
    tuple[str, str, str],
    dict[str, str],
]:
    """
    Read only cache rows created by the current cache version.
    """
    if not path.exists():
        return {}

    with path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(
            csv.DictReader(handle)
        )

    cache: dict[
        tuple[str, str, str],
        dict[str, str],
    ] = {}

    for row in rows:
        if (
            row.get("cache_version")
            != MEMBERSHIP_CACHE_VERSION
        ):
            continue

        required = {
            "year",
            "scope",
            "name",
            "members",
            "published_update",
            "source_url",
            "scraped_at",
        }

        if not required.issubset(row):
            continue

        try:
            members = int(
                row["members"]
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        if members < 1_000:
            continue

        key = (
            row["year"],
            row["scope"],
            row["name"],
        )

        cache[key] = row

    return cache


def update_membership_cache(
    session: requests.Session,
    geographies: list[Geography],
    pages: dict[
        tuple[str, str],
        MembershipPage,
    ],
    cache_path: Path,
    year: str,
    force_refresh: bool,
) -> dict[
    tuple[str, str],
    int,
]:
    """
    Read cached membership or scrape missing/stale values.
    """
    cache = read_membership_cache(
        cache_path
    )

    updated_cache = dict(cache)

    result: dict[
        tuple[str, str],
        int,
    ] = {}

    for geography in geographies:
        key = (
            year,
            geography.scope,
            geography.name,
        )

        row = cache.get(key)

        if row and not force_refresh:
            count = int(
                row["members"]
            )

            if count < 1_000:
                raise ValueError(
                    f"Suspicious cached membership value "
                    f"{count:,} for {geography.name}"
                )

        else:
            page = pages[
                (
                    geography.scope,
                    geography.name,
                )
            ]

            count, updated, source = (
                scrape_membership(
                    session,
                    page,
                )
            )

            row = {
                "cache_version": (
                    MEMBERSHIP_CACHE_VERSION
                ),
                "year": year,
                "scope": geography.scope,
                "name": geography.name,
                "members": str(count),
                "published_update": updated,
                "source_url": source,
                "scraped_at": (
                    datetime.now()
                    .astimezone()
                    .isoformat(
                        timespec="seconds"
                    )
                ),
            }

            updated_cache[key] = row

        result[
            (
                geography.scope,
                geography.name,
            )
        ] = count

    cache_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fields = [
        "cache_version",
        "year",
        "scope",
        "name",
        "members",
        "published_update",
        "source_url",
        "scraped_at",
    ]

    with cache_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        writer.writeheader()
        writer.writerows(
            updated_cache.values()
        )

    return result


# ============================================================
# JSON / CSV HELPERS
# ============================================================

def write_json(
    path: Path,
    data: Any,
) -> None:
    """Write UTF-8 JSON."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            data,
            handle,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    """Write dictionaries to CSV."""
    if not rows:
        return

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# DATAWRAPPER API
# ============================================================

def datawrapper_headers(
    token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "TempleAttendanceResearch/1.0",
    }


def build_datawrapper_title(
    geography_label: str,
    window_start: date,
    window_end: date,
) -> str:
    """Build the current trailing-window chart title."""
    return (
        "Annualized Temple Endowment sessions attended per member of record, "
        f"by {geography_label} "
        f"({window_start:%b %-d, %Y} to {window_end:%b %-d, %Y})"
    )


def update_datawrapper_chart(
    session: requests.Session,
    token: str,
    chart_id: str,
    csv_path: Path,
    chart_name: str,
    title: str,
) -> str:
    """
    Upload CSV data to an existing Datawrapper chart,
    update its title, and publish it.
    """
    csv_data = csv_path.read_bytes()

    data_url = (
        f"{DATAWRAPPER_API_BASE}/charts/"
        f"{chart_id}/data"
    )

    response = session.put(
        data_url,
        headers={
            **datawrapper_headers(token),
            "Content-Type": "text/csv",
        },
        data=csv_data,
        timeout=40,
    )

    response.raise_for_status()

    metadata_url = (
        f"{DATAWRAPPER_API_BASE}/charts/"
        f"{chart_id}"
    )

    response = session.patch(
        metadata_url,
        headers={
            **datawrapper_headers(token),
            "Content-Type": "application/json",
        },
        json={
            "title": title,
        },
        timeout=40,
    )

    response.raise_for_status()

    publish_url = (
        f"{DATAWRAPPER_API_BASE}/charts/"
        f"{chart_id}/publish"
    )

    response = session.post(
        publish_url,
        headers=datawrapper_headers(token),
        timeout=60,
    )

    response.raise_for_status()

    public_url = ""

    try:
        payload = response.json()

        public_url = (
            payload.get("data", {})
            .get("publicUrl", "")
        )

    except ValueError:
        pass

    print(
        f"✓ Datawrapper {chart_name} chart updated "
        f"and published: {chart_id}"
    )

    if public_url:
        print(
            f"  Public URL: {public_url}"
        )

    return public_url


def update_datawrapper(
    session: requests.Session,
    output_dir: Path,
    window_start: date,
    window_end: date,
) -> None:
    """Update all three configured Datawrapper charts."""
    token = os.getenv("DATAWRAPPER_TOKEN")

    us_chart_id = os.getenv(
        "DATAWRAPPER_US_CHART_ID"
    )

    countries_chart_id = os.getenv(
        "DATAWRAPPER_COUNTRIES_CHART_ID"
    )

    historical_chart_id = os.getenv(
        "DATAWRAPPER_HISTORICAL_CHART_ID"
    )

    missing = []

    if not token:
        missing.append(
            "DATAWRAPPER_TOKEN"
        )

    if not us_chart_id:
        missing.append(
            "DATAWRAPPER_US_CHART_ID"
        )

    if not countries_chart_id:
        missing.append(
            "DATAWRAPPER_COUNTRIES_CHART_ID"
        )

    if not historical_chart_id:
        missing.append(
            "DATAWRAPPER_HISTORICAL_CHART_ID"
        )

    if missing:
        raise RuntimeError(
            "Missing Datawrapper environment variables: "
            + ", ".join(missing)
        )

    print()
    print("Updating Datawrapper charts...")

    us_url = update_datawrapper_chart(
        session=session,
        token=token,
        chart_id=us_chart_id,
        csv_path=output_dir / "datawrapper_us.csv",
        chart_name="U.S.",
        title=build_datawrapper_title(
            "state",
            window_start,
            window_end,
        ),
    )

    countries_url = update_datawrapper_chart(
        session=session,
        token=token,
        chart_id=countries_chart_id,
        csv_path=output_dir / "datawrapper_countries.csv",
        chart_name="countries",
        title=build_datawrapper_title(
            "country",
            window_start,
            window_end,
        ),
    )

    historical_url = update_datawrapper_chart(
        session=session,
        token=token,
        chart_id=historical_chart_id,
        csv_path=output_dir / "historical_summary.csv",
        chart_name="historical",
        title=(
            "Temple Endowment Attendance Trends, "
            "annualized trailing 7 days"
        ),
    )

    if not us_url:
        raise RuntimeError(
            "Datawrapper U.S. chart published successfully, "
            "but no public URL was returned."
        )

    if not countries_url:
        raise RuntimeError(
            "Datawrapper countries chart published successfully, "
            "but no public URL was returned."
        )

    if not historical_url:
        raise RuntimeError(
            "Datawrapper historical chart published successfully, "
            "but no public URL was returned."
        )

    datawrapper_urls = {
        "us": us_url,
        "countries": countries_url,
        "historical": historical_url,
    }

    write_json(
        output_dir / "datawrapper_urls.json",
        datawrapper_urls,
    )

    print(
        "✓ Current Datawrapper public URLs saved to "
        "datawrapper_urls.json"
    )


# ============================================================
# HISTORICAL / WINDOW CALCULATIONS
# ============================================================

def activity_window(
    rows: list[DailyActivity],
    window_end: date,
) -> tuple[date, int, list[DailyActivity]]:
    """Return the start date, calendar-day count, and rows in the window."""
    earliest = min(
        row.activity_date
        for row in rows
    )

    start = max(
        earliest,
        window_end - timedelta(days=364),
    )

    days = (
        window_end - start
    ).days + 1

    selected = [
        row
        for row in rows
        if start <= row.activity_date <= window_end
    ]

    return (
        start,
        days,
        selected,
    )


def locate_daily_rows(
    rows: list[DailyActivity],
) -> list[tuple[DailyActivity, Geography]]:
    """Map every historical temple name to a state or country."""
    located = []
    unrecognized = []

    for row in rows:
        geography = locate_temple(
            row.temple
        )

        if geography is None:
            unrecognized.append(
                row.temple
            )
        else:
            located.append(
                (
                    row,
                    geography,
                )
            )

    if unrecognized:
        names = sorted(
            set(unrecognized)
        )

        raise RuntimeError(
            "These Fuller Consideration temple names could not be mapped "
            "to a physical U.S. state/country:\n  - "
            + "\n  - ".join(names)
            + "\n\nThe script will not silently exclude them."
        )

    return located


def aggregate_window(
    located_rows: list[
        tuple[DailyActivity, Geography]
    ],
    memberships: dict[
        tuple[str, str],
        int,
    ],
    window_start: date,
    window_end: date,
    window_days: int,
) -> list[dict[str, Any]]:
    """Aggregate the selected daily rows and annualize over calendar days."""
    grouped: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row, geography in located_rows:
        if not (
            window_start
            <= row.activity_date
            <= window_end
        ):
            continue

        key = (
            geography.scope,
            geography.name,
        )

        aggregate = grouped.setdefault(
            key,
            {
                "scope": geography.scope,
                "name": geography.name,
                "slug": geography.slug,
                "iso3": geography.iso3,
                "members": memberships[key],
                "endowments": 0,
                "living": 0,
                "temple_names": set(),
            },
        )

        aggregate["endowments"] += row.endowments
        aggregate["living"] += row.living

        aggregate["temple_names"].add(
            row.temple
        )

    for record in grouped.values():
        record["calendar_days"] = window_days

        record["annualized_endowments"] = (
            record["endowments"]
            * 365
            / window_days
        )

        record["annualized_living"] = (
            record["living"]
            * 365
            / window_days
        )

        record["annualized_per_member"] = (
            record["annualized_endowments"]
            / record["members"]
        )

        record["temple_count"] = len(
            record["temple_names"]
        )

        record.pop(
            "temple_names"
        )

    return list(
        grouped.values()
    )


def build_current_map_rows(
    records: list[dict[str, Any]],
    all_state_memberships: dict[str, int],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Build U.S. and country Datawrapper map CSV rows."""
    us_rows = []

    for record in sorted(
        (
            r
            for r in records
            if r["scope"] == "state"
        ),
        key=lambda r: r["name"],
    ):
        abbreviation = next(
            abbreviation
            for name, abbreviation in STATES
            if name == record["name"]
        )

        us_rows.append(
            {
                "id": abbreviation,
                "name": record["name"],
                "value": record[
                    "annualized_per_member"
                ],
            }
        )

    country_rows = []

    for record in sorted(
        (
            r
            for r in records
            if r["scope"] == "country"
        ),
        key=lambda r: r["name"],
    ):
        country_rows.append(
            {
                "id": record["iso3"],
                "name": record["name"],
                "value": record[
                    "annualized_per_member"
                ],
            }
        )

    us_members = sum(
        all_state_memberships.values()
    )

    us_endowments = sum(
        r["endowments"]
        for r in records
        if r["scope"] == "state"
    )

    us_annualized = (
        us_endowments
        * 365
        / records[0]["calendar_days"]
        if records
        else 0
    )

    us_rate = (
        us_annualized / us_members
        if us_members
        else 0
    )

    country_rows.append(
        {
            "id": "USA",
            "name": "United States",
            "value": us_rate,
        }
    )

    return (
        us_rows,
        country_rows,
    )


# ============================================================
# GLOBAL HISTORICAL TREND
# ============================================================

def build_daily_trend(
    located_rows: list[
        tuple[DailyActivity, Geography]
    ],
    us_members: int,
    world_members: int,
    eligible_members: int,
    first_date: date,
    last_date: date,
) -> list[dict[str, Any]]:
    """Build daily trailing-7-calendar-day annualized trend metrics."""
    daily_world: dict[
        date,
        tuple[int, int],
    ] = {}

    daily_us: dict[
        date,
        int,
    ] = {}

    for current in (
        first_date
        + timedelta(days=i)
        for i in range(
            (last_date - first_date).days + 1
        )
    ):
        world_endowments = 0
        world_living = 0
        us_endowments = 0

        for row, geography in located_rows:
            if row.activity_date != current:
                continue

            world_endowments += row.endowments
            world_living += row.living

            if geography.scope == "state":
                us_endowments += row.endowments

        daily_world[current] = (
            world_endowments,
            world_living,
        )

        daily_us[current] = us_endowments

    rows = []

    trend_start = (
        first_date
        + timedelta(days=6)
    )

    for current in (
        trend_start
        + timedelta(days=i)
        for i in range(
            (last_date - trend_start).days + 1
        )
    ):
        start = current - timedelta(days=6)

        world_endowments = sum(
            daily_world[d][0]
            for d in (
                start
                + timedelta(days=i)
                for i in range(7)
            )
        )

        world_living = sum(
            daily_world[d][1]
            for d in (
                start
                + timedelta(days=i)
                for i in range(7)
            )
        )

        us_endowments = sum(
            daily_us[d]
            for d in (
                start
                + timedelta(days=i)
                for i in range(7)
            )
        )

        annual_factor = 365 / 7

        rows.append(
            {
                "run_date": current.isoformat(),
                "worldwide_rate": (
                    world_endowments
                    * annual_factor
                    / world_members
                ),
                "usa_rate": (
                    us_endowments
                    * annual_factor
                    / us_members
                ),
                "living_ordinance_rate": (
                    world_living
                    * annual_factor
                    / eligible_members
                    * 100
                ),
            }
        )

    return rows


# ============================================================
# GEOGRAPHIC DASHBOARD TREND DATA
# ============================================================

def build_dashboard_trends(
    located_rows: list[
        tuple[DailyActivity, Geography]
    ],
    memberships: dict[
        tuple[str, str],
        int,
    ],
    first_date: date,
    last_date: date,
) -> list[dict[str, Any]]:
    """
    Build daily trailing-7-day annualized endowment attendance data
    for every state and country.

    IMPORTANT:
    The output deliberately includes both membership and activity
    totals, not merely the calculated rate.

    This allows the browser dashboard to combine any arbitrary
    selection of geographies correctly.

    For example:

        Europe rate =
            total annualized endowments in Europe
            / total members in Europe

    rather than:

        average of the individual country rates.
    """

    # --------------------------------------------------------
    # Aggregate daily endowments by geography
    # --------------------------------------------------------

    daily: dict[
        tuple[date, str, str],
        int,
    ] = {}

    geography_info: dict[
        tuple[str, str],
        Geography,
    ] = {}

    geography_first_date: dict[
        tuple[str, str],
        date,
    ] = {}

    for row, geography in located_rows:
        if row.activity_date > last_date:
            continue

        key = (
            geography.scope,
            geography.name,
        )

        geography_info[key] = geography

        prior_first = geography_first_date.get(
            key
        )

        if (
            prior_first is None
            or row.activity_date < prior_first
        ):
            geography_first_date[key] = (
                row.activity_date
            )

        daily_key = (
            row.activity_date,
            geography.scope,
            geography.name,
        )

        daily[daily_key] = (
            daily.get(
                daily_key,
                0,
            )
            + row.endowments
        )

    # --------------------------------------------------------
    # Build complete 7-day trailing history
    # --------------------------------------------------------

    output: list[dict[str, Any]] = []

    for geography_key, geography in sorted(
        geography_info.items(),
        key=lambda item: (
            item[0][0],
            item[0][1],
        ),
    ):
        scope, name = geography_key

        members = memberships.get(
            geography_key
        )

        if not members:
            continue

        geography_start = (
            geography_first_date[
                geography_key
            ]
        )

        trend_start = max(
            first_date,
            geography_start,
        ) + timedelta(days=6)

        if trend_start > last_date:
            continue

        if scope == "state":
            continent = "North America"
            country = "United States"
            geography_type = "state"
        else:
            continent = COUNTRY_CONTINENTS.get(
                name,
                "Other",
            )
            country = name
            geography_type = "country"

        for current in (
            trend_start
            + timedelta(days=i)
            for i in range(
                (last_date - trend_start).days + 1
            )
        ):
            start = current - timedelta(days=6)

            seven_day_total = 0

            for offset in range(7):
                current_day = (
                    start
                    + timedelta(days=offset)
                )

                seven_day_total += daily.get(
                    (
                        current_day,
                        scope,
                        name,
                    ),
                    0,
                )

            annualized_endowments = (
                seven_day_total
                * (365 / 7)
            )

            annualized_rate = (
                annualized_endowments
                / members
            )

            output.append(
                {
                    "date": current.isoformat(),
                    "type": geography_type,
                    "continent": continent,
                    "country": country,
                    "name": name,
                    "members": members,
                    "endowments_7d": seven_day_total,
                    "annualized_endowments": round(
                        annualized_endowments,
                        6,
                    ),
                    "rate": round(
                        annualized_rate,
                        6,
                    ),
                }
            )

    return output


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate annualized temple endowment activity from "
            "Fuller Consideration's complete dated history."
        )
    )

    parser.add_argument(
        "--membership-year",
        default=MEMBERSHIP_YEAR,
    )

    parser.add_argument(
        "--refresh-membership",
        action="store_true",
    )

    parser.add_argument(
        "--skip-datawrapper",
        action="store_true",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            Path(__file__).resolve().parent
            / "temple_attendance_output"
        ),
    )

    args = parser.parse_args()

    cache_path = (
        Path(__file__).resolve().parent
        / "membership_counts.csv"
    )

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "TempleAttendanceResearch/1.0 "
                "(personal data analysis)"
            )
        }
    )

    try:
        print(
            "Reading Fuller Consideration complete "
            "endowment history..."
        )

        history = scrape_full_history(
            session
        )

        first_date = min(
            row.activity_date
            for row in history
        )

        source_end = max(
            row.activity_date
            for row in history
        )

        today = (
            datetime.now()
            .astimezone()
            .date()
        )

        window_end = min(
            source_end,
            today - timedelta(days=1),
        )

        if window_end < first_date:
            raise RuntimeError(
                "Fuller Consideration has no completed day "
                "available for analysis."
            )

        (
            window_start,
            window_days,
            window_rows,
        ) = activity_window(
            history,
            window_end,
        )

        print(
            f"Parsed {len(history):,} dated temple rows "
            f"from {first_date} through {source_end}."
        )

        print(
            f"Current window: {window_start} through "
            f"{window_end} "
            f"({window_days} calendar days)."
        )

        located = locate_daily_rows(
            history
        )

        temple_geographies = {
            geography
            for row, geography in located
            if row.activity_date <= window_end
        }

        all_geographies = set(
            temple_geographies
        )

        # Include all 50 states so the U.S. denominator is complete,
        # even when a state currently has no operating temple.
        for state_name, _ in STATES:
            all_geographies.add(
                Geography(
                    "state",
                    state_name,
                    slugify(state_name),
                )
            )

        geographies = sorted(
            all_geographies,
            key=lambda g: (
                g.scope,
                g.name,
            ),
        )

        print(
            "Building Church membership source pages..."
        )

        membership_pages = (
            build_membership_page_map(
                session,
                geographies,
            )
        )

        print(
            "Reading membership counts..."
        )

        memberships = update_membership_cache(
            session,
            geographies,
            membership_pages,
            cache_path,
            args.membership_year,
            args.refresh_membership,
        )

        all_state_memberships = {
            state_name: memberships[
                (
                    "state",
                    state_name,
                )
            ]
            for state_name, _ in STATES
        }

        records = aggregate_window(
            located,
            memberships,
            window_start,
            window_end,
            window_days,
        )

        us_members = sum(
            all_state_memberships.values()
        )

        world_members = scrape_world_membership(
            session
        )

        eligible_members = (
            ELIGIBLE_CHILDREN_OF_RECORD
            + ELIGIBLE_CONVERTS
        )

        us_endowments = sum(
            r["endowments"]
            for r in records
            if r["scope"] == "state"
        )

        world_endowments = sum(
            row.endowments
            for row in window_rows
        )

        world_living = sum(
            row.living
            for row in window_rows
        )

        annual_factor = (
            365 / window_days
        )

        us_rate = (
            us_endowments
            * annual_factor
            / us_members
        )

        world_rate = (
            world_endowments
            * annual_factor
            / world_members
        )

        eligible_rate = (
            world_living
            * annual_factor
            / eligible_members
        )

        # ----------------------------------------------------
        # Datawrapper current maps
        # ----------------------------------------------------

        us_rows, country_rows = (
            build_current_map_rows(
                records,
                all_state_memberships,
            )
        )

        write_csv(
            args.output_dir
            / "datawrapper_us.csv",
            us_rows,
        )

        write_csv(
            args.output_dir
            / "datawrapper_countries.csv",
            country_rows,
        )

        # ----------------------------------------------------
        # Historical trend
        # ----------------------------------------------------

        trend_rows = build_daily_trend(
            located,
            us_members,
            world_members,
            eligible_members,
            first_date,
            window_end,
        )

        write_csv(
            args.output_dir
            / "historical_summary.csv",
            trend_rows,
        )

        # ----------------------------------------------------
        # Interactive dashboard trend data
        # ----------------------------------------------------

        dashboard_rows = build_dashboard_trends(
            located,
            memberships,
            first_date,
            window_end,
        )

        write_json(
            args.output_dir
            / "trend_dashboard.json",
            dashboard_rows,
        )

        print(
            f"Dashboard trend rows: "
            f"{len(dashboard_rows):,}"
        )

        # ----------------------------------------------------
        # Canonical daily raw dataset
        # ----------------------------------------------------

        raw_rows = [
            {
                "date": row.activity_date.isoformat(),
                "temple": row.temple,
                "endowments": row.endowments,
                "living": row.living,
                "scope": geography.scope,
                "geography": geography.name,
            }
            for row, geography in located
        ]

        write_csv(
            args.output_dir
            / "fuller_consideration_daily.csv",
            raw_rows,
        )

        print()

        print(
            f"Current window endowments: "
            f"{world_endowments:,}"
        )

        print(
            f"Worldwide annualized endowments/member: "
            f"{world_rate:.3f}"
        )

        print(
            f"U.S. annualized endowments/member: "
            f"{us_rate:.3f}"
        )

        print(
            f"Annualized living endowments/eligible member: "
            f"{eligible_rate:.1%}"
        )

        print(
            f"Trend rows: {len(trend_rows):,} "
            f"(starts "
            f"{trend_rows[0]['run_date'] if trend_rows else 'n/a'})"
        )

        print(
            f"CSV/JSON outputs: "
            f"{args.output_dir.resolve()}"
        )

        if args.skip_datawrapper:
            print(
                "Skipping Datawrapper update "
                "(--skip-datawrapper)."
            )
        else:
            update_datawrapper(
                session,
                args.output_dir,
                window_start,
                window_end,
            )

        return 0

    except (
        requests.RequestException,
        RuntimeError,
        ValueError,
        KeyError,
    ) as error:
        print(
            f"Error: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
