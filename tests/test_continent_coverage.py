"""Country/continent denominator regression tests; no network required."""
import importlib.util
import json
import subprocess
import shutil
import sys
import unittest
from datetime import date,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('continent_pipeline',ROOT/'temple_attendance_datawrapper3.py')
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

class ContinentCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=m.MembershipModel(ROOT/'membership_data')

    def test_africa_has_non_temple_members_and_zero_sessions(self):
        start=date(2026,11,1)
        activity=[(m.DailyActivity(start+timedelta(days=i), 'Nairobi Kenya Temple',100,1),
                   m.Geography('country','Kenya','ghana')) for i in range(10)]
        rows=m.build_dashboard_trends(activity,self.model,start,start+timedelta(days=9))
        last='2026-11-10'
        african=[r for r in rows if r['continent']=='Africa' and r['date']==last]
        names={r['name'] for r in african}
        self.assertTrue({'Kenya','Nigeria','South Africa'}.issubset(names))
        nigeria=next(r for r in african if r['name']=='Nigeria')
        self.assertEqual(nigeria['annualized_endowments'],0)
        self.assertTrue(nigeria['membership_only'])
        self.assertGreater(nigeria['members'],0)
        self.assertEqual(len([r for r in rows if r['type']=='state' and r['date']==last]),50)
        expected=sum(m._aggregate_membership_average(self.model,('country',r['name']),
                   start+timedelta(days=3),start+timedelta(days=9)) for r in african)
        self.assertAlmostEqual(sum(r['members'] for r in african),expected,places=3)
        self.assertEqual(sum(r['annualized_endowments'] for r in african),36500)

    def test_reference_world_and_usa_are_full_population(self):
        start=date(2026,11,1)
        activity=[(m.DailyActivity(start+timedelta(days=i),'Nairobi Kenya Temple',100,1),
                   m.Geography('country','Kenya','ghana')) for i in range(10)]
        refs=m.build_dashboard_references(activity,self.model,start,start+timedelta(days=9))
        latest=refs['worldwide'][-1]
        us=refs['usa'][-1]
        self.assertAlmostEqual(latest['members'],self.model.average(m.MembershipModel.WORLD_KEY,
          date(2026,11,4),date(2026,11,10)),places=3)
        self.assertEqual(latest['annualizedSessions'],36500)
        self.assertEqual(us['annualizedSessions'],0)
        self.assertAlmostEqual(us['members'],self.model.us_average(date(2026,11,4),date(2026,11,10)),places=3)

    def test_single_anchor_country_included_without_faked_rate(self):
        model=self.model
        key=('country','Angola')
        prior=model.data[model.latest_year].get(key)
        try:
            model.data[model.latest_year][key]=8779
            d=date(2026,11,1)
            rows=m.build_dashboard_trends([],model,d,d+timedelta(days=6))
            row=next(r for r in rows if (r['type'],r['name'])==key)
            self.assertEqual(row['members'],8779)
            self.assertIsNone(row['rate'])
            self.assertEqual(row['membership_status'],'single_published_anchor')
        finally:
            if prior is None: del model.data[model.latest_year][key]
            else: model.data[model.latest_year][key]=prior

    def test_all_157_published_2025_countries_classified(self):
        # Exact country names from the current expanded 2025 membership
        # snapshot in the repository, including countries without temples.
        names=(ROOT/'tests'/'published_2025_country_names.txt').read_text().splitlines()
        self.assertEqual(len(names),157)
        assigned={name:m.continent_for_country(name) for name in names}
        self.assertEqual(assigned['French Guiana'],'South America')
        self.assertEqual(assigned['Macau'],'Asia')
        self.assertEqual(assigned['Micronesia'],'Oceania')
        self.assertEqual(assigned['Virgin Islands'],'North America')
        self.assertEqual(assigned['Reunion'],'Africa')

    @unittest.skipUnless(shutil.which('node'),'Node required for browser JS regression')
    def test_browser_aggregation_node(self):
        proc=subprocess.run(['node',str(ROOT/'tests'/'test_continent_dashboard.js')],
            cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(proc.returncode,0,proc.stdout+'\n'+proc.stderr)

    def test_index_explains_population_denominator(self):
        html=(ROOT/'index.html').read_text()
        self.assertIn('countries without temples',html)
        self.assertIn('worldwide membership total',html)
        self.assertIn('dashboard.js',html)

if __name__=='__main__': unittest.main()
