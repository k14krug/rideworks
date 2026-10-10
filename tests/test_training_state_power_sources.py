"""Independent stress eligibility preserves the best-20 Performance contract."""
from datetime import datetime, timezone
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from fit_fixture import make_fit
from rideworks.history import presentation
from rideworks.performance import evaluate, rebuild_performance, performance_history
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.strava_streams import persist
from rideworks.training_state import DEFAULT_HR, calculate_ride, evaluate_power, training_state

FTP = dict(value=200,status='available')


class PowerSourceTests(TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'store');self.addCleanup(self.store.close)

    def native(self,span=900,loss=0,power=200,activity_id=None):
        base=1100000000;times=[base+i for i in range(span) if not 400<=i<400+loss]
        path=self.root/f'fixture-{span}-{loss}-{power}.fit'
        path.write_bytes(make_fit(powers=[power]*len(times),heart_rates=[120]*len(times),timestamps=times,
            elapsed=span,timer=span,session_timestamp=base+span,event_timestamps=(base,base+span)))
        return self.store.import_file(path,activity_id=activity_id)

    def api(self,times,device=True,series='time'):
        item=dict(id=123,name='Synthetic virtual workout',type='VirtualRide',sport_type='VirtualRide',
            start_date='2026-10-01T12:00:00Z',elapsed_time=times[-1]+1,moving_time=len(times),
            device_watts=device,has_heartrate=True,average_heartrate=120)
        apply_observations(self.store,[normalize(item)],321,1791500000)
        def stream(values):return dict(data=values,original_size=len(values),resolution='high',series_type=series)
        persist(self.store,123,dict(time=stream(times),watts=stream([200]*len(times))))
        return self.store.activity_history()[0]

    def result(self,snapshot=None):
        s=snapshot or self.store.activity_history()[0]
        return calculate_ride(self.store,s,presentation(s),FTP,DEFAULT_HR)

    def test_short_complete_power_scores_without_best20_and_preserves_performance(self):
        self.native();s=self.store.activity_history()[0]
        rebuild_performance(self.store);before=performance_history(self.store)
        self.assertEqual(evaluate(self.store,s)['reason'],'activity_shorter_than_required')
        r=self.result(s);self.assertEqual(r['selected']['method'],'power');self.assertEqual(r['selected']['stress'],25)
        self.assertTrue(r['power']['whole_session_verified'])
        self.assertEqual(performance_history(self.store),before)

    def test_short_fit_gap_estimate_without_best20_keeps_observed_work(self):
        self.native(loss=6);r=self.result()
        self.assertEqual(r['power']['status'],'corrected_estimate');self.assertEqual(r['power']['stress'],25)
        self.assertEqual(r['power']['observed_work_kj'],178.8);self.assertFalse(r['power']['whole_session_verified'])

    def test_no_best20_continuous_window_still_has_partial_stress(self):
        # Break every possible 1200-second window while retaining two >=600-second runs.
        base=1100000000
        path=self.root/'middle.fit';times=[base+i for i in range(1800) if not 890<=i<910]
        path.write_bytes(make_fit(powers=[200]*1780,heart_rates=[120]*1780,timestamps=times,
            elapsed=1800,timer=1800,session_timestamp=base+1800,event_timestamps=(base,base+1800)))
        imported=self.store.import_fit(path);s=self.store.activity_history(imported['activity_id'])[0]
        self.assertFalse(evaluate(self.store,s)['eligible'])
        r=self.result(s);self.assertEqual(r['power']['status'],'partial');self.assertEqual(len(r['power']['intervals']),2)
        self.assertAlmostEqual(r['power']['stress'],1780/36)
        self.assertEqual(r['selected']['method'],'power')

    def test_competing_native_stress_sources_rejected_without_ranking(self):
        a=self.native();self.native(power=250,activity_id=a['activity_id'])
        r=self.result();self.assertEqual(r['power']['reason'],'multiple_usable_power_sources')
        self.assertIsNone(r['power']['stress']);self.assertEqual(len(r['power_candidates']),2)

    def test_short_api_observed_only_and_device_trust(self):
        s=self.api(list(range(900)));self.assertFalse(evaluate(self.store,s)['eligible'])
        r=self.result(s);self.assertEqual(r['selected']['stress'],25);self.assertEqual(r['selected']['method'],'power')
        s=self.api(list(range(900)),device=False);r=self.result(s)
        self.assertEqual(r['power']['reason'],'api_device_watts_not_confirmed');self.assertEqual(r['selected']['method'],'hr')

    def test_api_gap_retains_hr_precedence_without_session_estimator(self):
        s=self.api(list(range(900))+list(range(905,1800)))
        r=self.result(s);self.assertEqual(r['power']['status'],'partial');self.assertEqual(r['power']['corrected_seconds'],0)
        self.assertEqual(r['selected']['method'],'hr');self.assertNotIn('session_estimate',r)

    def test_native_power_blocks_api_fallback(self):
        s=self.api(list(range(900)));identity=s['activity']['activity_id']
        self.native(span=500,activity_id=identity);r=self.result(self.store.activity_history(identity)[0])
        self.assertIsNone(r['power']['stress']);self.assertEqual(len(r['power_candidates']),1)
        self.assertEqual(r['power_candidates'][0]['source']['format'],'FIT')

    def test_api_pairing_and_current_source_ambiguity_never_ranked(self):
        s=self.api(list(range(900)));observations=self.store.strava_stream_evidence(s['activity']['activity_id'])
        other=deepcopy(observations[0]);other['source_id']='synthetic-competing-observation'
        with patch.object(self.store,'strava_stream_evidence',return_value=observations+[other]):
            power,_=evaluate_power(self.store,s,FTP)
            self.assertEqual(power['reason'],'api_current_source_ambiguous');self.assertIsNone(power['stress'])
        malformed=deepcopy(observations);malformed[0]['streams']['watts']['series_type']='distance'
        with patch.object(self.store,'strava_stream_evidence',return_value=malformed):
            power,_=evaluate_power(self.store,s,FTP)
            self.assertEqual(power['reason'],'api_stream_pairing_ambiguous');self.assertIsNone(power['stress'])

    def test_missing_ftp_never_backfilled_but_observed_work_survives(self):
        self.native();p,c=evaluate_power(self.store,self.store.activity_history()[0],dict(value=None,status='unknown_prehistory'))
        self.assertIsNone(p['stress']);self.assertEqual(p['reason'],'ftp_unavailable');self.assertEqual(p['observed_work_kj'],180)

    def test_power_policy_changes_invalidate_cache_then_reuse(self):
        self.native();now=datetime(2026,10,9,tzinfo=timezone.utc)
        with patch('rideworks.training_state.POWER_SOURCE_POLICY','old-synthetic-policy'):
            old=training_state(self.store,'UTC',as_of=now)
        with patch('rideworks.training_state.calculate_ride',wraps=calculate_ride) as calc:
            new=training_state(self.store,'UTC',as_of=now);self.assertEqual(calc.call_count,1)
        self.assertNotEqual(new['power_source_policy'],old['power_source_policy'])
        with patch('rideworks.training_state.calculate_ride',side_effect=AssertionError('current cache must be reused')):
            self.assertEqual(new,training_state(self.store,'UTC',as_of=now))
