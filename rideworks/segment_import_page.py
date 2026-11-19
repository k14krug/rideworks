"""Import history and preview forms for the Segments screen."""
from html import escape

from .segment_import import PASTE_LIMIT, api_saved_counts, batch_id, local_ride, paste_enrichments
from .web import duration


def options(matches):
    sources = {'api': 'Strava API', 'both': 'Strava API and paste', 'paste': 'My Results paste'}
    return ''.join(
        f'<option value="{escape(item.key, quote=True)}">Already saved: {escape(item.date)} · '
        f'{duration(item.seconds)} · {sources[item.source]}'
        f'{(" · effort " + escape(item.key[4:])) if item.key.startswith("api:") else (" · saved result " + escape(item.key[6:]))}</option>'
        for item in matches
    )


def import_form(segment_id, nonce, draft, notice, preview):
    return f'''<section class="segment-history" id="segment-import" aria-labelledby="history-title">
<h3 id="history-title">Import history</h3>
<form id="history-import-form" action="/segments/history/preview" method="post">
<input type="hidden" name="nonce" value="{escape(nonce, quote=True)}">
<input type="hidden" name="segment" value="{escape(segment_id, quote=True)}">
<label for="history-paste">Paste My Results</label>
<textarea id="history-paste" name="paste" rows="5" maxlength="{PASTE_LIMIT}" aria-describedby="history-instructions">{escape(draft.get('paste', ''))}</textarea>
<p id="history-instructions">Copy rows from Strava’s My Results table, including the Date and Time columns.</p>
<div class="segment-import-actions"><button name="method" value="api">From Strava</button>
<button name="method" value="paste">Preview paste</button></div>
</form>
<p id="history-progress" role="status">{escape(notice or '')}</p>
{preview}</section><script src="/static/segment_history.js" defer></script>'''


def preview_panel(store, preview, nonce, watch):
    if not preview or watch is None:
        return ''
    rows = preview['rows']
    warnings = preview.get('warnings', [])
    notes = ''.join(f'<li>{escape(str(message))}</li>' for message in warnings)
    notes = f'<ul>{notes}</ul>' if notes else ''
    nonce = escape(nonce, quote=True)
    token = escape(preview['token'], quote=True)
    if preview['method'] == 'api':
        already, enriched = api_saved_counts(store, rows)
        summary = f'<p>{len(rows)} validated efforts · {already} already saved · {len(rows)-already} to save.</p>'
        if enriched:
            summary += f'<p>New metrics are available for {enriched} saved efforts.</p>'
        summary += f'<p>{preview["requests"]} Strava history requests. History may be incomplete.</p>'
        summary += '<p>Possible matches with saved pasted results can be reviewed after saving.</p>'
        action = bool(len(rows)-already or enriched)
        exceptions = ''
    else:
        identity = batch_id(watch['segment_id'], rows)
        repeated = bool(rows and store.connection.execute('SELECT 1 FROM strava_paste_batches WHERE batch_id=?',
                                                          (identity,)).fetchone())
        enriched = sum(1 for _ in paste_enrichments(store, identity, rows)) if repeated else 0
        invalid = preview['invalid']
        overlap = preview['candidates']
        linked = sum(local_ride(store, row.external_activity_id) is not None for row in rows)
        summary = (f'<p>{len(rows)} readable rows · {linked} unique ride links · {len(invalid)} unparsed · '
                   f'{len(overlap)} possible duplicates skipped by default.</p>')
        if not rows:
            summary = ('<p><strong>Nothing imported.</strong> Copy complete rows from Strava’s My Results table, '
                       'including Date and Time, then paste them and select Preview paste.</p>' + summary)
        summary += '<p>This batch was already reviewed.</p>' if repeated else ''
        if enriched:
            summary += f'<p>New metrics are available for {enriched} saved efforts.</p>'
        exceptions = ''
        if invalid:
            bad = ''.join(f'<li>Line {line} · {escape(text)}</li>' for line, text in invalid)
            exceptions += f'<details><summary>Unparsed rows</summary><ul>{bad}</ul></details>'
        if overlap and not repeated:
            fields = []
            for index, choices in overlap.items():
                row = rows[index]
                fields.append(f'<label for="history-choice-{index}">{escape(row.calendar_day)} · {duration(row.displayed_seconds)}</label>'
                              f'<select id="history-choice-{index}" name="r{index}">'
                              '<option value="skip">Skip this row</option><option value="keep">Keep as a separate attempt</option>'
                              f'{options(choices)}</select>')
            exceptions += f'<fieldset><legend>Possible duplicates</legend>{"".join(fields)}</fieldset>'
        action = bool(rows and (not repeated or enriched))
    confirm = (f'<form action="/segments/history/save" method="post"><input type="hidden" name="nonce" value="{nonce}">'
               f'<input type="hidden" name="preview" value="{token}">{exceptions}'
               '<button>Save history</button></form>') if action else exceptions
    return (f'<section class="segment-preview" id="history-preview" aria-labelledby="history-preview-title" tabindex="-1">'
            f'<h3 id="history-preview-title">Import preview · {escape(watch["name"])}</h3>'
            f'{summary}{notes}{confirm}</section>')
