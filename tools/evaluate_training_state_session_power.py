#!/usr/bin/env python3
"""Private session-PSS experiment; never a production selector or cache writer.

Compare a pinned Elevate time-buffer method with recorded evidence and explain
duration/representativeness risks. Published output contains only aggregates.
"""
import argparse
from bisect import bisect_right
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.history import presentation
from rideworks.store import Store
from rideworks.training_state import daily_series, epoch, finite, timer_scope
from tools.diagnose_training_state_power import bins, table_digest, response
from tools.compare_training_state_elevate import read_reference

METHOD='diagnostic-elevate-time-buffer-session-pss-v2'
REPRESENTATIVENESS='diagnostic-distributed-observations-v1'
SCREEN_VARIANTS={
    'proposed':dict(total_floor=.8,local_floor=.5,window_seconds=300),
    'total_70_percent':dict(total_floor=.7,local_floor=.5,window_seconds=300),
    'total_90_percent':dict(total_floor=.9,local_floor=.5,window_seconds=300),
    'total_95_percent':dict(total_floor=.95,local_floor=.5,window_seconds=300),
    'total_99_percent':dict(total_floor=.99,local_floor=.5,window_seconds=300),
    'local_40_percent':dict(total_floor=.8,local_floor=.4,window_seconds=300),
    'local_60_percent':dict(total_floor=.8,local_floor=.6,window_seconds=300),
    'local_75_percent':dict(total_floor=.8,local_floor=.75,window_seconds=300),
    'window_180_seconds':dict(total_floor=.8,local_floor=.5,window_seconds=180),
    'window_600_seconds':dict(total_floor=.8,local_floor=.5,window_seconds=600),
}
REFERENCE_COMMIT='df9e2cebf5055d28b652628c8654a701845935cc'
REFERENCE_SOURCE_SHA256='8fd699848e597a307b1d1adaffe19f5b99a149412d39bcd35a5e4e87806dd909'


def buffer_fourths(times, powers):
    """Available samples only: time triggers batch emission, no resampling.

    Mirrors the pinned reference's check-before-time-add and dropped final batch.
    Means are arithmetic sample means, not time-weighted or overlapping windows.
    """
    elapsed=0.;buffer=[];fourths=[]
    for i in range(1,len(times)):
        buffer.append(powers[i])
        if elapsed>=30:
            fourths.append((math.fsum(buffer)/len(buffer))**4)
            elapsed=0.;buffer=[]
        elapsed+=times[i]-times[i-1]
    return fourths


def reference_np(times,powers):
    values=buffer_fourths(times,powers)
    return (math.fsum(values)/len(values))**.25 if values else None


def distribution_screen(times,intervals,*,total_floor=.8,local_floor=.5,window_seconds=300):
    """Observed half-open bins only; no missing sample/pause reconstruction.

    Closed timers define an active-time axis. Without them the caller supplies
    the full same-source elapsed timeline, NOT the shorter moving-time value.
    Test every sliding window exactly: extrema occur at bin boundaries or those
    boundaries minus window width. Include leading/trailing omissions.
    """
    segments=[];offset=0.
    for a,b in intervals:
        for t in times:
            lo=max(a,t);hi=min(b,t+1)
            if hi>lo:segments.append((offset+lo-a,offset+hi-a))
        offset+=b-a
    merged=[]
    for a,b in sorted(segments):
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    starts=[a for a,b in merged];prefix=[0.]
    for a,b in merged:prefix.append(prefix[-1]+b-a)
    def observed_until(t):
        i=bisect_right(starts,t)-1
        return 0. if i<0 else prefix[i]+min(t,merged[i][1])-merged[i][0]
    width=min(window_seconds,offset)
    boundaries=[0.,offset-width]
    for a,b in merged:boundaries.extend((a,b,a-width,b-width))
    windows=[(observed_until(s+width)-observed_until(s),s)
             for s in boundaries if 0<=s<=offset-width]
    least,start=min(windows) if windows else (0.,0.)
    total=prefix[-1]/offset if offset else 0.;local=least/width if width else 0.
    holes=[];last=0.
    for a,b in merged:
        if a>last:holes.append(dict(start_seconds=last,end_seconds=a,seconds=a-last))
        last=b
    if last<offset:holes.append(dict(start_seconds=last,end_seconds=offset,seconds=offset-last))
    reason='insufficient_distributed_observations' if total<total_floor-1e-12 else 'concentrated_recording_omission' if local<local_floor-1e-12 else None
    return dict(policy=REPRESENTATIVENESS,passes=reason is None,reason=reason,
        total_floor=total_floor,local_floor=local_floor,window_seconds=width,
        timeline_seconds=offset,observed_seconds=prefix[-1],observed_fraction=total,
        worst_window_start_seconds=start,worst_window_observed_seconds=least,
        worst_window_observed_fraction=local,omissions=holes,
        longest_omission_seconds=max((h['seconds'] for h in holes),default=0),
        representativeness_proven=False)


