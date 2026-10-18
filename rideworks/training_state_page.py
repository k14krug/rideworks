"""Training State in the established local shell."""
from calendar import monthrange
from datetime import date
from html import escape
from .goals import query_zone
from .training_state import training_state
from .web import shell
from .home import safe_json

HELP = '''<details class="training-help"><summary>How these numbers work</summary>
<p>Fitness and Fatigue are 42- and 7-day exponential models of selected daily cycling stress. Form is yesterday’s Fitness minus yesterday’s Fatigue: the modeled start of the selected day. These describe your own training trend, rather than measured physiology or readiness.</p>
<p>Qualified virtual-ride power uses your approved dated FTP history. FIT estimates may correct small internal gaps (at most 15 seconds each and 1% overall); verified pauses are excluded and restart the calculation. API power remains observed-only. Recorded intervals are not automatically complete sessions.</p>
<p>When recorded power is incomplete but measured watts are sufficiently distributed, an Estimated session power score uses available-sample weighted power, the same source’s reported moving/timer duration and dated FTP. It requires at least 80% observed elapsed or verified active time, at least 50% of every sliding five-minute interval, and a continuous ten-minute observed segment. Missing watts are not filled. These guardrails do not prove complete effort; unknown gap intensity and pause semantics remain uncertain. Complete/corrected recorded-power results keep priority.</p>
<p>When no qualifying power session estimate exists, measured heart rate supplies an approximate stress estimate ahead of observed partial power. A supported HR stream is preferred; an independently valid same-source average HR and reported moving/active duration can supply an HR summary estimate when the stream is incomplete. Summary completeness and pause treatment are unverified. The retrospective assumptions are resting HR 58, maximum HR 158 and threshold HR 143 bpm unless accepted dated settings apply. One hour at threshold gives 100 HR stress points. The fixed response coefficient is 1.92; no HR-to-power multiplier is applied.</p>
<p>Each ride contributes one method. An unscored ride retains unavailable stress but contributes zero to the numeric curve; this can understate load. No-record dates are not confirmed rest days. The model starts at zero before the first usable score, with early history provisional. Observed work (kJ) is separate and contains no invented power.</p>
</details>'''


def training_page(store, query=''):
    zone=query_zone(query)
    header='<header><h1>Training State</h1><p>Your training trend and the rides behind it.</p><p><a href="/performance/ftp">FTP History &amp; comparison</a></p></header>'
    if zone is None:
        return shell('Training State',header+'<p>Invalid timezone. Supply one valid timezone or omit the parameter to use America/Los_Angeles.</p>'+HELP,active='training',page_class='training-redesign')
    data=training_state(store,zone.key)
    if not data['days']:
        return shell('Training State',header+'<section class="panel"><h2>No usable training stress yet</h2><p>Recorded rides remain available in Activities. Training State needs qualified power with dated FTP or usable measured HR and active duration.</p><a href="/activities">Open Activities</a></section>'+HELP,active='training',page_class='training-redesign')
    content=header+'''<section class="panel training-trend" aria-label="Training trend">
<div class="training-toolbar"><div role="group" aria-label="History range" id="training-ranges">
<button type="button" data-range="42" aria-pressed="false">6 weeks</button><button type="button" data-range="3months" aria-pressed="true">3 months</button><button type="button" data-range="12months" aria-pressed="false">12 months</button><button type="button" data-range="all" aria-pressed="false">All history</button></div>
<label class="training-date">Selected date <input type="date" id="training-date"></label></div>
<div class="training-values" aria-live="polite">
<div class="training-fitness"><span>Fitness · 42-day</span><strong id="training-fitness"></strong><span id="training-fitness-change"></span></div>
<div class="training-fatigue"><span>Fatigue · 7-day</span><strong id="training-fatigue"></strong><span id="training-fatigue-change"></span></div>
<div class="training-form"><span>Form · start of day</span><strong id="training-form"></strong><span id="training-form-change"></span></div></div>
<div class="training-toggles" role="group" aria-label="Chart lines">
<label class="training-fitness"><input type="checkbox" data-line="fitness" checked>Fitness</label>
<label class="training-fatigue"><input type="checkbox" data-line="fatigue" checked>Fatigue</label>
<label class="training-form"><input type="checkbox" data-line="form">Form</label></div>
<svg id="training-chart" viewBox="0 0 1000 770" tabindex="0" role="group" aria-label="Daily training trend. Left and right arrows select a date; Home and End select range endpoints."></svg>
<p id="training-chart-readout" class="training-readout"></p>
<p class="training-strip-legend"><span class="training-power">Power</span><span class="training-hr">HR estimate</span><span class="training-partial">Partial / mixed</span><span>× Unscored ride</span> · daily selected stress</p>
<p class="training-keyboard">Click or touch to select a day. Use arrow keys on the chart, or choose an exact date.</p></section>
<div class="training-lower"><section class="panel"><h2 id="training-day-heading">Selected day</h2><div id="training-day-detail" aria-live="polite"></div></section>
<section class="panel"><h2>Recent workload</h2><div id="training-workload"></div><p>Stress points and observed kJ have different meanings. Subtotals reflect recorded evidence; omissions do not assert zero effort.</p></section></div>
<noscript>Enable JavaScript for the interactive trend and exact daily inspection.</noscript>'''
    content+=HELP+f'<script id="training-state-data" type="application/json">{safe_json(data)}</script><script src="/static/training_state.js" defer></script>'
    return shell('Training State',content,active='training',page_class='training-redesign')


