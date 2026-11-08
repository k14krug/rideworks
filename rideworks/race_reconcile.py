"""Explicit source-observation reconciliation, independent of activity matching."""

import json
import hashlib
import re

from .race_results import FIELDS, RaceError, normalize_row, validate_shape


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


def overlap_candidates(source_observations, sections):
    """Identify possible repeated source rows, never asserting that they are equal."""
    pairs = []
    for right, second in enumerate(source_observations):
        b = normalize_row(second['row'])
        for left, first in enumerate(source_observations[:right]):
            if not adjacent(first, second, sections):
                continue
            a = normalize_row(first['row'])
            words_a = set(re.findall(r'[a-z0-9]+', (a.get('event') or '').casefold()))
            words_b = set(re.findall(r'[a-z0-9]+', (b.get('event') or '').casefold()))
            words_a -= {'zwift', 'race', 'racing', 'stage', 'event', 'the'}
            words_b -= {'zwift', 'race', 'racing', 'stage', 'event', 'the'}
            title_evidence = bool({word for word in words_a & words_b if len(word) >= 3 and not word.isdecimal()})
            same_time = bool(a.get('start_time') and a['start_time'] == b.get('start_time'))
            same_date = bool(a.get('date') and a['date'] == b.get('date'))
            same_finish = a.get('finish') is not None and a['finish'] == b.get('finish')
            missing_date = not a.get('date') or not b.get('date')
            same_title = bool(a.get('event') and a['event'].casefold() == (b.get('event') or '').casefold())
            if ((title_evidence and (same_date or missing_date or (same_time and same_title and same_finish)))
                    or (same_date and same_time and same_finish)):
                pairs.append((left, right))
                if len(pairs) > 400:
                    raise RaceError('Too many possible overlapping races to review safely. Try a shorter screenshot.')
    return pairs


def overlap_groups(source_observations, sections, choices, *, require_resolved=True):
    """Apply pair-level Owner decisions and retain all source observations."""
    pairs = overlap_candidates(source_observations, sections)
    if set(choices) - set(pairs):
        raise RaceError('Overlap decisions changed. Review the race list again.')
    parents = list(range(len(source_observations)))

    def root(index):
        while parents[index] != index:
            index = parents[index]
        return index

    unresolved = []
    for left, right in pairs:
        choice = choices.get((left, right), '')
        if choice not in ('same', 'different'):
            if choice:
                raise RaceError('Invalid overlap decision. Review the race list again.')
            unresolved.append((left, right))
        elif choice == 'same':
            a, b = root(left), root(right)
            if a != b:
                parents[max(a, b)] = min(a, b)
    groups_by_root = {}
    for index in range(len(source_observations)):
        groups_by_root.setdefault(root(index), []).append(index)
    groups = list(groups_by_root.values())
    for group in groups:
        members = [source_observations[index]['section'] for index in group]
        if len(set(members)) != len(members):
            raise RaceError('A race cannot contain two observations from the same section.')
    if any(choices.get(pair) == 'different' and root(pair[0]) == root(pair[1]) for pair in pairs):
        raise RaceError('Overlap decisions contradict one another. Review the race list again.')
    if unresolved and require_resolved:
        raise RaceError('Decide whether each possible overlap is the same race or two races.')
    return groups, unresolved


def apply_overlap_choices(source_observations, sections, draft, choices, *, require_resolved=True):
    if len(draft) != len(source_observations):
        raise RaceError('The race list changed. Reload the review.')
    groups, unresolved = overlap_groups(source_observations, sections, choices, require_resolved=require_resolved)
    prepared = [{**item, 'group': 'different'} for item in draft]
    for group in groups:
        for index in group[1:]:
            targets = [other for other in group if other < index
                       and adjacent(source_observations[index], source_observations[other], sections)]
            if not targets:
                raise RaceError('Overlap decisions cannot be reconciled in screenshot order.')
            prepared[index]['group'] = str(targets[-1] + 1)
    return prepared, groups, unresolved


def overlap_conflicts(source, source_observations, groups, draft, choices, timezone_name):
    """Bind each conflicting same-race decision to its source, grouping and final values."""
    roots = {member: group for group in groups for member in group}
    conflicts = []
    for (left, right), choice in sorted(choices.items()):
        if choice != 'same':
            continue
        first, second = source_observations[left]['row'], source_observations[right]['row']
        fields = [field for field in FIELDS if first.get(field) != second.get(field)]
        if not fields:
            continue
        group = roots[left]
        relevant_choices = [(a, b, value) for (a, b), value in sorted(choices.items())
                            if a in group or b in group]
        binding = [source['import_id'], source['image_sha256'], left, right, first, second,
                   group, relevant_choices, draft[group[0]]['values'], timezone_name]
        token = hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        conflicts.append({'pair': (left, right), 'group': group, 'fields': fields, 'token': token})
    return conflicts


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
