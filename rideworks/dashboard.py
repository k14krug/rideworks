"""Read-only mileage presentation and accepted Performance snapshots."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from math import fsum

from .goals import annual_goal, browser_zone
from .history import presentation
from .performance import performance_history
from .performance_view import performance_view
from .recent_context import select_recent_context

CYCLING = ('ride', 'virtual ride', 'cycling', 'biking')
METRES_PER_MILE = 1609.344


def mileage(rows, zone_name, *, as_of=None):
    zone = browser_zone(zone_name)
    as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        raise ValueError('Dashboard as-of must be an absolute instant.')
    today = as_of.astimezone(zone).date()
    cycling = [r for r in rows if r['activity_type'].casefold() in CYCLING]
    dated = []
    unknown = missing = future = 0
    for row in cycling:
        if row['start_time'] is None:
            missing += 1
            continue
        stamp = datetime.fromisoformat(row['start_time'])
        if row['absolute_time']:
            day = stamp.astimezone(zone).date()
            if stamp > as_of:
                future += 1
                continue
        else:
            day = stamp.date()  # Supported source date; no invented timezone.
            unknown += 1
            if day > today:
                future += 1
                continue
        dated.append((row, day))

    def period(start, end):
        selected = [r for r, day in dated if start <= day < end]
        amounts = {'file': [], 'api': []}
        unavailable = 0
        for row in selected:
            if row['distance'] is None:
                unavailable += 1
            else:
                kind = 'api' if row['distance_source']['context'] == 'Strava API summary' else 'file'
                amounts[kind].append(row['distance'])
        count = sum(len(values) for values in amounts.values())
        return dict(start=start.isoformat(), end_exclusive=end.isoformat(),
                    miles=fsum(v for values in amounts.values() for v in values)/METRES_PER_MILE
                        if count or not unavailable else None,
                    contributing_activities=count, dated_cycling_activities=len(selected),
                    file_count=len(amounts['file']), file_miles=fsum(amounts['file'])/METRES_PER_MILE,
                    api_count=len(amounts['api']), api_miles=fsum(amounts['api'])/METRES_PER_MILE,
                    distance_unavailable=unavailable, date_unavailable_excluded=missing)

    end = today + timedelta(days=1)
    monday = today - timedelta(days=today.weekday())
    weeks = [period(monday-timedelta(weeks=i), min(monday-timedelta(weeks=i-1), end))
             for i in range(11, -1, -1)]
    for week in weeks:
        cutoff = date.fromisoformat(week['end_exclusive'])
        week['ytd_miles'] = (period(date(today.year,1,1), cutoff)['miles']
                             if cutoff > date(today.year,1,1) else None)
    annual_series = []
    for year in range(today.year, today.year-3, -1):
        start = date(year, 1, 1)
        last = today if year == today.year else date(year, 12, 31)
        selected = [(r, day) for r, day in dated if start <= day <= last]
        known = [(r, day) for r, day in selected if r['distance'] is not None]
        points = []
        if known:
            points.append(dict(day=start.isoformat(), miles=0))
            amounts = []
            for day in sorted({day for _, day in known}):
                amounts.extend(r['distance'] for r, d in known if d == day)
                points.append(dict(day=day.isoformat(), miles=fsum(amounts)/METRES_PER_MILE))
            # Current YTD uses the accepted as-of cutoff. Historical source
            # coverage is unknown, so do not project prior years beyond their
            # last recorded distance.
            if year == today.year and points[-1]['day'] != last.isoformat():
                points.append(dict(day=last.isoformat(), miles=points[-1]['miles']))
        annual_series.append(dict(year=year, points=points,
                                  contributing_activities=len(known),
                                  distance_unavailable=len(selected)-len(known)))
    recent = sorted(cycling, key=lambda r:r['activity_id'])
    recent.sort(key=lambda r:(r['date_key'] is not None, r['date_key'] or ''), reverse=True)
    return dict(timezone=zone_name, as_of=as_of.isoformat(), today=today.isoformat(), year=today.year,
                ytd=period(date(today.year,1,1), end), last7=period(today-timedelta(days=6), end),
                prior7=period(today-timedelta(days=13), today-timedelta(days=6)), weeks=weeks,
                this_week=dict(weeks[-1]), annual_series=annual_series,
                recent=recent[:6], diagnostics=dict(cycling_activities=len(cycling),
                    excluded_noncycling=len(rows)-len(cycling), date_unavailable=missing,
                    timezone_unknown=unknown, future_excluded=future,
                    included_classifications=dict(Counter(r['activity_type'] for r in cycling)),
                    excluded_classifications=dict(Counter(r['activity_type'] for r in rows if r['activity_type'].casefold() not in CYCLING))))


def needed_weekly(year, day, actual, target):
    """Remaining goal over calendar time after the supplied day; no advice."""
    if target is None or actual is None or day.year != year:
        return None
    remaining = max(0, float(target)-actual)
    days = max(0, (date(year+1,1,1)-(day+timedelta(days=1))).days)
    return 0 if remaining == 0 else remaining*7/days if days else None


def weekly_goal(data):
    result = []
    for i, week in enumerate(data['weeks']):
        current = i == len(data['weeks'])-1
        day = date.fromisoformat(week['end_exclusive'])-timedelta(days=1)
        needed = needed_weekly(data['year'], day, week['ytd_miles'], data['target_miles'])
        result.append(dict(start=week['start'], as_of_day=day.isoformat(), current=current,
                           actual_miles=week['miles'], ytd_miles=week['ytd_miles'],
                           needed_miles_per_week=needed,
                           bar_miles=week['miles'], bar_kind='actual'))
    return result


def average_power(row):
    """Narrow Home summary evidence, independent of Performance inputs."""
    sources = row['sources']  # Already in accepted imported-at/Source-ID order.
    files = [s for s in sources if s['source']['kind'] not in ('strava_api','strava_export')]
    apis = [s for s in reversed(sources) if s['source']['kind']=='strava_api' and s['source']['is_current']]
    for source in files+apis:
        api = source['source']['kind']=='strava_api'
        value = source['summary'].get('values',{}).get('average_watts') if api else source['summary'].get('avg_power')
        context = 'Strava API summary' if api else f"{source['source']['content_format']} session"
        if value is None and source['source']['content_format']=='TCX':
            laps = source.get('xml_context',{}).get('lap_summaries',[])
            if len(laps)==1:
                value = laps[0].get('avg_power'); context = 'TCX single lap'
        if value is not None:
            return value,dict(source_id=source['source']['source_id'],context=context)
    return None,None


def goal_progress(year, today, actual, target):
    if target is None or actual is None:
        return None
    target = float(target)
    day = date.fromisoformat(today)
    days = (date(year+1,1,1)-date(year,1,1)).days
    elapsed = (day-date(year,1,1)).days+1
    expected = target * elapsed / days
    return dict(target_miles=target, actual_miles=actual, percent=100*actual/target,
                remaining_miles=max(0,target-actual), calendar_days_elapsed=elapsed,
                calendar_days_in_year=days, target_to_date=expected, pace_difference=actual-expected,
                remaining_calendar_days=max(0,days-elapsed),
                needed_miles_per_week=needed_weekly(year,day,actual,target))


def dashboard(store, zone_name, *, as_of=None):
    as_of = as_of or datetime.now(timezone.utc)
    data = mileage([presentation(s) for s in store.activity_history()], zone_name, as_of=as_of)
    goal = annual_goal(store, data['year'])
    data['target_miles'] = goal['target_miles'] if goal else None
    data['goal'] = goal_progress(data['year'], data['today'], data['ytd']['miles'], data['target_miles'])
    data['weekly_goal'] = weekly_goal(data)
    for row in data['recent']:
        row['average_power'],row['average_power_source'] = average_power(row)
    history = performance_history(store)
    view = performance_view(history['points'], as_of=as_of)
    selected = {name:history['points'][index] if index is not None else None
                for name,index in view['summaries'].items() if name in ('current','latest')}
    start = view['range_starts']['1yr']
    seed = next((s for s in reversed(view['rolling']) if s['at'] <= start), None)
    series = ([dict(at=start,index=seed['index'])] if seed else []) + [s for s in view['rolling'] if s['at'] > start]
    data['performance'] = dict(policy=history['policy'], method=history['method'], pending=history['pending'],
        **selected, range_start=start, range_end=view['as_of'],
        rolling=[dict(at=s['at'], point=history['points'][s['index']] if s['index'] is not None else None)
                 for s in series],
        recent=select_recent_context(history, selected['latest']['activity_id']) if selected['latest'] else None)
    sync = store.connection.execute('SELECT successful_at FROM strava_sync_state WHERE singleton=1').fetchone()
    data['successful_sync'] = datetime.fromtimestamp(sync[0],timezone.utc).isoformat() if sync and sync[0] else None
    return data
