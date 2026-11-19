"""Bounded watched-segment history previews and explicit confirmation."""
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import re
from urllib.parse import urlsplit

from .segments import Effort, exact_id, save_effort
from .strava import ApiError, AuthenticationError, TokenFile, exhausted, refreshed_connection
from .strava_api import SyncError, absolute

PAGE_LIMIT = 100
REQUEST_LIMIT = 5
PASTE_LIMIT = 24_000
ROW_LIMIT = 200

MONTHS = {month: i for i, month in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(), 1)}
DAY = r'(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[A-Z][a-z]{2} [0-9]{1,2}, [0-9]{4})'
DURATION = r'(?:[0-9]{1,3}:)?[0-9]{1,3}:[0-9]{2}'
METRIC = r'(?:[0-9]+(?:\.[0-9]+)?\s*(?:mph|km/h|kph|bpm|W(?:svg)?)|[—–-])'
MULTILINE_START = re.compile(fr'[0-9]+\s+.*?\b({DAY})(?:\s+{METRIC})*')


@dataclass(frozen=True)
class PastedRow:
    calendar_day: str
    displayed_seconds: int
    external_activity_id: str | None = None


@dataclass(frozen=True)
class Candidate:
    key: str
    date: str
    seconds: int
    source: str


def watched_segment(store, segment_id):
    row = store.connection.execute('SELECT * FROM strava_watched_segments WHERE segment_id=?', (segment_id,)).fetchone()
    if row is None:
        raise SyncError('Select a watched segment.')
    return row


def day_value(text):
    if '-' in text:
        return date.fromisoformat(text)
    month, day, year = text.replace(',', '').split()
    return date(int(year), MONTHS[month], int(day))


def duration_value(text):
    parts = list(map(int, text.split(':')))
    if parts[-1] >= 60 or len(parts) == 3 and parts[1] >= 60:
        raise ValueError('Invalid duration')
    seconds = sum(part * 60**i for i, part in enumerate(reversed(parts)))
    if not seconds:
        raise ValueError('Duration must be positive')
    return seconds


def activity_link_id(text):
    url = urlsplit(text)
    ride = re.fullmatch(r'/activities/([1-9][0-9]{0,18})/?', url.path)
    if url.scheme != 'https' or url.netloc not in ('strava.com', 'www.strava.com') or not ride or url.fragment:
        raise ValueError('Unsupported activity link')
    return exact_id(int(ride[1]))


def parse_pasted_row(line):
    # Rich clipboard text can arrive as Markdown with linked date and athlete
    # cells. Plain copies typically arrive as tab-separated cells.
    separator = r'\t+|\|' if '|' in line or '\t' in line else r' {2,}'
    cells = [cell.strip() for cell in re.split(separator, line.strip().strip('|'))]
    cells = [cell for cell in cells if cell]
    if len(cells) == 1:
        two = re.fullmatch(fr'({DAY})\s+({DURATION})', cells[0])
        if two:
            cells = list(two.groups())
    if not cells or not re.fullmatch(DURATION, cells[-1]):
        raise ValueError('Expected a final Time cell')
    matches, links = [], []
    for cell in cells[:-1]:
        matched = re.fullmatch(fr'\[({DAY})\]\(([^\s)]+)\)', cell)
        if matched:
            matches.append(matched[1])
            links.append(activity_link_id(matched[2]))
        elif re.fullmatch(DAY, cell):
            matches.append(cell)
        elif cell.startswith(('https://www.strava.com/activities/', 'https://strava.com/activities/')):
            links.append(activity_link_id(cell))
    if len(matches) != 1 or len(set(links)) > 1:
        raise ValueError('Expected one date and at most one activity')
    return PastedRow(day_value(matches[0]).isoformat(), duration_value(cells[-1]), links[0] if links else None)


def parse_paste(text):
    if len(text) > PASTE_LIMIT:
        raise SyncError(f'Paste at most {PASTE_LIMIT:,} characters per batch.')
    rows, invalid = [], []
    pending = None
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or (re.fullmatch(r'[\s|:\-]+', stripped) and '-' in stripped):
            continue
        labels = [cell.strip().casefold() for cell in re.split(r'\t+|\|', stripped) if cell.strip()]
        if ('date' in labels and labels[-1] == 'time'
                or re.fullmatch(r'Rank\s+Name\s+Date\s+Speed\s+HR\s+Power\s+Time', stripped, re.I)):
            if pending:
                invalid.append((pending[0], pending[1][:180]))
                pending = None
            continue
        if pending:
            start, first_line, day = pending
            if re.fullmatch(fr'{METRIC}(?:\s+{METRIC})*', stripped):
                continue
            pending = None
            if re.fullmatch(DURATION, stripped):
                number, line = start, f'{day}\t{stripped}'
                stripped = f'{first_line} · {stripped}'
            else:
                invalid.append((start, first_line[:180]))
        try:
            rows.append(parse_pasted_row(line))
        except (ValueError, KeyError, SyncError):
            start_match = MULTILINE_START.fullmatch(stripped)
            if start_match and len(re.findall(DAY, stripped)) == 1:
                pending = (number, stripped, start_match[1])
            else:
                invalid.append((number, stripped[:180]))
        if len(rows) + len(invalid) + bool(pending) > ROW_LIMIT:
            raise SyncError(f'Paste at most {ROW_LIMIT} rows per batch.')
    if pending:
        invalid.append((pending[0], pending[1][:180]))
    return rows, invalid


