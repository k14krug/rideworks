"""Shared next ride, compact milestone rotation and honest workout context."""
from datetime import date
from html import escape
import json
from urllib.parse import urlencode

from .goals import query_zone
from .planning import CATEGORIES, activity_context, plan
from .web import detail_rows, duration, local_time, shell


def hidden(name,value):
    return f'<input type="hidden" name="{name}" value="{escape(str(value),quote=True)}">'


def day_label(day, today):
    offset=(date.fromisoformat(day)-date.fromisoformat(today)).days
    relative='Today' if offset==0 else 'Tomorrow' if offset==1 else f'In {offset} days'
    return relative+' · '+date.fromisoformat(day).strftime('%a, %b %d, %Y')


def ride_content(rec,*,reason=True):
    explanation=f'<p class="recommended-reason">{escape(rec["reason"])}</p>' if reason else ''
    return f'<h3 class="recommended-type">{escape(rec["category"])}</h3><p class="recommended-target">{escape(rec["duration"])} · {escape(rec["power"])}</p>{explanation}'


def completed_card(data,*,compact=False):
    if not data['today_actual']: return ''
    rows=[]
    for r in data['today_actual']:
        avg='Average power unavailable' if r.get('average_power') is None else f'{r["average_power"]:g} W average'
        rows.append(f'<article><h3>{escape(r["classification"]["category"])} ride logged</h3><p>{duration(r.get("duration"))} · {avg}</p><a href="/activities/{r["activity_id"]}">Review completed ride</a></article>')
    heading='Completed today' if compact else 'Today’s completed activity'
    return f'<section class="panel plan-completed"><h2>{heading} · <time datetime="{data["today"]}">{date.fromisoformat(data["today"]).strftime("%a, %b %d")}</time></h2>{"".join(rows)}</section>'


def today_card(data,nonce=None,*,compact=False,label='Next Recommended Ride',identifier='next-recommended',show_status=True,include_completed=True):
    """The shared primary recommendation is future-dated once today is ridden."""
    rec=data['next_ride'];zone=data['timezone']
    controls=f'<a class="plan-open" href="/plan?{urlencode({"plan_tz":zone})}#rotation-heading">View Plan</a>'
    if not compact and not data['today_actual']:
        base=hidden('nonce',nonce)+hidden('tz',zone)+hidden('day',data['today'])
        controls=f'<form method="post" action="/plan/intent" class="plan-intent">{base}{hidden("category",rec["category"])}<button type="submit">I plan to do this</button></form>'
        if data['intent']:
            intended=json.loads(data['intent']['recommendation_json'])['recommendation']['category']
            controls+=f'<p class="plan-intent-note">Recorded intent: {escape(intended)} · confirmed {local_time(data["intent"]["confirmed_at"],compact=True)}.</p>'
        else: controls+='<p class="plan-intent-note">No recorded intent. This is a suggestion.</p>'
    status='<p class="plan-caveat">Provisional; check sync and actual classifications in Plan.</p>' if show_status and data['provisional'] else ''
    actual=completed_card(data,compact=True) if compact and label=='Next Recommended Ride' and include_completed else ''
    # calendar-day, rather than recommendation-day, drives midnight reload.
    number=f'<span class="plan-number">Hard day #{rec["hard_number"]}</span>' if rec['hard_number'] else ''
    return f'<section class="panel next-recommended" data-recommended-day="{data["today"]}" data-next-day="{rec["day"]}" aria-labelledby="{identifier}-heading"><h2 id="{identifier}-heading">{escape(label)}</h2><p class="next-ride-date"><time datetime="{rec["day"]}">{day_label(rec["day"],data["today"])}</time>{number}</p>{ride_content(rec)}{status}{controls}{actual}</section>'


def correction_form(ride,nonce,zone,*,back='plan'):
    category=ride['classification']['category'];identity=ride['activity_id']
    options='<option value="automatic">Use source inference</option>'+''.join(f'<option value="{escape(c,quote=True)}"{" selected" if category==c and ride["classification"]["confidence"]=="rider confirmed" else ""}>{escape(c)}</option>' for c in CATEGORIES)
    return f'<form method="post" action="/plan/classification" class="plan-correction">{hidden("nonce",nonce)}{hidden("tz",zone)}{hidden("activity_id",identity)}{hidden("back",back)}<label for="category-{identity}">Correct actual category</label><select id="category-{identity}" name="category">{options}</select><button type="submit">Save category</button></form>'


def quick_race(ride,nonce,zone):
    identity=ride['activity_id']
    return f'<form method="post" action="/plan/classification" class="plan-quick-race">{hidden("nonce",nonce)}{hidden("tz",zone)}{hidden("activity_id",identity)}{hidden("back","plan")}{hidden("category","Race")}<button type="submit">Confirm this was a race</button></form>'


