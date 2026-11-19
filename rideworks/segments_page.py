"""Segments screen backed only by the locally saved watchlist and efforts."""
from collections import defaultdict
from html import escape
from urllib.parse import parse_qs

from .history import presentation
from .segment_import import PastedRow, candidates
from .segment_import_page import import_form, options, preview_panel
from .web import duration, local_time, shell


def segments_page(store, settings, query):
    try:
        filters = parse_qs(query, max_num_fields=4)
    except ValueError:
        filters = {}
    ride = filters.get('ride', [''])[0]
    if ride:
        snapshots = store.activity_history(ride)
        title = presentation(snapshots[0])['title'] if snapshots else 'Ride unavailable'
        heading = f'<p>{escape(title)} · <a href="/segments">All watched segments</a></p>'
    else:
        heading = ''
    sql = """SELECT w.segment_id, w.name, e.effort_id, e.external_activity_id,
                    e.start_time, e.calendar_day, e.seconds, e.source, e.paste_id, l.activity_id
             FROM strava_watched_segments w
             LEFT JOIN strava_segment_history e USING (segment_id)
             LEFT JOIN strava_saved_effort_ride_links l USING (external_activity_id)"""
    rows = store.connection.execute(
        sql + (' WHERE l.activity_id=?' if ride else '') +
        ' ORDER BY w.name COLLATE NOCASE, w.segment_id, COALESCE(e.start_time,e.calendar_day) DESC, e.effort_id, e.paste_id',
        (ride,) if ride else (),
    )
    groups = defaultdict(list)
    for row in rows:
        groups[(row['segment_id'], row['name'])].append(row)
    sections = []
    for (segment_id, name), rows in groups.items():
        efforts = [row for row in rows if row['source'] is not None]
        attempts = []
        for effort in efforts:
            source = ''
            if effort['effort_id']:
                href = f'https://www.strava.com/activities/{effort["external_activity_id"]}/segments/{effort["effort_id"]}'
                source = f'<a href="{escape(href, quote=True)}">Strava effort</a>'
            elif effort['external_activity_id']:
                href = f'https://www.strava.com/activities/{effort["external_activity_id"]}'
                source = f'<a href="{escape(href, quote=True)}">Strava activity</a>'
            provenance = {'api':'Strava API', 'both':'Strava API and My Results paste',
                          'paste':'My Results paste · displayed time'}[effort['source']]
            linked = (f'<a href="/activities/{escape(effort["activity_id"], quote=True)}">RideWorks ride</a>'
                      if effort['activity_id'] else '<span>RideWorks ride link unavailable</span>')
            when = (local_time(effort['start_time'], compact=True) if effort['start_time']
                    else escape(effort['calendar_day']))
            review = ''
            if effort['source'] == 'paste':
                pasted = PastedRow(effort['calendar_day'], effort['seconds'], effort['external_activity_id'])
                matches = candidates(store, segment_id, pasted, api_only=True)
                if matches:
                    pid = effort['paste_id']
                    review = f'''<details class="segment-later-match"><summary>Review possible API match</summary>
<form action="/segments/history/match" method="post">
<input type="hidden" name="nonce" value="{escape(settings.nonce, quote=True)}">
<input type="hidden" name="paste_id" value="{pid}">
<label for="segment-match-{pid}">Saved API effort</label>
<select id="segment-match-{pid}" name="effort" required><option value="">Choose a match</option>
{options(matches)}</select><button>Confirm same effort</button></form></details>'''
            attempts.append(f'<li>{when}<strong>{duration(effort["seconds"])}</strong>'
                            f'<span>{provenance}</span>{source}{linked}{review}</li>')
        best = (f'<p>{"Fastest saved on this ride" if ride else "Fastest saved effort"} · '
                f'{duration(min(row["seconds"] for row in efforts))} · {len(efforts)} saved</p>') if efforts else ''
        sections.append(f'<section class="panel segment-card"><h2>{escape(name)}</h2>{best}'
                        f'<ul class="segment-attempts">{"".join(attempts)}</ul></section>')
    if not sections:
        sections.append('<p>No saved efforts for this ride.</p>' if ride else '<p>No watched segments yet.</p>')
    form = ''
    if not ride:
        notice = escape(settings.segment_notice or '')
        form = f'''<section class="panel segment-add"><h2>Add segment</h2>
<p>Paste an effort link from one of your Strava Zwift rides. Standalone segment links are unsupported.</p>
<form action="/segments/add" method="post" data-settings-action>
<input type="hidden" name="nonce" value="{escape(settings.nonce, quote=True)}">
<label for="segment-link">Strava activity-effort link</label>
<input id="segment-link" name="link" type="url" maxlength="500" required>
<button type="submit">Save effort</button></form><p role="status">{notice}</p></section>'''
    imports = ''
    if not ride:
        imports = import_form([(key, name) for key, name in groups], settings.nonce)
        preview = settings.current_history_preview()
        if preview and filters.get('preview') == ['1']:
            watch = store.connection.execute('SELECT * FROM strava_watched_segments WHERE segment_id=?',
                                             (preview['segment_id'],)).fetchone()
            imports = preview_panel(store, preview, settings.nonce, watch) + imports
    return shell('Segments', f'''<header><h1>Segments</h1>{heading}
<p>Only saved efforts are shown. Strava history may be incomplete.</p></header>
<div class="segments-content">{form}{imports}{"".join(sections)}</div>''', active='segments')
