#!/usr/bin/env python3
"""Create clearly synthetic source-backed curves in a new disposable store."""
import argparse
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.store import Store
from rideworks.strava_api import apply_observations,normalize
from rideworks.strava_streams import persist
from rideworks.performance import rebuild_performance
from rideworks.power_curve import rebuild_curves


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args()
    if (args.data_dir/'rideworks.sqlite3').exists():p.error('Synthetic preview requires a new empty store.')
    now=datetime.now(timezone.utc).replace(hour=16,minute=0,second=0,microsecond=0)
    entries=[(1,-400,'Synthetic long endurance ride',7201),(2,-22,'Synthetic short surges',3601),
             (3,-7,'Synthetic sustained effort',5401),(4,-3,'Synthetic interval session',2801),
             (5,-2,'Synthetic outdoor ride — unavailable',1801),(6,-1,'Synthetic missing power',90)]
    with Store(args.data_dir) as s:
        for identity,days,title,count in entries:
            powers=[]
            for i in range(count):
                w=160 if identity==1 else 145 if identity==2 else 185 if identity==3 else 135
                if identity==2 and i<40:w=500 if i<5 else 350
                if identity==3 and 1200<=i<2400:w=210
                if identity==4 and i%300<60:w=270
                if identity==4 and i<5:w=430
                if identity==4 and i==1500:w=None
                if identity==6:w=None
                powers.append(w)
            values=normalize(dict(id=identity,name=title,type='Ride',sport_type='Ride' if identity==5 else 'VirtualRide',
                start_date=(now+timedelta(days=days)).isoformat(),elapsed_time=count,moving_time=count,
                device_watts=True,distance=count*5))
            apply_observations(s,[values],999,int(now.timestamp()))
            stream=lambda xs:dict(data=xs,original_size=len(xs),resolution='high',series_type='time')
            persist(s,identity,dict(time=stream(list(range(count))),watts=stream(powers),heartrate=stream([115]*count)))
        rebuild_performance(s);report=rebuild_curves(s)
    print('Synthetic-only preview created:',report)


if __name__=='__main__':main()
