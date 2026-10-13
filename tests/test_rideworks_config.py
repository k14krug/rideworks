"""Known local startup keys only, explicit precedence and loopback diagnostics."""

from contextlib import redirect_stdout
from http.client import HTTPConnection
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from rideworks.__main__ import main
from rideworks.config import ConfigurationError, startup_config
from rideworks.web import create_server


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def settings(self, text=None, **kwargs):
        if text is not None:
            (self.root / '.env').write_text(text)
        return startup_config(repo_root=self.root, environ=kwargs.pop('environ', {}), **kwargs)

    def test_missing_env_keeps_established_defaults(self):
        config = self.settings()
        self.assertIsNone(config.data_dir)
        self.assertEqual(config.port, 8766)
        self.assertFalse(config.debug)
        self.assertIsNone(config.public_origin)
        with patch.dict(os.environ, {}, clear=True):
            from rideworks.store import resolve_data_dir
            self.assertEqual(resolve_data_dir(config.data_dir), Path(__file__).resolve().parents[1] / 'data')

    def test_project_default_is_independent_of_cwd_and_missing_server_does_not_create(self):
        from rideworks.store import resolve_data_dir
        from rideworks.web import serve
        from rideworks.errors import RideWorksError
        previous=Path.cwd()
        try:
            os.chdir(self.root)
            with patch.dict(os.environ,{},clear=True):
                self.assertEqual(resolve_data_dir(),Path(__file__).resolve().parents[1]/'data')
            missing=self.root/'missing-store'
            with self.assertRaisesRegex(RideWorksError,'store is missing'):
                serve(missing,8766)
            self.assertFalse(missing.exists())
        finally:os.chdir(previous)

    def test_supported_values_quotes_comments_and_export(self):
        config = self.settings('''# local settings
export DEBUG = yes
RUN_PORT="8877" # local port
RIDEWORKS_DATA_DIR='local_data/review with spaces'
''')
        self.assertEqual((config.port, config.debug, config.data_dir), (8877, True, 'local_data/review with spaces'))

    def test_exported_environment_wins_without_mutation(self):
        environment = {'RUN_PORT': '8999', 'DEBUG': 'off', 'RIDEWORKS_DATA_DIR': 'exported-store'}
        original = environment.copy()
        config = self.settings('RUN_PORT=8877\nDEBUG=1\nRIDEWORKS_DATA_DIR=file-store\n', environ=environment)
        self.assertEqual((config.port, config.debug, config.data_dir), (8999, False, 'exported-store'))
        self.assertEqual(environment, original)

    def test_cli_wins_over_environment_and_env_file(self):
        config = self.settings('RUN_PORT=8877\nRIDEWORKS_DATA_DIR=file-store\n',
            environ={'RUN_PORT': '8999', 'RIDEWORKS_DATA_DIR': 'exported-store'},
            data_dir='cli-store', port=9001)
        self.assertEqual((config.port, config.data_dir), (9001, 'cli-store'))

    def test_invalid_lower_priority_port_does_not_defeat_cli(self):
        config = self.settings('RUN_PORT="unterminated\n',
            environ={'RUN_PORT': 'invalid'}, port=9001)
        self.assertEqual(config.port, 9001)

    def test_invalid_ports_fail_without_echoing_payload(self):
        for value in ('', '0', '-1', '65536', '8.5', 'abc', '１２３', 'not-a-secret-to-echo'):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError) as error:
                    self.settings(environ={'RUN_PORT': value})
                self.assertIn('RUN_PORT', str(error.exception))
                if value == 'not-a-secret-to-echo':
                    self.assertNotIn(value, str(error.exception))
        with self.assertRaises(ConfigurationError):
            self.settings('RUN_PORT=invalid\n')
        with self.assertRaises(ConfigurationError):
            self.settings(port=65536)

    def test_debug_spellings_and_invalid_values(self):
        for value in ('1', 'true', 'YES', 'On'):
            self.assertTrue(self.settings(environ={'DEBUG': value}).debug)
        for value in ('0', 'false', 'NO', 'Off'):
            self.assertFalse(self.settings(environ={'DEBUG': value}).debug)
        for value in ('', '2', 'maybe'):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                self.settings(environ={'DEBUG': value})

    def test_known_invalid_syntax_fails_but_unrelated_settings_are_ignored(self):
        for line in ('DEBUG', 'RUN_PORT="unclosed', 'RIDEWORKS_DATA_DIR=two words'):
            with self.subTest(line=line), self.assertRaises(ConfigurationError):
                self.settings(line)
        config = self.settings('UNRELATED_SECRET="unclosed\nOTHER=$(do-not-run)\nDEBUG=0\n')
        self.assertFalse(config.debug)

    def test_no_expansion_shell_execution_or_global_environment_changes(self):
        with patch.dict(os.environ, {'UNRELATED': 'unchanged'}, clear=True):
            original = dict(os.environ)
            config = self.settings('RIDEWORKS_DATA_DIR="${UNRELATED}/literal"\nDEBUG=0\n')
            self.assertEqual(config.data_dir, '${UNRELATED}/literal')
            self.assertEqual(dict(os.environ), original)

    def test_env_is_rooted_at_checkout_not_current_directory(self):
        other = self.root / 'elsewhere'
        other.mkdir()
        (other / '.env').write_text('RUN_PORT=8999\n')
        (self.root / '.env').write_text('RUN_PORT=8877\n')
        previous = Path.cwd()
        try:
            os.chdir(other)
            with patch('rideworks.config.repository_root', return_value=self.root):
                self.assertEqual(startup_config(environ={}).port, 8877)
        finally:
            os.chdir(previous)

    def test_empty_data_dir_is_not_silently_current_directory(self):
        with self.assertRaises(ConfigurationError):
            self.settings('RIDEWORKS_DATA_DIR=\n')

    def test_last_file_assignment_wins(self):
        self.assertEqual(self.settings('RUN_PORT=8877\nRUN_PORT=8999\n').port, 8999)

    def test_cli_passes_config_to_stdlib_server(self):
        (self.root / '.env').write_text('RUN_PORT=8877\nDEBUG=1\nRIDEWORKS_DATA_DIR=file-store\n')
        with patch.dict(os.environ, {}, clear=True), patch('rideworks.config.repository_root', return_value=self.root), patch('rideworks.web.serve') as serve:
            self.assertEqual(main(['serve']), 0)
            serve.assert_called_once_with('file-store', 8877, debug=True, public_origin=None)
            serve.reset_mock()
            self.assertEqual(main(['--data-dir', 'cli-store', 'serve', '--port', '9001']), 0)
            serve.assert_called_once_with('cli-store', 9001, debug=True, public_origin=None)

    def test_cli_invalid_config_fails_before_server_starts(self):
        (self.root / '.env').write_text('DEBUG=maybe\n')
        with patch.dict(os.environ, {}, clear=True), patch('rideworks.config.repository_root', return_value=self.root), patch('rideworks.web.serve') as serve, patch('sys.stderr', new_callable=io.StringIO) as errors:
            self.assertEqual(main(['serve']), 1)
            self.assertIn('DEBUG', errors.getvalue())
            serve.assert_not_called()

    def test_public_origin_environment_file_precedence_normalization_and_no_mutation(self):
        config = self.settings('PUBLIC_ORIGIN=http://RideWorks.lan:80\n')
        self.assertEqual(config.public_origin, 'http://rideworks.lan')
        environment = {'PUBLIC_ORIGIN': 'http://192.168.1.20:8080'}
        original = environment.copy()
        config = self.settings('PUBLIC_ORIGIN="unclosed\n', environ=environment)
        self.assertEqual(config.public_origin, 'http://192.168.1.20:8080')
        self.assertEqual(environment, original)
        self.assertEqual(self.settings('PUBLIC_ORIGIN=http://one.lan\nPUBLIC_ORIGIN=http://two.lan\n').public_origin, 'http://two.lan')

    def test_http_https_dns_ip_and_default_ports(self):
        for supplied, expected in (
            ('http://rideworks', 'http://rideworks'),
            ('http://rideworks.lan:80', 'http://rideworks.lan'),
            ('http://192.168.1.20', 'http://192.168.1.20'),
            ('http://192.168.1.20:8080', 'http://192.168.1.20:8080'),
            ('http://[fd00::20]:80', 'http://[fd00::20]'),
            ('http://[fd00::20]:8080', 'http://[fd00::20]:8080'),
            ('https://RideWorks.example:443', 'https://rideworks.example'),
            ('https://rideworks.example:8443', 'https://rideworks.example:8443'),
        ):
            with self.subTest(supplied=supplied):
                self.assertEqual(self.settings(environ={'PUBLIC_ORIGIN': supplied}).public_origin, expected)

    def test_malformed_public_origins_fail_without_echoing_values(self):
        invalid = ('', ' ', 'ftp://rideworks.lan', '//rideworks.lan', 'http://',
            'http://rideworks.lan/', 'http://rideworks.lan/path', 'http://rideworks.lan?',
            'http://rideworks.lan#', 'http://user:private-secret@rideworks.lan',
            'http://rideworks.lan:0', 'http://rideworks.lan:65536', 'http://rideworks.lan:abc',
            'http://rideworks.lan:', 'http://rideworks.lan:80:80', 'http://*.lan',
            'http://-bad.lan', 'http://bad_.lan', 'http://bad..lan', 'http://rideworks.lan.',
            'http://127.1', 'http://999.1.2.3', 'http://192.168.001.20',
            'http://[bad]', 'http://[::1', 'http://[fd00::20%eth0]',
            'http://rideworks.lan\n', 'http://rideworks.lan\r\nHost:evil.lan',
            'http://rideworks.lan\\evil', 'http://ridéworks.lan',
            'http://' + 'a'*64 + '.lan')
        for supplied in invalid:
            with self.subTest(supplied=supplied), self.assertRaises(ConfigurationError) as error:
                self.settings(environ={'PUBLIC_ORIGIN': supplied})
            self.assertIn('PUBLIC_ORIGIN', str(error.exception))
            self.assertNotIn('private-secret', str(error.exception))

    def test_legacy_runtime_names_are_ignored_without_parsing(self):
        config = self.settings('FLASK_RUN_PORT="unclosed\nFLASK_DEBUG=invalid\n',
            environ={'FLASK_RUN_PORT': '9000', 'FLASK_DEBUG': '1'})
        self.assertEqual((config.port, config.debug), (8766, False))
        config = self.settings('RUN_PORT=8877\nDEBUG=yes\n',
            environ={'FLASK_RUN_PORT': '9000', 'FLASK_DEBUG': 'invalid'})
        self.assertEqual((config.port, config.debug), (8877, True))

    def test_cli_public_origin_passes_to_server_and_invalid_origin_fails_first(self):
        (self.root / '.env').write_text('PUBLIC_ORIGIN=http://rideworks.lan\nRUN_PORT=8877\n')
        with patch.dict(os.environ, {}, clear=True), patch('rideworks.config.repository_root', return_value=self.root), patch('rideworks.web.serve') as serve:
            self.assertEqual(main(['serve']), 0)
            serve.assert_called_once_with(None, 8877, debug=False, public_origin='http://rideworks.lan')
            serve.reset_mock()
            (self.root / '.env').write_text('PUBLIC_ORIGIN=http://user:private-secret@rideworks.lan\n')
            with patch('sys.stderr', new_callable=io.StringIO) as errors:
                self.assertEqual(main(['serve']), 1)
            self.assertIn('PUBLIC_ORIGIN', errors.getvalue())
            self.assertNotIn('private-secret', errors.getvalue())
            serve.assert_not_called()

    def test_invalid_origin_does_not_initialize_store_or_bind(self):
        missing = self.root / 'missing'
        with patch('rideworks.web.ThreadingHTTPServer') as bind, self.assertRaises(ConfigurationError):
            create_server(missing, 0, public_origin='http://bad.lan/path')
        bind.assert_not_called()
        self.assertFalse(missing.exists())

    def test_env_data_dir_applies_to_import_commands(self):
        data_dir = self.root / 'data'
        (self.root / '.env').write_text(f'RIDEWORKS_DATA_DIR="{data_dir}"\n')
        with patch.dict(os.environ, {}, clear=True), patch('rideworks.config.repository_root', return_value=self.root), patch('rideworks.__main__.Store') as store, redirect_stdout(io.StringIO()):
            store.return_value.__enter__.return_value.import_fit.return_value = {'status': 'synthetic'}
            self.assertEqual(main(['import-fit', 'synthetic.fit']), 0)
            store.assert_called_once_with(str(data_dir))

    def test_debug_only_adds_safe_local_diagnostics_and_keeps_loopback(self):
        for debug in (False, True):
            output = io.StringIO()
            server = create_server(self.root / 'data', 0, debug=debug)
            self.assertEqual(server.server_address[0], '127.0.0.1')
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            with redirect_stdout(output):
                thread.start()
                try:
                    connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    connection.request('GET', '/?secret=do-not-log')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    body = response.read().decode()
                    self.assertNotIn('Werkzeug', body)
                    connection.close()
                finally:
                    server.shutdown()
                    thread.join()
                    server.server_close()
            self.assertEqual('RideWorks request: GET 200' in output.getvalue(), debug)
            self.assertNotIn('do-not-log', output.getvalue())
            self.assertNotIn(str(self.root), output.getvalue())


if __name__ == '__main__':
    unittest.main()