def home_fitness_chart(days):
    """Compact Fitness-only view of the full Training State page's 3-month range."""
    end = date.fromisoformat(days[-1]['day'])
    month_index = end.year * 12 + end.month - 1 - 3
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    cutoff = date(year, month, min(end.day, monthrange(year, month)[1])).isoformat()
    # Match training_state.js: three calendar months back, excluding cutoff.
    visible = [row for row in days if row['day'] > cutoff]
    values = [row['fitness'] for row in visible]
    minimum, maximum = min(values), max(values)
    padding = max(1.0, (maximum - minimum) * .1)
    low, high = max(0.0, minimum - padding), maximum + padding
    if high == low:
        high = low + 1.0
    x = lambda i: 48 + 528 * (i / (len(visible) - 1)) if len(visible) > 1 else 312
    y = lambda v: 142 - 118 * (v - low) / (high - low)
    grid = ''.join(
        f'<line x1="48" x2="576" y1="{y(low + (high-low)*i/2):.2f}" y2="{y(low + (high-low)*i/2):.2f}" class="home-fitness-grid"/>'
        f'<text x="40" y="{y(low + (high-low)*i/2)+4:.2f}" text-anchor="end">{low + (high-low)*i/2:.1f}</text>'
        for i in range(3))
    points = ' '.join(f'{x(i):.2f},{y(row["fitness"]):.2f}' for i, row in enumerate(visible))
    line = f'<polyline class="home-fitness-line" data-series="fitness" points="{points}"/>' if len(visible) > 1 else ''
    end_x, end_y = x(len(visible) - 1), y(visible[-1]['fitness'])
    start_label = date.fromisoformat(visible[0]['day']).strftime('%b %d')
    end_label = end.strftime('%b %d')
    labels = (f'<text x="48" y="173">{start_label}</text>'
              f'<text x="576" y="173" text-anchor="end">{end_label}</text>') if len(visible) > 1 else f'<text x="312" y="173" text-anchor="middle">{end_label}</text>'
    return f'''<svg id="home-fitness-chart" class="home-fitness-chart" viewBox="0 0 600 185" role="img" aria-labelledby="home-fitness-chart-title home-fitness-chart-desc" data-range-start="{visible[0]["day"]}" data-range-end="{visible[-1]["day"]}" data-point-count="{len(visible)}">
<title id="home-fitness-chart-title">Fitness over the past three months</title>
<desc id="home-fitness-chart-desc">RideWorks modeled Fitness from {visible[0]["day"]} through {end.isoformat()}. Current Fitness {visible[-1]["fitness"]:.1f}.</desc>
{grid}{line}<circle class="home-fitness-endpoint" cx="{end_x:.2f}" cy="{end_y:.2f}" r="4"/>{labels}</svg>'''


def training_home(store, zone_name, *, cache_writes=None):
    data = training_state(store, zone_name, cache_writes=cache_writes)
    days = data['days']
    heading = '<div class="home-panel-heading"><h2>Training State</h2><a href="/training-state">View Training State</a></div>'
    if not days:
        return f'<section class="panel home-training">{heading}<p class="empty">No usable training stress yet.</p></section>'
    current = days[-1]
    change = current['changes7']['fitness']
    if change is None:
        delta = '7-day change unavailable'
    elif round(change, 1) == 0:
        delta = 'No change from 7 days ago'
    else:
        direction = '↑' if change > 0 else '↓'
        delta = f'{direction} {abs(change):.1f} from 7 days ago'
    summary = (f'<div class="home-fitness-summary"><strong>{current["fitness"]:.1f}</strong>'
               f'<div><span>Current fitness</span><p class="home-fitness-change">{delta}</p></div></div>')
    return f'<section class="panel home-training">{heading}{summary}{home_fitness_chart(days)}</section>'
