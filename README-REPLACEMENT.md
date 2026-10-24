# Church Stats reliability update

This bundle replaces the script and workflow configuration with a deterministic continent classifier and pinned Python dependencies.

## Files to copy into the repository

- `temple_attendance_datawrapper3.py` → repository root, replacing the existing script
- `requirements.txt` → repository root, replacing the existing requirements file
- `.github/workflows/update.yml` → existing scheduled workflow
- `.github/workflows/test.yml` → new test workflow
- `.github/dependabot.yml` → new Dependabot configuration
- `tests/test_continent_mapping.py` → new regression tests

Keep the repository's existing `temple_attendance_output/` directory and any other project files.

## What changes

- Removes `country_converter` from the runtime path and uses a version-controlled ISO-3-to-continent map.
- Pins Python to 3.12.10 and pins the direct Python dependencies.
- Tests that every ISO-3 entry in the pinned `pycountry` dataset has a continent classification, tests representative classifications, and checks that unknown names fail with a useful error.
- Runs compile and regression checks before the production scraper runs.
- Adds a separate test workflow for code changes and Dependabot monthly update proposals.
- Adds a workflow timeout and concurrency guard to avoid overlapping scheduled/manual runs.

## Important limitation

These changes reduce avoidable failures; they cannot guarantee ten years of uninterrupted operation. Source websites, Datawrapper, GitHub-hosted runners, and GitHub Actions can change. Dependabot proposes dependency/action updates monthly; review and test those updates rather than allowing unattended upgrades into the scheduled production workflow.
