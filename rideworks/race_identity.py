"""Conservative, explicit cross-import source-race identity review."""

from datetime import date, datetime, timedelta
import hashlib
import json

from .race_matching import distinctive_words
from .race_results import RaceError, result_revision, screenshot


MAX_IDENTITY_PAIRS = 400


def identity_key(activity_id):
    return hashlib.sha256(activity_id.encode()).hexdigest()


def _source_available(store, identity):
    try:
        screenshot(store, identity)
    except (RaceError, OSError):
        return False
    return True


def _prior_groups(store, saved):
    groups = set()
    single_row = False
    records = store.connection.execute(
        'SELECT visible_count, decisions_json FROM race_import_reconciliations WHERE import_id=?',
        (saved['import_id'],))
    for record in records:
        provenance = json.loads(record['decisions_json'])
        if provenance.get('timezone') != saved['display_timezone']:
            continue
        for group in provenance.get('groups', []):
            if group.get('activity_id') == saved['activity_id'] and group.get('values') == json.loads(saved['values_json']):
                members = tuple(group.get('observations', []))
                if members:
                    groups.add(members)
                    single_row |= (provenance.get('count_type') != 'derived_distinct_races'
                                   and record['visible_count'] == 1 and len(provenance.get('groups', [])) == 1)
    return groups, single_row


def _nearby(row, previous):
    try:
        days = abs((date.fromisoformat(row['date']) - date.fromisoformat(previous['date'])).days)
        current_time = datetime.strptime(row['start_time'], '%H:%M')
        old_time = datetime.strptime(previous['start_time'], '%H:%M')
    except (TypeError, ValueError, KeyError):
        return False
    minutes = abs((current_time - old_time).total_seconds()) / 60
    minutes = min(minutes, 1440 - minutes)
    return (days <= 3 and minutes <= 10 and isinstance(previous.get('event'), str)
            and bool(distinctive_words(row['event']) & distinctive_words(previous['event'])))


def possible_associations(store, source, groups, rows, decisions, timezone_name, visible_count):
    """Return possible prior links for each matched group, without asserting identity."""
    days = set()
    for row, decision in zip(rows, decisions):
        if decision['activity_id']:
            day = date.fromisoformat(row['date'])
            for offset in range(-3, 4):
                try:
                    days.add((day + timedelta(days=offset)).isoformat())
                except OverflowError:
                    continue
    if not days:
        return [[] for _ in rows]
    placeholders = ','.join('?' for _ in days)
    saved_results = store.connection.execute(f'''
        SELECT r.*, i.image_sha256, i.rows_json AS source_rows_json FROM race_results r
        JOIN race_imports i ON i.import_id=r.import_id
        WHERE i.image_sha256=? OR json_extract(r.values_json, '$.date') IN ({placeholders})
        ORDER BY r.activity_id''', (source['image_sha256'], *sorted(days))).fetchall()
    available = {source['import_id']: _source_available(store, source['import_id'])}
    section_evidence = [tuple(section) for section in store.connection.execute('''
        SELECT section_index, top, bottom, width, image_height, status, output_json
        FROM race_import_sections WHERE import_id=? ORDER BY section_index''', (source['import_id'],))]
    prior = {}
    result = [[] for _ in rows]
    for index, (group, row, decision) in enumerate(zip(groups, rows, decisions)):
        if not decision['activity_id']:
            continue
        for saved in saved_results:
            if saved['activity_id'] == decision['activity_id']:
                continue
            previous = json.loads(saved['values_json'])
            same_image = saved['image_sha256'] == source['image_sha256']
            if not same_image and not _nearby(row, previous):
                continue
            if saved['activity_id'] not in prior:
                prior[saved['activity_id']] = _prior_groups(store, saved)
            old_groups, old_single = prior[saved['activity_id']]
            members = tuple(member + 1 for member in group)
            proven_same = same_image and (
                (saved['import_id'] == source['import_id'] and bool(old_groups)
                 and all(set(members) & set(old_group) for old_group in old_groups))
                or (visible_count == 1 and old_single and len(old_groups) == 1)
            )
            if saved['import_id'] not in available:
                available[saved['import_id']] = _source_available(store, saved['import_id'])
            old_revision = result_revision(saved, None)
            binding = [source['import_id'], source['image_sha256'], source['rows_json'], section_evidence,
                       members, row,
                       decision['activity_id'], timezone_name, saved['activity_id'],
                       saved['import_id'], saved['image_sha256'], saved['source_rows_json'],
                       sorted(old_groups), old_single, old_revision, proven_same]
            token = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            result[index].append({'activity_id': saved['activity_id'], 'import_id': saved['import_id'],
                                  'old_revision': old_revision, 'values': previous,
                                  'old_timezone': saved['display_timezone'], 'same_image': same_image,
                                  'new_import_id': source['import_id'], 'new_observations': members,
                                  'new_activity_id': decision['activity_id'],
                                  'proven_same': proven_same, 'token': token,
                                  'source_available': available[source['import_id']] and available[saved['import_id']]})
            if sum(map(len, result)) > MAX_IDENTITY_PAIRS:
                raise RaceError('Too many possible prior associations to review safely. Try a shorter screenshot.')
    return result


def validate_identity_choices(candidates, items, decisions, timezone_name):
    recorded = []
    for candidates_for_row, item in zip(candidates, items):
        submitted = item.get('identity', {})
        expected = {identity_key(candidate['activity_id']) for candidate in candidates_for_row}
        if set(submitted) - expected:
            raise RaceError('Prior associations changed. Review the entire batch again.')
        for candidate in candidates_for_row:
            choice = submitted.get(identity_key(candidate['activity_id']), '')
            if not candidate['source_available']:
                raise RaceError('A source screenshot is missing or failed integrity verification; identity review is blocked.')
            if choice == 'same:' + candidate['token'] or candidate['proven_same']:
                raise RaceError('A race is already attached to a different activity. Remove the old race result separately, then review the entire batch again.')
            if choice != 'different:' + candidate['token']:
                raise RaceError('A possible prior association is unresolved or changed. Review the source identity again.')
            recorded.append({'activity_id': candidate['activity_id'], 'import_id': candidate['import_id'],
                             'old_revision': candidate['old_revision'], 'decision': 'different',
                             'new_import_id': candidate['new_import_id'],
                             'new_observations': candidate['new_observations'],
                             'new_activity_id': candidate['new_activity_id'],
                             'new_source_token': candidate['token']})
            for other_item, other_decision in zip(items, decisions):
                if (other_decision['activity_id'] == candidate['activity_id']
                        and (other_item['values'] != candidate['values']
                             or timezone_name != candidate['old_timezone'])):
                    raise RaceError('A prior race marked different would be replaced by another row in this batch. Review the existing attachment separately.')
    return recorded