def batch_id(segment_id, rows):
    evidence = sorted((r.calendar_day, r.displayed_seconds, r.external_activity_id or '') for r in rows)
    return sha256(json.dumps([segment_id, evidence], separators=(',', ':')).encode()).hexdigest()


def local_ride(store, activity_id):
    if activity_id is None:
        return None
    rows = store.connection.execute(
        'SELECT activity_id FROM strava_api_activities WHERE external_id=? UNION '
        'SELECT activity_id FROM strava_export_sources WHERE external_id=?', (activity_id, activity_id),
    ).fetchall()
    return rows[0][0] if len(rows) == 1 else None


def candidates(store, segment_id, row, *, api_only=False):
    query = """SELECT h.*, p.confirmed_effort_id
               FROM strava_segment_history h LEFT JOIN strava_pasted_efforts p USING(paste_id)
               WHERE h.segment_id=? AND h.seconds=?"""
    if api_only:
        query += " AND h.source='api'"
    found = []
    for entry in store.connection.execute(query, (segment_id, row.displayed_seconds)):
        other_activity = entry['external_activity_id']
        day = entry['calendar_day'] or entry['start_time'][:10]
        if row.external_activity_id and other_activity:
            if row.external_activity_id != other_activity:
                continue
        else:
            # API dates in the store are UTC; a day on either side is only
            # a candidate, since the pasted calendar date has no timezone.
            days_apart = abs((date.fromisoformat(day) - date.fromisoformat(row.calendar_day)).days)
            if days_apart > (0 if entry['calendar_day'] else 1):
                continue
        key = 'api:' + entry['effort_id'] if entry['effort_id'] else 'paste:' + str(entry['paste_id'])
        found.append(Candidate(key, day, entry['seconds'], entry['source']))
    return found


def save_paste(store, segment_id, rows, decisions, displayed_candidates):
    identity = batch_id(segment_id, rows)
    with store._transaction(write=True):
        watched_segment(store, segment_id)
        if not rows or store.connection.execute('SELECT 1 FROM strava_paste_batches WHERE batch_id=?', (identity,)).fetchone():
            return 0, 0, 0, bool(rows)
        snapshots = [candidates(store, segment_id, row) for row in rows]
        store.connection.execute('INSERT INTO strava_paste_batches VALUES (?,?)', (identity, segment_id))
        saved = linked = skipped = 0
        used = set()
        for i, (row, possible) in enumerate(zip(rows, snapshots)):
            decision = decisions.get(i)
            match = None
            if possible or i in displayed_candidates:
                if decision == 'keep' and i in displayed_candidates:
                    pass
                elif (decision and decision in displayed_candidates.get(i, ())
                      and decision in {item.key for item in possible} and decision not in used):
                    used.add(decision)
                    if decision.startswith('api:'):
                        match = decision.removeprefix('api:')
                        taken = store.connection.execute(
                            'SELECT 1 FROM strava_pasted_efforts WHERE confirmed_effort_id=?', (match,)).fetchone()
                        if taken:
                            linked += 1
                            continue
                    else:
                        linked += 1
                        continue
                else:
                    skipped += 1
                    continue
            store.connection.execute(
                'INSERT INTO strava_pasted_efforts (batch_id, external_activity_id, calendar_day, displayed_seconds, confirmed_effort_id) '
                'VALUES (?,?,?,?,?)',
                (identity, row.external_activity_id, row.calendar_day, row.displayed_seconds, match),
            )
            if match:
                linked += 1
            else:
                saved += 1
    return saved, linked, skipped, False


def confirm_later_match(store, paste_id, effort_id):
    with store._transaction(write=True):
        entry = store.connection.execute(
            'SELECT h.* FROM strava_segment_history h WHERE paste_id=? AND source=\'paste\'', (paste_id,),
        ).fetchone()
        if not entry:
            raise SyncError('This pasted result is unavailable or already matched.')
        row = PastedRow(entry['calendar_day'], entry['seconds'], entry['external_activity_id'])
        if 'api:' + effort_id not in {c.key for c in candidates(store, entry['segment_id'], row, api_only=True)}:
            raise SyncError('That possible match is no longer available. Reload Segments.')
        store.connection.execute(
            'UPDATE strava_pasted_efforts SET confirmed_effort_id=? WHERE paste_id=?', (effort_id, paste_id),
        )


