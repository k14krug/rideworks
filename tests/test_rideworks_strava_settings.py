"""Settings integration with real loopback HTTP and fake Strava responses only."""
from contextlib import redirect_stdout
from http.client import HTTPConnection
import io
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

import test_rideworks_strava as fixture
from test_rideworks_strava import CREDS, Response, FakeHTTP
from rideworks.config import ConfigurationError
from rideworks.errors import RideWorksError
from rideworks.history import browse, presentation
from rideworks.performance import rebuild_performance, performance_history
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import csv
from rideworks.settings import Settings
from rideworks.strava import ApiClient, TokenFile, sync, disconnect
from rideworks.web import Application, create_server


class SettingsTests(unittest.TestCase):
    observation = fixture.StravaTests.observation
    count = fixture.StravaTests.count

    def setUp(self):
        fixture.StravaTests.setUp(self)
        self.http = FakeHTTP()
        self.credentials = CREDS
        self.settings = Settings(self.store.data_dir, credentials=self.configured,
                                 client_factory=lambda credentials: self.metadata_client(credentials))
        self.settings.port = 8765
        self.app = Application(self.store.data_dir, settings_factory=lambda root: self.settings)
        self.clock = patch('rideworks.strava.time.time', return_value=self.now)
        self.clock.start(); self.addCleanup(self.clock.stop)

    def metadata_client(self, credentials):
        client=ApiClient(credentials, opener=self.http)
        client.streams=lambda access,identity:{}  # Metadata/Settings tests; separate stream integration covers fetches.
        return client

    def configured(self):
        if self.credentials is None:
            raise ConfigurationError('private-secret-that-must-not-appear')
        return self.credentials

    def html(self):
        return self.app.get('/settings')[2].decode()

    def post(self, action, *, nonce=None, origin='http://127.0.0.1:8765'):
        return self.settings.post('/settings/strava/' + action,
                                  urlencode({'nonce': self.settings.nonce if nonce is None else nonce}).encode(), origin)

    def connect(self):
        self.tokens.clear()
        response = self.post('connect')
        self.assertEqual(response[0], 303)
        values = parse_qs(urlsplit(response[1]['Location']).query)
        self.assertEqual(values['scope'], ['activity:read_all'])
        self.assertEqual(values['redirect_uri'], ['http://127.0.0.1:8765/strava/callback'])
        return values['state'][0]

    def token_response(self):
        return Response(dict(access_token='new-fake-access', refresh_token='new-fake-refresh',
                             expires_at=self.now+7200, athlete={'id': 321}, scope='activity:read_all'))

    def assert_private(self, value):
        for secret in (CREDS[0], CREDS[1], 'synthetic-access', 'synthetic-refresh',
                       'new-fake-access', 'new-fake-refresh', 'private-code', 'private-secret-that-must-not-appear'):
            self.assertNotIn(secret, value)

    def home_action(self, sync=False, nonce=None, origin='http://127.0.0.1:8765'):
        fields = {'nonce': self.settings.nonce if nonce is None else nonce}
        if sync:
            fields['home'] = '1'
        return self.app.post('/settings/strava/sync' if sync else '/home/strava/check',
                             urlencode(fields).encode(), origin)

    def test_home_checks_known_export_and_new_then_shared_sync(self):
        self.assertIn('Sync now', self.app.get('/')[2].decode())
        self.assertEqual(self.http.requests, [])
        self.http.responses.append(Response([self.observation()]))
        for _ in range(2):
            self.assertEqual(json.loads(self.home_action()[2])['status'], 'clear')
        self.assertEqual(len(self.http.requests), 1)
        self.assertEqual(self.count('strava_sync_state'), 0)
        self.assertEqual(self.count('strava_api_activities'), 0)
        self.settings.recent_rides.invalidate()
        rows = [self.observation(), self.observation(identity=2, seconds=1)]
        self.http.responses.extend(Response(rows) for _ in range(3))
        self.assertEqual(json.loads(self.home_action()[2])['status'], 'new')
        self.assertEqual(self.home_action(True, nonce='bad')[0], 403)
        self.assertEqual(self.home_action(True, origin=None)[0], 403)
        self.assertEqual(self.home_action(origin='https://untrusted.example')[0], 403)
        with self.settings.operation:
            self.assertEqual(self.home_action(True)[0], 409)
            self.assertEqual(self.post('sync')[0], 409)
        self.assertEqual(json.loads(self.home_action(True)[2])['status'], 'complete')
        self.assertIn('Strava sync complete.', self.app.get('/')[2].decode())
        self.assertEqual(self.count('strava_api_activities'), 2)
        self.assertEqual(json.loads(self.home_action()[2])['status'], 'clear')
        self.assertEqual(len(self.http.requests), 4)

    def test_home_check_caches_incomplete_offline_and_rate_limit(self):
        from urllib.error import URLError
        for reply, expected in (
            (Response([self.observation()] * 100), 'incomplete'),
            (URLError('offline'), 'unavailable'),
            (HTTPError('https://www.strava.com', 429, '', {}, io.BytesIO()), 'rate_limited'),
        ):
            self.settings.recent_rides.invalidate()
            self.http.responses.append(reply)
            before = len(self.http.requests)
            for _ in range(2):
                self.assertEqual(json.loads(self.home_action()[2])['status'], expected)
            self.assertEqual(len(self.http.requests), before + 1)
        self.tokens.clear()
        self.assertEqual(json.loads(self.home_action()[2])['status'], 'disconnected')
        self.assertNotIn('Sync now', self.app.get('/')[2].decode())
        self.assertEqual(self.count('strava_sync_state'), 0)

    def test_home_check_coalesces_and_discards_pre_sync_response(self):
        entered, release, joined = (threading.Event() for _ in range(3))
        calls = []
        observation = self.observation(identity=2)

        class DelayedClient:
            def activities(inner, token, window, page):
                calls.append(page)
                entered.set()
                if not release.wait(5):
                    raise AssertionError('Test did not release the check')
                return [observation]

        checker = self.settings.recent_rides
        checker.client_factory = lambda credentials: DelayedClient()
        results = []
        def check():
            results.append(json.loads(self.home_action()[2])['status'])
        first = threading.Thread(target=check)
        second = threading.Thread(target=check)
        first.start()
        try:
            self.assertTrue(entered.wait(5))
            wait = checker.flight.result
            def signal_join(*args, **kwargs):
                joined.set()
                return wait(*args, **kwargs)
            with patch.object(checker.flight, 'result', side_effect=signal_join):
                second.start()
                self.assertTrue(joined.wait(5))
                self.http.responses.append(Response([observation]))
                self.assertEqual(self.post('sync')[0], 303)
        finally:
            release.set()
            first.join(5)
            if second.ident is not None:
                second.join(5)
        self.assertEqual(calls, [1])
        self.assertEqual(results, ['superseded', 'superseded'])
        self.assertEqual(json.loads(self.home_action()[2])['status'], 'clear')
        self.assertEqual(calls, [1, 1])

    def test_navigation_missing_configured_connected_and_attention(self):
        self.tokens.clear(); self.credentials = None
        html = self.html()
        self.assertIn('Missing', html); self.assertIn('Not connected', html)
        self.assertNotIn('Connect Strava</button>', html); self.assertIn('.env', html)
        self.assert_private(html)
        self.credentials = CREDS
        self.assertIn('Connect Strava</button>', self.html())
        self.tokens.path.write_text('invalid-private-secret-that-must-not-appear')
        html = self.html(); self.assertIn('Authorization needs attention', html)
        self.assertIn('Reconnect Strava', html); self.assert_private(html)
        self.http.responses.append(self.token_response())
        state = self.connect()
        self.settings.callback(urlencode(dict(state=state, code='private-code', scope='activity:read_all')))
        html = self.html(); self.assertIn('Connected', html); self.assertIn('Sync now', html)
        self.assertIn('Disconnect', html); self.assert_private(html)

    def test_oauth_shared_exchange_clean_redirect_private_storage_and_one_use(self):
        state = self.connect(); self.http.responses.append(self.token_response())
        with patch('rideworks.settings.complete_connect', wraps=__import__('rideworks.strava', fromlist=['complete_connect']).complete_connect) as exchange:
            result = self.settings.callback(urlencode(dict(state=state, code='private-code', scope='read,activity:read_all')))
        self.assertEqual(exchange.call_count, 1)
        self.assertEqual(result, (303, {'Location': '/settings'}, b''))
        self.assertEqual(self.tokens.read()['refresh_token'], 'new-fake-refresh')
        self.assertEqual(self.tokens.path.stat().st_mode & 0o777, 0o600)
        self.assert_private(self.html())
        requests = len(self.http.requests)
        self.settings.callback(urlencode(dict(state=state, code='private-code', scope='activity:read_all')))
        self.assertEqual(len(self.http.requests), requests)

    def test_declined_expired_nonascii_bad_state_missing_scope_and_wrong_athlete(self):
        for changes in ({'state': 'é'}, {'state': 'wrong'}, {'scope': 'read'}, {'error': 'denied'}):
            state = self.connect()
            result = self.settings.callback(urlencode(dict(state=state, code='private-code', scope='activity:read_all') | changes))
            self.assertEqual(result[1], {'Location': '/settings'})
            self.assertFalse(self.tokens.path.exists()); self.assertEqual(self.http.requests, [])
            self.assertIn('Authorization needs attention', self.html()); self.assert_private(self.html())
        self.connect(); self.settings.pending = (self.settings.pending[0], 0)
        self.assertIn('Authorization timed out', self.html())
        self.assertIn('127.0.0.1', self.html())
        self.settings.callback('code=private-code')
        self.assertEqual(self.http.requests, [])
        state = self.connect()
        self.http.responses.append(Response(dict(access_token='new-fake-access', refresh_token='new-fake-refresh', expires_at=self.now+7200, athlete={'id': 999})))
        self.store.connection.execute('INSERT INTO strava_sync_state VALUES(1,?,?)', ('321', self.now-1))
        self.settings.callback(urlencode(dict(state=state, code='private-code', scope='activity:read_all')))
        self.assertFalse(self.tokens.path.exists()); self.assert_private(self.html())

    def test_nonce_origin_method_actions_and_duplicate_submission(self):
        for nonce, origin in (('', 'http://127.0.0.1:8765'), ('wrong', 'http://127.0.0.1:8765'),
                              (None, None), (None, 'https://untrusted.example')):
            self.assertEqual(self.post('disconnect', nonce=nonce, origin=origin)[0], 403)
        for body in (b'', b'nonce=%FF', b'nonce=x&nonce=x', b'nonce=x&extra=1&extra2=2'):
            self.assertEqual(self.settings.post('/settings/strava/sync', body, 'http://127.0.0.1:8765')[0], 403)
        self.assertTrue(self.tokens.path.exists()); self.assertEqual(self.http.requests, [])
        # GET never dispatches a state-changing action.
        self.assertEqual(self.app.get('/settings/strava/disconnect')[0], 404)
        self.http.responses.append(Response({}))
        nonce = self.settings.nonce
        self.assertEqual(self.post('disconnect', nonce=nonce)[0], 303)
        self.assertEqual(self.post('disconnect', nonce=nonce)[0], 403)
        self.assertFalse(self.tokens.path.exists()); self.assertEqual(self.count('activities'), 1)

    def test_sync_calls_shared_logic_retains_compact_outcome_restart_idempotence_refresh(self):
        self.http.responses.append(Response([self.observation(), self.observation(identity=2, seconds=1)]))
        with patch('rideworks.settings.sync', wraps=sync) as shared:
            self.assertEqual(self.post('sync')[0], 303)
        self.assertEqual(shared.call_count, 1)
        html = self.html(); self.assertIn('1 new · 1 enriched · 0 unchanged', html)
        self.assertIn('Performance updated', html); self.assertNotIn('class="performance-update"',html); self.assert_private(html)
        checkpoint = tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone())
        old_count = self.count('strava_api_sources')
        state = self.tokens.read(); state['expires_at'] = self.now; self.tokens.save(state)
        restarted = Settings(self.store.data_dir, credentials=self.configured,
                             client_factory=lambda credentials: self.metadata_client(credentials))
        restarted_app = Application(self.store.data_dir, settings_factory=lambda root: restarted)
        self.assertIn('1 new · 1 enriched · 0 unchanged', restarted_app.get('/settings')[2].decode())
        self.http.responses.extend([self.token_response(), Response([self.observation(), self.observation(identity=2, seconds=1)])])
        result = restarted.post('/settings/strava/sync', urlencode(dict(nonce=restarted.nonce)).encode(), 'http://127.0.0.1:8765')
        self.assertEqual(result[0], 303)
        self.assertIn('0 new · 0 enriched · 2 unchanged', restarted_app.get('/settings')[2].decode())
        self.assertEqual(self.count('strava_api_sources'), old_count)
        self.assertEqual(self.tokens.read()['refresh_token'], 'new-fake-refresh')
        self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone()), checkpoint)
        self.assertEqual(restarted.display.path.stat().st_mode & 0o777, 0o600)

    def test_failure_revocation_reconnect_preserves_history_checkpoint_and_secret_safety(self):
        self.http.responses.append(Response([self.observation()]))
        self.post('sync'); checkpoint = tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone())
        self.http.responses.append(HTTPError('https://www.strava.com/', 401, 'private-secret-that-must-not-appear', {}, None))
        self.post('sync'); html = self.html()
        self.assertFalse(self.tokens.path.exists()); self.assertIn('Reconnect Strava', html)
        self.assert_private(html); self.assertEqual(self.count('activities'), 1)
        self.assertEqual(tuple(self.store.connection.execute('SELECT * FROM strava_sync_state').fetchone()), checkpoint)
        restart = Settings(self.store.data_dir, credentials=self.configured)
        self.assertTrue(restart.state()['attention'])
        state = self.connect(); self.http.responses.append(self.token_response())
        self.settings.callback(urlencode(dict(state=state, code='private-code', scope='activity:read_all')))
        self.assertIn('Sync now', self.html())

    def test_sync_rate_error_and_display_failure_do_not_hide_success(self):
        self.http.responses.append(HTTPError('https://www.strava.com/', 429, 'private-code', {}, None))
        self.post('sync'); self.assertIn('rate limit reached', self.html()); self.assertEqual(self.count('strava_sync_state'), 0)
        self.http.responses.append(Response([]))
        with patch.object(self.settings.display, 'save', side_effect=OSError('private-code')):
            self.post('sync')
        self.assertIn('Display details could not be saved', self.html())
        self.assertEqual(self.count('strava_sync_state'), 1); self.assert_private(self.html())

    def test_disconnect_shared_logic_with_missing_credentials_and_failed_remote_revoke(self):
        self.http.responses.append(HTTPError('https://www.strava.com/', 503, 'private-code', {}, None))
        with patch('rideworks.settings.disconnect', wraps=disconnect) as shared:
            self.post('disconnect')
        self.assertEqual(shared.call_count, 1); self.assertFalse(self.tokens.path.exists())
        self.assertIn('remote revocation was not confirmed', self.html()); self.assert_private(self.html())
        self.http.responses.append(self.token_response()); state = self.connect()
        self.settings.callback(urlencode(dict(state=state, code='private-code', scope='activity:read_all')))
        self.credentials = None; self.post('disconnect')
        self.assertFalse(self.tokens.path.exists()); self.assertEqual(self.count('activities'), 1)

    def test_inflight_and_cross_cli_lock_reject_concurrent_operations(self):
        with self.settings.operation:
            self.assertEqual(self.post('sync')[0], 409)
        with TokenFile(self.store.data_dir).lock():
            self.post('sync')
        self.assertIn('Another Strava operation', self.html()); self.assertEqual(self.http.requests, [])

    def test_mixed_rfc3339_api_file_export_unknown_dates_local_filters_and_order(self):
        with (self.export/'activities.csv').open('a', newline='') as stream:
            csv.writer(stream).writerow(['3', 'Unknown date', 'Virtual Ride', 'unparsed source date', ''])
        self.store.import_strava_export(self.export)
        stamp = datetime.combine(self.start.date()+timedelta(days=1), datetime.min.time(), timezone.utc)+timedelta(minutes=30)
        item = self.observation(identity=2); item['start_date'] = stamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        self.http.responses.append(Response([self.observation(), item]))
        with patch('rideworks.strava.time.time', return_value=int(stamp.timestamp())+3600):
            self.post('sync')
        self.assertEqual(self.count('activities'), 3)  # One enrichment, one new API-only, one unknown CSV.
        for zone in ('America/Los_Angeles', 'Asia/Tokyo'):
            newest = browse(self.store, 'tz='+zone)['rows']; oldest = browse(self.store, 'sort=oldest&tz='+zone)['rows']
            self.assertEqual(newest[0]['title'], 'API title'); self.assertTrue(newest[0]['absolute_time'])
            self.assertEqual(newest[0]['date_key'], stamp.replace(tzinfo=None).isoformat())
            self.assertEqual(newest[0]['date_day'], stamp.astimezone(ZoneInfo(zone)).date().isoformat())
            self.assertEqual(newest[-1]['title'], 'Unknown date'); self.assertEqual(oldest[-1]['title'], 'Unknown date')
            self.assertEqual(oldest[0]['activity_id'], self.native['activity_id'])
            self.assertEqual(newest[1]['activity_id'], self.native['activity_id'])
            day = newest[0]['date_day']
            filtered = browse(self.store, 'tz='+zone+'&from='+day+'&to='+day)['rows']
            self.assertIn(newest[0]['activity_id'], [r['activity_id'] for r in filtered])
            self.assertNotIn(newest[-1]['activity_id'], [r['activity_id'] for r in filtered])
        api_row = newest[0]
        self.assertEqual(self.store.get_activity(api_row['activity_id'])['sources'][0]['summary']['values']['start_date'], item['start_date'])
        self.assertIn('View Activities', self.html())
        self.assertEqual(self.app.get('/activities/'+api_row['activity_id'])[0], 200)

    def test_sync_rebuild_failure_app_wide_exception_manual_retry_and_atomic_failure(self):
        self.http.responses.append(Response([self.observation(), self.observation(identity=2, seconds=1)]))
        with patch('rideworks.performance.evaluate', side_effect=RideWorksError('Synthetic automatic update failure')):
            self.post('sync')
        before = [tuple(r) for r in self.store.connection.execute('SELECT * FROM performance_history')]
        routes = ['/settings', '/', '/performance', '/activities/'+self.native['activity_id']]
        for route in routes:
            self.assertIn('Performance update incomplete', self.app.get(route)[2].decode())
        self.assertEqual(performance_history(self.store)['pending'], 2)
        restart = Application(self.store.data_dir)
        self.assertIn('Performance update incomplete', restart.get('/settings')[2].decode())
        path = '/settings/performance/rebuild'
        self.assertEqual(self.settings.post(path, b'nonce=invalid', 'http://127.0.0.1:8765')[0], 403)
        original_evaluate = __import__('rideworks.performance', fromlist=['evaluate']).evaluate
        calls = []
        def fail_after_first(store, snapshot):
            calls.append(1)
            if len(calls) > 1:
                raise RideWorksError('private-secret-that-must-not-appear')
            return original_evaluate(store, snapshot)
        with patch('rideworks.performance.evaluate', side_effect=fail_after_first):
            result = self.settings.post(path, urlencode(dict(nonce=self.settings.nonce)).encode(), 'http://127.0.0.1:8765')
        self.assertEqual(result[0], 303); self.assertIn('Performance update incomplete', self.html()); self.assert_private(self.html())
        self.assertEqual(before, [tuple(r) for r in self.store.connection.execute('SELECT * FROM performance_history')])
        self.assertIn('Performance update incomplete', self.html())
        with patch('rideworks.settings.rebuild_performance', wraps=rebuild_performance) as shared:
            self.settings.post(path, urlencode(dict(nonce=self.settings.nonce)).encode(), 'http://127.0.0.1:8765')
        self.assertEqual(shared.call_count, 1); self.assertEqual(performance_history(self.store)['pending'], 0)
        for route in routes:
            self.assertNotIn('Performance update incomplete', self.app.get(route)[2].decode())
        self.assertIn('Performance updated: 2 Activities evaluated', self.html())
        self.assertNotIn('Performance update incomplete', Application(self.store.data_dir).get('/settings')[2].decode())

    def test_http_second_operation_rejected_while_first_sync_waits(self):
        entered, release = threading.Event(), threading.Event()
        parent_http = self.http
        class BlockingHTTP:
            def open(inner, request, timeout):
                entered.set()
                if not release.wait(5):
                    raise AssertionError('Synthetic test release timed out')
                return parent_http.open(request, timeout)
        self.http.responses.append(Response([]))
        self.settings.client_factory = lambda credentials: ApiClient(credentials, opener=BlockingHTTP())
        with create_server(self.store.data_dir, port=0, settings_factory=lambda root: self.settings) as server:
            thread = threading.Thread(target=server.serve_forever); thread.start()
            result = []
            def submit(nonce):
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                try:
                    connection.request('POST', '/settings/strava/sync', urlencode(dict(nonce=nonce)),
                                       {'Origin': f'http://127.0.0.1:{server.server_port}', 'Content-Type': 'application/x-www-form-urlencoded'})
                    response = connection.getresponse(); response.read(); return response.status
                finally:
                    connection.close()
            first = threading.Thread(target=lambda: result.append(submit(self.settings.nonce)))
            try:
                first.start(); self.assertTrue(entered.wait(5))
                self.assertEqual(submit(self.settings.nonce), 409)
                self.assertEqual(self.count('strava_sync_state'), 0)
            finally:
                release.set(); first.join(); server.shutdown(); thread.join()
            self.assertEqual(result, [303]); self.assertEqual(len(self.http.requests), 1)
            self.assertEqual(self.count('strava_sync_state'), 1)

    def test_http_origin_host_bounds_callback_clean_url_and_safe_diagnostics(self):
        output = io.StringIO()
        with redirect_stdout(output), create_server(self.store.data_dir, port=0, debug=True,
                                                  settings_factory=lambda root: self.settings) as server:
            thread = threading.Thread(target=server.serve_forever); thread.start()
            self.addCleanup(thread.join)
            def request(method, path, body=None, headers=None):
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                try:
                    connection.request(method, path, body, headers or {})
                    response = connection.getresponse()
                    return response.status, dict(response.getheaders()), response.read()
                finally:
                    connection.close()
            try:
                self.assertEqual(request('GET', '/settings')[0], 200)
                self.assertEqual(request('GET', '/settings', headers={'Host': 'untrusted.example'})[0], 403)
                self.assertEqual(request('POST', '/settings/strava/sync', b'x'*1025)[0], 413)
                self.assertEqual(request('POST', '/settings/strava/sync', b'nonce=x')[0], 415)
                self.assertEqual(request('POST', '/settings/strava/disconnect', b'nonce=x', {'Content-Type': 'application/x-www-form-urlencoded'})[0], 403)
                self.tokens.clear()
                headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Origin': f'http://127.0.0.1:{server.server_port}'}
                result = request('POST', '/settings/strava/connect', urlencode(dict(nonce=self.settings.nonce)), headers)
                self.assertEqual(result[0], 303)
                query = parse_qs(urlsplit(result[1]['Location']).query)
                self.assertEqual(query['redirect_uri'], [f'http://127.0.0.1:{server.server_port}/strava/callback'])
                self.http.responses.append(self.token_response())
                callback = '/strava/callback?' + urlencode(dict(state=query['state'][0], code='private-code', scope='activity:read_all'))
                result = request('GET', callback)
                self.assertEqual(result[0], 303); self.assertEqual(result[1]['Location'], '/settings')
                self.assertEqual(result[1]['Referrer-Policy'], 'no-referrer')
                result = request('GET', '/settings'); self.assertIn(b'Sync now', result[2])
                self.assert_private(result[2].decode())
            finally:
                server.shutdown(); thread.join()
        self.assert_private(output.getvalue()); self.assertNotIn('/strava/callback?', output.getvalue())
