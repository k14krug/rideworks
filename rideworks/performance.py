"""Versioned Virtual Ride power history with explicit file/API precedence."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json

from .analysis import BEST_20_METHOD, WINDOW_SAMPLES, best_20_minute_power
from .errors import IntegrityError
from .history import presentation

POLICY = 'virtual-power-evidence-v2'


def file_power_present(snapshot):
    # Supplied file power is evidence too, but never substitutes for sample power.
    files=[e for e in snapshot['sources'] if e['source']['kind'] not in ('strava_export','strava_api')]
    return any(e['extraction'].get('power_present',0)
               or any(e['summary'].get(k) is not None for k in ('avg_power','max_power'))
               or any(lap.get(k) is not None for lap in e.get('xml_context',{}).get('lap_summaries',[])
                      for k in ('avg_power','max_power'))
               for e in files)


def _check_extractions(store):
    if store.connection.execute('''SELECT 1 FROM sources s LEFT JOIN extractions e
        ON e.source_id=s.source_id WHERE e.extraction_id IS NULL LIMIT 1''').fetchone():
        raise IntegrityError('File Source has no current extraction; performance stopped')


def classification(snapshot):
    evidence = sorted(snapshot['sources'], key=lambda e: (e['source']['imported_at'], e['source']['source_id']))
    csv = [e for e in evidence if e['source']['kind'] == 'strava_export'
           and (e['summary'].get('activity_type') or '').strip()]
    api = [e for e in evidence if e['source']['kind']=='strava_api' and e['source']['is_current']
           and (e['summary'].get('activity_type') or '').strip()]
    if api or csv:
        latest = (api or csv)[-1]
        return dict(activity_type=latest['summary']['activity_type'].strip(),
                    source_ids=[latest['source']['source_id']], basis='latest_strava_type')
    types = []
    for e in evidence:
        if e['source']['kind'] in ('strava_export','strava_api'):
            continue
        summary = e['summary']
        kind = ('Virtual Ride' if summary.get('sub_sport') == 'virtual_activity' else
                'Ride' if (summary.get('sport') or '').casefold() in ('cycling', 'biking') else
                summary.get('sport'))
        if kind:
            types.append((kind, e['source']['source_id']))
    kinds = {kind for kind, _ in types}
    return dict(activity_type=next(iter(kinds)) if len(kinds) == 1 else None,
                source_ids=[source for _, source in types],
                basis='conflicting_native_classification' if len(kinds) > 1 else 'native_session')


def input_signature(snapshot, store=None):
    """All current candidate identities matter, including newly competing files.

    Metadata is small; including classification/date evidence also invalidates
    changed observation selection without a generalized dependency graph.
    """
    inputs = sorted((dict(source_id=e['source']['source_id'],
                          imported_at=e['source']['imported_at'],
                          extraction=e['extraction'], summary=e['summary'],
                          **({'is_current':e['source']['is_current']} if e['source']['kind']=='strava_api' else {}))
                     for e in snapshot['sources']), key=lambda e: e['source_id'])
    if store is not None and not file_power_present(snapshot):
        # Digests/identities only: freshness reads never load large stream arrays.
        streams=[dict(row) for row in store.connection.execute('''SELECT s.source_id,s.summary_source_id,
            s.observation_sha256,s.mapping_version FROM strava_stream_sources s
            JOIN strava_stream_current c ON c.source_id=s.source_id WHERE s.activity_id=? ORDER BY s.source_id''',
            (snapshot['activity']['activity_id'],))]
        if streams:
            inputs.append(dict(api_streams=streams))
    return sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def api_candidate(store, snapshot, result):
    """Strict v2 fallback; columns remain native-only, API provenance is explicit."""
    from .strava_streams import review_best20
    summaries=[e for e in snapshot['sources'] if e['source']['kind']=='strava_api' and e['source']['is_current']]
    if not summaries:
        return result  # Preserve existing no-file/no-native reasons for non-API history.
    result['reason']='api_power_stream_unavailable'
    if len(summaries)!=1:
        result['reason']='api_current_source_ambiguous';return result
    summary=summaries[0]
    observations=[s for s in store.strava_stream_evidence(result['activity_id']) if s['is_current']]
    if len(observations)!=1:
        if observations:result['reason']='api_current_source_ambiguous'
        return result
    observed=observations[0];streams=observed['streams']
    result['api_evidence']=dict(evidence_kind='Strava API stream',stream_source_id=observed['source_id'],
        summary_source_id=summary['source']['source_id'],related_summary_source_id=observed['summary_source_id'],
        observation_sha256=observed['observation_sha256'],mapping_version=observed['mapping_version'],
        device_watts=summary['summary']['values'].get('device_watts'),start_date=observed['start_date'],
        metadata=observed['metadata'])
    if not observed['summary_compatible'] or observed['current_summary_source_id'] != summary['source']['source_id']:
        result['reason']='api_stream_summary_not_current';return result
    if 'watts' not in streams or 'time' not in streams:return result
    time,watts=streams['time'],streams['watts']
    if summary['summary']['values'].get('device_watts') is not True:
        result['reason']='api_device_watts_not_confirmed';return result
    if any(s['resolution']!='high' for s in (time,watts)):
        result['reason']='api_stream_not_high_resolution';return result
    if any(s['original_size']!=len(s['data']) for s in (time,watts)):
        result['reason']='api_stream_not_full_length';return result
    if len(time['data'])!=len(watts['data']):
        result['reason']='api_stream_length_mismatch';return result
    offsets=time['data']
    if (any(type(t) is not int or t<0 for t in offsets)
            or any(b<=a for a,b in zip(offsets,offsets[1:]))):
        result['reason']='api_stream_invalid_timing';return result
    # The retained stream contract permits only nonnegative exact integer watts/null.
    if any(v is not None and (type(v) is not int or v<0) for v in watts['data']):
        result['reason']='api_stream_invalid_power';return result
    best=review_best20(observed)
    if best['status']!='available':
        result['reason']={'no_complete_one_second_window':'no_complete_timestamp_contiguous_window',
                          'incomplete_power':'no_complete_power_window',
                          'signal_time_pairing_ambiguous':'api_stream_pairing_ambiguous'}.get(best['reason'],best['reason'])
        return result
    result.update({k:best[k] for k in ('average_watts','rounded_watts','start_offset','end_exclusive_offset',
                                      'sample_count','eligible_window_count')})
    result.update(eligible=True,status='eligible',reason=None,content_format='Strava API stream')
    return result


def evaluate(store, snapshot):
    activity_id = snapshot['activity']['activity_id']
    cohort = classification(snapshot)
    result = dict(activity_id=activity_id, policy=POLICY, method=BEST_20_METHOD,
                  duration_seconds=WINDOW_SAMPLES, classification=cohort,
                  status='ineligible', reason=None, eligible=False,
                  source_id=None, extraction_id=None, candidates=[])
    kind = cohort['activity_type']
    if kind != 'Virtual Ride':
        result['reason'] = ('outdoor_ride_excluded' if kind == 'Ride' else
                            'ambiguous_classification' if cohort['basis'] == 'conflicting_native_classification'
                            else 'non_virtual_activity' if kind else 'classification_unavailable')
        return result
    files = [e for e in snapshot['sources'] if e['source']['kind'] not in ('strava_export','strava_api')]
    eligible = []
    for metadata in files:
        source, extraction = metadata['source'], metadata['extraction']
        if not extraction or not extraction.get('extraction_id'):
            raise IntegrityError('Performance candidate has no current extraction')
        candidate = dict(source_id=source['source_id'], extraction_id=extraction['extraction_id'],
                         content_format=source['content_format'], eligible=False, reason='no_native_power')
        counts = store.connection.execute('SELECT COUNT(*), COUNT(power) FROM records WHERE extraction_id=?',
                                           (extraction['extraction_id'],)).fetchone()
        if tuple(counts) != (extraction['record_count'], extraction['power_present']):
            raise IntegrityError('Native record counts do not match current extraction')
        if extraction['power_present']:
            native = store.get_source(source['source_id'])
            records = native['records']
            if len(records) != extraction['record_count'] or sum(r['power'] is not None for r in records) != extraction['power_present']:
                raise IntegrityError('Native record counts do not match current extraction')
            # Naive timestamps are known unsupported timing, not guessed UTC.
            # Malformed timestamps/negative or invalid power remain fatal defects.
            try:
                timestamps = [datetime.fromisoformat(r['timestamp']) for r in records if r['timestamp'] is not None]
            except (ValueError, TypeError) as exc:
                raise IntegrityError('Invalid timestamp in current native extraction') from exc
            if any(r['power'] is not None and (not isinstance(r['power'], int) or r['power'] < 0) for r in records):
                raise IntegrityError('Unexpected native power in performance candidate')
            if any(t.tzinfo is None for t in timestamps):
                candidate['reason'] = 'native_timestamp_timezone_unknown'
            else:
                best = best_20_minute_power(records, activity_id=activity_id,
                                           source_id=source['source_id'], extraction_id=extraction['extraction_id'])
                candidate.update(eligible=best['eligible'], reason=best['reason'])
                if best['eligible']:
                    eligible.append(best | dict(content_format=source['content_format']))
        result['candidates'].append(candidate)
    if len(eligible) > 1:
        result['reason'] = 'multiple_eligible_native_sources'
    elif eligible:
        result.update(eligible[0])
        result.update(status='eligible', eligible=True, reason=None)
    else:
        reasons = {c['reason'] for c in result['candidates']}
        result['reason'] = (next(iter(reasons)) if len(reasons) == 1 else
                            'no_eligible_native_source' if reasons else 'no_native_file_source')
        if not file_power_present(snapshot):
            result=api_candidate(store,snapshot,result)
    return result


def rebuild_performance(store):
    """One serialized snapshot, atomic replacement; fatal failure preserves history."""
    totals, kinds, formats = Counter(), Counter(), Counter()
    calculated_at = datetime.now(timezone.utc).isoformat()
    with store._transaction(write=True):
        _check_extractions(store)
        snapshots = store.activity_history()
        rows = []
        for snapshot in snapshots:
            result = evaluate(store, snapshot)
            kind = result['classification']['activity_type']
            kinds[kind or 'Unknown'] += 1
            totals[result['reason'] or 'eligible'] += 1
            if result['eligible']:
                formats[result['content_format']] += 1
            rows.append((result['activity_id'], WINDOW_SAMPLES, POLICY, BEST_20_METHOD,
                         result['source_id'], result['extraction_id'], input_signature(snapshot,store),
                         calculated_at, json.dumps(result, sort_keys=True)))
        store.connection.execute('DELETE FROM performance_history WHERE duration_seconds = ? AND policy = ?',
                                 (WINDOW_SAMPLES, POLICY))
        store.connection.executemany('INSERT INTO performance_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', rows)
    return dict(status='completed', evaluated=len(snapshots), virtual_candidates=kinds['Virtual Ride'],
                outdoor_activities=kinds['Ride'], non_cycling_activities=sum(v for k, v in kinds.items() if k not in ('Ride', 'Virtual Ride')),
                eligible=totals['eligible'], ineligible_by_reason={k: v for k, v in sorted(totals.items()) if k != 'eligible'},
                eligible_source_formats=dict(formats), policy=POLICY, method=BEST_20_METHOD,
                duration_seconds=WINDOW_SAMPLES)


def performance_history(store):
    """Current metadata/results only. Changed inputs are explicitly stale, never plotted."""
    with store._transaction():
        _check_extractions(store)
        snapshots = {s['activity']['activity_id']: s for s in store.activity_history()}
        saved = store.connection.execute('SELECT * FROM performance_history WHERE duration_seconds = ? AND policy = ? AND method = ?',
                                         (WINDOW_SAMPLES, POLICY, BEST_20_METHOD)).fetchall()
        results, points = [], []
        stale = 0
        for record in saved:
            snapshot = snapshots[record['activity_id']]
            if input_signature(snapshot,store) != record['input_signature']:
                stale += 1
                continue
            result = json.loads(record['result_json'])
            result['calculated_at'] = record['calculated_at']
            row = presentation(snapshot)
            result['date_available'] = row['date_key'] is not None
            results.append(result)
            if result['eligible'] and row['date_key'] is not None:
                points.append(dict(activity_id=row['activity_id'], title=row['title'], start_time=row['start_time'],
                                   date_day=row['date_day'], date_key=row['date_key'], absolute_time=row['absolute_time'],
                                   average_watts=result['average_watts'], rounded_watts=result['rounded_watts'],
                                   source_id=result['source_id'], extraction_id=result['extraction_id'],
                                   content_format=result['content_format'], classification=result['classification'],
                                   start_timestamp=result.get('start_timestamp'), end_exclusive_timestamp=result.get('end_exclusive_timestamp'),
                                   **({k:result[k] for k in ('api_evidence','start_offset','end_exclusive_offset')} if 'api_evidence' in result else {})))
        points.sort(key=lambda p: (p['date_key'], p['activity_id']))
        return dict(points=points, results=results, evaluated=len(snapshots), current=len(results),
                    pending=len(snapshots) - len(results), stale=stale,
                    missing_dates=sum(r['eligible'] and not r['date_available'] for r in results),
                    policy=POLICY, method=BEST_20_METHOD)


def converge_performance(store):
    """Post-sync convergence; failure cannot undo committed source/checkpoint writes."""
    import sqlite3
    from .errors import RideWorksError
    try:
        history=performance_history(store)
        if history['pending']==0:
            return dict(performance_update='current',performance_pending=0,performance_eligible=len(history['points']))
        rebuilt=rebuild_performance(store)
        return dict(performance_update='updated',performance_pending=0,performance_eligible=rebuilt['eligible'])
    except (RideWorksError,OSError,sqlite3.Error):
        return dict(performance_update='incomplete')  # Fixed safe state; no private exception text.