def estimate(times,powers,*,duration,elapsed_duration,ftp,events=(),summary=None,known_omitted_effort=False,duration_tolerance=0,timeline_start=0):
    result=dict(method=METHOD,status='unavailable',stress=None,scope='estimated session; representativeness unverified',
        duration_seconds=duration,elapsed_seconds=elapsed_duration,weighted_power=None,buffer_count=0,
        samples_invented=0,whole_session_verified=False,observed_recording=bins(times,powers),limitations=[])
    def reject(reason):return result|dict(reason=reason)
    if len(times)!=len(powers) or not times:return reject('empty_or_unpaired_power')
    if any(not finite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):return reject('invalid_or_ambiguous_timing')
    if any(p is not None and (not finite(p) or p<0) for p in powers):return reject('invalid_watts')
    result['missing_watt_samples_excluded']=sum(p is None for p in powers)
    available=[(t,p) for t,p in zip(times,powers) if p is not None]
    times=[t for t,p in available];powers=[p for t,p in available]
    if not times:return reject('no_available_watts')
    if not finite(ftp) or ftp<=0:return reject('missing_dated_ftp')
    # Reported integer seconds and inclusive sample bins can differ by one bin.
    if not finite(duration) or not finite(elapsed_duration) or not 0<duration<=elapsed_duration+duration_tolerance:return reject('unsupported_or_implausible_duration')
    if times[-1]-times[0]>elapsed_duration+1:return reject('recording_exceeds_reported_elapsed')
    intervals,problem,verified=timer_scope(events,summary or {})
    if any(e['event']=='timer' for e in events) and intervals is None:return reject('contradictory_or_unresolved_timer')
    if intervals and abs(math.fsum(b-a for a,b in intervals)-duration)>1:return reject('timer_reported_duration_conflict')
    groups=[]
    if intervals:
        for a,b in intervals:
            points=[(t,p) for t,p in zip(times,powers) if a<=t and t+1<=b]
            if not points:return reject('unobserved_active_timer_interval')
            groups.append(points)
    else:groups=[list(zip(times,powers))]
    active_times=[t for g in groups for t,p in g];active_powers=[p for g in groups for t,p in g]
    if not intervals and not finite(timeline_start):return reject('unsupported_elapsed_timeline_origin')
    timeline=intervals or [(timeline_start,timeline_start+elapsed_duration)]
    # Raw samples after a verified stop remain valid source evidence, excluded
    # from the active estimate rather than mistaken for a timing contradiction.
    if finite(timeline_start) and (times[0]<timeline_start-1 or times[-1]>timeline_start+elapsed_duration+1):return reject('power_outside_reported_elapsed_timeline')
    screens={name:distribution_screen(active_times,timeline,**parameters) for name,parameters in SCREEN_VARIANTS.items()}
    result.update(representativeness=screens['proposed'],screen_sensitivity=screens,
        distribution_time_basis='verified active timer intervals' if intervals else 'same-source elapsed timeline; pauses unverified')
    if known_omitted_effort:return reject('known_omitted_workout_effort')
    if not screens['proposed']['passes']:return reject(screens['proposed']['reason'])
    evidence=bins(active_times,active_powers)
    if not any(r['seconds']>=600 for r in evidence['continuous_runs']):return reject('no_accepted_600_second_observed_segment')
    if len(active_times)>elapsed_duration+1:return reject('observed_bins_exceed_elapsed_duration')
    fourths=[]
    for g in groups:fourths+=buffer_fourths([t for t,p in g],[p for t,p in g])
    if not fourths:return reject('no_complete_time_buffer')
    weighted=(math.fsum(fourths)/len(fourths))**.25
    literal=reference_np(times,powers)
    result.update(status='diagnostic_estimate',stress=100*duration/3600*(weighted/ftp)**2,
        weighted_power=weighted,buffer_count=len(fourths),literal_reference_weighted_power=literal,
        literal_reference_stress=100*duration/3600*(literal/ftp)**2 if literal is not None else None,
        observed_active_bins=len(active_times),observed_bins_per_reported_second=len(active_times)/duration,
        timer_boundaries_verified=verified,timer_problem=problem,
        timer_intervals=len(intervals or []),known_pause_samples_excluded=len(times)-len(active_times),reason=None)
    if evidence['timestamp_gaps']:result['limitations'].append('Gap intensity is unknown; sample fraction cannot establish representativeness')
    if not intervals:result['limitations'].append('No explicit timer events; moving duration/pause semantics are unverified')
    if len(active_times)>duration+1:result['limitations'].append('Recorded samples include time outside reported movement; sample count is not active-duration proof')
    result['limitations'].append('Batch mean weights samples equally; elapsed gaps can change emission timing without supplying missing watts')
    result['limitations'].append('Distribution screening excludes severe omissions but cannot establish unknown gap intensity or physiological accuracy')
    return result


