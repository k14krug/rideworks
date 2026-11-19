"""Segments screen backed only by the locally saved watchlist and efforts."""
from collections import defaultdict
from datetime import datetime
from html import escape
from urllib.parse import parse_qs, urlencode

from .history import presentation
from .segment_import import PastedRow, candidates
from .segment_import_page import import_form, options, preview_panel
from .web import duration, local_time, shell

COLUMNS = (('date', 'Date'), ('seconds', 'Time'), ('effort_rank', 'Rank / Behind best'),
           ('avg_power', 'Avg Power'), ('avg_hr', 'Avg HR'))
SHORT_HISTORY = 10


def segments_link(*, anchor='', **filters):
    query = urlencode({key: value for key, value in filters.items() if value})
    return escape('/segments' + ('?' + query if query else '') + ('#' + anchor if anchor else ''), quote=True)


def add_segment(nonce, notice):
    return f'''<section class="panel segment-add" id="add-segment">
<h2>Add segment</h2><p>Paste an effort link from one of your Strava Zwift rides.</p>
<form action="/segments/add" method="post" data-settings-action>
<input type="hidden" name="nonce" value="{escape(nonce, quote=True)}">
<label for="segment-link">Strava activity-effort link</label>
<input id="segment-link" name="link" type="url" maxlength="500" required>
<button type="submit">Save effort</button></form><p role="status">{escape(notice or '')}</p>
</section>'''


def possible_matches(store, efforts, nonce):
    exceptions = []
    for effort in efforts:
        if effort['source'] != 'paste':
            continue
        pasted = PastedRow(effort['calendar_day'], effort['seconds'], effort['external_activity_id'])
        matches = candidates(store, effort['segment_id'], pasted, api_only=True)
        if not matches:
            continue
        pid = effort['paste_id']
        exceptions.append(f'''<li><form class="segment-later-match" action="/segments/history/match" method="post">
<input type="hidden" name="nonce" value="{escape(nonce, quote=True)}">
<input type="hidden" name="paste_id" value="{pid}">
<label for="segment-match-{pid}">Pasted effort · {escape(pasted.calendar_day)} · {duration(pasted.displayed_seconds)}</label>
<select id="segment-match-{pid}" name="effort" required><option value="">Choose a saved API effort</option>
{options(matches)}</select><button>Confirm same effort</button></form></li>''')
    if not exceptions:
        return ''
    return (f'<details class="segment-match-review"><summary>Review possible matches ({len(exceptions)})</summary>'
            f'<ul>{"".join(exceptions)}</ul></details>')


def metric_cell(value, unit, device=None):
    if value is None:
        return '<span aria-label="Unavailable">—</span>'
    suffix = ' <small>est.</small>' if unit == 'W' and device == 0 else ''
    return f'<span>{value:.10g} {unit}</span>{suffix}'


def history_table(efforts, name, sort, direction, links):
    headers = []
    for key, label in COLUMNS:
        active = key == sort
        next_direction = 'asc' if active and direction == 'desc' else 'desc'
        indicator = (' ↑' if direction == 'asc' else ' ↓') if active else ' ↕'
        aria_sort = f' aria-sort="{"ascending" if direction == "asc" else "descending"}"' if active else ''
        href = segments_link(**(links | {'sort': key, 'direction': next_direction}))
        headers.append(f'<th scope="col" role="columnheader"{aria_sort}><a href="{href}">{label}'
                       f'<span aria-hidden="true">{indicator}</span></a></th>')
    headers.append('<th scope="col" role="columnheader">Ride</th>')
    attempts = []
    for effort in efforts:
        linked = (f'<a href="/activities/{escape(effort["activity_id"], quote=True)}">RideWorks ride</a>'
                  if effort['activity_id'] else '<span>RideWorks ride link unavailable</span>')
        when = (local_time(effort['start_time'], compact=True) if effort['start_time']
                else escape(effort['calendar_day']))
        behind = f'+{duration(effort["behind_best"])}' if effort['behind_best'] else 'Best'
        rank = f'<span class="segment-rank">#{effort["effort_rank"]} · {behind}</span>'
        cells = (when, f'<strong>{duration(effort["seconds"])}</strong>',
                 rank,
                 metric_cell(effort['avg_power'], 'W', effort['device_watts']),
                 metric_cell(effort['avg_hr'], 'bpm'),
                 linked)
        attempts.append('<tr role="row">' + ''.join(
            f'<td role="cell"><span class="segment-cell-label" aria-hidden="true">{label}</span>'
            f'<div>{value}</div></td>'
            for label, value in zip([label for _, label in COLUMNS] + ['Ride'], cells)
        ) + '</tr>')
    return (f'<table class="segment-attempts" role="table" aria-label="{escape(name, quote=True)} saved efforts">'
            f'<thead role="rowgroup"><tr role="row">{"".join(headers)}</tr></thead>'
            f'<tbody role="rowgroup">{"".join(attempts)}</tbody></table>')


def date_key(row, zone):
    start = row['start_time']
    day = datetime.fromisoformat(start).astimezone(zone).date().isoformat() if start else row['calendar_day']
    return day, start or ''


def sorted_efforts(efforts, sort, direction, zone):
    by_date = sorted(efforts, key=lambda row: date_key(row, zone), reverse=sort != 'date' or direction == 'desc')
    if sort == 'date':
        return by_date
    known = sorted((row for row in by_date if row[sort] is not None), key=lambda row: row[sort],
                   reverse=direction == 'desc')
    return known + [row for row in by_date if row[sort] is None]


