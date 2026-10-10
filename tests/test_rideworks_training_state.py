"""Synthetic independent math, provenance, timing and retained-store checks."""
import csv
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from fit_fixture import make_fit
from rideworks.errors import IntegrityError
from rideworks.store import Store
from rideworks.performance import rebuild_performance, performance_history
from rideworks.training_state import (DEFAULT_HR, daily_series, ftp_history, ftp_on, hr_context,
    hrss, hr_stream, hr_summary, power_candidate, selected_stress, training_state, VERSION)
from rideworks.web import Application

FTP = dict(value=200,status='available')
FIT = dict(format='FIT',source_id='synthetic')
API = dict(format='Strava API stream',source_id='synthetic')
BASE = 1600000000


def stamp(seconds):
    return datetime.fromtimestamp(BASE+seconds,timezone.utc).isoformat()


def timer(start,end):
    return [dict(event='timer',event_type='start',timestamp=stamp(start)),
            dict(event='timer',event_type='stop_all',timestamp=stamp(end))]


def session(seconds):
    return dict(start_time=stamp(0),timestamp=stamp(seconds),total_timer_time=seconds,total_elapsed_time=seconds)


def ride(day,stress,identity='1',status='calculated',work=10):
    return dict(day=day,activity_id=identity,selected=dict(stress=stress,status=status),
                power=dict(observed_work_kj=work,missing_seconds=0,excluded_short_seconds=0))