def synthetic_cases():
    times=list(range(3600));powers=[100]*3600
    for start in range(600,3000,600):powers[start:start+90]=[350]*90
    rows=[]
    for label,removed in [('complete',set()),('missing_hard',set(range(600,690))),
                          ('missing_recovery',set(range(900,990))),('high_density_missing_hard',set(range(600,630))),
                          ('uniform_sparse',set(range(3600))-set(range(0,3600,10))),
                          ('clustered_sparse',set(range(600,3000))),
                          ('one_600_second_segment',set(range(600,3600))),
                          ('distributed_omissions',set(range(600,3600,5))),
                          ('same_fraction_concentrated_omissions',set(range(1200,1800))),
                          ('missing_start',set(range(600))),
                          ('missing_end',set(range(3000,3600))),
                          ('unknown_hard_omission',set(range(600,690)))]:
        t=[t for t in times if t not in removed];w=[powers[i] for i in t]
        omitted_hard=label in ('missing_hard','high_density_missing_hard','clustered_sparse')
        candidate=estimate(t,w,duration=3600,elapsed_duration=3600,ftp=200,known_omitted_effort=omitted_hard)
        rows.append(dict(case=label,times=t,powers=w,observed_fraction=len(t)/3600,estimate=candidate,
                         literal_np=reference_np(t,w),known_missing_hard_interval=omitted_hard))
    times=list(range(3660));powers=[100]*1800+[600]*60+[200]*1800
    stamp=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
    events=[dict(event='timer',event_type=kind,timestamp=stamp(t)) for t,kind in [(0,'start'),(1800,'stop_all'),(1860,'start'),(3660,'stop_all')]]
    summary=dict(start_time=stamp(0),timestamp=stamp(3660),total_timer_time=3600,total_elapsed_time=3660)
    candidate=estimate(times,powers,duration=3600,elapsed_duration=3660,ftp=200,events=events,summary=summary)
    rows.append(dict(case='verified_pause_with_nonzero_samples',times=times,powers=powers,
        observed_fraction=1.,estimate=candidate,literal_np=reference_np(times,powers),known_missing_hard_interval=False))
    complete=rows[0]['estimate']['stress']
    for row in rows:
        score=100*(row['literal_np']/200)**2 if row['literal_np'] is not None else None
        row['literal_reference_stress']=score
        row['relative_error_against_complete']=score/complete-1 if score is not None and row['case']!='verified_pause_with_nonzero_samples' else None
        if row['known_missing_hard_interval']:
            row['proposed_selection_exception']='Known workout structure establishes omitted intense effort; reject representativeness claim'
    return rows


