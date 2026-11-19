"""Import history and preview forms for the Segments screen."""
from html import escape

from .segment_import import PASTE_LIMIT, api_known, batch_id, candidates, local_ride
from .web import duration


def options(matches):
    sources = {'api': 'Strava API', 'both': 'Strava API and paste', 'paste': 'My Results paste'}
    return ''.join(
        f'<option value="{escape(item.key, quote=True)}">Already saved: {escape(item.date)} · '
        f'{duration(item.seconds)} · {sources[item.source]}'
        f'{(" · effort " + escape(item.key[4:])) if item.key.startswith("api:") else (" · saved result " + escape(item.key[6:]))}</option>'
        for item in matches
    )


def import_form(watches, nonce):
    if not watches:
        return ''
    choices = ''.join(f'<option value="{escape(w[0], quote=True)}">{escape(w[1])}</option>' for w in watches)
    return f'''<section class="panel segment-add segment-history"><h2>Import history</h2>
<form action="/segments/history/preview" method="post">
<input type="hidden" name="nonce" value="{escape(nonce, quote=True)}">
<label for="history-segment">Watched segment</label>
<select id="history-segment" name="segment" required>{choices}</select>
<label for="history-paste">Paste My Results</label>
<textarea id="history-paste" name="paste" rows="5" maxlength="{PASTE_LIMIT}"></textarea>
<p>Include the Date and Time columns. Activity links in the pasted text can connect results to saved rides.</p>
<div class="segment-import-actions"><button name="method" value="api">From Strava</button>
<button name="method" value="paste">Preview paste</button></div>
</form></section>'''


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
        already = len(api_known(store, rows))
        summary = f'<p>{len(rows)} validated efforts · {already} already saved · {len(rows)-already} to save.</p>'
        summary += f'<p>{preview["requests"]} Strava history requests. History may be incomplete.</p>'
        summary += '<p>Possible matches with saved pasted results can be reviewed after saving.</p>'
        action = bool(len(rows)-already)
        exceptions = ''
    else:
        repeated = bool(rows and store.connection.execute('SELECT 1 FROM strava_paste_batches WHERE batch_id=?',
                                                          (batch_id(watch['segment_id'], rows),)).fetchone())
        invalid = preview['invalid']
        overlap = preview['candidates']
        linked = sum(local_ride(store, row.external_activity_id) is not None for row in rows)
        summary = (f'<p>{len(rows)} readable rows · {linked} unique ride links · {len(invalid)} unparsed · '
                   f'{len(overlap)} possible duplicates skipped by default.</p>')
        summary += '<p>This batch was already reviewed.</p>' if repeated else ''
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
        action = bool(rows and not repeated)
    confirm = (f'<form action="/segments/history/save" method="post"><input type="hidden" name="nonce" value="{nonce}">'
               f'<input type="hidden" name="preview" value="{token}">{exceptions}'
               '<button>Save history</button></form>') if action else exceptions
    return (f'<section class="panel segment-add segment-preview"><h2>Import preview · {escape(watch["name"])}</h2>'
            f'{summary}{notes}{confirm}<a href="/segments">Back to watched segments</a></section>')
