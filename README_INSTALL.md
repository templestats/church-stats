# Church Stats — 18-year/1-year living-endowment model + automatic annual statistical reports

## What changed

- **Geographic rates remain as previously implemented.** Annual country, territory, US state and worldwide membership snapshots are linearly interpolated to daily estimates. Each 7-day or longer window uses the matching daily-average denominator. Verified 2024/2025 `membership_data/*.csv` remain untouched.
- **Living-endowment rates now use a time-aligned annual new-eligibility proxy:** year Y children of record **from report Y−18** plus convert baptisms **from report Y−1**. Each year's known annual proxy is linearly interpolated to daily values; after the newest known year, the latest annual absolute change is projected forward.
- **Corrects the 2026 child cohort:** the old `94,006` constant came from **2006**. The correct 2008 count for the 2026 cohort is **123,502**. With the 2025 convert baptisms of **385,490**, the 2026 year-end proxy is **508,992**.
- **Adds official historical sources** as immutable per-reporting-year CSV snapshots in `annual_statistics/`. Base reports are from 2006, 2007, 2008, 2009, 2023, 2024, 2025. Their official citations are preserved in the files.
- **Changes your existing annual GitHub Actions workflow** to collect the Church statistical report (children of record, converts, worldwide members) alongside the annual geographic membership snapshot. Before publishing either, it verifies source year and plausible data, cross-checks worldwide totals, and ensures the future eligibility anchor can be formed. It automatically fetches the needed 18-year-old historical report if not already archived.
- **Rebuilds `index.html`**, preserving the existing three Datawrapper embed IDs/URLs and interactive explorer element IDs, explaining the new denominator and cohort assumptions, and displaying estimated membership rounded to whole persons (full-precision calculations remain in JSON/Python).
- **Adds diagnostic outputs** (`living_eligibility_daily_estimates.csv`, `living_eligibility_annual_anchors.csv`, `living_eligibility_model_metadata.json`) into your usual `temple_attendance_output/` folder.
- **Includes updated offline regression tests** that will continue to work after future annual snapshots are added. Do not delete your repository's existing `test_continent_mapping.py` or other tests.

## Installation: upload these files to the matching GitHub paths

Extract the ZIP; **upload its contents over the corresponding files in your existing repository**, preserving the folder hierarchy:

```text
church-stats/
  index.html                                    REPLACE
  temple_attendance_datawrapper3.py            REPLACE
  membership_automation.py                     REPLACE
  living_eligibility.py                        NEW
  .github/workflows/membership-refresh.yml    REPLACE (hidden .github folder)
  annual_statistics/                            NEW FOLDER
    2006.csv
    2007.csv
    2008.csv
    2009.csv
    2023.csv
    2024.csv
    2025.csv
    README.md
  tests/
    test_membership_model.py                   REPLACE
    test_membership_automation.py              REPLACE (corrected failing test included)
    test_living_eligibility.py                 NEW
  README_INSTALL.md                             REPLACE
```

**VERY IMPORTANT: The ZIP deliberately does NOT contain `membership_data/2024.csv` or `membership_data/2025.csv`. DO NOT overwrite or delete your existing `membership_data/` folder.** The previous country-expansion bootstrap may have added countries to those CSVs; restoring older bundled copies could silently lose those additions. Keep all your current `membership_data/YYYY.csv` files.

Also keep your existing `dashboard.js`, `dashboard.css`, daily update workflow, secrets and other repository files. This update does not change them.

On macOS the `.github` directory is hidden in Finder. In GitHub's browser editor, navigate to `.github` → `workflows` and replace `membership-refresh.yml` there explicitly. Never place that YAML at the repository root.

If using a local repository clone, copy the extracted files into the clone (preserve paths) and then run:

```bash
git add index.html temple_attendance_datawrapper3.py membership_automation.py living_eligibility.py \
  annual_statistics/ .github/workflows/membership-refresh.yml tests/ README_INSTALL.md
git commit -m 'Model lagged living eligibility and automate statistical reports'
git push
```

### Verify after installing

