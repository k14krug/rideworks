#!/usr/bin/env python3
"""Read-only P4-02 outdoor HR diagnostics; alternatives are NOT production policy.

Private ride-level output and aggregate-only publication are separate. No network,
CSV-duration inference, vendor-score import, cache write or original mutation.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import inspect
import json
import math
from pathlib import Path
import sqlite3
import sys
from types import FunctionType
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.store import Store
from rideworks.history import presentation
from rideworks.training_state import (DEFAULT_HR, calculate_ride, daily_series, epoch, finite, ftp_history, ftp_on,
    hr_stream, hr_summary, hrss, source_ref, timer_scope)

VERSION='p4-02-outdoor-diagnostics-v1'
ALTERNATIVES=('summary_fallback','partial_hr','coverage_0.99','coverage_0.98','coverage_0.95','coverage_0.9','symmetric_1_percent')


def observed_segments(times, hrs, events, summary, starts=()):
    """Diagnostic observed-interval HR; no claim that elapsed bins equal moving time."""
    result=dict(stress=None, scope='partial recorded HR intervals; active/full-ride scope unverified',
                represented_seconds=0,excluded_short_seconds=0,unrepresented_recording_seconds=None,
                known_uncovered_timer_seconds=None,segments=[],timer_problem=None)
    if not times or len(times)!=len(hrs) or any(not finite(t) for t in times) or any(b<a for a,b in zip(times,times[1:])):
        return result|dict(reason='invalid_timing')
    counts=Counter(times)
    result['duplicate_timestamp_records_excluded']=sum(counts[t]>1 for t in times)
    intervals,problem,verified=timer_scope(events,summary);result['timer_problem']=problem
    if any(e['event']=='timer' for e in events) and intervals is None:return result|dict(reason='unresolved_timer')
    def active(t):return next((i for i,(a,b) in enumerate(intervals) if a<=t<b),None) if intervals else 0
    pieces=[];seconds=weighted=0.;breaks=set(starts)
    def finish():
        nonlocal seconds,weighted
        if seconds:pieces.append(dict(seconds=seconds,mean_hr=weighted/seconds))
        seconds=weighted=0.
    for i,(t,h) in enumerate(zip(times,hrs)):
        group=active(t);valid=counts[t]==1 and finite(h) and 0<h<255 and group is not None
        paired=i+1<len(times) and active(times[i+1])==group and i+1 not in breaks
        if paired and valid and counts[times[i+1]]==1 and finite(hrs[i+1]) and 0<hrs[i+1]<255 and 0<times[i+1]-t<=15:
            step=times[i+1]-t;seconds+=step;weighted+=step*(h+hrs[i+1])/2
        else:
            if valid and (not intervals or t+1<=intervals[group][1]):seconds+=1;weighted+=h
            finish()
    finish()
    selected=[p for p in pieces if p['seconds']>=600]
    for p in selected:p['stress']=hrss(p['mean_hr'],p['seconds'],DEFAULT_HR)
    usable=[p for p in selected if p['stress'] is not None]
    result.update(segments=usable,represented_seconds=math.fsum(p['seconds'] for p in usable),
        excluded_short_seconds=math.fsum(p['seconds'] for p in pieces if p['seconds']<600),
        unrepresented_recording_seconds=max(0,times[-1]-times[0]+1-math.fsum(p['seconds'] for p in usable)),
        known_uncovered_timer_seconds=max(0,math.fsum(b-a for a,b in intervals)-math.fsum(p['seconds'] for p in usable)) if verified else None,
        stress=math.fsum(p['stress'] for p in usable) if usable else None,
        reason=None if usable else 'no_valid_600_second_recorded_hr_interval',
        timer_boundaries_verified=verified,possible_false_completeness=True)
    return result


def screens():
    result={}
    for fraction in (.99,.98,.95,.90):
        fn=FunctionType(hr_stream.__code__,hr_stream.__globals__|dict(HR_COVERAGE=fraction),hr_stream.__name__,hr_stream.__defaults__)
        fn.__kwdefaults__=hr_stream.__kwdefaults__
        result[f'coverage_{fraction}']=fn
    # Controlled diagnostic copy: the only change is permitting 1% overcoverage.
    source=inspect.getsource(hr_stream)
    marker='coverage > 1.000001'
    if source.count(marker)!=1:raise ValueError('HR screen changed; inspect before rerunning sensitivity')
    namespace=dict(hr_stream.__globals__)
    exec(compile(source.replace(marker,'coverage > 1.01'),'<diagnostic-asymmetric-coverage>','exec'),namespace)
    result['symmetric_1_percent']=namespace['hr_stream']
    return result


def file_evidence(native, screeners):
    summary=native['summary'];records=native['records'];ref=source_ref(native)
    times=[epoch(r['timestamp']) for r in records];hrs=[r['heart_rate'] for r in records]
    laps=native.get('xml_context',{}).get('lap_summaries',[])
    duration=summary.get('total_timer_time');basis='FIT total_timer_time' if ref['format']=='FIT' else 'active duration unavailable'
    mean=summary.get('avg_heart_rate')
    if len(laps)==1:
        if duration is None:duration=laps[0].get('total_time_seconds');basis='TCX single-lap TotalTimeSeconds (active meaning not independently verified)'
        if mean is None:mean=laps[0].get('avg_heart_rate')
    intervals,problem,verified=timer_scope(native['events'],summary)
    known=[t for t in times if t is not None]
    breaks=native.get('xml_context',{}).get('segment_start_record_indexes',[])
    args=dict(settings=DEFAULT_HR,source=ref,events=native['events'],summary=summary,duration=duration,segment_starts=breaks)
    alternatives={name:fn(times,hrs,**args) for name,fn in screeners.items()}
    valid_duration=finite(duration) and duration>0 and (not finite(summary.get('total_elapsed_time')) or duration<=summary['total_elapsed_time'])
    summary_test=hr_summary(mean,duration if valid_duration else None,settings=DEFAULT_HR,source=ref)
    summary_test.update(duration_basis=basis,stream_present=any(h is not None for h in hrs),
                        timer_boundaries_verified=verified,possible_false_completeness=not verified,
                        mean_active_scope_independently_verified=False)
    return dict(format=ref['format'],source_id=ref['source_id'],extraction_id=ref['extraction_id'],
        hr_stream_present=any(h is not None for h in hrs),hr_samples=sum(h is not None for h in hrs),
        hr_summary_present=mean is not None or any(l.get('avg_heart_rate') is not None for l in laps),summary_mean_hr=mean,
        lap_hr_summary_count=sum(l.get('avg_heart_rate') is not None for l in laps),
        records=len(records),valid_absolute_timestamps=sum(t is not None for t in times),
        ordered_unique_timestamps=bool(times) and len(known)==len(times) and all(b>a for a,b in zip(times,times[1:])),
        recorded_span_seconds=known[-1]-known[0]+1 if known else None,
        missing_absolute_timestamps=len(times)-len(known),
        duplicate_timestamp_records=len(known)-len(set(known)),
        backward_timestamp_pairs=sum(b<a for a,b in zip(known,known[1:])),
        gap_seconds_over_15=math.fsum(max(0,b-a-1) for a,b in zip(known,known[1:]) if b-a>15),
        gaps_over_15=sum(b-a>15 for a,b in zip(known,known[1:])),
        timer_events=sum(e['event']=='timer' for e in native['events']),timer_problem=problem,
        timer_boundaries_verified=verified,source_active_duration=duration,source_duration_basis=basis,
        source_elapsed_seconds=summary.get('total_elapsed_time'),summary_fallback=summary_test,
        partial_hr=observed_segments(times,hrs,native['events'],summary,breaks)|dict(source=ref),sensitivities=alternatives)


def diagnose(store, as_of):
    zone=ZoneInfo('America/Los_Angeles');history,_=ftp_history();screeners=screens();rides=[];all_model_rides=[];cache_checks=0
    with store._transaction():
        for snapshot in store.activity_history():
            row=presentation(snapshot)
            if row['activity_type'] not in ('Ride','Virtual Ride') or not row['start_time']:continue
            stamp=datetime.fromisoformat(row['start_time']);day=stamp.astimezone(zone).date() if stamp.tzinfo else stamp.date()
            if day>as_of:continue
            if row['activity_type']=='Virtual Ride':
                saved=store.connection.execute('SELECT result_json FROM training_stress_cache WHERE activity_id=?',(row['activity_id'],)).fetchone()
                if not saved:raise ValueError('Missing baseline cache; run private-copy production verification first')
                all_model_rides.append(json.loads(saved[0])|dict(day=str(day)))
                continue
            baseline=calculate_ride(store,snapshot,row,ftp_on(history,str(day),row['absolute_time']),dict(DEFAULT_HR))
            saved=store.connection.execute('SELECT result_json FROM training_stress_cache WHERE activity_id=?',(row['activity_id'],)).fetchone()
            if not saved or json.loads(saved[0])!=baseline:
                raise ValueError('Baseline cache missing or changed; verify private copy before diagnostics')
            cache_checks+=1
            evidence=[];source_types=[]
            for metadata in snapshot['sources']:
                source=metadata['source'];source_types.append(source['content_format'])
                if source['kind'] not in ('strava_api','strava_export'):
                    evidence.append(file_evidence(store.get_source(source['source_id']),screeners))
                elif source['kind']=='strava_api' and source['is_current']:
                    values=metadata['summary']['values'];duration=values.get('moving_time');mean=values.get('average_heartrate')
                    current=[s for s in store.strava_stream_evidence(row['activity_id']) if s['is_current'] and s['summary_source_id']==source['source_id']]
                    stream_hr=any('heartrate' in s['streams'] for s in current)
                    valid=values.get('has_heartrate') is True and finite(duration) and finite(values.get('elapsed_time')) and 0<duration<=values['elapsed_time']
                    summary_test=hr_summary(mean,duration if valid else None,settings=DEFAULT_HR,source=dict(format='Strava API summary',source_id=source['source_id']))
                    summary_test.update(duration_basis='Strava API moving_time seconds',stream_present=stream_hr,
                        timer_boundaries_verified=False,possible_false_completeness=True,
                        mean_active_scope_independently_verified=False)
                    sensitivity={};partials=[]
                    for observation in current:
                        streams=observation['streams']
                        if 'time' not in streams or 'heartrate' not in streams:continue
                        if any(s['resolution']!='high' or s['original_size']!=len(s['data']) for s in (streams['time'],streams['heartrate'])):continue
                        t,h=streams['time']['data'],streams['heartrate']['data'];kwargs=dict(settings=DEFAULT_HR,source=summary_test['source'],duration=duration)
                        sensitivity={name:fn(t,h,**kwargs) for name,fn in screeners.items()}
                        partials.append(observed_segments(t,h,[],{})|dict(source=dict(format='Strava API stream',source_id=observation['source_id'],summary_source_id=source['source_id'])))
                    api_times=[o['streams'].get('time',{}).get('data',[]) for o in current]
                    evidence.append(dict(format='Strava API',source_id=source['source_id'],hr_stream_present=stream_hr,
                        hr_summary_present=mean is not None,source_active_duration=duration,
                        valid_relative_timestamps=sum(sum(finite(t) for t in times) for times in api_times),
                        ordered_unique_timestamps=any(times and all(finite(t) for t in times) and all(b>a for a,b in zip(times,times[1:])) for times in api_times),
                        gaps_over_15=sum(sum(b-a>15 for a,b in zip(times,times[1:]) if finite(a) and finite(b)) for times in api_times),
                        source_elapsed_seconds=values.get('elapsed_time'),source_duration_basis='Strava API moving_time seconds',summary_fallback=summary_test,
                        api_stream_observations=[dict(hr_samples=sum(h is not None for h in o['streams'].get('heartrate',{}).get('data',[])),
                            time_samples=len(o['streams'].get('time',{}).get('data',[])),
                            full_high_resolution=all(v['resolution']=='high' and v['original_size']==len(v['data']) for v in o['streams'].values())) for o in current],
                        timer_boundaries_verified=False,timer_events=0,sensitivities=sensitivity,
                        partial_hr=next((p for p in partials if p['stress'] is not None),{})))
                elif source['kind']=='strava_export':
                    # Evidence presence only: explicitly do NOT pair unknown-unit CSV durations.
                    summary=metadata['summary']
                    evidence.append(dict(format='CSV',source_id=source['source_id'],
                        hr_summary_present=any(f['column']=='Average Heart Rate' and f['status']=='present' for f in summary.get('fields',[])),
                        hr_stream_present=False,source_active_duration=None,timer_events=0,timer_boundaries_verified=False))
            rejection=sorted({c.get('reason') or 'usable' for c in baseline['hr_candidates']})
            if baseline['selected']['stress'] is not None:reason='scored'
            elif not any(e.get('hr_stream_present') or e.get('hr_summary_present') for e in evidence):reason='no_hr_evidence'
            else:reason=' + '.join(rejection) if rejection else 'no_supported_hr_duration_pair'
            options={}
            for name in ALTERNATIVES:
                candidates=[(e.get(name,{}) if name in ('summary_fallback','partial_hr') else e.get('sensitivities',{}).get(name,{})) for e in evidence]
                available=[c for c in candidates if c.get('stress') is not None]
                # Any-source experimental upper screen, with ambiguity explicitly reported.
                options[name]=dict(qualifying_sources=len(available),candidate=available[0] if len(available)==1 else None,
                    recovered=baseline['selected']['stress'] is None and len(available)==1,
                    ambiguous=len(available)>1)
            ride=dict(activity_id=row['activity_id'],day=str(day),year=day.year,title=row['title'],
                source_types=sorted(set(source_types)),source_signature='+'.join(sorted(set(source_types))),
                baseline=baseline,evidence=evidence,rejection=reason,alternatives=options)
            rides.append(ride);all_model_rides.append(baseline|dict(day=str(day)))
    days=daily_series(all_model_rides,str(as_of));by_day={d['day']:d for d in days}
    for r in rides:r['plotted_day']={k:by_day[r['day']][k] for k in ('day','stress','fitness','fatigue','form','unscored','contributors')} if r['day'] in by_day else None
    def group(items):
        evidence_counts={key:sum(any(e.get(key) for e in r['evidence']) for r in items) for key in
            ('hr_stream_present','hr_summary_present','ordered_unique_timestamps','valid_absolute_timestamps','timer_events','timer_boundaries_verified','source_active_duration','duplicate_timestamp_records','backward_timestamp_pairs','missing_absolute_timestamps')}
        evidence_counts['hr_any']=sum(any(e.get('hr_stream_present') or e.get('hr_summary_present') for e in r['evidence']) for r in items)
        return dict(rides=len(items),scored=sum(r['baseline']['selected']['stress'] is not None for r in items),
                    ride_level_rejections=dict(Counter(r['rejection'] for r in items)),evidence_presence=evidence_counts,
                    alternatives={name:dict(recovered_rides=sum(r['alternatives'][name]['recovered'] for r in items),
                        ambiguous_rides=sum(r['alternatives'][name]['ambiguous'] for r in items),
                        available_rides=sum(r['alternatives'][name]['candidate'] is not None for r in items),
                        recovered_represented_seconds=math.fsum((r['alternatives'][name]['candidate'] or {}).get('represented_seconds',0) for r in items if r['alternatives'][name]['recovered']),
                        recovered_source_duration_seconds=math.fsum((r['alternatives'][name]['candidate'] or {}).get('active_seconds') or 0 for r in items if r['alternatives'][name]['recovered']),
                        recovered_unknown_timer_scope_rides=sum((r['alternatives'][name]['candidate'] or {}).get('known_uncovered_timer_seconds') is None for r in items if r['alternatives'][name]['recovered']),
                        recovered_known_uncovered_timer_seconds=math.fsum((r['alternatives'][name]['candidate'] or {}).get('known_uncovered_timer_seconds') or 0 for r in items if r['alternatives'][name]['recovered']),
                        recovered_unrepresented_recording_seconds=math.fsum((r['alternatives'][name]['candidate'] or {}).get('unrepresented_recording_seconds') or 0 for r in items if r['alternatives'][name]['recovered']))
                        for name in ALTERNATIVES})
    impacts={}
    for name in ALTERNATIVES:
        recovered=[r for r in rides if r['alternatives'][name]['recovered']]
        def delta(tau, prior=False):
            return math.fsum(r['alternatives'][name]['candidate']['stress']*(-math.expm1(-1/tau))*math.exp(-age/tau)
                for r in recovered if (age:=(as_of-date.fromisoformat(r['day'])).days-int(prior))>=0)
        impacts[name]=dict(recovered_rides=len(recovered),fitness_delta=delta(42),fatigue_delta=delta(7),
            start_of_day_form_delta=delta(42,True)-delta(7,True),
            interpretation='Diagnostic additive effect of newly recovered estimates only; existing scores unchanged, no vendor calibration')
    report=dict(version=VERSION,as_of=str(as_of),outdoor=group(rides),outdoor_baseline_cache_results_unchanged=cache_checks,
        by_source_type={kind:group([r for r in rides if kind in r['source_types']]) for kind in sorted({kind for r in rides for kind in r['source_types']})},
        current_model_diagnostic_effect=impacts,
        by_year={str(y):group([r for r in rides if r['year']==y]) for y in sorted({r['year'] for r in rides})},
        by_source_signature={kind:group([r for r in rides if r['source_signature']==kind]) for kind in sorted({r['source_signature'] for r in rides})},
        by_year_and_source={str(y):{kind:group([r for r in rides if r['year']==y and r['source_signature']==kind]) for kind in sorted({r['source_signature'] for r in rides if r['year']==y})} for y in sorted({r['year'] for r in rides})},
        recent={str(n):group([r for r in rides if as_of-timedelta(days=n-1)<=date.fromisoformat(r['day'])<=as_of]) for n in (42,90)},
        method_notes=['Ride-level rejection sets are disjoint categories; candidate counts are not summed as rides.',
            'Alternative recoveries overlap and must not be added.',
            'Source-type cohorts overlap on multi-source rides; source-signature cohorts are disjoint.',
            'HR summary presence includes multi-lap summaries even when no supported single active-duration pair exists.',
            'Summary fallback remains a diagnostic estimate; mean active-time basis and pause treatment are not independently verified.',
            'Zero summed known uncovered seconds does not mean none missing: consult unknown-timer-scope ride counts; summary alternatives do not establish observed represented seconds.',
            'Partial HR uses recorded >=600s segments with <=15s adjacent measured endpoints; elapsed coverage is not moving time.',
            'Partial HR excludes all records at duplicate timestamps and splits there; it never picks a duplicate value, reorders backward records or claims full coverage.',
            'Coverage sensitivities retain the 15s interval cap and existing overcoverage rule.',
            'Symmetric screen changes only overcoverage ceiling to 101%; it does not prove which recording time was active.',
            'No CSV duration values, vendor scores, API crawl or production eligibility changes.'])
    return report,rides


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True);p.add_argument('--aggregate-output',type=Path,required=True)
    p.add_argument('--private-output',type=Path,required=True);a=p.parse_args()
    db=a.data_dir/'rideworks.sqlite3';before=hashlib.sha256(db.read_bytes()).hexdigest()
    store=Store.__new__(Store);store.data_dir=a.data_dir.resolve()
    store.connection=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True);store.connection.row_factory=sqlite3.Row
    store.connection.execute('PRAGMA query_only=ON')
    try:report,private=diagnose(store,a.as_of)
    finally:store.close()
    after=hashlib.sha256(db.read_bytes()).hexdigest();assert before==after,'Private database changed during diagnostics'
    report['private_database_byte_preserved']=True
    for path,value in [(a.aggregate_output,report),(a.private_output,private)]:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(outdoor=report['outdoor'],recent=report['recent']),indent=2))

if __name__=='__main__':main()
