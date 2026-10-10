#!/usr/bin/env python3
"""Read-only P4-02 source diagnosis, not a proposed production selection policy.

Cases are predeclared privately by local date/title, independently of selected
stress. Detailed evidence stays private; only source-neutral counts are public.
No fetching, reconstruction, cache writes or replacement score selection occurs.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rideworks.history import presentation
from rideworks.performance import evaluate, file_power_present
from rideworks.store import Store
from rideworks.training_state import (calculate_ride, daily_series, epoch, finite,
    ftp_history, ftp_on, hr_context, power_candidate, source_ref, VERSION, POWER_SOURCE_POLICY)
from tools.compare_training_state_elevate import read_reference
from tools.verify_training_state_production import preservation, readonly


def close(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9)


def table_digest(connection):
    """Include derived caches and schema, not just the original-source tables."""
    tables = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    content = []
    for name, sql in tables:
        quoted = '"' + name.replace('"', '""') + '"'
        rows = sorted(tuple(r) for r in connection.execute('SELECT * FROM ' + quoted))
        content.append((name, sql, rows))
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def bins(times, powers):
    counts = Counter(t for t in times if finite(t))
    valid = [(t, p) for t, p in zip(times, powers)
             if finite(t) and counts[t] == 1 and finite(p) and p >= 0]
    runs = []; run = []; last = None
    for t, p in valid:
        if last is not None and t != last + 1:
            if run: runs.append(run)
            run = []
        run.append((t, p)); last = t
    if run: runs.append(run)
    return dict(sample_count=len(times), valid_unique_power_bins=len(valid),
        invalid_or_missing_power=sum(not finite(p) or p < 0 for p in powers),
        missing_timestamps=sum(not finite(t) for t in times),
        duplicate_timestamp_bins=sum(counts[t] > 1 for t in times if finite(t)),
        first_timestamp=times[0] if times else None, last_timestamp=times[-1] if times else None,
        timestamp_gaps=[dict(before=a, after=b, missing_seconds=b-a-1)
                        for a, b in zip(times, times[1:]) if finite(a) and finite(b) and b != a+1],
        continuous_runs=[dict(start=r[0][0], end_exclusive=r[-1][0]+1, seconds=len(r)) for r in runs])


def verify_score(candidate, times, powers, events, summary):
    """Independent direct 30-second sums for accepted observed/corrected bins."""
    if candidate['stress'] is None: return 0
    from rideworks.training_state import timer_scope
    intervals, _, _ = timer_scope(events, summary)
    counts = Counter(t for t in times if finite(t)); groups = {}
    for t, p in zip(times, powers):
        if not finite(t) or counts[t] != 1 or not finite(p) or p < 0: continue
        group = next((i for i, (a, b) in enumerate(intervals) if a <= t and t+1 <= b), None) if intervals else 0
        if group is not None: groups.setdefault(group, []).append((t, p))
    runs = []
    for points in groups.values():
        if candidate['status'] == 'corrected_estimate':
            values = []
            for i, (t, p) in enumerate(points):
                values.extend([p] * (int(t-points[i-1][0]) if i else 1))
            runs.append(values)
        elif candidate['status'] == 'calculated': runs.append([p for t, p in points])
        else:
            run = []; last = None
            for t, p in points:
                if last is not None and t != last+1:
                    if len(run) >= 600: runs.append(run)
                    run = []
                run.append(p); last = t
            if len(run) >= 600: runs.append(run)
    expected = []
    for run in runs:
        np = (math.fsum((math.fsum(run[i:i+30])/30)**4 for i in range(len(run)-29))/(len(run)-29))**.25
        expected.append(len(run)/36*(np/candidate['ftp']['value'])**2)
    close(candidate['stress'], math.fsum(expected))
    close(candidate['observed_work_kj'], math.fsum(p for points in groups.values() for t, p in points)/1000)
    return len(runs)


def candidates(store, snapshot, ftp, kind):
    """Audit each source; only already supported virtual power enters candidates.

    Independent of best-20 suitability, but retain file/API trust and precedence.
    A stress result here is diagnostic evidence, never the selected ride result.
    """
    output = []; formula_checks = 0
    native_present = file_power_present(snapshot)
    for metadata in snapshot['sources']:
        source = metadata['source']
        if source['kind'] in ('strava_api', 'strava_export'): continue
        native = store.get_source(source['source_id']); records = native['records']
        times = [epoch(r['timestamp']) for r in records]; powers = [r['power'] for r in records]
        rejection = None
        if kind != 'Virtual Ride': rejection = 'outdoor_or_nonvirtual_power_not_admitted'
        elif any(r['timestamp'] is not None and epoch(r['timestamp']) is None for r in records): rejection = 'native_timestamp_timezone_unknown_or_invalid'
        elif any(p is not None and (type(p) is not int or p < 0) for p in powers): rejection = 'invalid_native_power'
        assert len(records) == metadata['extraction']['record_count']
        assert sum(p is not None for p in powers) == metadata['extraction']['power_present']
        result = None
        if rejection is None:
            result = power_candidate(times, powers, ftp=ftp, source=source_ref(native),
                                     events=native['events'], summary=native['summary'])
            formula_checks += verify_score(result, times, powers, native['events'], native['summary'])
        output.append(dict(source=source, evidence_version=native['extraction'],
            original_measured_power_present=any(p is not None for p in powers),
            recording=bins(times, powers), summary=native['summary'], timer_events=native['events'],
            trust_rejection=rejection, diagnostic_power=result))
    summaries = [s for s in snapshot['sources'] if s['source']['kind']=='strava_api' and s['source']['is_current']]
    observations = store.strava_stream_evidence(snapshot['activity']['activity_id'])
    current = [s for s in observations if s['is_current']]
    for observation in observations:
        streams = observation['streams']; time = streams.get('time', {}); watts = streams.get('watts', {})
        times = time.get('data', []); powers = watts.get('data', [])
        summary = next((s for s in summaries if s['source']['source_id']==observation['summary_source_id']), None)
        values = summary['summary']['values'] if summary else {}
        rejection = None
        if kind != 'Virtual Ride': rejection = 'outdoor_or_nonvirtual_power_not_admitted'
        elif native_present: rejection = 'native_power_evidence_blocks_api_fallback'
        elif not observation['is_current'] or len(current)!=1 or len(summaries)!=1 or summary is None: rejection = 'api_current_source_ambiguous_or_unpaired'
        elif values.get('device_watts') is not True: rejection = 'api_device_watts_not_confirmed'
        elif not time or not watts: rejection = 'api_power_stream_unavailable'
        elif any(s['resolution']!='high' or s['original_size']!=len(s['data']) for s in (time, watts)): rejection = 'api_stream_resolution_or_length'
        elif len(times)!=len(powers) or any(time[k]!=watts[k] for k in ('original_size','resolution','series_type')): rejection = 'api_stream_pairing_ambiguous'
        elif any(type(t) is not int or t<0 for t in times) or any(b<=a for a,b in zip(times,times[1:])): rejection = 'api_stream_invalid_timing'
        elif any(p is not None and (type(p) is not int or p<0) for p in powers): rejection = 'api_stream_invalid_power'
        ref = dict(format='Strava API stream', stream_source_id=observation['source_id'],
                   summary_source_id=observation['summary_source_id'], observation_sha256=observation['observation_sha256'])
        result = None
        if rejection is None:
            result = power_candidate(times, powers, ftp=ftp, source=ref, duration=values.get('moving_time'))
            formula_checks += verify_score(result, times, powers, [], {})
        output.append(dict(source=ref, evidence_version=observation['mapping_version'],
            current=observation['is_current'], metadata=observation['metadata'],
            original_measured_power_present=values.get('device_watts') is True and bool(powers),
            recording=bins(times, powers), summary=values,
            moving_false_samples=[dict(offset=t, watts=p) for t,p,m in zip(times,powers,streams.get('moving',{}).get('data',[])) if m is False],
            timer_events=[], pause_evidence='moving flags do not verify timer stops or gap inactivity',
            trust_rejection=rejection, diagnostic_power=result))
    return output, formula_checks


def response(days, day, ride, reference):
    index = next(i for i,d in enumerate(days) if d['day']==day); current = days[index]
    previous = days[index-1]; following = days[index+1] if index+1<len(days) else None
    close(current['fitness'], previous['fitness']*math.exp(-1/42)+current['stress']*(-math.expm1(-1/42)))
    close(current['fatigue'], previous['fatigue']*math.exp(-1/7)+current['stress']*(-math.expm1(-1/7)))
    close(current['form'], previous['fitness']-previous['fatigue'])
    if following: close(following['form'], current['fitness']-current['fatigue'])
    fields = ('day','stress','fitness','fatigue','form','no_record','contributors','unscored')
    stress = ride['selected']['stress'] or 0
    return dict(previous_calendar_day={k:previous[k] for k in fields},
        selected_day={k:current[k] for k in fields}, next_calendar_day={k:following[k] for k in fields} if following else None,
        daily_changes={k:current[k]-previous[k] for k in ('fitness','fatigue')},
        isolated_selected_contribution=dict(fitness=stress*(-math.expm1(-1/42)),fatigue=stress*(-math.expm1(-1/7)),
            next_day_form=stress*((-math.expm1(-1/42))-(-math.expm1(-1/7)))),
        surrounding_calendar_days=[dict(rideworks={k:d[k] for k in fields},reference=reference.get(d['day']))
                                   for d in days[max(0,index-2):index+3]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('data-dir','baseline-dir','cases','reference','aggregate-output','private-output'):
        parser.add_argument('--'+flag, type=Path, required=True)
    parser.add_argument('--as-of', required=True)
    args = parser.parse_args(); as_of = datetime.fromisoformat(args.as_of)
    cases = json.loads(args.cases.read_text()); history, ftp_digest = ftp_history()
    completed, projected = read_reference(args.reference); reference = {r['date']:r for r in completed}
    before = preservation(args.data_dir, args.baseline_dir)
    with readonly(args.data_dir) as database:
        assert database.execute('PRAGMA user_version').fetchone()[0]==8, 'Supply the existing schema-8 private review copy'
        initial_digest = table_digest(database)
    with Store(args.data_dir) as store:
        store.connection.execute('PRAGMA query_only=ON')
        snapshots = store.activity_history(); rides = []; matches = []; census = Counter(); blocked = []; formula_checks = 0
        for snapshot in snapshots:
            row = presentation(snapshot)
            if row['activity_type'] not in ('Ride','Virtual Ride') or not row['start_time']: continue
            stamp = datetime.fromisoformat(row['start_time']); day = stamp.astimezone(ZoneInfo('America/Los_Angeles')).date() if row['absolute_time'] else stamp.date()
            if day>as_of.astimezone(ZoneInfo('America/Los_Angeles')).date() or row['absolute_time'] and stamp>as_of: continue
            ftp = ftp_on(history, day.isoformat(), row['absolute_time']); settings = hr_context(day.isoformat())
            result = calculate_ride(store, snapshot, row, ftp, settings)
            result.update(day=day.isoformat(), title=row['title']); rides.append(result)
            roles = [c for c in cases if c['day']==result['day'] and (not c.get('title') or c['title']==row['title'])
                     and (not c.get('activity_id') or c['activity_id']==row['activity_id'])]
            performance = evaluate(store, snapshot)
            if row['activity_type']=='Virtual Ride': census['virtual_rides']+=1
            if roles or row['activity_type']=='Virtual Ride' and not performance['eligible']:
                sources, checks = candidates(store, snapshot, ftp, row['activity_type']); formula_checks+=checks
                qualifying = [s['diagnostic_power'] for s in sources if s['diagnostic_power'] and s['diagnostic_power']['stress'] is not None]
                if row['activity_type']=='Virtual Ride' and not performance['eligible']:
                    census['best20_ineligible_virtual_rides']+=1
                    if qualifying:
                        census['best20_ineligible_with_stress_candidate']+=1
                        for status in set(c['status'] for c in qualifying): census['blocked_candidate_'+status]+=1
                        blocked.append(dict(ride=result,performance=performance,sources=sources))
                if roles: matches.append(dict(roles=roles,ride=result,performance=performance,sources=sources))
        for case in cases:
            assert sum(case in m['roles'] for m in matches)==1, 'Predeclared case not uniquely matched'
        days = daily_series(rides, as_of.astimezone(ZoneInfo('America/Los_Angeles')).date().isoformat())
        for match in matches:
            match['behavior'] = response(days, match['ride']['day'], match['ride'], reference)
        assert table_digest(store.connection)==initial_digest, 'Diagnosis changed database or cache'
    after = preservation(args.data_dir, args.baseline_dir); assert before==after
    windows = {}
    for n in (90,365):
        cutoff = date.fromisoformat(days[-1]['day'])-timedelta(days=n-1)
        rows = [d for d in days if date.fromisoformat(d['day'])>=cutoff]
        windows[str(n)] = dict(calendar_days=len(rows), source_classes=dict(Counter(r['selected']['status'] for d in rows for r in d['rides'])),
            no_record_days=sum(d['no_record'] for d in rows),unscored_rides=sum(d['unscored'] for d in rows))
    coupling = dict(census)
    coupling.update(best20_rejection_reasons_with_stress_candidate=dict(Counter(c['performance']['reason'] for c in blocked)),
        candidate_source_formats=dict(Counter(s['source'].get('format') or s['source']['content_format']
            for c in blocked for s in c['sources'] if s['diagnostic_power'] and s['diagnostic_power']['stress'] is not None)),
        current_selected_classes=dict(Counter(c['ride']['selected']['status'] for c in blocked)),
        affected_rides_in_windows={str(n):sum(date.fromisoformat(c['ride']['day']) >= date.fromisoformat(days[-1]['day'])-timedelta(days=n-1)
            for c in blocked) for n in (90,365)})
    aggregate = dict(diagnostic_only=True, calculation_version=VERSION,power_source_policy=POWER_SOURCE_POLICY,
        selection='Predeclared local dates/source workout descriptions; independent of selected stress ranking',
        representative_cases=len(matches), case_roles=dict(Counter(c['role'] for m in matches for c in m['roles'])),
        performance_statuses=dict(Counter('eligible' if m['performance']['eligible'] else m['performance']['reason'] for m in matches)),
        selected_methods=dict(Counter(m['ride']['selected']['status'] for m in matches)),
        independent_power_interval_formula_checks=formula_checks, daily_response_cases=len(matches),
        broader_best20_coupling=coupling, windows=windows, preservation=after,
        all_tables_including_cache_unchanged=True, ftp_source_sha256=ftp_digest,
        reference_bytes=args.reference.stat().st_size,reference_sha256=hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        projected_reference_rows_excluded=len(projected), production_policy_changed=False)
    private = dict(cases=matches, blocked_best20_cases=blocked, windows=windows,
        curves=[dict(rideworks={k:d[k] for k in ('day','stress','fitness','fatigue','form','no_record','unscored')},reference=reference.get(d['day'])) for d in days])
    for path, report in ((args.private_output,private),(args.aggregate_output,aggregate)):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(aggregate,indent=2,sort_keys=True))


if __name__=='__main__': main()
