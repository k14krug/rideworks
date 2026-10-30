"""Strict allowlist validation of Strava stream observations; no native conversion."""
from .strava import STREAM_KEYS
from .strava_api import SyncError

MAPPING = 'strava-stream-observation-v1'


def score_only_equal(left, right):
    """Compare complete normalized summaries, ignoring only vendor effort."""
    return ({k: v for k, v in left.items() if k != 'suffer_score'} ==
            {k: v for k, v in right.items() if k != 'suffer_score'})


def parse_streams(payload):
    if not isinstance(payload, dict):
        raise SyncError('Invalid Strava stream set')
    result = {}
    for key in STREAM_KEYS:
        if key not in payload:
            continue
        stream = payload[key]
        if (not isinstance(stream, dict) or stream.get('type', key) != key
                or stream.get('resolution') not in ('low', 'medium', 'high')
                or stream.get('series_type') not in ('time', 'distance')
                or type(stream.get('original_size')) is not int or stream['original_size'] < 0
                or not isinstance(stream.get('data'), list)):
            raise SyncError('Invalid Strava stream metadata')
        values = stream['data']
        for value in values:
            if value is None and key != 'time':
                continue  # Missing stays missing, distinct from zero.
            if key == 'moving':
                valid = type(value) is bool
            else:
                valid = type(value) is int and 0 <= value <= 2**53-1  # Exact integer representation in browser JSON.
            if not valid:
                raise SyncError('Invalid Strava stream data')
        result[key] = {field: stream[field] for field in ('data', 'original_size', 'resolution', 'series_type')}
    return result


def chart_reason(streams):
    """Pair only explicitly compatible arrays; gaps stay gaps, no repaired samples."""
    time = streams.get('time')
    if time is None or not time['data']:
        return 'time_missing'
    if any(b <= a for a, b in zip(time['data'], time['data'][1:])):
        return 'time_not_strictly_increasing'
    available = []
    for key in ('watts', 'heartrate'):
        signal = streams.get(key)
        if signal is None:
            continue
        if (len(signal['data']) != len(time['data'])
                or any(signal[field] != time[field] for field in ('original_size','resolution','series_type'))):
            return 'signal_time_pairing_ambiguous'
        if any(v is not None for v in signal['data']):
            available.append(key)
    return None if available else 'power_and_hr_missing'


