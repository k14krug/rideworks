#!/usr/bin/env python3
"""Reproduce the HOME-UI-05 timing using a disposable synthetic preview Store."""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from statistics import median
from threading import Thread
from time import perf_counter
from unittest.mock import patch
from urllib.request import urlopen

from rideworks.store import Store
from rideworks.web import create_server

AS_OF = datetime(2026, 10, 30, 20, tzinfo=timezone.utc)


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return AS_OF.astimezone(tz) if tz else AS_OF.replace(tzinfo=None)


def add_old_activities(store):
    """Extend a fresh synthetic preview; never use with personal data."""
    from rideworks.performance import rebuild_performance
    from rideworks.power_curve import rebuild_curves
    from rideworks.strava_api import normalize
    for i in range(250):
        activity, source, external = f'benchmark-old-{i:04d}', f'benchmark-source-{i:04d}', str(5000000+i)
        values = normalize(dict(id=int(external), name='Synthetic old activity', type='Ride', sport_type='VirtualRide',
            start_date=(AS_OF-timedelta(days=120+i)).isoformat(), elapsed_time=1200, moving_time=1200))
        payload = json.dumps(values, sort_keys=True, ensure_ascii=True, allow_nan=False)
        store.connection.execute('INSERT INTO activities VALUES (?,?)', (activity, AS_OF.isoformat()))
        store.connection.execute('INSERT INTO strava_api_sources VALUES (?,?,?,?,?,?,?,?)',
            (source, activity, external, sha256(payload.encode()).hexdigest(), 'synthetic', AS_OF.isoformat(), 'strava-summary-v1', payload))
        store.connection.execute('INSERT INTO strava_api_activities VALUES (?,?,?)', (external, activity, source))
    rebuild_performance(store)
    rebuild_curves(store)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', required=True, help='Disposable synthetic preview Store only')
    parser.add_argument('--add-old', action='store_true', help='Add 250 synthetic old activities once')
    args = parser.parse_args()
    with Store(args.data_dir) as store:
        if args.add_old:
            if store.connection.execute("SELECT 1 FROM activities WHERE activity_id LIKE 'benchmark-old-%' LIMIT 1").fetchone():
                parser.error('Synthetic old activities already exist')
            add_old_activities(store)
        with patch('rideworks.dashboard.datetime', FixedDateTime), create_server(args.data_dir, 0) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f'http://127.0.0.1:{server.server_address[1]}/?home_tz=UTC'
            try:
                for _ in range(3):
                    with urlopen(url) as response:
                        response.read()
                times = []
                for _ in range(20):
                    start = perf_counter()
                    with urlopen(url) as response:
                        response.read()
                    times.append((perf_counter()-start)*1000)
            finally:
                server.shutdown()
                thread.join()
        count = store.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0]
        print(f'warm requests=20 median_ms={median(times):.1f} p95_ms={sorted(times)[18]:.1f} activities={count}')
        from rideworks import power_curve
        if hasattr(power_curve, 'recent_bests'):
            result = power_curve.recent_bests(store, AS_OF)
            print(f"plausible_date_rows={result['scanned']} candidate_activities={result['candidates']} validated_profiles={result['validated']}")


if __name__ == '__main__':
    main()