def rotation(data):
    """One chronological sequence; adjacent low days share a compact group."""
    blocks=[];low=[]
    def flush():
        if not low:return
        rows=[]
        for rec in low:
            rows.append(f'<li class="plan-day plan-low" data-plan-day="{rec["day"]}"><time datetime="{rec["day"]}">{day_label(rec["day"],data["today"])}</time><div><strong>{escape(rec["category"])}</strong><p>{escape(rec["duration"])} · {escape(rec["power"])}</p></div></li>')
        blocks.append('<li class="plan-low-group"><ol>'+''.join(rows)+'</ol></li>');low.clear()
    for rec in data['days']:
        if rec['offset']==0 and data['today_actual']: continue
        if not rec['hard']:
            low.append(rec);continue
        flush()
        blocks.append(f'<li class="panel plan-day plan-hard" id="hard-{rec["hard_number"]}" data-plan-day="{rec["day"]}" data-hard-number="{rec["hard_number"]}"><div class="plan-date"><time datetime="{rec["day"]}">{day_label(rec["day"],data["today"])}</time><span class="plan-number">Hard day #{rec["hard_number"]}</span></div><div>{ride_content(rec)}</div></li>')
    flush()
    return '<ol class="plan-days">'+''.join(blocks)+'</ol>'


def plan_page(store,query='',nonce=''):
    zone=query_zone(query,'plan_tz')
    if zone is None:
        return shell('Plan','<header><h1>Rolling Plan</h1></header><section class="panel"><p>Invalid timezone. Supply one valid timezone or omit the parameter to use America/Los_Angeles.</p></section>',active='plan',page_class='plan-redesign')
    data=plan(store,zone.key);latest=data['latest_hard']
    last=f'<a href="/activities/{latest["activity_id"]}">{escape(latest["classification"]["category"])}</a> · {latest["day"]}' if latest else 'No classified hard session'
    sync='Synced today' if data['fresh'] else 'Sync stale or unknown'
    uncertain=[]
    for r in data['recent_uncertain']:
        c=r['classification'];race=c.get('title_hint')=='Race'
        action=quick_race(r,nonce,zone.key) if race else f'<a href="/activities/{r["activity_id"]}">Review / correct category</a>'
        uncertain.append(f'<div class="plan-classification-exception"><p><a href="/activities/{r["activity_id"]}">{escape(r["title"])}</a> · {r["day"]}: {"race label needs confirmation" if race else "training type uncertain"}. {"It may add a hard date to the weekly count." if race else "Check its actual stimulus before quality work."}</p>{action}</div>')
    caveat='<p class="plan-status" role="status">Provisional: '+('refresh sync before quality work. ' if not data['fresh'] else '')+('Review the uncertain recent classifications below. ' if data['recent_uncertain'] else '')+('Recent activity dates are unresolved. ' if data['recent_undated'] else '')+'</p>' if (not data['fresh'] or data['recent_undated']) else ''
    normal='Not reported; assess legs during warmup' if data['legs']=='unknown' else 'Unusually heavy today' if data['legs']=='heavy' else 'Normal today'
    base=hidden('nonce',nonce)+hidden('tz',zone.key)+hidden('day',data['today'])
    choices=''.join(f'<option value="{v}"{" selected" if data["legs"]==v else ""}>{s}</option>' for v,s in [('unknown','Not reported'),('normal','Normal'),('heavy','Unusually heavy')])
    feedback=f'<form method="post" action="/plan/feedback" class="plan-feedback">{base}<label for="plan-legs">Legs today</label><select name="legs" id="plan-legs">{choices}</select><button type="submit">Update</button></form>'
    exception=[r for r in data['days'] if r['frequency_exception']]
    preference='Usually two hard sessions in seven dates. Two supported recovery dates can justify an immediate quality option above that target; future projections favor two.'
    if exception:preference+=f' The next quality option would be hard date {exception[0]["hard_dates_in_window"]} in seven; this is an exception, conditional on normal legs.'
    missing=[r['day'] for r in data['recent_days'] if 'assumed rest' in r['state']]
    assumed=f'<p>Past synced dates without rides: {", ".join(missing)} · assumed rest for planning, not completed rides.</p>' if missing else ''
    milestones=''.join(f'<a class="panel plan-milestone" href="#hard-{r["hard_number"]}"><span>Hard day #{r["hard_number"]}</span><h3>{escape(r["category"])}</h3><time datetime="{r["day"]}">{date.fromisoformat(r["day"]).strftime("%a, %b %d")}</time><p>{escape(r["power"])}</p></a>' for r in data['days'] if r['hard'])
    history=''.join(f'<article class="plan-history-row"><p>{r["day"]} · <a href="/activities/{r["activity_id"]}">{escape(r["title"])}</a></p><p><strong>{escape(r["classification"]["category"])}</strong> · {escape(r["classification"]["confidence"])}</p><p>{escape(r["classification"]["reason"])}</p>{correction_form(r,nonce,zone.key)}</article>' for r in reversed(data['history']))
    from .home import safe_json
    next_label='Next Recommended Ride' if data['today_actual'] else 'Today’s recommendation'
    return shell('Plan',f'<header class="plan-header"><div><h1>Rolling Plan</h1><p>Through your next three hard days · {escape(zone.key)}</p></div><p>{sync} · <a href="/settings">Sync now</a></p></header><div class="plan-workspace"><div class="plan-summary">{completed_card(data)}{today_card(data,nonce,label=next_label,show_status=False)}</div><section class="panel plan-context"><h2>Why this plan?</h2><p><strong>Last hard:</strong> {last} · <strong>Hard dates in seven:</strong> {data["recent_hard_dates"]} · <strong>Legs:</strong> {normal}</p><p>{preference}</p>{assumed}{caveat}{"".join(uncertain)}{feedback}<a href="#plan-method">How the plan works</a></section><section aria-labelledby="milestones-heading"><div class="plan-section-heading"><h2 id="milestones-heading">Your next three hard days</h2><p>Projected · refreshed after actual rides</p></div><div class="plan-milestones">{milestones}</div></section><section aria-labelledby="rotation-heading"><div class="plan-section-heading"><h2 id="rotation-heading">Daily rotation</h2><p>Every intervening date · no fixed weekdays</p></div>{rotation(data)}</section><p class="plan-footnote">Future dates assume the suggested hard rides occur and legs recover. Actual rides, skipped dates and feedback can move them. Targets are approximate current coaching context, not historical zones or a readiness diagnosis.</p><details class="panel plan-history"><summary>Recent actual rides · evidence and category corrections</summary>{history or "<p>No recorded rides yet.</p>"}</details><details class="panel plan-help" id="plan-method"><summary>Method, intent and calendar evidence</summary><p>A suggestion is not a completed ride or confirmed intent. “I plan to do this” saves a separate pre-ride date-level intent. Skipping does not create a failed workout or reset recovery. Projected stress never contributes to Training State.</p><p>Two recovery calendar dates follow a hard day. Race follows structured quality; threshold supports the FTP goal, with VO2 considered after recent threshold work. Race metadata is source-reported; a title alone remains a hint. Observed-power classifications are approximate and correctable.</p><p>Last successful sync: {local_time(data["sync_at"],compact=True) if data["sync_at"] else "Never"}. Today is unfinished until a ride is recorded. Only past dates covered by sync can be assumed rest for planning.</p>{detail_rows([(r["day"],r["state"]) for r in data["recent_days"]])}{detail_rows([("Planner",data["version"]),("Classification",data["classifier"]),("As of",data["as_of"]),("Current dated FTP",data["current_ftp"].get("value")),("FTP provenance",data["current_ftp"].get("status"))])}</details><script type="application/json" id="plan-data">{safe_json({k:v for k,v in data.items() if k!="history"})}</script><script src="/static/planning.js" defer></script></div>',active='plan',page_class='plan-redesign')


