#!/usr/bin/env python3
"""Create a disposable synthetic Store for Relative Effort browser checks."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from fit_fixture import make_fit
from ftp_fixture import seed_ftp
from rideworks.performance import rebuild_performance
from rideworks.power_curve import rebuild_curves
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    if (args.data_dir / 'rideworks.sqlite3').exists():
        parser.error('Use a new empty preview Store.')
    subprocess.run([sys.executable, str(ROOT / 'tools/preview_home.py'),
                    '--data-dir', str(args.data_dir)], check=True)
    now = datetime.now(timezone.utc).replace(hour=16, minute=0, second=0, microsecond=0)
    epoch = datetime(1989, 12, 31, tzinfo=timezone.utc)
    with Store(args.data_dir) as store, tempfile.TemporaryDirectory() as temporary:
        seed_ftp(store, [('2000-01-01', 200), ('2030-01-01', 200)])
        for i in range(10):
            start = int(((now - timedelta(days=20-i*2)) - epoch).total_seconds())
            path = Path(temporary) / f'synthetic-{i}.fit'
            path.write_bytes(make_fit(powers=[120+i*9]*1801, heart_rates=[120]*1801,
                timestamps=range(start, start+1801), elapsed=1800, timer=1800,
                session_start_time=start, session_timestamp=start+1800,
                lap_start_time=start, lap_timestamp=start+1800,
                event_timestamps=(start, start+1800), distance=15000, avg_power=120+i*9))
            store.import_fit(path)
            observation = dict(id=800000+i, name=f'Synthetic effort {i}', type='Ride',
                sport_type='VirtualRide', start_date=(now-timedelta(days=20-i*2)).isoformat(),
                elapsed_time=1800, moving_time=1800, distance=15000, suffer_score=None if i == 9 else i*20)
            apply_observations(store, [normalize(observation)], 999, int(now.timestamp()))
        rebuild_performance(store)
        rebuild_curves(store)
    print('Synthetic Relative Effort preview created; no personal source data used.')


if __name__ == '__main__':
    main()
