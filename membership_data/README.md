# Church Stats membership data (annual December 31 anchors)

Snapshot files `YYYY.csv` use `scope,name,members,source_url` and live in Git, separately from temple attendance scraping. The Python model computes **daily** estimates: interpolation between actual December 31 anchors and straight-line extrapolation beyond the latest anchor, separately for every geography.

- 2024: 50 US states from historical archive `state-2025-04-27.csv`; 44 existing country counts from `country-2025-04-27.csv`; worldwide from the Church News published statistics.
- 2025: 50 states from validated `us_membership_audit.csv`, 44 countries from validated `annualized_by_region.csv`, worldwide 17,887,212.
- On installation, `.github/workflows/membership-refresh.yml` automatically expands **both** years to countries/territories for which the historical Church-statistics archive has a positive published year-end value in the corresponding year. It does not change verified existing rows.
- Starting April 2027, the annual workflow collects new data **directly from the Church**. It verifies the report's year-end date and numerical consistency; only approved CSVs are committed.

A 0 in the third-party historical archive can indicate that a country has no publicly reported membership. The bootstrap skips such countries rather than treating 0 as an actual membership denominator. Missing membership history does not justify guessing.

Historical archive: https://github.com/acbass49/scrape_lds_stats
Church statistics: https://www.churchofjesuschrist.org/learn/facts-statistics?lang=eng

The US dashboard denominator is the sum of the **50** state membership series (excluding DC and territories). World uses the official global membership total. Historical rates are recomputed when verified year-end snapshots are added, not overwritten by current-year membership.