def activity_panels(store,activity_id,nonce,query=''):
    context=activity_context(store,activity_id);c=context['classification'];intent=context['intent']
    message='No recorded intent. No prior recommendation is assigned retrospectively to this ride.'
    if intent:
        intended=json.loads(intent['recommendation_json'])['recommendation']['category']
        outcome='Actual stimulus is uncertain; confirm the category before comparing.' if c['category'] in ('Uncertain','Hard (type uncertain)') else 'Actual category aligns with the intended stimulus; interval completion is not established.' if c['category']==intended else 'Actual category differs from intent. This is not a failed workout.'
        message=f'Recorded date-level cycling intent: {escape(intended)} · confirmed {local_time(intent["confirmed_at"],compact=True)}. {outcome} A unique activity match is not established.'
    zone=query_zone(query,'plan_tz')
    correction=correction_form(dict(activity_id=activity_id,classification=c),nonce,zone.key if zone else '',back='activity') if context.get('cycling',True) else ''
    next_panel=''
    if context.get('cycling',True):
        if zone:
            # Keep Activity Review's read boundary: newly calculated replaceable
            # caches can be used for this response without persisting mutations.
            store.connection.execute('SAVEPOINT review_plan')
            try:data=plan(store,zone.key)
            finally:
                store.connection.execute('ROLLBACK TO review_plan');store.connection.execute('RELEASE review_plan')
            today_ids={r['activity_id'] for r in data['today_actual']}
            label='Next Recommended Ride' if activity_id in today_ids else 'Current next ride'
            next_panel=today_card(data,compact=True,label=label,identifier='review-next',include_completed=False)
        else:
            next_panel='<section class="panel"><h2>Current next ride</h2><p>Invalid timezone. Supply one valid timezone or omit the parameter to use America/Los_Angeles.</p></section>'
    context_panel = f'<section class="panel activity-plan-context" aria-labelledby="activity-plan-heading"><h2 id="activity-plan-heading">Workout context</h2><p>Actual: <strong>{escape(c["category"])}</strong> · {escape(c["confidence"])}</p><p>{escape(c["reason"])}</p><p>{message}</p>{correction}<a href="/plan">View Plan</a></section><script src="/static/planning.js" defer></script>'
    return context_panel, next_panel
