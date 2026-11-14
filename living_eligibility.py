"""Living-endowment eligibility proxy from lagged annual Church statistical reports.

A year's proxy equals children of record reported 18 years earlier plus
converts baptized reported one year earlier. These are *annual intake counts*,
NOT a literal census of eligible members. Interpolating between *known lagged*
year-end proxies yields a smooth estimated denominator for attendance windows.

The annual updater populates annual_statistics/YYYY.csv, not the daily job.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

STAT_FIELDS = ('report_year', 'new_children_of_record', 'convert_baptisms', 'source_url')


class EligibilityError(ValueError):
    pass


def read_reports(directory: Path) -> dict[int, dict]:
    reports = {}
    for path in sorted(directory.glob('[0-9][0-9][0-9][0-9].csv')):
        with path.open(newline='', encoding='utf-8-sig') as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not set(STAT_FIELDS).issubset(reader.fieldnames):
                raise EligibilityError(f'{path} must contain: {", ".join(STAT_FIELDS)}')
            rows = list(reader)
        if len(rows) != 1 or int(rows[0]['report_year']) != int(path.stem):
            raise EligibilityError(f'{path} must contain one matching reporting-year row')
        row = rows[0]
        try:
            children = int(row['new_children_of_record'])
            converts = int(row['convert_baptisms'])
        except (TypeError, ValueError) as exc:
            raise EligibilityError(f'Non-integer annual statistics in {path}') from exc
        if not 30_000 <= children <= 200_000:
            raise EligibilityError(f'Implausible children-of-record count {children:,} in {path}')
        if not 100_000 <= converts <= 650_000:
            raise EligibilityError(f'Implausible convert-baptism count {converts:,} in {path}')
        if not row['source_url'].startswith('https://'):
            raise EligibilityError(f'Missing source URL for {path}')
        reports[int(path.stem)] = dict(children=children, converts=converts,
                                      source_url=row['source_url'])
    return reports


class LivingEligibilityModel:
    CHILD_LAG = 18
    CONVERT_LAG = 1

    def __init__(self, directory: Path):
        self.directory = directory
        self.reports = read_reports(directory)
        self.anchors = {}
        # An eligible year often has no same-year statistical report yet.
        # E.g. the 2026 eligible anchor is known from 2008 + 2025 reports.
        eligible_years = ({y + self.CHILD_LAG for y in self.reports}
                          | {y + self.CONVERT_LAG for y in self.reports})
        for year in sorted(eligible_years):
            child_year = year - self.CHILD_LAG
            convert_year = year - self.CONVERT_LAG
            if child_year not in self.reports or convert_year not in self.reports:
                continue
            children = self.reports[child_year]['children']
            converts = self.reports[convert_year]['converts']
            self.anchors[year] = dict(children=children, converts=converts,
                                      total=children + converts,
                                      child_report_year=child_year,
                                      convert_report_year=convert_year)
        self.years = sorted(self.anchors)
        if len(self.years) < 2:
            raise EligibilityError('Need two years of complete lagged living-eligibility anchors')
        for left, right in zip(self.years, self.years[1:]):
            if right != left+1:
                raise EligibilityError(f'Gap in eligible-proxy anchors: {left} to {right}')

    @property
    def latest_year(self) -> int:
        return self.years[-1]

    @lru_cache(maxsize=80000)
    def on(self, day: date) -> float:
        years = self.years
        if day <= date(years[0], 12, 31):
            left, right = years[:2]
        elif day >= date(years[-1], 12, 31):
            left, right = years[-2:]
        else:
            left, right = years[:2]
            for a,b in zip(years, years[1:]):
                if date(a,12,31) <= day <= date(b,12,31):
                    left, right = a,b
                    break
        d1,d2 = date(left,12,31),date(right,12,31)
        t = (day-d1).days/(d2-d1).days
        value = self.anchors[left]['total'] + (self.anchors[right]['total']-self.anchors[left]['total'])*t
        if value <= 0:
            raise EligibilityError(f'Nonpositive projected eligibility proxy on {day}')
        return value

    @lru_cache(maxsize=80000)
    def average(self, start: date, end: date) -> float:
        if end < start:
            raise EligibilityError('Invalid eligibility averaging window')
        n = (end-start).days+1
        return sum(self.on(start + timedelta(days=i)) for i in range(n))/n

    def status(self, day: date) -> str:
        if day > date(self.latest_year,12,31):
            return 'projected'
        if day < date(self.years[0],12,31):
            return 'backward_extrapolated'
        if day == date(day.year,12,31) and day.year in self.anchors:
            return 'known_lagged_year_end_proxy'
        return 'interpolated_between_known_proxies'