def source_candidate(store,ride):
    power=ride['power'];ref=power.get('source')
    if not ref:return dict(method=METHOD,status='unavailable',stress=None,reason='no_unambiguous_trusted_power_source')
    if ref['format']=='Strava API stream':
        observation=next(o for o in store.strava_stream_evidence(ride['activity_id']) if o['source_id']==ref['stream_source_id'])
        times=observation['streams']['time']['data'];powers=observation['streams']['watts']['data']
        values=store.get_source(ref['summary_source_id'])['summary']['values']
        duration=values.get('moving_time');elapsed=values.get('elapsed_time');events=[];summary={};origin=0
        basis='same-source API moving_time / elapsed_time'
    else:
        native=store.get_source(ref['source_id']);times=[epoch(r['timestamp']) for r in native['records']];powers=[r['power'] for r in native['records']]
        summary=native['summary'];events=native['events'];duration=summary.get('total_timer_time');elapsed=summary.get('total_elapsed_time');origin=epoch(summary.get('start_time'))
        basis='same-source FIT total_timer_time / total_elapsed_time'
    result=estimate(times,powers,duration=duration,elapsed_duration=elapsed,ftp=ride['ftp']['value'],events=events,summary=summary,
                    duration_tolerance=1 if ref['format']=='FIT' else 0,timeline_start=origin)
    result.update(source=ref,duration_basis=basis)
    return result,times,powers


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('data-dir','before','after','blocked-cases','cases','reference','reference-source','private-output','aggregate-output'):
        p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args();before=json.loads(a.before.read_text());after=json.loads(a.after.read_text())
    old={r['activity_id']:r for r in before['rides']};new={r['activity_id']:r for r in after['rides']};assert old.keys()==new.keys()
    blocked=json.loads(a.blocked_cases.read_text())['blocked_best20_cases'];ids={c['ride']['activity_id'] for c in blocked}
    changed=[]
    for identity,r in new.items():
        prior=old[identity];assert prior['hr']==r['hr'] and prior['hr_candidates']==r['hr_candidates']
        if prior['power']['status'] in ('calculated','corrected_estimate','partial'):
            assert {k:v for k,v in prior['power'].items() if k!='eligibility'}=={k:v for k,v in r['power'].items() if k!='eligibility'}
            assert prior['selected']==r['selected']
        if prior['selected']!=r['selected']:assert identity in ids;changed.append(r)
    completed,_=read_reference(a.reference);reference={r['date']:r for r in completed}
    cases=json.loads(a.cases.read_text());examples=[];oracle_inputs=[];synthetic=synthetic_cases()
    for row in synthetic:
        oracle_inputs.append(dict(time=row['times'],watts=row['powers'],expected=row['literal_np']))
    with Store(a.data_dir) as store:
        store.connection.execute('PRAGMA query_only=ON');digest=table_digest(store.connection)
        for case in cases:
            matches=[r for r in new.values() if r['day']==case['day'] and (not case.get('activity_id') or r['activity_id']==case['activity_id']) and (not case.get('title') or r['title']==case['title'])]
            assert len(matches)==1;ride=matches[0];result=source_candidate(store,ride)
            if isinstance(result,tuple):
                candidate,times,powers=result
                if len(times)==len(powers) and all(finite(t) for t in times) and all(p is None or finite(p) for p in powers):
                    points=[(t,p) for t,p in zip(times,powers) if p is not None]
                    t=[t for t,p in points];w=[p for t,p in points]
                    oracle_inputs.append(dict(time=t,watts=w,expected=reference_np(t,w)))
            else:candidate=result
            examples.append(dict(role=case['role'],ride=ride,before_ride=old[ride['activity_id']],session_candidate=candidate,
                behavior=response(after['data']['days'],ride['day'],ride,reference)))
        assert digest==table_digest(store.connection)
    assert hashlib.sha256(a.reference_source.read_bytes()).hexdigest()==REFERENCE_SOURCE_SHA256, 'Pinned Elevate source integrity mismatch'
    source=a.reference_source.read_text();start=source.index('    const poweredWeightedWatts = [];');end=source.index('\n  }',start)
    body=source[start:end]
    # Execute the actual pinned reference function body independently from Python.
    script="const _={mean:a=>a.length?a.reduce((x,y)=>x+y,0)/a.length:NaN};const ActivityComputer={WEIGHTED_WATTS_TIME_BUFFER:30};const f=new Function('powerArray','timeArray',"+json.dumps(body)+");let s='';process.stdin.on('data',b=>s+=b);process.stdin.on('end',()=>process.stdout.write(JSON.stringify(JSON.parse(s).map(x=>f(x.watts,x.time)))));"
    actual=json.loads(subprocess.run(['node','-e',script],input=json.dumps(oracle_inputs),text=True,capture_output=True,check=True).stdout)
    for row,value in zip(oracle_inputs,actual):
        if row['expected'] is None:assert value is None
        else:assert math.isclose(value,row['expected'],rel_tol=1e-11)
    scenario=deepcopy(after['rides']);overrides={e['ride']['activity_id']:e['session_candidate'] for e in examples if e['session_candidate']['stress'] is not None}
    for ride in scenario:
        candidate=overrides.get(ride['activity_id'])
        if candidate and ride['power']['status'] not in ('calculated','corrected_estimate'):
            ride['selected']=dict(method='diagnostic_session_power',status='diagnostic_session_estimate',stress=candidate['stress'],scope=candidate['scope'])
    scenario_days=daily_series(scenario,after['data']['today'])
    windows={}
    for n in (7,42,90,365):
        cutoff=(date.fromisoformat(after['data']['today'])-timedelta(days=n-1)).isoformat()
        b=[d for d in before['data']['days'] if d['day']>=cutoff];c=[d for d in after['data']['days'] if d['day']>=cutoff];s=[d for d in scenario_days if d['day']>=cutoff]
        windows[str(n)]=dict(before_stress=math.fsum(d['stress'] for d in b),after_decoupling_stress=math.fsum(d['stress'] for d in c),diagnostic_scenario_stress=math.fsum(d['stress'] for d in s),
            changed_rides=sum(r['day']>=cutoff for r in changed))
    outcomes={}
    for status in ('calculated','corrected_estimate','partial'):
        cohort=[c for c in blocked if any(s['diagnostic_power'] and s['diagnostic_power']['status']==status for s in c['sources'])]
        outcomes[status]=dict(rides=len(cohort),before_selected=dict(Counter(old[c['ride']['activity_id']]['selected']['status'] for c in cohort)),
            after_selected=dict(Counter(new[c['ride']['activity_id']]['selected']['status'] for c in cohort)))
    aggregate=dict(production_version=after['data']['version'],power_source_policy=after['data']['power_source_policy'],
        before_coverage=before['data']['coverage'],after_coverage=after['data']['coverage'],selected_changes=len(changed),
        selection_transitions=dict(Counter(old[r['activity_id']]['selected']['status']+' -> '+r['selected']['status'] for r in changed)),
        diagnostic_117_outcomes=outcomes,all_prior_power_scores_preserved=True,all_hr_candidates_preserved=True,
        estimator_method=METHOD,estimator_production_enabled=False,reference_commit=REFERENCE_COMMIT,
        reference_source_sha256=hashlib.sha256(a.reference_source.read_bytes()).hexdigest(),reference_np_oracle_checks=len(actual),
        case_roles=dict(Counter(e['role'] for e in examples)),session_candidate_reasons=dict(Counter(e['session_candidate'].get('reason') or 'diagnostic_candidate' for e in examples)),
        representativeness_policy=REPRESENTATIVENESS,screen_parameters=SCREEN_VARIANTS,
        representativeness_sensitivity={name:dict(
            real_cases_evaluated=sum('screen_sensitivity' in e['session_candidate'] for e in examples),
            real_cases_passing=sum(e['session_candidate'].get('screen_sensitivity',{}).get(name,{}).get('passes',False) for e in examples),
            synthetic_cases_passing=sum(r['estimate'].get('screen_sensitivity',{}).get(name,{}).get('passes',False) for r in synthetic)) for name in SCREEN_VARIANTS},
        synthetic=[{k:r[k] for k in ('case','observed_fraction','relative_error_against_complete','known_missing_hard_interval')}|dict(
            reason=r['estimate'].get('reason'),distribution={k:v for k,v in r['estimate'].get('representativeness',{}).items() if k!='omissions'},
            sensitivity={name:s['passes'] for name,s in r['estimate'].get('screen_sensitivity',{}).items()}) for r in synthetic],
        windows=windows,diagnostic_database_and_cache_unchanged=True,
        endpoint_after_decoupling_minus_before={k:after['data']['days'][-1][k]-before['data']['days'][-1][k] for k in ('fitness','fatigue','form')},
        diagnostic_scenario_endpoint_minus_decoupling={k:scenario_days[-1][k]-after['data']['days'][-1][k] for k in ('fitness','fatigue','form')},
        diagnostic_scenario_selected_substitutions=sum(e['session_candidate']['stress'] is not None and e['ride']['power']['status'] not in ('calculated','corrected_estimate') for e in examples))
    private=dict(examples=examples,changed_rides=changed,blocked_outcomes=[dict(before=old[i],after=new[i]) for i in sorted(ids)],
        synthetic=synthetic,diagnostic_curve=scenario_days,windows=windows)
    for path,obj in ((a.aggregate_output,aggregate),(a.private_output,private)):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
    print(json.dumps(aggregate,indent=2,sort_keys=True))


if __name__=='__main__':main()
