#!/usr/bin/env python3
"""Owner-discovered post-sync case on a supplied disposable copy, with safe output."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.store import Store
from rideworks.planning import completed_history, plan, project
from rideworks.training_state import training_state
from rideworks.performance import performance_history
from rideworks.web import Application


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def preserve(root,baseline):
    def ro(directory):return sqlite3.connect((directory.resolve()/'rideworks.sqlite3').as_uri()+'?mode=ro',uri=True)
    with ro(root) as current, ro(baseline) as prior:
        tables=[r[0] for r in prior.execute("SELECT name FROM sqlite_master WHERE type='table'")
                if not r[0].startswith('planning_') and r[0]!='training_stress_cache']
        for name in tables:
            sql='SELECT * FROM "'+name+'"'
            assert sorted(current.execute(sql).fetchall())==sorted(prior.execute(sql).fetchall()),name
        originals=0
        for table in ('sources','export_snapshots'):
            for path,sha,size in prior.execute('SELECT stored_path,sha256,byte_size FROM '+table):
                for directory in (root,baseline):
                    raw=(directory/path).read_bytes();assert len(raw)==size and hashlib.sha256(raw).hexdigest()==sha
                originals+=1
        assert current.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not current.execute('PRAGMA foreign_key_check').fetchall()
    return dict(source_tables_preserved=len(tables),originals_preserved=originals,integrity='ok',foreign_key_violations=0)


def horizon(data):
    days=data['days'];hard=[r for r in days if r['hard']]
    assert len(hard)==3 and days[-1]['hard_number']==3
    assert [r['hard_number'] for r in hard]==[1,2,3]
    start=datetime.fromisoformat(days[0]['day'])
    assert [r['day'] for r in days]==[(start+timedelta(days=i)).date().isoformat() for i in range(len(days))]
    assert all(r['category'] in ('Race','Threshold','VO2','Recovery','Easy','Z2 endurance') for r in days)


def main():
    p=argparse.ArgumentParser()
    for name in ('data-dir','baseline-dir','prior-planner','private-output','aggregate-output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--as-of',required=True);a=p.parse_args();asof=datetime.fromisoformat(a.as_of);zone='America/Los_Angeles'
    spec=importlib.util.spec_from_file_location('rideworks._prior_planner',a.prior_planner)
    prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
    with Store(a.baseline_dir) as baseline:
        baseline_state=training_state(baseline,zone,as_of=asof);baseline_performance=performance_history(baseline)
    with Store(a.data_dir) as s:
        actual,_=completed_history(s,zone,as_of=asof);data=plan(s,zone,as_of=asof)
        assert data['today']=='2026-10-10' and data['fresh']
        completed=[r for r in data['today_actual'] if r['classification']['category']=='Recovery']
        assert len(completed)==1 and 2400<=completed[0]['duration']<=2500 and 93<=completed[0]['average_power']<=95
        assert data['latest_hard']['day']=='2026-10-07' and data['latest_hard']['classification']['category']=='VO2'
        assert all('assumed rest' in r['state'] for r in data['recent_days'] if r['day'] in ('2026-10-08','2026-10-09'))
        horizon(data)
        assert data['next_ride']['day']=='2026-10-11' and data['next_ride']['category']=='Race'
        assert not data['days'][0]['hard']
        old=prior.project(actual,data['today'],fresh=True)
        assert old['days'][0]['day']=='2026-10-10' and old['days'][0]['category']=='Easy'
        before_history=[r for r in actual if r['day']<data['today']]
        before=project(before_history,data['today'],fresh=True);horizon(before)
        assert before['next_ride']['day']=='2026-10-10' and before['next_ride']['category']=='Race'
        confirmed=deepcopy(before_history)
        race=next(r for r in confirmed if r['day']=='2026-10-04' and r['classification'].get('title_hint')=='Race')
        race['classification'].update(category='Race',hard=True,confidence='simulated rider confirmation')
        third=project(confirmed,data['today'],fresh=True);horizon(third)
        assert third['next_ride']['frequency_exception'] and third['next_ride']['hard_dates_in_window']==3
        assert 'above the usual two' in third['next_ride']['reason']
        old_confirmed=prior.project(confirmed,data['today'],fresh=True)
        assert old_confirmed['days'][0]['category']=='Z2 endurance'
        heavy=project(confirmed,data['today'],fresh=True,legs='heavy');assert heavy['next_ride']['category']=='Recovery'
        stale=project(before_history,data['today'],fresh=False);assert stale['next_ride']['category']=='Easy'
        assert not any(r['frequency_exception'] for r in third['days'][1:])
        state=training_state(s,zone,as_of=asof);performance=performance_history(s)
        assert state==baseline_state and performance==baseline_performance
        assert plan(s,zone,as_of=asof)==data
        with Store(a.data_dir) as reopened:assert plan(reopened,zone,as_of=asof)==data
        app=Application(a.data_dir)
        html={name:app.get(route)[2].decode() for name,route in [
            ('Home','/?home_tz=America%2FLos_Angeles'),('Plan','/plan?plan_tz=America%2FLos_Angeles'),
            ('Activity Review','/activities/'+completed[0]['activity_id']+'?plan_tz=America%2FLos_Angeles')]}
        assert all('data-next-day="2026-10-11"' in page for page in html.values())
        preservation=preserve(a.data_dir,a.baseline_dir)
        sha={name:hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in (
            'data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv',)}
        safe=dict(planner=data['version'],classifier=data['classifier'],as_of=a.as_of,
            actual_owner_case_verified=True,assumed_recovery_dates_verified=2,
            before_primary=dict(offset=0,category=old['days'][0]['category']),
            after_primary=dict(offset=1,category=data['next_ride']['category']),
            home_plan_review_same_next=True,before_ride_quality_eligible=True,
            confirmed_race_third_in_seven=True,prior_rigid_cap_category=old_confirmed['days'][0]['category'],
            after_soft_guideline_category=third['next_ride']['category'],
            race_metadata_present=bool(race['classification'].get('race_metadata_source')),
            source_race_requires_confirmation=True,heavy_and_stale_verified=True,
            future_default_third_exceptions=0,projected_days=len(data['days']),hard_offsets=[r['offset'] for r in data['days'] if r['hard']],
            training_state_same_digest=digest(state),performance_same_digest=digest(performance),
            training_state_unchanged=True,performance_unchanged=True,repeat_restart_deterministic=True,
            preservation=preservation,approved_dataset_hashes=sha)
        private=dict(actual_plan=data,prior_plan=old,before_ride=before,confirmed_race_before_ride=third,completed=completed)
        a.private_output.parent.mkdir(parents=True,exist_ok=True);a.private_output.write_text(json.dumps(private,indent=2))
        a.aggregate_output.parent.mkdir(parents=True,exist_ok=True);a.aggregate_output.write_text(json.dumps(safe,indent=2)+'\n')
        print(json.dumps(safe,indent=2))


if __name__=='__main__':main()
