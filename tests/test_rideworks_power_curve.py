"""Synthetic exact MMP, source, historical-window, cache and route regressions."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fit_fixture import make_fit
from rideworks.analysis import best_20_minute_power
from rideworks.errors import IntegrityError
from rideworks.power_curve import (comparison, curve_history, duration_grid, envelope,
                                   mmp, rebuild_curves, converge_curves)
from rideworks.performance import performance_history, rebuild_performance
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.strava_streams import persist
from rideworks.web import Application

BASE = datetime(2026, 10, 7, 16, tzinfo=timezone.utc)


def records(powers, offsets=None):
    offsets = range(len(powers)) if offsets is None else offsets
    return [dict(record_index=i, power=p, timestamp=(BASE+timedelta(seconds=t)).isoformat() if t is not None else None)
            for i,(p,t) in enumerate(zip(powers,offsets))]


def oracle(rows, d):
    candidates = []
    for i in range(len(rows)-d+1):
        window = rows[i:i+d]
        if any(r['power'] is None or r['timestamp'] is None for r in window):
            continue
        times = [datetime.fromisoformat(r['timestamp']) for r in window]
        if any(b-a != timedelta(seconds=1) for a,b in zip(times,times[1:])):
            continue
        candidates.append((sum(r['power'] for r in window),i))
    if not candidates:
        return None
    best = min(candidates,key=lambda r:(-r[0],r[1]))
    return best + (len(candidates),)


def stream(values, **changes):
    return dict(data=values, original_size=len(values), resolution='high', series_type='time') | changes


class CurveMathTests(unittest.TestCase):
    def test_small_independent_brute_force_many_durations(self):
        rng = random.Random(4501)
        for size in (1,2,8,45,120):
            powers = [rng.randrange(501) if rng.random()>.12 else None for _ in range(size)]
            offsets = list(range(size))
            for i in range(size//11,size,size//7+1):
                offsets[i] += 2
            rows = records(powers, offsets)
            results = {p['duration_seconds']:p for p in mmp(rows,durations=range(1,size+2))['points']}
            for d in range(1,size+2):
                expected = oracle(rows,d)
                if expected is None:
                    self.assertNotIn(d,results)
                else:
                    p = results[d]
                    self.assertEqual((p['sum_watts'],p['start_record_index'],p['eligible_window_count']),expected)
                    self.assertEqual(p['average_watts'],expected[0]/d)
                    self.assertEqual(p['rounded_watts'],(expected[0]+d//2)//d)

    def test_ties_zeros_low_watts_and_no_extrapolation(self):
        for value in (0,1,2):
            points=mmp(records([value]*1200))['points']
            last=points[-1]
            self.assertEqual(last['duration_seconds'],1200)
            self.assertEqual(last['average_watts'],value)
            self.assertEqual(last['start_record_index'],0)
            self.assertEqual(last['eligible_window_count'],1)
        points=mmp(records([900,0,0,0,0]),durations=[1,5,6])['points']
        self.assertEqual([p['average_watts'] for p in points],[900,180])

    def test_null_gap_duplicate_backward_and_unknown_sample(self):
        rows=records([100]*20,[0,1,2,3,4,4,3,8,None,10,11,12,13,14,15,16,17,18,19,20])
        self.assertEqual(mmp(rows)['longest_continuous_seconds'],11)
        rows[12]['power']=None
        self.assertEqual(mmp(rows)['longest_continuous_seconds'],7)

    def test_invalid_power_and_timestamps_fail(self):
        for value in (-1,1.5,True):
            with self.assertRaises(IntegrityError):mmp(records([value]))
        for stamp in ('bad','2026-01-01T00:00:00'):
            rows=records([1]);rows[0]['timestamp']=stamp
            with self.assertRaises(IntegrityError):mmp(rows)

    def test_verified_endpoint_and_pause_group_separation(self):
        rows=records([100]*1200+[500])
        start=BASE.timestamp()
        scoped=mmp(rows,intervals=[(start,start+1200)])
        best=next(p for p in scoped['points'] if p['duration_seconds']==1200)
        accepted=best_20_minute_power(rows,activity_id='x',source_id='y',extraction_id='z')
        self.assertEqual(best['average_watts'],accepted['average_watts'])
        self.assertEqual(best['start_record_index'],accepted['start_record_index'])
        split=mmp(records([100]*1300),intervals=[(start,start+650),(start+650,start+1299)])
        self.assertEqual(split['longest_continuous_seconds'],651)
        self.assertFalse(any(p['duration_seconds']==1200 for p in split['points']))

    def test_grid_dense_exact_and_unbounded(self):
        grid=duration_grid(100000)
        self.assertEqual(grid[:30],list(range(1,31)))
        for d in (60,300,1200,3600,7200,14400):self.assertIn(d,grid)
        self.assertGreater(grid[-1],86400)
        self.assertTrue(all(b<=a*1.07+1 for a,b in zip(grid,grid[1:])))


class CurveSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'data');self.addCleanup(self.store.close)

    def native(self,powers,*,activity_id=None,marker=150,verified=True):
        count=len(powers);start=1100000000
        p=self.root/'synthetic.fit'
        p.write_bytes(make_fit(powers=powers,heart_rates=[100]*count,timestamps=range(start,start+count),
                    max_hr=marker,elapsed=count-1,timer=count-1 if verified else count+300,
                    event_timestamps=(start,start+count-1 if verified else start+max(1,count-200)),
                    session_timestamp=start+count-1,session_start_time=start))
        return self.store.import_file(p,activity_id=activity_id)

    def api(self,identity,powers,*,when=BASE,metadata=None,payload=None):
        source=dict(id=identity,name='Synthetic effort '+str(identity),type='Ride',sport_type='VirtualRide',
                    start_date=when.isoformat(),moving_time=len(powers),elapsed_time=len(powers),device_watts=True)
        source.update(metadata or {})
        apply_observations(self.store,[normalize(source)],999,int(BASE.timestamp()))
        persist(self.store,identity,payload or dict(time=stream(list(range(len(powers)))),watts=stream(powers)))
        return self.store.connection.execute('SELECT activity_id FROM strava_api_activities WHERE external_id=?',(str(identity),)).fetchone()[0]

    def result(self,identity):return curve_history(self.store)['results'][identity]

    def test_native_and_api_best20_exact_shared_source_parity(self):
        native=self.native([100]*1200+[101])
        api=self.api(1,[80]*1200+[300])
        rebuild_performance(self.store);before=list(self.store.connection.execute('SELECT * FROM performance_history'))
        rebuild_curves(self.store)
        for r in performance_history(self.store)['results']:
            p=next(p for p in self.result(r['activity_id'])['points'] if p['duration_seconds']==1200)
            self.assertEqual((p['average_watts'],p['rounded_watts']),(r['average_watts'],r['rounded_watts']))
            if r['activity_id']==native['activity_id']:
                self.assertEqual(p['start_record_index'],r['start_record_index'])
                self.assertEqual(p['source']['timer_quality'],'session_verified')
            else:self.assertEqual(p['start_offset'],r['start_offset'])
        self.assertEqual(list(self.store.connection.execute('SELECT * FROM performance_history')),before)
        self.assertEqual(len(curve_history(self.store)['profiles']),2)

    def test_short_native_and_api_and_unverified_poststop_observations(self):
        native=self.native([100]*30)
        api=self.api(1,[200]*15)
        conflicting=self.native([100]*1200+[300]*200,marker=151,verified=False)
        rebuild_curves(self.store)
        for identity,d in [(native['activity_id'],30),(api,15)]:
            points=self.result(identity)['points'];self.assertEqual(points[-1]['duration_seconds'],d)
            self.assertFalse(any(p['duration_seconds']==1200 for p in points))
        best=next(p for p in self.result(conflicting['activity_id'])['points'] if p['duration_seconds']==1200)
        self.assertTrue(best['source']['timer_discrepancy'])
        self.assertEqual(best['source']['timer_quality'],'paired_scope_unverified')
        self.assertEqual(best['average_watts'],(100*1000+300*200)/1200)

    def test_duration_specific_competing_files_and_file_precedence(self):
        first=self.native([100]*1200)
        self.native([300]*15,activity_id=first['activity_id'],marker=151)
        rebuild_curves(self.store)
        result=self.result(first['activity_id'])
        self.assertEqual(result['ambiguous_durations'],list(range(1,16)))
        self.assertTrue(any(p['duration_seconds']==1200 for p in result['points']))
        # Add retained API metadata/streams to the established file identity;
        # explicit local test association leaves the file policy in control.
        api=self.api(1,[500]*1200)
        self.store.connection.execute('UPDATE strava_api_activities SET activity_id=? WHERE activity_id=?',(first['activity_id'],api))
        self.store.connection.execute('UPDATE strava_api_sources SET activity_id=? WHERE activity_id=?',(first['activity_id'],api))
        self.store.connection.execute('UPDATE strava_stream_sources SET activity_id=? WHERE activity_id=?',(first['activity_id'],api))
        rebuild_curves(self.store)
        self.assertTrue(all(p['source']['content_format']=='FIT' for p in self.result(first['activity_id'])['points']))

    def test_api_policy_resolution_full_length_pairing_and_device(self):
        cases=[(dict(time=stream([0,1,2]),watts=stream([100]*3,resolution='medium')),'api_stream_not_high_resolution'),
               (dict(time=stream([0,1,2],original_size=4),watts=stream([100]*3)),'api_stream_not_full_length'),
               (dict(time=stream([0,1,2]),watts=stream([100]*2)),'api_stream_length_mismatch'),
               (dict(time=stream([0,1,2]),watts=stream([100]*3,series_type='distance')),'api_stream_pairing_ambiguous'),
               (dict(time=stream([0,0,2]),watts=stream([100]*3)),'api_stream_invalid_timing')]
        for i,(payload,reason) in enumerate(cases,1):
            identity=self.api(i,[100]*3,payload=payload);rebuild_curves(self.store)
            self.assertEqual(self.result(identity)['reason'],reason)
        identity=self.api(8,[100]*3,metadata=dict(device_watts=False));rebuild_curves(self.store)
        self.assertEqual(self.result(identity)['reason'],'api_device_watts_not_confirmed')

    def test_api_rfc3339_z_start_matches_accepted_best20(self):
        identity=self.api(1,[100]*1200+[200],metadata=dict(start_date=BASE.isoformat().replace('+00:00','Z')))
        rebuild_curves(self.store);rebuild_performance(self.store)
        p=next(p for p in self.result(identity)['points'] if p['duration_seconds']==1200)
        accepted=next(r for r in performance_history(self.store)['results'] if r['activity_id']==identity)
        self.assertEqual(p['average_watts'],accepted['average_watts'])
        self.assertEqual(p['start_offset'],accepted['start_offset'])

    def test_outdoor_summary_only_and_missing_power_do_not_create_curve(self):
        outside=self.api(1,[900]*1200,metadata=dict(sport_type='Ride'))
        absent=self.api(2,[None]*20)
        rebuild_curves(self.store)
        self.assertEqual(self.result(outside)['reason'],'outdoor_ride_excluded')
        self.assertEqual(self.result(absent)['points'],[])
        self.store.connection.execute('DELETE FROM strava_stream_current')
        rebuild_curves(self.store)
        self.assertEqual(curve_history(self.store)['profiles'],[])

    def test_cache_staleness_no_raw_reads_restart_and_atomic_failure(self):
        native=self.native([100]*1200);api=self.api(1,[200]*30)
        first=rebuild_curves(self.store);self.assertEqual(first['computed'],2)
        expected=curve_history(self.store)
        with patch.object(self.store,'get_source',side_effect=AssertionError('raw source read')),patch.object(self.store,'strava_stream_evidence',side_effect=AssertionError('raw API read')):
            self.assertEqual(rebuild_curves(self.store)['reused'],2)
            self.assertEqual(curve_history(self.store),expected)
            self.assertTrue(comparison(self.store)['series']['all']['points'])
        with Store(self.store.data_dir) as reopened:self.assertEqual(curve_history(reopened),expected)
        persist(self.store,1,dict(time=stream(list(range(30))),watts=stream([300]*30)))
        self.assertEqual(curve_history(self.store)['pending'],1)
        self.assertNotIn(api,curve_history(self.store)['results'])
        self.assertEqual(rebuild_curves(self.store)['computed'],1)
        before=list(self.store.connection.execute('SELECT * FROM power_curve_profiles ORDER BY activity_id'))
        self.store.connection.execute('UPDATE extractions SET record_count=record_count+1 WHERE extraction_id=?',(native['extraction_id'],))
        with self.assertRaises(IntegrityError):rebuild_curves(self.store,force=True)
        self.assertEqual(list(self.store.connection.execute('SELECT * FROM power_curve_profiles ORDER BY activity_id')),before)

    def test_reextraction_and_summary_selection_invalidate(self):
        native=self.native([100]*30);self.api(1,[100]*30)
        rebuild_curves(self.store)
        self.store.reextract(native['source_id'])
        self.assertEqual(curve_history(self.store)['pending'],1)
        rebuild_curves(self.store)
        changed=normalize(dict(id=1,name='Changed synthetic',type='Ride',sport_type='VirtualRide',
                                start_date=BASE.isoformat(),elapsed_time=30,moving_time=30,device_watts=True))
        apply_observations(self.store,[changed],999,int(BASE.timestamp()))
        self.assertEqual(curve_history(self.store)['pending'],1)
        rebuild_curves(self.store)
        other=next(r for r in curve_history(self.store)['results'].values() if r['activity_id']!=native['activity_id'])
        self.assertEqual(other['reason'],'api_stream_summary_not_current')

    def test_verified_pause_conflict_stops_without_overwriting_cache(self):
        native=self.native([100]*1300)
        rebuild_curves(self.store)
        before=list(self.store.connection.execute('SELECT * FROM power_curve_profiles'))
        events=[dict(r) for r in self.store.connection.execute('SELECT * FROM events WHERE extraction_id=? ORDER BY source_order',(native['extraction_id'],))]
        start=datetime.fromisoformat(events[0]['timestamp'])
        self.store.connection.execute('DELETE FROM events WHERE extraction_id=?',(native['extraction_id'],))
        for i,offset,kind in [(0,0,'start'),(1,650,'stop_all'),(2,650,'start'),(3,1299,'stop_all')]:
            self.store.connection.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(native['extraction_id'],i,(start+timedelta(seconds=offset)).isoformat(),'timer',kind,None))
        with self.assertRaisesRegex(IntegrityError,'Analyst review'):rebuild_curves(self.store)
        self.assertEqual(list(self.store.connection.execute('SELECT * FROM power_curve_profiles')),before)

    def test_historical_six_week_bounds_never_include_future(self):
        ids={}
        for i,delta,power in [(1,-42,100),(2,-43,900),(3,-1,120),(4,0,800),(5,1,1000),(6,400,1200)]:
            ids[i]=self.api(i,[power]*30,when=BASE+timedelta(days=delta))
        selected=self.api(7,[200]*30)
        rebuild_curves(self.store)
        data=comparison(self.store,activity_id=selected)
        self.assertEqual(data['series']['six']['count'],2)
        self.assertEqual(data['series']['six']['points'][0]['activity']['activity_id'],ids[3])
        self.assertEqual(data['series']['year']['count'],3)
        self.assertEqual(data['series']['all']['count'],3)
        self.assertEqual(data['series']['six']['start'],(BASE-timedelta(days=42)).isoformat())
        self.assertEqual(data['series']['six']['end_exclusive'],BASE.isoformat())
        # Same day but after the selected start must be excluded too.
        self.api(8,[1500]*30,when=BASE+timedelta(seconds=1));rebuild_curves(self.store)
        self.assertEqual(comparison(self.store,activity_id=selected)['series'],data['series'])

    def test_empty_baseline_and_missing_absolute_start(self):
        native=self.native([100]*30);rebuild_curves(self.store)
        data=comparison(self.store,activity_id=native['activity_id'])
        self.assertTrue(data['series']['ride']['points']);self.assertEqual(data['series']['six']['points'],[])
        self.store.connection.execute('UPDATE sessions SET start_time=NULL WHERE extraction_id=?',(native['extraction_id'],))
        rebuild_curves(self.store)
        data=comparison(self.store,activity_id=native['activity_id'])
        self.assertEqual(data['baseline_reason'],'activity_absolute_start_unavailable')
        self.assertTrue(data['series']['ride']['points'])

    def test_performance_calendar_periods_and_exclusive_ends(self):
        now=datetime(2026,1,1,8,30,tzinfo=timezone.utc)
        self.api(1,[100]*30,when=now-timedelta(hours=1))
        self.api(2,[200]*30,when=now-timedelta(minutes=10))
        self.api(3,[900]*30,when=now)
        rebuild_curves(self.store)
        west=comparison(self.store,as_of=now,zone=ZoneInfo('America/Los_Angeles'))
        utc=comparison(self.store,as_of=now)
        self.assertEqual(west['series']['ytd']['count'],1)
        self.assertEqual(west['series']['last_year']['count'],1)
        self.assertEqual(utc['series']['ytd']['count'],2)
        self.assertEqual(west['series']['all']['count'],2)

    def test_routes_update_action_and_failed_sync_derivation(self):
        identity=self.api(1,[100]*30);app=Application(self.store.data_dir)
        html=app.get('/performance')[2].decode()
        self.assertIn('20-Minute History',html);self.assertIn('Update power curves',html)
        body=('nonce='+app.settings.nonce).encode()
        status,headers,_=app.post('/settings/power-curves/rebuild',body,'http://127.0.0.1:8765')
        self.assertEqual(status,303);self.assertEqual(headers['Location'],'/performance?curve=1')
        self.assertEqual(curve_history(self.store)['pending'],0)
        self.assertIn('power-curve-data',app.get('/activities/'+identity)[2].decode())
        self.assertEqual(app.get('/static/power_curve.js')[0],200)
        self.assertEqual(app.post('/settings/power-curves/rebuild',b'nonce=bad','http://127.0.0.1:8765')[0],403)
        with patch('rideworks.power_curve.rebuild_curves',side_effect=IntegrityError('private')):
            self.assertEqual(converge_curves(self.store),dict(power_curve_update='incomplete'))

    def test_additive_migration_rollback_preserves_version_nine(self):
        self.store.connection.execute('DROP TABLE power_curve_profiles')
        self.store.connection.execute('PRAGMA user_version=9')
        import rideworks.store as module
        with patch.object(module,'MIGRATION_10',module.MIGRATION_10.replace('PRAGMA user_version = 10;','INSERT INTO nonexistent VALUES(1);')):
            with self.assertRaises(sqlite3.Error):Store(self.store.data_dir)
        self.assertEqual(self.store.connection.execute('PRAGMA user_version').fetchone()[0],9)
        with Store(self.store.data_dir) as restarted:self.assertEqual(restarted.connection.execute('PRAGMA user_version').fetchone()[0],11)

    def test_curve_migration_waits_for_completed_planning_migration(self):
        import rideworks.store as module
        with patch.object(module,'MIGRATION_9',''):
            with Store(self.root/'paused') as paused:
                self.assertEqual(paused.connection.execute('PRAGMA user_version').fetchone()[0],8)
                self.assertIsNone(paused.connection.execute("SELECT name FROM sqlite_master WHERE name='power_curve_profiles'").fetchone())
        with Store(self.root/'paused') as recovered:
            self.assertEqual(recovered.connection.execute('PRAGMA user_version').fetchone()[0],11)

    def test_changed_input_during_build_is_not_published(self):
        identity=self.api(1,[100]*20)
        from rideworks.power_curve import evaluate
        def change_after_calculation(store,snapshot):
            profile=evaluate(store,snapshot)
            changed=normalize(dict(id=1,name='Changed while calculating',type='Ride',sport_type='VirtualRide',
                                   start_date=BASE.isoformat(),elapsed_time=20,moving_time=20,device_watts=True))
            apply_observations(store,[changed],999,int(BASE.timestamp()))
            return profile
        with patch('rideworks.power_curve.evaluate',side_effect=change_after_calculation):
            report=rebuild_curves(self.store)
        self.assertEqual(report['status'],'incomplete')
        self.assertEqual(report['changed_during_build'],1)
        self.assertEqual(report['computed'],0)
        self.assertNotIn(identity,curve_history(self.store)['results'])
        self.assertEqual(curve_history(self.store)['pending'],1)


class CurveSyncTests(unittest.TestCase):
    def setUp(self):
        import test_rideworks_strava as fixture
        fixture.StravaTests.setUp(self)

    def test_normal_sync_failure_keeps_sources_and_retries_incrementally(self):
        import test_rideworks_strava as fixture
        from rideworks.strava import ApiClient, sync
        item=fixture.StravaTests.observation(self,identity=2,seconds=3600)
        payload=dict(time=stream(list(range(20))),watts=stream([200]*20))
        http=fixture.FakeHTTP(fixture.Response([item]),fixture.Response(payload))
        client=ApiClient(fixture.CREDS,opener=http)
        with patch('rideworks.power_curve.evaluate',side_effect=IntegrityError('private derivation failure')):
            report=sync(self.store,client,now=self.now)
        self.assertEqual(report['power_curve_update'],'incomplete')
        self.assertEqual(self.store.connection.execute('SELECT successful_at FROM strava_sync_state').fetchone()[0],self.now)
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM strava_stream_sources').fetchone()[0],1)
        http.responses.append(fixture.Response([item]))
        report=sync(self.store,client,now=self.now+1)
        self.assertEqual(report['power_curve_update'],'updated');self.assertEqual(report['stream_fetches'],0)
        h=curve_history(self.store);self.assertEqual(h['pending'],0)
        api=next(p for p in h['profiles'] if p['activity_id']!=self.native['activity_id'])
        self.assertEqual(api['points'][-1]['duration_seconds'],20)
        native_cache=tuple(self.store.connection.execute('SELECT * FROM power_curve_profiles WHERE activity_id=?',(self.native['activity_id'],)).fetchone())
        changed=item|dict(name='Changed synthetic API ride')
        http.responses.extend([fixture.Response([changed]),fixture.Response(dict(time=stream(list(range(20))),watts=stream([300]*20)))])
        report=sync(self.store,client,now=self.now+2)
        self.assertEqual(report['stream_fetches'],1);self.assertEqual(report['power_curve_update'],'updated')
        api=next(p for p in curve_history(self.store)['profiles'] if p['activity_id']!=self.native['activity_id'])
        self.assertEqual(api['points'][0]['average_watts'],300)
        self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM power_curve_profiles WHERE activity_id=?',(self.native['activity_id'],)).fetchone()),native_cache)
        http.responses.append(fixture.Response([changed]))
        with patch('rideworks.power_curve.evaluate',side_effect=AssertionError('Unchanged sync recalculated a curve')):
            report=sync(self.store,client,now=self.now+3)
        self.assertEqual(report['power_curve_update'],'current');self.assertEqual(report['stream_fetches'],0)


class EnvelopeTests(unittest.TestCase):
    def test_duration_crossings_and_deterministic_ties(self):
        profiles=[]
        for identity,day,values in [('early',1,[500,400,200,100,90]),('late',2,[400,400,250,200,120])]:
            profiles.append(dict(activity=dict(activity_id=identity,title='Synthetic',absolute_time=True,
                       start_time=(BASE-timedelta(days=day)).isoformat()),points=[dict(duration_seconds=d,
                       sum_watts=d*w,average_watts=w) for d,w in zip((5,30,300,1200,3600),values)]))
        result=envelope(profiles,end=BASE)
        self.assertEqual([p['activity']['activity_id'] for p in result['points']],['early','late','late','late','late'])
        self.assertEqual(envelope(profiles,end=BASE-timedelta(days=3))['points'],[])
