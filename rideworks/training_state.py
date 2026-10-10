"""Versioned cycling stress, source candidates and exact rider-local daily model.

Stress eligibility is independent of best-20 Performance. The cache is replaceable;
original/source evidence remains authoritative. No network access occurs here.
"""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from zoneinfo import ZoneInfo
import io
import json
import math

from .errors import IntegrityError
from .goals import browser_zone
from .history import presentation
from .performance import classification, file_power_present, input_signature

VERSION = 'training-state-v3'
POWER_SOURCE_POLICY = 'virtual-recorded-stress-evidence-v1'
HR_SOURCE_POLICY = 'same-source-hr-summary-fallback-v2'
POWER_METHOD = 'recorded-power-stress-v1'
HR_METHOD = 'threshold-normalized-average-hr-v1'
MODEL_METHOD = 'daily-exponential-42-7-prior-form-v1'
FTP_CALENDAR = 'America/Los_Angeles'  # Accepted DESIGN-003 historical-setting calendar.
DEFAULT_HR = dict(resting_hr=58, max_hr=158, threshold_hr=143,
                  basis='Owner-approved retrospective modeling assumptions',
                  status='assumed', effective_from=None, effective_until_exclusive=None,
                  coefficient=1.92)
MIN_SEGMENT = 600
HR_COVERAGE = .99
MAX_HR_INTERVAL = 15


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def epoch(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp.timestamp() if stamp.tzinfo else None
    except ValueError:
        return None


def ftp_history(source_path=None):
    """Load the packaged approved source, or an explicitly updated dated record.

    A path must be supplied deliberately by the caller; source content rather
    than record count identifies it and invalidates derived caches.
    """
    payload = Path(source_path).read_bytes() if source_path is not None else files('rideworks').joinpath('data/strava_ftp_history.csv').read_bytes()
    reader = csv.DictReader(io.StringIO(payload.decode()))
    if reader.fieldnames != ['effective_from_date', 'effective_until_date_exclusive', 'ftp_watts']:
        raise IntegrityError('FTP source columns changed; Analyst review required')
    rows = list(reader)
    previous = None
    for i, row in enumerate(rows):
        try:
            start = date.fromisoformat(row['effective_from_date'])
            end = row['effective_until_date_exclusive'] or None
            watts = int(row['ftp_watts'])
            if end is not None:
                date.fromisoformat(end)
            if None in row or start.isoformat() != row['effective_from_date']:
                raise ValueError('Malformed FTP row')
        except (ValueError, TypeError) as exc:
            raise IntegrityError('Invalid FTP effective intervals') from exc
        if watts <= 0 or (previous and start <= previous) or end != (rows[i+1]['effective_from_date'] if i+1 < len(rows) else None):
            raise IntegrityError('Invalid FTP effective intervals')
        row.update(ftp_watts=watts, effective_until_date_exclusive=end)
        previous = start
    if not rows:
        raise IntegrityError('FTP history is empty')
    return rows, sha256(payload).hexdigest()


def ftp_on(rows, day, absolute=True):
    def lookup(target):
        return next((r for r in reversed(rows) if r['effective_from_date'] <= target), None)
    result = lookup(day)
    uncertain = not absolute and any(lookup((date.fromisoformat(day)+timedelta(days=d)).isoformat()) != result for d in (-1, 1))
    return dict(status='date_uncertain' if uncertain else 'available' if result else 'unknown_prehistory',
                value=None if uncertain or result is None else result['ftp_watts'],
                interval=result, calendar_date=day,
                calendar_timezone=FTP_CALENDAR if absolute else 'source date; timezone unknown',
                source='Owner-provided Strava UI historical FTP setting')


def hr_context(day, history=None):
    """Accept only explicitly dated supplied settings; defaults remain assumptions.

    No generic profile engine or automatic inference from observed peaks.
    """
    matches = [r for r in (history or []) if r['effective_from'] <= day and
               (not r.get('effective_until_exclusive') or day < r['effective_until_exclusive'])]
    if len(matches) > 1:
        raise IntegrityError('Overlapping dated HR settings')
    return dict(matches[0], coefficient=1.92, status='dated') if matches else dict(DEFAULT_HR)


def hrss(mean_hr, seconds, settings):
    values = [mean_hr, seconds] + [settings.get(k) for k in ('resting_hr','max_hr','threshold_hr','coefficient')]
    if not all(finite(v) for v in values):
        return None
    rest, maximum, threshold = (settings[k] for k in ('resting_hr','max_hr','threshold_hr'))
    if not rest < mean_hr < maximum or not rest < threshold < maximum or seconds <= 0:
        return None
    reserve = (mean_hr-rest)/(maximum-rest)
    threshold_reserve = (threshold-rest)/(maximum-rest)
    coefficient = settings['coefficient']
    return 100*seconds/3600*(reserve*math.exp(coefficient*reserve))/(threshold_reserve*math.exp(coefficient*threshold_reserve))


def normalized_power(values):
    total = math.fsum(values[:30]); fourths = [(total/30)**4]
    for i in range(30, len(values)):
        total += values[i]-values[i-30]
        fourths.append((total/30)**4)
    return (math.fsum(fourths)/len(fourths))**.25


def timer_scope(events, summary):
    timers = [e for e in events if e['event'] == 'timer']
    if not timers:
        return None, 'no_timer_events', False
    intervals = []; active = None; previous = None
    for event in timers:
        t = epoch(event['timestamp'])
        if t is None or previous is not None and t < previous:
            return None, 'invalid_timer_time', False
        previous = t
        if event['event_type'] == 'start' and active is None:
            active = t
        elif event['event_type'] in ('stop','stop_all','stop_disable','stop_disable_all') and active is not None and t > active:
            intervals.append((active, t)); active = None
        else:
            return None, 'unpaired_timer_events', False
    if active is not None or not intervals:
        return None, 'unclosed_timer', False
    start, end = epoch(summary.get('start_time')), epoch(summary.get('timestamp'))
    elapsed, timer = summary.get('total_elapsed_time'), summary.get('total_timer_time')
    verified = bool(start == intervals[0][0] and end is not None and intervals[-1][1] <= end and
                    finite(elapsed) and intervals[-1][1] <= start+elapsed and finite(timer) and
                    abs(math.fsum(b-a for a,b in intervals)-timer) < 1e-6)
    return intervals, None if verified else 'timer_summary_boundary_unverified', verified


def power_candidate(times, powers, *, ftp, source, events=(), summary=None, duration=None):
    """Half-open observed 1 s bins; timer pauses excluded, NP reset per interval.

    FIT gaps use the arriving sample backward, as in accepted P4-01 research.
    This estimate never contributes synthetic observed work.
    """
    result = dict(method=POWER_METHOD, status='unavailable', stress=None, source=source,
                  scope='recorded interval', observed_work_kj=None, observed_seconds=0,
                  missing_seconds=None, excluded_short_seconds=0, corrected_seconds=0,
                  excluded_pause_samples=0, whole_session_verified=False, intervals=[], ftp=ftp)
    if len(times) != len(powers) or not times:
        return result | dict(reason='unpaired_or_empty_power')
    known = [t for t in times if finite(t)]
    if any(t % 1 for t in known) or any(b < a for a,b in zip(known,known[1:])):
        return result | dict(reason='unsupported_power_timing')
    intervals, timer_problem, verified = timer_scope(events, summary or {})
    result.update(timer_problem=timer_problem, timer_boundaries_verified=verified)
    if events and any(e['event']=='timer' for e in events) and intervals is None:
        return result | dict(reason='unresolved_timer_scope')
    counts = Counter(known)
    invalid = any(not finite(t) or counts[t] != 1 or not finite(p) or p < 0 for t,p in zip(times,powers))
    active_groups = defaultdict(list)
    for i,(t,p) in enumerate(zip(times,powers)):
        if not finite(t):
            continue
        group = next((j for j,(a,b) in enumerate(intervals) if a <= t and t+1 <= b), None) if intervals else 0
        if group is None:
            result['excluded_pause_samples'] += 1
        elif counts[t] == 1 and finite(p) and p >= 0:
            active_groups[group].append(i)
    observed = [i for group in active_groups.values() for i in group]
    result['observed_seconds'] = len(observed)
    if observed:
        result['observed_work_kj'] = math.fsum(powers[i] for i in observed)/1000
    parts = []; candidates = []; total_span = 0; missing = 0; largest_gap = 0
    boundary_loss = False
    for group, indexes in sorted(active_groups.items()):
        span = int(times[indexes[-1]]-times[indexes[0]]+1)
        total_span += span
        loss = span-len(indexes); missing += loss
        if verified and intervals and (times[indexes[0]] != intervals[group][0] or times[indexes[-1]]+1 != intervals[group][1]):
            boundary_loss = True
        runs = []; run = []; corrected = []
        for index in indexes:
            if run and times[index] != times[run[-1]]+1:
                runs.append(run); run = []
            run.append(index)
            if corrected:
                gap = int(times[index]-times[previous_index]-1)
                largest_gap = max(largest_gap, gap)
                corrected.extend([powers[index]]*gap)
            corrected.append(powers[index]); previous_index = index
        if run: runs.append(run)
        parts.extend(runs)
        candidates.append((span, loss, corrected))
    if intervals:
        boundary_loss |= len(active_groups) != len(intervals)
        result['timer_uncovered_seconds'] = max(0, int(math.fsum(b-a for a,b in intervals))-len(observed))
        result['verified_boundary_missing_seconds'] = max(0,result['timer_uncovered_seconds']-missing) if verified else None
    result['missing_seconds'] = missing if known else None
    if not finite(ftp.get('value')) or ftp['value'] <= 0:
        return result | dict(reason='ftp_unavailable')
    wattage = ftp['value']
    active_duration = duration if finite(duration) else (summary or {}).get('total_timer_time')
    materially_partial = finite(active_duration) and total_span < active_duration*.99
    result['recorded_active_span_seconds'] = total_span
    result['source_active_duration_seconds'] = active_duration
    result['materially_partial_scope'] = materially_partial
    dense = not invalid and not boundary_loss and not materially_partial and bool(candidates)
    correctable = (dense and source['format']=='FIT' and largest_gap <= 15 and
                   missing <= total_span*.01 and all(span >= MIN_SEGMENT for span,_,_ in candidates))
    complete = dense and missing == 0 and all(span >= MIN_SEGMENT for span,_,_ in candidates)
    if complete or correctable:
        for span,loss,values in candidates:
            np = normalized_power(values)
            result['intervals'].append(dict(seconds=span, np_watts=np, stress=span/36*(np/wattage)**2,
                                            corrected_seconds=loss))
        result.update(status='corrected_estimate' if missing else 'calculated',
                      corrected_seconds=missing, stress=math.fsum(p['stress'] for p in result['intervals']),
                      whole_session_verified=bool(verified and complete and not boundary_loss))
        if result['whole_session_verified']:
            result['scope']='verified timer session'
        return result | dict(reason=None)
    chosen = [run for run in parts if len(run) >= MIN_SEGMENT]
    for run in chosen:
        np = normalized_power([powers[i] for i in run])
        result['intervals'].append(dict(seconds=len(run), np_watts=np, stress=len(run)/36*(np/wattage)**2,
                                        corrected_seconds=0))
    result['excluded_short_seconds'] = len(observed)-sum(map(len, chosen))
    if chosen:
        result.update(status='partial', scope='observed segments >=600 seconds',
                      stress=math.fsum(p['stress'] for p in result['intervals']))
    return result | dict(reason='incomplete_power_scope')


def hr_stream(times, hrs, *, settings, source, events=(), summary=None, duration=None, segment_starts=()):
    """Measured native endpoints; trapezoidal time-weighted mean, no filled samples.

    >=99% active-time coverage and adjacent native intervals <=15 s. A final
    1 s bin follows the native-bin convention. Known pauses are never bridged.
    Duration must align with recorded span/timer to within max(1s,1%).
    """
    result = dict(method=HR_METHOD, evidence_kind='stream', source_policy=HR_SOURCE_POLICY, status='unavailable', stress=None, source=source,
                  settings=settings, mean_hr=None, active_seconds=None, coverage=None,
                  scope='full recorded active HR estimate', duration_choice=None)
    if len(times) != len(hrs) or not times:
        return result | dict(reason='unpaired_or_empty_hr')
    if any(not finite(t) for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        return result | dict(reason='invalid_hr_timing')
    intervals, problem, verified = timer_scope(events, summary or {})
    if any(e['event']=='timer' for e in events) and intervals is None:
        return result | dict(reason='unresolved_timer_scope')
    recorded_span = times[-1]-times[0]+1
    if intervals:
        # Paired events identify pauses independently of complete-session proof.
        # Clip only to native recorded bounds; never extend HR into unrecorded time.
        intervals = [(max(a,times[0]),min(b,times[-1]+1)) for a,b in intervals
                     if min(b,times[-1]+1) > max(a,times[0])]
        target = math.fsum(b-a for a,b in intervals)
        choice = 'recorded timer-active interval; known pauses excluded'
        source_duration = (summary or {}).get('total_timer_time')
        if target <= 0 or not finite(source_duration) or abs(target-source_duration) > max(1,source_duration*.01):
            return result | dict(reason='hr_duration_span_mismatch')
    elif finite(duration) and duration > 0:
        target = duration; choice = 'source active duration aligned to recorded span'
        if abs(target-recorded_span) > max(1, target*.01):
            return result | dict(reason='hr_duration_span_mismatch')
    else:
        # An unexplained sparse span alone does not establish active effort.
        return result | dict(reason='hr_active_duration_unavailable')
    weighted = []; covered = []; largest_unknown = 0
    def active(t):
        return next((j for j,(a,b) in enumerate(intervals) if a <= t < b), None) if intervals else 0
    starts = set(segment_starts)
    for i,(t,h) in enumerate(zip(times,hrs)):
        group = active(t)
        valid = finite(h) and 0 < h < 255 and group is not None
        next_in_group = i+1<len(times) and active(times[i+1]) == group and i+1 not in starts
        if next_in_group:
            step = times[i+1]-t; following = hrs[i+1]
            if valid and finite(following) and 0 < following < 255 and step <= MAX_HR_INTERVAL:
                weighted.append(step*(h+following)/2); covered.append(step)
            else:
                largest_unknown = max(largest_unknown, step)
        elif valid:
            # Only a known final second; never extend to a distant stop boundary.
            if not intervals or t+1 <= intervals[group][1]:
                weighted.append(h); covered.append(1)
    seconds = math.fsum(covered)
    coverage = seconds/target
    result.update(coverage=coverage, covered_seconds=seconds, active_seconds=target,
                  duration_choice=choice, known_uncovered_seconds=max(0,target-seconds),
                  timer_boundaries_verified=verified, timer_problem=problem)
    if coverage < HR_COVERAGE or coverage > 1.000001 or largest_unknown > MAX_HR_INTERVAL:
        return result | dict(reason='insufficient_hr_coverage')
    mean = math.fsum(weighted)/seconds
    stress = hrss(mean,target,settings)
    return result | dict(mean_hr=mean, stress=stress, status='estimated' if stress is not None else 'unavailable',
                         reason=None if stress is not None else 'invalid_hr_parameters')


def hr_summary(mean, seconds, *, settings, source, duration_basis='same-source reported active duration',
               stream_rejections=()):
    stress = hrss(mean,seconds,settings)
    return dict(method=HR_METHOD, evidence_kind='summary', source_policy=HR_SOURCE_POLICY,
                status='estimated' if stress is not None else 'unavailable',
                stress=stress, source=source, settings=settings, mean_hr=mean, active_seconds=seconds,
                reported_duration_seconds=seconds, coverage=None, completeness_verified=False,
                pause_treatment='unverified', mean_active_scope_verified=False,
                scope='HR summary estimate; completeness and pause treatment unverified',
                duration_choice=duration_basis, duration_basis=duration_basis,
                stream_rejections=list(stream_rejections),
                reason=None if stress is not None else 'invalid_hr_summary')


def native_hr_summary(native, settings, stream_rejections=()):
    """Independently eligible reported fields, never recording span as active time."""
    summary=native['summary'];source=source_ref(native);kind=source['format']
    if kind=='FIT':
        mean=summary.get('avg_heart_rate');seconds=summary.get('total_timer_time')
        basis='FIT total_timer_time (reported timer-active seconds)'
        elapsed=summary.get('total_elapsed_time')
        compatible=elapsed is None or finite(elapsed) and elapsed>0 and finite(seconds) and seconds<=elapsed
        intervals,_,_=timer_scope(native['events'],summary)
        if intervals and finite(seconds):
            compatible &= abs(math.fsum(b-a for a,b in intervals)-seconds)<=max(1,seconds*.01)
    elif kind=='TCX' and len(native.get('xml_context',{}).get('lap_summaries',[]))==1:
        lap=native['xml_context']['lap_summaries'][0]
        mean=lap.get('avg_heart_rate');seconds=lap.get('total_time_seconds')
        source=source|dict(lap_index=0)
        basis='TCX single-lap TotalTimeSeconds (reported lap seconds; active/pause semantics unverified)'
        compatible=True
    else:
        return hr_summary(None,None,settings=settings,source=source,stream_rejections=stream_rejections)|dict(reason='unsupported_native_hr_summary')
    result=hr_summary(mean,seconds,settings=settings,source=source,duration_basis=basis,
                      stream_rejections=stream_rejections)
    if not compatible:
        result.update(stress=None,status='unavailable',reason='incompatible_hr_summary_duration')
    return result


def choose_hr(candidates, settings):
    """Supported streams precede summary estimates; competing sources stay ambiguous."""
    available=[c for c in candidates if c['stress'] is not None]
    streams=[c for c in available if c['evidence_kind']=='stream']
    preferred=streams or available
    if len(preferred)==1:
        return preferred[0]
    return dict(method=HR_METHOD,source_policy=HR_SOURCE_POLICY,status='unavailable',stress=None,
                reason='ambiguous_hr_sources' if preferred else 'no_usable_hr',settings=settings)


def selected_stress(power, hr):
    if power.get('status') in ('calculated','corrected_estimate'):
        return dict(method='power', stress=power['stress'], status=power['status'], scope=power['scope'])
    if hr.get('stress') is not None:
        return dict(method='hr', stress=hr['stress'], status='hr_estimate', scope=hr['scope'])
    if power.get('status') == 'partial':
        return dict(method='power', stress=power['stress'], status='partial', scope=power['scope'])
    return dict(method=None, stress=None, status='unavailable', scope='unscored recorded ride')


def source_ref(native):
    return dict(source_id=native['source']['source_id'], extraction_id=native['extraction'].get('extraction_id'),
                format=native['source']['content_format'], artifact_sha256=native['source'].get('sha256'))


def evaluate_power(store, snapshot, ftp):
    """Trusted recorded-power candidates without a best-20 window prerequisite.

    Keep native/API precedence and ambiguity explicit. This does not introduce
    session estimation or change accepted interval/timer/gap calculations.
    """
    unavailable = dict(status='unavailable', stress=None, method=POWER_METHOD,
        observed_work_kj=None, observed_seconds=0, missing_seconds=None, excluded_short_seconds=0)
    cohort = classification(snapshot)
    def rejected(reason, source=None):
        return unavailable | dict(reason=reason, source=source)
    if cohort['activity_type'] != 'Virtual Ride':
        reason = 'outdoor_ride_excluded' if cohort['activity_type']=='Ride' else 'non_virtual_or_ambiguous_classification'
        return rejected(reason) | dict(eligibility=dict(eligible=False, reason=reason, policy=POWER_SOURCE_POLICY)), []
    candidates = []
    for metadata in snapshot['sources']:
        if metadata['source']['kind'] in ('strava_api','strava_export'):
            continue
        extraction=metadata['extraction']; sid=metadata['source']['source_id']
        if not extraction or not extraction.get('extraction_id'):
            raise IntegrityError('Power candidate has no current extraction')
        counts=store.connection.execute('SELECT COUNT(*),COUNT(power) FROM records WHERE extraction_id=?',
                                        (extraction['extraction_id'],)).fetchone()
        if tuple(counts)!=(extraction['record_count'],extraction['power_present']):
            raise IntegrityError('Native record counts do not match current extraction')
        if not extraction['power_present']:
            continue
        native=store.get_source(sid); records=native['records']; ref=source_ref(native)
        if len(records)!=extraction['record_count'] or sum(r['power'] is not None for r in records)!=extraction['power_present']:
            raise IntegrityError('Native record counts do not match current extraction')
        if any(r['power'] is not None and (type(r['power']) is not int or r['power']<0) for r in records):
            raise IntegrityError('Unexpected native power in stress candidate')
        try:
            stamps=[datetime.fromisoformat(r['timestamp']) for r in records if r['timestamp'] is not None]
        except (ValueError,TypeError) as exc:
            raise IntegrityError('Invalid timestamp in current native extraction') from exc
        if any(t.tzinfo is None for t in stamps):
            candidates.append(rejected('native_timestamp_timezone_unknown',ref)); continue
        candidates.append(power_candidate([epoch(r['timestamp']) for r in records],[r['power'] for r in records],
            ftp=ftp,source=ref,events=native['events'],summary=native['summary']))
    if not file_power_present(snapshot):
        summaries=[s for s in snapshot['sources'] if s['source']['kind']=='strava_api' and s['source']['is_current']]
        observations=[s for s in store.strava_stream_evidence(snapshot['activity']['activity_id']) if s['is_current']]
        reason='api_power_stream_unavailable'; ref=None
        if len(summaries)!=1 or len(observations)!=1:
            if len(summaries)>1 or len(observations)>1: reason='api_current_source_ambiguous'
        else:
            api=summaries[0]; observation=observations[0]; values=api['summary']['values']; streams=observation['streams']
            ref=dict(format='Strava API stream',evidence_kind='Strava API stream',stream_source_id=observation['source_id'],
                summary_source_id=api['source']['source_id'],related_summary_source_id=observation['summary_source_id'],
                observation_sha256=observation['observation_sha256'],mapping_version=observation['mapping_version'],
                device_watts=values.get('device_watts'),start_date=observation['start_date'],metadata=observation['metadata'])
            time,watts=streams.get('time'),streams.get('watts')
            if observation['summary_source_id']!=api['source']['source_id']: reason='api_stream_summary_not_current'
            elif values.get('device_watts') is not True: reason='api_device_watts_not_confirmed'
            elif time is None or watts is None: pass
            elif any(s['resolution']!='high' for s in (time,watts)): reason='api_stream_not_high_resolution'
            elif any(s['original_size']!=len(s['data']) for s in (time,watts)): reason='api_stream_not_full_length'
            elif len(time['data'])!=len(watts['data']) or any(time[k]!=watts[k] for k in ('original_size','resolution','series_type')):
                reason='api_stream_pairing_ambiguous'
            elif any(type(t) is not int or t<0 for t in time['data']) or any(b<=a for a,b in zip(time['data'],time['data'][1:])):
                reason='api_stream_invalid_timing'
            elif any(p is not None and (type(p) is not int or p<0) for p in watts['data']): reason='api_stream_invalid_power'
            else:
                candidates.append(power_candidate(time['data'],watts['data'],ftp=ftp,source=ref,duration=values.get('moving_time')))
                reason=None
        if reason is not None: candidates.append(rejected(reason,ref))
    usable=[c for c in candidates if c['stress'] is not None]
    if len(usable)>1:
        chosen=rejected('multiple_usable_power_sources')
    elif usable:
        chosen=usable[0]
    elif len(candidates)==1:
        chosen=candidates[0]
    else:
        chosen=rejected('multiple_power_sources_unresolved' if candidates else 'no_native_power_api_fallback_blocked')
    chosen=chosen | dict(eligibility=dict(eligible=bool(len(usable)==1),reason=chosen.get('reason'),policy=POWER_SOURCE_POLICY))
    return chosen,candidates


def calculate_ride(store, snapshot, row, ftp, settings):
    power,power_candidates=evaluate_power(store,snapshot,ftp)
    candidates = []
    for metadata in snapshot['sources']:
        if metadata['source']['kind'] in ('strava_api','strava_export'):
            continue
        sid = metadata['source']['source_id']
        native = store.get_source(sid)
        times = [epoch(r['timestamp']) for r in native['records']]
        hrs = [r['heart_rate'] for r in native['records']]
        summary = native['summary']
        duration = summary.get('total_timer_time')
        laps = native.get('xml_context',{}).get('lap_summaries',[])
        if duration is None and len(laps)==1:
            duration=laps[0].get('total_time_seconds')
        candidate = hr_stream(times,hrs,settings=settings,source=source_ref(native),events=native['events'],
                              summary=summary,duration=duration,
                              segment_starts=native.get('xml_context',{}).get('segment_start_record_indexes',[]))
        candidates.append(candidate)
        if candidate['stress'] is None:
            candidates.append(native_hr_summary(native,settings,[candidate]))
    apis = [s for s in snapshot['sources'] if s['source']['kind']=='strava_api' and s['source']['is_current']]
    for api in apis:
        values=api['summary']['values']
        ref=dict(source_id=api['source']['source_id'],format='Strava API summary',
                 artifact_sha256=api['source'].get('sha256'))
        observations=[s for s in store.strava_stream_evidence(row['activity_id']) if s['is_current'] and s['summary_source_id']==ref['source_id']]
        source_streams=[]
        for observation in observations:
            streams=observation['streams']
            if 'heartrate' not in streams:
                continue
            stream_ref=ref|dict(format='Strava API stream',stream_source_id=observation['source_id'],
                                observation_sha256=observation['observation_sha256'])
            if 'time' in streams and all(s['resolution']=='high' and s['original_size']==len(s['data']) for s in (streams['time'],streams['heartrate'])):
                candidate=hr_stream(streams['time']['data'],streams['heartrate']['data'],settings=settings,
                                    source=stream_ref,duration=values.get('moving_time'))
            else:
                candidate=dict(method=HR_METHOD,evidence_kind='stream',source_policy=HR_SOURCE_POLICY,
                    source=stream_ref,stress=None,status='unavailable',
                    reason='missing_hr_stream_time' if 'time' not in streams else 'unsupported_hr_stream_resolution')
            source_streams.append(candidate);candidates.append(candidate)
        if not any(c['stress'] is not None for c in source_streams):
            summary=hr_summary(values.get('average_heartrate'),values.get('moving_time'),settings=settings,source=ref,
                               duration_basis='Strava API moving_time (reported moving seconds)',stream_rejections=source_streams)
            if not (values.get('has_heartrate') is True and finite(values.get('moving_time')) and finite(values.get('elapsed_time')) and 0 < values['moving_time'] <= values['elapsed_time']):
                summary.update(stress=None,status='unavailable',reason='invalid_api_hr_summary')
            candidates.append(summary)
    hr=choose_hr(candidates,settings)
    selected=selected_stress(power,hr)
    return dict(version=VERSION, power_source_policy=POWER_SOURCE_POLICY, hr_source_policy=HR_SOURCE_POLICY, activity_id=row['activity_id'], selected=selected, power=power, power_candidates=power_candidates, hr=hr,
                hr_candidates=candidates, ftp=ftp, hr_settings=settings)


def ride_results(store, zone_name, *, as_of=None, hr_history=None, ftp_source=None):
    zone=browser_zone(zone_name); as_of=as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError('Training State as-of must be absolute')
    today=as_of.astimezone(zone).date(); history,digest=ftp_history(ftp_source)
    rows=[]; excluded=Counter()
    with store._transaction(write=True):
        for snapshot in store.activity_history():
            row=presentation(snapshot)
            if row['activity_type'] not in ('Ride','Virtual Ride'):
                excluded['noncycling']+=1; continue
            if not row['start_time']:
                excluded['missing_date']+=1; continue
            stamp=datetime.fromisoformat(row['start_time'])
            day=stamp.astimezone(zone).date() if row['absolute_time'] else stamp.date()
            if day>today or row['absolute_time'] and stamp>as_of:
                excluded['future']+=1; continue
            athlete_day=stamp.astimezone(ZoneInfo(FTP_CALENDAR)).date() if row['absolute_time'] else stamp.date()
            ftp=ftp_on(history,athlete_day.isoformat(),row['absolute_time']); settings=hr_context(athlete_day.isoformat(),hr_history)
            # Include HR streams even when native power prevents API Performance fallback.
            streams=[dict(r) for r in store.connection.execute('''SELECT s.source_id,s.summary_source_id,s.observation_sha256
                FROM strava_stream_sources s JOIN strava_stream_current c ON c.source_id=s.source_id
                WHERE s.activity_id=? ORDER BY s.source_id''',(row['activity_id'],))]
            signature=sha256(json.dumps([VERSION,POWER_SOURCE_POLICY,HR_SOURCE_POLICY,input_signature(snapshot,store),streams,ftp,settings,digest],sort_keys=True).encode()).hexdigest()
            saved=store.connection.execute('SELECT input_signature,result_json FROM training_stress_cache WHERE activity_id=?',(row['activity_id'],)).fetchone()
            if saved and saved[0]==signature:
                result=json.loads(saved[1])
            else:
                result=calculate_ride(store,snapshot,row,ftp,settings)
                store.connection.execute('''INSERT INTO training_stress_cache VALUES (?,?,?) ON CONFLICT(activity_id)
                    DO UPDATE SET input_signature=excluded.input_signature,result_json=excluded.result_json''',
                    (row['activity_id'],signature,json.dumps(result,sort_keys=True,allow_nan=False)))
            rows.append(result|dict(day=day.isoformat(),title=row['title'],timezone_unknown=not row['absolute_time']))
    return rows, dict(today=today.isoformat(),timezone=zone_name,as_of=as_of.isoformat(),excluded=dict(excluded),
                      ftp_source_sha256=digest,version=VERSION,power_source_policy=POWER_SOURCE_POLICY,model_method=MODEL_METHOD,
                      hr_method=HR_METHOD,hr_source_policy=HR_SOURCE_POLICY,hr_default_assumptions=DEFAULT_HR)


def daily_series(rides, today):
    """Zero seed before first usable score; unscored evidence never becomes zero."""
    grouped=defaultdict(list)
    for ride in rides:
        grouped[ride['day']].append(ride)
    usable=[r['day'] for r in rides if r['selected']['stress'] is not None]
    if not usable:
        return []
    start=date.fromisoformat(min(usable)); end=date.fromisoformat(today)
    fitness=fatigue=0.; rows=[]
    for offset in range((end-start).days+1):
        day=(start+timedelta(days=offset)).isoformat(); group=sorted(grouped[day],key=lambda r:r['activity_id'])
        selected=[r for r in group if r['selected']['stress'] is not None]
        stress=math.fsum(r['selected']['stress'] for r in selected)
        form=fitness-fatigue
        fitness+=(stress-fitness)*(-math.expm1(-1/42)); fatigue+=(stress-fatigue)*(-math.expm1(-1/7))
        classes=Counter(r['selected']['status'] for r in selected)
        row=dict(day=day,fitness=fitness,fatigue=fatigue,form=form,stress=stress,rides=group,
                 no_record=not group,unscored=len(group)-len(selected),contributors=len(selected),
                 source_classes=dict(classes),early_history_provisional=offset<126,
                 work_kj=math.fsum(r['power']['observed_work_kj'] for r in group if r['power'].get('observed_work_kj') is not None),
                 work_contributors=sum(r['power'].get('observed_work_kj') is not None for r in group),
                 known_missing_power_seconds=sum(r['power'].get('missing_seconds') or 0 for r in group),
                 excluded_short_power_seconds=sum(r['power'].get('excluded_short_seconds') or 0 for r in group),
                 verified_boundary_missing_seconds=sum(r['power'].get('verified_boundary_missing_seconds') or 0 for r in group))
        row['changes7']={k:row[k]-rows[-7][k] if len(rows)>=7 else None for k in ('fitness','fatigue','form')}
        rows.append(row)
        for n in (7,42):
            window=rows[-n:]; counts=Counter()
            for d in window: counts.update(d['source_classes'])
            row[f'window{n}']=dict(calendar_days=len(window),stress=math.fsum(d['stress'] for d in window),
                work_kj=math.fsum(d['work_kj'] for d in window),rides=sum(len(d['rides']) for d in window),
                contributors=sum(d['contributors'] for d in window),unscored=sum(d['unscored'] for d in window),
                work_contributors=sum(d['work_contributors'] for d in window),
                work_omissions=sum(len(d['rides'])-d['work_contributors'] for d in window),
                no_record_days=sum(d['no_record'] for d in window),source_classes=dict(counts),
                known_missing_power_seconds=sum(d['known_missing_power_seconds'] for d in window),
                excluded_short_power_seconds=sum(d['excluded_short_power_seconds'] for d in window),
                verified_boundary_missing_seconds=sum(d['verified_boundary_missing_seconds'] for d in window))
    return rows


def training_state(store, zone_name, *, as_of=None, hr_history=None, ftp_source=None):
    rides,context=ride_results(store,zone_name,as_of=as_of,hr_history=hr_history,ftp_source=ftp_source)
    days=daily_series(rides,context['today'])
    return context|dict(days=days,coverage=dict(rides=len(rides),scored=sum(r['selected']['stress'] is not None for r in rides),
                       selected_classes=dict(Counter(r['selected']['status'] for r in rides)),
                       days=len(days),scored_days=sum(d['contributors']>0 for d in days),
                       before_model_start=sum(bool(days) and r['day']<days[0]['day'] for r in rides)))
