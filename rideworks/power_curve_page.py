"""Shared Power Curve panel and exact cached comparison data."""
from html import escape
import json

from .goals import query_zone
from .power_curve import comparison


def panel(store, nonce, *, activity_id=None, query=''):
    zone = query_zone(query,'curve_tz')
    if zone is None:
        return '<section class="panel"><h2>Power curve</h2><p>Invalid timezone. Supply one valid curve_tz timezone or omit it to use America/Los_Angeles.</p></section>'
    data = comparison(store,activity_id=activity_id,zone=zone)
    payload = json.dumps(data, ensure_ascii=True, allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')
    activity = activity_id is not None
    heading = 'Power curve' if activity else 'Power-duration comparison'
    caption = ('This ride compared with prior performance. Baseline ends at this ride’s start, excluding this ride and every later activity.' if activity else
               'Strongest calculated average observed power at each supported duration.')
    choices = [('six','Previous 6 weeks'),('year','Prior 12 months'),('all','All earlier history')] if activity else [
        ('six','Last 6 weeks'),('previous','Previous 6 weeks'),('ytd','Year to date'),('last_year','Previous calendar year'),('all','All time')]
    def selector(name, selected):
        return f'<select id="curve-{name}" aria-label="Compare {name.upper()}">' + ''.join(
            f'<option value="{key}"{" selected" if key == selected else ""}>{label}</option>' for key,label in choices) + '</select>'
    left = '<strong>This ride</strong>' if activity else '<label for="curve-a">Compare A</label>'+selector('a','six')
    right = '<label for="curve-b">Compare with</label>'+selector('b','six') if activity else '<label for="curve-b">Compare B</label>'+selector('b','all')
    pending = ''
    if data['pending']:
        pending = f'''<div class="curve-pending" role="status"><p>{data['pending']:,} new or changed activities await Power Curve update. Outdated profiles are unavailable.</p>
<form method="post" data-settings-action action="/settings/power-curves/rebuild"><input type="hidden" name="nonce" value="{escape(nonce,quote=True)}"><button type="submit">Update power curves</button></form></div>'''
    return f'''<section class="panel power-curve-panel" id="power-curve-panel" aria-labelledby="power-curve-heading" data-curve-activity="{'true' if activity else 'false'}"{' hidden' if not activity else ''}>
<div class="curve-heading"><div><h2 id="power-curve-heading">{heading}</h2><p>{caption}</p></div><span>Watts</span></div>
{pending}<div class="curve-series-controls">
<div class="curve-series"><div><i class="curve-swatch curve-a-swatch" aria-hidden="true"></i>{left}</div><p id="curve-a-bounds"></p></div>
<div class="curve-series"><div><i class="curve-swatch curve-b-swatch" aria-hidden="true"></i>{right}</div><p id="curve-b-bounds"></p></div></div>
<svg id="power-curve-chart" role="img" tabindex="0" aria-label="Power-duration comparison: logarithmic duration axis, watts. Arrow keys inspect exact calculated durations; Enter opens the first available contributing activity." aria-describedby="curve-help"></svg>
<p id="curve-empty" role="status"></p>
<div class="curve-inspection" aria-live="polite"><article><h3 id="curve-a-label"></h3><strong id="curve-a-watts"></strong><p id="curve-a-ride"></p><a id="curve-a-link">Open contributing activity →</a><details><summary>Effort provenance</summary><dl id="curve-a-source"></dl></details></article>
<article><h3 id="curve-b-label"></h3><strong id="curve-b-watts"></strong><p id="curve-b-ride"></p><a id="curve-b-link">Open contributing activity →</a><details><summary>Effort provenance</summary><dl id="curve-b-source"></dl></details></article>
<article><h3 id="curve-duration"></h3><strong id="curve-difference"></strong><p>Calculated at the selected duration. Lines connect evaluated anchors; intervening durations are not exact results.</p></article></div>
<p id="curve-help">Hover, touch or use arrow keys to inspect. Each period point may come from a different qualifying Virtual Ride. Missing windows are unavailable, not zero. Comparisons describe recorded efforts, not FTP or readiness.</p>
<details class="curve-method"><summary>Power Curve method &amp; coverage</summary><p>Highest arithmetic mean over exactly d observed nonnegative watt samples at consecutive one-second timestamps. Missing samples, gaps, duplicate/backwards times and verified distinct active intervals split windows. Terminal stop observations may be valid endpoints; unverified timers cannot clip recorded samples. Outdoor power, CSV/summary watts and estimated stress do not create curves. File watt evidence takes precedence over validated high-resolution, full-length API fallback. Competing supported file sources are ambiguous at that duration.</p>
<p>Exact anchors: every second through 30, then a common grid with approximately 7% duration spacing (rounded up to integer seconds) plus familiar durations including 5 and 20 minutes and hour-plus efforts. No fixed long-duration cap; curves end at supported anchors. Raw averages and integer sums are inspectable. Ties use the earliest source window, then earliest contributing activity start and Activity ID. Period membership is [start, end), in absolute time; calendar-year bounds use the selected timezone. Activity prior 12 months uses calendar subtraction in UTC. Undated/unknown-zone activities cannot establish period membership.</p>
<p>Method: {data['method']} · Grid: {data['grid']}. Profiles use retained source observations and update through normal sync or the explicit update above. No raw source calculation occurs when inspecting or changing periods.</p></details>
<noscript>Enable JavaScript to inspect the Power Curve. Stored source evidence and the existing 20-minute results remain available.</noscript>
<script type="application/json" id="power-curve-data">{payload}</script><script src="/static/power_curve.js" defer></script></section>'''
