"""Server-rendered Race Results and explicit import review."""

from html import escape
import json
from urllib.parse import parse_qs

from .history import presentation
from .race_cost import estimate_cost
from .race_matching import batch_matches
from .race_results import FIELDS, PROMPT_VERSION, matching_activities, normalize_row, other_result_conflicts, result_revision, result_state, row_errors
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
<p>Leave timezone blank if unknown. Unknown timezone prevents automatic matching.</p>
<button type="submit">Extract screenshot</button></form></section>''',
                 active='races', page_class='race-page')


def review_page(store, source, nonce, *, draft=None, timezone_name=None, message=''):
    extracted = json.loads(source['rows_json'])
    if draft is None:
        draft = [{'values': normalize_row(row), 'replace': False} for row in extracted]
    timezone_name = source['display_timezone'] if timezone_name is None else timezone_name
    activities = matching_activities(store)
    decisions = batch_matches([item['values'] for item in draft], timezone_name, activities)
    conflicts = other_result_conflicts(store, [item['values'] for item in draft], decisions)
    cards = []
    approvals_pending = False
    for index, (item, decision) in enumerate(zip(draft, decisions)):
        row = item['values']
        choices = decision['candidates']
        selected = decision['activity_id']
        existing, removed = result_state(store, selected) if selected else (None, None)
        if row_errors(row):
            state = 'Invalid — correct fields before confirming'
        elif not selected:
            state = 'Unresolved — batch blocked'
        elif index in conflicts:
            state = 'Possible existing attachment — batch blocked'
        elif existing:
            state = ('Already imported' if json.loads(existing['values_json']) == row and existing['display_timezone'] == (timezone_name or None)
                     else 'Changed — replacement requires approval')
        elif removed:
            state = 'Previously removed — restoration requires approval'
        else:
            state = 'New — review before confirming'
        matched = next((choice for choice in choices if choice['id'] == selected), None)
        match_details = (f'<p>Automatically matched: {esc(candidate_label(matched))}</p>'
                         if matched else f'<p class="race-error">{esc(decision["reason"])}</p>')
        if index in conflicts:
            match_details += (f'<p class="race-error">This race may already be linked to a different activity '
                              f'({esc(conflicts[index])}). Review and remove any incorrect attachment on '
                              f'<a href="/race-results">Race Results</a> first.</p>')
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
        prior = (f'<p>Previously confirmed: {esc(json.dumps(json.loads(existing["values_json"]), ensure_ascii=False))}; '
                 f'display timezone: {esc(existing["display_timezone"] or "Unknown")}</p>'
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
        cards.append(f'''<fieldset class="race-review-row"><legend>Row {index + 1} — {esc(state)}</legend>
<div class="race-fields">{''.join(inputs)}</div>{f'<ul class="race-error">{errors}</ul>' if errors else ''}
{prior}<input type="hidden" name="{index}.shown_activity" value="{esc(selected)}">
<input type="hidden" name="{index}.shown_revision" value="{esc(shown_revision)}">
<div class="race-row-controls">{match_details}{diagnostics}{approval}</div>
</fieldset>''')
    notice = f'<p class="race-error" role="alert">{esc(message)}</p>' if message else ''
    usage = json.loads(source['usage_json']) if source['usage_json'] else None
    usage_text = f'<p>Reported usage: {esc(json.dumps(usage))}</p>' if usage else '<p>API usage was not reported.</p>'
    estimate = estimate_cost([{'model': source['model'], 'service_tier': usage.get('service_tier'),
                               'usage': usage}] if usage else [{'model': source['model']}])
    amount = estimate['amount_usd']
    cost_text = (f"${amount:.8f}" if amount is not None else 'unavailable')
    if estimate['state'] == 'partial':
        cost_text += ' (partial; some usage or pricing is unavailable)'
    usage_text += (f'<p>Estimated API cost: {esc(cost_text)} '
                   f'({esc(estimate["pricing_version"])}; standard-tier estimate, not the amount billed).</p>')
    older_prompt = ('<p class="race-error">This earlier extraction may contain incorrect values, including watts and scores. '
                    'Check every row against the screenshot or extract it again.</p>'
                    if source['prompt_version'] != PROMPT_VERSION else '')
    matched = bool(decisions) and not conflicts and all(decision['activity_id'] for decision in decisions)
    disabled = ' disabled' if not matched or approvals_pending else ''
    return shell('Review Race Import', f'''<header class="race-header"><div><h1>Review Race Import</h1>
<p><a href="/race-results">Back to Race Results</a></p></div></header>
<section class="panel race-panel race-review-panel">{notice}{older_prompt}<p>Model output can be wrong. Check every field, especially average watts, and ride against the original before confirming.</p>
{usage_text}<details><summary>View original screenshot</summary><img class="race-image" src="/race-results/image/{esc(source['import_id'])}" alt="Uploaded race screenshot"></details>
<form class="race-review-form" data-matched="{str(matched).lower()}" action="/race-results/review/{esc(source['import_id'])}" method="post">
<input type="hidden" name="nonce" value="{esc(nonce)}">
<label>Screenshot display timezone (IANA, optional)<input name="timezone" maxlength="100" value="{esc(timezone_name)}"></label>
<p>Dates and times are normalized for review; the original model response is retained. Select Review changes after editing fields or changing timezone.
Every row must match a different activity automatically or the entire batch is blocked. Nearby activities are shown for diagnosis, not selection.
Activity details include the local date, time, ride type, title and available source average watts; different watt sources may disagree.</p>
{''.join(cards) if cards else '<p>No fully visible race rows were returned. Try another screenshot.</p>'}
<div class="race-actions"><button type="submit" name="operation" value="preview">Review changes</button>
<button type="submit" name="operation" value="confirm"{disabled}>Confirm Batch</button></div>
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
