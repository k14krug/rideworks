"""Owner-selected Strava segment efforts and bounded checks of newly synced rides."""
from dataclasses import dataclass
from html import escape
import re
import sqlite3
from urllib.parse import urlencode, urlsplit

from .strava import ApiError, AuthenticationError, TokenFile, exhausted, refreshed_connection
from .strava_api import SyncError, absolute

CHECK_BUDGET = 5
ID_PATTERN = '[1-9][0-9]{0,18}'
MAX_ID = 2**63 - 1


@dataclass(frozen=True)
class Effort:
    effort_id: str
    segment_id: str
    name: str
    start_time: str
    elapsed_seconds: int


def exact_id(value):
    if type(value) is not int or not 0 < value <= MAX_ID:
        raise SyncError('Strava returned an invalid identifier.')
    return str(value)


def link_ids(value):
    message = 'Paste a Strava activity-effort link from a Zwift ride. Standalone segment links are unsupported.'
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        raise SyncError(message) from None
    if parts.scheme == 'https' and parts.netloc in ('www.strava.com', 'strava.com'):
        pair = re.fullmatch(fr'/activities/({ID_PATTERN})/segments/({ID_PATTERN})/?', parts.path)
        ride = re.fullmatch(fr'/activities/({ID_PATTERN})/?', parts.path)
        if pair:
            return tuple(exact_id(int(value)) for value in pair.groups())
        if ride and re.fullmatch(ID_PATTERN, parts.fragment):
            return exact_id(int(ride[1])), exact_id(int(parts.fragment))
    raise SyncError(message)


def zwift_summary(values):
    """Require virtual cycling and upstream Zwift provenance for automatic capture."""
    return (values.get('sport_type') == 'VirtualRide'
            and re.search(r'\bzwift\b|^zwift(?=[_-])', values.get('external_id') or '', re.I) is not None)


def read_efforts(detail, activity_id, athlete_id):
    if (not isinstance(detail, dict) or detail.get('resource_state') != 3
            or exact_id(detail.get('id')) != activity_id
            or not isinstance(detail.get('athlete'), dict)
            or exact_id(detail['athlete'].get('id')) != athlete_id
            or detail.get('sport_type') != 'VirtualRide'
            or not (zwift_summary(detail) or str(detail.get('device_name', '')).strip().casefold() == 'zwift')
            or not isinstance(detail.get('segment_efforts'), list)):
        raise SyncError('Strava did not return complete effort detail for a verified Zwift ride.')
    attempts = {}
    for row in detail['segment_efforts']:
        if (not isinstance(row, dict)
                or any(not isinstance(row.get(key), dict) for key in ('athlete', 'activity', 'segment'))
                or exact_id(row['athlete'].get('id')) != athlete_id
                or exact_id(row['activity'].get('id')) != activity_id):
            raise SyncError('Strava returned an effort with unverified ownership or ride linkage.')
        effort_id = exact_id(row.get('id'))
        segment_id = exact_id(row['segment'].get('id'))
        name = row['segment'].get('name') or row.get('name')
        elapsed = row.get('elapsed_time')
        if (effort_id in attempts or not isinstance(name, str) or not name.strip()
                or len(name) > 500 or type(elapsed) is not int or not 0 < elapsed <= MAX_ID):
            raise SyncError('Strava returned an incomplete or duplicate segment effort.')
        attempts[effort_id] = Effort(effort_id, segment_id, name.strip(),
                                     absolute(row.get('start_date')).isoformat(), elapsed)
    return attempts


def save_effort(store, activity_id, effort):
    fields = (effort.segment_id, activity_id, effort.start_time, effort.elapsed_seconds)
    previous = store.connection.execute(
        'SELECT segment_id, external_activity_id FROM strava_saved_efforts WHERE effort_id=?',
        (effort.effort_id,),
    ).fetchone()
    if previous and tuple(previous) != fields[:2]:
        raise SyncError('This Strava effort conflicts with its saved segment or ride.')
    store.connection.execute(
        'INSERT INTO strava_saved_efforts VALUES (?, ?, ?, ?, ?) ON CONFLICT(effort_id) DO NOTHING',
        (effort.effort_id, *fields),
    )


