#!/usr/bin/env python3
"""P5-01 verification: private evidence detail and separate safe aggregate output.

Run only against a disposable copy. No network, source edits or generated rides.
Representative labels are chosen independently from titles/Owner-known cases,
then challenged with native observed evidence. Titles do not become race proof.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.planning import plan, project, set_classification, set_feedback, activity_context
from rideworks.performance import performance_history
from rideworks.training_state import training_state
from verify_training_state_production import preservation


def fingerprint(root):
    db=sqlite3.connect((root.resolve()/'rideworks.sqlite3').as_uri()+'?mode=ro',uri=True)
    hashes={}
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        if name.startswith('planning_'): continue
        values=sorted(tuple(r) for r in db.execute('SELECT * FROM "'+name+'"'))
        hashes[name]=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
    db.close();return hashes


def horizon(data):
    hard=[r for r in data['days'] if r['hard']]
    assert len(hard)==3 and [r['hard_number'] for r in hard]==[1,2,3]
    assert data['days'][-1]['hard']
    today=date.fromisoformat(data['days'][0]['day'])
    assert [r['day'] for r in data['days']]==[(today+timedelta(days=i)).isoformat() for i in range(len(data['days']))]
    assert all(r['category'] in ('Race','Threshold','VO2','Recovery','Easy','Z2 endurance') for r in data['days'])
    return len(data['days'])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--baseline-dir',type=Path,required=True)
    parser.add_argument('--as-of',required=True)
    parser.add_argument('--private-output',type=Path,required=True)
    parser.add_argument('--aggregate-output',type=Path,required=True)
    args=parser.parse_args();now=datetime.fromisoformat(args.as_of);zone='America/Los_Angeles'
    from rideworks.store import Store
    with Store(args.data_dir) as store:
        before=fingerprint(args.data_dir)
        state=training_state(store,zone,as_of=now);performance=performance_history(store)
        initial=plan(store,zone,as_of=now);length=horizon(initial)
        assert plan(store,zone,as_of=now)==initial
        # Independently choose labeled examples, not sorted selected stress.
        history=plan(store,zone,as_of=now)['history']
        private=[];candidates=[]
        from rideworks.history import presentation
        for snap in store.activity_history():
            row=presentation(snap)
            if not row['absolute_time'] or row['activity_type'] not in ('Ride','Virtual Ride'):continue
            if datetime.fromisoformat(row['start_time'])>now:continue
            candidates.append(row)
        candidates.sort(key=lambda r:r['start_time'],reverse=True)
        selectors=[('Owner-known short-interval VO2',lambda r:'2026-10-07' in r['start_time'] and re.search(r'v[o0]2|30.?15',r['title'],re.I)),
                   ('Race-labeled source',lambda r:re.search(r'\brace\b|\bracing\b',r['title'],re.I)),
                   ('Z2-labeled source',lambda r:re.search(r'\bz2\b|90_z2',r['title'],re.I)),
                   ('Easy/recovery-labeled source',lambda r:re.search(r'easy|recovery',r['title'],re.I))]
        checks={}
        for name,predicate in selectors:
            sample=next((r for r in candidates if predicate(r)),None)
            if sample is None:
                checks[name]=dict(found=False);continue
            context=activity_context(store,sample['activity_id'],as_of=now)
            c=context['classification'];private.append(dict(role=name,activity_id=sample['activity_id'],title=sample['title'],start_time=sample['start_time'],classification=c))
            checks[name]=dict(found=True,category=c['category'],confidence=c['confidence'],hard=c.get('hard',False),
                              short_bouts=c.get('short_bouts'),longest_threshold_seconds=c.get('longest_threshold_seconds'))
            assert context['intent'] is None
            if name=='Race-labeled source':
                assert c['category']!='Race' or c['confidence']=='rider confirmed'
                # Simulated correction in disposable copy; then restore inference.
                set_classification(store,sample['activity_id'],'Race',as_of=now)
                assert activity_context(store,sample['activity_id'],as_of=now)['classification']['category']=='Race'
                race_asof=datetime.fromisoformat(sample['start_time'])+timedelta(days=1)
                race_plan=plan(store,zone,as_of=race_asof)
                horizon(race_plan)
                assert race_plan['days'][0]['category']=='Recovery'
                assert race_plan['days'][1]['power']=='~105–120 W'
                assert next(d for d in race_plan['days'] if d['hard'])['category'] in ('Threshold','VO2')
                checks[name]['simulated_manual_race_rotation']=[d['category'] for d in race_plan['days']]
                set_classification(store,sample['activity_id'],'automatic',as_of=now)
        assert checks['Owner-known short-interval VO2']['found']
        assert checks['Owner-known short-interval VO2']['category']=='VO2'
        set_feedback(store,zone,'heavy',as_of=now);heavy=plan(store,zone,as_of=now)
        assert heavy['days'][0]['category']=='Recovery';horizon(heavy)
        set_feedback(store,zone,'unknown',as_of=now)
        assert plan(store,zone,as_of=now)==initial
        # Behavior challenge from real latest hard history, with skipped date and extra race.
        from rideworks.planning import completed_history
        actual,_=completed_history(store,zone,as_of=now)
        tomorrow=date.fromisoformat(initial['today'])+timedelta(days=1)
        skipped=project(actual,tomorrow,fresh=True);horizon(skipped)
        unplanned=dict(activity_id='simulated',day=initial['today'],start_time=now.isoformat(),classification=dict(category='Race',hard=True,confidence='simulated correction'))
        extra=project(actual+[unplanned],tomorrow,fresh=True);horizon(extra)
        assert extra['days'][0]['category']=='Recovery'
        assert training_state(store,zone,as_of=now)==state
        assert performance_history(store)==performance
        assert fingerprint(args.data_dir)==before
        originals=preservation(args.data_dir,args.baseline_dir)
        hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ('data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv',)}
        with Store(args.data_dir) as reopened:assert plan(reopened,zone,as_of=now)==initial
        aggregate=dict(planner=initial['version'],classifier=initial['classifier'],as_of=args.as_of,
            three_hard_horizon_verified=True,displayed_dates=length,hard_offsets=[r['offset'] for r in initial['days'] if r['hard']],
            recommendation_categories=[r['category'] for r in initial['days']],representative_checks=checks,
            heavy_feedback_verified=True,skipped_date_horizon=len(skipped['days']),unplanned_race_horizon=len(extra['days']),
            repeat_restart_deterministic=True,training_state_unchanged=True,performance_unchanged=True,
            preexisting_tables_unchanged=len(before),preservation=originals,approved_dataset_hashes=hashes,
            no_private_source_detail_in_aggregate=True)
        args.private_output.parent.mkdir(parents=True,exist_ok=True)
        args.private_output.write_text(json.dumps(dict(samples=private,initial=initial,skipped=skipped,unplanned=extra),indent=2))
        args.aggregate_output.parent.mkdir(parents=True,exist_ok=True)
        args.aggregate_output.write_text(json.dumps(aggregate,indent=2))
        print(json.dumps(aggregate,indent=2))


if __name__=='__main__':main()
