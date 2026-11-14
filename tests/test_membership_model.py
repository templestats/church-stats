"""Offline tests; no network or Datawrapper credentials required."""
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'temple_attendance_datawrapper3', ROOT/'temple_attendance_datawrapper3.py'
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class MembershipModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = module.MembershipModel(ROOT/'membership_data')

    def test_snapshot_completeness(self):
        self.assertTrue({2024,2025}.issubset(set(self.model.years)))
        for year in self.model.years:
            self.assertEqual(len([k for k in self.model.data[year] if k[0]=='state']), 50)
            self.assertGreaterEqual(len([k for k in self.model.data[year] if k[0]=='country']), 44)
        self.assertEqual(self.model.us_on(date(2024,12,31)), 6_926_618)
        self.assertEqual(self.model.us_on(date(2025,12,31)), 6_925_312)
        self.assertEqual(self.model.estimate(module.MembershipModel.WORLD_KEY,date(2024,12,31)),17_509_781)
        self.assertEqual(self.model.estimate(module.MembershipModel.WORLD_KEY,date(2025,12,31)),17_887_212)

    def test_between_years_and_forward_projection(self):
        k=('state','Utah')
        start=date(2024,12,31)
        end=date(2025,12,31)
        one_quarter=start+timedelta(days=91)
        a=self.model.data[2024][k]
        b=self.model.data[2025][k]
        self.assertAlmostEqual(self.model.estimate(k,one_quarter), a+(b-a)*91/365)
        # Forecast behavior must be tested against *fixed 2024/25 inputs*,
        # not whatever newly published years the production repo contains.
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for year in (2024,2025):
                (folder/f'{year}.csv').write_bytes((ROOT/'membership_data'/f'{year}.csv').read_bytes())
            baseline=module.MembershipModel(folder)
            self.assertEqual(baseline.estimate(k,date(2026,12,31)),b+(b-a))
            self.assertEqual(baseline.status(date(2026,11,13)),'projected')
        self.assertEqual(self.model.status(date(2025,12,31)),'published_year_end')
        self.assertEqual(self.model.status(date(2025,9,1)),'interpolated')

    def test_window_average_is_daily_average(self):
        k=('country','Japan')
        start=date(2025,12,30)
        end=date(2026,1,5)
        expected=sum(self.model.estimate(k,start+timedelta(days=i)) for i in range(7))/7
        self.assertAlmostEqual(self.model.average(k,start,end),expected)
        self.assertAlmostEqual(
            self.model.us_average(start,end),
            sum(self.model.us_on(start+timedelta(days=i)) for i in range(7))/7,
        )

    def test_yearly_update_recasts_2026_and_projects_2027(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for year in (2024,2025):
                (folder/f'{year}.csv').write_bytes((ROOT/'membership_data'/f'{year}.csv').read_bytes())
            with (folder/'2025.csv').open(newline='') as source:
                template=list(csv.DictReader(source))
            for row in template:
                if row['scope']=='state' and row['name']=='Utah':
                    row['members']=str(int(row['members'])+20_000)
            with open(folder/'2026.csv','w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=['scope','name','members','source_url'])
                writer.writeheader()
                writer.writerows(template)
            updated=module.MembershipModel(folder)
            key=('state','Utah')
            self.assertEqual(updated.estimate(key,date(2025,12,31)),self.model.data[2025][key])
            self.assertEqual(updated.estimate(key,date(2026,12,31)),self.model.data[2025][key]+20_000)
            self.assertEqual(updated.estimate(key,date(2027,12,31)),self.model.data[2025][key]+40_000)
            baseline_value = (self.model.data[2024][key] +
                              (self.model.data[2025][key]-self.model.data[2024][key]) *
                              ((date(2026,6,30)-date(2024,12,31)).days/365))
            self.assertNotEqual(updated.estimate(key,date(2026,6,30)),baseline_value)
            self.assertEqual(updated.status(date(2026,6,30)),'interpolated')
            self.assertEqual(updated.status(date(2027,6,30)),'projected')

    def test_duplicate_membership_geography_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for year in (2024,2025):
                (folder/f'{year}.csv').write_bytes((ROOT/'membership_data'/f'{year}.csv').read_bytes())
            with (folder/'2025.csv').open('a') as f:
                f.write('state,Utah,3000000,https://example.com/\n')
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                module.MembershipModel(folder)

    def test_full_pipeline_without_any_membership_network_requests(self):
        # Simulate complete local execution; monkeypatch every legacy membership
        # network function so accidental calls fail the test.
        rows=[]
        for i in range(10):
            d=date(2026,11,1)+timedelta(days=i)
            rows.extend([
                module.DailyActivity(d,'Salt Lake Utah Temple',600,5),
                module.DailyActivity(d,'Paris France Temple',80,1),
            ])
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            with patch.object(sys,'argv',[
                'temple_attendance_datawrapper3.py',
                '--skip-datawrapper',
                '--membership-dir',str(ROOT/'membership_data'),
                '--output-dir',str(out),
            ]), patch.object(module,'scrape_full_history',return_value=rows), \
                 patch.object(module,'build_membership_page_map',side_effect=AssertionError('network membership called')), \
                 patch.object(module,'scrape_world_membership',side_effect=AssertionError('network world called')), \
                 patch.object(module,'update_membership_cache',side_effect=AssertionError('network cache called')):
                rc=module.main()
            self.assertEqual(rc,0)
            for file in ('datawrapper_countries.csv','datawrapper_us.csv',
                         'historical_summary.csv','trend_dashboard.json',
                         'membership_daily_estimates.csv','membership_model_metadata.json',
                         'us_membership_audit.csv',
                         'living_eligibility_daily_estimates.csv',
                         'living_eligibility_annual_anchors.csv',
                         'living_eligibility_model_metadata.json'):
                self.assertTrue((out/file).exists(),file)
            with (out/'datawrapper_countries.csv').open(newline='') as source:
                us=[r for r in csv.DictReader(source) if r['id']=='USA']
            self.assertEqual(len(us),1)
            avg_us=self.model.us_average(date(2026,11,1),date(2026,11,10))
            expected=600*10*(365/10)/avg_us
            self.assertAlmostEqual(float(us[0]['value']),expected)
            with (out/'historical_summary.csv').open(newline='') as source:
                history=list(csv.DictReader(source))
            self.assertGreaterEqual(len(history),1)
            self.assertGreater(float(history[-1]['usa_rate']),0)
            trend=json.loads((out/'trend_dashboard.json').read_text())
            self.assertEqual({x['name'] for x in trend},{'Utah','France'})
            for item in trend:
                self.assertAlmostEqual(item['rate'],item['annualized_endowments']/item['members'],places=5)
            meta=json.loads((out/'membership_model_metadata.json').read_text())
            self.assertEqual(meta['latest_published_membership_year'],self.model.latest_year)

if __name__=='__main__':
    unittest.main()
