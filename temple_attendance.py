"""Weekly temple endowment activity per Church membership, by state and country."""

from __future__ import annotations

import argparse
import bisect
import csv
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import plotly.graph_objects as go
import pycountry
import requests
from bs4 import BeautifulSoup


CHURCH_BASE = (
    "https://www.churchofjesuschrist.org/learn/facts-statistics/"
)

NEWSROOM_BASE = (
    "https://newsroom.churchofjesuschrist.org/facts-and-statistics/state/"
)

GEOGRAPHY_INDEX_URL = (
    "https://newsroom.churchofjesuschrist.org/"
    "facts-and-statistics/state/california"
)

TRACKER_URL = (
    "https://fullerconsideration.com/TempleTracker/"
)

WORLD_STATS_URL = CHURCH_BASE + "?lang=eng"

WEEKS_PER_YEAR = 52

# Increment this whenever the membership parsing/cache format changes.
# This prevents stale data from an older parser from silently surviving.
MEMBERSHIP_CACHE_VERSION = "2"

ELIGIBLE_CHILDREN_OF_RECORD = 94_006
ELIGIBLE_CONVERTS = 385_490

COLORS = [
    "#8b1e2d",
    "#c75b58",
    "#e9a298",
    "#f1e4b8",
    "#a8c9dc",
    "#558fb7",
    "#1c4f7a",
]

GREY = "#c5c6c3"


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


# These temples have names that do not directly identify their
# physical state/country.
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


# Names used by Fuller Consideration / temple names that differ from
# the Church's geography-page names or ISO names.
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
    "Republic of the Congo": ("Republic of the Congo", "COG"),
    "Puerto Rico": ("Puerto Rico", "PRI"),
    "Guam": ("Guam", "GUM"),
    "American Samoa": ("American Samoa", "ASM"),
    "Canada": ("Canada", "CAN"),
    "French Polynesia": ("French Polynesia", "PYF"),
    "United Kingdom": ("United Kingdom", "GBR"),
    "Peru": ("Peru", "PER"),
    "Cape Verde": ("Cape Verde", "CPV"),
}


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


def clean_text(value: str) -> str:
    """Normalize whitespace in visible page text."""
    return re.sub(r"\s+", " ", value).strip()


def clean_url(value: str) -> str:
    """
    Return a plain URL.

    This is defensive because Markdown-style URLs accidentally made their
    way into an earlier version. URLs should normally already be plain
    strings.
    """
    value = str(value).strip()

    # Handle Markdown syntax:
    # [label](https://example.com)
    match = re.fullmatch(
        r"\[[^\]]+\]\((https?://[^)]+)\)",
        value,
    )

    if match:
        return match.group(1)

    return value


def normalize_name(value: str) -> str:
    """Normalize names so accents/punctuation do not prevent matching."""
    value = unicodedata.normalize("NFKD", value)

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )

    value = value.casefold()
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", " ", value)

    return clean_text(value)


def parse_count(value: str) -> int:
    """Convert a formatted numeric string to an integer."""
    digits = re.sub(r"[^0-9]", "", value)

    if not digits:
        raise ValueError(
            f"Expected a numeric count, found {value!r}"
        )

    return int(digits)


def page_soup(
    session: requests.Session,
    url: str,
) -> BeautifulSoup:
    """Fetch a page and return its parsed HTML."""
    url = clean_url(url)

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url!r}")

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


def scrape_weekly_temples(
    session: requests.Session,
) -> list[Temple]:
    """
    Scrape Fuller Consideration's Past 7 Days temple activity table.
    """
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

            if "temple" in labels and "endowments" in labels:
                header_index = index

                columns = {
                    label: position
                    for position, label in enumerate(labels)
                }

                break

        if header_index is None:
            continue

        temples = []

        for row in rows[header_index + 1 :]:
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

            if name.endswith("*") or first_cell.endswith("*"):
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


