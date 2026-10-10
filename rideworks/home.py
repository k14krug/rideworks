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


def pace(value):
    if round(value,1) == 0:
        return 'On calendar pace'
    return f'{abs(value):,.1f} mi {"ahead of" if value > 0 else "behind"} calendar pace'


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


def home_page(store, query=''):
    zone = query_zone(query,'home_tz')
    if zone is None:
        return shell('Home','''<header><h1>Home</h1></header><section class="panel" data-calendar-timezone="home_tz"><h2>Cycling mileage and Performance</h2><p>Enable JavaScript to use your browser timezone for calendar mileage and annual goals.</p><p><a href="/activities">Activities</a> · <a href="/performance">Performance</a></p></section>''',active='home')
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
            goal_note = f'<p>{pace(goal["pace_difference"])}</p>'
            needed = goal['needed_miles_per_week']
            needed_text = 'Unavailable' if needed is None else f'{needed:,.1f} mi/week'
            progress += f'<progress id="annual-mileage-progress" value="{min(goal["actual_miles"],goal["target_miles"])}" max="{goal["target_miles"]}" aria-label="Annual mileage progress"></progress>{goal_summary}<p id="needed-weekly">Needed average: {needed_text}</p>{goal_note}'
        else:
            progress += '<p>Remaining miles: Unavailable</p><p id="needed-weekly">Needed average: Unavailable</p><p>No supported YTD distance.</p>'
    def card(name,title,value,note,symbol):
        return f'<section class="metric home-metric" id="home-{name}"><div>{icon(symbol)}<h2>{title}</h2></div><strong>{value}</strong>{note}</section>'
    weekly_note = ''
    if data['last7']['miles'] is not None and data['prior7']['miles'] is not None:
        difference = data['last7']['miles']-data['prior7']['miles']
        weekly_note = f'<p>{abs(difference):,.1f} mi {"more" if difference>0 else "less"} than previous 7 days</p>' if round(difference,1) else '<p>Same mileage as previous 7 days</p>'
    recent_mileage = f'''<section class="metric home-metric home-recent-mileage" id="home-recent-mileage">
<div>{icon('distance')}<h2>Recent Mileage</h2></div><div class="home-mileage-submetrics">
<div id="home-this-week"><h3>This Week</h3><strong>{miles(data['this_week']['miles'])}</strong><p>Monday through today · actual cycling miles</p></div>
<div id="home-last7"><h3>Last 7 Days</h3><strong>{miles(data['last7']['miles'])}</strong>{weekly_note}</div>
</div></section>'''
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
        latest_note += f'<p>{escape(text)}</p>'
        insights.append(text)
    insight_panel = '<section class="panel home-insights"><h2>Recent context</h2>'+''.join(f'<p>{escape(text)}</p>' for text in insights)+'<details><summary>How this is calculated</summary><p>The best-20 comparison uses the accepted (Activity start − 42 days, Activity start) window, excluding both endpoints and the current ride. Details are available in Activity Review.</p></details></section>' if insights else ''
    rows = []
    for row in data['recent']:
        rows.append(f'''<tr class="home-recent-row" data-activity-id="{row['activity_id']}"><td>{browser_time(row,compact=True)}</td><td><a href="/activities/{row['activity_id']}">{escape(row['title'])}</a><span>{escape(row['activity_type'])}</span></td><td>{miles(row['distance']/1609.344 if row['distance'] is not None else None)}</td><td>{duration(row['duration'])}</td><td class="home-avg-power">{'Unavailable' if row['average_power'] is None else f'{row["average_power"]:,g} W'}</td></tr>''')
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
    sync = f'<p>Last sync: {local_time(data["successful_sync"],compact=True)} · <a href="/settings">Settings</a></p>' if data['successful_sync'] else ''
    from .training_state_page import training_home
    training = training_home(store, zone.key)
    compact = {k:v for k,v in data.items() if k!='recent'}
    compact['recent'] = [{k:r[k] for k in ('activity_id','title','activity_type','start_time','absolute_time','date_text','distance','duration','distance_source','duration_source','average_power','average_power_source')} for r in data['recent']]
    return shell('Home',f'''<header class="home-heading" data-calendar-timezone="home_tz"><div><h1>Home</h1><p>{data['year']} cycling mileage · Virtual Ride + outdoor Ride</p></div>{sync}</header>
<div class="metrics home-summary">{recent_mileage}{card('current','Current 42-day best',current,current_note,'power')}{card('latest','Latest eligible 20-minute ride',latest,latest_note,'power')}</div>
<div class="home-layout"><section class="panel home-recent"><div class="home-panel-heading"><h2>Recent Activities</h2><a href="/activities">View all Activities</a></div>{recent}</section>
<section class="panel home-mileage"><div class="home-panel-heading"><h2>Mileage Progress</h2><span>Last 12 weeks · miles</span></div>{weekly_chart(data['weekly_goal'])}<p class="home-mileage-legend"><span class="legend-actual">Bars = actual miles</span><span class="legend-needed">Line = needed average/week</span></p><p>Monday–Sunday weeks; outlined current bar is actual Monday-through-today mileage. Needed pace uses remaining mileage and calendar days after each Sunday; current pace uses today. Required points apply to the goal year.</p><div class="home-goal-progress"><strong>{miles(ytd['miles'])} YTD</strong>{progress}</div>
<details><summary>Weekly distances</summary><div class="home-evidence-table"><table><thead><tr><th>Week of</th><th>Actual mi</th><th>Needed mi/week</th><th>File</th><th>API</th><th>Missing</th></tr></thead><tbody>{week_rows}</tbody></table></div></details></section>
<section class="panel home-performance"><div class="home-panel-heading"><h2>20-minute Performance</h2><a href="/performance">View Performance</a></div>{power_chart(performance,zone)}<p>Rolling 42-day best · past year · current Performance-v2 evidence. Gaps mean no eligible result.</p></section>{insight_panel}{training}</div>
<details class="panel home-diagnostics"><summary>Mileage evidence &amp; calendar boundaries</summary>{detail_rows(details)}<p>File-backed understood distance precedes current API summary distance. Unspecified CSV units are excluded. Known zero distance counts. Supported dates with unknown timezone use their source date; missing dates are excluded from period totals. Future Activities are excluded from totals. Weekly periods are local calendar buckets; YTD includes evidence through the as-of instant. Mileage is recalculated from retained source summaries. Needed weekly average is remaining goal mileage divided by remaining calendar days after today, times seven; it is arithmetic goal progress, not a training recommendation. Recent Avg Pwr prefers file session or a single TCX lap summary, then current API summary; CSV watts and raw streams are not used.</p></details>
<script id="dashboard-data" type="application/json">{safe_json(compact)}</script><script src="/static/home.js" defer></script>''',active='home')
