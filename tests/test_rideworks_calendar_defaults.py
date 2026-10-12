"""OPS-01: real first responses, calendar boundaries and read-only inventory."""
from contextlib import ExitStack
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from rideworks.goals import DEFAULT_TIMEZONE, query_zone
from rideworks.history import browse
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.strava_streams import persist
from rideworks.web import Application


def payload(html, name):
    return json.loads(re.search(r'<script[^>]*id="'+name+r'"[^>]*>(.*?)</script>', html, re.S).group(1))


class CalendarDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.app=Application(self.root)
        with Store(self.root) as store:
            apply_observations(store,[normalize(dict(id=1,name='Synthetic year boundary',type='Ride',sport_type='VirtualRide',
                start_date='2026-01-01T01:00:00Z',distance=16093.44,elapsed_time=3600,average_heartrate=120,has_heartrate=True,moving_time=3600))],999,1767229200)
            stream=lambda values:dict(data=values,original_size=len(values),resolution='high',series_type='time')
            persist(store,1,dict(time=stream(list(range(3601))),heartrate=stream([120]*3601)))

    def test_only_absent_zone_defaults(self):
        for key in ('tz','home_tz','plan_tz'):
            self.assertEqual(query_zone('',key).key,DEFAULT_TIMEZONE)
            for bad in ('', 'NoSuch/Timezone','../UTC','/etc/passwd'):
                self.assertIsNone(query_zone(urlencode({key:bad}),key))
            self.assertIsNone(query_zone(f'{key}=UTC&{key}=Asia%2FTokyo',key))
            for name in ('UTC','Asia/Tokyo'):
                self.assertEqual(query_zone(urlencode({key:name}),key).key,name)

    def test_first_response_and_invalid_explicit_requests(self):
        for route,key,content in [('/','home_tz','Mileage Progress'),('/plan','plan_tz','Daily rotation'),
                                  ('/training-state','tz','Training trend'),('/settings','tz','Annual cycling mileage goal'),
                                  ('/activities','tz','Synthetic year boundary')]:
            status,_,body=self.app.get(route);self.assertEqual(status,200)
            html=body.decode();self.assertIn(content,html)
            self.assertIn('data-display-timezone="America/Los_Angeles"',html)
            self.assertNotIn('data-calendar-timezone',html)
            self.assertNotIn('Enable JavaScript to use',html)
            for value in ('','bad','../UTC'):
                status,_,body=self.app.get(route+'?'+urlencode({key:value}))
                self.assertEqual(status,400);self.assertIn(b'Invalid timezone',body)
            self.assertEqual(self.app.get(route+f'?{key}=UTC&{key}=UTC')[0],400)

    def test_empty_calendar_pages_and_power_curve_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(Path(directory))
            for route,text in [('/', 'Mileage Progress'),('/plan','Daily rotation'),('/training-state','No usable training stress yet')]:
                status,_,body=app.get(route)
                self.assertEqual(status,200);self.assertIn(text,body.decode())
                self.assertNotIn('Enable JavaScript to use',body.decode())
        for zone in (DEFAULT_TIMEZONE,'UTC','Asia/Tokyo'):
            query='' if zone==DEFAULT_TIMEZONE else '?'+urlencode({'curve_tz':zone})
            status,_,body=self.app.get('/performance'+query)
            self.assertEqual(status,200)
            self.assertEqual(payload(body.decode(),'power-curve-data')['calendar_timezone'],zone)
        for bad in ('','bad'):
            self.assertEqual(self.app.get('/performance?'+urlencode({'curve_tz':bad}))[0],400)

    def test_fixed_clock_default_equals_explicit_la_through_dst_and_new_year(self):
        for stamp in ('2026-01-01T01:30:00+00:00','2026-07-01T06:30:00+00:00',
                      '2026-03-08T09:59:00+00:00','2026-03-08T10:01:00+00:00',
                      '2026-11-01T08:59:00+00:00','2026-11-01T09:01:00+00:00'):
            now=datetime.fromisoformat(stamp)
            class Clock(datetime):
                @classmethod
                def now(cls,tz=None):return now if tz is None else now.astimezone(tz)
            with self.subTest(stamp=stamp),ExitStack() as stack:
                for module in ('dashboard','planning','training_state','settings'):
                    stack.enter_context(patch('rideworks.'+module+'.datetime',Clock))
                for route,key in [('/','home_tz'),('/plan','plan_tz'),('/training-state','tz'),('/settings','tz'),('/activities','tz')]:
                    self.assertEqual(self.app.get(route)[2],self.app.get(route+'?'+urlencode({key:DEFAULT_TIMEZONE}))[2])
                for zone in (DEFAULT_TIMEZONE,'UTC','Asia/Tokyo'):
                    expected=now.astimezone(ZoneInfo(zone)).date().isoformat()
                    home=payload(self.app.get('/?'+urlencode({'home_tz':zone}))[2].decode(),'dashboard-data')
                    plan=payload(self.app.get('/plan?'+urlencode({'plan_tz':zone}))[2].decode(),'plan-data')
                    training=payload(self.app.get('/training-state?'+urlencode({'tz':zone}))[2].decode(),'training-state-data')
                    self.assertEqual(home['today'],expected);self.assertEqual(plan['today'],expected)
                    self.assertEqual(training['today'],expected)
                    self.assertIn('goal · '+expected[:4],self.app.get('/settings?'+urlencode({'tz':zone}))[2].decode())

    def test_missing_zone_uses_la_filter_day_without_changing_source_instants(self):
        with Store(self.root) as store:
            before=store.activity_history()
            self.assertEqual(browse(store,'from=2025-12-31&to=2025-12-31')['count'],1)
            self.assertEqual(browse(store,'from=2026-01-01&to=2026-01-01')['count'],0)
            for zone in ('UTC','Asia/Tokyo'):
                self.assertEqual(browse(store,'from=2026-01-01&to=2026-01-01&'+urlencode({'tz':zone}))['count'],1)
            self.assertEqual(store.activity_history(),before)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('inventory',Path(__file__).resolve().parents[1]/'tools/inventory_rideworks_stores.py')
        self.tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.tool)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        with Store(self.root):pass

    def test_read_only_and_no_secret_read_or_file_change(self):
        (self.root/'.strava-tokens.json').write_text('must not parse this secret')
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()}
        result=self.tool.inspect(self.root)
        after={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before,after);self.assertEqual(result['integrity'],['ok'])
        self.assertTrue(result['sidecars']['.strava-tokens.json']);self.assertNotIn('must not parse',json.dumps(result))

    def test_wal_and_journal_are_refused_without_creating_sidecars(self):
        db=self.root/'rideworks.sqlite3'
        (self.root/'rideworks.sqlite3-journal').touch()
        with self.assertRaises(ValueError):self.tool.inspect(self.root)
        (self.root/'rideworks.sqlite3-journal').unlink()
        with sqlite3.connect(db) as conn:conn.execute('PRAGMA journal_mode=WAL')
        before={p.name:p.stat().st_mtime_ns for p in self.root.iterdir() if p.is_file()}
        with self.assertRaises(ValueError):self.tool.inspect(self.root)
        self.assertEqual(before,{p.name:p.stat().st_mtime_ns for p in self.root.iterdir() if p.is_file()})
