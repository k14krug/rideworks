"""Training State in the established local shell."""
from html import escape
from .goals import query_zone
from .training_state import training_state
from .web import shell
from .home import safe_json

HELP = '''<details class="training-help"><summary>How these numbers work</summary>
<p>Fitness and Fatigue are 42- and 7-day exponential models of selected daily cycling stress. Form is yesterday’s Fitness minus yesterday’s Fatigue: the modeled start of the selected day. These describe your own training trend, rather than measured physiology or readiness.</p>
<p>Qualified virtual-ride power uses your approved dated FTP history. FIT estimates may correct small internal gaps (at most 15 seconds each and 1% overall); verified pauses are excluded and restart the calculation. API power remains observed-only. Recorded intervals are not automatically complete sessions.</p>
<p>When power is unavailable or materially partial, measured heart rate supplies an approximate stress estimate. A supported HR stream is preferred; an independently valid same-source average HR and reported moving/active duration can supply an HR summary estimate when the stream is incomplete. Summary completeness and pause treatment are unverified. The retrospective assumptions are resting HR 58, maximum HR 158 and threshold HR 143 bpm unless accepted dated settings apply. One hour at threshold gives 100 HR stress points. The fixed response coefficient is 1.92; no HR-to-power multiplier is applied.</p>
<p>Each ride contributes one method. An unscored ride retains unavailable stress but contributes zero to the numeric curve; this can understate load. No-record dates are not confirmed rest days. The model starts at zero before the first usable score, with early history provisional. Observed work (kJ) is separate and contains no invented power.</p>
</details>'''


def training_page(store, query=''):
    zone=query_zone(query)
    header='<header data-calendar-timezone="tz"><h1>Training State</h1><p>Your training trend and the rides behind it.</p></header>'
    if zone is None:
        return shell('Training State',header+'<p>Enable JavaScript to use your browser’s local calendar.</p>'+HELP,active='training')
    data=training_state(store,zone.key)
    if not data['days']:
        return shell('Training State',header+'<section class="panel"><h2>No usable training stress yet</h2><p>Recorded rides remain available in Activities. Training State needs qualified power with dated FTP or usable measured HR and active duration.</p><a href="/activities">Open Activities</a></section>'+HELP,active='training')
    content=header+HELP+'''<section class="panel training-trend" aria-label="Training trend">
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
    content+=f'<script id="training-state-data" type="application/json">{safe_json(data)}</script><script src="/static/training_state.js" defer></script>'
    return shell('Training State',content,active='training')


def training_home(store, zone_name):
    data=training_state(store,zone_name)
    day=data['days'][-1] if data['days'] else None
    values=(f'Fitness {day["fitness"]:.1f} · Fatigue {day["fatigue"]:.1f} · Form {day["form"]:.1f}' if day else 'No usable training stress yet')
    return f'''<section class="panel home-training"><div class="home-panel-heading"><h2>Training State</h2><a href="/training-state">View Training State</a></div><p>{escape(values)}</p><p>42-/7-day modeled trend · Form at start of day · selected cycling stress</p></section>'''
