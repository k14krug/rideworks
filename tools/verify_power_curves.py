#!/usr/bin/env python3
"""Independent PC-01 numerical/preservation verification on a disposable copy.

Only source-neutral counts/hashes are published. Requires the completed cache.
The baseline is opened read-only; no source or benchmark is modified.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.store import Store
from rideworks.power_curve import comparison, curve_history, rebuild_curves
from rideworks.training_state import timer_scope


def independent(records, durations, intervals=None):
    """Prefix counts over the original sequence, independent of production runs."""
    totals, missing, edges, groups, stamps = [0], [0], [0], [], []
    for i,r in enumerate(records):
        stamp=datetime.fromisoformat(r['timestamp']).timestamp() if r['timestamp'] else None
        group=0 if intervals is None else next((j for j,(a,b) in enumerate(intervals)
                   if stamp is not None and a<=stamp<=b),None)
        valid=stamp is not None and r['power'] is not None and group is not None
        totals.append(totals[-1]+(r['power'] if r['power'] is not None else 0))
        missing.append(missing[-1]+(not valid))
        broken=i>0 and (stamp is None or stamps[-1] is None or stamp-stamps[-1]!=1 or group!=groups[-1])
        edges.append(edges[-1]+broken)
        stamps.append(stamp);groups.append(group)
    results={}
    for d in durations:
        best,position,count=None,None,0
        for j in range(len(records)-d+1):
            end=j+d
            if missing[end]!=missing[j] or edges[end]!=edges[j+1]:continue
            count+=1;total=totals[end]-totals[j]
            if best is None or total>best:best,position=total,j
        if best is not None:
            results[d]=dict(sum_watts=best,start_record_index=records[position]['record_index'],
                            end_exclusive_record_index=records[position+d-1]['record_index']+1,
                            eligible_window_count=count,average_watts=best/d,
                            rounded_watts=(best+d//2)//d,
                            start_timestamp=records[position]['timestamp'],
                            end_exclusive_timestamp=(datetime.fromisoformat(records[position]['timestamp'])+timedelta(seconds=d)).isoformat())
    return results


def preserve(current, baseline):
    def read(root):return sqlite3.connect((root/'rideworks.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    originals=0
    with read(current) as db,read(baseline) as before:
        tables=[r[0] for r in before.execute("SELECT name FROM sqlite_master WHERE type='table'")
                if not r[0].startswith('planning_') and r[0] not in ('training_stress_cache','power_curve_profiles')]
        for name in tables:
            sql='SELECT * FROM "'+name+'"'
            assert sorted(db.execute(sql).fetchall())==sorted(before.execute(sql).fetchall()),'Preserved table mismatch: '+name
        for table in ('sources','export_snapshots'):
            for path,digest,size in before.execute('SELECT stored_path,sha256,byte_size FROM '+table):
                for root in (current,baseline):
                    raw=(root/path).read_bytes();assert len(raw)==size and sha256(raw).hexdigest()==digest
                originals+=1
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    hashes={path:sha256(Path(path).read_bytes()).hexdigest() for path in (
        'data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv',)}
    return dict(source_tables_preserved=len(tables),originals_preserved=originals,
                integrity='ok',foreign_key_violations=0,approved_reference_hashes=hashes)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--baseline-dir',type=Path,required=True)
    parser.add_argument('--aggregate-output',type=Path,required=True)
    args=parser.parse_args()
    started=perf_counter();counts=Counter();durations=[];quality=Counter();formats=Counter()
    with Store(args.data_dir) as store:
        history=curve_history(store);assert history['pending']==0
        saved={r['activity_id']:json.loads(r['result_json']) for r in store.connection.execute(
             "SELECT * FROM performance_history WHERE policy='virtual-power-evidence-v2'")}
        for profile in history['profiles']:
            by_source={}
            for p in profile['points']:by_source.setdefault(p['source']['source_id'],[]).append(p)
            for source_id,points in by_source.items():
                ref=points[0]['source'];formats[ref['content_format']]+=1
                if ref['content_format']=='Strava API stream':
                    observed=next(e for e in store.strava_stream_evidence(profile['activity_id']) if e['source_id']==source_id)
                    start=datetime.fromisoformat(observed['start_date'].replace('Z','+00:00'))
                    records=[dict(record_index=i,power=p,timestamp=(start+timedelta(seconds=t)).isoformat())
                             for i,(t,p) in enumerate(zip(observed['streams']['time']['data'],observed['streams']['watts']['data']))]
                    intervals=None;verified=False
                else:
                    native=store.get_source(source_id);records=native['records']
                    intervals,_,verified=timer_scope(native['events'],native['summary'])
                    if not verified:intervals=None
                quality[ref['timer_quality']]+=1
                expected=independent(records,[p['duration_seconds'] for p in points],intervals)
                for p in points:
                    d=p['duration_seconds'];durations.append(d)
                    for key,value in expected[d].items():assert p[key]==value,'Numerical MMP mismatch: '+key
                    counts['independent_duration_windows_verified']+=1
                    counts['efforts_with_timer_discrepancy']+=bool(p['source']['timer_discrepancy'])
                accepted=saved.get(profile['activity_id'])
                p=next((p for p in points if p['duration_seconds']==1200),None)
                if accepted and accepted['eligible']:
                    assert p is not None
                    for key in ('average_watts','rounded_watts'):assert p[key]==accepted[key]
                    if ref['content_format']=='Strava API stream':
                        for key in ('start_offset','end_exclusive_offset'):assert p[key]==accepted[key]
                        counts['api_best20_parity']+=1
                    else:
                        assert ref['source_id']==accepted['source_id']
                        for key in ('start_record_index','end_exclusive_record_index','start_timestamp','end_exclusive_timestamp'):assert p[key]==accepted[key]
                        counts['native_best20_parity']+=1
                    if not verified:assert p['eligible_window_count']==accepted['eligible_window_count']
                    elif p['eligible_window_count']!=accepted['eligible_window_count']:counts['verified_scope_window_count_changes']+=1
            counts['profiles_shorter_than_20min']+=not any(p['duration_seconds']==1200 for p in profile['points'])
            counts['profiles_hour_plus']+=any(p['duration_seconds']>=3600 for p in profile['points'])
        # A historical prior cohort is independently scanned by start-time
        # and exact sums, not by production envelope membership logic.
        anchor=max(history['profiles'],key=lambda p:p['activity']['start_time'])
        when=datetime.fromisoformat(anchor['activity']['start_time'])
        data=comparison(store,activity_id=anchor['activity_id'])
        eligible=[p for p in history['profiles'] if p['activity']['absolute_time']
                  and p['activity_id']!=anchor['activity_id']
                  and when-timedelta(days=42)<=datetime.fromisoformat(p['activity']['start_time'])<when]
        for best in data['series']['six']['points']:
            d=best['duration_seconds']
            candidates=[(p,q) for p in eligible for q in p['points'] if q['duration_seconds']==d]
            p,q=min(candidates,key=lambda pair:(-pair[1]['sum_watts'],datetime.fromisoformat(pair[0]['activity']['start_time']),pair[0]['activity_id']))
            assert best['sum_watts']==q['sum_watts'] and best['activity']['activity_id']==p['activity_id']
            counts['historical_envelope_anchors_verified']+=1
        assert len(eligible)==data['series']['six']['count']
        assert counts['native_best20_parity']==sum(r['eligible'] and r.get('extraction_id') is not None for r in saved.values())
        assert counts['api_best20_parity']==sum(r['eligible'] and 'api_evidence' in r for r in saved.values())
        first=curve_history(store)
        repeat=rebuild_curves(store);assert repeat['computed']==0
        assert curve_history(store)==first
        with Store(args.data_dir) as restart:assert curve_history(restart)==first
        before=perf_counter();comparison(store);counts['aggregation_runtime_ms']=round((perf_counter()-before)*1000)
        report=dict(method=history['method'],grid=history['grid'],evaluated=history['evaluated'],
                    profiles=len(history['profiles']),pending=0,counts=dict(counts),
                    source_formats=dict(formats),timer_quality=dict(quality),
                    shortest_anchor_seconds=min(durations),longest_anchor_seconds=max(durations),
                    distinct_anchor_count=len(set(durations)),profile_anchor_count=len(durations),
                    longest_observed_run_seconds=max(p.get('longest_continuous_seconds',0) for p in history['profiles']),
                    repeat_incremental_build=repeat,verification_elapsed_seconds=round(perf_counter()-started,3))
    report['preservation']=preserve(args.data_dir,args.baseline_dir)
    args.aggregate_output.parent.mkdir(parents=True,exist_ok=True)
    args.aggregate_output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
