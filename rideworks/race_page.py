"""Server-rendered Race Results and explicit import review."""

from html import escape
import json
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from .history import presentation
from .race_results import FIELDS, PROMPT_VERSION, activity_candidate, candidates, matching_activities, normalize_row, revision, row_errors, suggested_match
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
<td>{esc(value_text(data['race_score']))}</td><td>{esc(change_text)}</td></tr>''')
    table = (f'''<div class="race-table-wrap"><table class="race-table"><thead><tr>
<th>Date</th><th>Event / Activity</th><th>Group</th><th>Finish</th><th>Zwift avg watts</th>
<th>Racing Score</th><th>Change</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
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
        draft = [{'values': normalize_row(row), 'activity_id': '', 'action': 'skip', 'replace': False} for row in extracted]
        initial = True
    else:
        initial = False
    timezone_name = source['display_timezone'] if timezone_name is None else timezone_name
    activities = matching_activities(store)
    cards = []
    for index, item in enumerate(draft):
        row = item['values']
        choices = candidates(store, row, timezone_name, activities=activities)
        if initial:
            suggested = suggested_match(row, timezone_name, choices)
            if suggested:
                item['activity_id'] = suggested
                item['action'] = 'confirm'
        selected = item['activity_id']
        existing = store.connection.execute('SELECT values_json, display_timezone FROM race_results WHERE activity_id=?', (selected,)).fetchone() if selected else None
        if row_errors(row):
            state = 'Invalid — correct fields before confirming'
        elif not selected:
            state = 'Ambiguous' if len(choices) > 1 else 'Unmatched — select an activity or skip'
        elif existing:
            state = ('Already imported' if json.loads(existing['values_json']) == row and existing['display_timezone'] == (timezone_name or None)
                     else 'Changed — replacement requires approval')
        else:
            state = 'New — review before confirming'
        options = '<option value="">Select a candidate</option>'
        for choice in choices:
            options += f'<option value="{esc(choice["id"])}"{" selected" if choice["id"] == selected else ""}>{esc(candidate_label(choice))}</option>'
        if selected and all(choice['id'] != selected for choice in choices):
            activity = next((activity for activity in activities if activity['activity_id'] == selected), None)
            choice = activity_candidate(activity, ZoneInfo(timezone_name) if timezone_name else None) if activity else None
            label = candidate_label(choice) if choice else f'Selected activity {selected} (date unavailable)'
            options += f'<option value="{esc(selected)}" selected>{esc(label)}</option>'
        inputs = []
        labels = {'date': 'Date', 'start_time': 'Start time', 'event': 'Event', 'race_group': 'Race group',
                  'finish': 'Finish', 'avg_watts': 'Zwift avg watts', 'race_score': 'Racing Score',
                  'race_score_change': 'Score change'}
        for key in FIELDS:
            kind = 'text'
            max_length = '250' if key == 'event' else '50'
            inputs.append(f'<label>{labels[key]}<input type="{kind}" name="{index}.{key}" value="{esc(row[key])}" maxlength="{max_length}"></label>')
        errors = ''.join(f'<li>{esc(error)}</li>' for error in row_errors(row))
        checked_confirm = ' checked' if item['action'] == 'confirm' else ''
        checked_skip = ' checked' if item['action'] != 'confirm' else ''
        checked_replace = ' checked' if item['replace'] else ''
        prior = (f'<p>Previously confirmed: {esc(json.dumps(json.loads(existing["values_json"]), ensure_ascii=False))}; '
                 f'display timezone: {esc(existing["display_timezone"] or "Unknown")}</p>'
                 if existing else '')
        shown_revision = revision(existing['values_json'], existing['display_timezone']) if existing else 'new'
        cards.append(f'''<fieldset class="race-review-row"><legend>Row {index + 1} — {esc(state)}</legend>
<div class="race-fields">{''.join(inputs)}</div>{f'<ul class="race-error">{errors}</ul>' if errors else ''}
{prior}<input type="hidden" name="{index}.shown_activity" value="{esc(selected)}">
<input type="hidden" name="{index}.shown_revision" value="{esc(shown_revision)}">
<div class="race-row-controls"><label class="race-candidate">Candidate activity<select name="{index}.activity">{options}</select></label>
<details class="race-manual"><summary>Enter activity ID</summary>
<label>Existing activity ID<input name="{index}.manual" maxlength="36" placeholder="Activity ID"></label></details>
<div class="race-row-decisions">
<label><input type="radio" name="{index}.action" value="skip"{checked_skip}> Skip</label>
<label><input type="radio" name="{index}.action" value="confirm"{checked_confirm}> Confirm linked result</label>
<label><input type="checkbox" name="{index}.replace" value="yes"{checked_replace}> Approve replacement if changed</label>
</div></div>
</fieldset>''')
    notice = f'<p class="race-error" role="alert">{esc(message)}</p>' if message else ''
    usage = json.loads(source['usage_json']) if source['usage_json'] else None
    usage_text = f'<p>Reported usage: {esc(json.dumps(usage))}</p>' if usage else '<p>API usage was not reported.</p>'
    older_prompt = ('<p class="race-error">This earlier extraction may contain incorrect values, including watts and scores. '
                    'Check every row against the screenshot or extract it again.</p>'
                    if source['prompt_version'] != PROMPT_VERSION else '')
    return shell('Review Race Import', f'''<header class="race-header"><div><h1>Review Race Import</h1>
<p><a href="/race-results">Back to Race Results</a></p></div></header>
<section class="panel race-panel race-review-panel">{notice}{older_prompt}<p>Model output can be wrong. Check every field, especially average watts, and ride against the original before confirming.</p>
{usage_text}<details><summary>View original screenshot</summary><img class="race-image" src="/race-results/image/{esc(source['import_id'])}" alt="Uploaded race screenshot"></details>
<form action="/race-results/review/{esc(source['import_id'])}" method="post">
<input type="hidden" name="nonce" value="{esc(nonce)}">
<label>Screenshot display timezone (IANA, optional)<input name="timezone" maxlength="100" value="{esc(timezone_name)}"></label>
<p>Dates and times are normalized for review; the original model response is retained. Update candidates and duplicate status after editing or changing timezone.
Candidates show the activity date, local time, ride type, title and available source average watts; different watt sources may disagree.
<a href="/activities" target="_blank" rel="noopener">Find an activity ID</a>.</p>
{''.join(cards) if cards else '<p>No fully visible race rows were returned. Try another screenshot.</p>'}
<div class="race-actions"><button type="submit" name="operation" value="preview">Review changes</button>
<button type="submit" name="operation" value="confirm">Confirm Import</button></div>
</form></section>''', active='races', page_class='race-page')


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
