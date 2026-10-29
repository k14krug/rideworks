"""Home presentation using the existing RideWorks shell and evidence boundary."""
from datetime import date, datetime, timedelta
from calendar import month_abbr, monthrange
from decimal import Decimal
from html import escape
import json
from math import ceil, isfinite
from urllib.parse import urlencode

from .dashboard import dashboard
from .goals import query_zone
from .performance_view import months_before
from .web import browser_time, detail_rows, duration, icon, local_time, shell


def safe_json(value):
    return json.dumps(value,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')


def miles(value):
    return 'Unavailable' if value is None else f'{value:,.1f} mi'


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


def annual_mileage_chart(series, today):
    """Show a calendar-clamped window of cumulative recorded yearly mileage."""
    current = date.fromisoformat(today)
    first, last = max(1, current.month-3), min(12, current.month+1)
    count = last-first+1

    def position(day):
        # Month fractions align March in leap and common years; Jan 1 of the
        # next year denotes the right boundary of a December window.
        return 80+495*((day.month-first)+(day.day-1)/monthrange(day.year,day.month)[1])/count

    visible = []
    for s in series:
        start = date(s['year'], first, 1)
        end = date(s['year']+1, 1, 1) if last == 12 else date(s['year'], last+1, 1)
        points = [(date.fromisoformat(p['day']), p['miles']) for p in s['points']]
        if not points or points[-1][0] < start:
            visible.append([])
            continue
        before = [p for p in points if p[0] <= start]
        clipped = [(start, before[-1][1])] if before else []
        clipped.extend(p for p in points if start < p[0] < end)
        if points[-1][0] >= end:
            prior = [p for p in points if p[0] < end]
            clipped.append((end, prior[-1][1]))
        visible.append(clipped)

    legend = ''.join(
        f'<span class="home-annual-legend-{i}"><b>{s["year"]}</b><span>{miles(s["points"][-1]["miles"]) + (" YTD" if i == 0 else " recorded") if s["points"] else "No data"}</span></span>'
        for i, s in enumerate(series))
    legend_html = f'<div class="home-annual-legend">{legend}</div>'
    if not any(visible):
        return '<p class="home-annual-empty">No recorded cycling distances in this window.</p>'+legend_html
    minimum = min(points[0][1] for points in visible if points)
    maximum = max(value for points in visible for _, value in points)
    if maximum == minimum:
        maximum = minimum + max(1, abs(minimum)*.05)
    def x(day, year):
        return 575 if day.year > year else position(day)
    def y(value):
        return 260-225*(value-minimum)/(maximum-minimum)
    axes = [f'<line class="chart-grid" x1="80" x2="575" y1="{v}" y2="{v}"/>' for v in (35, 147.5, 260)]
    for value, pos in ((maximum,39),((maximum+minimum)/2,151.5),(minimum,264)):
        axes.append(f'<text x="72" y="{pos}" text-anchor="end">{value:,.0f}</text>')
    for month in range(first,last+1):
        px = 80+495*(month-first+.5)/count
        axes.append(f'<text class="home-annual-month" x="{px:.3f}" y="286" text-anchor="middle">{month_abbr[month]}</text>')
    paths = []
    for index in (2,1,0):
        s, points = series[index], visible[index]
        if not points:
            continue
        path = f'M{x(points[0][0],s["year"]):.3f},{y(points[0][1]):.3f} '
        for day, value in points[1:]:
            path += f'H{x(day,s["year"]):.3f} V{y(value):.3f} '
        paths.append(f'<path class="home-annual-line home-annual-{index}" data-year="{s["year"]}" d="{path}"/>')
        last_day = date.fromisoformat(s['points'][-1]['day'])
        if points[-1][0] == last_day and last_day.month <= last:
            value = points[-1][1]
            px, py = x(last_day,s['year']), y(value)
            description = f'{s["year"]}: {miles(value)} recorded through {last_day.isoformat()}'
            paths.append(f'<g tabindex="0" role="img" aria-label="{description}" aria-describedby="annual-tooltip" data-annual-value="{description}"><circle class="home-annual-hit" cx="{px:.3f}" cy="{py:.3f}" r="12"/><circle class="home-annual-point home-annual-{index}" cx="{px:.3f}" cy="{py:.3f}" r="4"/></g>')
            if index == 0:
                anchor = 'start' if px < 200 else 'end'
                paths.append(f'<text class="home-annual-endpoint" x="{px:.3f}" y="{max(18,py-10):.3f}" text-anchor="{anchor}">{value:,.1f}</text>')
    missing = sum(s['distance_unavailable'] for s in series)
    coverage = f' {missing} cycling Activities lack distance.' if missing else ''
    return f'''<svg class="home-chart home-annual-chart" id="home-annual-chart" viewBox="0 0 600 300" role="group" aria-labelledby="annual-chart-title annual-chart-desc" data-y-min="{minimum}" data-y-max="{maximum}"><title id="annual-chart-title">Recorded cumulative cycling mileage by year</title><desc id="annual-chart-desc">Calendar months align across years. Lines show recorded distances only; history may be incomplete. Prior years end at the last known distance.{coverage} The vertical axis starts at the lowest visible starting value, not necessarily zero. Endpoints provide dates and values. Goal pace is arithmetic, not a training recommendation.</desc>{''.join(axes)}{''.join(paths)}</svg><output id="annual-tooltip" class="home-mileage-tooltip" role="status" hidden></output>{legend_html}'''


def trend_axes(start, end, low, high, months, step, *, years=False):
    """Shared Home SVG frame; calendar ticks do not resample source values."""
    span = (end-start).total_seconds() if isinstance(start, datetime) else (end-start).days
    parts = [f'<line class="chart-grid" x1="80" x2="570" y1="{y}" y2="{y}"/>' for y in (36,156)]
    for value, py in ((high,40),(low,160)):
        label = f'{value:.0f}' if years else f'{value:.1f}'
        parts.append(f'<text x="72" y="{py}" text-anchor="end">{label}</text>')
    for offset in range(months, -1, -step):
        tick = months_before(end,offset)
        delta = (tick-start).total_seconds() if isinstance(start, datetime) else (tick-start).days
        px = 80+490*delta/(span or 1)
        anchor = 'start' if offset == months else 'end' if offset == 0 else 'middle'
        label = tick.strftime('%b %Y' if years else '%b')
        label_class = 'home-axis-year' if years else 'home-axis-month'
        if offset not in (0,months): label_class += ' home-axis-intermediate'
        parts.append(f'<line class="chart-grid" x1="{px:.3f}" x2="{px:.3f}" y1="36" y2="156"/><text class="{label_class}" x="{px:.3f}" y="186" text-anchor="{anchor}">{label}</text>')
    return ''.join(parts)


def fitness_chart(data):
    """Present accepted daily Fitness, using the full page's calendar cutoff."""
    end = date.fromisoformat(data['today'])
    start = months_before(end,6)
    days = [d for d in data['days'] if start.isoformat() < d['day'] <= end.isoformat()]
    known = [d for d in days if d['fitness'] is not None and isfinite(d['fitness'])]
    if not known:
        return '<p class="empty">No usable Fitness history in the last six months.</p>'
    values = [d['fitness'] for d in known]
    padding = max((max(values)-min(values))*.1,.5)
    low, high = max(0,min(values)-padding), max(values)+padding
    span = (end-start).days
    parts, path, previous = [], '', None
    for day in days:
        stamp = date.fromisoformat(day['day'])
        value = day['fitness']
        if value is None or not isfinite(value):
            if path: parts.append(f'<path class="home-power-line" d="{path}"/>')
            path, previous = '', None
            continue
        if previous is not None and stamp-previous != timedelta(days=1):
            parts.append(f'<path class="home-power-line" d="{path}"/>')
            path = ''
        px = 80+490*(stamp-start).days/span
        py = 156-120*(value-low)/(high-low)
        path += f'{"L" if path else "M"}{px:.3f},{py:.3f} '
        # A dot also makes isolated source days visible without bridging gaps.
        parts.append(f'<circle class="home-power-point home-fitness-point" data-day="{day["day"]}" data-value="{value}" cx="{px:.3f}" cy="{py:.3f}" r="1.5"/>')
        previous = stamp
    if path: parts.append(f'<path class="home-power-line" d="{path}"/>')
    latest = known[-1]
    px = 80+490*(date.fromisoformat(latest['day'])-start).days/span
    py = 156-120*(latest['fitness']-low)/(high-low)
    label = f'{latest["fitness"]:.1f}'
    # Short histories can end at the left edge. Keep their label in the frame.
    anchor = 'start' if px < 150 else 'end'
    parts.append(f'<g class="home-chart-endpoint" data-day="{latest["day"]}" data-value="{latest["fitness"]}"><circle class="home-power-point" cx="{px:.3f}" cy="{py:.3f}" r="4"/><text x="{px:.3f}" y="{py-12:.3f}" text-anchor="{anchor}">{label}</text></g>')
    note = f'<p class="home-trend-note">Latest available: {latest["day"]}.</p>' if latest['day'] != data['today'] else ''
    provisional = ' Early history is provisional.' if any(d.get('early_history_provisional') for d in days) else ''
    return f'''<svg class="home-chart home-trend-chart" id="home-fitness-chart" viewBox="0 0 600 200" role="img" aria-labelledby="fitness-chart-title fitness-chart-desc" data-range-start="{start}" data-range-end="{end}" data-y-min="{low}" data-y-max="{high}">
<title id="fitness-chart-title">Fitness (42-day) over the last six months</title><desc id="fitness-chart-desc">Latest available Fitness: {label} on {latest['day']}. Model of selected daily cycling stress, not measured physiology or readiness. Unscored rides can understate load; dates without records are not confirmed rest.{provisional}</desc>
{trend_axes(start,end,low,high,6,1)}{''.join(parts)}</svg>{note}'''


def power_chart(performance, zone):
    series = performance['rolling']
    known = [s['point']['average_watts'] for s in series if s['point']]
    if not known:
        return '<p class="empty">No current eligible 20-minute results in this range.</p>'
    start = datetime.fromisoformat(performance['range_start'])
    end = datetime.fromisoformat(performance['range_end'])
    span = (end-start).total_seconds()
    low, high = max(0,min(known)-15), max(known)+15
    x = lambda stamp:80+490*(datetime.fromisoformat(stamp)-start).total_seconds()/(span or 1)
    y = lambda watts:156-120*(watts-low)/(high-low)
    parts = []
    path = ''
    for i, step in enumerate(series):
        point = step['point']
        if point is None:
            if path:
                parts.append(f'<path class="home-power-line" d="{path}"/>'); path = ''
            continue
        px, py = x(step['at']), y(point['average_watts'])
        until = x(series[i+1]['at']) if i+1 < len(series) else 570
        path += f'{"L" if path else "M"}{px:.3f},{py:.3f} H{until:.3f} '
        parts.append(f'<a href="/activities/{point["activity_id"]}"><circle class="home-power-point" data-activity-id="{point["activity_id"]}" data-at="{step["at"]}" cx="{px:.3f}" cy="{py:.3f}" r="3"><title>{point["rounded_watts"]} W · {escape(point["title"])}</title></circle></a>')
    if path:
        parts.append(f'<path class="home-power-line" d="{path}"/>')
    current = performance['current']
    description = 'Current rolling 42-day best unavailable; no eligible result in the current window.'
    if current is not None:
        description = f'Current rolling 42-day best: {current["rounded_watts"]} W as of {performance["range_end"]}.'
        parts.append(f'<g class="home-chart-endpoint" data-at="{performance["range_end"]}" data-value="{current["average_watts"]}"><circle class="home-power-point" cx="570" cy="{y(current["average_watts"]):.3f}" r="4"/><text x="570" y="{y(current["average_watts"])-12:.3f}" text-anchor="end">{current["rounded_watts"]} W</text></g>')
    return f'''<svg class="home-chart home-trend-chart" id="home-power-chart" viewBox="0 0 600 200" role="img" aria-labelledby="power-chart-title power-chart-desc" data-range-start="{performance['range_start']}" data-range-end="{performance['range_end']}"><title id="power-chart-title">20-minute rolling 42-day best over the past year, from current Performance history</title><desc id="power-chart-desc">{escape(description)} Gaps mean no eligible result.</desc>
{trend_axes(start.astimezone(zone),end.astimezone(zone),low,high,12,4,years=True)}{''.join(parts)}</svg>'''+('' if current else '<p class="home-trend-note">Current 42-day best unavailable.</p>')


def home_page(store, query='', *, cache_writes=None):
    own_cache_writes = cache_writes is None
    pending = ([], []) if own_cache_writes else cache_writes
    with store._transaction(write=True):
        html = _home_page(store, query, cache_writes=pending)
        if own_cache_writes:
            from .planning import write_history_caches
            write_history_caches(store, pending)
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
    if target is not None:
        display_target = format(Decimal(target),',f')
        if goal:
            needed = goal['needed_miles_per_week']
            progress = f'<p class="home-annual-remaining">{miles(goal["remaining_miles"])} to goal</p>'
            if goal['remaining_miles'] == 0:
                progress += '<p>Yearly goal reached.</p>'
            elif needed is None:
                progress += '<p>Year ended; weekly goal pace unavailable.</p>'
            else:
                progress += f'<p>Ride {ceil(needed):,} miles/week to meet yearly goal of {escape(display_target)} miles.</p>'
        else:
            progress = '<p>Remaining miles unavailable; no supported YTD distance.</p>'
    annual_chart = annual_mileage_chart(data['annual_series'], data['today'])
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
    # Defer both cache batches until the full response has been rendered.
    from .planning import plan
    from .planning_page import today_card
    advisor = today_card(plan(store,zone.key,as_of=datetime.fromisoformat(data['as_of']),cache_writes=cache_writes),compact=True)
    from .relative_effort import for_store as relative_effort_ratings
    ratings = relative_effort_ratings(store, cache_writes=cache_writes[0]) if data['recent'] else {}
    rows = []
    for row in data['recent']:
        rows.append(f'''<tr class="home-recent-row" data-activity-id="{row['activity_id']}"><td data-label="Date">{browser_time(row,compact=True)}</td><td data-label="Ride">{recent_ride_link(row, ratings.get(row['activity_id']))}</td><td data-label="Distance">{miles(row['distance']/1609.344 if row['distance'] is not None else None)}</td><td data-label="Duration">{duration(row['duration'])}</td><td data-label="Avg Pwr" class="home-avg-power">{'Unavailable' if row['average_power'] is None else f'{row["average_power"]:,g} W'}</td></tr>''')
    recent = f'<div class="home-recent-list"><table class="home-recent-table"><thead><tr><th>Date</th><th>Ride</th><th>Distance</th><th>Duration</th><th>Avg Pwr</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>' if rows else '<p class="empty">No cycling Activities yet.</p>'
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
<div class="home-layout"><section class="panel home-recent"><div class="home-panel-heading"><h2>Recent Activities</h2><a href="/activities">View all Activities</a></div>{recent}</section><div class="home-companions">{training}<section class="panel home-performance home-trend"><div class="home-panel-heading"><h2>20-minute Performance</h2><a href="/performance">View Performance</a></div><p class="home-trend-subtitle">Best 20-minute power · Last 12 months</p>{power_chart(performance,zone)}<p class="home-trend-note">Rolling 42-day best · current Performance-v2 evidence. Gaps mean no eligible result.</p></section></div></div>
<div class="home-progress-layout"><section class="panel home-mileage"><div class="home-panel-heading"><h2>Mileage Progress</h2><span>Last 12 weeks · miles</span></div>{weekly_chart(data['weekly_goal'])}<p class="home-mileage-legend"><span class="legend-actual">Bars = actual miles</span><span class="legend-needed">Line = needed average/week</span></p><p>Outlined current week is partial · actual Monday-through-today mileage.</p></section><section class="panel home-goal-progress"><h2>Mileage by Year</h2>{annual_chart}<div class="home-annual-goal">{progress}</div></section></div>
<section class="panel home-supporting" aria-labelledby="home-supporting-title"><h2 id="home-supporting-title">Context &amp; supporting details</h2>{insight_panel}<details class="home-weekly-details"><summary>Weekly distances</summary><p>Monday–Sunday weeks; outlined current bar is actual Monday-through-today mileage. Needed pace uses remaining mileage and calendar days after each Sunday; current pace uses today. Required points apply to the goal year.</p><div class="home-evidence-table"><table><thead><tr><th>Week of</th><th>Actual mi</th><th>Needed mi/week</th><th>File</th><th>API</th><th>Missing</th></tr></thead><tbody>{week_rows}</tbody></table></div></details>
<details class="home-diagnostics"><summary>Mileage evidence &amp; calendar boundaries</summary>{detail_rows(details)}<p>File-backed understood distance precedes current API summary distance. Unspecified CSV units are excluded. Known zero distance counts. Supported dates with unknown timezone use their source date; missing dates are excluded from period totals. Future Activities are excluded from totals. Weekly periods are local calendar buckets; YTD includes evidence through the as-of instant. Mileage is recalculated from retained source summaries. Needed weekly average is remaining goal mileage divided by remaining calendar days after today, times seven; it is arithmetic goal progress, not a training recommendation. Recent Avg Pwr prefers file session or a single TCX lap summary, then current API summary; CSV watts and raw streams are not used.</p></details></section>
<script id="dashboard-data" type="application/json">{safe_json(compact)}</script><script src="/static/planning.js" defer></script><script src="/static/home.js" defer></script></div>''',active='home')
