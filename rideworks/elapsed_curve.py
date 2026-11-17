"""Source-backed elapsed power windows shared by both Power Curve views."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from time import perf_counter

from .history import presentation
from .errors import IntegrityError
from .performance import classification, file_power_present, _check_extractions
from .performance_view import months_before
from .power_curve import duration_grid, signature
from .training_state import timer_scope

METHOD = 'elapsed-power-v3'
GRID = 'seconds-1-30-plus-7-percent-endpoint-v1'
POLICY = 'elapsed-observed90-fit-boundary-v3'


def elapsed_signature(store, snapshot):
    return sha256(json.dumps([METHOD, GRID, POLICY, signature(store, snapshot)], separators=(',', ':')).encode()).hexdigest()


def parse_start(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def calculate(duration, samples, *, start, pauses=(), source=None, timer_problem=None, durations=None):
    """Calculate from (offset, watts) observations on a validated elapsed lattice."""
    result = dict(points=[], minimum=None, duration_seconds=duration, reason=None,
                  timer_problem=timer_problem)
    if (isinstance(duration, bool) or not isinstance(duration, (int, float)) or
            not math.isfinite(duration) or duration <= 0 or start is None):
        return result | dict(reason='elapsed_clock_unavailable')
    n = math.ceil(duration)
    values = [None] * n
    previous = -1
    for offset, power in samples:
        if (isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset)
                or offset < 0 or offset > duration or offset <= previous or
                (offset != duration and offset % 1)):
            return result | dict(reason='invalid_elapsed_timing')
        if power is not None and (type(power) is not int or power < 0):
            return result | dict(reason='invalid_power')
        previous = offset
        if offset < duration:
            values[int(offset)] = power
    flags = ['observed' if p is not None else 'unknown' for p in values]
    conflicts = []
    for a,b in pauses:
        if a < 0 or b > duration or a >= b or a % 1 or b % 1:
            conflicts.append('invalid_pause_boundaries'); continue
        a,b = int(a),int(b)
        if any(values[i] is not None and values[i] > 0 for i in range(a+1,b)):
            conflicts.append('power_inside_pause'); continue
        for i in range(a,b):
            flags[i] = 'pause'
    # Only one full missing second with immediate observed neighbors may be repaired.
    watts = [v if v is not None else 0 for v in values]
    for i in range(1,n-1):
        if (flags[i] == 'unknown' and flags[i-1] == flags[i+1] == 'observed'
                and i+1 <= duration):
            flags[i] = 'estimated'
            watts[i] = (values[i-1] + values[i+1]) / 2
    buckets = ('observed','pause','estimated','unknown')
    # Prefixes use full seconds. A fractional final bin is handled separately.
    prefixes = {k:[0] for k in (*buckets,'work','observed_work')}
    for i in range(n):
        weight = min(1, duration-i)
        for k in buckets:
            prefixes[k].append(prefixes[k][-1] + (weight if flags[i] == k else 0))
        prefixes['work'].append(prefixes['work'][-1] + (watts[i]*weight if flags[i] in ('observed','estimated') else 0))
        prefixes['observed_work'].append(prefixes['observed_work'][-1] + (watts[i]*weight if flags[i] == 'observed' else 0))

    def window(a,b):
        return {k:prefixes[k][b]-prefixes[k][a] for k in prefixes}

    def point(d, a, evidence):
        seconds = evidence['observed'] + evidence['estimated'] + evidence['unknown']
        coverage = evidence['observed']/seconds if seconds else 0
        work = evidence['work']
        end = duration if d == duration and a == 0 else a+d
        return dict(duration_seconds=d, average_watts=work/d, rounded_watts=math.floor(work/d+0.5),
                    sum_watts=work, observed_watt_seconds=evidence['observed_work'],
                    observed_seconds=evidence['observed'], pause_seconds=evidence['pause'],
                    estimated_seconds=evidence['estimated'], unknown_seconds=evidence['unknown'],
                    coverage=coverage, start_offset=a, end_exclusive_offset=end,
                    start_timestamp=(start+timedelta(seconds=a)).isoformat(),
                    end_exclusive_timestamp=(start+timedelta(seconds=end)).isoformat(),
                    source=source or {}, timer_problem=timer_problem, timer_conflicts=conflicts,
                    result_kind='elapsed_power')

    anchors = sorted(set(list(duration_grid(math.floor(duration)) if durations is None else durations) + [duration]))
    result['anchors'] = anchors
    full = window(0,n)
    result['endpoint_coverage'] = (full['observed']/(duration-full['pause']) if duration>full['pause'] else 0)
    for d in anchors:
        if d <= 0 or d > duration:
            continue
        if d == duration:
            candidates = [(0,full)]
        elif float(d).is_integer():
            d = int(d)
            observed_prefix, pause_prefix, work_prefix = (prefixes[k] for k in ('observed','pause','work'))
            best_start, best_work = None, None
            for a in range(math.floor(duration)-d+1):
                b=a+d
                observed=observed_prefix[b]-observed_prefix[a]
                nonpause=d-(pause_prefix[b]-pause_prefix[a])
                if observed <= 0 or nonpause <= 0 or observed*100 < 90*nonpause:
                    continue
                work=work_prefix[b]-work_prefix[a]
                if best_work is None or work > best_work:
                    best_start,best_work=a,work
            candidates = [(best_start,window(best_start,best_start+d))] if best_start is not None else []
        else:
            continue
        best = None
        for a,ev in candidates:
            nonpause = d-ev['pause']
            if ev['observed'] <= 0 or nonpause <= 0 or ev['observed']*100 < 90*nonpause:
                continue
            if best is None or ev['work'] > best[1]['work']:
                best = (a,ev)
        if best:
            result['points'].append(point(d,*best))
    if not result['points']:
        result['reason'] = 'insufficient_recorded_power'
    return result


def api_candidate(store, snapshot):
    summaries = [e for e in snapshot['sources'] if e['source']['kind']=='strava_api' and e['source']['is_current']]
    observations = [e for e in store.strava_stream_evidence(snapshot['activity']['activity_id']) if e['is_current']]
    if len(summaries)!=1 or len(observations)!=1:
        return dict(points=[],minimum=None,reason='api_power_stream_unavailable')
    summary, observed = summaries[0], observations[0]
    if not observed['summary_compatible'] or observed['current_summary_source_id'] != summary['source']['source_id']:
        return dict(points=[],minimum=None,reason='api_stream_summary_not_current')
    values = summary['summary']['values']
    if values.get('device_watts') is not True:
        return dict(points=[],minimum=None,reason='api_device_watts_not_confirmed')
    start = parse_start(values.get('start_date'))
    stream_start = parse_start(observed.get('start_date'))
    if start is None or stream_start is None or start != stream_start:
        return dict(points=[],minimum=None,reason='elapsed_clock_unavailable')
    time, watts = (observed['streams'].get(k) for k in ('time','watts'))
    if time is None or watts is None:
        return dict(points=[],minimum=None,reason='api_power_stream_unavailable')
    if any(s['resolution']!='high' or s['original_size']!=len(s['data']) for s in (time,watts)):
        return dict(points=[],minimum=None,reason='api_stream_not_full_length')
    if len(time['data'])!=len(watts['data']) or any(time[k]!=watts[k] for k in ('original_size','resolution','series_type')):
        return dict(points=[],minimum=None,reason='api_stream_pairing_ambiguous')
    ref=dict(source_id=observed['source_id'], summary_source_id=observed['summary_source_id'],
             current_summary_source_id=summary['source']['source_id'], observation_sha256=observed['observation_sha256'],
             mapping_version=observed['mapping_version'], content_format='Strava API stream',
             origin='elapsed recorded power', timer_quality='not_available')
    return calculate(values.get('elapsed_time'),zip(time['data'],watts['data']),start=start,source=ref)


def native_candidate(store, metadata):
    extraction=metadata['extraction']; source=metadata['source']
    if not extraction['power_present']:
        return dict(points=[],minimum=None,reason='no_native_power')
    count=store.connection.execute('SELECT COUNT(*),COUNT(power) FROM records WHERE extraction_id=?',(extraction['extraction_id'],)).fetchone()
    if tuple(count)!=(extraction['record_count'],extraction['power_present']):
        raise IntegrityError('Elapsed curve native counts disagree with extraction')
    native=store.get_source(source['source_id']); summary=native['summary']; start=parse_start(summary.get('start_time'))
    if start is None:
        return dict(points=[],minimum=None,reason='elapsed_clock_unavailable')
    samples=[]
    for r in native['records']:
        stamp=parse_start(r['timestamp'])
        if stamp is None:
            return dict(points=[],minimum=None,reason='invalid_elapsed_timing')
        samples.append(((stamp-start).total_seconds(),r['power']))
    intervals,problem,verified=timer_scope(native['events'],summary)
    pauses=[(a-start.timestamp(),b-start.timestamp()) for (_,a),(b,_) in zip(intervals,intervals[1:])] if verified else []
    ref=dict(source_id=source['source_id'],extraction_id=extraction['extraction_id'],content_format=source['content_format'],
             origin='elapsed recorded power',timer_quality='session_verified' if verified else 'unverified')
    duration=summary.get('total_elapsed_time')
    if source['content_format'].upper()!='FIT':
        return calculate(duration,samples,start=start,pauses=pauses,source=ref,timer_problem=problem)
    if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:
        return dict(points=[],minimum=None,reason='elapsed_clock_unavailable')
    # Validate every record before using observations to establish either boundary.
    previous=-1; observed=[]
    for offset,power in samples:
        if (not math.isfinite(offset) or offset<0 or offset>duration or offset<=previous or
                (offset!=duration and offset%1)):
            return dict(points=[],minimum=None,reason='invalid_elapsed_timing')
        if power is not None and (type(power) is not int or power<0):
            return dict(points=[],minimum=None,reason='invalid_power')
        previous=offset
        if power is not None and offset<duration:observed.append(offset)
    if not observed:return dict(points=[],minimum=None,reason='insufficient_recorded_power')
    first,last=observed[0],min(duration,observed[-1]+1)
    first_verified=verified and abs(intervals[0][0]-start.timestamp())<1
    last_verified=verified and abs(intervals[-1][1]-(start.timestamp()+duration))<1
    lower=0 if first_verified else first
    upper=duration if last_verified else last
    clipped=lower>0 or upper<duration
    if not clipped:
        return calculate(duration,samples,start=start,pauses=pauses,source=ref,timer_problem=problem)
    scope=upper-lower
    ref.update(scope_reason='fit_elapsed_bounds_not_supported',reported_elapsed_seconds=duration,
               supported_start_offset=lower,supported_end_offset=upper)
    scoped_samples=[(offset-lower,power) for offset,power in samples if lower<=offset<=upper]
    scoped_pauses=[(max(a,lower)-lower,min(b,upper)-lower) for a,b in pauses if max(a,lower)<min(b,upper)]
    grid=duration_grid(math.floor(scope))
    result=calculate(scope,scoped_samples,start=start+timedelta(seconds=lower),pauses=scoped_pauses,
                     source=ref,timer_problem=problem,durations=grid)
    # A clipped boundary is not a full-ride endpoint, but may coincide with the common grid.
    common=set(grid)
    result['points']=[p for p in result['points'] if p['duration_seconds'] in common]
    result['anchors']=[d for d in result.get('anchors',[]) if d in common]
    for point in result['points']:
        point['start_offset']+=lower;point['end_exclusive_offset']+=lower
    result.update(duration_seconds=None,grid_duration=scope,scope_reason=ref['scope_reason'],endpoint_coverage=None)
    return result


def evaluate(store,snapshot):
    identity=snapshot['activity']['activity_id']; cohort=classification(snapshot)
    result=dict(activity_id=identity,method=METHOD,grid=GRID,policy=POLICY,classification=cohort,points=[],minimum=None,reason=None)
    if cohort['activity_type']!='Virtual Ride':
        return result | dict(reason='non_virtual_or_ambiguous_classification')
    if not file_power_present(snapshot):
        return result | api_candidate(store,snapshot)
    candidates=[native_candidate(store,e) for e in snapshot['sources'] if e['source']['kind'] not in ('strava_export','strava_api')]
    if len(candidates)==1:
        for key in ('duration_seconds','grid_duration','scope_reason','anchors','endpoint_coverage'):
            if key in candidates[0]:result[key]=candidates[0][key]
    by_duration={}
    for c in candidates:
        for p in c['points']:
            by_duration.setdefault(p['duration_seconds'],[]).append(p)
    result['ambiguous_durations']=[d for d,ps in by_duration.items() if len(ps)>1]
    result['points']=[ps[0] for d,ps in sorted(by_duration.items()) if len(ps)==1]
    if not result['points']:
        result['reason']='competing_native_sources' if by_duration else (candidates[0]['reason'] if len(candidates)==1 else 'no_supported_native_window')
    return result


def rebuild(store, *, force=False):
    started=perf_counter(); counts=Counter(); rows=[]; calculated_at=datetime.now(timezone.utc).isoformat()
    _check_extractions(store)
    ids=[s['activity']['activity_id'] for s in store.activity_history()]
    for identity in ids:
        with store._transaction():
            snapshot=store.activity_history(identity)[0]; sig=elapsed_signature(store,snapshot)
            row=store.connection.execute('SELECT input_signature FROM elapsed_power_curve_profiles WHERE activity_id=? AND method=?',(identity,METHOD)).fetchone()
            if not force and row and row[0]==sig:
                counts['reused']+=1; continue
            profile=evaluate(store,snapshot)
            rows.append((identity,sig,json.dumps(profile,sort_keys=True,allow_nan=False)))
    with store._transaction(write=True):
        current={s['activity']['activity_id']:s for s in store.activity_history()} if rows else {}
        for identity,sig,payload in rows:
            if identity not in current or elapsed_signature(store,current[identity])!=sig:
                counts['changed_during_build']+=1; continue
            store.connection.execute('''INSERT INTO elapsed_power_curve_profiles VALUES(?,?,?,?,?)
                ON CONFLICT(activity_id) DO UPDATE SET method=excluded.method,input_signature=excluded.input_signature,
                calculated_at=excluded.calculated_at,result_json=excluded.result_json''',(identity,METHOD,sig,calculated_at,payload))
            counts['computed']+=1
    return dict(status='incomplete' if counts['changed_during_build'] else 'completed',computed=counts['computed'],reused=counts['reused'],changed_during_build=counts['changed_during_build'],elapsed_seconds=round(perf_counter()-started,3))


def envelope(profiles, *, start, end, exclude=None):
    """Select standard common-grid elapsed results for a half-open period."""
    winners={}; selected=[]; anchors=set()
    for p in profiles:
        a=p['activity']
        if a['activity_id']==exclude or not a['absolute_time']:continue
        stamp=datetime.fromisoformat(a['start_time']).astimezone(timezone.utc)
        if stamp>=end or start is not None and stamp<start:continue
        selected.append((stamp,a['activity_id'],p))
    for _,_,p in sorted(selected,key=lambda x:x[:2]):
        common=set(duration_grid(math.floor(p.get('grid_duration') or p.get('duration_seconds') or 0)))
        anchors.update(common)
        for pt in p['points']:
            d=pt['duration_seconds']
            if d not in common:continue
            if d not in winners or pt['average_watts']>winners[d]['average_watts']:
                winners[d]=pt | dict(activity=p['activity'])
    return dict(points=[p for _,p in sorted(winners.items())],anchors=sorted(anchors),count=len(selected),start=start.isoformat() if start else None,end_exclusive=end.isoformat())


def comparison(store,activity_id=None, *, as_of=None, zone=timezone.utc):
    with store._transaction():
        snapshots=store.activity_history(); saved={r['activity_id']:r for r in store.connection.execute('SELECT * FROM elapsed_power_curve_profiles WHERE method=?',(METHOD,))}
        profiles=[];results={};pending=0
        for s in snapshots:
            identity=s['activity']['activity_id']; row=saved.get(identity)
            if row is None or row['input_signature']!=elapsed_signature(store,s):
                pending+=1;continue
            p=json.loads(row['result_json'])
            if (p.get('method'),p.get('grid'),p.get('policy'))!=(METHOD,GRID,POLICY):
                pending+=1;continue
            a=presentation(s);p['activity']={k:a[k] for k in ('activity_id','title','start_time','absolute_time','date_day')}
            results[identity]=p
            if p['points']:profiles.append(p)
        if activity_id is None:
            end=as_of or datetime.now(timezone.utc)
            if end.tzinfo is None:raise ValueError('Power Curve as-of timezone is required')
            local=end.astimezone(zone)
            year=local.replace(month=1,day=1,hour=0,minute=0,second=0,microsecond=0)
            data=dict(method=METHOD,grid=GRID,pending=pending,mode='performance',series={},as_of=end.isoformat(),calendar_timezone=str(zone))
            for key,start,stop in [('six',end-timedelta(days=42),end),('previous',end-timedelta(days=84),end-timedelta(days=42)),('two_year',months_before(local,24),end),('five_year',months_before(local,60),end),('ytd',year,end),('last_year',year.replace(year=year.year-1),year),('all',None,end)]:
                data['series'][key]=envelope(profiles,start=start,end=stop)
            return data
        result=results.get(activity_id);current=next((presentation(s) for s in snapshots if s['activity']['activity_id']==activity_id),None)
        points=[p | dict(activity=result['activity']) for p in result['points']] if result else []
        data=dict(method=METHOD,grid=GRID,pending=pending,mode='activity',series={},current_reason=result['reason'] if result else 'profile_update_required',ambiguous_durations=result.get('ambiguous_durations',[]) if result else [],minimum=None)
        if result:
            data['elapsed_duration']=result.get('duration_seconds')
            data['endpoint_coverage']=result.get('endpoint_coverage')
            data['scope_reason']=result.get('scope_reason')
        data['series']['ride']=dict(points=points,anchors=result.get('anchors',[]) if result else [],count=int(bool(points)),start=None,end_exclusive=None)
        if not current or not current['absolute_time']:
            data['baseline_reason']='activity_absolute_start_unavailable'
            for key in ('six','year','two_year','five_year','all'):data['series'][key]=dict(points=[],count=0,start=None,end_exclusive=None)
            return data
        end=datetime.fromisoformat(current['start_time']).astimezone(timezone.utc)
        for key,start in [('six',end-timedelta(days=42)),('year',months_before(end,12)),('two_year',months_before(end,24)),('five_year',months_before(end,60)),('all',None)]:
            data['series'][key]=envelope(profiles,start=start,end=end,exclude=activity_id)
        return data
