"""Synthetic Strava responses for watched segments and manual Sync."""
from datetime import timedelta
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode

import test_rideworks_strava as fixtures
from test_rideworks_strava import CREDS, FakeHTTP, Response
from rideworks.segments import CHECK_BUDGET, link_ids, tracked_counts
from rideworks.settings import Settings
from rideworks.strava import ApiClient, SyncError
from rideworks.web import Application

ACTIVITY = 9007199254740993
EFFORT = 9223372036854775806
SEGMENT = 9007199254740995
ORIGIN = 'http://127.0.0.1:8765'


class SegmentTests(unittest.TestCase):
    observation = fixtures.StravaTests.observation
    count = fixtures.StravaTests.count

    def setUp(self):
        fixtures.StravaTests.setUp(self)
        self.http = FakeHTTP()
        self.settings = Settings(self.store.data_dir, credentials=lambda: CREDS, client_factory=self.client)
        self.app = Application(self.store.data_dir, settings_factory=lambda root: self.settings)
        from unittest.mock import patch
        clock = patch('rideworks.strava.time.time', return_value=self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def client(self, credentials):
        client = ApiClient(credentials, opener=self.http)
        client.streams = lambda token, identity: {}
        return client

    def attempt(self, activity=ACTIVITY, effort=EFFORT, segment=SEGMENT, **overrides):
        return dict({'id': effort, 'segment': {'id': segment, 'name': 'Synthetic Watched Loop'},
                     'activity': {'id': activity}, 'athlete': {'id': 321},
                     'elapsed_time': 375, 'start_date': (self.start+timedelta(seconds=5)).isoformat()}, **overrides)

    def listing(self, activity):
        return self.observation(identity=activity, seconds=activity % 100 + 1,
                                external_id=f'zwift-activity-{activity}')

    def detail(self, activity, *efforts, **overrides):
        return self.listing(activity) | dict(resource_state=3, segment_efforts=list(efforts)) | overrides

    def add(self, activity=ACTIVITY, effort=EFFORT, origin=ORIGIN, **fields):
        body = dict(nonce=self.settings.nonce, link=f'https://www.strava.com/activities/{activity}/segments/{effort}')
        return self.app.post('/segments/add', urlencode(body | fields).encode(), origin)

    def sync(self, home=False):
        body = {'nonce': self.settings.nonce}
        if home:
            body['home'] = '1'
        return self.app.post('/settings/strava/sync', urlencode(body).encode(), ORIGIN)

    def test_link_precision_ownership_and_shared_protections(self):
        self.assertEqual(link_ids(f'https://www.strava.com/activities/{ACTIVITY}#{EFFORT}'),
                         (str(ACTIVITY), str(EFFORT)))
        for link in ('https://www.strava.com/segments/1', 'https://strava.com.evil.test/activities/1/segments/2',
                     'http://www.strava.com/activities/1/segments/2', 'https://www.strava.com/activities/1/segments/9223372036854775808'):
            with self.assertRaises(SyncError):
                link_ids(link)
        self.assertEqual(self.add(nonce='wrong')[0], 403)
        self.assertEqual(self.add(origin=None)[0], 403)
        with self.settings.operation:
            self.assertEqual(self.add()[0], 409)
        self.assertEqual(self.http.requests, [])
        for detail in (self.detail(ACTIVITY, self.attempt(athlete={'id': 322})),
                       self.detail(ACTIVITY, self.attempt(activity=42)),
                       self.detail(ACTIVITY, self.attempt(effort=EFFORT-1)),
                       self.detail(ACTIVITY, self.attempt(), athlete={'id': 322}),
                       self.detail(ACTIVITY, self.attempt(), sport_type='Ride')):
            self.http.responses.append(Response(detail))
            self.assertEqual(self.add()[0], 303)
            self.assertEqual(self.count('strava_watched_segments'), 0)
            self.assertEqual(self.count('strava_saved_efforts'), 0)
        self.assertTrue(self.http.requests[-1].full_url.endswith(f'/activities/{ACTIVITY}?include_all_efforts=true'))

    def test_selected_attempts_deduplicate_link_later_and_render_offline(self):
        old = self.attempt()
        other = self.attempt(effort=EFFORT-1, elapsed_time=369)
        self.http.responses.extend(Response(self.detail(ACTIVITY, old, other)) for _ in range(4))
        for effort in (EFFORT, EFFORT, EFFORT-1, EFFORT-1):
            self.assertEqual(self.add(effort=effort)[1]['Location'], '/segments')
        self.assertEqual(self.count('strava_watched_segments'), 1)
        self.assertEqual(self.count('strava_saved_efforts'), 2)
        html = self.app.get('/segments')[2].decode()
        self.assertIn('RideWorks ride link unavailable', html)
        self.assertIn('Fastest saved effort · 6:09', html)
        self.assertIn(str(EFFORT), html)
        self.http.responses.extend([Response([self.listing(ACTIVITY)]), Response(self.detail(ACTIVITY, old, other))])
        self.assertEqual(json.loads(self.sync(home=True)[2])['status'], 'complete')
        self.assertEqual(self.count('strava_saved_efforts'), 2)
        ride = self.store.connection.execute('SELECT activity_id FROM strava_api_activities WHERE external_id=?',
                                             (str(ACTIVITY),)).fetchone()[0]
        self.assertEqual(tracked_counts(self.store, [ride]), {ride: 1})
        for path in ('/', '/activities'):
            self.assertIn(f'/segments?ride={ride}">1 tracked segment', self.app.get(path)[2].decode())
        filtered = self.app.get(f'/segments?ride={ride}')[2].decode()
        self.assertEqual(filtered.count('Strava effort</a>'), 2)
        self.assertIn('All watched segments', filtered)
        self.assertNotIn('RideWorks ride link unavailable', filtered)
        self.assertEqual(len(self.http.requests), 6)

    def test_manual_sync_no_watchlist_budget_partial_and_retry_without_new_rides(self):
        def api_error(code):
            import io
            return HTTPError('https://www.strava.com', code, '', {}, io.BytesIO())
        self.http.responses.append(Response([self.listing(70)]))
        self.assertEqual(self.sync()[0], 303)
        self.assertEqual(len(self.http.requests), 1)
        self.http.responses.append(Response(self.detail(ACTIVITY, self.attempt())))
        self.add()
        ids = range(100, 100+CHECK_BUDGET+2)
        self.http.responses.append(Response([self.listing(70), *(self.listing(i) for i in ids)]))
        for i in list(ids)[:CHECK_BUDGET]:
            attempts = (self.attempt(activity=i, effort=i),) if i == 100 else ()
            self.http.responses.append(Response(self.detail(i, *attempts)))
        self.assertEqual(json.loads(self.sync(home=True)[2])['status'], 'complete')
        self.assertEqual(self.count('strava_pending_segment_rides'), 2)
        self.assertEqual(self.count('strava_saved_efforts'), 2)
        self.assertIn('Tracked segment checks pending for 2 rides.', self.app.get('/')[2].decode())
        self.http.responses.extend([Response([]), api_error(429)])
        self.assertEqual(self.sync()[0], 303)
        self.assertEqual(self.count('strava_pending_segment_rides'), 2)
        html = self.app.get('/settings')[2].decode()
        self.assertIn('Tracked segment checks pending for 2 rides.', html)
        self.assertIn('Strava rate limit reached.', html)
        self.http.responses.extend([Response([]), Response(self.detail(106)), Response(self.detail(105))])
        self.assertEqual(self.sync()[0], 303)
        self.assertEqual(self.count('strava_pending_segment_rides'), 0)
        self.assertEqual(self.count('strava_api_activities'), 8)
        self.assertEqual(self.count('strava_saved_efforts'), 2)
        self.assertEqual(self.http.responses, [])

    def test_incomplete_detail_keeps_ride_pending_for_retry(self):
        self.http.responses.append(Response(self.detail(ACTIVITY, self.attempt())))
        self.add()
        incomplete = self.detail(100)
        del incomplete['segment_efforts']
        self.http.responses.extend([Response([self.listing(100)]), Response(incomplete)])
        self.assertEqual(self.sync()[0], 303)
        self.assertEqual(self.count('strava_api_activities'), 1)
        self.assertEqual(self.count('strava_pending_segment_rides'), 1)
        self.assertEqual(self.count('strava_saved_efforts'), 1)
        self.http.responses.extend([Response([]), Response(self.detail(100))])
        self.assertEqual(self.sync()[0], 303)
        self.assertEqual(self.count('strava_pending_segment_rides'), 0)

    def test_authorization_stops_remaining_details_and_no_ride_is_lost(self):
        import io
        self.http.responses.append(Response(self.detail(ACTIVITY, self.attempt())))
        self.add()
        self.http.responses.extend([
            Response([self.listing(100), self.listing(101)]),
            HTTPError('https://www.strava.com', 401, '', {}, io.BytesIO()),
        ])
        self.assertEqual(json.loads(self.sync(home=True)[2])['status'], 'complete')
        self.assertEqual(self.count('strava_api_activities'), 2)
        self.assertEqual(self.count('strava_pending_segment_rides'), 2)
        self.assertEqual(self.count('strava_saved_efforts'), 1)
        self.assertEqual(len(self.http.requests), 3)
        self.assertIn('Check your Strava connection in Settings.', self.app.get('/')[2].decode())
