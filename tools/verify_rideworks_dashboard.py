#!/usr/bin/env python3
"""Independent SQL/Decimal mileage and direct-scan Performance verification."""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rideworks.dashboard import dashboard
from rideworks.store import Store


def source_rows(db):
    """Inspect durable summaries directly; no production history presentation."""
    result=[]
    for identity, in db.execute('SELECT activity_id FROM activities'):
        files=[dict(r) for r in db.execute('''SELECT f.source_id,f.imported_at,f.content_format,s.*,
            x.context_json FROM sources f JOIN extractions e ON e.source_id=f.source_id
            JOIN sessions s ON s.extraction_id=e.extraction_id LEFT JOIN xml_context x ON x.extraction_id=e.extraction_id
            WHERE f.activity_id=? ORDER BY f.imported_at,f.source_id''',(identity,))]
        apis=[dict(json.loads(r[1]),_source_id=r[0]) for r in db.execute('''SELECT s.source_id,s.evidence_json FROM strava_api_sources s
            JOIN strava_api_activities a ON a.current_source_id=s.source_id WHERE s.activity_id=?
            ORDER BY s.imported_at DESC,s.source_id DESC''',(identity,))]
        csvs=[dict(r) for r in db.execute('SELECT * FROM strava_export_sources WHERE activity_id=? ORDER BY imported_at DESC,source_id DESC',(identity,))]
        kinds=[]
        for api in apis:
            sport=api.get('sport_type') or api.get('type')
            kinds.append('Virtual Ride' if sport=='VirtualRide' else 'Ride' if api.get('type')=='Ride' or sport in ('Ride','MountainBikeRide','GravelRide','EBikeRide','EMountainBikeRide') else api.get('type') or sport)
        kinds += [r['activity_type'] for r in csvs]
        kind=next((k for k in kinds if k),None)
        if kind is None:
            first=files[0] if files else {}
            sport=first.get('sport') or 'Activity'
            kind='Virtual Ride' if first.get('sub_sport')=='virtual_activity' else 'Ride' if sport.casefold() in ('cycling','biking') else sport.replace('_',' ').title()
        candidates=[f['start_time'] for f in files]+[a['start_date'] for a in apis]+[json.loads(c['evidence_json']).get('date_parsed') for c in csvs]
        stamp=None
        for text in candidates:
            if text:
                try:stamp=datetime.fromisoformat(text.replace('Z','+00:00'))
                except ValueError:continue
                if stamp.tzinfo:stamp=stamp.astimezone(timezone.utc)
                break
        distance=None;origin=None
        for f in files:
            value=f['total_distance']
            if value is None and f['content_format']=='TCX' and f['context_json']:
                laps=json.loads(f['context_json']).get('lap_summaries',[])
                if len(laps)==1:value=laps[0].get('distance_m')
            if value is not None:
                distance=Decimal(str(value));origin='file';break
        if distance is None:
            for a in apis:
                if a.get('distance') is not None:distance=Decimal(str(a['distance']));origin='api';break
        watts=None;power_source=None
        for f in files:
            value=f['avg_power'];context=f['content_format']+' session'
            if value is None and f['content_format']=='TCX' and f['context_json']:
                laps=json.loads(f['context_json']).get('lap_summaries',[])
                if len(laps)==1:value=laps[0].get('avg_power');context='TCX single lap'
            if value is not None:watts=value;power_source=dict(source_id=f['source_id'],context=context);break
        if watts is None:
            for a in apis:
                if a.get('average_watts') is not None:
                    watts=a['average_watts'];power_source=dict(source_id=a['_source_id'],context='Strava API summary');break
        result.append(dict(activity_id=identity,kind=kind,stamp=stamp,metres=distance,origin=origin,
            average_power=watts,average_power_source=power_source,
            file_api_conflict=bool(origin=='file' and any(a.get('distance') is not None and Decimal(str(a['distance']))!=distance for a in apis))))
    return result


