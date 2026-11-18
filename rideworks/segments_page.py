"""Segments screen backed only by the locally saved watchlist and efforts."""
from collections import defaultdict
from html import escape
from urllib.parse import parse_qs

from .history import presentation
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
                    e.start_time, e.elapsed_seconds, l.activity_id
             FROM strava_watched_segments w
             LEFT JOIN strava_saved_efforts e USING (segment_id)
             LEFT JOIN strava_saved_effort_ride_links l USING (external_activity_id)"""
    rows = store.connection.execute(
        sql + (' WHERE l.activity_id=?' if ride else '') +
        ' ORDER BY w.name COLLATE NOCASE, w.segment_id, e.start_time DESC, e.effort_id',
        (ride,) if ride else (),
    )
    groups = defaultdict(list)
    for row in rows:
        groups[(row['segment_id'], row['name'])].append(row)
    sections = []
    for (_, name), rows in groups.items():
        efforts = [row for row in rows if row['effort_id'] is not None]
        attempts = []
        for effort in efforts:
            source = f'https://www.strava.com/activities/{effort["external_activity_id"]}/segments/{effort["effort_id"]}'
            linked = (f'<a href="/activities/{escape(effort["activity_id"], quote=True)}">RideWorks ride</a>'
                      if effort['activity_id'] else '<span>RideWorks ride link unavailable</span>')
            attempts.append(f'<li>{local_time(effort["start_time"], compact=True)}'
                            f'<strong>{duration(effort["elapsed_seconds"])}</strong>'
                            f'<a href="{escape(source, quote=True)}">Strava effort</a> {linked}</li>')
        best = (f'<p>{"Fastest saved on this ride" if ride else "Fastest saved effort"} · '
                f'{duration(min(row["elapsed_seconds"] for row in efforts))}</p>') if efforts else ''
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
    return shell('Segments', f'''<header><h1>Segments</h1>{heading}
<p>History starts with saved efforts. It covers rides you select and eligible new rides checked during Sync.</p></header>
<div class="segments-content">{form}{"".join(sections)}</div>''', active='segments')
