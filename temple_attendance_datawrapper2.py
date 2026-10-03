from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
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
        r"\[[^\]]+\]\((https?://[^)]+)\)",
        value,
    )

    if match:
        return match.group(1)

    return value


def normalize_name(value: str) -> str:
    """Normalize names for matching."""
    value = unicodedata.normalize(
        "NFKD",
        value,
    )

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

def scrape_weekly_temples(
    session: requests.Session,
) -> list[Temple]:
    """Scrape Fuller Consideration's Past 7 Days temple activity."""
    soup = page_soup(
        session,
        TRACKER_URL,
    )

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        header_index = None
        columns: dict[str, int] = {}

        for index, row in enumerate(rows):
            cells = row.find_all(
                ["th", "td"],
                recursive=False,
            )

            labels = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                ).casefold()
                for cell in cells
            ]

            if (
                "temple" in labels
                and "endowments" in labels
            ):
                header_index = index

                columns = {
                    label: position
                    for position, label in enumerate(labels)
                }

                break

        if header_index is None:
            continue

        temples: list[Temple] = []

        for row in rows[header_index + 1:]:
            cells = row.find_all(
                ["th", "td"],
                recursive=False,
            )

            if not cells:
                continue

            link = cells[0].find(
                "a",
                href=re.compile(
                    r"endowments.*\.php\?temple=",
                    re.IGNORECASE,
                ),
            )

            if not link:
                continue

            name = clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            first_cell = clean_text(
                cells[0].get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                name.endswith("*")
                or first_cell.endswith("*")
            ):
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

            try:
                endowments = parse_count(
                    values[columns["endowments"]]
                )

                living = parse_count(
                    values[columns["living"]]
                )

            except (
                IndexError,
                KeyError,
                ValueError,
            ):
                continue

            temples.append(
                Temple(
                    name=name,
                    endowments=endowments,
                    living=living,
                )
            )

        if temples:
            return temples

    raise RuntimeError(
        "Could not find Fuller Consideration's "
        "'Past 7 days' temple table."
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
        temple_name.removesuffix(
            " Temple"
        ).rstrip("* ")
    ).casefold()

    # Check states first.
    for state_name, _ in sorted(
        STATES,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if normalized.endswith(
            state_name.casefold()
        ):
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

        if normalized.endswith(
            candidate.casefold()
        ):
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

    The geography-specific section appears before the page's
    "Worldwide Statistics" section. We deliberately ignore the
    worldwide section so its membership figure cannot be mistaken
    for the geography's figure.
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
# CSV HELPERS
# ============================================================

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
# DATAWRAPPER CSV GENERATION
# ============================================================

def build_datawrapper_us_rows(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build the CSV consumed by the U.S. Datawrapper map.

    Only states with operating temples are included.
    """
    rows: list[dict[str, Any]] = []

    for record in sorted(
        (
            record
            for record in records
            if record["scope"] == "state"
        ),
        key=lambda record: record["name"],
    ):
        abbreviation = next(
            abbreviation
            for name, abbreviation in STATES
            if name == record["name"]
        )

        rows.append(
            {
                "id": abbreviation,
                "name": record["name"],
                "value": (
                    record["annualized_per_member"]
                ),
            }
        )

    return rows


def build_datawrapper_country_rows(
    records: list[dict[str, Any]],
    all_state_memberships: dict[str, int],
) -> list[dict[str, Any]]:
    """
    Build the CSV consumed by the country Datawrapper map.

    Adds a synthetic USA row whose denominator is the total
    membership of all 50 U.S. states, not merely states with
    operating temples.
    """
    rows: list[dict[str, Any]] = []

    for record in sorted(
        (
            record
            for record in records
            if record["scope"] == "country"
        ),
        key=lambda record: record["name"],
    ):
        rows.append(
            {
                "id": record["iso3"],
                "name": record["name"],
                "value": (
                    record["annualized_per_member"]
                ),
            }
        )

    us_members = sum(
        all_state_memberships.values()
    )

    us_endowments = sum(
        record["weekly_endowments"]
        for record in records
        if record["scope"] == "state"
    )

    us_annualized = (
        us_endowments
        * WEEKS_PER_YEAR
    )

    us_rate = (
        us_annualized
        / us_members
    )

    rows.append(
        {
            "id": "USA",
            "name": "United States",
            "value": us_rate,
        }
    )

    return rows


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
) -> str:
    """
    Build the chart title using the date on which the script runs.
    """
    now = datetime.now().astimezone()

    as_of = (
        f"{now.month}/"
        f"{now.day}/"
        f"{now:%y}"
    )

    return (
        "Annualized Temple Endowment sessions attended "
        "per member of record, "
        f"by {geography_label} "
        f"(last 7 days, as of {as_of})"
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

    Returns the published public URL when available.
    """
    csv_data = csv_path.read_bytes()

    # --------------------------------------------------------
    # Upload current data
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Update dynamic chart title
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Publish chart
    # --------------------------------------------------------

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
) -> None:
    """
    Update both configured Datawrapper charts.
    """
    token = os.getenv(
        "DATAWRAPPER_TOKEN"
    )

    us_chart_id = os.getenv(
        "DATAWRAPPER_US_CHART_ID"
    )

    countries_chart_id = os.getenv(
        "DATAWRAPPER_COUNTRIES_CHART_ID"
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

    if missing:
        raise RuntimeError(
            "Missing Datawrapper environment variables: "
            + ", ".join(missing)
        )

    print()
    print(
        "Updating Datawrapper charts..."
    )

    us_title = build_datawrapper_title(
        "state"
    )

    countries_title = build_datawrapper_title(
        "country"
    )

    update_datawrapper_chart(
        session=session,
        token=token,
        chart_id=us_chart_id,
        csv_path=(
            output_dir
            / "datawrapper_us.csv"
        ),
        chart_name="U.S.",
        title=us_title,
    )

    update_datawrapper_chart(
        session=session,
        token=token,
        chart_id=countries_chart_id,
        csv_path=(
            output_dir
            / "datawrapper_countries.csv"
        ),
        chart_name="countries",
        title=countries_title,
    )



# ============================================================
# HISTORICAL OUTPUTS
# ============================================================

def upsert_historical_csv(
    path: Path,
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
) -> None:
    """
    Add the current run to a historical CSV.

    If rows for the same key already exist, replace them. This makes
    repeated runs on the same day idempotent while preserving all
    earlier historical observations.
    """
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict[str, Any]] = []

    if path.exists():
        with path.open(
            newline="",
            encoding="utf-8",
        ) as handle:
            existing = list(csv.DictReader(handle))

    current_keys = {
        tuple(str(row[field]) for field in key_fields)
        for row in rows
    }

    filtered_existing = [
        row
        for row in existing
        if tuple(str(row.get(field, "")) for field in key_fields)
        not in current_keys
    ]

    combined = filtered_existing + rows

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
        writer.writerows(combined)


def build_historical_detail_rows(
    run_date: str,
    records: list[dict[str, Any]],
    all_state_memberships: dict[str, int],
    membership_year: str,
) -> list[dict[str, Any]]:
    """
    Build a historical snapshot containing every U.S. state plus every
    country with an operating temple.

    States without an operating temple are retained with zero activity.
    This preserves the complete 50-state membership universe for future
    analysis while keeping the current Datawrapper map limited to
    states with operating temples.
    """
    rows: list[dict[str, Any]] = []

    record_lookup = {
        (
            record["scope"],
            record["name"],
        ): record
        for record in records
    }

    for state_name, abbreviation in STATES:
        record = record_lookup.get(
            ("state", state_name)
        )

        if record is None:
            members = all_state_memberships[state_name]
            weekly_endowments = 0
            weekly_living = 0
            temple_count = 0
            annualized_endowments = 0
            annualized_per_member = 0.0
            membership_source = "Church state pages"
        else:
            members = record["members"]
            weekly_endowments = record["weekly_endowments"]
            weekly_living = record["weekly_living"]
            temple_count = record["temple_count"]
            annualized_endowments = record[
                "annualized_endowments"
            ]
            annualized_per_member = record[
                "annualized_per_member"
            ]
            membership_source = record[
                "membership_source"
            ]

        rows.append(
            {
                "run_date": run_date,
                "scope": "state",
                "id": abbreviation,
                "name": state_name,
                "weekly_endowments": weekly_endowments,
                "weekly_living": weekly_living,
                "members": members,
                "temple_count": temple_count,
                "annualized_endowments": annualized_endowments,
                "annualized_endowments_per_member": (
                    annualized_per_member
                ),
                "membership_year": membership_year,
                "membership_source": membership_source,
            }
        )

    for record in sorted(
        (
            record
            for record in records
            if record["scope"] == "country"
        ),
        key=lambda record: record["name"],
    ):
        rows.append(
            {
                "run_date": run_date,
                "scope": "country",
                "id": record["iso3"],
                "name": record["name"],
                "weekly_endowments": record[
                    "weekly_endowments"
                ],
                "weekly_living": record[
                    "weekly_living"
                ],
                "members": record["members"],
                "temple_count": record[
                    "temple_count"
                ],
                "annualized_endowments": record[
                    "annualized_endowments"
                ],
                "annualized_endowments_per_member": (
                    record["annualized_per_member"]
                ),
                "membership_year": record[
                    "membership_year"
                ],
                "membership_source": record[
                    "membership_source"
                ],
            }
        )

    return rows


def build_historical_summary_row(
    run_date: str,
    world_rate: float,
    us_rate: float,
    eligible_rate: float,
) -> dict[str, Any]:
    """
    Build the simple historical time-series row.

    Rates are stored as percentage points for easy charting:
    21.9 means 21.9%.
    """
    return {
        "run_date": run_date,
        "worldwide_rate": world_rate,
        "usa_rate": us_rate,
        "living_ordinance_rate": eligible_rate * 100,
    }


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate annualized temple endowments per "
            "Church member by physical temple location."
        )
    )

    parser.add_argument(
        "--membership-year",
        default=MEMBERSHIP_YEAR,
        help=(
            "Membership denominator year "
            f"(default: {MEMBERSHIP_YEAR})."
        ),
    )

    parser.add_argument(
        "--refresh-membership",
        action="store_true",
        help=(
            "Re-scrape and replace cached membership counts."
        ),
    )

    parser.add_argument(
        "--skip-datawrapper",
        action="store_true",
        help=(
            "Generate CSVs without uploading or publishing "
            "Datawrapper charts."
        ),
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
        # ----------------------------------------------------
        # Temple activity
        # ----------------------------------------------------

        print(
            "Reading Fuller Consideration temple activity..."
        )

        temples = scrape_weekly_temples(
            session
        )

        located: list[
            tuple[Temple, Geography]
        ] = []

        unrecognized: list[str] = []

        for temple in temples:
            geography = locate_temple(
                temple.name
            )

            if geography is None:
                unrecognized.append(
                    temple.name
                )
            else:
                located.append(
                    (
                        temple,
                        geography,
                    )
                )

        if unrecognized:
            raise RuntimeError(
                "These active temples could not be mapped "
                "to a physical state/country:\n  - "
                + "\n  - ".join(
                    unrecognized
                )
                + "\n\n"
                "The script will not silently exclude them."
            )

        print(
            f"Active temples parsed: {len(temples)}"
        )

        # ----------------------------------------------------
        # Membership source pages
        # ----------------------------------------------------
        #
        # We need membership pages for:
        #
        # 1. Every geography with an operating temple
        # 2. Every U.S. state, because the USA aggregate needs
        #    the membership denominator for all 50 states.
        # ----------------------------------------------------

        temple_geographies = {
            geography
            for _, geography in located
        }

        all_geographies = set(
            temple_geographies
        )

        for state_name, _ in STATES:
            all_geographies.add(
                Geography(
                    scope="state",
                    name=state_name,
                    slug=slugify(state_name),
                )
            )

        geographies = sorted(
            all_geographies,
            key=lambda item: (
                item.scope,
                item.name,
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

        temple_state_count = sum(
            1
            for geography in temple_geographies
            if geography.scope == "state"
        )

        temple_country_count = sum(
            1
            for geography in temple_geographies
            if geography.scope == "country"
        )

        print(
            f"✓ Resolved membership pages for "
            f"all 50 U.S. states, "
            f"{temple_state_count} temple states, "
            f"and {temple_country_count} temple countries"
        )

        # ----------------------------------------------------
        # Membership counts
        # ----------------------------------------------------

        print(
            f"Reading {args.membership_year} membership counts..."
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

        # ----------------------------------------------------
        # Aggregate temples by physical geography
        # ----------------------------------------------------

        grouped: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        temple_rows: list[
            dict[str, Any]
        ] = []

        for temple, geography in located:
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
                    "weekly_endowments": 0,
                    "weekly_living": 0,
                    "temple_count": 0,
                },
            )

            aggregate[
                "weekly_endowments"
            ] += temple.endowments

            aggregate[
                "weekly_living"
            ] += temple.living

            aggregate[
                "temple_count"
            ] += 1

            temple_rows.append(
                {
                    "temple": temple.name,
                    "scope": geography.scope,
                    "geography": geography.name,
                    "endowments_7d": temple.endowments,
                    "living_7d": temple.living,
                }
            )

        records = list(
            grouped.values()
        )

        for record in records:
            record[
                "annualized_endowments"
            ] = (
                record["weekly_endowments"]
                * WEEKS_PER_YEAR
            )

            record[
                "annualized_per_member"
            ] = (
                record[
                    "annualized_endowments"
                ]
                / record["members"]
            )

            record[
                "membership_year"
            ] = args.membership_year

            record[
                "membership_source"
            ] = (
                "UK English Church country pages"
                if record["scope"] == "country"
                else "Church state pages"
            )

        # ----------------------------------------------------
        # Output CSVs
        # ----------------------------------------------------

        # ----------------------------------------------------
        # Datawrapper-ready CSVs
        # ----------------------------------------------------

        datawrapper_us_rows = (
            build_datawrapper_us_rows(
                records
            )
        )

        datawrapper_country_rows = (
            build_datawrapper_country_rows(
                records,
                all_state_memberships,
            )
        )

        write_csv(
            args.output_dir
            / "datawrapper_us.csv",
            datawrapper_us_rows,
        )

        write_csv(
            args.output_dir
            / "datawrapper_countries.csv",
            datawrapper_country_rows,
        )

        # ----------------------------------------------------
        # Worldwide check
        # ----------------------------------------------------

        world_members = scrape_world_membership(
            session
        )

        total_endowments = sum(
            temple.endowments
            for temple in temples
        )

        total_living = sum(
            temple.living
            for temple in temples
        )

        world_rate = (
            total_endowments
            * WEEKS_PER_YEAR
            / world_members
        )

        eligible = (
            ELIGIBLE_CHILDREN_OF_RECORD
            + ELIGIBLE_CONVERTS
        )

        eligible_rate = (
            total_living
            * WEEKS_PER_YEAR
            / eligible
        )

        # ----------------------------------------------------
        # U.S. aggregate check
        # ----------------------------------------------------

        us_members = sum(
            all_state_memberships.values()
        )

        us_weekly_endowments = sum(
            record["weekly_endowments"]
            for record in records
            if record["scope"] == "state"
        )

        us_rate = (
            us_weekly_endowments
            * WEEKS_PER_YEAR
            / us_members
        )

        # ----------------------------------------------------
        # Historical outputs
        # ----------------------------------------------------

        run_date = (
            datetime.now()
            .astimezone()
            .date()
            .isoformat()
        )

        historical_detail_rows = (
            build_historical_detail_rows(
                run_date=run_date,
                records=records,
                all_state_memberships=all_state_memberships,
                membership_year=args.membership_year,
            )
        )

        historical_summary_row = (
            build_historical_summary_row(
                run_date=run_date,
                world_rate=world_rate,
                us_rate=us_rate,
                eligible_rate=eligible_rate,
            )
        )

        upsert_historical_csv(
            args.output_dir
            / "historical_detail.csv",
            historical_detail_rows,
            key_fields=("run_date", "scope", "id"),
        )

        upsert_historical_csv(
            args.output_dir
            / "historical_summary.csv",
            [historical_summary_row],
            key_fields=("run_date",),
        )

        print()

        print(
            f"Membership denominator year: "
            f"{args.membership_year}"
        )

        print(
            "Country membership source: "
            "UK English Church country pages"
        )

        print(
            f"Active temples parsed: {len(temples)}; "
            f"weekly endowments: "
            f"{total_endowments:,}"
        )

        print(
            "Worldwide annualized endowments per member: "
            f"{world_rate:.3f} "
            "(target reference: about 0.52)"
        )

        print(
            f"U.S. members across all 50 states: "
            f"{us_members:,}"
        )

        print(
            f"U.S. weekly endowments: "
            f"{us_weekly_endowments:,}"
        )

        print(
            "U.S. annualized endowments per member: "
            f"{us_rate:.3f}"
        )

        print(
            f"Living endowments: {total_living:,}/week; "
            f"eligible population: {eligible:,}; "
            f"annualized eligible-member ratio: "
            f"{eligible_rate:.1%}"
        )

        print(
            f"CSV outputs: "
            f"{args.output_dir.resolve()}"
        )

        # ----------------------------------------------------
        # Datawrapper
        # ----------------------------------------------------

        if args.skip_datawrapper:
            print()
            print(
                "Skipping Datawrapper update "
                "(--skip-datawrapper)."
            )
        else:
            update_datawrapper(
                session,
                args.output_dir,
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