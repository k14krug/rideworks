#!/usr/bin/env python3
"""Start the existing local application and open its browser, using normal config."""
from html import escape
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rideworks.config import startup_config
from rideworks.store import resolve_data_dir

URL = 'http://127.0.0.1:8766/'


def running(data_dir):
    try:
        with urlopen(URL+'settings', timeout=3) as response:
            html = response.read().decode()
    except (URLError, TimeoutError):
        return False
    if f'<code>{escape(str(data_dir))}</code>' not in html or 'id="active-data-dir"' not in html:
        raise RuntimeError('Port 8766 is occupied by a different application or store. Close it before starting RideWorks.')
    return True


def main():
    config = startup_config(port=8766)
    data_dir = resolve_data_dir(config.data_dir)
    if not (data_dir/'rideworks.sqlite3').is_file():
        raise RuntimeError('RideWorks store is missing. Restore the project data folder before launching; no empty store was created.')
    if not running(data_dir):
        descriptor = os.open(data_dir/'rideworks.log', os.O_CREAT|os.O_APPEND|os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'a') as log:
            process = subprocess.Popen([sys.executable, '-m', 'rideworks', '--data-dir', str(data_dir), 'serve', '--port', '8766'],
                                       cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
        for _ in range(40):
            if process.poll() is not None:
                raise RuntimeError('RideWorks could not start. Check rideworks.log in the selected data folder.')
            if running(data_dir):
                break
            time.sleep(.25)
        else:
            raise RuntimeError('RideWorks startup timed out. Check rideworks.log in the selected data folder.')
    print('RideWorks: '+URL)
    if shutil.which('cmd.exe'):
        subprocess.run(['cmd.exe', '/c', 'start', '', URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(URL)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        print('RideWorks: '+str(error), file=sys.stderr)
        raise SystemExit(1)
