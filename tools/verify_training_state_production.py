#!/usr/bin/env python3
"""P4-02 verification on a supplied private store; output is aggregate only.

Compare every preexisting table and original against a readonly baseline. Verify
model math independently by closed-form exponential convolution, and power NP
by direct 30-s window sums. Local titles/identities never enter the safe report.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.store import Store
from rideworks.training_state import training_state, ride_results
from rideworks.history import presentation


def readonly(root):
    db=sqlite3.connect((root.resolve()/'rideworks.sqlite3').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    return db


def preservation(root,baseline):
    with readonly(root) as current, readonly(baseline) as prior:
        tables=[r[0] for r in prior.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'training_stress_cache'")]
        for name in tables:
            quoted='"'+name.replace('"','""')+'"'
            a=sorted(tuple(r) for r in prior.execute('SELECT * FROM '+quoted))
            b=sorted(tuple(r) for r in current.execute('SELECT * FROM '+quoted))
            assert a==b, 'Preexisting table changed: '+name
        assert current.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not current.execute('PRAGMA foreign_key_check').fetchall()
        count=0
        for table in ('sources','export_snapshots'):
            for r in prior.execute('SELECT stored_path,sha256,byte_size FROM '+table):
                for directory in (root,baseline):
                    payload=(directory/r[0]).read_bytes()
                    assert len(payload)==r[2] and hashlib.sha256(payload).hexdigest()==r[1]
                count+=1
    return dict(tables_preserved=len(tables),original_artifacts_preserved=count,integrity='ok',foreign_key_violations=0)


def verify(data,store):
    days=data['days'];previous_f=previous_a=0; power_checks=0;hr_checks=0
    # Independent form of each exponential update (no production recurrence).
    for i,d in enumerate(days):
        for name,tau in [('fitness',42),('fatigue',7)]:
            # Full-history closed convolution, explicit zero seed.
            expected=(1-math.exp(-1/tau))*math.fsum(p['stress']*math.exp(-(i-j)/tau) for j,p in enumerate(days[:i+1]))
            assert math.isclose(d[name],expected,rel_tol=1e-11,abs_tol=1e-10)
        assert math.isclose(d['form'],previous_f-previous_a,rel_tol=1e-11,abs_tol=1e-10)
        previous_f,previous_a=d['fitness'],d['fatigue']
        assert d['stress']==math.fsum(r['selected']['stress'] for r in d['rides'] if r['selected']['stress'] is not None)
        assert d['unscored']==sum(r['selected']['stress'] is None for r in d['rides'])
        for n in (7,42):
            window=days[max(0,i+1-n):i+1]
            assert math.isclose(d[f'window{n}']['stress'],math.fsum(p['stress'] for p in window),abs_tol=1e-10)
            assert math.isclose(d[f'window{n}']['work_kj'],math.fsum(p['work_kj'] for p in window),abs_tol=1e-10)
        for ride in d['rides']:
            hr=ride['hr'];power=ride['power'];selected=ride['selected']
            if hr['stress'] is not None:
                s=hr['settings'];r=(hr['mean_hr']-s['resting_hr'])/(s['max_hr']-s['resting_hr']);threshold=(s['threshold_hr']-s['resting_hr'])/(s['max_hr']-s['resting_hr'])
                expected=100*hr['active_seconds']/3600*(r*math.exp(1.92*r))/(threshold*math.exp(1.92*threshold))
                assert math.isclose(expected,hr['stress'],rel_tol=1e-12);hr_checks+=1
            if selected['method']=='hr':assert selected['stress']==hr['stress'] and power['status'] not in ('calculated','corrected_estimate')
            if selected['method']=='power':assert selected['stress']==power['stress']
            if selected['stress'] is None:assert selected['status']=='unavailable'
            if not power.get('source') or power.get('observed_work_kj') is None:continue
            source=power['source']
            if source['format']=='Strava API stream':
                stream=next(s for s in store.strava_stream_evidence(ride['activity_id']) if s['source_id']==source['stream_source_id'])
                times=stream['streams']['time']['data'];values=stream['streams']['watts']['data'];events=[]
                assert power['status']!='corrected_estimate'
            else:
                native=store.get_source(source['source_id']);events=native['events']
                times=[datetime.fromisoformat(r['timestamp']).timestamp() if r['timestamp'] else None for r in native['records']]
                values=[r['power'] for r in native['records']]
            intervals=[];active=None
            for e in events:
                if e['event']!='timer':continue
                t=datetime.fromisoformat(e['timestamp']).timestamp()
                if e['event_type']=='start':active=t
                else:intervals.append((active,t));active=None
            counts=Counter(times);observed=[];groups={}
            for t,v in zip(times,values):
                if t is None or counts[t]!=1 or v is None or v<0:continue
                group=next((j for j,(a,b) in enumerate(intervals) if a<=t and t+1<=b),None) if intervals else 0
                if group is None:continue
                observed.append(v);groups.setdefault(group,[]).append((t,v))
            assert math.isclose(math.fsum(observed)/1000,power['observed_work_kj'],abs_tol=1e-9)
            runs=[]
            for points in groups.values():
                if power['status']=='corrected_estimate':
                    dense=[]
                    for j,(t,v) in enumerate(points):
                        dense.extend([v]*(int(t-points[j-1][0]) if j else 1))
                    runs.append(dense)
                elif power['status']=='calculated':runs.append([v for t,v in points])
                elif power['status']=='partial':
                    run=[];last=None
                    for t,v in points:
                        if last is not None and t!=last+1:
                            if len(run)>=600:runs.append(run)
                            run=[]
                        run.append(v);last=t
                    if len(run)>=600:runs.append(run)
            if power['stress'] is not None:
                scores=[]
                for run in runs:
                    np=(math.fsum((math.fsum(run[i:i+30])/30)**4 for i in range(len(run)-29))/(len(run)-29))**.25
                    scores.append(len(run)/3600*(np/power['ftp']['value'])**2*100)
                assert math.isclose(math.fsum(scores),power['stress'],rel_tol=1e-10,abs_tol=1e-9)
            power_checks+=1
    return dict(exact_daily_models=len(days),independent_observed_power_checks=power_checks,independent_hr_formula_checks=hr_checks)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--baseline-dir',type=Path,required=True)
    p.add_argument('--as-of',type=str,required=True);p.add_argument('--timezone',default='America/Los_Angeles')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();before=preservation(a.data_dir,a.baseline_dir)
    with Store(a.data_dir) as store:
        data=training_state(store,a.timezone,as_of=datetime.fromisoformat(a.as_of))
        checks=verify(data,store)
        repeated=training_state(store,a.timezone,as_of=datetime.fromisoformat(a.as_of));assert data==repeated
        all_rides,_=ride_results(store,a.timezone,as_of=datetime.fromisoformat(a.as_of))
        kinds={s['activity']['activity_id']:presentation(s)['activity_type'] for s in store.activity_history()}
        cohorts={kind:dict(rides=sum(kinds[r['activity_id']]==kind for r in all_rides),
            selected_classes=dict(Counter(r['selected']['status'] for r in all_rides if kinds[r['activity_id']]==kind)))
            for kind in ('Virtual Ride','Ride')}
    after=preservation(a.data_dir,a.baseline_dir);assert before==after
    rides=[r for d in data['days'] for r in d['rides']]
    report=dict(version=data['version'],power_source_policy=data['power_source_policy'],coverage=data['coverage'],coverage_by_activity_type=cohorts,verification=checks,preservation=after,
                hr_candidate_reasons=dict(Counter(c.get('reason') or 'usable' for r in rides for c in r['hr_candidates'])),
                model_period_rides=len(rides),
                power_candidate_classes_in_model_period=dict(Counter(r['power']['status'] for r in rides)),
                source_digest=data['ftp_source_sha256'],restart_recompute='deterministic',
                known_limitations=['Recorded interval is not whole session','HR formula is a retrospective model',
                  'HR threshold/max assumptions can exclude values outside modeled range',
                  'Unscored rides retain unavailable evidence; model contribution is zero',
                  'HR stream coverage >=99%, adjacent measured intervals <=15s, duration alignment <=max(1s,1%); independent same-source summary fallback does not claim stream completeness',
                  'HR summaries use reported moving/timer/lap duration; mean active scope and pause treatment are unverified'])
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
