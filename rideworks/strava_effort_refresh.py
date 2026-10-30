"""Explicit, bounded refresh of recent established Strava activity summaries."""
import json
import time

from .strava import TokenFile, refreshed_connection
from .strava_api import SyncError, absolute, activity_type, apply_observations, normalize
from .strava_streams import score_only_equal
from .performance import converge_performance
from .power_curve import converge_curves

MAX_ACTIVITIES = 30
LOOKBACK_DAYS = 60


def refresh_recent(store, client, *, now=None):
    timestamp = int(time.time()) if now is None else now
    candidates = []
    for row in store.connection.execute('''
        SELECT a.external_id, a.activity_id, a.current_source_id, s.evidence_json
        FROM strava_api_activities a JOIN strava_api_sources s
        ON s.source_id=a.current_source_id AND s.activity_id=a.activity_id
        AND s.external_id=a.external_id
    '''):
        values = json.loads(row['evidence_json'])
        start = int(absolute(values.get('start_date')).timestamp())
        if (timestamp - LOOKBACK_DAYS * 86400 < start < timestamp and
                activity_type(values) in ('Ride', 'Virtual Ride')):
            candidates.append((start, row['external_id'], row['activity_id'], row['current_source_id'], values))
    candidates.sort(reverse=True)
    candidates = candidates[:MAX_ACTIVITIES]
    tokens = TokenFile(store.data_dir)
    with tokens.lock():
        current = tokens.read()
        checkpoint = store.connection.execute('SELECT athlete_id FROM strava_sync_state WHERE singleton=1').fetchone()
        if checkpoint and checkpoint[0] != str(current['athlete_id']):
            raise SyncError('Connected Strava athlete differs from the stored checkpoint')
        if not candidates:
            return dict(status='completed', activity_requests=0, observations=0, skipped_non_score_changes=0, rate_limits={})
        current = refreshed_connection(tokens, client, now=timestamp)
        observations, targets, expected = [], {}, {}
        skipped = 0
        for _, external, identity, source_id, stored in candidates:
            payload = client.activity_summary(current['access_token'], external)
            if isinstance(payload, dict) and 'athlete' in payload:
                if not isinstance(payload['athlete'], dict) or payload['athlete'].get('id') != current['athlete_id']:
                    raise SyncError('Strava activity belongs to an unexpected athlete')
            values = normalize(payload)
            if str(values['id']) != external:
                raise SyncError('Targeted response identity differs from the established ride')
            if not score_only_equal(stored, values):
                skipped += 1
                continue
            observations.append(values)
            targets[external] = identity
            expected[external] = source_id
        result = apply_observations(store, observations, current['athlete_id'], None,
                                    established_targets=targets, expected_current_sources=expected)
    return dict(status='completed', activity_requests=len(candidates),
                observations=len(observations), skipped_non_score_changes=skipped,
                rate_limits=dict(client.rate), **result, **converge_performance(store), **converge_curves(store))