def add_selected_effort(store, client, link):
    activity_id, effort_id = link_ids(link)
    tokens = TokenFile(store.data_dir)
    with tokens.lock():
        auth = refreshed_connection(tokens, client)
        athlete_id = exact_id(auth.get('athlete_id'))
        saved_owners = store.connection.execute(
            'SELECT athlete_id FROM strava_sync_state UNION SELECT athlete_id FROM strava_watched_segments'
        )
        if any(row[0] != athlete_id for row in saved_owners):
            raise SyncError('Connect the Strava athlete who owns this RideWorks store.')
        detail = client.activity_detail(auth['access_token'], activity_id)
        effort = read_efforts(detail, activity_id, athlete_id).get(effort_id)
        if effort is None:
            raise SyncError('The selected effort was not present in this ride’s Strava detail.')
        with store._transaction(write=True):
            store.connection.execute(
                'INSERT INTO strava_watched_segments VALUES (?, ?, ?) ON CONFLICT(segment_id) DO NOTHING',
                (effort.segment_id, athlete_id, effort.name),
            )
            save_effort(store, activity_id, effort)


def check_pending(store, client, auth, *, stop=None):
    athlete_id = str(auth['athlete_id'])
    watched = {row[0] for row in store.connection.execute(
        'SELECT segment_id FROM strava_watched_segments WHERE athlete_id=?', (athlete_id,))}
    if not watched:
        return {}
    pending = store.connection.execute(
        'SELECT external_activity_id FROM strava_pending_segment_rides WHERE athlete_id=? '
        'ORDER BY attempts, rowid LIMIT ?', (athlete_id, CHECK_BUDGET),
    ).fetchall()
    failed = checked = 0
    for (activity_id,) in pending:
        if stop or exhausted(client.rate):
            stop = stop or 'rate_limit'
            break
        try:
            # The shared Sync fetches summaries and streams, neither of which
            # includes complete efforts. Check each pending ride once per run.
            detail = client.activity_detail(auth['access_token'], activity_id)
            efforts = read_efforts(detail, activity_id, athlete_id)
            with store._transaction(write=True):
                for effort in efforts.values():
                    if effort.segment_id in watched:
                        save_effort(store, activity_id, effort)
                store.connection.execute('DELETE FROM strava_pending_segment_rides WHERE external_activity_id=?',
                                         (activity_id,))
            checked += 1
        except (SyncError, OSError, sqlite3.Error) as error:
            failed += 1
            store.connection.execute('UPDATE strava_pending_segment_rides SET attempts=attempts+1 WHERE external_activity_id=?',
                                     (activity_id,))
            if isinstance(error, AuthenticationError) or isinstance(error, ApiError) and error.status == 403:
                stop = 'authorization'
            elif isinstance(error, ApiError) and error.status == 429:
                stop = 'rate_limit'
    remaining = store.connection.execute(
        'SELECT COUNT(*) FROM strava_pending_segment_rides WHERE athlete_id=?', (athlete_id,),
    ).fetchone()[0]
    return dict(segment_pending=remaining, segment_checked=checked, segment_failed=failed,
                segment_stop=stop if remaining else None)


def pending_message(result):
    if result.get('segment_stop') == 'local_error':
        return 'Tracked segment checks could not finish. Run Sync now later to retry.'
    count = result.get('segment_pending', 0)
    if not count:
        return ''
    reason = {'rate_limit': 'Strava rate limit reached. ', 'authorization': 'Check your Strava connection in Settings. '}.get(
        result.get('segment_stop'), '')
    if result.get('segment_failed') and not reason:
        reason = 'Some effort checks failed. '
    return f'Tracked segment checks pending for {count} {"ride" if count == 1 else "rides"}. {reason}Run Sync now later to retry.'


def tracked_counts(store, activity_ids):
    if not activity_ids:
        return {}
    marks = ','.join('?' for _ in activity_ids)
    return dict(store.connection.execute(
        'SELECT l.activity_id, COUNT(DISTINCT e.segment_id) FROM strava_segment_history e '
        'JOIN strava_saved_effort_ride_links l USING (external_activity_id) '
        f'WHERE l.activity_id IN ({marks}) GROUP BY l.activity_id',
        activity_ids,
    ).fetchall())


def tracked_link(activity_id, count):
    if not count:
        return ''
    href = escape('/segments?' + urlencode({'ride': activity_id}), quote=True)
    return f'<a class="tracked-segment-link" href="{href}">{count} tracked {"segment" if count == 1 else "segments"}</a>'
