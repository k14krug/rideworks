"""Exact observed-window MMP profiles; replaceable cache, no source rewriting."""
from bisect import bisect_left
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from time import perf_counter

from .analysis import best_20_minute_power
from .errors import IntegrityError
from .history import presentation
from .performance import classification, file_power_present, input_signature, _check_extractions
from .performance_view import months_before
from .training_state import timer_scope

METHOD = 'observed-mmp-grid-v1'
POLICY = 'virtual-duration-power-v1'
GRID = 'seconds-1-30-plus-7-percent-v1'


def duration_grid(longest):
    """Common exact anchors; no ride-specific invented or interpolated values.

    All integer seconds through 30, then ceil(previous * 1.07), plus familiar
    durations. No fixed upper limit: extend through each supported recording.
    """
    values = set(range(1, min(30, longest) + 1))
    d = 30
    while d <= longest:
        values.add(d)
        d = (d * 107 + 99) // 100
    values.update(d for d in (60, 90, 120, 180, 300, 600, 900, 1200, 1800,
                              2400, 3600, 5400, 7200, 10800, 14400) if d <= longest)
    return sorted(values)


def mmp(records, *, intervals=None, durations=None):
    """O(samples * anchors) integer prefix sums over supported continuous runs.

    Records are observations, not forward timer bins. Shared timer endpoints
    belong to the earlier interval. Distinct verified intervals remain separate.
    Exact sum comparisons retain the earliest source-order maximal window.
    """
    runs, current, previous, last_group = [], [], None, None
    stops = [end for _, end in intervals] if intervals is not None else []
    for i, record in enumerate(records):
        power, timestamp = record['power'], record['timestamp']
        if power is not None and (type(power) is not int or power < 0):
            raise IntegrityError('Invalid power in current curve extraction')
        try:
            stamp = datetime.fromisoformat(timestamp) if timestamp is not None else None
        except (ValueError, TypeError) as exc:
            raise IntegrityError('Invalid timestamp in current curve extraction') from exc
        if stamp is not None and stamp.tzinfo is None:
            raise IntegrityError('Unsupported naive timestamp in curve calculation')
        epoch = stamp.timestamp() if stamp is not None else None
        group = 0
        if intervals is not None:
            group = bisect_left(stops, epoch) if epoch is not None else len(stops)
            if group == len(stops) or epoch < intervals[group][0]:
                group = None
        valid = power is not None and stamp is not None and group is not None
        consecutive = valid and previous is not None and stamp-previous == timedelta(seconds=1) and group == last_group
        if not valid or not consecutive:
            if current:
                runs.append(current)
                current = []
        if valid:
            current.append((i, power))
        previous, last_group = (stamp if valid else None), group
    if current:
        runs.append(current)
    longest = max((len(run) for run in runs), default=0)
    anchors = duration_grid(longest) if durations is None else sorted(set(durations))
    prefixes = []
    for run in runs:
        sums = [0]
        for _, power in run:
            sums.append(sums[-1] + power)
        prefixes.append((run[0][0], sums))
    points = []
    for d in anchors:
        if type(d) is not int or d <= 0:
            raise ValueError('Curve durations must be positive integers')
        best, start, windows = None, None, 0
        for offset, sums in prefixes:
            count = len(sums) - d
            if count <= 0:
                continue
            windows += count
            for j in range(count):
                total = sums[j+d] - sums[j]
                if best is None or total > best:
                    best, start = total, offset+j
        if best is None:
            continue
        first, last = records[start], records[start+d-1]
        points.append(dict(duration_seconds=d, sum_watts=best, average_watts=best/d,
                           rounded_watts=(best+d//2)//d, eligible_window_count=windows,
                           start_record_index=first['record_index'],
                           end_exclusive_record_index=last['record_index']+1,
                           start_timestamp=first['timestamp'],
                           end_exclusive_timestamp=(datetime.fromisoformat(first['timestamp'])+timedelta(seconds=d)).isoformat()))
    return dict(points=points, longest_continuous_seconds=longest)


def signature(store, snapshot):
    # Timer rows belong to immutable extractions; include their small content
    # explicitly so changed timing evidence also invalidates derived profiles.
    events = [tuple(r) for r in store.connection.execute('''SELECT e.* FROM events e
        JOIN extractions x ON x.extraction_id=e.extraction_id JOIN sources s ON s.source_id=x.source_id
        WHERE s.activity_id=? ORDER BY e.extraction_id,e.source_order''', (snapshot['activity']['activity_id'],))]
    payload = [METHOD, POLICY, GRID, input_signature(snapshot, store), events]
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def native_profile(store, metadata, activity_id):
    source, extraction = metadata['source'], metadata['extraction']
    count = store.connection.execute('SELECT COUNT(*),COUNT(power) FROM records WHERE extraction_id=?',
                                     (extraction['extraction_id'],)).fetchone()
    if tuple(count) != (extraction['record_count'], extraction['power_present']):
        raise IntegrityError('Curve native counts disagree with extraction')
    if not extraction['power_present']:
        return dict(points=[], reason='no_native_power')
    native = store.get_source(source['source_id'])
    records = native['records']
    try:
        stamps = [datetime.fromisoformat(r['timestamp']) for r in records if r['timestamp'] is not None]
    except (ValueError, TypeError) as exc:
        raise IntegrityError('Invalid curve extraction timestamp') from exc
    if any(t.tzinfo is None for t in stamps):
        return dict(points=[], reason='native_timestamp_timezone_unknown')
    intervals, problem, verified = timer_scope(native['events'], native['summary'])
    timers = any(e['event'] == 'timer' for e in native['events'])
    quality = ('session_verified' if verified else 'events_absent' if not timers else
               'paired_scope_unverified' if intervals is not None else 'unpaired_or_invalid')
    profile = mmp(records, intervals=intervals if verified else None)
    ref = dict(source_id=source['source_id'], extraction_id=extraction['extraction_id'],
               content_format=source['content_format'], origin='calculated observed power',
               timeline='recorded_sample_timeline', timer_quality=quality, timer_problem=problem)
    for p in profile['points']:
        discrepancy = False
        if intervals is not None and not verified:
            a, b = datetime.fromisoformat(p['start_timestamp']).timestamp(), datetime.fromisoformat(p['end_exclusive_timestamp']).timestamp()-1
            discrepancy = not any(start <= a and b <= end for start, end in intervals)
        p['source'] = ref | dict(timer_discrepancy=discrepancy)
    best = best_20_minute_power(records, activity_id=activity_id, source_id=source['source_id'],
                               extraction_id=extraction['extraction_id'])
    shared = next((p for p in profile['points'] if p['duration_seconds'] == 1200), None)
    if best['eligible'] and (shared is None or any(shared[k] != best[k] for k in
                          ('average_watts','rounded_watts','start_record_index','end_exclusive_record_index'))):
        raise IntegrityError('Verified timer segmentation conflicts with accepted best-20; Analyst review required')
    return profile | dict(reason=None if profile['points'] else 'no_supported_observed_window')


def api_profile(store, snapshot):
    summaries = [e for e in snapshot['sources'] if e['source']['kind'] == 'strava_api' and e['source']['is_current']]
    if len(summaries) != 1:
        return dict(points=[], reason='api_current_source_ambiguous' if summaries else 'no_qualifying_power_source')
    observations = [e for e in store.strava_stream_evidence(snapshot['activity']['activity_id']) if e['is_current']]
    if len(observations) != 1:
        return dict(points=[], reason='api_current_source_ambiguous' if observations else 'api_power_stream_unavailable')
    summary, observed = summaries[0], observations[0]
    def unavailable(reason):
        return dict(points=[], reason=reason)
    if observed['summary_source_id'] != summary['source']['source_id']:
        return unavailable('api_stream_summary_not_current')
    if summary['summary']['values'].get('device_watts') is not True:
        return unavailable('api_device_watts_not_confirmed')
    time, watts = (observed['streams'].get(k) for k in ('time','watts'))
    if time is None or watts is None:
        return unavailable('api_power_stream_unavailable')
    if any(s['resolution'] != 'high' for s in (time,watts)):
        return unavailable('api_stream_not_high_resolution')
    if any(s['original_size'] != len(s['data']) for s in (time,watts)):
        return unavailable('api_stream_not_full_length')
    if len(time['data']) != len(watts['data']):
        return unavailable('api_stream_length_mismatch')
    if any(time[k] != watts[k] for k in ('original_size','resolution','series_type')):
        return unavailable('api_stream_pairing_ambiguous')
    offsets = time['data']
    if (any(type(t) is not int or t < 0 for t in offsets)
            or any(b <= a for a,b in zip(offsets, offsets[1:]))):
        return unavailable('api_stream_invalid_timing')
    try:
        start = datetime.fromisoformat(observed['start_date'].replace('Z','+00:00'))
    except (ValueError, TypeError):
        return unavailable('api_start_unavailable')
    if start.tzinfo is None:
        return unavailable('api_start_unavailable')
    records = [dict(record_index=i, timestamp=(start+timedelta(seconds=t)).isoformat(),power=p)
               for i,(t,p) in enumerate(zip(offsets, watts['data']))]
    profile = mmp(records)
    ref = dict(source_id=observed['source_id'], summary_source_id=observed['summary_source_id'],
               observation_sha256=observed['observation_sha256'], mapping_version=observed['mapping_version'],
               content_format='Strava API stream', origin='calculated observed power',
               timeline='validated_API_offsets', timer_quality='not_available', timer_discrepancy=False)
    for p in profile['points']:
        p.update(source=ref, start_offset=offsets[p['start_record_index']],
                 end_exclusive_offset=offsets[p['start_record_index']]+p['duration_seconds'])
    return profile | dict(reason=None if profile['points'] else 'no_supported_observed_window')


def evaluate(store, snapshot):
    cohort = classification(snapshot)
    result = dict(activity_id=snapshot['activity']['activity_id'],method=METHOD,policy=POLICY,
                  grid=GRID, classification=cohort, points=[],reason=None,candidates=[])
    if cohort['activity_type'] != 'Virtual Ride':
        return result | dict(reason='outdoor_ride_excluded' if cohort['activity_type'] == 'Ride' else 'non_virtual_or_ambiguous_classification')
    files = [e for e in snapshot['sources'] if e['source']['kind'] not in ('strava_export','strava_api')]
    candidates = []
    for e in files:
        candidate = native_profile(store,e,result['activity_id'])
        result['candidates'].append(dict(source_id=e['source']['source_id'],reason=candidate['reason'],
                                         supported_durations=len(candidate['points'])))
        candidates.append(candidate)
    by_duration = {}
    for candidate in candidates:
        for point in candidate['points']:
            by_duration.setdefault(point['duration_seconds'],[]).append(point)
    result['ambiguous_durations'] = sorted(d for d,p in by_duration.items() if len(p)>1)
    result['points'] = [p[0] for d,p in sorted(by_duration.items()) if len(p)==1]
    result['longest_continuous_seconds'] = max((c.get('longest_continuous_seconds',0) for c in candidates),default=0)
    if not file_power_present(snapshot):
        result.update(api_profile(store,snapshot))
    elif not result['points']:
        result['reason'] = 'competing_native_sources' if by_duration else 'no_supported_native_window'
    return result


def rebuild_curves(store, *, force=False):
    """Incremental compute with short read snapshots, then atomic publication.

    No archive-long write lock: Home/Plan may maintain their own caches while
    this runs. Recheck all input signatures in the final write snapshot. A
    concurrently changed source stays pending rather than publishing stale math.
    """
    started = perf_counter()
    calculated_at = datetime.now(timezone.utc).isoformat()
    counts = Counter()
    _check_extractions(store)
    identities = [s['activity']['activity_id'] for s in store.activity_history()]
    rows = []
    for identity in identities:
        with store._transaction():
            snapshot = store.activity_history(identity)[0]
            sig = signature(store,snapshot)
            row = store.connection.execute('SELECT input_signature FROM power_curve_profiles WHERE activity_id=? AND method=?',
                                            (identity,METHOD)).fetchone()
            if not force and row is not None and row[0] == sig:
                counts['reused'] += 1
                continue
            profile = evaluate(store,snapshot)
            rows.append((identity,sig,bool(profile['points']),json.dumps(profile,sort_keys=True)))
    publish_started = perf_counter()
    with store._transaction(write=True):
        _check_extractions(store)
        current = {s['activity']['activity_id']:s for s in store.activity_history()} if rows else {}
        for identity,sig,has_power,payload in rows:
            if identity not in current or signature(store,current[identity]) != sig:
                counts['changed_during_build'] += 1
                continue
            store.connection.execute('''INSERT INTO power_curve_profiles VALUES(?,?,?,?,?)
                ON CONFLICT(activity_id) DO UPDATE SET method=excluded.method,
                input_signature=excluded.input_signature,calculated_at=excluded.calculated_at,result_json=excluded.result_json''',
                (identity,METHOD,sig,calculated_at,payload))
            counts['computed'] += 1
            counts['with_power'] += has_power
    return dict(status='incomplete' if counts['changed_during_build'] else 'completed',method=METHOD,grid=GRID,
                computed=counts['computed'],reused=counts['reused'],with_power=counts['with_power'],
                changed_during_build=counts['changed_during_build'],
                publication_seconds=round(perf_counter()-publish_started,3),
                elapsed_seconds=round(perf_counter()-started,3))


def curve_history(store):
    """Metadata/signature check, cached profiles only; stale inputs never plotted."""
    with store._transaction():
        snapshots = store.activity_history()
        saved = {r['activity_id']:r for r in store.connection.execute('SELECT * FROM power_curve_profiles WHERE method=?',(METHOD,))}
        profiles, results, pending = [], {}, 0
        for snapshot in snapshots:
            identity = snapshot['activity']['activity_id']
            row = saved.get(identity)
            if row is None or row['input_signature'] != signature(store,snapshot):
                pending += 1
                continue
            result = json.loads(row['result_json'])
            metadata = presentation(snapshot)
            result['activity'] = {k:metadata[k] for k in ('activity_id','title','start_time','absolute_time','date_day')}
            results[identity] = result
            if result['points']:
                profiles.append(result)
        return dict(profiles=profiles,results=results,pending=pending,evaluated=len(snapshots),method=METHOD,grid=GRID)


def converge_curves(store):
    """Post-sync derivation cannot undo committed originals/checkpoint updates."""
    import sqlite3
    from .errors import RideWorksError
    try:
        report = rebuild_curves(store)
        return dict(power_curve_update='incomplete' if report['status']=='incomplete' else 'updated' if report['computed'] else 'current')
    except (RideWorksError, OSError, sqlite3.Error):
        return dict(power_curve_update='incomplete')


def envelope(profiles, *, start=None, end=None, exclude=None):
    """[start,end) absolute membership; earliest start then ID breaks exact ties."""
    selected = []
    for profile in profiles:
        a = profile['activity']
        if a['activity_id'] == exclude or not a['absolute_time']:
            continue
        stamp = datetime.fromisoformat(a['start_time']).astimezone(timezone.utc)
        if start is not None and stamp < start or end is not None and stamp >= end:
            continue
        selected.append((stamp,a['activity_id'],profile))
    points = {}
    for stamp,identity,profile in sorted(selected,key=lambda r:r[:2]):
        for p in profile['points']:
            d = p['duration_seconds']
            if d not in points or p['sum_watts'] > points[d]['sum_watts']:
                points[d] = p | dict(activity=profile['activity'])
    return dict(points=[p for _,p in sorted(points.items())],count=len(selected),
                start=start.isoformat() if start is not None else None,
                end_exclusive=end.isoformat() if end is not None else None)


def comparison(store, *, activity_id=None, as_of=None, zone=timezone.utc):
    history = curve_history(store)
    profiles = history['profiles']
    data = dict(method=METHOD,grid=GRID,pending=history['pending'],series={},mode='activity' if activity_id else 'performance')
    if activity_id:
        result = history['results'].get(activity_id)
        snapshots = store.activity_history(activity_id)
        a = presentation(snapshots[0]) if snapshots else None
        current = [p | dict(activity=result['activity']) for p in result['points']] if result else []
        data['current_reason'] = result['reason'] if result else 'profile_update_required'
        data['series']['ride'] = dict(points=current,count=int(bool(current)),start=None,end_exclusive=None)
        data['ambiguous_durations'] = result.get('ambiguous_durations',[]) if result else []
        if a is None or not a['absolute_time']:
            data['baseline_reason'] = 'activity_absolute_start_unavailable'
            for key in ('six','year','all'):
                data['series'][key] = dict(points=[],count=0,start=None,end_exclusive=None)
        else:
            end = datetime.fromisoformat(a['start_time']).astimezone(timezone.utc)
            for key,start in [('six',end-timedelta(days=42)),('year',months_before(end,12)),('all',None)]:
                data['series'][key] = envelope(profiles,start=start,end=end,exclude=activity_id)
    else:
        end = as_of or datetime.now(timezone.utc)
        if end.tzinfo is None:
            raise ValueError('Power Curve as-of timezone is required')
        local = end.astimezone(zone)
        year = local.replace(month=1,day=1,hour=0,minute=0,second=0,microsecond=0)
        data['as_of'] = end.isoformat()
        data['calendar_timezone'] = str(zone)
        for key,start,stop in [('six',end-timedelta(days=42),end),
                               ('previous',end-timedelta(days=84),end-timedelta(days=42)),
                               ('ytd',year,end),('last_year',year.replace(year=year.year-1),year),('all',None,end)]:
            data['series'][key] = envelope(profiles,start=start,end=stop)
    return data
