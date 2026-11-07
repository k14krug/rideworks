"""Explicit source-observation reconciliation, independent of activity matching."""

import json

from .race_results import RaceError, normalize_row, validate_shape


def observations(store, source):
    sections = [dict(row) for row in store.connection.execute(
        'SELECT * FROM race_import_sections WHERE import_id=? ORDER BY section_index',
        (source['import_id'],))]
    if not sections:
        rows = validate_shape({'races': json.loads(source['rows_json'])})
        return [{'section': 0, 'row': row, 'legacy': True} for row in rows], [], True
    result = []
    for expected, section in enumerate(sections):
        if section['section_index'] != expected:
            raise RaceError('Screenshot section provenance is inconsistent. Retry the import.')
        if section['status'] != 'completed':
            continue
        rows = validate_shape({'races': json.loads(section['output_json'])})
        result.extend({'section': expected, 'row': row, 'legacy': False} for row in rows)
    if [item['row'] for item in result] != json.loads(source['rows_json']):
        raise RaceError('Screenshot observation provenance is inconsistent. Retry the import.')
    return result, sections, all(section['status'] == 'completed' for section in sections)


def adjacent(first, second, sections):
    if abs(first['section'] - second['section']) != 1 or not sections:
        return False
    left, right = sections[first['section']], sections[second['section']]
    return max(left['top'], right['top']) < min(left['bottom'], right['bottom'])


def reconcile(source_observations, sections, complete, draft, visible_count, confirmed, *, require_corrections=True):
    if not complete:
        raise RaceError('A screenshot section failed or is incomplete. Try a shorter screenshot; no results can be saved.')
    if not source_observations or len(source_observations) != len(draft):
        raise RaceError('No complete observation set is available. Retry the screenshot import.')
    if not confirmed or type(visible_count) is not int or visible_count < 1:
        raise RaceError('Verify the number of visible physical race rows in the original screenshot.')
    groups = []
    roots = []
    for index, item in enumerate(draft):
        choice = item.get('group')
        if choice == 'different':
            roots.append(index)
            groups.append([index])
        elif isinstance(choice, str) and choice.isascii() and choice.isdecimal():
            target = int(choice) - 1
            if target < 0 or target >= index or not adjacent(source_observations[index], source_observations[target], sections):
                raise RaceError(f'Observation {index + 1}: choose an observation from an adjacent overlapping section.')
            root = roots[target]
            group = next(group for group in groups if group[0] == root)
            if any(source_observations[member]['section'] == source_observations[index]['section'] for member in group):
                raise RaceError(f'Observation {index + 1}: a group cannot contain two observations from the same section.')
            roots.append(root)
            group.append(index)
        else:
            raise RaceError(f'Observation {index + 1}: explicitly mark a different row or the same screenshot row.')
    if len(groups) != visible_count:
        raise RaceError(f'Visible-row count is {visible_count}, but {len(groups)} distinct races were reconciled.')
    for group in groups:
        root = group[0]
        if any(source_observations[i]['row'] != source_observations[root]['row'] for i in group[1:]):
            if require_corrections and not draft[root].get('corrected'):
                raise RaceError(f'Observation {root + 1}: conflicting values require correction and confirmation against the screenshot.')
        for index in group[1:]:
            if draft[index]['values'] != normalize_row(source_observations[index]['row']):
                raise RaceError(f'Observation {index + 1}: correct the final values on observation {root + 1}, not the duplicate.')
    return groups