class MathTests(TestCase):
    def test_hr_threshold_normalization_and_independent_numeric_case(self):
        self.assertAlmostEqual(hrss(143,3600,DEFAULT_HR),100,places=12)
        expected=50*(.62*math.exp(1.92*.62))/(.85*math.exp(1.92*.85))
        self.assertAlmostEqual(hrss(120,1800,DEFAULT_HR),expected,places=12)
        for mean,seconds in [(58,3600),(158,3600),(float('nan'),3600),(140,0),(None,3600)]:
            self.assertIsNone(hrss(mean,seconds,DEFAULT_HR))
        self.assertIsNone(hrss(140,3600,DEFAULT_HR|dict(threshold_hr=158)))

    def test_dated_hr_assumption_and_invalid_settings(self):
        self.assertEqual(hr_context('2010-01-01')['status'],'assumed')
        known=dict(effective_from='2020-01-01',effective_until_exclusive='2021-01-01',
                   resting_hr=55,max_hr=160,threshold_hr=145,basis='Owner dated observation')
        self.assertEqual(hr_context('2020-01-01',[known])['status'],'dated')
        self.assertEqual(hr_context('2021-01-01',[known])['status'],'assumed')
        for change in [dict(max_hr=58),dict(resting_hr=None),dict(threshold_hr=58),dict(coefficient=float('inf'))]:
            self.assertIsNone(hrss(140,3600,DEFAULT_HR|change))

    def test_packaged_ftp_identical_and_all_inclusive_exclusive_boundaries(self):
        history,digest=ftp_history(); self.assertEqual(len(history),66)
        self.assertEqual(Path('data/athlete/strava_ftp_history.csv').read_bytes(),Path('rideworks/data/strava_ftp_history.csv').read_bytes())
        self.assertEqual(len(digest),64)
        self.assertIsNone(ftp_on(history,'2019-07-17')['value'])
        for i,row in enumerate(history):
            self.assertEqual(ftp_on(history,row['effective_from_date'])['value'],row['ftp_watts'])
            if i:
                before=(date.fromisoformat(row['effective_from_date'])-timedelta(days=1)).isoformat()
                self.assertEqual(ftp_on(history,before)['value'],history[i-1]['ftp_watts'])
        self.assertEqual(ftp_on(history,'2099-01-01')['value'],history[-1]['ftp_watts'])
        self.assertEqual(ftp_on(history,history[0]['effective_from_date'],False)['status'],'date_uncertain')

    def test_updated_ftp_record_length_and_strict_intervals(self):
        header=['effective_from_date','effective_until_date_exclusive','ftp_watts']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'approved.csv'
            with Path('data/athlete/strava_ftp_history.csv').open() as handle:
                rows=list(csv.DictReader(handle))
            rows[-1]['effective_until_date_exclusive']='2026-10-10'
            rows.append(dict(zip(header,['2026-10-10','',190])))
            def write(values):
                with path.open('w',newline='') as handle:
                    writer=csv.DictWriter(handle,fieldnames=header);writer.writeheader();writer.writerows(values)
            write(rows)
            history,digest=ftp_history(path)
            self.assertEqual(len(history),67)
            self.assertNotEqual(digest,ftp_history()[1])
            self.assertEqual(ftp_on(history,'2026-10-10')['value'],190)
            for update in [dict(effective_from_date='2026-09-01'),dict(ftp_watts='0'),
                           dict(ftp_watts='190.5'),dict(effective_until_date_exclusive='2027-01-01'),
                           dict(effective_from_date='not-a-date')]:
                write(rows[:-1]+[rows[-1]|update])
                with self.assertRaises(IntegrityError):ftp_history(path)
            write([])
            with self.assertRaises(IntegrityError):ftp_history(path)

    def test_exact_exponential_decay_prior_form_and_zero_seed(self):
        rows=daily_series([ride('2026-01-01',100),ride('2026-01-02',None,'2','unavailable')],'2026-02-12')
        f=100*(1-math.exp(-1/42));a=100*(1-math.exp(-1/7))
        self.assertEqual(rows[0]['form'],0)
        for i,row in enumerate(rows):
            self.assertAlmostEqual(row['fitness'],f*math.exp(-i/42),places=12)
            self.assertAlmostEqual(row['fatigue'],a*math.exp(-i/7),places=12)
            if i:self.assertAlmostEqual(row['form'],rows[i-1]['fitness']-rows[i-1]['fatigue'])
        self.assertEqual(rows[1]['unscored'],1); self.assertFalse(rows[1]['no_record'])
        self.assertIsNone(rows[1]['rides'][0]['selected']['stress']);self.assertTrue(rows[2]['no_record'])
        self.assertEqual(rows[6]['window7']['stress'],100); self.assertEqual(rows[7]['window7']['stress'],0)
        self.assertEqual(rows[41]['window42']['stress'],100);self.assertEqual(rows[42]['window42']['stress'],0)
        self.assertAlmostEqual(rows[7]['changes7']['fitness'],rows[7]['fitness']-rows[0]['fitness'])

    def test_multi_ride_sum_no_rounding_and_consecutive_workouts(self):
        rides=[ride('2024-02-28',33.33333),ride('2024-02-28',66.66667,'2'),ride('2024-02-29',50,'3')]
        rows=daily_series(rides,'2024-03-01')
        self.assertEqual(rows[0]['stress'],100);self.assertEqual(rows[0]['contributors'],2)
        self.assertAlmostEqual(rows[1]['fitness'],100*(1-math.exp(-1/42))*math.exp(-1/42)+50*(1-math.exp(-1/42)))
        self.assertEqual(rows[2]['window7']['work_kj'],30)
        self.assertEqual(daily_series([ride('2020-01-01',None,status='unavailable')],'2020-01-02'),[])


