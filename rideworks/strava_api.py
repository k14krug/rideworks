"""Allowlisted API observations and conservative source association; no streams."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from uuid import uuid4

from .errors import RideWorksError
from .history import presentation

MAPPING = 'strava-summary-v1'
OVERLAP_DAYS = 3
TEXT = {'name','type','sport_type','start_date','start_date_local','timezone','external_id','gear_id','visibility'}
NUMBERS = {'utc_offset','elapsed_time','moving_time','distance','total_elevation_gain','workout_type',
           'upload_id','average_watts','weighted_average_watts','kilojoules','max_watts',
           'average_heartrate','max_heartrate','average_cadence','suffer_score'}
BOOLEANS = {'trainer','commute','manual','device_watts','private','has_heartrate'}
FIELDS = TEXT | NUMBERS | BOOLEANS | {'id'}


class SyncError(RideWorksError):
    """Fixed safe messages only: response payloads/credentials never enter errors."""


def absolute(value):
    try:
        stamp = datetime.fromisoformat(value.replace('Z','+00:00'))
        if stamp.tzinfo is None:
            raise ValueError
        return stamp.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError, OverflowError):
        raise SyncError('Strava activity has no valid absolute start date') from None


def normalize(observation):
    if not isinstance(observation,dict) or type(observation.get('id')) is not int or observation['id'] <= 0:
        raise SyncError('Invalid Strava SummaryActivity identity')
    values = {k:v for k,v in observation.items() if k in FIELDS}
    for k,v in values.items():
        if v is None:
            continue
        valid = (isinstance(v,str) and len(v)<=4096 if k in TEXT else
                 type(v) in (int,float) and math.isfinite(v) if k in NUMBERS else
                 type(v) is bool if k in BOOLEANS else type(v) is int)
        if not valid:
            raise SyncError('Invalid Strava SummaryActivity field shape')
    absolute(values.get('start_date'))
    if not (values.get('sport_type') or values.get('type')):
        raise SyncError('Strava SummaryActivity classification is missing')
    for k in ('elapsed_time','moving_time','distance','total_elevation_gain','suffer_score'):
        if values.get(k) is not None and values[k] < 0:
            raise SyncError('Invalid negative Strava activity summary')
    return values


def activity_type(values):
    sport = values.get('sport_type') or values.get('type')
    if sport == 'VirtualRide':
        return 'Virtual Ride'
    if values.get('type') == 'Ride' or sport in ('Ride','MountainBikeRide','GravelRide','EBikeRide','EMountainBikeRide'):
        return 'Ride'
    return values.get('type') or sport


def sync_window(store, athlete_id, now):
    checkpoint = store.connection.execute('SELECT * FROM strava_sync_state WHERE singleton=1').fetchone()
    if checkpoint:
        if checkpoint['athlete_id'] != str(athlete_id):
            raise SyncError('This store belongs to a different connected Strava athlete; reconnect the original account')
        after = checkpoint['successful_at'] - OVERLAP_DAYS*86400
        basis = 'last_successful_sync_minus_3_days'
    else:
        days = []
        for row in store.connection.execute('SELECT evidence_json FROM strava_export_sources'):
            parsed = json.loads(row[0]).get('date_parsed')
            if parsed:
                try: days.append(datetime.fromisoformat(parsed).date())
                except ValueError: raise SyncError('Stored export boundary date is invalid') from None
        if not days:
            raise SyncError('No safe Strava-export boundary exists; sync stopped without historical fallback')
        boundary = datetime.combine(max(days),datetime.min.time(),tzinfo=timezone.utc)
        after = int((boundary-timedelta(days=OVERLAP_DAYS)).timestamp())
        basis = 'latest_export_calendar_day_utc_minus_3_days'
    if after >= now or after < 0:
        raise SyncError('Stored sync boundary is incompatible with the current time')
    return dict(after=after,before=now,window_basis=basis,overlap_days=OVERLAP_DAYS)


def _strong_candidates(store, values):
    """Exact start, classification and duration, with distance when supplied."""
    candidates = set()
    stamp = absolute(values['start_date'])
    kind = activity_type(values)
    for snapshot in store.activity_history():
        identity = snapshot['activity']['activity_id']
        # A different established upstream identity cannot be silently reassigned.
        if any(e['source']['kind'] in ('strava_export','strava_api') for e in snapshot['sources']):
            continue
        row = presentation(snapshot)
        if not row['absolute_time'] or absolute(row['start_time']) != stamp or row['activity_type'] != kind:
            continue
        duration = values.get('elapsed_time')
        if duration is None or row['duration'] is None or abs(duration-row['duration']) > 1:
            continue
        if values.get('distance') is not None and row['distance'] is not None and abs(values['distance']-row['distance']) > 1:
            continue
        candidates.add(identity)
    return candidates


def apply_observations(store, observations, athlete_id, successful_at, *, established_targets=None, expected_current_sources=None):
    """Atomic observations; targeted maintenance must preserve the sync checkpoint."""
    if established_targets is not None and successful_at is not None:
        raise SyncError('Targeted enrichment cannot advance the forward-sync checkpoint')
    totals = dict(new_activities=0,existing_activities_enriched=0,unchanged_observations=0,
                  changed_observations=0,new_observations=0,ambiguous_new_associations=0,
                  strong_local_matches=0,performance_rebuild_recommended=0)
    touched = set()
    with store._transaction(write=True):
        checkpoint = store.connection.execute('SELECT * FROM strava_sync_state WHERE singleton=1').fetchone()
        if checkpoint and checkpoint['athlete_id'] != str(athlete_id):
            raise SyncError('Connected Strava athlete differs from the stored checkpoint')
        for values in observations:
            external = str(values['id'])
            established = {r[0] for r in store.connection.execute('SELECT DISTINCT activity_id FROM strava_export_sources WHERE external_id=?',(external,))}
            previous = store.connection.execute('SELECT * FROM strava_api_activities WHERE external_id=?',(external,)).fetchone()
            if expected_current_sources is not None and (previous is None or
                    previous['current_source_id'] != expected_current_sources.get(external)):
                raise SyncError('Targeted summary changed during preflight; retry refresh')
            if previous:
                established.add(previous['activity_id'])
            if len(established)>1:
                raise SyncError('Conflicting established Strava identities; no Activities were merged')
            if established_targets is not None:
                if external not in established_targets or established != {established_targets[external]}:
                    raise SyncError('Targeted summary does not match its established Activity')
            matches = set() if established else _strong_candidates(store,values)
            created = not established and len(matches)!=1
            identity = next(iter(established or matches)) if not created else str(uuid4())
            basis = ('established_strava_identity' if established else
                     'exact_start_type_duration_distance' if len(matches)==1 else
                     'ambiguous_local_match_new_activity' if matches else 'new_api_activity')
            if created:
                store.connection.execute('INSERT INTO activities VALUES (?,?)',(identity,datetime.now(timezone.utc).isoformat()))
                totals['new_activities']+=1
                totals['ambiguous_new_associations']+=bool(matches)
            elif matches:
                totals['strong_local_matches']+=1
            encoded = json.dumps(values,sort_keys=True,ensure_ascii=True,allow_nan=False)
            digest = sha256(encoded.encode()).hexdigest()
            existing = store.connection.execute('SELECT * FROM strava_api_sources WHERE external_id=? AND observation_sha256=?',(external,digest)).fetchone()
            source_id = existing['source_id'] if existing else str(uuid4())
            unchanged = previous is not None and previous['current_source_id']==source_id
            if unchanged:
                totals['unchanged_observations']+=1
                continue
            if existing and existing['activity_id'] != identity:
                raise SyncError('Conflicting API Source association; sync stopped')
            if not existing:
                store.connection.execute('INSERT INTO strava_api_sources VALUES (?,?,?,?,?,?,?,?)',
                    (source_id,identity,external,digest,basis,datetime.now(timezone.utc).isoformat(),MAPPING,encoded))
                totals['new_observations']+=1
            if previous:
                totals['changed_observations']+=1
            if not created:
                totals['existing_activities_enriched']+=1
            store.connection.execute('INSERT INTO strava_api_activities VALUES (?,?,?) ON CONFLICT(external_id) DO UPDATE SET current_source_id=excluded.current_source_id',
                                     (external,identity,source_id))
            touched.add(identity)
        if touched:
            totals['performance_rebuild_recommended'] = sum(bool(store.connection.execute('SELECT 1 FROM performance_history WHERE activity_id=?',(identity,)).fetchone()) for identity in touched)
        if established_targets is None:
            store.connection.execute('INSERT INTO strava_sync_state VALUES (1,?,?) ON CONFLICT(singleton) DO UPDATE SET athlete_id=excluded.athlete_id,successful_at=excluded.successful_at',
                                     (str(athlete_id),successful_at))
    return totals
