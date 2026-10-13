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
export FLASK_DEBUG = yes
FLASK_RUN_PORT="8877" # local port
RIDEWORKS_DATA_DIR='local_data/review with spaces'
''')
        self.assertEqual((config.port, config.debug, config.data_dir), (8877, True, 'local_data/review with spaces'))

    def test_exported_environment_wins_without_mutation(self):
        environment = {'FLASK_RUN_PORT': '8999', 'FLASK_DEBUG': 'off', 'RIDEWORKS_DATA_DIR': 'exported-store'}
        original = environment.copy()
        config = self.settings('FLASK_RUN_PORT=8877\nFLASK_DEBUG=1\nRIDEWORKS_DATA_DIR=file-store\n', environ=environment)
        self.assertEqual((config.port, config.debug, config.data_dir), (8999, False, 'exported-store'))
        self.assertEqual(environment, original)

    def test_cli_wins_over_environment_and_env_file(self):
        config = self.settings('FLASK_RUN_PORT=8877\nRIDEWORKS_DATA_DIR=file-store\n',
            environ={'FLASK_RUN_PORT': '8999', 'RIDEWORKS_DATA_DIR': 'exported-store'},
            data_dir='cli-store', port=9001)
        self.assertEqual((config.port, config.data_dir), (9001, 'cli-store'))

    def test_invalid_lower_priority_port_does_not_defeat_cli(self):
        config = self.settings('FLASK_RUN_PORT="unterminated\n',
            environ={'FLASK_RUN_PORT': 'invalid'}, port=9001)
        self.assertEqual(config.port, 9001)

    def test_invalid_ports_fail_without_echoing_payload(self):
        for value in ('', '0', '-1', '65536', '8.5', 'abc', '１２３', 'not-a-secret-to-echo'):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError) as error:
                    self.settings(environ={'FLASK_RUN_PORT': value})
                self.assertIn('FLASK_RUN_PORT', str(error.exception))
                if value == 'not-a-secret-to-echo':
                    self.assertNotIn(value, str(error.exception))
        with self.assertRaises(ConfigurationError):
            self.settings('FLASK_RUN_PORT=invalid\n')
        with self.assertRaises(ConfigurationError):
            self.settings(port=65536)

    def test_debug_spellings_and_invalid_values(self):
        for value in ('1', 'true', 'YES', 'On'):
            self.assertTrue(self.settings(environ={'FLASK_DEBUG': value}).debug)
        for value in ('0', 'false', 'NO', 'Off'):
            self.assertFalse(self.settings(environ={'FLASK_DEBUG': value}).debug)
        for value in ('', '2', 'maybe'):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                self.settings(environ={'FLASK_DEBUG': value})

    def test_known_invalid_syntax_fails_but_unrelated_settings_are_ignored(self):
        for line in ('FLASK_DEBUG', 'FLASK_RUN_PORT="unclosed', 'RIDEWORKS_DATA_DIR=two words'):
            with self.subTest(line=line), self.assertRaises(ConfigurationError):
                self.settings(line)
        config = self.settings('UNRELATED_SECRET="unclosed\nOTHER=$(do-not-run)\nFLASK_DEBUG=0\n')
        self.assertFalse(config.debug)

    def test_no_expansion_shell_execution_or_global_environment_changes(self):
        with patch.dict(os.environ, {'UNRELATED': 'unchanged'}, clear=True):
            original = dict(os.environ)
            config = self.settings('RIDEWORKS_DATA_DIR="${UNRELATED}/literal"\nFLASK_DEBUG=0\n')
            self.assertEqual(config.data_dir, '${UNRELATED}/literal')
            self.assertEqual(dict(os.environ), original)

    def test_env_is_rooted_at_checkout_not_current_directory(self):
        other = self.root / 'elsewhere'
        other.mkdir()
        (other / '.env').write_text('FLASK_RUN_PORT=8999\n')
        (self.root / '.env').write_text('FLASK_RUN_PORT=8877\n')
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
        self.assertEqual(self.settings('FLASK_RUN_PORT=8877\nFLASK_RUN_PORT=8999\n').port, 8999)

    def test_cli_passes_config_to_stdlib_server(self):
        (self.root / '.env').write_text('FLASK_RUN_PORT=8877\nFLASK_DEBUG=1\nRIDEWORKS_DATA_DIR=file-store\n')
        with patch.dict(os.environ, {}, clear=True), patch('rideworks.config.repository_root', return_value=self.root), patch('rideworks.web.serve') as serve:
            self.assertEqual(main(['serve']), 0)
            serve.assert_called_once_with('file-store', 8877, debug=True)
            serve.reset_mock()
            self.assertEqual(main(['--data-dir', 'cli-store', 'serve', '--port', '9001']), 0)
            serve.assert_called_once_with('cli-store', 9001, debug=True)

    def test_cli_invalid_config_fails_before_server_starts(self):
        (self.root / '.env').write_text('FLASK_DEBUG=maybe\n')
        with patch.dict(os.environ, {}, clear=True), patch('rideworks.config.repository_root', return_value=self.root), patch('rideworks.web.serve') as serve, patch('sys.stderr', new_callable=io.StringIO) as errors:
            self.assertEqual(main(['serve']), 1)
            self.assertIn('FLASK_DEBUG', errors.getvalue())
            serve.assert_not_called()

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