def segments_page(store, settings, query, zone):
    try:
        filters = {key: values[0] for key, values in parse_qs(query, max_num_fields=8).items()}
    except ValueError:
        filters = {}
    ride = filters.get('ride')
    selected = filters.get('segment')
    sort = filters.get('sort')
    if sort not in dict(COLUMNS):
        sort = 'date'
    direction = 'asc' if filters.get('direction') == 'asc' else 'desc'
    heading = ''
    if ride:
        snapshots = store.activity_history(ride)
        title = presentation(snapshots[0])['title'] if snapshots else 'Ride unavailable'
        heading = f'<p>{escape(title)} · <a href="/segments">All watched segments</a></p>'
    rows = store.connection.execute(
        """WITH ranked_efforts AS (
               SELECT *,
                      RANK() OVER (PARTITION BY segment_id ORDER BY seconds) AS effort_rank,
                      seconds - MIN(seconds) OVER (PARTITION BY segment_id) AS behind_best
               FROM strava_segment_history
           )
           SELECT w.segment_id, w.name, e.*, l.activity_id
           FROM strava_watched_segments w
           LEFT JOIN ranked_efforts e USING (segment_id)
           LEFT JOIN strava_saved_effort_ride_links l USING (external_activity_id)"""
        + (' WHERE l.activity_id=?' if ride else '')
        + ' ORDER BY w.name COLLATE NOCASE, w.segment_id, COALESCE(e.start_time,e.calendar_day) DESC, e.effort_id, e.paste_id',
        (ride,) if ride else (),
    )
    groups = defaultdict(list)
    for row in rows:
        groups[(row['segment_id'], row['name'])].append(row)

    draft = settings.current_history_draft()
    preview = settings.current_history_preview() if filters.get('preview') == '1' else None
    notice = settings.segment_history_notice
    import_target = filters.get('import') or (preview['segment_id'] if preview else None)

    sections = []
    for (segment_id, name), rows in groups.items():
        anchor = f'segment-{segment_id}'
        active = segment_id == selected
        full = active and filters.get('view') == 'all'
        attempts = [row for row in rows if row['source'] is not None]
        total = len(attempts)
        best = (f'<p>{"Fastest saved on this ride" if ride else "Fastest saved effort"} · '
                f'<strong>{duration(min(row["seconds"] for row in attempts))}</strong> · {total} saved</p>'
                if total else '<p>0 saved</p>')
        imports = ''
        if not ride:
            if import_target == segment_id:
                current = preview if preview and preview['segment_id'] == segment_id else None
                result = preview_panel(store, current, settings.nonce, {'name': name, 'segment_id': segment_id})
                imports = import_form(segment_id, settings.nonce, draft if draft.get('segment_id') == segment_id else {},
                                      notice if settings.segment_history_target == segment_id else None, result)
                action_href = segments_link(segment=segment_id, anchor=anchor)
                action = f'<a class="segment-secondary" href="{action_href}">Close import</a>'
            else:
                action_href = segments_link(**{'import': segment_id}, anchor='segment-import')
                action = f'<a class="segment-secondary" href="{action_href}" aria-label="Import history for {escape(name, quote=True)}">Import history</a>'
        else:
            action = ''
        history = ''
        if total:
            card_sort, card_direction = (sort, direction) if active else ('date', 'desc')
            ordered = sorted_efforts(attempts, card_sort, card_direction, zone)
            visible = ordered if full else ordered[:SHORT_HISTORY]
            links = dict(ride=ride, segment=segment_id, view='all' if full else '',
                         tz=filters.get('tz'), anchor=f'{anchor}-history')
            table = history_table(visible, name, card_sort, card_direction, links)
            more = ''
            if total > SHORT_HISTORY:
                href = segments_link(**(links | {'view': '' if full else 'all', 'sort': card_sort, 'direction': card_direction}))
                label = 'Show short history' if full else f'View all {total} efforts'
                more = f'<p><a href="{href}">{label}</a></p>'
            expanded = ' open' if active or ride else ''
            coverage = (' on this ride. Rank uses all saved efforts for this segment.' if ride else '')
            history = (f'<details class="segment-saved-list" id="{anchor}-history"{expanded}><summary>Saved history</summary>'
                       f'<p>Showing {len(visible)} of {total} saved efforts{coverage}</p>{table}{more}</details>')
        review = possible_matches(store, attempts, settings.nonce)
        sections.append(f'<section class="panel segment-card" id="{anchor}"><div class="segment-heading">'
                        f'<div><h2>{escape(name)}</h2>{best}</div>{action}</div>{imports}{history}{review}</section>')
    if not sections:
        sections.append('<p>No saved efforts for this ride.</p>' if ride else '<p>No watched segments yet.</p>')
    show_add = not ride and filters.get('add') == '1'
    add_link = ''
    form = ''
    if filters.get('history-status') == '1' and notice:
        form = f'<p role="status">{escape(notice)}</p>'
    if not ride:
        add_link = ('<a class="segment-secondary" href="/segments">Cancel add</a>' if show_add
                    else '<a class="segment-secondary" href="/segments?add=1#add-segment">Add segment</a>')
        if show_add:
            form = add_segment(settings.nonce, settings.segment_notice)
        elif settings.segment_notice and not form:
            form = f'<p role="status">{escape(settings.segment_notice)}</p>'
    return shell('Segments', f'''<header><div class="segment-heading"><h1>Segments</h1>{add_link}</div>{heading}
<p>Only saved efforts are shown. Strava history may be incomplete.</p></header>
<div class="segments-content">{form}{"".join(sections)}</div>''', active='segments', page_class='segments-page')
