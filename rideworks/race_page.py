"""Server-rendered Race Results and explicit import review."""

from html import escape
import json
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from .history import presentation
from .race_cost import estimate_cost
from .race_identity import identity_key, possible_associations, validate_identity_choices
from .race_matching import batch_matches
from .race_reconcile import apply_overlap_choices, observations, overlap_candidates, overlap_conflicts
from .race_results import CURRENT_PROMPT_VERSIONS, FIELDS, RaceError, activity_candidate, matching_activities, normalize_row, result_revision, result_state, row_errors, screenshot
from .web import shell


def esc(value):
    return escape('' if value is None else str(value), quote=True)


def value_text(value, suffix=''):
    return 'Unknown' if value is None else f'{value}{suffix}'


def candidate_label(choice):
    label = f"{choice['date']} {choice['time']} · {choice['title']} · {choice['type']}"
    if not choice['absolute']:
        label += ' · timezone unknown'
    if choice['watts'] is not None:
        label += f" · {choice['watts']} W ({choice['watts_source']})"
    return label


def results_page(store, query=''):
    try:
        params = parse_qs(query, max_num_fields=10)
    except ValueError:
        params = {}
    sort = params.get('sort', ['newest'])[0]
    sort = sort if sort in ('newest', 'oldest') else 'newest'
    try:
        page = int(params.get('page', ['1'])[0])
        page = max(1, page)
    except ValueError:
        page = 1
    total = store.connection.execute('SELECT COUNT(*) FROM race_results').fetchone()[0]
    pages = max(1, (total + 29) // 30)
    page = min(page, pages)
    direction = 'DESC' if sort == 'newest' else 'ASC'
    records = store.connection.execute(f'''SELECT * FROM race_results
        ORDER BY json_extract(values_json, '$.date') IS NULL, json_extract(values_json, '$.date') {direction}, accepted_at DESC, activity_id
        LIMIT 30 OFFSET ?''', ((page - 1) * 30,)).fetchall()
    rows = []
    for record in records:
        data = json.loads(record['values_json'])
        snapshots = store.activity_history(record['activity_id'])
        title = presentation(snapshots[0])['title'] if snapshots else 'Activity unavailable'
        change = data['race_score_change']
        change_text = 'Unknown' if change is None else f'{change:+d}'
        rows.append(f'''<tr><td>{esc(value_text(data['date']))}</td>
<td><a href="/activities/{esc(record['activity_id'])}">{esc(value_text(data['event']))}</a>
<small>{esc(title)}</small></td><td>{esc(value_text(data['race_group']))}</td>
<td>{esc(value_text(data['finish']))}</td><td>{esc(value_text(data['avg_watts'], ' W'))}</td>
<td>{esc(value_text(data['race_score']))}</td><td>{esc(change_text)}</td>
<td><a href="/race-results/remove/{esc(record['activity_id'])}">Remove race result</a></td></tr>''')
    table = (f'''<div class="race-table-wrap"><table class="race-table"><thead><tr>
<th>Date</th><th>Event / Activity</th><th>Group</th><th>Finish</th><th>Zwift avg watts</th>
<th>Racing Score</th><th>Change</th><th>Action</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<nav aria-label="Race results pages"><a href="/race-results?sort={sort}&amp;page={max(1, page - 1)}">Previous</a>
<span> Page {page} of {pages} </span><a href="/race-results?sort={sort}&amp;page={min(pages, page + 1)}">Next</a></nav>'''
             if rows else '<p>No confirmed race results yet. Import a screenshot to review and link races.</p>')
    return shell('Race Results', f'''<header class="race-header"><div><h1>Race Results</h1>
<p>Confirmed Zwift Racing Profile results linked to existing rides.</p></div>
<a class="race-button" href="/race-results/import">Import Screenshot</a></header>
<section class="panel race-panel"><h2>Race history</h2>
<form method="get" action="/race-results"><label>Sort by date
<select name="sort"><option value="newest"{" selected" if sort == "newest" else ""}>Newest first</option>
<option value="oldest"{" selected" if sort == "oldest" else ""}>Oldest first</option></select></label>
<button type="submit">Apply</button></form>{table}
<p>Zwift-reported watts are separate from FIT and RideWorks power measurements.</p></section>''',
                 active='races', page_class='race-page')


def removal_page(store, activity_id, nonce, *, message=''):
    current, removed = result_state(store, activity_id)
    if not current:
        return None
    data = json.loads(current['values_json'])
    snapshots = store.activity_history(activity_id)
    title = presentation(snapshots[0])['title'] if snapshots else 'Activity unavailable'
    notice = f'<p class="race-error" role="alert">{esc(message)}</p>' if message else ''
    return shell('Remove race result', f'''<header class="race-header"><h1>Remove race result</h1></header>
<section class="panel race-panel">{notice}<p>Remove <strong>{esc(value_text(data['event']))}</strong>
from <strong>{esc(title)}</strong>?</p>
<p>The activity, FIT data, source screenshot and result history will be retained.</p>
<form action="/race-results/remove/{esc(activity_id)}" method="post">
<input type="hidden" name="nonce" value="{esc(nonce)}">
<input type="hidden" name="revision" value="{esc(result_revision(current, removed))}">
<button type="submit">Remove race result</button> <a href="/race-results">Cancel</a>
</form></section>''', active='races', page_class='race-page')


def upload_page(nonce, *, message=''):
    notice = f'<p class="race-error" role="alert">{esc(message)}</p>' if message else ''
    return shell('Import Race Screenshot', f'''<header class="race-header"><div><h1>Import Screenshot</h1>
<p><a href="/race-results">Back to Race Results</a></p></div></header>
<section class="panel race-panel"><h2>Upload a race results screenshot</h2>{notice}
<p>Choose a PNG, JPEG or WebP image. Clicking Extract sends the screenshot to OpenAI and incurs API charges.
No race results are saved until you review and confirm them.</p>
<form action="/race-results/extract" method="post" enctype="multipart/form-data">
<input type="hidden" name="nonce" value="{esc(nonce)}">
<label>Screenshot <input type="file" name="image" accept="image/png,image/jpeg,image/webp" required></label>
<label>Screenshot display timezone (IANA, optional)
<input name="timezone" maxlength="100" value="America/Los_Angeles"></label>
<label>Extraction mode <select name="mode">
<option value="sectioned">Overlapping sections</option>
<option value="full">Full image (comparison)</option></select></label>
<p>Leave timezone blank if unknown. Unknown timezone prevents automatic matching.</p>
<button type="submit">Extract screenshot</button></form></section>''',
                 active='races', page_class='race-page')


def review_page(store, source, nonce, *, draft=None, timezone_name=None, message='',
                overlap_choices=None, list_acknowledged=False, conflict_verifications=None):
    observed, sections, complete = observations(store, source)
    if draft is None:
        draft = [{'values': normalize_row(item['row']), 'replace': False} for item in observed]
    overlap_choices = overlap_choices or {}
    conflict_verifications = conflict_verifications or {}
    timezone_name = source['display_timezone'] if timezone_name is None else timezone_name
    try:
        draft, groups, unresolved = apply_overlap_choices(observed, sections, draft, overlap_choices,
                                                          require_resolved=False)
        pairs = overlap_candidates(observed, sections)
    except RaceError as exc:
        groups = [[index] for index in range(len(observed))]
        pairs = []
        unresolved = []
        message = message or str(exc)
        overlap_choices = {}
    conflicts_by_pair = {conflict['pair']: conflict for conflict in
                         overlap_conflicts(source, observed, groups, draft, overlap_choices, timezone_name)}
    final_rows = [draft[group[0]]['values'] for group in groups]
    activities = matching_activities(store)
    decisions = batch_matches(final_rows, timezone_name, activities)
    identity_error = ''
    try:
        screenshot(store, source['import_id'])
        conflicts = (possible_associations(store, source, groups, final_rows, decisions, timezone_name, len(groups))
                     if groups else [])
    except RaceError as exc:
        conflicts = [[] for _ in groups]
        identity_error = str(exc)
    except OSError:
        conflicts = [[] for _ in groups]
        identity_error = 'Source screenshot is missing or failed integrity verification.'
    activity_by_id = {activity['activity_id']: activity for activity in activities}
    decision_by_root = {group[0]: (i, decision) for i, (group, decision) in enumerate(zip(groups, decisions))}
    group_by_member = {member: group[0] for group in groups for member in group}
    cards = []
    approvals_pending = False
    attention = 0
    for index, item in enumerate(draft):
        row = item['values']
        observation = observed[index]
        group_index, decision = decision_by_root.get(index, (None, {'activity_id': None, 'reason': '', 'candidates': []}))
        if group_by_member.get(index) != index:
            cards.append('<tr hidden><td colspan="9">'
                         + ''.join(f'<input type="hidden" name="{index}.{key}" value="{esc(row[key])}">' for key in FIELDS)
                         + f'<input type="hidden" name="{index}.shown_activity" value="">'
                         + f'<input type="hidden" name="{index}.shown_revision" value="new"></td></tr>')
            continue
        choices = decision['candidates']
        selected = decision['activity_id']
        existing, removed = result_state(store, selected) if selected else (None, None)
        if any(group_by_member.get(member) == index for pair in unresolved for member in pair):
            state = 'Possible duplicate'
        elif row_errors(row):
            state = 'Needs correction'
        elif not selected:
            state = 'Needs correction'
        elif any(index in conflict['group'] and conflict_verifications.get(pair) != conflict['token']
                 for pair, conflict in conflicts_by_pair.items()):
            state = 'Needs attention'
        elif group_index is not None and any(
                candidate['proven_same'] or not candidate['source_available']
                or item.get('identity', {}).get(identity_key(candidate['activity_id'])) != 'different:' + candidate['token']
                for candidate in conflicts[group_index]):
            state = 'Needs attention'
        elif existing:
            state = ('Already imported' if json.loads(existing['values_json']) == row and existing['display_timezone'] == (timezone_name or None)
                     else 'Replacement approval required')
        elif removed:
            state = 'Restoration approval required'
        else:
            state = 'Matched'
        if state not in ('Matched', 'Already imported'):
            attention += 1
        matched = next((choice for choice in choices if choice['id'] == selected), None)
        match_details = (f'<p>Automatically matched: {esc(candidate_label(matched))}</p>' if matched
                         else f'<p class="race-error">{esc(decision["reason"])}</p>' if decision['reason'] else '')
        identity_cards = []
        if group_index is not None:
            for candidate in conflicts[group_index]:
                key = identity_key(candidate['activity_id'])
                selected_identity = item.get('identity', {}).get(key, '')
                same_value = 'same:' + candidate['token']
                different_value = 'different:' + candidate['token']
                choice_options = (f'<option value="">Choose after comparing source evidence</option>'
                                  f'<option value="{same_value}"{" selected" if selected_identity == same_value else ""}>Same race — correct old attachment</option>')
                if not candidate['proven_same']:
                    choice_options += (f'<option value="{different_value}"'
                                       f'{" selected" if selected_identity == different_value else ""}>Different races — retain both</option>')
                old_activity = activity_by_id.get(candidate['activity_id'])
                old_choice = activity_candidate(old_activity, ZoneInfo(timezone_name)) if old_activity and timezone_name else None
                old_label = candidate_label(old_choice) if old_choice else 'Activity date/time unavailable'
                evidence = 'Same original screenshot' if candidate['same_image'] else 'Nearby date, time and event wording; not proof of identity'
                integrity = ('' if candidate['source_available'] else
                             '<p class="race-error">A source screenshot is unavailable or failed integrity verification. Identity review is blocked.</p>')
                identity_cards.append(f'''<div class="race-identity-card">
<p class="race-error">Possible existing attachment — {esc(evidence)}.
{"Preserved row provenance identifies the same source row; remove the old attachment first." if candidate["proven_same"] else "Compare the source evidence before choosing."}</p>
<p>New automatic Activity: {esc(candidate_label(matched) if matched else "Unavailable")}</p>
<p>Old linked Activity: {esc(old_label)} ({esc(candidate["activity_id"])})</p>
<p>Old race: {esc(candidate["values"].get("date"))} · {esc(candidate["values"].get("event"))}.</p>{integrity}
<details><summary>Compare original screenshots</summary><div class="race-crop-comparison">
<div><p>Current screenshot</p><img src="/race-results/image/{esc(source["import_id"])}" alt="Current original screenshot"></div>
<div><p>Previous screenshot</p><img src="/race-results/image/{esc(candidate["import_id"])}" alt="Previous original screenshot"></div>
</div></details>
<label>Source race identity <select name="{index}.identity.{key}">{choice_options}</select></label>
<p>For the same race, <a href="/race-results/remove/{esc(candidate["activity_id"])}" target="_blank" rel="noopener">remove the old race result</a> separately, then return and review changes.</p>
</div>''')
        nearby = ''.join(f'<li>{esc(candidate_label(choice))}</li>' for choice in choices[:20])
        diagnostics = (f'<details><summary>Nearby activities (diagnostic only)</summary><ul>{nearby}</ul>'
                       f'{"<p>Only the first 20 are shown.</p>" if len(choices) > 20 else ""}</details>'
                       if choices and not selected else '')
        inputs = []
        labels = {'date': 'Date', 'start_time': 'Start time', 'event': 'Event', 'race_group': 'Race group',
                  'finish': 'Finish', 'avg_watts': 'Zwift avg watts', 'race_score': 'Racing Score',
                  'race_score_change': 'Score change'}
        for key in FIELDS:
            kind = 'text'
            max_length = '250' if key == 'event' else '50'
            inputs.append(f'<label>{labels[key]}<input type="{kind}" name="{index}.{key}" value="{esc(row[key])}" maxlength="{max_length}"></label>')
        errors = ''.join(f'<li>{esc(error)}</li>' for error in row_errors(row))
        prior = (f'<details><summary>Previously confirmed values</summary><p>{esc(json.dumps(json.loads(existing["values_json"]), ensure_ascii=False))}; '
                 f'display timezone: {esc(existing["display_timezone"] or "Unknown")}</p></details>'
                 if existing else '')
        shown_revision = result_revision(existing, removed)
        checked_replace = (' checked' if item.get('replace') and item.get('shown_activity') == selected
                           and item.get('shown_revision') == shown_revision else '')
        needs_approval = bool(removed or (existing and
                              (json.loads(existing['values_json']) != row or existing['display_timezone'] != (timezone_name or None))))
        if needs_approval and not checked_replace:
            approvals_pending = True
        approval = (f'<label><input type="checkbox" class="race-approval" name="{index}.replace" value="yes"{checked_replace}> '
                    'Approve replacement or restoration</label>' if needs_approval else '')
        group = next((group for group in groups if group[0] == index), [])
        needs_correction = bool(group and any(observed[member]['row'] != observation['row'] for member in group[1:]))
        correction = ('<p class="race-error">The extractions disagree. Check and correct these values against the screenshot.</p>'
                      if needs_correction else '')
        cells = ''.join(f'<td>{esc(value_text(row[key]))}</td>' for key in FIELDS)
        cards.append(f'''<tr class="race-candidate-row">{cells}<td>{esc(state)}
{f'<ul class="race-error">{errors}</ul>' if errors else ''}{correction}
{match_details if not selected else f'<details><summary>Matched activity</summary>{match_details}</details>'}{diagnostics}{approval}{prior}{''.join(identity_cards)}
<details><summary>Edit</summary><div class="race-fields">{''.join(inputs)}</div></details>
<input type="hidden" name="{index}.shown_activity" value="{esc(selected)}">
<input type="hidden" name="{index}.shown_revision" value="{esc(shown_revision)}"></td></tr>''')
    if not complete and not message:
        message = 'A section failed or is incomplete. Resolve the extraction issue or try a shorter screenshot; no race results can be saved.'
    try:
        review_items = []
        for group, candidates_for_row in zip(groups, conflicts):
            item = draft[group[0]]
            valid_keys = {identity_key(candidate['activity_id']) for candidate in candidates_for_row}
            review_items.append({**item, 'identity': {key: value for key, value in item.get('identity', {}).items()
                                                     if key in valid_keys}})
        validate_identity_choices(conflicts, review_items, decisions, timezone_name or None)
        identity_ready = True
    except RaceError as exc:
        identity_ready = False
        identity_error = str(exc)
    notice = f'<p class="race-error" role="alert">{esc(message or identity_error)}</p>' if message or identity_error else ''
    usage = json.loads(source['usage_json']) if source['usage_json'] else None
    attempts = []
    for section in sections:
        if section['status'] != 'planned':
            section_usage = json.loads(section['usage_json']) if section['usage_json'] else None
            attempts.append({'model': section['model'], 'service_tier': section_usage.get('service_tier') if section_usage else None,
                             'usage': section_usage})
    if not sections:
        attempts = [{'model': source['model'], 'service_tier': usage.get('service_tier') if usage else None, 'usage': usage}]
    estimate = estimate_cost(attempts)
    amount = estimate['amount_usd']
    cost_text = (f"${amount:.8f}" if amount is not None else 'unavailable')
    if estimate['state'] == 'partial':
        cost_text += ' (partial; some usage or pricing is unavailable)'
    technical = {'model': source['model'], 'prompt_version': source['prompt_version'],
                 'schema_version': source['schema_version'], 'pricing_version': estimate['pricing_version'],
                 'sections': sections, 'original_observations': [item['row'] for item in observed],
                 'usage': usage}
    pair_cards = []
    labels = {'date': 'Date', 'start_time': 'Start time', 'event': 'Event', 'race_group': 'Race group',
              'finish': 'Finish', 'avg_watts': 'Race avg W', 'race_score': 'Racing Score',
              'race_score_change': 'Score change'}
    for left, right in pairs:
        first, second = observed[left], observed[right]
        choice = overlap_choices.get((left, right), '')
        comparison = ''.join(
            f'<div><p>{esc(value_text(item["row"].get("date")))} · {esc(value_text(item["row"].get("event")))}</p>'
            f'<img src="/race-results/section/{esc(source["import_id"])}/{item["section"]}" '
            f'alt="Screenshot crop for possible duplicate"></div>' for item in (first, second))
        conflict = conflicts_by_pair.get((left, right))
        verification = ''
        if conflict:
            differences = ''.join(
                f'<li>{esc(labels[field])}: {esc(value_text(first["row"].get(field)))} / '
                f'{esc(value_text(second["row"].get(field)))}</li>' for field in conflict['fields'])
            checked = conflict_verifications.get((left, right)) == conflict['token']
            if not checked:
                approvals_pending = True
            verification = (f'<div class="race-conflict"><p>These extractions disagree:</p><ul>{differences}</ul>'
                            '<p>Edit the final race values in the list if needed, then review changes.</p>'
                            f'<label><input type="checkbox" class="race-approval race-conflict-verification" '
                            f'name="verify.{left}.{right}" value="{conflict["token"]}"{" checked" if checked else ""}> '
                            'I checked these conflicting values against the original screenshot.</label></div>')
        pair_cards.append(f'''<div class="race-overlap">
<p>These two extractions may be the same race: {esc(value_text(first["row"].get("date")))} · {esc(value_text(first["row"].get("event")))}
 / {esc(value_text(second["row"].get("date")))} · {esc(value_text(second["row"].get("event")))}.</p>
<label><input type="radio" name="overlap.{left}.{right}" value="same"{" checked" if choice == "same" else ""}> Same race</label>
<label><input type="radio" name="overlap.{left}.{right}" value="different"{" checked" if choice == "different" else ""}> Two races</label>
<details><summary>Compare screenshot crops</summary><div class="race-crop-comparison">{comparison}</div></details>{verification}</div>''')
    older_prompt = ('<p class="race-error">This earlier extraction may contain incorrect values, including watts and scores. '
                    'Check every row against the screenshot or extract it again.</p>'
                    if source['prompt_version'] not in CURRENT_PROMPT_VERSIONS else '')
    matched = (bool(groups) and complete and not unresolved and not message and not identity_error and identity_ready
               and all(decision['activity_id'] for decision in decisions))
    disabled = ' disabled' if not matched or approvals_pending or not list_acknowledged else ''
    matched_count = sum(bool(decision['activity_id']) for decision in decisions)
    return shell('Review Race Import', f'''<header class="race-header"><div><h1>Review Race Import</h1>
<p><a href="/race-results">Back to Race Results</a></p></div></header>
<section class="panel race-panel race-review-panel">{notice}{older_prompt}
<p><strong>{len(groups)} races identified · {matched_count} automatically matched · {attention} need attention</strong></p>
<p>Estimated API cost: {esc(cost_text)} (estimate, not the amount billed).</p>
<details><summary>View original screenshot</summary><img class="race-image" src="/race-results/image/{esc(source['import_id'])}" alt="Uploaded race screenshot"></details>
<details><summary>Technical details</summary><pre>{esc(json.dumps(technical, ensure_ascii=False, indent=2))}</pre></details>
<form class="race-review-form" data-matched="{str(matched).lower()}" action="/race-results/review/{esc(source['import_id'])}" method="post">
<input type="hidden" name="nonce" value="{esc(nonce)}">
<details><summary>Screenshot timezone: {esc(timezone_name or "Unknown")}</summary><label>Timezone (IANA)
<input name="timezone" maxlength="100" value="{esc(timezone_name)}"></label></details>
{''.join(pair_cards)}
<div class="race-table-wrap"><table class="race-table race-review-table"><thead><tr>
<th>Date</th><th>Time</th><th>Event</th><th>Group</th><th>Finish</th><th>Race avg W</th>
<th>Racing Score</th><th>Change</th><th>Status</th></tr></thead><tbody>{''.join(cards)}</tbody></table></div>
{'' if cards else '<p>No race rows were returned. Try another screenshot.</p>'}
<label><input class="race-approval" name="list_acknowledged" type="checkbox" value="yes"{" checked" if list_acknowledged else ""}>
I checked these races against my screenshot.</label>
<p>Each race must match a different activity. If a race is missing, cancel and retry with a clearer or shorter screenshot.</p>
<div class="race-actions"><button type="submit" name="operation" value="preview">Review changes</button>
<button type="submit" name="operation" value="confirm"{disabled}>Import all {len(groups)} races</button></div>
<p class="race-review-dirty" role="status" hidden>Fields changed. Select Review changes to recompute all matches.</p>
</form><script src="/static/race_review.js" defer></script></section>''', active='races', page_class='race-page')


def activity_panel(store, activity_id):
    result = store.connection.execute('SELECT values_json FROM race_results WHERE activity_id=?', (activity_id,)).fetchone()
    if not result:
        return ''
    row = json.loads(result['values_json'])
    change = row['race_score_change']
    return f'''<section class="panel race-panel"><h2>Race Result</h2>
<p>{esc(value_text(row['event']))} · {esc(value_text(row['race_group']))}</p>
<p>Finish: {esc(value_text(row['finish']))} · Zwift-reported average: {esc(value_text(row['avg_watts'], ' W'))}
· Racing Score: {esc(value_text(row['race_score']))} · Change: {esc('Unknown' if change is None else f'{change:+d}')}</p>
<p>Source: Zwift Racing Profile screenshot; not FIT-measured power.</p><a href="/race-results">View Race Results</a></section>'''