class EvidenceTests(TestCase):
    def power(self,times,powers,**kwargs):
        return power_candidate(times,powers,ftp=FTP,source=FIT,**kwargs)

    def test_constant_and_real_zero_work_power_and_recorded_scope(self):
        result=self.power(list(range(1200)),[200]*1200)
        self.assertEqual(result['status'],'calculated');self.assertFalse(result['whole_session_verified'])
        self.assertAlmostEqual(result['stress'],100/3);self.assertEqual(result['observed_work_kj'],240)
        zero=self.power(list(range(1200)),[0]*1200)
        self.assertEqual(zero['stress'],0);self.assertEqual(zero['observed_work_kj'],0)

    def test_fit_15_second_one_percent_limit_and_api_never_corrected(self):
        def candidate(loss,span,source=FIT):
            times=[BASE+i for i in range(span) if not 700 <= i < 700+loss]
            return power_candidate(times,[200]*len(times),ftp=FTP,source=source,events=timer(0,span),summary=session(span))
        r=candidate(15,1500);self.assertEqual(r['status'],'corrected_estimate');self.assertEqual(r['corrected_seconds'],15)
        self.assertEqual(r['observed_work_kj'],297);self.assertAlmostEqual(r['stress'],1500/36)
        self.assertFalse(r['whole_session_verified'])
        self.assertEqual(candidate(16,2000)['status'],'partial')
        self.assertEqual(candidate(15,1200)['status'],'partial')
        self.assertEqual(candidate(15,1500,API)['status'],'partial')

    def test_missing_duplicate_invalid_backward_and_short_segments(self):
        times=list(range(1300));powers=[200]*1300;powers[650]=None
        r=self.power(times,powers);self.assertEqual(r['status'],'partial');self.assertEqual(r['excluded_short_seconds'],0)
        r=self.power(list(range(500)),[200]*500);self.assertEqual(r['status'],'unavailable');self.assertEqual(r['observed_work_kj'],100)
        r=self.power([0,1,1,2],[200]*4);self.assertEqual(r['observed_seconds'],2)
        r=self.power([0,2,1],[200]*3);self.assertEqual(r['reason'],'unsupported_power_timing')
        r=power_candidate(list(range(1200)),[200]*1200,ftp=dict(value=None),source=FIT)
        self.assertIsNone(r['stress']);self.assertEqual(r['observed_work_kj'],240)

    def test_pause_exclusion_and_independent_np_reset_sum(self):
        events=timer(0,900)+timer(960,1860)
        summary=session(1860)|dict(total_timer_time=1800)
        powers=[100]*900+[999]*60+[300]*900
        r=self.power([BASE+i for i in range(1860)],powers,events=events,summary=summary)
        self.assertEqual(r['observed_work_kj'],360);self.assertAlmostEqual(r['stress'],62.5)
        self.assertTrue(r['whole_session_verified']);self.assertEqual(r['excluded_pause_samples'],60)
        self.assertEqual(len(r['intervals']),2)
        malformed=events[:-1]
        self.assertEqual(self.power([BASE+i for i in range(1860)],powers,events=malformed,summary=summary)['reason'],'unresolved_timer_scope')

    def test_hr_stream_full_partial_pause_and_sparse_native_intervals(self):
        kwargs=dict(settings=DEFAULT_HR,source=FIT)
        r=hr_stream(list(range(3600)),[143]*3600,duration=3600,**kwargs)
        self.assertEqual(r['coverage'],1);self.assertAlmostEqual(r['stress'],100)
        sparse=list(range(0,3600,5))+[3599]
        r=hr_stream(sparse,[143]*len(sparse),duration=3600,**kwargs)
        self.assertAlmostEqual(r['stress'],100)
        times=list(range(3600));hrs=[143]*3600;hrs[100:150]=[None]*50
        self.assertIsNone(hr_stream(times,hrs,duration=3600,**kwargs)['stress'])
        self.assertIsNone(hr_stream(times,[143]*3600,duration=4000,**kwargs)['stress'])
        self.assertIsNone(hr_stream(times,[143]*3600,**kwargs)['stress'])
        events=timer(0,1800)+timer(1860,3660)
        r=hr_stream([BASE+i for i in range(3660)],[143]*1800+[250]*60+[143]*1800,
            events=events,summary=session(3660)|dict(total_timer_time=3600),**kwargs)
        self.assertAlmostEqual(r['stress'],100);self.assertEqual(r['coverage'],1)
        r=hr_stream([BASE+i for i in range(3600)],[143]*3600,events=timer(0,3600),summary=session(3600)|dict(total_timer_time=3400),**kwargs)
        self.assertEqual(r['reason'],'hr_duration_span_mismatch')

    def test_source_precedence_never_adds_candidates_and_unavailable_preserved(self):
        power=dict(status='calculated',stress=50,scope='recorded interval');hr=dict(stress=90,scope='HR active estimate')
        self.assertEqual(selected_stress(power,hr)['stress'],50)
        partial=power|dict(status='partial')
        self.assertEqual(selected_stress(partial,hr)['stress'],90)
        self.assertEqual(selected_stress(partial,dict(stress=None))['stress'],50)
        self.assertIsNone(selected_stress(dict(status='unavailable'),dict(stress=None))['stress'])
        self.assertEqual(hr_summary(143,3600,settings=DEFAULT_HR,source=FIT)['stress'],100)


class StoreTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'store');self.addCleanup(self.store.close)
        p=self.root/'synthetic.fit';p.write_bytes(make_fit(powers=[200]*1200,heart_rates=[143]*1200,
            timestamps=range(1100000000,1100001200),elapsed=1200,timer=1200,
            event_timestamps=(1100000000,1100001200),session_timestamp=1100001200))
        self.imported=self.store.import_fit(p);rebuild_performance(self.store)

    def test_cache_restart_reextract_settings_and_performance_preserved(self):
        before=performance_history(self.store)
        when=datetime(2026,10,9,tzinfo=timezone.utc)
        data=training_state(self.store,'America/Los_Angeles',as_of=when)
        original=self.store.get_source(self.imported['source_id'])
        self.assertEqual(data['version'],VERSION);self.assertEqual(data['coverage']['rides'],1)
        with patch('rideworks.training_state.calculate_ride',side_effect=AssertionError('cache should be current')):
            second=training_state(self.store,'America/Los_Angeles',as_of=when)
        self.assertEqual(data,second);self.assertEqual(performance_history(self.store),before)
        self.assertEqual(self.store.get_source(self.imported['source_id']),original)
        self.store.reextract(self.imported['source_id'])
        with patch('rideworks.training_state.calculate_ride',wraps=__import__('rideworks.training_state',fromlist=['calculate_ride']).calculate_ride) as calc:
            training_state(self.store,'America/Los_Angeles',as_of=when);self.assertEqual(calc.call_count,1)
        with Store(self.root/'store') as reopened:
            self.assertEqual(reopened.connection.execute('PRAGMA user_version').fetchone()[0],8)
            self.assertEqual(reopened.connection.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            training_state(reopened,'America/Los_Angeles',as_of=when)

    def test_explicit_updated_ftp_source_invalidates_cached_scores(self):
        when=datetime(2026,10,9,tzinfo=timezone.utc)
        first=training_state(self.store,'America/Los_Angeles',as_of=when)
        path=self.root/'approved-ftp.csv'
        # Synthetic dated setting covers the synthetic activity, deliberately supplied.
        path.write_text('effective_from_date,effective_until_date_exclusive,ftp_watts\n2000-01-01,,250\n')
        with patch('rideworks.training_state.calculate_ride',wraps=__import__('rideworks.training_state',fromlist=['calculate_ride']).calculate_ride) as calc:
            updated=training_state(self.store,'America/Los_Angeles',as_of=when,ftp_source=path)
            self.assertEqual(calc.call_count,1)
        self.assertNotEqual(first['ftp_source_sha256'],updated['ftp_source_sha256'])
        self.assertEqual(updated['days'][0]['rides'][0]['ftp']['value'],250)
        self.assertAlmostEqual(updated['days'][0]['stress'],1200/36*(200/250)**2)
        with patch('rideworks.training_state.calculate_ride',side_effect=AssertionError('updated source cache should match')):
            self.assertEqual(updated,training_state(self.store,'America/Los_Angeles',as_of=when,ftp_source=path))
        with patch('rideworks.training_state.calculate_ride',wraps=__import__('rideworks.training_state',fromlist=['calculate_ride']).calculate_ride) as calc:
            self.assertEqual(first,training_state(self.store,'America/Los_Angeles',as_of=when))
            self.assertEqual(calc.call_count,1)

    def test_page_routes_safe_help_navigation_and_home(self):
        app=Application(self.root/'store')
        for route in ('/training-state?tz=America%2FLos_Angeles','/?home_tz=America%2FLos_Angeles','/performance','/activities'):
            status,mime,body=app.get(route);self.assertEqual(status,200);self.assertIn(b'Training State',body)
        status,mime,body=app.get('/training-state?tz=UTC');self.assertIn(b'How these numbers work',body)
        self.assertIn(b'training-state-data',body);self.assertNotIn(str(self.root).encode(),body)
        self.assertEqual(app.get('/static/training_state.js')[0],200)

    def test_rollback_schema_migration_preserves_accepted_tables(self):
        self.store.connection.execute('DROP TABLE training_stress_cache');self.store.connection.execute('PRAGMA user_version=7')
        records=list(self.store.connection.execute('SELECT * FROM records'))
        with Store(self.root/'store') as migrated:
            self.assertEqual([tuple(r) for r in migrated.connection.execute('SELECT * FROM records')],[tuple(r) for r in records])
            self.assertEqual(migrated.connection.execute('PRAGMA foreign_key_check').fetchall(),[])

class AdditionalTests(TestCase):
    def test_nonconstant_np_matches_direct_window_oracle(self):
        watts=[0]*100+[220]*350+[340]*400+[120]*350
        result=power_candidate(list(range(1200)),watts,ftp=FTP,source=FIT)
        np=(sum((sum(watts[i:i+30])/30)**4 for i in range(1171))/1171)**.25
        self.assertAlmostEqual(result['stress'],1200/36*(np/200)**2,places=10)
        self.assertEqual(result['observed_work_kj'],sum(watts)/1000)

    def test_recorded_interval_with_unverified_outer_timer_is_not_session(self):
        events=timer(-40,1205);summary=session(1200)
        times=[BASE+i for i in range(1200)]
        r=power_candidate(times,[200]*1200,ftp=FTP,source=FIT,events=events,summary=summary)
        self.assertEqual(r['status'],'calculated');self.assertFalse(r['whole_session_verified'])
        hr=hr_stream(times,[143]*1200,settings=DEFAULT_HR,source=FIT,events=events,summary=summary)
        self.assertEqual(hr['status'],'estimated');self.assertFalse(hr['timer_boundaries_verified'])
        self.assertAlmostEqual(hr['stress'],100/3)

    def test_materially_partial_power_prefers_full_covering_hr(self):
        power=power_candidate(list(range(1200)),[200]*1200,ftp=FTP,source=FIT,duration=2400)
        self.assertEqual(power['status'],'partial');self.assertTrue(power['materially_partial_scope'])
        hr=hr_summary(143,2400,settings=DEFAULT_HR,source=FIT)
        self.assertEqual(selected_stress(power,hr)['method'],'hr')

    def test_hr_time_weighted_mean_and_bad_pairing_dont_manufacture_samples(self):
        r=hr_stream([0,5,10],[100,140,150],duration=11,settings=DEFAULT_HR,source=FIT)
        expected_mean=(5*120+5*145+150)/11
        self.assertAlmostEqual(r['mean_hr'],expected_mean)
        self.assertEqual(r['covered_seconds'],11)
        r=hr_stream([0,20,21],[120,140,140],duration=22,settings=DEFAULT_HR,source=FIT)
        self.assertEqual(r['reason'],'insufficient_hr_coverage')
        r=hr_stream([0,1,1],[120]*3,duration=3,settings=DEFAULT_HR,source=FIT)
        self.assertEqual(r['reason'],'invalid_hr_timing')

    def test_schema8_failure_is_atomic(self):
        from rideworks import store as module
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            with Store(directory) as store:
                store.connection.execute('DROP TABLE training_stress_cache')
                store.connection.execute('PRAGMA user_version=7')
            broken=module.MIGRATION_8.replace('PRAGMA user_version = 8;','INSERT INTO nonexistent VALUES(1);')
            with patch.object(module,'MIGRATION_8',broken),self.assertRaises(sqlite3.Error):Store(directory)
            with sqlite3.connect(Path(directory)/'rideworks.sqlite3') as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],7)
                self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='training_stress_cache'").fetchone())

class ApiAndRecalculationTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'store');self.addCleanup(self.store.close)
        self.now=datetime(2026,10,9,23,tzinfo=timezone.utc)
        self.item=dict(id=123,name='Synthetic outdoor ride',type='Ride',sport_type='Ride',start_date='2026-10-01T12:00:00Z',
                       moving_time=3600,elapsed_time=3600,has_heartrate=True,average_heartrate=143,device_watts=False)

    def apply(self):
        from rideworks.strava_api import apply_observations,normalize
        apply_observations(self.store,[normalize(self.item)],321,int(self.now.timestamp()))

    def result(self,**kwargs):
        d=training_state(self.store,'America/Los_Angeles',as_of=self.now,**kwargs)
        return next(r for day in d['days'] for r in day['rides']),d

    def test_outdoor_measured_api_summary_excludes_estimated_power_and_recalculates(self):
        self.apply();r,d=self.result();self.assertEqual(r['selected']['method'],'hr')
        self.assertEqual(r['selected']['stress'],100);self.assertEqual(r['hr']['settings']['status'],'assumed')
        self.assertIsNone(r['power']['observed_work_kj'])
        self.assertFalse(r['power']['eligibility']['eligible'])
        saved=list(self.store.connection.execute('SELECT * FROM training_stress_cache'))
        self.apply();r,again=self.result();self.assertEqual(d,again)
        self.assertEqual([tuple(x) for x in saved],[tuple(x) for x in self.store.connection.execute('SELECT * FROM training_stress_cache')])
        self.item['average_heartrate']=120;self.apply();r,changed=self.result();self.assertLess(r['selected']['stress'],100)
        settings=dict(effective_from='2026-01-01',effective_until_exclusive=None,resting_hr=50,max_hr=170,threshold_hr=145,basis='Synthetic accepted dated evidence')
        r,dated=self.result(hr_history=[settings]);self.assertEqual(r['hr']['settings']['status'],'dated');self.assertNotEqual(changed,dated)

    def test_api_stream_power_observed_only_hr_prefers_partial_no_double_count(self):
        from rideworks.strava_streams import persist
        def stream(values):return dict(data=values,original_size=len(values),resolution='high',series_type='time')
        self.item.update(type='VirtualRide',sport_type='VirtualRide',device_watts=True,average_heartrate=143,moving_time=3600)
        self.apply()
        times=list(range(1800))+list(range(1805,3600));powers=[200]*len(times);hrs=[143]*len(times)
        persist(self.store,123,dict(time=stream(times),watts=stream(powers),heartrate=stream(hrs)))
        r,d=self.result();self.assertEqual(r['power']['status'],'partial')
        self.assertEqual(r['selected']['method'],'hr');self.assertAlmostEqual(r['selected']['stress'],100)
        self.assertEqual(r['power']['corrected_seconds'],0)
        self.assertEqual(r['power']['observed_work_kj'],719)
        self.assertEqual(d['days'][-9]['stress'],r['selected']['stress'])
        # A changed current HR stream invalidates training stress without changing Performance inputs.
        persist(self.store,123,dict(time=stream(times),watts=stream(powers),heartrate=stream([120]*len(times))))
        other,_=self.result();self.assertNotEqual(other['selected']['stress'],r['selected']['stress'])

    def test_bad_hr_stream_retained_beside_independently_eligible_summary(self):
        from rideworks.strava_streams import persist
        def stream(values):return dict(data=values,original_size=len(values),resolution='high',series_type='time')
        self.apply();persist(self.store,123,dict(time=stream([0,1800,3599]),heartrate=stream([143]*3)))
        data=training_state(self.store,'America/Los_Angeles',as_of=self.now)
        self.assertEqual(data['coverage']['scored'],1)
        ride=data['days'][0]['rides'][0]
        self.assertEqual(ride['selected']['stress'],100)
        self.assertEqual(ride['hr']['evidence_kind'],'summary')
        self.assertFalse(ride['hr']['completeness_verified'])
        self.assertEqual(ride['hr']['pause_treatment'],'unverified')
        self.assertEqual(ride['hr']['stream_rejections'][0]['reason'],'insufficient_hr_coverage')
        self.assertIsNone(ride['hr_candidates'][0]['stress'])
        self.assertEqual(ride['hr']['duration_basis'],'Strava API moving_time (reported moving seconds)')


    def test_summary_invalid_fields_and_unknown_duration_never_rescued_by_sparse_stream(self):
        from rideworks.strava_streams import persist
        def stream(values):return dict(data=values,original_size=len(values),resolution='high',series_type='time')
        valid=dict(self.item)
        for changes in [dict(has_heartrate=False),dict(average_heartrate=None),dict(average_heartrate=158),
                        dict(moving_time=0),dict(moving_time=3601),dict(elapsed_time=None)]:
            self.item=valid|changes;self.apply()
            persist(self.store,123,dict(time=stream([0,1800,3599]),heartrate=stream([143]*3)))
            data=training_state(self.store,'America/Los_Angeles',as_of=self.now)
            self.assertEqual(data['coverage']['scored'],0,changes)

    def test_valid_api_stream_precedes_conflicting_summary_mean(self):
        from rideworks.strava_streams import persist
        def stream(values):return dict(data=values,original_size=len(values),resolution='high',series_type='time')
        self.item['average_heartrate']=120;self.apply()
        persist(self.store,123,dict(time=stream(list(range(3600))),heartrate=stream([143]*3600)))
        ride,_=self.result()
        self.assertEqual(ride['selected']['stress'],100)
        self.assertEqual(ride['hr']['evidence_kind'],'stream')
        self.assertFalse(any(c['evidence_kind']=='summary' for c in ride['hr_candidates']))

    def test_historical_ftp_calendar_does_not_change_with_browser_timezone(self):
        from rideworks.strava_streams import persist
        def stream(values):return dict(data=values,original_size=len(values),resolution='high',series_type='time')
        self.item.update(start_date='2019-07-18T00:30:00Z',type='VirtualRide',sport_type='VirtualRide',device_watts=True,has_heartrate=False)
        self.apply();persist(self.store,123,dict(time=stream(list(range(3600))),watts=stream([200]*3600)))
        from rideworks.training_state import ride_results
        rides,_=ride_results(self.store,'Asia/Tokyo',as_of=self.now)
        self.assertEqual(rides[0]['day'],'2019-07-18')
        self.assertEqual(rides[0]['ftp']['calendar_date'],'2019-07-17')
        self.assertIsNone(rides[0]['ftp']['value'])
        self.assertIsNone(rides[0]['power']['stress'])