def review_best20(observation):
    """On-demand ride-local API result; returned offsets, no native conversion/write.

    Match best-average-power-v1 using rolling integer sums and exact timing edges.
    The independent Stage A prefix-sum verifier remains a separate oracle.
    """
    from .analysis import BEST_20_METHOD, WINDOW_SAMPLES
    streams = observation['streams']
    result = dict(source_id=observation['source_id'], summary_source_id=observation['summary_source_id'],
                  origin='calculated', evidence_kind='Strava API stream evidence', method=BEST_20_METHOD,
                  duration_seconds=WINDOW_SAMPLES, status='unavailable', reason=None,
                  sample_count=None, eligible_window_count=0, start_offset=None,
                  end_exclusive_offset=None, average_watts=None, rounded_watts=None)
    time, watts = streams.get('time'), streams.get('watts')
    if watts is None:
        result['reason'] = 'watts_stream_missing'
        return result
    if time is None:
        result['reason'] = 'time_missing'
        return result
    offsets, powers = time['data'], watts['data']
    if (len(offsets) != len(powers)
            or any(time[field] != watts[field] for field in ('original_size', 'resolution', 'series_type'))):
        result['reason'] = 'signal_time_pairing_ambiguous'
        return result
    if len(offsets) < WINDOW_SAMPLES:
        result['reason'] = 'activity_shorter_than_required'
        return result
    bad_edges = [0] + [int(b-a != 1) for a,b in zip(offsets,offsets[1:])]
    total = missing = bad_timing = timestamp_windows = 0
    best_total = best_start = None
    for end, power in enumerate(powers):
        total += power if power is not None else 0
        missing += power is None
        bad_timing += bad_edges[end]
        if end >= WINDOW_SAMPLES:
            leaving = powers[end-WINDOW_SAMPLES]
            total -= leaving if leaving is not None else 0
            missing -= leaving is None
            bad_timing -= bad_edges[end-WINDOW_SAMPLES+1]
        if end < WINDOW_SAMPLES-1 or bad_timing:
            continue
        timestamp_windows += 1
        if missing:
            continue
        result['eligible_window_count'] += 1
        if best_total is None or total > best_total:
            best_total, best_start = total, end-WINDOW_SAMPLES+1
    if best_start is None:
        result['reason'] = ('no_complete_one_second_window' if not timestamp_windows else 'incomplete_power')
        return result
    result.update(status='available', sample_count=WINDOW_SAMPLES,
                  start_offset=offsets[best_start], end_exclusive_offset=offsets[best_start]+WINDOW_SAMPLES,
                  average_watts=best_total/WINDOW_SAMPLES,
                  rounded_watts=(best_total+WINDOW_SAMPLES//2)//WINDOW_SAMPLES)
    return result


REASONS = {
    'not_fetched': 'Strava stream evidence has not been fetched yet.',
    'start_context_changed': 'Strava start-date evidence changed after the stream fetch. Retry with a later Sync now.',
    'time_missing': 'No usable Strava time stream was returned.',
    'time_not_strictly_increasing': 'Strava time offsets are duplicate or backward; chart pairing is unavailable.',
    'signal_time_pairing_ambiguous': 'Strava signal arrays cannot be paired with time without assumptions.',
    'power_and_hr_missing': 'Strava returned no usable power or heart-rate stream.',
    'fetch_failed': 'Strava stream fetch failed. Retry with a later manual Sync now.',
    'rate_limited': 'Strava stream enrichment stopped at a rate limit. Retry with a later manual Sync now.',
    'authorization': 'Strava stream authorization needs attention; reconnect before another manual sync.',
    'not_found': 'Strava did not make streams available for this Activity.',
}


def persist(store, external_id, payload, *, retrieved_at=None):
    from datetime import datetime, timezone
    from hashlib import sha256
    import json
    from uuid import uuid4
    streams = parse_streams(payload)
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat()
    content = json.dumps(streams, sort_keys=True, separators=(',', ':'), allow_nan=False)
    digest = sha256((MAPPING+'\n'+content).encode()).hexdigest()
    reason = chart_reason(streams)
    with store._transaction(write=True):
        identity = store.connection.execute('SELECT * FROM strava_api_activities WHERE external_id=?', (str(external_id),)).fetchone()
        if identity is None:
            raise SyncError('Stream observation has no established Strava Activity')
        summary = identity['current_source_id']
        existing = store.connection.execute('''SELECT source_id FROM strava_stream_sources
            WHERE external_id=? AND summary_source_id=? AND observation_sha256=?''', (str(external_id), summary, digest)).fetchone()
        source_id = existing[0] if existing else str(uuid4())
        if existing is None:
            store.connection.execute('INSERT INTO strava_stream_sources VALUES(?,?,?,?,?,?,?,?,?)',
                (source_id,identity['activity_id'],str(external_id),summary,digest,timestamp,MAPPING,json.dumps(list(STREAM_KEYS)),content))
        store.connection.execute('''INSERT INTO strava_stream_current VALUES(?,?)
            ON CONFLICT(external_id) DO UPDATE SET source_id=excluded.source_id''', (str(external_id),source_id))
        attempt(store,external_id,'fetched' if reason is None else 'unavailable',reason or 'usable',timestamp=timestamp)
    return dict(new_stream_observation=existing is None,usable=reason is None)


def attempt(store,external_id,outcome,reason,*,timestamp=None):
    from datetime import datetime, timezone
    if reason not in REASONS and reason!='usable':
        raise SyncError('Unsupported stream attempt reason')
    store.connection.execute('''INSERT INTO strava_stream_attempts VALUES(?,?,?,?)
        ON CONFLICT(external_id) DO UPDATE SET attempted_at=excluded.attempted_at,outcome=excluded.outcome,reason=excluded.reason''',
        (str(external_id),timestamp or datetime.now(timezone.utc).isoformat(),outcome,reason))


def evidence(store,activity_id):
    import json
    results=[]
    for row in store.connection.execute('''SELECT s.*, c.source_id=s.source_id AS is_current, j.evidence_json AS summary_json, latest.evidence_json AS current_summary_json, a.current_source_id AS current_summary_source_id
        FROM strava_stream_sources s JOIN strava_stream_current c ON c.external_id=s.external_id
        JOIN strava_api_sources j ON j.source_id=s.summary_source_id AND j.external_id=s.external_id AND j.activity_id=s.activity_id
        JOIN strava_api_activities a ON a.external_id=s.external_id AND a.activity_id=s.activity_id
        JOIN strava_api_sources latest ON latest.source_id=a.current_source_id AND latest.external_id=a.external_id AND latest.activity_id=a.activity_id WHERE s.activity_id=? ORDER BY s.retrieved_at,s.source_id''',(activity_id,)):
        value=dict(row);streams=json.loads(value.pop('evidence_json'));summary=json.loads(value.pop('summary_json'))
        from .strava_api import absolute
        current_summary=json.loads(value.pop('current_summary_json'))
        reason=chart_reason(streams)
        if absolute(summary['start_date'])!=absolute(current_summary['start_date']):reason='start_context_changed'
        value.update(summary_compatible=score_only_equal(summary, current_summary),
                     requested=json.loads(value.pop('requested_json')),streams=streams,start_date=summary['start_date'],
                     metadata={key:{field:stream[field] for field in ('original_size','resolution','series_type')}|dict(returned_length=len(stream['data'])) for key,stream in streams.items()},
                     chart_unavailable_reason=reason)
        results.append(value)
    return results


def api_only_candidates(store):
    """No file/export source: stream review cannot displace supported file evidence."""
    from .strava_api import activity_type
    import json
    results=[]
    for row in store.connection.execute('''SELECT a.external_id,a.activity_id,s.evidence_json FROM strava_api_activities a
        JOIN strava_api_sources s ON s.source_id=a.current_source_id
        WHERE NOT EXISTS(SELECT 1 FROM sources f WHERE f.activity_id=a.activity_id)
        AND NOT EXISTS(SELECT 1 FROM strava_export_sources e WHERE e.activity_id=a.activity_id) ORDER BY a.external_id'''):
        values=json.loads(row['evidence_json'])
        if activity_type(values) in ('Ride','Virtual Ride'):
            results.append(dict(external_id=row['external_id'],activity_id=row['activity_id'],start_date=values['start_date']))
    return results


def recent_candidates(store,window):
    from .strava_api import absolute
    return [row['external_id'] for row in api_only_candidates(store)
            if window['after']<absolute(row['start_date']).timestamp()<window['before']]


def enrich(store,client,access_token,external_ids):
    """Explicit sequential fetches; metadata is already committed by the caller.

    Caller holds the existing token lock. Optional absence/failure never undoes metadata.
    Usable persisted streams are reused. Retries occur only on a later explicit sync.
    """
    from .strava import ApiError, AuthenticationError, TokenFile
    import sqlite3
    result=dict(stream_candidates=len(external_ids),stream_fetches=0,stream_enriched=0,stream_reused=0,
                stream_unavailable=0,stream_failed=0,stream_deferred=0,stream_authorization_attention=False,stream_rate_limited=False)
    before=client.stream_requests
    for index,identity in enumerate(external_ids):
        row=store.connection.execute('SELECT activity_id,current_source_id FROM strava_api_activities WHERE external_id=?',(str(identity),)).fetchone()
        if row is None:
            raise SyncError('Stream enrichment requires an established identity')
        current=next((s for s in reversed(evidence(store,row[0])) if s['is_current'] and s['external_id']==str(identity)),None)
        if current and current['chart_unavailable_reason'] is None and current['summary_compatible'] and current['current_summary_source_id']==row['current_source_id']:
            result['stream_reused']+=1;continue
        try:
            payload=client.streams(access_token,identity)
            observation=persist(store,identity,payload)
            result['stream_enriched' if observation['usable'] else 'stream_unavailable']+=1
        except (SyncError,OSError,sqlite3.Error) as error:
            reason='fetch_failed';stop=False
            if isinstance(error,AuthenticationError):
                TokenFile(store.data_dir).clear();reason='authorization';stop=True;result['stream_authorization_attention']=True
            elif isinstance(error,ApiError) and error.status==429:
                reason='rate_limited';stop=True;result['stream_rate_limited']=True
            elif isinstance(error,ApiError) and error.status==404:
                reason='not_found'
            try:attempt(store,identity,'failed',reason)
            except sqlite3.Error:stop=True  # Do not undo committed metadata or issue more fetches when local storage fails.
            result['stream_failed']+=1
            if stop:
                result['stream_deferred']=len(external_ids)-index-1;break
    result['stream_fetches']=client.stream_requests-before
    return result
