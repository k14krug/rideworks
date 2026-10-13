"""Source-neutral nginx-like HTTP requests; only synthetic stores and fake OAuth."""
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from http.client import HTTPConnection
import io
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

import test_rideworks_strava as fixture
from rideworks.settings import Settings
from rideworks.strava import ApiClient
from rideworks.web import create_server


class ProxyTests(unittest.TestCase):
    def setUp(self):
        fixture.StravaTests.setUp(self)
        self.http = fixture.FakeHTTP()
        self.settings = Settings(self.store.data_dir, credentials=lambda: fixture.CREDS,
            client_factory=lambda credentials: ApiClient(credentials, opener=self.http))

    @contextmanager
    def server(self, public_origin=None, *, debug=False):
        with create_server(self.store.data_dir, 0, public_origin=public_origin, debug=debug,
                           settings_factory=lambda root: self.settings) as server:
            self.assertEqual(server.server_address[0], '127.0.0.1')
            self.port = server.server_port
            thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01))
            thread.start()
            try:
                yield server
            finally:
                server.shutdown()
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())

    def request(self, method, path, *, host=None, origin=None, values=None, headers=()):
        connection = HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            body = urlencode(values).encode() if values is not None else None
            connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            connection.putheader('Host', host if host is not None else f'127.0.0.1:{self.port}')
            if origin is not None:
                connection.putheader('Origin', origin)
            if body is not None:
                connection.putheader('Content-Type', 'application/x-www-form-urlencoded')
                connection.putheader('Content-Length', str(len(body)))
            for name, value in headers:
                connection.putheader(name, value)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def form(self, path, origin, *, host=None, nonce=None, **values):
        return self.request('POST', path, host=host, origin=origin,
                            values={'nonce': self.settings.nonce if nonce is None else nonce, **values})

    def assert_no_credentials(self, value):
        for secret in (fixture.CREDS[1], 'synthetic-access', 'synthetic-refresh',
                       'fake-new-access', 'fake-new-refresh', 'private-code', 'private-error'):
            self.assertNotIn(secret, value)

    def test_http_default_external_port_host_routes_and_retained_connection(self):
        before = self.tokens.path.read_bytes()
        with self.server('http://RideWorks.lan:80'):
            for host in ('rideworks.lan', 'rideworks.lan:80', 'RIDEWORKS.LAN',
                         f'127.0.0.1:{self.port}', f'localhost:{self.port}'):
                for route in ('/', '/activities', '/performance', '/performance?curve=1',
                              '/training-state', '/plan', '/settings', '/activities/'+self.native['activity_id']):
                    with self.subTest(host=host, route=route):
                        status, _, body = self.request('GET', route, host=host)
                        self.assertEqual(status, 200)
                        self.assert_no_credentials(body.decode())
            self.assertIn(b'Connected', self.request('GET', '/settings', host='rideworks.lan')[2])
        self.assertEqual(self.tokens.path.read_bytes(), before)
        self.assertEqual(self.http.requests, [])

    def test_http_lan_ip_custom_external_port_differs_from_backend(self):
        with self.server('http://192.168.1.20:8080'):
            self.assertNotEqual(self.port, 8080)
            self.assertEqual(self.request('GET', '/', host='192.168.1.20:8080')[0], 200)
            for host in ('192.168.1.20', '192.168.1.20:80', f'192.168.1.20:{self.port}', '192.168.1.21:8080'):
                self.assertEqual(self.request('GET', '/', host=host)[0], 403)
            self.assertEqual(self.form('/settings/annual-goal', 'http://192.168.1.20:8080',
                host='192.168.1.20:8080', tz='America/Los_Angeles', target_miles='4000')[0], 303)
            self.assertEqual(self.form('/plan/classification', 'http://192.168.1.20:8080',
                host='192.168.1.20:8080', tz='America/Los_Angeles',
                activity_id=self.native['activity_id'], category='Easy', back='activity')[0], 303)

    def test_http_lan_ip_default_port_and_ipv6(self):
        for public, hosts in (('http://192.168.1.20:80', ('192.168.1.20', '192.168.1.20:80')),
                              ('http://[fd00::20]:8080', ('[fd00::20]:8080',))):
            with self.subTest(public=public), self.server(public):
                for host in hosts:
                    self.assertEqual(self.request('GET', '/settings', host=host)[0], 200)
                self.assertEqual(self.form('/settings/annual-goal', self.settings.access.public_origin,
                    host=hosts[0], tz='America/Los_Angeles', target_miles='4000')[0], 303)

    def test_unconfigured_public_host_and_forwarded_headers_do_not_grant_access(self):
        with self.server():
            self.assertEqual(self.request('GET', '/settings')[0], 200)
            self.assertEqual(self.request('GET', '/', host='rideworks.lan', headers=(
                ('X-Forwarded-Host', f'localhost:{self.port}'), ('X-Forwarded-Proto', 'http')))[0], 403)
            self.assertEqual(self.form('/settings/annual-goal', 'http://rideworks.lan',
                tz='America/Los_Angeles', target_miles='4000')[0], 403)

    def test_foreign_suffix_malformed_duplicate_and_missing_hosts_rejected(self):
        with self.server('http://rideworks.lan'):
            for host in ('', 'evil.lan', 'rideworks.lan.evil.lan', 'evilrideworks.lan',
                         'rideworks.lan:8080', f'rideworks.lan:{self.port}',
                         'http://rideworks.lan', 'rideworks.lan/', 'rideworks.lan.',
                         'user@rideworks.lan', 'rideworks.lan:abc', 'rideworks.lan:80:80',
                         'rideworks.lan, evil.lan', 'rideworks.lan:080', 'rideworks.lan '):
                with self.subTest(host=host):
                    result = self.request('GET', '/settings', host=host, headers=(
                        ('X-Forwarded-Host', 'rideworks.lan'), ('X-Forwarded-Proto', 'http')))
                    self.assertEqual(result[0], 403)
            self.assertEqual(self.request('GET', '/', host='rideworks.lan',
                headers=(('Host', 'rideworks.lan'),))[0], 403)
            connection = HTTPConnection('127.0.0.1', self.port, timeout=5)
            try:
                connection.putrequest('GET', '/', skip_host=True)
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
            finally:
                connection.close()

    def test_settings_and_plan_allow_exact_http_origin_and_keep_nonce_constraints(self):
        with self.server('http://rideworks.lan'):
            for origin in ('http://rideworks.lan', f'http://127.0.0.1:{self.port}', f'http://localhost:{self.port}'):
                self.assertEqual(self.form('/settings/annual-goal', origin, host='rideworks.lan',
                    tz='America/Los_Angeles', target_miles='4000')[0], 303)
                day = datetime.now(timezone.utc).astimezone(ZoneInfo('America/Los_Angeles')).date().isoformat()
                self.assertEqual(self.form('/plan/feedback', origin, host='rideworks.lan',
                    tz='America/Los_Angeles', day=day, legs='heavy')[0], 303)
            for path, values in (
                ('/settings/annual-goal', dict(tz='America/Los_Angeles', target_miles='5000')),
                ('/plan/classification', dict(tz='America/Los_Angeles', activity_id=self.native['activity_id'], category='Race', back='activity')),
            ):
                for nonce in ('', 'wrong'):
                    self.assertEqual(self.form(path, 'http://rideworks.lan', host='rideworks.lan', nonce=nonce, **values)[0], 403)
            nonce = self.settings.nonce
            self.assertEqual(self.form('/settings/annual-goal', 'http://rideworks.lan', host='rideworks.lan',
                tz='America/Los_Angeles', target_miles='5000')[0], 303)
            self.assertEqual(self.form('/settings/annual-goal', 'http://rideworks.lan', host='rideworks.lan', nonce=nonce,
                tz='America/Los_Angeles', target_miles='6000')[0], 403)
            self.assertEqual(self.form('/plan/classification', 'http://rideworks.lan', host='rideworks.lan',
                tz='America/Los_Angeles', activity_id=self.native['activity_id'], category='Invented', back='activity')[0], 400)

    def test_foreign_missing_spoofed_and_duplicate_origins_cannot_write(self):
        with self.server('http://rideworks.lan'):
            tables = ('annual_mileage_goals', 'planning_classifications', 'planning_feedback', 'planning_intents')
            before = {table: list(self.store.connection.execute('SELECT * FROM '+table)) for table in tables}
            for origin in (None, 'null', 'http://evil.lan', 'http://rideworks.lan.evil',
                           'https://rideworks.lan', 'http://rideworks.lan:8080',
                           'http://rideworks.lan:80', 'http://rideworks.lan/',
                           'http://user@rideworks.lan', 'http://rideworks.lan http://evil.lan'):
                for path, values in (
                    ('/settings/annual-goal', dict(tz='America/Los_Angeles', target_miles='4000')),
                    ('/plan/classification', dict(tz='America/Los_Angeles', activity_id=self.native['activity_id'], category='Race', back='activity')),
                ):
                    with self.subTest(origin=origin, path=path):
                        self.assertEqual(self.form(path, origin, host='rideworks.lan', **values)[0], 403)
            for path, values in (('/settings/strava/connect', {}),
                                 ('/plan/classification', dict(tz='America/Los_Angeles', activity_id=self.native['activity_id'], category='Race', back='activity'))):
                self.assertEqual(self.request('POST', path, host='rideworks.lan', origin='http://rideworks.lan',
                    values={'nonce': self.settings.nonce, **values}, headers=(('Origin', 'http://rideworks.lan'),))[0], 403)
            after = {table: list(self.store.connection.execute('SELECT * FROM '+table)) for table in tables}
            self.assertEqual(after, before)
            self.assertIsNone(self.settings.pending)
            self.assertEqual(self.http.requests, [])

    def test_browser_oauth_redirect_callback_state_and_secrets_public_and_local(self):
        output = io.StringIO()
        for public in (None, 'http://rideworks.lan:80', 'http://192.168.1.20:8080', 'https://rideworks.example:8443'):
            with self.subTest(public=public), redirect_stdout(output), self.server(public, debug=True):
                self.tokens.clear()
                origin = self.settings.access.public_origin or f'http://127.0.0.1:{self.port}'
                host = urlsplit(origin).netloc
                result = self.form('/settings/strava/connect', origin, host=host)
                self.assertEqual(result[0], 303)
                query = parse_qs(urlsplit(result[1]['Location']).query)
                self.assertEqual(query['redirect_uri'], [origin+'/strava/callback'])
                self.assertEqual(query['scope'], ['activity:read_all'])
                self.http.responses.append(fixture.Response(dict(access_token='fake-new-access', refresh_token='fake-new-refresh',
                    expires_at=4102444800, athlete={'id': 321}, scope='activity:read_all')))
                callback = '/strava/callback?' + urlencode(dict(state=query['state'][0], code='private-code', scope='activity:read_all'))
                result = self.request('GET', callback, host=host)
                self.assertEqual((result[0], result[1]['Location']), (303, '/settings'))
                self.assertEqual(result[1]['Referrer-Policy'], 'no-referrer')
                self.assertEqual(self.tokens.read()['refresh_token'], 'fake-new-refresh')
                self.assertEqual(self.tokens.path.stat().st_mode & 0o777, 0o600)
                self.assert_no_credentials(self.request('GET', '/settings', host=host)[2].decode())
                requests = len(self.http.requests)
                self.assertEqual(self.request('GET', callback, host=host)[0], 303)
                self.assertEqual(len(self.http.requests), requests)
        self.assert_no_credentials(output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertNotIn('/strava/callback?', output.getvalue())

    def test_oauth_headers_never_choose_callback_and_wrong_state_never_exchanges(self):
        with self.server('http://rideworks.lan'):
            result = self.request('POST', '/settings/strava/connect', host='rideworks.lan', origin='http://rideworks.lan',
                values={'nonce': self.settings.nonce}, headers=(('X-Forwarded-Host', 'evil.lan'), ('X-Forwarded-Proto', 'https')))
            query = parse_qs(urlsplit(result[1]['Location']).query)
            self.assertEqual(query['redirect_uri'], ['http://rideworks.lan/strava/callback'])
            self.assertEqual(self.request('GET', '/strava/callback?state=wrong&code=private-code&scope=activity:read_all', host='rideworks.lan')[0], 303)
            self.assertEqual(self.http.requests, [])
            self.assertIn(b'Callback Domain is rideworks.lan', self.request('GET', '/settings', host='rideworks.lan')[2])

    def test_configured_domain_in_setup_and_timeout_messages(self):
        with self.server('http://192.168.1.20:8080'):
            self.settings.credentials = lambda: None
            body = self.request('GET', '/settings', host='192.168.1.20:8080')[2]
            self.assertIn(b'<code>192.168.1.20</code>', body)
            self.assertNotIn(b'Callback Domain is 127.0.0.1', body)
            self.settings.pending = ('synthetic-state', 0)
            self.assertIn(b'Callback Domain is 192.168.1.20', self.request('GET', '/settings', host='192.168.1.20:8080')[2])

    def test_https_default_port_remains_optional(self):
        with self.server('https://rideworks.example:443'):
            for host in ('rideworks.example', 'rideworks.example:443'):
                self.assertEqual(self.request('GET', '/', host=host)[0], 200)
            self.assertEqual(self.request('GET', '/', host='rideworks.example:80')[0], 403)
            self.assertEqual(self.form('/settings/annual-goal', 'https://rideworks.example', host='rideworks.example',
                tz='America/Los_Angeles', target_miles='4000')[0], 303)
            self.assertEqual(self.form('/settings/annual-goal', 'http://rideworks.example', host='rideworks.example',
                tz='America/Los_Angeles', target_miles='4000')[0], 403)

    def test_safe_error_response_and_diagnostics_on_public_route(self):
        output = io.StringIO()
        with redirect_stdout(output), self.server('http://rideworks.lan', debug=True), patch('rideworks.web.Application.get', side_effect=RuntimeError('private-error '+str(self.root))):
            result = self.request('GET', '/?code=private-code', host='rideworks.lan')
            self.assertEqual(result[0], 500)
        self.assert_no_credentials(result[2].decode()+output.getvalue())
        self.assertNotIn(str(self.root), result[2].decode()+output.getvalue())


if __name__ == '__main__':
    unittest.main()