1. GitHub → **Actions** → `Church Stats - Annual membership refresh`. A push to `membership_automation.py` triggers the existing bootstrap, which still expands historic countries and now tests the living model too. It may attempt the external archival scrape; if it fails, it won't change snapshots.
2. Go to **Actions** → your regular daily `Update Church Stats` workflow → **Run workflow**, or allow the next daily run to execute.
3. Check that `temple_attendance_output/living_eligibility_model_metadata.json` says `latest_known_eligibility_year: 2026`, and `living_eligibility_annual_anchors.csv` includes a 2026 total of `508992`.
4. Check the updated `index.html` methodology on the site and confirm comparison-table memberships are rounded to whole people.
5. If a workflow fails, the existing site's last successful outputs should remain; inspect its Actions log for validation errors.

## Annual schedule and what happens in April 2027

No extra annual workflow or manual registration is required. The existing annual workflow runs **the Monday after the second Sunday of April**, first on **Monday, April 12, 2027**, at 9:23 a.m. Pacific. On that date it will collect **2026 year-end membership by state/country/world** plus the Church's **2026 annual statistical report**. It also requires the **2009 children-of-record figure**, which is already saved in this ZIP.

- When both collections pass validation, GitHub Actions commits `membership_data/2026.csv` **and** `annual_statistics/2026.csv` together. The next daily run automatically recasts geographic membership projections for 2026 and the eligibility projection for **2027**.
- **2026 living eligibility values are not recast**: the 2026 endpoint was already known from the 2008 and 2025 reports. Thus reporting year 2026 statistics affect the **2027** living eligibility denominator.
- In April 2028 the updater will also fetch the 2010 historical children's report if needed for the 2028 living eligibility endpoint. It continues indefinitely with the same code so long as the official historical and new report pages remain available in recognized format.
- On failure, no newly scraped annual data is committed. Daily website updates keep using the last verified membership/eligibility snapshots. The workflow retries on the next six days, then fails with a GitHub notification (subject to your account's Actions notification settings).
- Workflow run artifacts and logs are *not* published to your GitHub Pages website, although logs may be publicly accessible in a public GitHub repository.

## Testing

After copying into your **existing repo** (with `membership_data/` still present):

```bash
python -m pip install requests beautifulsoup4 pycountry
python -m py_compile temple_attendance_datawrapper3.py membership_automation.py living_eligibility.py
python -m unittest discover -s tests -v
python membership_automation.py due --today 2027-04-12
```

The release's **22 offline tests pass**, including a mocked daily pipeline and simulated annual publication with data rejected on incomplete or incorrect source-year statistics. The repository may have additional tests. Tests were also run against a simulated future repository containing 2026 membership and 2026 statistical-report snapshots.

## Accuracy and operating limits

- The annual cohort proxy is an analytical assumption, **not** an actual count of eligible adults or the proportion receiving a living endowment. Children of record can include people who never join, and converts can be children; this is explained on the website.
- **Live Church report scraping and GitHub publication cannot be verified offline.** The 2026 statistical report does not exist as of November 2026. The annual source validator accepts only a report explicitly marked with the expected reporting year and year-end date, with reasonable values. If Church pages change layout, the updater will fail and notify rather than publish an incorrect denominator. The first 2027 run remains the end-to-end live test.
- Geographic membership data is separate from the annual child/convert report and remains version controlled. No day-to-day membership scraping is reintroduced.
- If the Church stops publishing a value or published figures are anomalous, automatic publication is withheld rather than silently correcting them.

## Official historical reports included

- 2006 children of record: 94,006 — source linked in `annual_statistics/2006.csv`
- 2007 children of record: 93,698 — `2007.csv`
- 2008 children of record: 123,502 — `2008.csv`
- 2009 children of record: 119,722 — `2009.csv`
- 2023 converts: 251,763 — `2023.csv`
- 2024 converts: 308,682 — `2024.csv`
- 2025 converts: 385,490 — `2025.csv`

These published figures have been confirmed against the Church's official statistical reports. Each CSV preserves its individual source URL.
