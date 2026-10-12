#!/usr/bin/env python3
"""Extend the existing source-neutral review fixture for Home visual checks."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rideworks.goals import set_annual_goal
from rideworks.performance import rebuild_performance
from rideworks.power_curve import rebuild_curves
from rideworks.store import Store
from rideworks.strava_api import apply_observations, normalize
from rideworks.strava_streams import persist


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--long-facts',action='store_true',help='Stress wrapping with generated long contributor names and a large mileage value.')
    a=p.parse_args()
    if (a.data_dir/'rideworks.sqlite3').exists():p.error('Use a new empty preview store.')
    subprocess.run([sys.executable,str(ROOT/'tools/preview_activity_review.py'),'--data-dir',str(a.data_dir)],check=True)
    now=datetime.now(timezone.utc).replace(hour=16,minute=0,second=0,microsecond=0)
    with Store(a.data_dir) as store:
        rows=[normalize(dict(id=100+i,name='Synthetic weekly mileage',type='Ride',sport_type='Ride',
            start_date=(now-timedelta(days=7*i+4)).isoformat(),distance=(25+i%4*10)*1609.344,
            elapsed_time=3600,average_watts=120)) for i in range(1,12)]
        apply_observations(store,rows,999,int(now.timestamp()))
        if a.long_facts:
            long_rows=[]
            streams=[]
            for identity in (3,9):
                evidence=store.connection.execute('SELECT s.evidence_json FROM strava_api_activities a JOIN strava_api_sources s ON s.source_id=a.current_source_id WHERE a.external_id=?',(str(identity),)).fetchone()[0]
                values=json.loads(evidence)
                values['name']='Synthetic long contributor — '+('EnduranceAfterRecoveryWithoutAbbreviations'*4)+' · '+('source-supported words '*8)
                if identity==9:values['distance']=12345.6*1609.344
                long_rows.append(normalize(values))
                retained=store.connection.execute('SELECT s.evidence_json FROM strava_stream_current c JOIN strava_stream_sources s ON s.source_id=c.source_id WHERE c.external_id=?',(str(identity),)).fetchone()[0]
                streams.append((identity,json.loads(retained)))
            apply_observations(store,long_rows,999,int(now.timestamp()))
            # Bind the generated streams to their new summary observations.
            for identity,payload in streams:persist(store,identity,payload)
        set_annual_goal(store,now.year,'2200')
        rebuild_performance(store);rebuild_curves(store)
    print('Synthetic Home preview created; no personal source data used.')


if __name__=='__main__':main()
