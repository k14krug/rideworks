"""Synthetic diagnostic checks; no production source policy changes."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from unittest import TestCase

from fit_fixture import make_fit
from rideworks.history import presentation
from rideworks.performance import evaluate
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.strava_streams import persist
from rideworks.training_state import DEFAULT_HR, calculate_ride
from tools.diagnose_training_state_power import bins, candidates, table_digest

FTP = dict(value=200, status='available')


class PowerDiagnosisTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/'store'); self.addCleanup(self.store.close)

    def api(self, times, *, device_watts=True, kind='VirtualRide'):
        item = dict(id=123, name='Synthetic structured workout', type=kind, sport_type=kind,
            start_date='2026-10-01T12:00:00Z', elapsed_time=times[-1]+1,
            moving_time=len(times), device_watts=device_watts,
            has_heartrate=True, average_heartrate=120)
        apply_observations(self.store, [normalize(item)], 321, 1791500000)
        def stream(values):
            return dict(data=values, original_size=len(values), resolution='high', series_type='time')
        persist(self.store, 123, dict(time=stream(times), watts=stream([200]*len(times))))
        return self.store.activity_history()[0]

    def diagnose(self, snapshot):
        row = presentation(snapshot)
        before = table_digest(self.store.connection)
        self.store.connection.execute('PRAGMA query_only=ON')
        result = candidates(self.store, snapshot, FTP, row['activity_type'])
        self.assertEqual(table_digest(self.store.connection), before)
        return result

    def test_short_native_recording_has_stress_but_no_best20(self):
        base = 1100000000; seconds = 900
        path = Path(self.temp.name)/'synthetic.fit'
        path.write_bytes(make_fit(powers=[200]*seconds, heart_rates=[120]*seconds,
            timestamps=list(range(base,base+seconds)), elapsed=seconds, timer=seconds,
            session_start_time=base, session_timestamp=base+seconds,
            event_timestamps=(base,base+seconds)))
        self.store.import_fit(path); snapshot = self.store.activity_history()[0]
        self.assertEqual(evaluate(self.store,snapshot)['reason'], 'activity_shorter_than_required')
        sources, checks = self.diagnose(snapshot)
        self.assertEqual(checks,1)
        self.assertEqual(sources[0]['diagnostic_power']['status'],'calculated')
        self.assertEqual(sources[0]['diagnostic_power']['stress'],25)
        self.assertFalse(evaluate(self.store,snapshot)['eligible'])

    def test_long_api_gap_passes_best20_but_hr_wins_over_partial(self):
        snapshot = self.api(list(range(2500))+list(range(2634,2809)))
        self.assertTrue(evaluate(self.store,snapshot)['eligible'])
        sources, checks = self.diagnose(snapshot); power = sources[0]['diagnostic_power']
        self.assertEqual(power['status'],'partial'); self.assertEqual(power['corrected_seconds'],0)
        self.assertEqual(power['missing_seconds'],134); self.assertEqual(power['excluded_short_seconds'],175)
        self.assertEqual(checks,1); self.assertAlmostEqual(power['stress'],2500/36)
        result = calculate_ride(self.store,snapshot,presentation(snapshot),FTP,DEFAULT_HR)
        self.assertEqual(result['selected']['method'],'hr')
        self.assertEqual(result['power']['stress'],power['stress'])

    def test_short_api_power_candidate_does_not_require_best20(self):
        snapshot = self.api(list(range(900)))
        self.assertFalse(evaluate(self.store,snapshot)['eligible'])
        sources, checks = self.diagnose(snapshot)
        self.assertEqual(checks,1)
        self.assertEqual(sources[0]['diagnostic_power']['stress'],25)

    def test_unconfirmed_device_watts_and_outdoor_power_remain_excluded(self):
        snapshot = self.api(list(range(900)),device_watts=False)
        sources, checks = self.diagnose(snapshot)
        self.assertEqual(checks,0)
        self.assertEqual(sources[0]['trust_rejection'],'api_device_watts_not_confirmed')
        self.assertIsNone(sources[0]['diagnostic_power'])
        self.store.connection.execute('PRAGMA query_only=OFF')
        snapshot = self.api(list(range(900)),kind='Ride')
        sources, checks = self.diagnose(snapshot)
        self.assertEqual(sources[0]['trust_rejection'],'outdoor_or_nonvirtual_power_not_admitted')
        self.assertIsNone(sources[0]['diagnostic_power'])

    def test_recording_summary_does_not_join_gaps_or_choose_duplicate_watts(self):
        result = bins([0,1,1,2,100,101],[200]*6)
        self.assertEqual(result['duplicate_timestamp_bins'],2)
        self.assertEqual(result['valid_unique_power_bins'],4)
        self.assertEqual([r['seconds'] for r in result['continuous_runs']],[1,1,2])
        self.assertEqual(result['timestamp_gaps'][-1]['missing_seconds'],97)
