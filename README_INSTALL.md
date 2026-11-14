# Church Stats — Automated Country Membership + Annual Refresh

## Overview

This is a complete, ready-to-commit update to the existing Church Stats project.
The daily `temple_attendance_datawrapper3.py` continues to scrape **only temple attendance**; no membership website requests are made by the daily job. Membership is read from version-controlled year-end CSV snapshots. Every US state, country/territory with published positive membership in two years, and worldwide membership get independent **daily** interpolated/projected denominators. The US denominator remains the sum of the 50 state estimates.

## Files to add or replace (one commit)

```text
church-stats/
├── temple_attendance_datawrapper3.py          REPLACE existing
├── membership_automation.py                   NEW
├── membership_data/
│   ├── 2024.csv                               REPLACE existing
│   ├── 2025.csv                               REPLACE existing
│   └── README.md                              NEW / REPLACE
├── .github/workflows/
│   └── membership-refresh.yml                 NEW (keep all other workflows)
└── tests/
    ├── test_membership_model.py               NEW / REPLACE
    └── test_membership_automation.py          NEW
```

Keep the **same names and folders**. Copy all files in one commit to the default branch. Do not replace or delete your existing attendance workflow. Do not commit `membership_update_reports/` or `temple_attendance_output/` manually.

### Simplest Git installation (Mac)

If you already have a local clone of the repository, extract the ZIP, copy these files into that clone while preserving paths, then run:

```bash
git add temple_attendance_datawrapper3.py membership_automation.py membership_data/ .github/workflows/membership-refresh.yml tests/
git commit -m "Automate annual membership snapshots and full-country coverage"
git push
```

If you prefer GitHub's web interface, upload each file to the corresponding path, including the hidden `.github/workflows` directory, and commit **all files before** running the workflow. A partial install can temporarily break the daily job.

## What happens automatically at installation

A push that includes `membership_automation.py` or `.github/workflows/membership-refresh.yml` triggers the **bootstrap** job:

1. Download preserved April 2025 / April 2026 country statistics (for year-end 2024 / 2025) from `acbass49/scrape_lds_stats` (a *third-party archive of Church-published data*).
2. Add every country with a **positive published figure in each individual year** to its corresponding snapshot. A country needs two annual anchors to receive a modeled per-member rate. Preserve all your existing 50-state counts, 44 validated country counts, and worldwide totals unchanged.
3. Run offline regression tests. If they pass, commit expanded 2024 and 2025 CSVs with GitHub Actions credentials.
4. On the next scheduled daily attendance update, those countries become available as denominators with no additional edits.

**No 2026 membership values are invented.** Countries for which the historical archive has 0 or no published membership are not given fake denominators. A new temple in a country with only one annual count contributes to worldwide endowments, but has no country-specific per-member rate until the Church publishes a second annual count.

If the bootstrap job fails validation, the old 2024/2025 files remain unchanged. Look in GitHub → Actions → `Church Stats - Annual membership refresh` → `bootstrap`.

## Annual schedule and retries

GitHub Actions schedules the workflow at **9:23 a.m. America/Los_Angeles** on April 9–21. The Python guard performs the full download only on **the Monday after the second Sunday in April** and, if needed, during the following six days. **Next: Monday April 12, 2027** for 2026 year-end figures. Dates outside the seven-day window exit immediately with no data request.

- The updater retrieves the Church's current official worldwide, 50-state, and full country/territory pages.
- Official worldwide and country pages must report `Last Updated On 31 Dec YYYY` matching the intended year; the importer does **not** accept a fresh page with a stale reporting year.
- Validation includes: at least 140 positive published-country counts, preservation of previously reported countries, complete 50-state coverage, plausible US/world totals, a cross-check against the published US country total, and individual/geographic year-over-year change thresholds.
- Pass: atomically write `membership_data/YYYY.csv`, commit via GitHub Actions, and leave prior annual snapshots unchanged. The **next daily attendance run** automatically recasts last year's rates and projects the new year from the latest net changes.
- Fail: **do not create/commit the new annual CSV**; the public website and last-good membership snapshots remain unchanged. Retry the next day. If the seventh attempt fails, the job is marked **failed** for a GitHub Actions notification.

Note: A first failure may be a genuinely large membership change that the conservative safeguards flag. The workflow will then reject the data and notify you rather than silently publish it; that is intentional.

## Private (not published on website) error reports

Failures appear in GitHub Actions logs, with the candidate audit in `membership-refresh-diagnostics-<run>` artifacts (90-day retention). These are **not** copied to GitHub Pages or Datawrapper. **If your GitHub repository is public, workflow logs/artifacts are not strictly confidential**; they contain only public statistics and error messages, not passwords.

To receive a private email notification, in GitHub:

1. Open **Settings → Notifications**.
2. Under **System → Actions**, choose **Email** and **Only notify for failed workflows**.
3. Ensure you are the user who adds/owns the scheduled workflow. GitHub sends scheduled-workflow notifications to the user associated with the schedule.

If you don't opt in, GitHub cannot guarantee that you receive a private email. The workflow **does not** send emails directly and requires no email service credentials.

## GitHub repository permissions

The workflow requests `contents: write` so GitHub Actions can commit the validated snapshots. If the `git push` step reports an HTTP 403 or permission-denied error, check **Repository → Settings → Actions → General → Workflow permissions**. Repository or organization policies may restrict the token; the update cannot auto-commit until permission is granted.

## Testing

From the repo root, after installing `requests`, `beautifulsoup4`, `pycountry`:

```bash
python -m py_compile temple_attendance_datawrapper3.py membership_automation.py
python -m unittest discover -s tests -v
python membership_automation.py due --today 2027-04-12
```

Expected for `due`: `"retry_day": 0`. For an immediate one-time bootstrap, use **Actions → Church Stats - Annual membership refresh → Run workflow → bootstrap**. No manual intervention is required if the installation push runs successfully. To manually retry the annual fetch once 2026 values are live, choose `annual`; the scraper still validates before committing anything.

## Limits and exceptions

- Online source parsing and automatic Git pushes cannot be exercised by the offline tests. **Review the first bootstrap Action log** and the first live April refresh in 2027 to confirm the Church's HTML has not changed.
- If the church stops publishing a previously available country value, the updater refuses to replace it silently and will alert after retries.
- New temple names must still be recognized by the existing `locate_temple()` function (mostly country and state suffix matching plus overrides). Unusual new naming conventions can still require manual correction.
- No new model-year values go public until they have passed validation; even a successful annual job doesn't itself update Datawrapper. The next daily attendance job does.
- Historical archived country data should be described as derived from **archived scrapes of published Church statistics**, not as independently audited original Church filings.
