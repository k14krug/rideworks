"""Home presentation using the existing RideWorks shell and evidence boundary."""
from datetime import datetime
from decimal import Decimal
from html import escape
import json
from urllib.parse import urlencode

from .dashboard import dashboard
from .goals import query_zone
from .web import browser_time, detail_rows, duration, icon, local_time, shell


def safe_json(value):
    return json.dumps(value,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')


def miles(value):
    return 'Unavailable' if value is None else f'{value:,.1f} mi'


def pace(value, target_miles, days_in_year):
    weekly_target = target_miles * 7 / days_in_year
    if round(value,1) == 0:
        return f'On target pace ({weekly_target:,.1f} mi/week)'
    return f'{abs(value):,.1f} mi {"ahead of" if value > 0 else "behind"} target pace ({weekly_target:,.1f} mi/week)'


def annual_goal_meter(goal):
    """Show actual completion against today's arithmetic annual target pace.

    Reuse the dashboard's existing goal and target-to-date values. Both
    positions are capped at the bar's 0–100% range; underlying miles are not.
    """
    target = goal['target_miles']
    actual = goal['actual_miles']
    expected = goal['target_to_date']
    actual_pct = min(100.0, max(0.0, 100.0 * actual / target))
    expected_pct = min(100.0, max(0.0, 100.0 * expected / target))
    start_x = 10 * min(actual_pct, expected_pct)
    gap_width = 10 * abs(actual_pct - expected_pct)
    marker_x = 10 * expected_pct
    direction = 'behind' if goal['pace_difference'] < 0 else 'ahead'
    # Use SVG coordinates rather than inline CSS: the site's Content Security
    # Policy disallows style attributes, which would put the marker at x=0.
    gap = (f'<rect class="home-goal-pace-gap home-goal-pace-gap-{direction}" '
           f'x="{start_x:.4f}" y="5" width="{gap_width:.4f}" height="10"/>'
           if round(goal['pace_difference'], 1) != 0 and gap_width > 0 else '')
    label = f'Target pace today: {expected:,.1f} mi ({expected_pct:.1f}% of annual goal)'
    tooltip = escape(label, quote=True)
    return (f'<div class="home-goal-meter" data-actual-percent="{actual_pct:.4f}" '
            f'data-target-pace-percent="{expected_pct:.4f}">'
            f'<progress id="annual-mileage-progress" value="{min(actual, target)}" '
            f'max="{target}" aria-label="Annual mileage progress"></progress>'
            f'<svg class="home-goal-pace-overlay" viewBox="0 0 1000 20" '
            f'preserveAspectRatio="none" role="img" tabindex="0" aria-label="{tooltip}">'
            f'<title>{escape(label)}</title>{gap}'
            f'<line class="home-goal-pace-marker" x1="{marker_x:.4f}" y1="0" '
            f'x2="{marker_x:.4f}" y2="20"/>'
            f'<path class="home-goal-pace-tip" d="M{marker_x-9:.4f} 0 '
            f'L{marker_x+9:.4f} 0 L{marker_x:.4f} 7 Z"/></svg></div>')


def recent_ride_link(row, rating):
    """Ride title with the same Relative Effort category used on Activities."""
    label = rating['category'] if rating and rating.get('status') == 'available' else 'Not rated'
    slug = rating['slug'] if rating and rating.get('status') == 'available' else 'unavailable'
    title = escape(row['title'])
    identity = escape(row['activity_id'], quote=True)
    description = escape(f'Relative effort: {label}', quote=True)
    accessible = escape(f'{row["title"]} · Relative effort: {label}', quote=True)
    return (f'<a class="home-recent-ride" href="/activities/{identity}" '
            f'title="{description}" aria-label="{accessible}">'
            f'<span class="home-effort-dot effort-{slug}" aria-hidden="true"></span>'
            f'{title}</a>')


def weekly_chart(weeks):
    values = [value for w in weeks for value in (w['bar_miles'],w['needed_miles_per_week']) if value is not None]
    maximum = max(values,default=0) or 1
    bars, points, lines = [], [], []
    path = ''
    for i, week in enumerate(weeks):
        value, needed = week['bar_miles'], week['needed_miles_per_week']
        height = 120*(value or 0)/maximum
        day = datetime.fromisoformat(week['start']).strftime('%b %d')
        label = miles(value)
        kind = week['bar_kind']
        partial = ' home-mileage-current' if week['current'] else ''
        context = 'actual, partial week' if week['current'] else 'actual'
        bars.append(f'<g data-week="{week["start"]}" data-bar-kind="{kind}" data-mileage-value="{label}" tabindex="0" role="img" aria-label="Week of {day}, {context}: {label}" aria-describedby="mileage-tooltip"><rect class="home-mileage-hit" x="{40+i*45}" y="18" width="38" height="125"/><rect class="home-mileage-bar home-mileage-{kind}{partial}" x="{45+i*45}" y="{140-height:.3f}" width="26" height="{height:.3f}"/>')
        if value is None:
            bars.append(f'<text x="{58+i*45}" y="132" text-anchor="middle">—</text>')
        if i % 3 == 0 or i == 11:
            bars.append(f'<text x="{58+i*45}" y="160" text-anchor="middle">{day}</text>')
        bars.append('</g>')
        if needed is None:
            if path: lines.append(f'<path class="home-needed-line" d="{path}"/>'); path = ''
        else:
            px, py = 58+i*45, 140-120*needed/maximum
            path += f'{"L" if path else "M"}{px},{py:.3f} '
            label = miles(needed)
            points.append(f'<g data-needed-week="{week["start"]}" data-mileage-value="{label}" tabindex="0" role="img" aria-label="Week of {day}, needed average: {label}" aria-describedby="mileage-tooltip"><circle class="home-mileage-hit" cx="{px}" cy="{py:.3f}" r="10"/><circle class="home-needed-point" cx="{px}" cy="{py:.3f}" r="3.5"/></g>')
    if path: lines.append(f'<path class="home-needed-line" d="{path}"/>')
    return f'''<svg class="home-chart" id="home-mileage-chart" viewBox="0 0 600 180" role="group" aria-label="Completed weekly cycling miles and needed average miles per week toward the annual goal">
<line class="chart-grid" x1="40" x2="585" y1="140" y2="140"/><line class="chart-grid" x1="40" x2="585" y1="20" y2="20"/>
<text x="35" y="143" text-anchor="end">0</text><text x="35" y="24" text-anchor="end">{maximum:.0f}</text>{''.join(bars)}{''.join(lines)}{''.join(points)}</svg>
<output id="mileage-tooltip" class="home-mileage-tooltip" role="status" hidden></output>'''


def power_chart(performance, zone):
    series = performance['rolling']
    known = [s['point']['average_watts'] for s in series if s['point']]
    if not known:
        return '<p class="empty">No current eligible 20-minute results in this range.</p>'
    start = datetime.fromisoformat(performance['range_start'])
    end = datetime.fromisoformat(performance['range_end'])
    span = (end-start).total_seconds()
    low, high = max(0,min(known)-15), max(known)+15
    x = lambda stamp:40+545*(datetime.fromisoformat(stamp)-start).total_seconds()/span
    y = lambda watts:140-120*(watts-low)/(high-low)
    parts = []
    path = ''
    for i, step in enumerate(series):
        point = step['point']
        if point is None:
            if path:
                parts.append(f'<path class="home-power-line" d="{path}"/>'); path = ''
            continue
        px, py = x(step['at']), y(point['average_watts'])
        until = x(series[i+1]['at']) if i+1 < len(series) else 585
        path += f'{"L" if path else "M"}{px:.3f},{py:.3f} H{until:.3f} '
        parts.append(f'<a href="/activities/{point["activity_id"]}"><circle class="home-power-point" data-activity-id="{point["activity_id"]}" data-at="{step["at"]}" cx="{px:.3f}" cy="{py:.3f}" r="3"><title>{point["rounded_watts"]} W · {escape(point["title"])}</title></circle></a>')
    if path:
        parts.append(f'<path class="home-power-line" d="{path}"/>')
    return f'''<svg class="home-chart" id="home-power-chart" viewBox="0 0 600 180" role="img" aria-labelledby="power-chart-title"><title id="power-chart-title">20-minute rolling 42-day best over the past year, from current Performance history</title>
<line class="chart-grid" x1="40" x2="585" y1="20" y2="20"/><line class="chart-grid" x1="40" x2="585" y1="140" y2="140"/>
<text x="35" y="24" text-anchor="end">{high:.0f}</text><text x="35" y="143" text-anchor="end">{low:.0f}</text>
<text x="40" y="160">{start.astimezone(zone).strftime('%b %Y')}</text><text x="585" y="160" text-anchor="end">{end.astimezone(zone).strftime('%b %Y')}</text>{''.join(parts)}</svg>'''


def home_page(store, query='', *, cache_writes=None):
    """Render Home; supplied (stress, classification) batches belong to caller."""
    own_cache_writes=cache_writes is None
    pending=([],[]) if own_cache_writes else cache_writes
    with store._transaction(write=True):
        html=_home_page(store, query, cache_writes=pending)
        if own_cache_writes:
            from .planning import write_history_caches
            write_history_caches(store,pending)
        return html


def _home_page(store, query='', *, cache_writes):
    zone = query_zone(query,'home_tz')
    if zone is None:
        return shell('Home','''<div class="home-redesign"><header><h1>Home</h1></header><section class="panel"><h2>Cycling mileage and Performance</h2><p>Invalid timezone. Supply one valid timezone or omit the parameter to use America/Los_Angeles.</p><p><a href="/activities">Activities</a> · <a href="/performance">Performance</a></p></section></div>''',active='home')
    data = dashboard(store,zone.key)
    goal, ytd, performance = data['goal'], data['ytd'], data['performance']
    target = data['target_miles']
    settings = '/settings?'+urlencode({'tz':zone.key})+'#annual-goal'
    progress = f'<p><a href="{settings}">Set annual goal</a></p>'
    goal_note = progress
    goal_summary = ''
    if target is not None:
        display_target = format(Decimal(target),',f')
        progress = f'<p>Annual target: {escape(display_target)} mi · <a href="{settings}">Edit goal</a></p>'
        if goal:
            goal_summary = f'<p>{goal["percent"]:.1f}% complete · {miles(goal["remaining_miles"])} remaining</p>'
            goal_note = f'<p>{pace(goal["pace_difference"], goal["target_miles"], goal["calendar_days_in_year"])}</p>'
            needed = goal['needed_miles_per_week']
            needed_text = 'Unavailable' if needed is None else f'{needed:,.1f} mi/week'
            progress += f'{annual_goal_meter(goal)}{goal_summary}<p id="needed-weekly">Needed average: {needed_text}</p>{goal_note}'
        else:
            progress += '<p>Remaining miles: Unavailable</p><p id="needed-weekly">Needed average: Unavailable</p><p>No supported YTD distance.</p>'
    def card(name,title,value,note,symbol):
        missing = ' class="metric-unavailable"' if value == 'Unavailable' else ''
        return f'<div class="home-quick-fact" id="home-{name}"><h2>{icon(symbol)}{title}</h2><strong{missing}>{value}</strong>{note}</div>'
    weekly_note = ''
    if data['last7']['miles'] is not None and data['prior7']['miles'] is not None:
        difference = data['last7']['miles']-data['prior7']['miles']
        weekly_note = f'<p>{abs(difference):,.1f} mi {"more" if difference>0 else "less"} than previous 7 days</p>' if round(difference,1) else '<p>Same mileage as previous 7 days</p>'
    recent_mileage = card('this-week','This Week',miles(data['this_week']['miles']),
                          '<p>Monday through today · actual cycling miles</p>','distance')
    recent_mileage += card('last7','Last 7 Days',miles(data['last7']['miles']),weekly_note,'distance')
    def power_summary(point):
        if point is None:
            return 'Unavailable','<p>No current eligible result.</p>'
        return f'{point["rounded_watts"]} W',f'<p>{browser_time(point,compact=True)}</p><a href="/activities/{point["activity_id"]}">{escape(point["title"])}</a>'
    current, current_note = power_summary(performance['current'])
    latest, latest_note = power_summary(performance['latest'])
    comparison = performance['recent']
    insights = []
    if comparison and comparison['available']:
        diff = comparison['current']['rounded_watts']-comparison['prior']['rounded_watts']
        text = f'Latest eligible best-20: {abs(diff)} W {"above" if diff>0 else "below"} the previous six-week best.' if diff else 'Latest eligible best-20 matches the previous six-week best.'
        insights.append(text)
    insight_panel = '<details class="home-insights"><summary>Recent performance context</summary>'+''.join(f'<p>{escape(text)}</p>' for text in insights)+'<p>The best-20 comparison uses the accepted (Activity start − 42 days, Activity start) window, excluding both endpoints and the current ride. Details are available in Activity Review.</p></details>' if insights else ''
    # All Home stress consumers share pending writes. The request flushes only
    # after Training State, HTML and the response wrapper have finished.
    from .planning import plan
    from .planning_page import today_card
    advisor = today_card(plan(store,zone.key,as_of=datetime.fromisoformat(data['as_of']),cache_writes=cache_writes),compact=True,show_status=False,hide_provisional_reason=True)
    from .relative_effort import for_store as relative_effort_ratings
    # Use the same historical classifications as Activities and Ride Details.
    ratings = relative_effort_ratings(store,cache_writes=cache_writes[0]) if data['recent'] else {}
    rows = []
    for row in data['recent']:
        rows.append(f'''<tr class="home-recent-row" data-activity-id="{row['activity_id']}"><td data-label="Date">{browser_time(row,compact=True)}</td><td data-label="Ride">{recent_ride_link(row, ratings.get(row['activity_id']))}</td><td data-label="Distance">{miles(row['distance']/1609.344 if row['distance'] is not None else None)}</td><td data-label="Duration">{duration(row['duration'])}</td><td data-label="Avg Pwr" class="home-avg-power">{'Unavailable' if row['average_power'] is None else f'{row["average_power"]:,g} W'}</td></tr>''')
    recent = f'<table class="home-recent-table"><thead><tr><th>Date</th><th>Ride</th><th>Distance</th><th>Duration</th><th>Avg Pwr</th></tr></thead><tbody>{"".join(rows)}</tbody></table>' if rows else '<p class="empty">No cycling Activities yet.</p>'
    week_rows = ''.join(f'<tr><td>{w["start"]}</td><td>{miles(w["miles"])}</td><td>{miles(g["needed_miles_per_week"])}</td><td>{w["file_count"]}</td><td>{w["api_count"]}</td><td>{w["distance_unavailable"]}</td></tr>' for w,g in zip(data['weeks'],data['weekly_goal']))
    details = [('Browser timezone',zone.key),('YTD start',ytd['start']),('As of',data['as_of']),
        ('YTD contributing Activities',ytd['contributing_activities']),('YTD file distance',miles(ytd['file_miles'])),
        ('YTD file contribution count',ytd['file_count']),('YTD API distance',miles(ytd['api_miles'])),
        ('YTD API contribution count',ytd['api_count']),('YTD distance unavailable',ytd['distance_unavailable']),
        ('Cycling Activities without supported date',data['diagnostics']['date_unavailable']),
        ('Cycling source dates with unknown timezone',data['diagnostics']['timezone_unknown']),
        ('Last 7 days start',data['last7']['start']),('Previous 7 days start',data['prior7']['start']),
        ('Previous 7 days distance',miles(data['prior7']['miles'])),
        ('This week actual distance',miles(data['this_week']['miles'])),
        ('Included classifications',str(data['diagnostics']['included_classifications'])),
        ('Excluded classifications',str(data['diagnostics']['excluded_classifications']))]
    if goal:
        details += [('Calendar days elapsed',goal['calendar_days_elapsed']),('Calendar days in year',goal['calendar_days_in_year']),
                    ('Linear target to date (mi)',goal['target_to_date']),('Pace difference (mi)',goal['pace_difference']),
                    ('Remaining calendar days after today',goal['remaining_calendar_days']),
                    ('Needed average miles per week',goal['needed_miles_per_week'])]
    sync_status = 'Last sync: '+local_time(data['successful_sync'],compact=True) if data['successful_sync'] else 'No successful sync recorded'
    sync = f'<p class="home-sync">{sync_status} · <a href="/settings">Settings</a></p>'
    from .training_state_page import training_home
    training = training_home(store, zone.key, cache_writes=cache_writes[0])
    compact = {k:v for k,v in data.items() if k!='recent'}
    compact['recent'] = [{k:r[k] for k in ('activity_id','title','activity_type','start_time','absolute_time','date_text','distance','duration','distance_source','duration_source','average_power','average_power_source')} for r in data['recent']]
    return shell('Home',f'''<div class="home-redesign"><header class="home-heading"><div><h1>Home</h1><p>{data['year']} cycling mileage · Virtual Ride + outdoor Ride</p></div>{sync}</header>
<div class="home-lead"><section class="panel home-summary" id="home-recent-mileage" aria-label="Recent mileage and eligible power"><div class="home-quick-grid">{recent_mileage}{card('current','Current 42-day best',current,current_note,'power')}{card('latest','Latest eligible 20-minute ride',latest,latest_note,'power')}</div></section>{advisor}</div>
<div class="home-layout"><section class="panel home-recent"><div class="home-panel-heading"><h2>Recent Activities</h2><a href="/activities">View all Activities</a></div>{recent}</section><div class="home-companions">{training}<section class="panel home-performance"><div class="home-panel-heading"><h2>20-minute Performance</h2><a href="/performance">View Performance</a></div>{power_chart(performance,zone)}</section></div></div>
<div class="home-progress-layout"><section class="panel home-mileage"><div class="home-panel-heading"><h2>Mileage Progress</h2><span>Last 12 weeks · miles</span></div>{weekly_chart(data['weekly_goal'])}<p class="home-mileage-legend"><span class="legend-actual">Bars = actual miles</span><span class="legend-needed">Line = needed average/week</span></p></section><section class="panel home-goal-progress"><h2>Annual Mileage Goal</h2><strong>{miles(ytd['miles'])} YTD</strong>{progress}</section></div>
<section class="panel home-supporting" aria-labelledby="home-supporting-title"><h2 id="home-supporting-title">Context &amp; supporting details</h2>{insight_panel}<details class="home-weekly-details"><summary>Weekly distances</summary><p>Monday–Sunday weeks; outlined current bar is actual Monday-through-today mileage. Needed pace uses remaining mileage and calendar days after each Sunday; current pace uses today. Required points apply to the goal year.</p><div class="home-evidence-table"><table><thead><tr><th>Week of</th><th>Actual mi</th><th>Needed mi/week</th><th>File</th><th>API</th><th>Missing</th></tr></thead><tbody>{week_rows}</tbody></table></div></details>
<details class="home-diagnostics"><summary>Mileage evidence &amp; calendar boundaries</summary>{detail_rows(details)}<p>File-backed understood distance precedes current API summary distance. Unspecified CSV units are excluded. Known zero distance counts. Supported dates with unknown timezone use their source date; missing dates are excluded from period totals. Future Activities are excluded from totals. Weekly periods are local calendar buckets; YTD includes evidence through the as-of instant. Mileage is recalculated from retained source summaries. Needed weekly average is remaining goal mileage divided by remaining calendar days after today, times seven; it is arithmetic goal progress, not a training recommendation. Recent Avg Pwr prefers file session or a single TCX lap summary, then current API summary; CSV watts and raw streams are not used.</p></details></section>
<script id="dashboard-data" type="application/json">{safe_json(compact)}</script><script src="/static/planning.js" defer></script><script src="/static/home.js" defer></script></div>''',active='home')
