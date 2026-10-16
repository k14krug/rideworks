"""FTP comparison uses current Performance evidence and the athlete calendar."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from zoneinfo import ZoneInfo

from .ftp_history import snapshot
from .performance import performance_history
from .training_state import ftp_on, FTP_CALENDAR


def comparison(store):
    with store._transaction():
        history = snapshot(store)
        performance = performance_history(store)
        points = []
        for point in performance['points']:
            day = (datetime.fromisoformat(point['start_time']).astimezone(ZoneInfo(FTP_CALENDAR)).date().isoformat()
                   if point['absolute_time'] else point['date_day'])
            ftp = ftp_on(history['rows'], day, point['absolute_time'])
            watts = .95 * point['average_watts']
            proposed = int((Decimal(str(point['average_watts'])) * Decimal('.95')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            points.append(dict(activity_id=point['activity_id'], title=point['title'], date=day,
                               absolute_time=point['absolute_time'], raw_watts=point['average_watts'],
                               watts=watts, proposed=proposed, ftp=ftp,
                               category='unavailable' if ftp['value'] is None else 'above' if watts > ftp['value'] else 'below'))
        return dict(**history, points=points, pending=performance['pending'], missing_dates=performance['missing_dates'])


def page(store, nonce, *, message='', draft=None):
    from .web import shell
    from .home import safe_json
    data = comparison(store)
    draft = draft or {}
    data['draft'] = {k: draft.get(k, '') for k in ('date', 'watts')}
    content = f'''<header><div class="breadcrumb"><a href="/performance">Performance</a> / FTP History</div><h1>FTP History</h1><p>Compare dated FTP with 95% of each eligible ride’s best 20-minute power.</p></header>
<p>Dates use America/Los_Angeles. FTP unavailable means the comparison is unknown: a ride may predate the first setting, or its source timezone may leave the setting boundary uncertain. For an uncertain ride, choose and confirm the effective calendar date yourself; RideWorks will not infer an absolute ride time.</p>
<p id="ftp-message" role="status">{escape(message)}</p>
<section class="panel ftp-chart-panel" aria-label="FTP comparison">
<form id="ftp-range" class="ftp-controls"><label>From<input id="ftp-from" type="date" required></label><label>To<input id="ftp-to" type="date" required></label><button>Apply range</button><button type="button" id="ftp-reset">Reset to all</button></form>
<div class="legend ftp-legend"><span class="ftp-key">Blue: recorded FTP</span><label><input type="checkbox" data-category="above" checked>Orange: above FTP</label><label><input type="checkbox" data-category="below" checked>Gray: at or below FTP</label><label><input type="checkbox" data-category="unavailable" checked>Outline: FTP unavailable</label></div>
<svg id="ftp-chart" role="img" aria-label="Dated FTP step line and eligible 20-minute ride results"></svg>
<div class="ftp-navigator-wrap"><p>History range navigator · drag the window to pan or either handle to resize</p><svg id="ftp-navigator" viewBox="0 0 1000 88" role="group" aria-label="Date range navigator; use the handles to adjust the From and To dates"></svg></div>
<p id="ftp-count"></p><p id="ftp-hover" aria-live="polite">Select a ride below or tap a dot to propose an entry.</p>
<p>{data['pending']} Activities pending Performance update; {data['missing_dates']} eligible results without dates omitted.</p></section>
<section class="panel ftp-editor"><h2>Add a historical FTP value</h2><p>Ride power is evidence for your decision, not an automatic FTP estimate. A gray ride does not imply that FTP fell. A new earliest setting applies from its date through the day before the current first setting; earlier dates remain unknown.</p>
<form id="ftp-add" method="post" action="/performance/ftp/add"><input type="hidden" name="nonce" value="{escape(nonce, quote=True)}"><input type="hidden" name="revision" value="{data['revision']}">
<div class="ftp-controls"><label>Effective date<input id="ftp-date" name="date" type="date" required></label><label>FTP · W<input id="ftp-watts" name="watts" type="number" min="1" max="9007199254740991" step="1" required></label></div>
<p id="ftp-selection"></p><p id="ftp-preview" aria-live="polite"></p><button id="ftp-save" disabled>Save FTP entry</button> <button type="button" id="ftp-cancel">Cancel / clear</button></form></section>
<section class="panel"><h2>Eligible ride results</h2><p>Use the list to select overlapping points. All categories can be inspected.</p><div class="ftp-table"><table><thead><tr><th>Date</th><th>Activity</th><th>95% best 20 min</th><th>Comparison</th><th>Action</th></tr></thead><tbody id="ftp-rides"></tbody></table></div><div class="ftp-controls"><button id="ftp-prev">Previous</button><span id="ftp-page"></span><button id="ftp-next">Next</button></div></section>
<noscript>Enable JavaScript to inspect the graph and preview an FTP insertion.</noscript>
<script id="ftp-data" type="application/json">{safe_json(data)}</script><script src="/static/ftp.js" defer></script>'''
    return shell('FTP History', content, active='performance', page_class='ftp-page')
