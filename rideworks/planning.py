"""Explainable projections, separate from actual evidence and Training State.

No projected stress is fed to Training State. Classification uses observed
trusted power; titles supply hints only. Rider corrections remain separate.
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from hashlib import sha256
import re
from uuid import uuid4
from zoneinfo import ZoneInfo

from .goals import browser_zone
from .dashboard import average_power
from .history import presentation
from .training_state import (epoch, ftp_history, ftp_on, FTP_CALENDAR, ride_results,
                             calculate_ride, hr_context, timer_scope)
from .performance import input_signature

VERSION = 'rolling-advisor-v2'
CLASSIFIER = 'observed-stimulus-v2'
CATEGORIES = ('Race', 'Threshold', 'VO2', 'Z2 endurance', 'Easy', 'Recovery')
HARD = ('Race', 'Threshold', 'VO2', 'Hard (type uncertain)')
# Initial engineering screens describe stimulus, not physiological readiness.
PARAMETERS = dict(vo2_ratio=1.10, vo2_min_bout=20, vo2_max_bout=90,
                  vo2_min_bouts=6, threshold_ratio=.90, threshold_min_seconds=480,
                  low_ratio=.70, low_coverage=.80)


def stimulus(times, powers, ftp):
    """Only consecutive observed one-second bins count; never bridge/drop gaps."""
    if not ftp or len(times) != len(powers):
        return dict(category='Uncertain', hard=False, reason='Dated FTP or trusted power unavailable.')
    counts = Counter(times)
    bouts = []; sustained = 0; longest = 0; current = 0; observed = []
    previous = None
    def close():
        nonlocal current
        if current: bouts.append(current)
        current = 0
    for t, p in zip(times, powers):
        valid = (type(t) in (int,float) and counts[t] == 1 and
                 type(p) in (int,float) and p >= 0)
        if not valid or previous is not None and t != previous+1:
            close(); sustained = 0
        if not valid:
            previous = None; continue
        observed.append(p)
        if p >= ftp*PARAMETERS['vo2_ratio']:
            current += 1
        else: close()
        sustained = sustained+1 if p >= ftp*PARAMETERS['threshold_ratio'] else 0
        longest = max(longest, sustained); previous = t
    close()
    short = [n for n in bouts if PARAMETERS['vo2_min_bout'] <= n <= PARAMETERS['vo2_max_bout']]
    info = dict(short_bouts=len(short),longest_threshold_seconds=longest,observed_seconds=len(observed))
    if len(short) >= PARAMETERS['vo2_min_bouts']:
        return info | dict(category='VO2',hard=True,reason=f'{len(short)} observed 20–90 second efforts at ≥110% of dated FTP. Inferred VO2 stimulus; confirm the workout type.')
    if longest >= PARAMETERS['threshold_min_seconds']:
        return info | dict(category='Threshold',hard=True,reason=f'Observed sustained ≥90% of dated FTP for {longest//60} min. Inferred threshold stimulus; a race can also produce this pattern.')
    valid_times = [t for t in times if type(t) in (int,float)]
    span = max(valid_times)-min(valid_times)+1 if valid_times else 0
    if observed and span >= 600 and len(observed)/span >= PARAMETERS['low_coverage']:
        mean = sum(observed)/len(observed)
        high_fraction = sum(p >= ftp*.90 for p in observed)/len(observed)
        if mean <= ftp*PARAMETERS['low_ratio'] and high_fraction < .05:
            category = 'Recovery' if mean <= 100 else 'Easy' if mean <= 110 else 'Z2 endurance'
            return info | dict(category=category,hard=False,reason='Observed power is predominantly low intensity, with ≥80% recording coverage. Approximate current coaching ranges describe the category.')
    return info | dict(category='Uncertain',hard=False,reason='Observed evidence does not clearly distinguish the training stimulus. Correct the category if known.')


def classify_activity(store, snapshot, row, result, *, cache_result=True,
                      cache_writes=None):
    correction = store.connection.execute('SELECT * FROM planning_classifications WHERE activity_id=?',(row['activity_id'],)).fetchone()
    if correction:
        return dict(category=correction['category'],hard=correction['category'] in HARD,
                    confidence='rider confirmed',reason='Rider classification correction; original sources unchanged.',
                    source=dict(updated_at=correction['updated_at']),version=CLASSIFIER)
    signature=sha256(json.dumps([CLASSIFIER,PARAMETERS,row['title'],input_signature(snapshot,store),result['ftp'],result['power']],sort_keys=True).encode()).hexdigest()
    saved=store.connection.execute('SELECT input_signature,result_json FROM planning_classification_cache WHERE activity_id=?',(row['activity_id'],)).fetchone()
    if saved and saved[0]==signature:
        return json.loads(saved[1])
    power = result['power']; source = power.get('source')
    outcome = dict(category='Uncertain',hard=False,reason='No unambiguous trusted observed-power evidence. HR stress and title alone cannot establish training type.')
    if source and power.get('observed_seconds',0) >= 600 and result['ftp'].get('value'):
        if source['format'] == 'Strava API stream':
            evidence = next(s for s in store.strava_stream_evidence(row['activity_id']) if s['source_id']==source['stream_source_id'])
            times = evidence['streams']['time']['data']; powers = evidence['streams']['watts']['data']
        else:
            native = store.get_source(source['source_id'])
            times = [epoch(r['timestamp']) for r in native['records']]; powers = [r['power'] for r in native['records']]
            intervals, _, verified = timer_scope(native['events'],native['summary'])
            if verified:
                powers=[p if t is not None and any(a<=t and t+1<=b for a,b in intervals) else None for t,p in zip(times,powers)]
        outcome = stimulus(times,powers,result['ftp']['value'])
    title = row['title'].casefold()
    hint = 'Race' if re.search(r'\brace\b|\bracing\b',title) else 'VO2' if re.search(r'v[o0]2|30.?15',title) else 'Threshold' if 'threshold' in title else None
    api=[s for s in snapshot['sources'] if s['source']['kind']=='strava_api' and s['source']['is_current']]
    # Supplied ride classification, not proof of a measured physiological effort.
    # Strava's published ride workout_type enum identifies 11 as race; a title
    # does not fill missing metadata. No API call or source-policy change.
    reported_race=len(api)==1 and api[0]['summary']['values'].get('workout_type')==11
    if reported_race:
        outcome=outcome | dict(category='Race',hard=True,reason='Current Strava ride metadata reports Race (workout_type 11). Source-reported category; correct it if inaccurate.')
    elif hint == 'Race':
        outcome = outcome | dict(category='Hard (type uncertain)' if outcome['hard'] else 'Uncertain',
            reason=outcome['reason']+' Race title is a hint, not race evidence; confirm if this was a race.')
    outcome=outcome | dict(confidence='source reported' if reported_race else 'inferred' if outcome['category']!='Uncertain' else 'uncertain',
                          title_hint=hint,source=source,version=CLASSIFIER,
                          race_metadata_source=api[0]['source']['source_id'] if reported_race else None)
    if cache_result:
        entry=(row['activity_id'],signature,json.dumps(outcome,sort_keys=True))
        if cache_writes is None:
            store.connection.execute('''INSERT INTO planning_classification_cache VALUES (?,?,?) ON CONFLICT(activity_id)
                DO UPDATE SET input_signature=excluded.input_signature,result_json=excluded.result_json''',entry)
        else:
            cache_writes.append(entry)
    return outcome


def completed_history(store, zone_name, *, as_of):
    with store._transaction():
        return _completed_history(store, zone_name, as_of=as_of)


def _completed_history(store, zone_name, *, as_of):
    stress_cache_writes=[];classification_cache_writes=[]
    results, _ = ride_results(store,zone_name,as_of=as_of,
                              cache_writes=stress_cache_writes)
    by_id = {r['activity_id']:r for r in results}
    history = []; undated = dict(total=0,recent=0)
    today=as_of.astimezone(browser_zone(zone_name)).date()
    def uncertain_date(row):
        undated['total']+=1
        stamp=row['start_time']
        # An old source-calendar date with unknown timezone stays excluded,
        # but cannot plausibly move into the current seven-date window.
        if not stamp or (today-datetime.fromisoformat(stamp).date()).days <= 7:
            undated['recent']+=1
    for snapshot in store.activity_history():
        row = presentation(snapshot)
        if row['activity_type'] not in ('Ride','Virtual Ride'): continue
        if row['activity_id'] not in by_id:
            if not row['start_time'] or not row['absolute_time']: uncertain_date(row)
            continue
        result = by_id[row['activity_id']]
        if not row['absolute_time']:
            uncertain_date(row); continue  # No assumed rider-local conversion of unknown source zones.
        history.append(dict(activity_id=row['activity_id'],day=result['day'],start_time=row['start_time'],
            title=row['title'],classification=classify_activity(store,snapshot,row,result,
                cache_writes=classification_cache_writes),
            duration=row['duration'],average_power=average_power(row)[0],
            stress=result['selected'],ftp=result['ftp']))
    # Training stress and classification misses are committed together only
    # after every ride has been calculated on this same read snapshot.
    if stress_cache_writes:
        store.connection.executemany('''INSERT INTO training_stress_cache VALUES (?,?,?) ON CONFLICT(activity_id)
            DO UPDATE SET input_signature=excluded.input_signature,result_json=excluded.result_json''',
            stress_cache_writes)
    if classification_cache_writes:
        store.connection.executemany('''INSERT INTO planning_classification_cache VALUES (?,?,?) ON CONFLICT(activity_id)
            DO UPDATE SET input_signature=excluded.input_signature,result_json=excluded.result_json''',
            classification_cache_writes)
    return sorted(history,key=lambda r:(r['start_time'],r['activity_id'])), undated


def recommendation(category, reason, *, second=False):
    ranges = {'Recovery':('45–60 min','~90–100 W'), 'Easy':('45–60 min','~100–110 W'),
              'Z2 endurance':('60–75 min','~115–120 W'), 'Race':('Duration depends on your event','Variable hard effort'),
              'Threshold':('Choose your familiar threshold session','~175–180 W work intervals'),
              'VO2':('Choose your familiar 30/15 session','~223 W efforts / ~93–100 W easy')}
    duration, power = ranges[category]
    if second: duration, power = '45–75 min','~105–120 W'
    return dict(category=category,duration=duration,power=power,reason=reason,hard=category in HARD)


def project(history, today, *, fresh=True, legs='unknown', unknown_dates=0, limit=90):
    """Use actual history, then simulate suggestions in a separate prospective list."""
    today = date.fromisoformat(today) if isinstance(today,str) else today
    actual = [r for r in history if date.fromisoformat(r['day']) <= today]
    hard_actual = [r for r in actual if r['classification']['hard']]
    hard_dates = {date.fromisoformat(r['day']) for r in hard_actual}
    latest = hard_actual[-1] if hard_actual else None
    last_day = date.fromisoformat(latest['day']) if latest else None
    last_type = latest['classification']['category'] if latest else None
    structured = [r['classification']['category'] for r in hard_actual if r['classification']['category'] in ('Threshold','VO2')]
    recent_uncertain = [r for r in actual if (today-date.fromisoformat(r['day'])).days < 7 and
                        r['classification']['category'] in ('Uncertain','Hard (type uncertain)')]
    blocking_uncertain=[r for r in recent_uncertain if last_day is None or date.fromisoformat(r['day'])>last_day]
    today_actual = [r for r in actual if r['day']==today.isoformat()]
    days = []; upcoming = 0
    next_offset=1 if today_actual else 0
    # The immediate real opportunity can exceed the weekly preference after
    # two supported recovery dates. The simulated tail retains ~two/week.
    actual_by_day={r['day']:[] for r in actual}
    for r in actual:actual_by_day[r['day']].append(r)
    def recovered(day):
        if not fresh or unknown_dates: return False
        for n in (1,2):
            recovered_day=day-timedelta(days=n)
            if recovered_day>today: continue  # prospective low day, conditional
            group=actual_by_day.get(recovered_day.isoformat(),[])
            if any(r['classification']['hard'] or r['classification']['category']=='Uncertain' for r in group):
                return False
        return True
    for offset in range(limit):
        day = today+timedelta(days=offset)
        elapsed = (day-last_day).days if last_day else None
        count = sum(0 <= (day-d).days <= 6 for d in hard_dates)
        if offset in (0,next_offset) and legs == 'heavy':
            rec = recommendation('Recovery','You reported unusually heavy legs today. Keep the next ride light and reassess before quality work.')
        elif elapsed == 1:
            rec = recommendation('Recovery','First calendar date after hard training: an easy recovery spin. A skipped past synced day still counts as elapsed recovery.')
        elif elapsed == 2:
            rec = recommendation('Easy','Second calendar date after '+str(last_type)+': keep it easy, if legs feel normal during warmup.',second=last_type!='VO2')
        elif offset == 0 and today_actual:
            rec = recommendation('Recovery' if elapsed == 0 else 'Easy','A ride is already recorded today. If you want another spin, keep it light. Completed training is context, not an upcoming hard recommendation.')
        elif offset == 0 and (not fresh or blocking_uncertain or unknown_dates):
            rec = recommendation('Easy','Provisional: sync and review uncertain recent classifications before quality work. Missing or undated history does not establish recovery.')
        elif count >= 2 and not (count==2 and offset==next_offset and elapsed is not None and elapsed>=3 and recovered(day) and legs!='heavy'):
            rec = recommendation('Z2 endurance','Aerobic riding keeps the projected rotation near the usual two hard sessions per seven dates. An immediate quality opportunity after supported recovery can exceed this preference.')
        elif elapsed is None or elapsed >= 3:
            category = 'Race' if last_type in ('Threshold','VO2') else 'VO2' if structured and structured[-1]=='Threshold' else 'Threshold'
            why = ('Race follows structured quality.' if category=='Race' else
                   'Structured quality follows the race or starts the rotation; '+('VO2 adds a different stimulus after recent threshold work.' if category=='VO2' else 'Threshold supports the current FTP-improvement goal.'))
            rec = recommendation(category,why+' Two recovery dates have passed where applicable. Only do this if legs feel normal during warmup.')
            if count>=2:
                rec['reason']+=f' This would be hard date {count+1} in seven: above the usual two. Two supported recovery dates make it an available quality option; keep the later rotation lighter.'
        else:
            rec = recommendation('Easy','Keep any additional riding light on the completed hard-session date.')
        number = None
        if rec['hard']:
            upcoming += 1; number = upcoming
            hard_dates.add(day); last_day = day; last_type = rec['category']
            if last_type in ('Threshold','VO2'): structured.append(last_type)
        days.append(rec | dict(day=day.isoformat(),offset=offset,hard_number=number,
                              frequency_exception=rec['hard'] and count>=2,
                              hard_dates_in_window=count+(1 if rec['hard'] else 0),
                              status='recommendation' if offset==0 else 'conditional projection'))
        if upcoming == 3: break
    if upcoming != 3:
        raise ValueError('Cannot project three upcoming hard recommendations within the defensive limit.')
    return dict(days=days,next_ride=days[next_offset],latest_hard=latest,today_actual=today_actual,recent_uncertain=recent_uncertain,
                recent_hard_dates=sum(0 <= (today-d).days <= 6 for d in {date.fromisoformat(r['day']) for r in hard_actual}),
                provisional=not fresh or bool(recent_uncertain) or bool(unknown_dates))


def plan(store, zone_name, *, as_of=None):
    zone = browser_zone(zone_name); as_of = as_of or datetime.now(timezone.utc)
    if as_of.tzinfo is None: raise ValueError('Planner as-of must be absolute.')
    today = as_of.astimezone(zone).date()
    with store._transaction():
        history, undated = completed_history(store,zone_name,as_of=as_of)
        row = store.connection.execute('SELECT successful_at FROM strava_sync_state WHERE singleton=1').fetchone()
        synced = datetime.fromtimestamp(row[0],timezone.utc) if row else None
        fresh = bool(synced and synced <= as_of and synced.astimezone(zone).date()==today)
        feedback = store.connection.execute('SELECT legs FROM planning_feedback WHERE day=? AND timezone=?',(today.isoformat(),zone_name)).fetchone()
        legs = feedback[0] if feedback else 'unknown'
        result = project(history,today,fresh=fresh,legs=legs,unknown_dates=undated['recent'])
        recorded = {r['day'] for r in history}
        recent_days = []
        for n in range(6,0,-1):
            day = today-timedelta(days=n)
            known_absence = bool(synced and synced<=as_of and day<synced.astimezone(zone).date())
            state = 'recorded activity' if day.isoformat() in recorded else 'assumed rest for planning (no recorded ride)' if known_absence else 'no recorded ride; sync does not establish rest'
            recent_days.append(dict(day=day.isoformat(),state=state))
        ftp, digest = ftp_history(store)
        current_ftp = ftp_on(ftp,as_of.astimezone(ZoneInfo(FTP_CALENDAR)).date().isoformat())
        intent = store.connection.execute('SELECT * FROM planning_intents WHERE day=? AND timezone=? ORDER BY confirmed_at DESC,intent_id DESC LIMIT 1',(today.isoformat(),zone_name)).fetchone()
    return result | dict(today=today.isoformat(),timezone=zone_name,as_of=as_of.isoformat(),sync_at=synced.isoformat() if synced else None,
        fresh=fresh,legs=legs,history=history[-10:],recent_days=recent_days,undated=undated['total'],recent_undated=undated['recent'],
        current_ftp=current_ftp,ftp_source_sha256=digest,version=VERSION,classifier=CLASSIFIER,parameters=PARAMETERS,
        intent=dict(intent) if intent else None)


def set_feedback(store,zone_name,legs,*,as_of=None):
    zone=browser_zone(zone_name); as_of=as_of or datetime.now(timezone.utc)
    if legs not in ('normal','heavy','unknown'): raise ValueError('Invalid leg feedback.')
    with store._transaction(write=True):
        store.connection.execute('''INSERT INTO planning_feedback VALUES (?,?,?,?) ON CONFLICT(day,timezone)
            DO UPDATE SET legs=excluded.legs,updated_at=excluded.updated_at''',
            (as_of.astimezone(zone).date().isoformat(),zone_name,legs,as_of.isoformat()))


def set_classification(store,activity_id,category,*,as_of=None):
    if category not in CATEGORIES+('automatic',): raise ValueError('Invalid ride category.')
    snapshots=store.activity_history(activity_id)
    if not snapshots: raise ValueError('Activity not found.')
    if presentation(snapshots[0])['activity_type'] not in ('Ride','Virtual Ride'):
        raise ValueError('Planning classifications apply to cycling rides.')
    with store._transaction(write=True):
        if category=='automatic':
            store.connection.execute('DELETE FROM planning_classifications WHERE activity_id=?',(activity_id,))
        else:
            store.connection.execute('''INSERT INTO planning_classifications VALUES (?,?,?) ON CONFLICT(activity_id)
                DO UPDATE SET category=excluded.category,updated_at=excluded.updated_at''',
                (activity_id,category,(as_of or datetime.now(timezone.utc)).isoformat()))


def confirm_intent(store,zone_name,*,as_of=None,expected_day=None,expected_category=None):
    as_of=as_of or datetime.now(timezone.utc)
    with store._transaction(write=True):
        data=plan(store,zone_name,as_of=as_of)
        if data['today_actual']: raise ValueError('A ride is already recorded today; intent must be confirmed before the ride.')
        rec=data['days'][0]
        if expected_day!=data['today'] or expected_category!=rec['category']:
            raise ValueError('The recommendation changed. Reload Plan before confirming intent.')
        snapshot={k:data[k] for k in ('version','classifier','parameters','as_of','fresh','legs','current_ftp','ftp_source_sha256')}
        snapshot['recommendation']=rec
        snapshot['basis']=dict(latest_actual_hard=data['latest_hard'],recent_hard_dates=data['recent_hard_dates'],
                               sync_at=data['sync_at'],provisional=data['provisional'])
        store.connection.execute('INSERT INTO planning_intents VALUES (?,?,?,?,?)',
            (str(uuid4()),data['today'],zone_name,as_of.isoformat(),json.dumps(snapshot,sort_keys=True)))


def activity_context(store, activity_id, *, as_of=None):
    with store._transaction():
        return _activity_context(store, activity_id, as_of=as_of)


def _activity_context(store, activity_id, *, as_of=None):
    """Only a real pre-ride confirmation can establish intended-versus-actual."""
    as_of=as_of or datetime.now(timezone.utc)
    snapshot=store.activity_history(activity_id)[0];row=presentation(snapshot)
    result = dict(intent=None,classification=dict(category='Uncertain',reason='Activity date or timezone unavailable.',confidence='uncertain'))
    if row['activity_type'] not in ('Ride','Virtual Ride'):
        return result | dict(cycling=False,classification=dict(category='Not a cycling ride',confidence='source type',reason='Ride recommendations apply to cycling activities.'))
    if not row['absolute_time']: return result
    start=datetime.fromisoformat(row['start_time'])
    # Shared source calculation; no retrospective suggestions are persisted.
    if start>as_of: return result
    athlete_day=start.astimezone(ZoneInfo(FTP_CALENDAR)).date().isoformat()
    history,_=ftp_history(store)
    ride=calculate_ride(store,snapshot,row,ftp_on(history,athlete_day),hr_context(athlete_day))
    result['classification']=classify_activity(store,snapshot,row,ride,cache_result=False)
    intents=store.connection.execute('SELECT * FROM planning_intents WHERE confirmed_at<? ORDER BY confirmed_at DESC,intent_id DESC',(start.isoformat(),)).fetchall()
    for intent in intents:
        if datetime.fromisoformat(intent['confirmed_at'])>=start: continue
        if start.astimezone(browser_zone(intent['timezone'])).date().isoformat()==intent['day']:
            result['intent']=dict(intent);break
    return result
