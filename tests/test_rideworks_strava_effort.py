"""Synthetic Strava score evidence and bounded recent refresh tests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import tempfile
import unittest

from rideworks.store import Store
from rideworks.strava import TokenFile
from rideworks.strava_api import SyncError, apply_observations, normalize
from rideworks.strava_effort import for_store, score
from rideworks.strava_effort_refresh import MAX_ACTIVITIES, refresh_recent
from rideworks.web import Application


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'data')
        self.addCleanup(self.store.close)
        self.now = int(datetime.now(timezone.utc).timestamp())
        TokenFile(self.store.data_dir).save(dict(access_token='fake', refresh_token='fake',
            expires_at=self.now + 7200, athlete_id=321, scope='activity:read_all'))

    def observation(self, identity=1, days=1, **fields):
        return dict(id=identity, name='Synthetic ride', type='Ride', sport_type='VirtualRide',
                    start_date=(datetime.fromtimestamp(self.now, timezone.utc)-timedelta(days=days)).isoformat(),
                    elapsed_time=3600, moving_time=3600, distance=10000, **fields)

    def add(self, item):
        apply_observations(self.store, [normalize(item)], 321, self.now-100)
        return self.store.connection.execute('SELECT activity_id FROM strava_api_activities WHERE external_id=?',
                                             (str(item['id']),)).fetchone()[0]

    def test_normalization_and_fixed_boundaries(self):
        base = self.observation()
        self.assertNotIn('suffer_score', normalize(base))
        self.assertIsNone(normalize(base | {'suffer_score': None})['suffer_score'])
        for value in (0, 0.0, 19, 20, 39, 40, 69, 70, 109, 110, 999):
            self.assertEqual(normalize(base | {'suffer_score': value})['suffer_score'], value)
        for value in (True, '10', -1, float('nan'), float('inf'), [], {}):
            with self.subTest(value=value), self.assertRaises(SyncError):
                normalize(base | {'suffer_score': value})
        cases = {0:'very-light',19:'very-light',20:'light',39:'light',40:'moderate',69:'moderate',
                 70:'high',109:'high',110:'very-high',999:'very-high'}
        for value, slug in cases.items():
            self.assertEqual(score(value)['slug'], slug)
        self.assertEqual(score(0.0)['value'], '0')
        self.assertIsNone(score(None))

    def test_only_current_associated_score_and_three_surfaces(self):
        item = self.observation(suffer_score=19)
        activity_id = self.add(item)
        self.add(item | {'suffer_score': 70})
        self.assertEqual(for_store(self.store)[activity_id]['value'], '70')
        app = Application(self.store.data_dir)
        for route in ('/', '/activities', '/activities/' + activity_id):
            status, _, body = app.get(route)
            self.assertEqual(status, 200)
            self.assertIn('Strava Relative Effort: 70, High', body.decode())
            self.assertNotIn('previous 42 days', body.decode())
        for value, label in ((None, 'Strava Relative Effort unavailable'), (0, 'Strava Relative Effort: 0, Very Light')):
            self.add(item | {'suffer_score': value})
            for route in ('/', '/activities', '/activities/' + activity_id):
                self.assertIn(label, app.get(route)[2].decode())

    def test_recent_refresh_is_bounded_and_preserves_checkpoint(self):
        targets = {}
        for i in range(1, MAX_ACTIVITIES + 4):
            item = self.observation(i, days=1)
            targets[str(i)] = (self.add(item), item | {'suffer_score': i})
        old = self.observation(999, days=61)
        self.add(old)
        before = tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone())

        class FakeClient:
            rate = {}
            def __init__(self): self.requested = []
            def activity_summary(self, token, external):
                self.requested.append(external)
                return targets[external][1]

        client = FakeClient()
        report = refresh_recent(self.store, client, now=self.now)
        self.assertEqual(report['activity_requests'], MAX_ACTIVITIES)
        self.assertEqual(len(client.requested), MAX_ACTIVITIES)
        self.assertNotIn('999', client.requested)
        self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone()), before)
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM activities').fetchone()[0], MAX_ACTIVITIES + 4)
        scores = for_store(self.store)
        for external in client.requested:
            self.assertEqual(scores[targets[external][0]]['value'], external)

    def test_multiple_current_api_associations_are_unavailable(self):
        first = self.add(self.observation(1, suffer_score=20))
        other = self.add(self.observation(2, suffer_score=70))
        self.store.connection.execute('UPDATE strava_api_activities SET activity_id=? WHERE external_id=?', (first, '2'))
        self.store.connection.execute('UPDATE strava_api_sources SET activity_id=? WHERE external_id=?', (first, '2'))
        self.assertIsNone(for_store(self.store)[first])
        self.assertNotEqual(first, other)

    def test_bad_target_response_keeps_all_observations_unchanged(self):
        self.add(self.observation(1))
        self.add(self.observation(2))
        before = [tuple(r) for r in self.store.connection.execute('SELECT * FROM strava_api_activities')]

        class FakeClient:
            rate = {}
            def activity_summary(inner, token, external):
                return self.observation(int(external), suffer_score=-1)

        with self.assertRaises(SyncError):
            refresh_recent(self.store, FakeClient(), now=self.now)
        self.assertEqual([tuple(r) for r in self.store.connection.execute('SELECT * FROM strava_api_activities')], before)


class ScoreOnlyStreamRegression(unittest.TestCase):
    observation = ScoreTests.observation
    add = ScoreTests.add

    def setUp(self):
        ScoreTests.setUp(self)
        from ftp_fixture import seed_ftp
        from rideworks.strava_streams import persist
        from rideworks.performance import rebuild_performance
        from rideworks.power_curve import rebuild_curves
        seed_ftp(self.store, [('2000-01-01', 200)])
        self.item = self.observation(101, days=1, device_watts=True, has_heartrate=True,
                                     average_heartrate=140) | dict(elapsed_time=1800, moving_time=1800)
        self.identity = self.add(self.item)
        def stream(values):
            return dict(data=values, original_size=len(values), resolution='high', series_type='time')
        persist(self.store, 101, dict(time=stream(list(range(1800))), watts=stream([200]*1800),
                                      heartrate=stream([140]*1800)))
        rebuild_performance(self.store)
        rebuild_curves(self.store)

    def numbers(self):
        from rideworks.history import presentation
        from rideworks.performance import performance_history
        from rideworks.power_curve import curve_history, rebuild_curves
        from rideworks.training_state import calculate_ride, DEFAULT_HR, training_state
        from rideworks.planning import plan
        snapshot = self.store.activity_history(self.identity)[0]
        perf = next(r for r in performance_history(self.store)['results'] if r['activity_id'] == self.identity)
        rebuild_curves(self.store)
        curve = curve_history(self.store)['results'][self.identity]
        ride = calculate_ride(self.store, snapshot, presentation(snapshot), dict(value=200,status='available'), DEFAULT_HR)
        state = training_state(self.store, 'UTC', as_of=datetime.fromtimestamp(self.now, timezone.utc))
        proposed = plan(self.store, 'UTC', as_of=datetime.fromtimestamp(self.now, timezone.utc))
        return (perf['eligible'], perf['average_watts'],
                [(p['duration_seconds'], p['average_watts']) for p in curve['points']],
                ride['hr']['stress'], ride['hr']['evidence_kind'], ride['selected']['stress'],
                [(d['day'], d['fitness'], d['fatigue'], d['form']) for d in state['days']], {k: proposed[k] for k in ('days', 'next_ride', 'recent_hard_dates', 'provisional')})

    def test_score_revisions_reuse_stream_and_preserve_results(self):
        from rideworks.strava_streams import enrich
        from rideworks.performance import performance_history
        from rideworks.power_curve import curve_history
        before = self.numbers()
        self.assertTrue(before[0]); self.assertTrue(before[2]); self.assertIsNotNone(before[3])
        self.assertEqual(before[4], 'stream'); self.assertIsNotNone(before[5])
        old_stream = tuple(self.store.connection.execute('SELECT * FROM strava_stream_sources').fetchone())
        old_summary = old_stream[3]
        class Client:
            rate = {}
            stream_requests = 0
            def activity_summary(inner, token, external): return self.item
            def streams(inner, *args): raise AssertionError('compatible stream must be reused')
        client = Client()
        for value in (19, 70, None):
            self.item = self.item | {'suffer_score': value}
            report = refresh_recent(self.store, client, now=self.now)
            self.assertEqual(report['skipped_non_score_changes'], 0)
            self.assertEqual(report['performance_pending'], 0)
            self.assertEqual(performance_history(self.store)['pending'], 0)
            self.assertEqual(curve_history(self.store)['pending'], 0)
            self.assertEqual(enrich(self.store, client, 'fake', ['101'])['stream_reused'], 1)
            self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM strava_stream_sources').fetchone()), old_stream)
            observation = self.store.strava_stream_evidence(self.identity)[0]
            self.assertTrue(observation['summary_compatible'])
            self.assertEqual(observation['summary_source_id'], old_summary)
            self.assertNotEqual(observation['current_summary_source_id'], old_summary)
            self.assertEqual(self.numbers(), before)

    def test_non_score_changes_remain_stale(self):
        from rideworks.performance import evaluate
        from rideworks.power_curve import evaluate as curve_evaluate
        from rideworks.training_state import evaluate_power, calculate_ride, DEFAULT_HR
        from rideworks.history import presentation
        variants = [dict(start_date=(datetime.fromtimestamp(self.now, timezone.utc)-timedelta(days=2)).isoformat()),
                    dict(device_watts=False), dict(moving_time=1799), dict(sport_type='Ride')]
        for change in variants:
            self.add(self.item | change)
            snapshot = self.store.activity_history(self.identity)[0]
            self.assertFalse(self.store.strava_stream_evidence(self.identity)[0]['summary_compatible'])
            if 'sport_type' not in change:
                self.assertEqual(evaluate(self.store, snapshot)['reason'], 'api_stream_summary_not_current')
                self.assertEqual(curve_evaluate(self.store, snapshot)['reason'], 'api_stream_summary_not_current')
            ride = calculate_ride(self.store, snapshot, presentation(snapshot), dict(value=200,status='available'), DEFAULT_HR)
            self.assertFalse(any(c.get('evidence_kind') == 'stream' and c.get('source', {}).get('format') == 'Strava API stream' for c in ride['hr_candidates']))
            reason = evaluate_power(self.store, snapshot, dict(value=200,status='available'))[0]['reason']
            self.assertEqual(reason, 'outdoor_ride_excluded' if 'sport_type' in change else 'api_stream_summary_not_current')

    def test_targeted_non_score_change_is_skipped(self):
        before_source = tuple(self.store.connection.execute('SELECT * FROM strava_api_activities').fetchone())
        before_checkpoint = tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone())
        before_stream = tuple(self.store.connection.execute('SELECT * FROM strava_stream_sources').fetchone())
        class Client:
            rate = {}
            def activity_summary(inner, token, external): return self.item | {'name':'Changed', 'suffer_score':45}
        report = refresh_recent(self.store, Client(), now=self.now)
        self.assertEqual((report['activity_requests'], report['observations'], report['skipped_non_score_changes']), (1, 0, 1))
        self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM strava_api_activities').fetchone()), before_source)
        self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone()), before_checkpoint)
        self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM strava_stream_sources').fetchone()), before_stream)

    def test_concurrent_summary_change_aborts_targeted_write(self):
        class Client:
            rate = {}
            def activity_summary(inner, token, external):
                self.add(self.item | {'name': 'Concurrent change'})
                return self.item | {'suffer_score': 10}
        with self.assertRaisesRegex(SyncError, 'changed during preflight'):
            refresh_recent(self.store, Client(), now=self.now)
        current = self.store.connection.execute('SELECT s.evidence_json FROM strava_api_activities a JOIN strava_api_sources s ON s.source_id=a.current_source_id WHERE a.external_id=?', ('101',)).fetchone()[0]
        self.assertEqual(json.loads(current)['name'], 'Concurrent change')
        self.assertNotIn('suffer_score', json.loads(current))

    def test_other_external_activity_cannot_borrow_stream(self):
        other = self.add(self.observation(102, days=1, device_watts=True))
        self.store.connection.execute('UPDATE strava_stream_sources SET summary_source_id=(SELECT current_source_id FROM strava_api_activities WHERE external_id=?) WHERE external_id=?', ('102','101'))
        self.assertEqual(self.store.strava_stream_evidence(self.identity), [])
        self.assertEqual(self.store.strava_stream_evidence(other), [])


if __name__ == '__main__':
    unittest.main()
