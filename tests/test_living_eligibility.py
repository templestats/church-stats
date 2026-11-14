"""No-network regression coverage of the 18-year / 1-year living proxy."""
import csv
import json
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from living_eligibility import LivingEligibilityModel, EligibilityError
import membership_automation as auto

ROOT=Path(__file__).resolve().parents[1]


def synthetic_report(year, children, converts, world=18_100_000):
    return f'''<html><body><h1>Statistical Report, {year}</h1>
    <p>The Church as of December 31, {year}.</p>
    <h2>Church Membership</h2><p>Total Church Membership {world:,}</p>
    <p>New Children of Record during {year} {children:,}</p>
    <p>Converts Baptized during {year} {converts:,}</p><h2>Missionaries</h2></body></html>'''


class LivingEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.model=LivingEligibilityModel(ROOT/'annual_statistics')

    def test_actual_2024_2025_2026_anchors_and_lags(self):
        self.assertTrue({2024,2025,2026}.issubset(set(self.model.years)))
        self.assertEqual([self.model.anchors[y]['total'] for y in (2024,2025,2026)],
                         [345_769,402_380,508_992])
        self.assertEqual(self.model.anchors[2026]['children'],123_502)
        self.assertEqual(self.model.anchors[2026]['converts'],385_490)
        self.assertEqual(self.model.anchors[2026]['child_report_year'],2008)
        self.assertEqual(self.model.anchors[2026]['convert_report_year'],2025)
        self.assertEqual(self.model.on(date(2026,12,31)),508_992)
        self.assertEqual(self.model.status(date(2026,12,31)),'known_lagged_year_end_proxy')

    def test_averaging_matches_daily_values_and_is_smooth(self):
        start=date(2026,11,1); end=start+timedelta(days=6)
        expected=sum(self.model.on(start+timedelta(days=i)) for i in range(7))/7
        self.assertAlmostEqual(self.model.average(start,end),expected)
        self.assertLess(self.model.on(end)-self.model.on(start),1800)
        self.assertEqual(self.model.status(end),'interpolated_between_known_proxies')

    def test_annual_2027_report_changes_2027_not_2026(self):
        early_2026=self.model.on(date(2026,5,5))
        # Recreate the original published baseline, even after real annual
        # reports for 2026 and later have been added to the repository.
        with tempfile.TemporaryDirectory() as base_tmp:
            baseline_folder=Path(base_tmp)
            for yr in (2006,2007,2008,2009,2023,2024,2025):
                shutil.copy2(ROOT/'annual_statistics'/f'{yr}.csv',baseline_folder/f'{yr}.csv')
            projected_2027=LivingEligibilityModel(baseline_folder).on(date(2027,7,1))
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            for yr in (2006,2007,2008,2009,2023,2024,2025):
                shutil.copy2(ROOT/'annual_statistics'/f'{yr}.csv',dest/f'{yr}.csv')
            with (dest/'2026.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=auto.STAT_FIELDS,lineterminator='\n')
                w.writeheader(); w.writerow(dict(report_year=2026,new_children_of_record=95_000,
                    convert_baptisms=420_000,source_url='https://example.com/'))
            updated=LivingEligibilityModel(dest)
            self.assertEqual(updated.latest_year,2027)
            self.assertEqual(updated.anchors[2027]['total'],119_722+420_000)
            self.assertEqual(updated.on(date(2026,5,5)),early_2026)
            self.assertEqual(updated.on(date(2026,12,31)),508_992)
            self.assertNotEqual(updated.on(date(2027,7,1)),projected_2027)

    def test_2025_official_report_parsing(self):
        html=synthetic_report(2025,91_835,385_490,17_887_212)
        r=auto.parse_statistical_report(html,2025,'https://example.com/2025')
        self.assertEqual((r['new_children_of_record'],r['convert_baptisms'],r['world_membership']),
                         (91_835,385_490,17_887_212))
        with self.assertRaisesRegex(auto.ValidationError,'Not the 2026 statistical report'):
            auto.parse_statistical_report(html,2026,'https://example.com/2025')
        legacy='''<h1>Statistical Report, 2008</h1><p>as of December 31, 2008</p>
           <h2>Church Membership</h2>Total Church Membership 13,508,509
           Increase in Children of Record 123,502 Converts Baptized 265,593
           <h2>Missionaries</h2>'''
        r=auto.parse_statistical_report(legacy,2008,'https://example.com/2008')
        self.assertEqual(r['new_children_of_record'],123_502)

    def test_missing_or_suspicious_stat_report_fails(self):
        with self.assertRaisesRegex(auto.ValidationError,'convert_baptisms'):
            auto.parse_statistical_report(synthetic_report(2026,90_000,310_000).replace('Converts Baptized','New Baptisms'),2026,'https://example.com/')
        report=auto.parse_statistical_report(synthetic_report(2026,90_000,310_000),2026,'https://example.com/')
        with self.assertRaisesRegex(auto.ValidationError,'differs >1%'):
            auto.validate_statistical_candidate(report,None,17_200_000)

    def test_next_year_old_child_report_fetched_only_when_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)
            for yr in (2006,2007,2008,2009,2023,2024,2025):
                shutil.copy2(ROOT/'annual_statistics'/f'{yr}.csv',dest/f'{yr}.csv')
            year=2027 # requires convert report 2027 and child report 2010
            returned=[]
            def fetched(y):
                returned.append(y)
                return dict(report_year=y,new_children_of_record=119_000,
                            convert_baptisms=310_000,world_membership=18_200_000,
                            source_url='https://example.com/')
            with patch.object(auto,'fetch_statistical_report',side_effect=fetched):
                pending=auto.prepare_statistical_snapshots(year,dest,18_200_000)
            self.assertEqual(set(returned),{2027,2010})
            self.assertEqual({int(path.stem) for path,_ in pending},{2027,2010})
            self.assertFalse((dest/'2027.csv').exists())
            self.assertFalse((dest/'2010.csv').exists())

    def test_statistical_report_error_does_not_publish_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            mdir=Path(tmp)/'membership_data';mdir.mkdir()
            sdir=Path(tmp)/'annual_statistics';sdir.mkdir()
            for yr in (2006,2007,2008,2009,2023,2024,2025):
                shutil.copy2(ROOT/'annual_statistics'/f'{yr}.csv',sdir/f'{yr}.csv')
            previous=auto.read_csv(ROOT/'membership_data/2025.csv')
            for i in range(110):
                name=f'Country {i}'
                previous[('country',name)]=dict(scope='country',name=name,
                    members=1800+i,source_url='https://example.com/')
            auto.write_snapshot_atomic(mdir/'2025.csv',previous)
            candidate={k:dict(v) for k,v in previous.items()}
            candidate[('world','Worldwide')]['members']+=300_000
            with patch.object(auto,'collect_annual',return_value=(candidate,{})), \
                 patch.object(auto,'prepare_statistical_snapshots',side_effect=auto.ValidationError('stale report')):
                with self.assertRaisesRegex(auto.ValidationError,'stale report'):
                    auto.annual(mdir,date(2027,4,12),statistics_dir=sdir)
            self.assertFalse((mdir/'2026.csv').exists())
            self.assertFalse((sdir/'2026.csv').exists())

    def test_index_methodology_updated_and_js_ids_preserved(self):
        html=(ROOT/'index.html').read_text()
        for text in ('Estimated Members','2008 children of record','Y − 18',
                     'Y − 1','dashboard.js','comparison-table','trend-chart'):
            self.assertIn(text,html)
        self.assertNotIn('most recently reported membership count',html)

if __name__=='__main__': unittest.main()