def verify(store,data):
    rows=source_rows(store.connection)
    zone=ZoneInfo(data['timezone']);now=datetime.fromisoformat(data['as_of']);today=now.astimezone(zone).date()
    cycling=[r for r in rows if r['kind'].casefold() in ('ride','virtual ride','cycling','biking')]
    periods=[data['ytd'],data['last7'],data['prior7'],*data['weeks']]
    missing=sum(r['stamp'] is None for r in cycling)
    for period in periods:
        start=date.fromisoformat(period['start']);end=date.fromisoformat(period['end_exclusive'])
        members=[]
        for row in cycling:
            stamp=row['stamp']
            if stamp is None:continue
            day=stamp.astimezone(zone).date() if stamp.tzinfo else stamp.date()
            if (stamp.tzinfo and stamp>now) or day>today:continue
            if start<=day<end:members.append(row)
        known=[r for r in members if r['metres'] is not None]
        expected=sum((r['metres'] for r in known),Decimal(0))/Decimal('1609.344')
        if known or not members:
            assert period['miles'] is not None and abs(Decimal(str(period['miles']))-expected)<Decimal('0.000000001')
        else:assert period['miles'] is None
        assert period['contributing_activities']==len(known)
        assert period['distance_unavailable']==len(members)-len(known)
        assert period['date_unavailable_excluded']==missing
        for kind in ('file','api'):
            selected=[r for r in known if r['origin']==kind]
            assert period[kind+'_count']==len(selected)
            amount=sum((r['metres'] for r in selected),Decimal(0))/Decimal('1609.344')
            assert abs(Decimal(str(period[kind+'_miles']))-amount)<Decimal('0.000000001')
    assert data['diagnostics']['cycling_activities']==len(cycling)
    assert data['diagnostics']['excluded_noncycling']==len(rows)-len(cycling)
    assert data['diagnostics']['included_classifications']==dict(Counter(r['kind'] for r in cycling))
    assert data['year']==today.year and data['today']==today.isoformat()
    goal=store.connection.execute('SELECT target_miles FROM annual_mileage_goals WHERE year=?',(today.year,)).fetchone()
    assert data['target_miles']==(goal[0] if goal else None)
    def same(actual,expected):
        if expected is None:assert actual is None
        else:assert actual is not None and abs(Decimal(str(actual))-expected)<Decimal('0.000000001')
    def required(actual,day):
        if goal is None or actual is None or day.year!=today.year:return None
        remaining=max(Decimal(0),Decimal(goal[0])-actual)
        days=max(0,(date(today.year+1,1,1)-day).days-1)
        return Decimal(0) if remaining==0 else remaining*7/days if days else None
    if goal and data['goal']:
        target=Decimal(goal[0]);actual=Decimal(str(data['ytd']['miles']))
        days=(date(today.year+1,1,1)-date(today.year,1,1)).days
        elapsed=(today-date(today.year,1,1)).days+1
        for field,expected in dict(percent=100*actual/target,remaining_miles=max(Decimal(0),target-actual),
                target_to_date=target*elapsed/days,pace_difference=actual-target*elapsed/days).items():
            assert abs(Decimal(str(data['goal'][field]))-expected)<Decimal('0.000000001')
        assert data['goal']['calendar_days_in_year']==days
        assert data['goal']['calendar_days_elapsed']==elapsed
        same(data['goal']['needed_miles_per_week'],required(actual,today))
        assert data['goal']['remaining_calendar_days']==days-elapsed
    assert data['this_week']==data['weeks'][-1]
    assert len(data['weekly_goal'])==len(data['weeks'])==12
    for i,(week,point) in enumerate(zip(data['weeks'],data['weekly_goal'])):
        cutoff=date.fromisoformat(week['end_exclusive']);day=cutoff-timedelta(days=1)
        values=[];unknown=0
        for row in cycling:
            stamp=row['stamp']
            if stamp is None or (stamp.tzinfo and stamp>now):continue
            local=stamp.astimezone(zone).date() if stamp.tzinfo else stamp.date()
            if date(today.year,1,1)<=local<cutoff:
                if row['metres'] is None:unknown+=1
                else:values.append(row['metres'])
        cumulative=(sum(values,Decimal(0))/Decimal('1609.344') if values or not unknown else None) if cutoff>date(today.year,1,1) else None
        same(week['ytd_miles'],cumulative);same(point['ytd_miles'],cumulative)
        needed=required(cumulative,day)
        same(point['needed_miles_per_week'],needed)
        current=i==11
        assert point['current']==current and point['start']==week['start'] and point['as_of_day']==day.isoformat()
        assert point['bar_kind']=='actual'
        same(point['actual_miles'],Decimal(str(week['miles'])) if week['miles'] is not None else None)
        same(point['bar_miles'],Decimal(str(week['miles'])) if week['miles'] is not None else None)
    assert len(data['recent'])==min(7,len(cycling))
    for recent in data['recent']:
        row=next(r for r in rows if r['activity_id']==recent['activity_id'])
        assert recent['average_power']==row['average_power']
        assert recent['average_power_source']==row['average_power_source']
    # Independent result selection; cached best-20 calculations are already accepted.
    by_id={r['activity_id']:r for r in rows}
    eligible=[]
    for r in store.connection.execute("SELECT activity_id,result_json FROM performance_history WHERE policy='virtual-power-evidence-v2' AND duration_seconds=1200"):
        value=json.loads(r['result_json']);row=by_id[r['activity_id']]
        if value['eligible'] and row['stamp'] is not None:
            eligible.append(dict(activity_id=r['activity_id'],stamp=row['stamp'],raw=value['average_watts'],rounded=value['rounded_watts']))
    def winner(at):
        active=[p for p in eligible if p['stamp'].tzinfo and at-timedelta(days=42)<p['stamp']<=at]
        return min(active,key=lambda p:(-p['raw'],p['stamp'],p['activity_id']),default=None)
    def identity(point):return point['activity_id'] if point else None
    selected=data['performance']
    assert data['performance']['pending']==0,'Run full oracle only on current history'
    assert identity(selected['current'])==identity(winner(now))
    latest=max(eligible,key=lambda p:(p['stamp'].replace(tzinfo=None).isoformat(),p['activity_id']),default=None)
    assert identity(selected['latest'])==identity(latest)
    start=datetime.fromisoformat(selected['range_start'])
    events={start,now}
    for point in eligible:
        if not point['stamp'].tzinfo:continue
        for event in (point['stamp'],point['stamp']+timedelta(days=42)):
            if start<=event<=now:events.add(event)
    for at in events:
        step=next((s for s in reversed(selected['rolling']) if datetime.fromisoformat(s['at'])<=at),None)
        assert identity(step['point'] if step else None)==identity(winner(at))
    context=selected['recent']
    if latest and latest['stamp'].tzinfo:
        prior=[p for p in eligible if p['stamp'].tzinfo and latest['stamp']-timedelta(days=42)<p['stamp']<latest['stamp'] and p['activity_id']!=latest['activity_id']]
        best=min(prior,key=lambda p:(-p['raw'],p['stamp'],p['activity_id']),default=None)
        assert identity(context['prior'])==identity(best)
    return dict(status='passed',timezone=zone.key,year=today.year,periods_independently_verified=len(periods),
        ytd={k:v for k,v in data['ytd'].items()},last7_miles=data['last7']['miles'],prior7_miles=data['prior7']['miles'],
        diagnostics=data['diagnostics'],goal_math_verified=bool(data['goal']),no_default_goal=data['target_miles'] is None,
        this_week_actual_miles=data['this_week']['miles'],weekly_required_points_verified=len(data['weekly_goal']),
        needed_miles_per_week=data['goal']['needed_miles_per_week'] if data['goal'] else None,
        all_bars_are_actual=True,current_bar_matches_this_week=True,current_actual_preserved=True,
        recent_average_power_sources_verified=len(data['recent']),
        performance_summary_references_verified=True,performance_event_times_verified=len(events),
        deterministic_latest_context_verified=True,file_api_distance_conflicts=sum(r['file_api_conflict'] for r in cycling))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--tz',default='America/Los_Angeles');parser.add_argument('--as-of')
    args=parser.parse_args()
    try:
        with Store(args.data_dir) as store:
            data=dashboard(store,args.tz,as_of=datetime.fromisoformat(args.as_of) if args.as_of else None)
            result=verify(store,data)
    except Exception as error:
        print('Dashboard verification stopped ('+type(error).__name__+'); inspect local evidence privately.',file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result,indent=2))
