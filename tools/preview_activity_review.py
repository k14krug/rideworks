#!/usr/bin/env python3
"""Build source-neutral synthetic review modes in a new disposable store."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from fit_fixture import make_fit
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.strava_streams import persist
from rideworks.performance import rebuild_performance
from rideworks.power_curve import rebuild_curves


def main():
    p = argparse.ArgumentParser(); p.add_argument('--data-dir', type=Path, required=True)
    a = p.parse_args()
    if (a.data_dir / 'rideworks.sqlite3').exists():
        p.error('Preview requires a new empty store.')
    now = datetime.now(timezone.utc).replace(hour=16, minute=0, second=0, microsecond=0)
    with Store(a.data_dir) as store, tempfile.TemporaryDirectory() as temporary:
        count = 3601
        for days, missing in [(-8, False), (-2, True)]:
            start = int(((now + timedelta(days=days)) - datetime(1989, 12, 31, tzinfo=timezone.utc)).total_seconds())
            power = [0 if i < 20 else 300 if i % 300 < 60 else 165 for i in range(count)]
            power[1500] = None
            path = Path(temporary) / ('synthetic-missing-signals.fit' if missing else 'synthetic-native.fit')
            path.write_bytes(make_fit(powers=[None]*count if missing else power,
                heart_rates=[None]*count if missing else [115 + (i % 80)//4 for i in range(count)],
                timestamps=list(range(start, start+count)), elapsed=count-1, timer=count,
                session_start_time=start, session_timestamp=start+count-1,
                lap_start_time=start, lap_timestamp=start+count-1,
                event_timestamps=(start,start+count-1), distance=25000, avg_power=None if missing else 190))
            store.import_fit(path)
        for identity, days, name, kind, mode in [
            (1,-400,'Synthetic long endurance ride','VirtualRide','rich'),
            (2,-22,'Synthetic short surges','VirtualRide','rich'),
            (3,-7,'Synthetic sustained effort','VirtualRide','rich'),
            (4,-3,'Synthetic interval session','VirtualRide','rich'),
            (5,-2,'Synthetic outdoor ride — unavailable','Ride','rich'),
            (6,-1,'Synthetic missing power','VirtualRide','hr'),
            (7,-1,'Synthetic metadata only','VirtualRide','thin'),
            (8,-1,'Synthetic missing both signals','VirtualRide','empty'),
            (9,-1,'Synthetic power without HR','VirtualRide','power')]:
            count = 7201 if identity == 1 else 5401 if identity == 3 else 2801 if identity == 4 else 3601
            values = normalize(dict(id=identity, name=name, type='Ride', sport_type=kind,
                start_date=(now+timedelta(days=days)).isoformat(), elapsed_time=count, moving_time=count,
                device_watts=True, distance=count*5, average_watts=180 if mode in ('rich','power') else None,
                average_heartrate=120 if mode in ('rich','hr') else None))
            apply_observations(store,[values],999,int(now.timestamp()))
            if mode == 'thin': continue
            stream = lambda data: dict(data=data,original_size=len(data),resolution='high',series_type='time')
            streams = dict(time=stream(list(range(count))))
            if mode in ('rich','power'):
                powers=[(500 if i<5 else 350 if i<40 else 145) if identity==2 else
                        (210 if 1200<=i<2400 else 185) if identity==3 else
                        (270 if i%300<60 else 135) if identity==4 else 160 for i in range(count)]
                if identity == 4: powers[1500] = None
                streams['watts'] = stream(powers)
            if mode in ('rich','hr'): streams['heartrate'] = stream([115]*count)
            persist(store,identity,streams)
        rebuild_performance(store); rebuild_curves(store)
    print('Synthetic Activity Review modes created.')


if __name__ == '__main__': main()