def slugify(name: str) -> str:
    """Create a URL-like slug from a geography name."""
    text = name.casefold().replace(
        "&",
        "and",
    )

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text,
    )

    return text.strip("-")


def country_names() -> list[str]:
    """Return country names usable for suffix matching."""
    names: set[str] = set(COUNTRY_OVERRIDES)

    for country in pycountry.countries:
        names.add(country.name)

        names.add(
            getattr(
                country,
                "common_name",
                country.name,
            )
        )

        names.add(
            getattr(
                country,
                "official_name",
                country.name,
            )
        )

    return sorted(
        names,
        key=len,
        reverse=True,
    )


def locate_temple(
    temple_name: str,
) -> Geography | None:
    """
    Determine the physical state/country where a temple is located.

    Explicit overrides are used for temples whose names do not directly
    identify their physical geography.
    """
    if temple_name in TEMPLE_LOCATION_OVERRIDES:
        scope, location_name = TEMPLE_LOCATION_OVERRIDES[
            temple_name
        ]

        if scope == "state":
            return Geography(
                "state",
                location_name,
                slugify(location_name),
            )

        display_name, iso3 = COUNTRY_OVERRIDES[
            location_name
        ]

        return Geography(
            "country",
            display_name,
            slugify(display_name),
            iso3,
        )

    normalized = clean_text(
        temple_name.removesuffix(" Temple").rstrip("* ")
    ).casefold()

    # States are checked first because temple names such as
    # "Washington D.C." are handled by an explicit override above.
    for state_name, _ in sorted(
        STATES,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if normalized.endswith(
            state_name.casefold()
        ):
            return Geography(
                "state",
                state_name,
                slugify(state_name),
            )

    for suffix in country_names():
        if not normalized.endswith(
            suffix.casefold()
        ):
            continue

        if suffix in COUNTRY_OVERRIDES:
            display_name, iso3 = COUNTRY_OVERRIDES[
                suffix
            ]

            return Geography(
                "country",
                display_name,
                slugify(display_name),
                iso3,
            )

        country = next(
            (
                item
                for item in pycountry.countries
                if suffix
                in {
                    item.name,
                    getattr(
                        item,
                        "common_name",
                        "",
                    ),
                    getattr(
                        item,
                        "official_name",
                        "",
                    ),
                }
            ),
            None,
        )

        if country:
            display_name = getattr(
                country,
                "common_name",
                country.name,
            )

            return Geography(
                "country",
                display_name,
                slugify(display_name),
                country.alpha_3,
            )

    return None


def discover_membership_pages(
    session: requests.Session,
) -> dict[tuple[str, str], MembershipPage]:
    """
    Discover the Church's actual geography URLs from the Church's own
    facts-and-statistics navigation.

    We deliberately do NOT construct country/state URLs ourselves.
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

        # href is a URL, not visible text.
        href = clean_url(
            link.get("href", "")
        )

        if not label or not href:
            continue

        absolute_url = urljoin(
            GEOGRAPHY_INDEX_URL,
            href,
        )

        parsed = urlparse(absolute_url)
        path = parsed.path.rstrip("/")

        scope = None

        # U.S. state pages.
        if "/facts-and-statistics/state/" in path:
            scope = "state"

        # Church country pages can appear either under the current
        # learn/facts-statistics structure or under Newsroom country pages.
        elif (
            "/facts-and-statistics/country/" in path
            or "/learn/facts-statistics/" in path
        ):
            scope = "country"

        if scope is None:
            continue

        if scope == "state":
            name = next(
                (
                    state_name
                    for state_name, _ in STATES
                    if normalize_name(state_name)
                    == normalize_name(label)
                ),
                None,
            )

            if name:
                discovered[
                    (
                        scope,
                        name,
                    )
                ] = MembershipPage(
                    scope=scope,
                    name=name,
                    url=absolute_url,
                )

        else:
            normalized_label = normalize_name(label)

            # Church geography navigation calls this "Cote d'Ivoire".
            if normalized_label == normalize_name(
                "Cote d'Ivoire"
            ):
                display_name = "Ivory Coast"

            elif normalized_label == normalize_name(
                "District of Columbia"
            ):
                display_name = "District of Columbia"

            else:
                display_name = label

            if display_name in COUNTRY_OVERRIDES:
                display_name = COUNTRY_OVERRIDES[
                    display_name
                ][0]

            discovered[
                (
                    "country",
                    display_name,
                )
            ] = MembershipPage(
                scope="country",
                name=display_name,
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
    Match every temple geography to a real Church geography page.

    No URLs are guessed. Missing pages cause the script to stop.
    """
    discovered = discover_membership_pages(
        session
    )

    result: dict[
        tuple[str, str],
        MembershipPage,
    ] = {}

    missing: list[str] = []

    for geography in geographies:
        key = (
            geography.scope,
            geography.name,
        )

        page = discovered.get(key)

        if page is None and geography.scope == "country":
            target = normalize_name(
                geography.name
            )

            candidates = [
                candidate
                for candidate in discovered.values()
                if candidate.scope == "country"
                and normalize_name(candidate.name)
                == target
            ]

            if len(candidates) == 1:
                page = candidates[0]

        if page is None:
            missing.append(
                f"{geography.scope}: {geography.name}"
            )
        else:
            result[key] = page

    if missing:
        raise RuntimeError(
            "Could not resolve these Church membership pages "
            "from the Church's own geography index:\n  - "
            + "\n  - ".join(missing)
            + "\n\nThe script will not guess a URL."
        )

    return result


def scrape_membership(
    session: requests.Session,
    page: MembershipPage,
    expected_year: str,
) -> tuple[int, str, str]:
    """
    Read the membership count from an actual Church geography page.

    Church state pages and country pages use slightly different layouts.

    State-style example:
        Utah 2,206,370 Total Church Membership

    Country-style example:
        Church Membership
        505,819

    We support both formats and reject suspiciously small values.
    """
    text = clean_text(
        page_soup(
            session,
            page.url,
        ).get_text(
            " ",
            strip=True,
        )
    )

    count = None

    # ------------------------------------------------------------
    # Format 1: state-style
    #
    #     2,206,370 Total Church Membership
    # ------------------------------------------------------------
    match = re.search(
        r"([0-9][0-9,\u202f]*)\s+"
        r"Total\s+Church\s+Membership\b",
        text,
        re.IGNORECASE,
    )

    if match:
        count = parse_count(
            match.group(1)
        )

    # ------------------------------------------------------------
    # Format 2: country-style
    #
    #     Church Membership 505,819
    #
    # clean_text() collapses the original line break into a space,
    # so this works whether the HTML has separate elements or text
    # on the same line.
    # ------------------------------------------------------------
    if count is None:
        match = re.search(
            r"Church\s+Membership\b\s+"
            r"([0-9][0-9,\u202f]*)",
            text,
            re.IGNORECASE,
        )

        if match:
            count = parse_count(
                match.group(1)
            )

    if count is None:
        raise ValueError(
            "Could not find Church Membership on "
            f"{page.url}"
        )

    # A value this small almost certainly means we parsed something
    # other than the actual membership count.
    if count < 1_000:
        raise ValueError(
            f"Suspicious Church Membership value "
            f"{count:,} on {page.url}. "
            "Refusing to cache it."
        )

    # ------------------------------------------------------------
    # Published update date
    # ------------------------------------------------------------
    updated_match = re.search(
        r"Last Updated On\s+"
        r"([\w ,\u00a0]+\d{4})",
        text,
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


def read_membership_cache(
    path: Path,
) -> dict[
    tuple[str, str, str],
    dict[str, str],
]:
    """
    Read only cache rows created by the current cache schema.

    Older cache files are intentionally ignored rather than trusted.
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
    Read cached membership values or scrape missing/stale values.
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

            count, updated, source = scrape_membership(
                session,
                page,
                year,
            )

            row = {
                "cache_version": MEMBERSHIP_CACHE_VERSION,
                "year": year,
                "scope": geography.scope,
                "name": geography.name,
                "members": str(count),
                "published_update": updated,
                "source_url": source,
                "scraped_at": datetime.now()
                .astimezone()
                .isoformat(
                    timespec="seconds"
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


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    """Write a list of dictionaries to CSV."""
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


def quantile(
    sorted_values: list[float],
    probability: float,
) -> float:
    """Calculate a linearly interpolated quantile."""
    position = (
        len(sorted_values) - 1
    ) * probability

    lower = int(position)

    upper = min(
        lower + 1,
        len(sorted_values) - 1,
    )

    fraction = position - lower

    return (
        sorted_values[lower] * (1 - fraction)
        + sorted_values[upper] * fraction
    )


def make_tiers(
    values: list[float],
) -> tuple[
    list[float],
    list[str],
]:
    """Create seven roughly equal-frequency map tiers."""
    ordered = sorted(values)

    if ordered[0] == ordered[-1]:
        breaks = [ordered[0]] * 6

    else:
        breaks = [
            quantile(
                ordered,
                index / 7,
            )
            for index in range(1, 7)
        ]

        # If repeated values make the quantile breaks collapse,
        # fall back to evenly spaced numeric breaks.
        if len(set(breaks)) < 6:
            breaks = [
                ordered[0]
                + (
                    ordered[-1]
                    - ordered[0]
                ) * index / 7
                for index in range(1, 7)
            ]

    labels = []

    for index in range(7):
        lower = (
            ""
            if index == 0
            else f"{breaks[index - 1]:.3f}"
        )

        upper = (
            ""
            if index == 6
            else f"{breaks[index]:.3f}"
        )

        if index == 0:
            labels.append(
                f"<= {upper}"
            )

        elif index == 6:
            labels.append(
                f"> {lower}"
            )

        else:
            labels.append(
                f"{lower} to {upper}"
            )

    return (
        breaks,
        labels,
    )


def tier_colorscale() -> list[list[Any]]:
    """Build a discrete seven-tier Plotly colorscale."""
    scale: list[list[Any]] = []

    for index, color in enumerate(COLORS):
        start = (
            0
            if index == 0
            else (index - 0.5) / 6
        )

        end = (
            1
            if index == 6
            else (index + 0.5) / 6
        )

        scale.extend(
            [
                [start, color],
                [end - 1e-6, color],
            ]
        )

    return scale


def create_map(
    records: list[dict[str, Any]],
    scope: str,
    output_path: Path,
    title: str,
) -> None:
    """Create a Plotly choropleth map."""
    active = [
        record
        for record in records
        if record["scope"] == scope
    ]

    if not active:
        raise RuntimeError(
            f"No {scope} temple records were recognized; "
            "review temple location mappings."
        )

    values = [
        record["annualized_per_member"]
        for record in active
    ]

    breaks, labels = make_tiers(
        values
    )

    all_same = len(set(values)) == 1

    for record in active:
        record["tier"] = (
            4
            if all_same
            else (
                bisect.bisect_right(
                    breaks,
                    record[
                        "annualized_per_member"
                    ],
                )
                + 1
            )
        )

    if scope == "state":
        by_name = {
            record["name"]: record
            for record in active
        }

        locations = [
            abbreviation
            for _, abbreviation in STATES
        ]

        z = [
            by_name.get(
                name,
                {},
            ).get(
                "tier",
                None,
            )
            for name, _ in STATES
        ]

        hover = [
            [
                name,
                item["members"],
                item["weekly_endowments"],
                item[
                    "annualized_per_member"
                ],
            ]
            if (
                item := by_name.get(name)
            )
            else [
                name,
                "No operating temple",
                "",
                "",
            ]
            for name, _ in STATES
        ]

        locationmode = "USA-states"

        geo = dict(
            scope="usa",
            showland=True,
            landcolor=GREY,
            showsubunits=True,
            subunitcolor="white",
        )

    else:
        locations = [
            record["iso3"]
            for record in active
        ]

        if any(
            not code
            for code in locations
        ):
            missing = [
                record["name"]
                for record in active
                if not record["iso3"]
            ]

            raise RuntimeError(
                "Missing ISO country codes for: "
                + ", ".join(missing)
            )

        z = [
            record["tier"]
            for record in active
        ]

        hover = [
            [
                record["name"],
                record["members"],
                record["weekly_endowments"],
                record[
                    "annualized_per_member"
                ],
            ]
            for record in active
        ]

        locationmode = "ISO-3"

        geo = dict(
            showland=True,
            landcolor="#e5e5e2",
            showcountries=True,
            countrycolor="white",
        )

    figure = go.Figure(
        go.Choropleth(
            locations=locations,
            z=z,
            locationmode=locationmode,
            zmin=1,
            zmax=7,
            colorscale=tier_colorscale(),
            customdata=hover,
            marker_line_color="white",
            marker_line_width=0.55,
            colorbar=dict(
                title="Annualized<br>per member",
                tickvals=list(range(1, 8)),
                ticktext=labels,
                len=0.78,
            ),
            hovertemplate=(
                "%{customdata[0]}<br>"
                "Members: %{customdata[1]}<br>"
                "Endowments in past 7 days: "
                "%{customdata[2]}<br>"
                "Annualized per member: "
                "%{customdata[3]:.3f}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        title=title,
        geo=geo,
        margin=dict(
            l=8,
            r=8,
            t=55,
            b=8,
        ),
        paper_bgcolor="white",
        font=dict(
            family="Arial, sans-serif",
            color="#252525",
        ),
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure.write_html(
        output_path,
        include_plotlyjs="cdn",
        full_html=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--membership-year",
        default="2025",
        help=(
            "Year of Church year-end membership counts "
            "(default: 2025)."
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
            "Reading Fuller Consideration temple activity..."
        )

        temples = scrape_weekly_temples(
            session
        )

        located: list[
            tuple[Temple, Geography]
        ] = []

        unrecognized = []

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
                + "\n\nThe script will not silently exclude them."
            )

        print(
            f"Active temples parsed: {len(temples)}"
        )

        print(
            "Discovering Church membership pages..."
        )

        geographies = sorted(
            {
                geography
                for _, geography in located
            },
            key=lambda item: (
                item.scope,
                item.name,
            ),
        )

        membership_pages = (
            build_membership_page_map(
                session,
                geographies,
            )
        )

        print(
            f"✓ Resolved {len(membership_pages)} "
            "Church geography pages"
        )

        print(
            f"Reading {args.membership_year} "
            "membership counts..."
        )

        memberships = update_membership_cache(
            session,
            geographies,
            membership_pages,
            cache_path,
            args.membership_year,
            args.refresh_membership,
        )

        grouped: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

        temple_rows = []

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

        write_csv(
            args.output_dir
            / "temple_activity.csv",
            temple_rows,
        )

        write_csv(
            args.output_dir
            / "annualized_by_region.csv",
            records,
        )

        create_map(
            records,
            "state",
            args.output_dir
            / "us_states.html",
            "Annualized Endowments per Member "
            "of Record by State",
        )

        create_map(
            records,
            "country",
            args.output_dir
            / "countries.html",
            "Annualized Endowments per Member "
            "of Record by Country",
        )

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

        print()

        print(
            f"Membership denominator year: "
            f"{args.membership_year}"
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
            f"Living endowments: {total_living:,}/week; "
            f"eligible population: {eligible:,}; "
            f"annualized eligible-member ratio: "
            f"{eligible_rate:.1%}"
        )

        print(
            f"Maps and CSVs: "
            f"{args.output_dir.resolve()}"
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