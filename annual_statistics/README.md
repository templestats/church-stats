# Annual Church statistical reports — immutable source snapshots

One `YYYY.csv` per **reporting year**. Each row is a verified figure from the Church's *Statistical Report* for that year. Columns: `report_year,new_children_of_record,convert_baptisms,source_url`.

## Why two different source-year offsets?

For **living-endowment eligibility year Y**, this project's *annual new-eligibility cohort proxy* is:

`new_children_of_record[Y - 18] + convert_baptisms[Y - 1]`

Thus the **2026** proxy is `2008 children of record (123,502) + 2025 converts (385,490) = 508,992`. The previously used `94,006` figure belongs to **2006**, not 2008, and is only appropriate for the 2024 eligible year under the 18-year offset.

The 2024, 2025 and 2026 known year-end eligibility proxies are 345,769; 402,380; and 508,992. Every attendance reporting window uses the average of the *daily linear interpolation* of these known annual proxies, with extrapolation only beyond the latest known eligibility year.

On the second Monday of April 2027, the annual workflow will collect the official **2026 statistical report**, add `2026.csv` here, and form the **2027** proxy from `2009 children of record (119,722)` and `2026 converts`. The **2026** proxy is already known and is **not** revised by this update. In future years the annual updater also automatically retrieves the historical child-of-record report from 18 years before the new eligibility year when it is not already archived here.

Each year's source URL is preserved in its CSV. Historical year-end anchor values are not overwritten. If any required official report is unavailable, stale, malformed or implausible, the annual workflow fails without committing new figures; the daily website continues using previously published inputs.

## Statistical interpretation

Children of record are an annual *record intake*, not necessarily a birth or a baptized adult; convert baptisms can include minors. The sum is a proxy for the **annual cohort newly reaching the minimum age/waiting period**, not a count of distinct people already eligible or receiving living endowments. Annualized living sessions divided by this cohort is a proxy ratio, **not** an observed conversion or lifetime endowment rate.
