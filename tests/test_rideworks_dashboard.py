"""Synthetic calendar/evidence/goal acceptance, with explicit expected values."""
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import urlencode

from fit_fixture import make_fit
from rideworks import store as store_module
from rideworks.dashboard import average_power, dashboard, goal_progress, mileage, needed_weekly, weekly_goal
from rideworks.goals import annual_goal, browser_zone, set_annual_goal, target_miles
from rideworks.history import presentation
from rideworks.performance import rebuild_performance
from rideworks.settings import Settings
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.web import Application


def activity(identity, stamp, metres, kind='Virtual Ride', origin='file'):
    dt = datetime.fromisoformat(stamp) if stamp else None
    return dict(activity_id=identity, start_time=stamp, activity_type=kind,
                absolute_time=bool(dt and dt.tzinfo), date_key=stamp,
                distance=metres, distance_source={'context':'Strava API summary' if origin=='api' else 'FIT session'})


class CalendarTests(TestCase):
    def test_cycling_distance_provenance_zero_and_missing_evidence(self):
        rows=[activity('1','2026-02-01T12:00:00+00:00',1609.344),
              activity('2','2026-02-02T12:00:00+00:00',3218.688,'Ride','api'),
              activity('3','2026-02-02T12:00:00+00:00',0,'Biking','api'),
              activity('4','2026-02-02T12:00:00+00:00',999,'Run'),
              activity('5','2026-02-02T12:00:00',None),activity('6',None,999)]
        result=mileage(rows,'America/Los_Angeles',as_of=datetime(2026,2,2,20,tzinfo=timezone.utc))
        ytd=result['ytd'];self.assertEqual(ytd['miles'],3)
        self.assertEqual((ytd['file_count'],ytd['api_count'],ytd['contributing_activities']),(1,2,3))
        self.assertEqual((ytd['file_miles'],ytd['api_miles']),(1,2))
        self.assertEqual((ytd['distance_unavailable'],ytd['date_unavailable_excluded']),(1,1))
        self.assertEqual(result['diagnostics']['excluded_noncycling'],1)
        self.assertEqual(result['diagnostics']['timezone_unknown'],1)

    def test_browser_local_year_edge_and_unknown_source_date(self):
        rows=[activity('1','2026-01-01T00:30:00+00:00',1609.344),
              activity('2','2026-01-01T01:00:00',1609.344)]
        now=datetime(2026,1,1,12,tzinfo=timezone.utc)
        la=mileage(rows,'America/Los_Angeles',as_of=now)
        tokyo=mileage(rows,'Asia/Tokyo',as_of=now)
        self.assertEqual(la['ytd']['miles'],1);self.assertEqual(tokyo['ytd']['miles'],2)
        self.assertEqual(la['diagnostics']['timezone_unknown'],1)
        self.assertEqual(rows[0]['start_time'],'2026-01-01T00:30:00+00:00')

    def test_seven_day_and_previous_boundaries_include_today_and_leap_day(self):
        rows=[activity(str(i),stamp,1609.344) for i,stamp in enumerate([
            '2024-02-17T00:00:00+00:00','2024-02-23T23:59:59+00:00',
            '2024-02-24T00:00:00+00:00','2024-02-29T12:00:00+00:00',
            '2024-03-01T12:00:00+00:00','2024-03-01T23:00:00+00:00'])]
        result=mileage(rows,'UTC',as_of=datetime(2024,3,1,18,tzinfo=timezone.utc))
        self.assertEqual(result['last7']['miles'],3);self.assertEqual(result['prior7']['miles'],2)
        self.assertEqual(result['last7']['start'],'2024-02-24')
        self.assertEqual(result['prior7']['end_exclusive'],'2024-02-24')
        self.assertEqual(result['diagnostics']['future_excluded'],1)
        self.assertEqual(len(result['weeks']),12)
        self.assertEqual(result['weeks'][-1]['start'],'2024-02-26')
        self.assertEqual(result['weeks'][-1]['miles'],2)

    def test_dst_uses_calendar_days_and_empty_or_unavailable_distance(self):
        rows=[activity('1','2026-03-08T08:00:00+00:00',1609.344),
              activity('2','2026-03-02T08:00:00+00:00',1609.344)]
        result=mileage(rows,'America/Los_Angeles',as_of=datetime(2026,3,9,6,tzinfo=timezone.utc))
        self.assertEqual(result['today'],'2026-03-08');self.assertEqual(result['last7']['miles'],2)
        self.assertEqual(mileage([],'UTC',as_of=datetime(2026,3,9,tzinfo=timezone.utc))['last7']['miles'],0)
        missing=mileage([activity('1','2026-03-09T00:00:00+00:00',None)],'UTC',as_of=datetime(2026,3,9,tzinfo=timezone.utc))
        self.assertIsNone(missing['last7']['miles'])

    def test_goal_leap_year_pace_percent_remaining_and_over_target(self):
        result=goal_progress(2024,'2024-02-29',80,'366')
        self.assertEqual((result['calendar_days_elapsed'],result['calendar_days_in_year']),(60,366))
        self.assertEqual(result['target_to_date'],60);self.assertEqual(result['pace_difference'],20)
        self.assertAlmostEqual(result['percent'],100*80/366);self.assertEqual(result['remaining_miles'],286)
        over=goal_progress(2026,'2026-12-31',400,'365')
        self.assertEqual(over['remaining_miles'],0);self.assertGreater(over['percent'],100)
        self.assertIsNone(goal_progress(2026,'2026-01-01',0,None))
        self.assertIsNone(goal_progress(2026,'2026-01-01',None,'365'))

    def test_timezone_validation_and_absolute_as_of_required(self):
        for name in ('','No/Such_Zone','../etc/passwd','a'*129):
            with self.assertRaises(ValueError):browser_zone(name)
        with self.assertRaises(ValueError):mileage([],'UTC',as_of=datetime(2026,1,1))

    def test_current_needed_average_and_completed_week_history(self):
        rows=[activity(str(i),stamp,100*1609.344) for i,stamp in enumerate([
            '2026-01-01T12:00:00+00:00','2026-09-28T12:00:00+00:00','2026-10-05T12:00:00+00:00'])]
        data=mileage(rows,'UTC',as_of=datetime(2026,10,7,18,tzinfo=timezone.utc))
        data['target_miles']='1000'
        chart=weekly_goal(data)
        self.assertEqual(data['this_week']['miles'],100)
        self.assertEqual(chart[-2]['ytd_miles'],200)
        self.assertAlmostEqual(chart[-2]['needed_miles_per_week'],800*7/88)
        self.assertEqual(chart[-2]['bar_miles'],100)
        self.assertEqual(chart[-2]['bar_kind'],'actual')
        self.assertEqual(chart[-1]['actual_miles'],100)
        self.assertEqual(chart[-1]['as_of_day'],'2026-10-07')
        self.assertEqual(chart[-1]['bar_miles'],data['this_week']['miles'])
        self.assertAlmostEqual(chart[-1]['needed_miles_per_week'],700*7/85)
        self.assertEqual(chart[-1]['bar_kind'],'actual')
        progress=goal_progress(2026,'2026-10-07',300,'1000')
        self.assertEqual(progress['needed_miles_per_week'],chart[-1]['needed_miles_per_week'])
        self.assertEqual(progress['remaining_calendar_days'],85)
        data['target_miles']='150'
        met=weekly_goal(data)
        self.assertEqual(met[-2]['needed_miles_per_week'],0)
        self.assertEqual(met[-1]['bar_miles'],100)
        self.assertEqual(met[-1]['actual_miles'],100)

    def test_needed_average_met_goal_year_end_leap_and_missing(self):
        self.assertEqual(needed_weekly(2026,date(2026,12,31),100,'100'),0)
        self.assertEqual(needed_weekly(2026,date(2026,12,31),101,'100'),0)
        self.assertIsNone(needed_weekly(2026,date(2026,12,31),99,'100'))
        self.assertAlmostEqual(needed_weekly(2024,date(2024,2,29),80,'366'),286*7/306)
        self.assertIsNone(needed_weekly(2026,date(2026,1,1),None,'100'))
        self.assertIsNone(needed_weekly(2026,date(2026,1,1),0,None))
        self.assertIsNone(needed_weekly(2026,date(2025,12,28),50,'100'))

    def test_weekly_goal_calendar_year_and_timezone_edges(self):
        rows=[activity('1','2026-01-01T00:30:00+00:00',1609.344),
              activity('2','2026-01-01T12:00:00',1609.344)]
        for zone,expected in [('America/Los_Angeles',1),('Asia/Tokyo',2)]:
            data=mileage(rows,zone,as_of=datetime(2026,1,1,12,tzinfo=timezone.utc));data['target_miles']='366'
            chart=weekly_goal(data)
            self.assertEqual(chart[-1]['ytd_miles'],expected)
            self.assertAlmostEqual(chart[-1]['needed_miles_per_week'],(366-expected)*7/364)
            self.assertTrue(all(w['needed_miles_per_week'] is None for w in chart[:-1]))
            self.assertEqual(data['this_week']['miles'],2)

    def test_weekly_chart_preserves_unavailable_without_default_goal(self):
        data=mileage([activity('1','2026-10-05T12:00:00+00:00',None)],'UTC',as_of=datetime(2026,10,7,tzinfo=timezone.utc))
        data['target_miles']='1000'
        chart=weekly_goal(data)
        self.assertIsNone(chart[-1]['actual_miles']);self.assertIsNone(chart[-1]['bar_miles'])
        self.assertIsNone(chart[-1]['needed_miles_per_week'])
        data['target_miles']=None
        self.assertTrue(all(w['needed_miles_per_week'] is None for w in weekly_goal(data)))
        known=mileage([activity('1','2026-10-05T12:00:00+00:00',1609.344)],'UTC',as_of=datetime(2026,10,7,tzinfo=timezone.utc))
        known['target_miles']=None
        self.assertEqual(weekly_goal(known)[-1]['bar_miles'],1)
        self.assertEqual(weekly_goal(known)[-1]['bar_kind'],'actual')


class DashboardTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'data');self.addCleanup(self.store.close)
        self.settings=Settings(self.store.data_dir,credentials=lambda:None)
        self.app=Application(self.store.data_dir,settings_factory=lambda root:self.settings)

    def post(self,**fields):
        fields={'nonce':self.settings.nonce,'tz':'America/Los_Angeles',**fields}
        return self.settings.post('/settings/annual-goal',urlencode(fields).encode(),'http://127.0.0.1:8765')

    def test_goal_unset_set_update_clear_restart_and_no_default(self):
        year=datetime.now(timezone.utc).astimezone(browser_zone('America/Los_Angeles')).year
        set_annual_goal(self.store,year-1,'80')
        self.assertIsNone(annual_goal(self.store,year))
        html=self.app.get('/?home_tz=America%2FLos_Angeles')[2].decode()
        self.assertIn('Set annual goal',html);self.assertNotIn('2,500',html)
        self.assertEqual(self.post(target_miles='1234.50')[0],303)
        self.assertEqual(annual_goal(self.store,year)['target_miles'],'1234.50')
        with Store(self.store.data_dir) as restarted:self.assertEqual(annual_goal(restarted,year)['target_miles'],'1234.50')
        self.assertEqual(self.post(target_miles='1500')[0],303)
        self.assertEqual(annual_goal(self.store,year)['target_miles'],'1500')
        self.assertEqual(self.post(clear='1')[0],303);self.assertIsNone(annual_goal(self.store,year))
        self.assertEqual(annual_goal(self.store,year-1)['target_miles'],'80')

    def test_failed_goal_write_rolls_back_and_does_not_claim_sync_failure(self):
        self.post(target_miles='123')
        before=[tuple(r) for r in self.store.connection.execute('SELECT * FROM annual_mileage_goals')]
        self.store.connection.executescript("""CREATE TRIGGER synthetic_goal_failure AFTER UPDATE ON annual_mileage_goals
            BEGIN SELECT RAISE(FAIL,'private synthetic database error'); END;""")
        response=self.post(target_miles='456')
        self.assertEqual(response[0],500)
        self.assertIn(b'previous target is retained',response[2])
        self.assertNotIn(b'private synthetic',response[2]);self.assertNotIn(b'Sync',response[2])
        self.assertEqual(before,[tuple(r) for r in self.store.connection.execute('SELECT * FROM annual_mileage_goals')])

    def test_goal_validation_does_not_change_saved_target(self):
        self.post(target_miles='123')
        for value in ('','0','-1','NaN','inf','1e3','100000.01','9'*33,' 123','1,234','123 '):
            with self.subTest(value=value):self.assertEqual(self.post(target_miles=value)[0],400)
        rows=self.store.connection.execute('SELECT target_miles FROM annual_mileage_goals').fetchall()
        self.assertEqual([r[0] for r in rows],['123'])
        self.assertEqual(target_miles('100000'),Decimal('100000'))

    def test_goal_nonce_origin_duplicate_fields_and_get_method(self):
        original=self.settings.nonce
        body=urlencode(dict(nonce=original,tz='UTC',target_miles='100')).encode()
        self.assertEqual(self.settings.post('/settings/annual-goal',body,'https://evil.invalid')[0],403)
        self.assertEqual(self.settings.post('/settings/annual-goal',body,'http://127.0.0.1:8765')[0],303)
        self.assertEqual(self.settings.post('/settings/annual-goal',body,'http://127.0.0.1:8765')[0],403)
        bad=urlencode(dict(nonce=self.settings.nonce,tz='UTC',target_miles='100')).encode()+b'&target_miles=200'
        self.assertEqual(self.settings.post('/settings/annual-goal',bad,'http://127.0.0.1:8765')[0],403)
        self.assertEqual(self.post(tz='unknown',target_miles='100')[0],400)
        self.assertEqual(self.app.get('/settings/annual-goal')[0],404)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM annual_mileage_goals').fetchone()[0],1)

    def test_goal_uses_browser_current_year_near_utc_boundary(self):
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return datetime(2026,1,1,0,30,tzinfo=timezone.utc)
        with patch('rideworks.settings.datetime',Clock):
            self.post(target_miles='100')
            self.post(tz='Asia/Tokyo',target_miles='200')
            html=self.app.get('/settings?tz=America%2FLos_Angeles')[2].decode()
        self.assertIn('goal · 2025',html)
        self.assertEqual(annual_goal(self.store,2025)['target_miles'],'100')
        self.assertEqual(annual_goal(self.store,2026)['target_miles'],'200')

    def test_home_browser_route_and_old_filter_redirect_preserve_query(self):
        self.assertIn('<h1>Home</h1>',self.app.get('/')[2].decode())
        self.assertIn('browser timezone',self.app.get('/?home_tz=bad')[2].decode())
        html=self.app.get('/?home_tz=UTC')[2].decode()
        for heading in ('Recent Mileage','This Week','Last 7 Days','Current 42-day best','Latest eligible 20-minute ride','Mileage Progress','20-minute Performance'):
            self.assertIn(heading,html)
        self.assertIn('href="/activities"',html);self.assertIn('href="/" class="active"',html)
        self.assertIn('No cycling Activities yet.',html);self.assertIn('Unavailable',html)
        browser=self.app.get('/activities')[2].decode();self.assertIn('action="/activities"',browser)
        for query in ('q=foo','type=all&sort=oldest&page=2&tz=Asia%2FTokyo','tz=UTC','from=2026-01-01'):
            self.assertEqual(self.app.get('/?'+query)[0],303)
            self.assertEqual(self.app.legacy_browser_target('/?'+query),'/activities?'+query)

    def test_actual_file_distance_precedence_api_fallback_and_metadata_only(self):
        raw=int(datetime(2026,1,1,tzinfo=timezone.utc).timestamp())-631065600
        path=self.root/'synthetic.fit';path.write_bytes(make_fit(distance=1609.344,avg_power=123,session_start_time=raw,
            session_timestamp=raw+2,timestamps=(raw,raw+1,raw+2),lap_start_time=raw,lap_timestamp=raw+2,
            event_timestamps=(raw,raw+2)))
        native=self.store.import_fit(path)
        native_start=self.store.get_source(native['source_id'])['summary']['start_time']
        export=self.root/'export';export.mkdir()
        import csv
        with (export/'activities.csv').open('w',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['Activity ID','Activity Name','Activity Type','Activity Date','Filename'])
            writer.writerow(['1','Synthetic overlap','Virtual Ride',native_start,'synthetic.fit'])
        (export/'synthetic.fit').write_bytes(path.read_bytes())
        self.store.import_strava_export(export)
        # Explicit established API identity for a controlled overlap, not a matching heuristic.
        for identity,stamp,metres in ((1,native_start,99999),(2,'2026-01-01T00:00:00Z',3218.688)):
            item=normalize(dict(id=identity,name='Synthetic ride',type='Ride',sport_type='VirtualRide',start_date=stamp,distance=metres,elapsed_time=2,average_watts=999))
            apply_observations(self.store,[item],42,1790000000)
        overlap=self.store.connection.execute("SELECT activity_id FROM strava_api_activities WHERE external_id='1'").fetchone()[0]
        self.assertEqual(overlap,native['activity_id'])
        rows=[presentation(s) for s in self.store.activity_history()]
        self.assertEqual(next(r for r in rows if r['activity_id']==overlap)['distance'],1609.34)
        result=mileage(rows,'UTC',as_of=datetime(2026,10,6,tzinfo=timezone.utc))
        self.assertAlmostEqual(result['ytd']['miles'],2+1609.34/1609.344)
        self.assertEqual((result['ytd']['file_count'],result['ytd']['api_count']),(1,1))
        rebuild_performance(self.store)
        statements=[];self.store.connection.set_trace_callback(statements.append)
        with patch.object(Store,'get_source',side_effect=AssertionError('Raw file read')):
            value=dashboard(self.store,'UTC',as_of=datetime(2026,10,6,tzinfo=timezone.utc))
        self.assertFalse(any('FROM records' in s or 'evidence_json' in s for s in statements))
        self.assertEqual(value['performance']['pending'],0)
        powers={r['activity_id']:r for r in value['recent']}
        self.assertEqual(powers[overlap]['average_power'],123)
        self.assertEqual(powers[overlap]['average_power_source']['context'],'FIT session')
        self.assertEqual(next(r for r in value['recent'] if r['activity_id']!=overlap)['average_power'],999)

    def test_average_power_file_tcx_api_zero_current_and_unavailable(self):
        def source(kind,fmt,summary,**extras):
            return dict(source=dict(kind=kind,content_format=fmt,source_id=kind+fmt,is_current=True),summary=summary,**extras)
        csv=source('strava_export','CSV',dict(avg_power=777,average_watts=888))
        api=source('strava_api','JSON',dict(values=dict(average_watts=999)))
        file=source('fit','FIT',dict(avg_power=0))
        self.assertEqual(average_power(dict(sources=[file,csv,api])),(0,dict(source_id='fitFIT',context='FIT session')))
        tcx=source('tcx','TCX',{},xml_context=dict(lap_summaries=[dict(avg_power=250)]))
        self.assertEqual(average_power(dict(sources=[tcx,csv,api]))[0],250)
        self.assertEqual(average_power(dict(sources=[tcx,csv,api]))[1]['context'],'TCX single lap')
        tcx['xml_context']['lap_summaries'].append(dict(avg_power=350))
        self.assertEqual(average_power(dict(sources=[tcx,csv,api]))[0],999)
        tcx['summary']['avg_power']=200
        self.assertEqual(average_power(dict(sources=[tcx,csv,api]))[0],200)
        file['summary']['avg_power']=None
        self.assertEqual(average_power(dict(sources=[file,csv,api]))[0],999)
        api['summary']['values']['average_watts']=0
        self.assertEqual(average_power(dict(sources=[file,csv,api]))[0],0)
        api['source']['is_current']=False
        self.assertEqual(average_power(dict(sources=[file,csv,api])),(None,None))

    def test_goal_only_in_mileage_and_no_native_mileage_tooltips(self):
        self.post(target_miles='2200')
        html=self.app.get('/?home_tz=America%2FLos_Angeles')[2].decode()
        self.assertNotIn('home-ytd',html);self.assertNotIn('YTD mileage goal',html)
        summary=html.split('home-summary">')[1].split('<div class="home-layout">')[0]
        self.assertNotIn('2200',summary);self.assertNotIn('2,200',summary)
        self.assertEqual(summary.count('<section'),3)
        self.assertEqual(summary.count('<h2>'),3)
        self.assertIn('id="home-recent-mileage"',summary)
        self.assertIn('Needed average:',html)
        chart=html.split('id="home-mileage-chart"')[1].split('</svg>')[0]
        self.assertNotIn('<title',chart)
        self.assertEqual(chart.count('data-bar-kind="actual"'),12)
        self.assertNotIn('data-bar-kind="needed"',chart)
        self.assertEqual(chart.count('home-mileage-current'),1)
        self.assertEqual(chart.count('data-needed-week='),12)
        self.assertIn('tabindex="0"',chart)
        self.assertEqual(self.app.get('/static/home.js')[0],200)

    def test_recent_mileage_keeps_distinct_values_and_comparison_in_one_card(self):
        import re
        observations=[normalize(dict(id=i,name='Synthetic ride',type='Ride',sport_type='VirtualRide',
            start_date=stamp,distance=amount*1609.344,elapsed_time=1200)) for i,stamp,amount in (
                (1,'2026-10-05T12:00:00Z',2),(2,'2026-10-03T12:00:00Z',5),(3,'2026-09-28T12:00:00Z',3))]
        apply_observations(self.store,observations,42,1790000000);rebuild_performance(self.store)
        value=dashboard(self.store,'UTC',as_of=datetime(2026,10,7,18,tzinfo=timezone.utc))
        with patch('rideworks.home.dashboard',return_value=value):
            html=self.app.get('/?home_tz=UTC')[2].decode()
        summary=html.split('home-summary">')[1].split('<div class="home-layout">')[0]
        week=re.search(r'<div id="home-this-week">(.*?)</div>',summary,re.S).group(1)
        last7=re.search(r'<div id="home-last7">(.*?)</div>',summary,re.S).group(1)
        self.assertIn('<strong>2.0 mi</strong>',week)
        self.assertIn('<strong>7.0 mi</strong>',last7)
        self.assertIn('4.0 mi more than previous 7 days',last7)
        self.assertNotIn('previous 7 days',week)
        self.assertEqual(summary.count('<section'),3)
        self.assertEqual(summary.count('<h2>Recent Mileage</h2>'),1)

    def test_independent_oracle_rejects_wrong_required_point_and_api_average(self):
        from copy import deepcopy
        from tools.verify_rideworks_dashboard import verify
        item=normalize(dict(id=1,name='Synthetic API ride',type='Ride',sport_type='VirtualRide',
                            start_date='2026-10-05T12:00:00Z',distance=1609.344,elapsed_time=1200,average_watts=88.5))
        apply_observations(self.store,[item],42,1790000000);rebuild_performance(self.store)
        set_annual_goal(self.store,2026,'1000')
        data=dashboard(self.store,'UTC',as_of=datetime(2026,10,7,18,tzinfo=timezone.utc))
        result=verify(self.store,data)
        self.assertEqual(result['weekly_required_points_verified'],12)
        self.assertEqual(result['recent_average_power_sources_verified'],1)
        for field in ('needed_miles_per_week','bar_miles','ytd_miles'):
            broken=deepcopy(data);broken['weekly_goal'][-1][field]+=1
            with self.assertRaises(AssertionError):verify(self.store,broken)
        broken=deepcopy(data);broken['recent'][0]['average_power']=999
        with self.assertRaises(AssertionError):verify(self.store,broken)
        broken=deepcopy(data)
        broken['weekly_goal'][-1]['bar_miles']=broken['goal']['needed_miles_per_week']
        with self.assertRaises(AssertionError):verify(self.store,broken)

    def test_schema6_atomic_migration_preserves_all_existing_tables(self):
        old=self.root/'schema6'
        with Store(old) as store:
            store.connection.execute('DROP TABLE training_stress_cache');store.connection.execute('DROP TABLE annual_mileage_goals');store.connection.execute('PRAGMA user_version=6')
        broken=store_module.MIGRATION_7.replace('PRAGMA user_version = 7;','INSERT INTO nonexistent VALUES(1);')
        with patch.object(store_module,'MIGRATION_7',broken),self.assertRaises(sqlite3.Error):Store(old)
        with sqlite3.connect(old/'rideworks.sqlite3') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],6)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='annual_mileage_goals'").fetchone())
        with Store(old) as migrated:
            self.assertEqual(migrated.connection.execute('PRAGMA user_version').fetchone()[0],8)
            self.assertEqual(migrated.connection.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_annual_goal_migration_waits_for_completed_stream_migration(self):
        old=self.root/'schema5'
        with patch.object(store_module,'MIGRATION_6',''):
            with Store(old) as stopped:
                self.assertEqual(stopped.connection.execute('PRAGMA user_version').fetchone()[0],5)
                self.assertIsNone(stopped.connection.execute("SELECT name FROM sqlite_master WHERE name='annual_mileage_goals'").fetchone())
        with Store(old) as migrated:
            self.assertEqual(migrated.connection.execute('PRAGMA user_version').fetchone()[0],8)

    def test_no_deferred_metrics_and_pending_banner_on_home(self):
        path=self.root/'synthetic.fit';path.write_bytes(make_fit());self.store.import_fit(path)
        html=self.app.get('/?home_tz=UTC')[2].decode()
        self.assertIn('Performance update incomplete',html)
        self.assertIn('Retry Performance update',html)
        for text in ('Fitness Score','Training Load','Next Workout','Power Curve','AI Insights','Current FTP'):
            self.assertNotIn(text,html)
        rebuild_performance(self.store)
        self.assertNotIn('class="performance-update"',self.app.get('/?home_tz=UTC')[2].decode())
