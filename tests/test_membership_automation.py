"""Offline regression tests for annual membership publication safeguards."""
import csv
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import membership_automation as auto
from temple_attendance_datawrapper3 import MembershipModel, Geography, DailyActivity, aggregate_window

ROOT=Path(__file__).resolve().parents[1]

class AnnualAutomationTests(unittest.TestCase):
    def test_second_monday_and_retries(self):
        self.assertEqual(auto.second_monday(2027),date(2027,4,12))
        self.assertIsNone(auto.retry_day(date(2027,4,11)))
        for offset in range(7):
            self.assertEqual(auto.retry_day(date(2027,4,12)+timedelta(days=offset)),offset)
        self.assertIsNone(auto.retry_day(date(2027,4,19)))
        self.assertEqual(auto.second_monday(2028),date(2028,4,10))

    def test_modern_geography_must_match_specific_published_year(self):
        html='<html><body><h5>Church Membership</h5><p>53,890</p><p>Last Updated On 31 Dec 2025</p>'\
             '<h3>Worldwide Statistics</h3><p>17,887,212</p></body></html>'
        self.assertEqual(auto.membership_from_html(html,kind='modern',expected_year=2025),53890)
        with self.assertRaisesRegex(auto.ValidationError,'year'):
            auto.membership_from_html(html,kind='modern',expected_year=2026)
        legacy='<html><body>Utah <strong>2,206,370</strong> Total Church Membership '\
               'Worldwide Statistics 17,887,212 Total Church Membership</body></html>'
        self.assertEqual(auto.membership_from_html(legacy,kind='legacy'),2206370)
        world='<div>Total Church Membership <span>17,887,212</span> Last Updated On 31 Dec 2025</div>'
        self.assertEqual(auto.membership_from_html(world,kind='world',expected_year=2025),17887212)

    def test_country_link_discovery(self):
        anchors=''.join(f'<a href="/facts-and-statistics/country/country-{i}">Country {i}</a>' for i in range(160))
        with patch.object(auto,'get',return_value='<html>'+anchors+'</html>'):
            pages=auto.discover_country_pages()
        self.assertEqual(len(pages),160)
        self.assertTrue(pages['Country 24'].endswith('/country-24'))

    def test_bootstrap_expands_both_years_and_preserves_verified_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for y in [2024,2025]:
                (folder/f'{y}.csv').write_bytes((ROOT/'membership_data'/f'{y}.csv').read_bytes())
            baseline=auto.read_csv(folder/'2025.csv')
            archives={y:{('country',f'New Country {i}'):{'scope':'country','name':f'New Country {i}',
                     'members':1000+i+y-2024,'source_url':'https://example.com/historical'} for i in range(151)}
                     for y in [2024,2025]}
            with patch.object(auto,'read_historical',side_effect=lambda year:archives[year]):
                report=auto.bootstrap(folder)
            self.assertGreaterEqual(report['countries_2025'],140)
            expanded=auto.read_csv(folder/'2025.csv')
            self.assertEqual(expanded[('state','Oklahoma')],baseline[('state','Oklahoma')])
            self.assertEqual(expanded[('country','Japan')],baseline[('country','Japan')])
            self.assertEqual(expanded[('country','New Country 4')]['members'],1005)
            model=MembershipModel(folder)
            self.assertTrue(model.has_two_anchors(('country','New Country 4')))
            self.assertGreater(model.estimate(('country','New Country 4'),date(2026,5,1)),1005)

    def test_failed_annual_update_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'2025.csv').write_bytes((ROOT/'membership_data/2025.csv').read_bytes())
            with patch.object(auto,'MIN_COUNTRIES',0), \
                 patch.object(auto,'collect_annual',side_effect=auto.ValidationError('page still says 2025')):
                with self.assertRaisesRegex(auto.ValidationError,'page still says 2025'):
                    auto.annual(folder,date(2027,4,12))
            self.assertFalse((folder/'2026.csv').exists())

    def test_new_country_with_only_one_anchor_not_published_as_fake_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for y in [2024,2025]:
                (folder/f'{y}.csv').write_bytes((ROOT/'membership_data'/f'{y}.csv').read_bytes())
            with (folder/'2025.csv').open(newline='') as source:
                rows=list(csv.DictReader(source))
            rows[0]['source_url']='https://example.com/'
            newer=[dict(r) for r in rows]
            newer.append(dict(scope='country',name='Newland',members='500',source_url='https://example.com/newland'))
            with (folder/'2026.csv').open('w',newline='') as fh:
                writer=csv.DictWriter(fh,fieldnames=auto.FIELDS)
                writer.writeheader();writer.writerows(newer)
            model=MembershipModel(folder)
            self.assertFalse(model.has_two_anchors(('country','Newland')))
            model.require_geographies([Geography('country','Newland','newland','NLD')])
            record=aggregate_window(
                [(DailyActivity(date(2026,6,1),'Newland Temple',20,0),
                  Geography('country','Newland','newland','NLD'))],
                {},date(2026,6,1),date(2026,6,1),1)[0]
            self.assertIsNone(record['annualized_per_member'])
            self.assertEqual(record['endowments'],20)

    def test_validated_annual_snapshot_is_written_once_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'membership_data'; folder.mkdir()
            statistics=Path(tmp)/'annual_statistics'; statistics.mkdir()
            for yr in (2006,2007,2008,2009,2023,2024,2025):
                src=ROOT/'annual_statistics'/f'{yr}.csv'
                (statistics/src.name).write_bytes(src.read_bytes())
            previous=auto.read_csv(ROOT/'membership_data/2025.csv')
            for i in range(110):
                name=f'Extra Country {i}'
                previous[('country',name)]=dict(scope='country',name=name,members=1000+i,
                    source_url='https://example.com/')
            auto.write_snapshot_atomic(folder/'2025.csv',previous)
            candidate={key:dict(value) for key,value in previous.items()}
            candidate[('world','Worldwide')]['members']+=300_000
            candidate[('state','California')]['members']+=10_000
            report=dict(report_year=2026,new_children_of_record=93_000,
                        convert_baptisms=390_000,source_url='https://example.com/report',
                        world_membership=candidate[('world','Worldwide')]['members'])
            pending=[(statistics/'2026.csv', report)]
            with patch.object(auto,'collect_annual',return_value=(candidate,{'checked':True})) as collect, \
                 patch.object(auto,'prepare_statistical_snapshots',return_value=pending):
                result=auto.annual(folder,date(2027,4,12),statistics_dir=statistics)
            self.assertEqual(result['status'],'published')
            self.assertEqual(result['eligibility_year'],2027)
            self.assertEqual(result['eligibility_proxy'],119_722+390_000)
            self.assertEqual(auto.read_csv(folder/'2026.csv')[('world','Worldwide')]['members'],
                             previous[('world','Worldwide')]['members']+300000)
            self.assertEqual(auto.annual(folder,date(2027,4,13),statistics_dir=statistics)['status'],'already_published')
            self.assertEqual(collect.call_count,1)

    def test_candidate_validation_catches_wrong_denominator(self):
        prev=auto.read_csv(ROOT/'membership_data/2025.csv')
        candidate={k:dict(v) for k,v in prev.items()}
        candidate[('state','Oklahoma')]['members']=6_500_000
        with self.assertRaisesRegex(auto.ValidationError,'US sum implausible'):
            auto.validate_candidate(candidate,prev,2026,{},None)

if __name__=='__main__':
    unittest.main()
