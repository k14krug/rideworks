"""Normal launcher cannot open the wrong store or create a missing history."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rideworks.config import StartupConfig

spec=importlib.util.spec_from_file_location('launcher',Path(__file__).resolve().parents[1]/'tools/launch_rideworks.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_missing_store_fails_before_starting_or_opening_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            missing=Path(directory)/'missing'
            with patch.object(launcher,'startup_config',return_value=StartupConfig(str(missing),8766,False)),patch.object(launcher.subprocess,'Popen') as start:
                with self.assertRaisesRegex(RuntimeError,'no empty store was created'):launcher.main()
                start.assert_not_called();self.assertFalse(missing.exists())

    def test_relative_override_is_resolved_once_before_child_changes_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'rideworks.sqlite3').touch()
            with patch.object(launcher,'startup_config',return_value=StartupConfig('relative-test',8766,False)),patch.object(launcher,'resolve_data_dir',return_value=root),patch.object(launcher,'running',side_effect=[False,True]),patch.object(launcher.subprocess,'Popen') as start,patch.object(launcher,'webbrowser'),patch.object(launcher.shutil,'which',return_value=None):
                start.return_value.poll.return_value=None
                launcher.main()
                args=start.call_args.args[0]
                self.assertEqual(args[args.index('--data-dir')+1],str(root))


if __name__=='__main__':unittest.main()