class SummarySourceTests(TestCase):
    def native(self,kind='TCX',**kwargs):
        return dict(source=dict(source_id='synthetic',content_format=kind),extraction={},
                    summary={},events=[],xml_context=dict(lap_summaries=[dict(avg_heart_rate=143,total_time_seconds=3600)]))|kwargs

    def test_tcx_single_lap_summary_does_not_assert_active_coverage_or_synthesize_work(self):
        from rideworks.training_state import native_hr_summary
        bad=hr_stream([0,1800,3599],[143]*3,settings=DEFAULT_HR,source=dict(format='TCX'),duration=3600)
        result=native_hr_summary(self.native(),DEFAULT_HR,[bad])
        self.assertAlmostEqual(result['stress'],100)
        self.assertEqual(result['source']['lap_index'],0)
        self.assertIsNone(result['coverage'])
        self.assertFalse(result['mean_active_scope_verified'])
        self.assertIn('unverified',result['scope'])
        self.assertEqual(result['stream_rejections'],[bad])
        self.assertEqual(selected_stress(dict(status='partial',stress=20,scope='partial'),result)['stress'],100)
        self.assertEqual(selected_stress(dict(status='calculated',stress=20,scope='recorded'),result)['stress'],20)
        self.assertNotIn('observed_work_kj',result)

    def test_missing_or_multi_lap_summaries_never_paired_or_combined(self):
        from rideworks.training_state import native_hr_summary
        for laps in [[],[dict(avg_heart_rate=143)],[dict(total_time_seconds=3600)],
                     [dict(avg_heart_rate=143,total_time_seconds=0)],
                     [dict(avg_heart_rate=143,total_time_seconds=1800)]*2]:
            self.assertIsNone(native_hr_summary(self.native(xml_context=dict(lap_summaries=laps)),DEFAULT_HR)['stress'])
        self.assertIsNone(native_hr_summary(self.native('GPX'),DEFAULT_HR)['stress'])

    def test_fit_reported_timer_summary_compatibility_and_known_pause(self):
        from rideworks.training_state import native_hr_summary
        events=timer(0,1800)+timer(1860,3660)
        native=self.native('FIT',summary=session(3660)|dict(avg_heart_rate=143,total_timer_time=3600),events=events)
        result=native_hr_summary(native,DEFAULT_HR)
        self.assertEqual(result['stress'],100)
        self.assertEqual(result['reported_duration_seconds'],3600)
        uncertain=native_hr_summary(native|dict(events=events[:-1]),DEFAULT_HR)
        self.assertEqual(uncertain['stress'],100)
        self.assertEqual(uncertain['pause_treatment'],'unverified')
        for update in [dict(total_timer_time=4000),dict(total_elapsed_time=float('nan')),dict(total_timer_time=3500)]:
            self.assertIsNone(native_hr_summary(native|dict(summary=native['summary']|update),DEFAULT_HR)['stress'])

    def test_competing_summary_sources_are_ambiguous_and_supported_stream_preferred(self):
        from rideworks.training_state import choose_hr
        one=hr_summary(143,3600,settings=DEFAULT_HR,source=dict(format='TCX',source_id='one'))
        two=hr_summary(120,3600,settings=DEFAULT_HR,source=dict(format='Strava API summary',source_id='two'))
        self.assertEqual(choose_hr([one,two],DEFAULT_HR)['reason'],'ambiguous_hr_sources')
        stream=hr_stream(list(range(3600)),[143]*3600,duration=3600,settings=DEFAULT_HR,source=dict(format='FIT',source_id='three'))
        self.assertEqual(choose_hr([one,two,stream],DEFAULT_HR),stream)
        other=stream|dict(source=dict(format='TCX',source_id='four'),stress=50)
        self.assertEqual(choose_hr([stream,other],DEFAULT_HR)['reason'],'ambiguous_hr_sources')

    def test_source_policy_version_recalculates_old_cache_then_reuses_it(self):
        with tempfile.TemporaryDirectory() as directory,Store(directory) as store:
            from rideworks.strava_api import apply_observations,normalize
            item=dict(id=123,name='Synthetic outdoor',type='Ride',sport_type='Ride',start_date='2026-10-01T12:00:00Z',moving_time=3600,elapsed_time=3600,has_heartrate=True,average_heartrate=143)
            apply_observations(store,[normalize(item)],321,1791500000)
            when=datetime(2026,10,9,tzinfo=timezone.utc)
            with patch('rideworks.training_state.VERSION','training-state-v1'):
                old=training_state(store,'UTC',as_of=when)
            with patch('rideworks.training_state.calculate_ride',wraps=__import__('rideworks.training_state',fromlist=['calculate_ride']).calculate_ride) as calc:
                new=training_state(store,'UTC',as_of=when);self.assertEqual(calc.call_count,1)
            self.assertNotEqual(old['version'],new['version'])
            with patch('rideworks.training_state.calculate_ride',side_effect=AssertionError('cache must reuse new policy')):
                self.assertEqual(new,training_state(store,'UTC',as_of=when))