def api_row(row, segment_id, athlete_id):
    try:
        effort_id = exact_id(row['id'])
        activity_id = exact_id(row['activity']['id'])
        segment = exact_id(row['segment']['id'])
        owner = exact_id(row['athlete']['id'])
        elapsed = row['elapsed_time']
        if segment != segment_id or owner != athlete_id or type(elapsed) is not int or not 0 < elapsed <= 2**63-1:
            raise ValueError
        start = absolute(row['start_date']).isoformat()
        return activity_id, Effort(effort_id, segment_id, '', start, elapsed)
    except (TypeError, KeyError, ValueError, SyncError):
        raise SyncError('Strava returned an invalid or unverified effort.') from None


def local_stamp(row):
    # Strava represents local wall time with a Z suffix. The endpoint's
    # bounds refer to that wall time, so do not convert it to a UTC instant.
    try:
        value = row['start_date_local']
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?', value):
            raise ValueError
        stamp = datetime.fromisoformat(value.removesuffix('Z'))
        return stamp if 1 < stamp.year < 9999 else None
    except (KeyError, TypeError, ValueError):
        return None


def api_preview(store, client, segment_id):
    watch = watched_segment(store, segment_id)
    tokens = TokenFile(store.data_dir)
    found, conflicts, warnings = {}, set(), []
    requests = 0
    windows = deque([(None, None)])
    with tokens.lock():
        auth = refreshed_connection(tokens, client)
        if exact_id(auth.get('athlete_id')) != watch['athlete_id']:
            raise SyncError('Connect the Strava athlete who owns this watched segment.')
        while windows and requests < REQUEST_LIMIT:
            if exhausted(client.rate):
                warnings.append('Strava’s rate limit stopped further reads.')
                break
            low, high = windows.popleft()
            bounds = {key: value.isoformat() + 'Z' for key, value in
                      [('start_date_local', low), ('end_date_local', high)] if value is not None}
            requests += 1
            try:
                page = client.segment_efforts(auth['access_token'], segment_id, **bounds)
            except AuthenticationError:
                warnings.append('Strava authorization failed. Reconnect in Settings.')
                break
            except ApiError as error:
                if error.status == 404:
                    warnings.append('Strava’s effort list is unavailable for this segment. Try Paste My Results.')
                    break
                if error.status in (401, 403, 429):
                    warnings.append('Strava rate limit reached. Further reads stopped.' if error.status == 429 else
                                    'Strava denied access. Further reads stopped.')
                    break
                warnings.append('A Strava history request failed.')
                continue
            except SyncError:
                warnings.append('A Strava history request failed.')
                continue
            if not isinstance(page, list) or len(page) > PAGE_LIMIT:
                warnings.append('Strava returned an unexpected history response.')
                continue
            dates = [local_stamp(row) for row in page]
            if bounds and any(t is None or (low is not None and t < low) or (high is not None and t > high) for t in dates):
                warnings.append('A response could not be verified against its date bounds.')
                continue
            for row in page:
                try:
                    activity_id, effort = api_row(row, segment_id, watch['athlete_id'])
                except SyncError:
                    warnings.append('Some efforts could not be verified and were excluded.')
                    continue
                key = effort.effort_id
                value = (activity_id, effort)
                if key in conflicts:
                    continue
                if key in found and found[key] != value:
                    del found[key]
                    conflicts.add(key)
                    warnings.append('Conflicting copies of an effort were excluded.')
                else:
                    found[key] = value
            if len(page) == PAGE_LIMIT:
                # Use an overlapping boundary because endpoint inclusivity is
                # unspecified. Effort IDs deduplicate the shared band.
                distinct = sorted({stamp for stamp in dates if stamp is not None})
                if len(distinct) >= 2:
                    middle = distinct[len(distinct)//2]
                    before = middle - timedelta(seconds=1)
                    after = middle + timedelta(seconds=1)
                    if (low is None or low < before) and (high is None or after < high):
                        windows.extend(((low, after), (before, high)))
                        continue
                warnings.append('A date window remained capped and could not be split safely.')
        if windows:
            warnings.append('Some date windows were left unverified.')
    return list(found.values()), list(dict.fromkeys(warnings)), requests


def api_known(store, rows):
    return {effort.effort_id for _, effort in rows if store.connection.execute(
        'SELECT 1 FROM strava_saved_efforts WHERE effort_id=?', (effort.effort_id,),
    ).fetchone()}


def save_api(store, segment_id, rows):
    tokens = TokenFile(store.data_dir)
    with tokens.lock(), store._transaction(write=True):
        watch = watched_segment(store, segment_id)
        auth = tokens.read()
        if exact_id(auth.get('athlete_id')) != watch['athlete_id']:
            raise SyncError('Connect the Strava athlete who owns this watched segment.')
        known = api_known(store, rows)
        for activity_id, effort in rows:
            save_effort(store, activity_id, effort)
        return len(rows) - len(known)
