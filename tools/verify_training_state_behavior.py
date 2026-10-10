#!/usr/bin/env python3
"""P4-02 real-ride behavioral validation: aggregate publication, private identities.

Before results and required regression cases are supplied locally. Vendor scores
are read only for comparison, never calculation inputs or acceptance targets.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.history import presentation
from rideworks.store import Store
from rideworks.training_state import ride_results, training_state
from tools.compare_training_state_elevate import read_reference


def close(actual,expected):
    assert math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10),(actual,expected)


def direction(value):
    return 'up' if value>1e-9 else 'down' if value < -1e-9 else 'flat'


def verify(store,before,cases,as_of,reference):
    data=training_state(store,'America/Los_Angeles',as_of=as_of)
    rides,_=ride_results(store,'America/Los_Angeles',as_of=as_of)
    old={r['activity_id']:r for r in before['rides']};new={r['activity_id']:r for r in rides}
    assert old.keys()==new.keys(),'Activity cohort changed'
    snapshots={s['activity']['activity_id']:s for s in store.activity_history()}
    kinds={identity:presentation(s)['activity_type'] for identity,s in snapshots.items()}
    changed=[];source_checks=0
    for r in rides:
        prior=old[r['activity_id']]
        assert prior['power']==r['power'],'Power evidence changed'
        if prior['power']['status'] in ('calculated','corrected_estimate'):
            assert prior['selected']==r['selected'],'Qualified power precedence changed'
        if prior['selected']['stress']!=r['selected']['stress']:
            assert r['selected']['method']=='hr' and r['hr']['evidence_kind']=='summary'
            assert r['selected']['stress'] is not None
            changed.append(r)
        hr=r['hr']
        if hr.get('evidence_kind')!='summary' or r['selected']['method']!='hr':continue
        source=next(s for s in snapshots[r['activity_id']]['sources'] if s['source']['source_id']==hr['source']['source_id'])
        fmt=hr['source']['format']
        if fmt=='Strava API summary':
            fields=source['summary']['values'];mean=fields['average_heartrate'];seconds=fields['moving_time']
            assert fields['has_heartrate'] is True and 0<seconds<=fields['elapsed_time']
        elif fmt=='TCX':
            assert len(source['xml_context']['lap_summaries'])==1
            fields=source['xml_context']['lap_summaries'][0];mean=fields['avg_heart_rate'];seconds=fields['total_time_seconds']
        elif fmt=='FIT':
            fields=source['summary'];mean=fields['avg_heart_rate'];seconds=fields['total_timer_time']
            assert fields['total_elapsed_time'] is None or seconds<=fields['total_elapsed_time']
        else:raise AssertionError('Unsupported summary source')
        settings=hr['settings'];reserve=(mean-settings['resting_hr'])/(settings['max_hr']-settings['resting_hr'])
        threshold=(settings['threshold_hr']-settings['resting_hr'])/(settings['max_hr']-settings['resting_hr'])
        expected=100*(seconds/3600)*reserve*math.exp(1.92*reserve)/(threshold*math.exp(1.92*threshold))
        close(hr['stress'],expected);close(hr['mean_hr'],mean);close(hr['active_seconds'],seconds)
        assert hr['coverage'] is None and not hr['completeness_verified'] and not hr['mean_active_scope_verified']
        assert hr['pause_treatment']=='unverified' and 'unverified' in hr['scope']
        assert all(c['stress'] is None for c in hr['stream_rejections'])
        assert r['selected']['stress']==hr['stress'] and hr['method']=='threshold-normalized-average-hr-v1'
        source_checks+=1
    today=date.fromisoformat(data['today']);days={d['day']:d for d in data['days']};old_days={d['day']:d for d in before['data']['days']}
    ref={r['date']:r for r in reference};required=cases['mandatory']
    mandatory=[r for r in rides if r['day']==required['day'] and r['title']==required['title']]
    assert len(mandatory)==1,'Required regression Activity not uniquely matched'
    mandatory=mandatory[0]
    assert old[mandatory['activity_id']]['selected']['stress'] is None
    assert mandatory['selected']['method']=='hr' and mandatory['hr']['evidence_kind']=='summary'
    candidates=[new[identity] for identity in cases['recent_summary_activity_ids']]
    assert len(candidates)==3
    for r in candidates:
        assert kinds[r['activity_id']]=='Ride' and old[r['activity_id']]['selected']['stress'] is None
        assert r['selected']['method']=='hr' and r['hr']['evidence_kind']=='summary'
    targets={mandatory['activity_id']:{'mandatory'},**{r['activity_id']:{'recent_outdoor_summary'} for r in candidates if r!=mandatory}}
    cohorts={}
    for n in (42,90):
        cutoff=today-timedelta(days=n-1)
        pool=[r for r in rides if cutoff<=date.fromisoformat(r['day'])<=today]
        eligible=sorted([r for r in pool if r['selected']['stress'] is not None],key=lambda r:(r['selected']['stress'],r['day'],r['activity_id']))
        assert len(eligible)>=3
        for label,r in [('low_load',eligible[0]),('ordinary_load',eligible[len(eligible)//2]),('high_load',eligible[-1])]:
            targets.setdefault(r['activity_id'],set()).add(f'{n}_day_{label}')
        window=[d for d in data['days'] if cutoff<=date.fromisoformat(d['day'])<=today]
        previous=[d for d in before['data']['days'] if cutoff<=date.fromisoformat(d['day'])<=today]
        def coverage(items,kind=None):
            values=[r for r in items if kind is None or kinds[r['activity_id']]==kind]
            return dict(rides=len(values),scored=sum(r['selected']['stress'] is not None for r in values),
                        unscored=sum(r['selected']['stress'] is None for r in values))
        cohorts[str(n)]=dict(before=coverage([old[r['activity_id']] for r in pool]),after=coverage(pool),
            outdoor_before=coverage([old[r['activity_id']] for r in pool],'Ride'),outdoor_after=coverage(pool,'Ride'),
            before_stress=math.fsum(d['stress'] for d in previous),after_stress=math.fsum(d['stress'] for d in window),
            before_scored_days=sum(d['contributors']>0 for d in previous),after_scored_days=sum(d['contributors']>0 for d in window),
            newly_scored_rides=sum(old[r['activity_id']]['selected']['stress'] is None and r['selected']['stress'] is not None for r in pool),
            changed_selected_stress_rides=sum(r['selected']['stress']!=old[r['activity_id']]['selected']['stress'] for r in pool))
    examples=[]
    for identity,labels in targets.items():
        r=new[identity];d=days[r['day']];index=data['days'].index(d)
        prev=data['days'][index-1] if index else dict(fitness=0,fatigue=0)
        close(d['stress'],math.fsum(p['selected']['stress'] for p in d['rides'] if p['selected']['stress'] is not None))
        close(d['fitness'],prev['fitness']*math.exp(-1/42)+d['stress']*(1-math.exp(-1/42)))
        close(d['fatigue'],prev['fatigue']*math.exp(-1/7)+d['stress']*(1-math.exp(-1/7)))
        close(d['form'],prev['fitness']-prev['fatigue'])
        next_day=data['days'][index+1] if index+1<len(data['days']) else None
        if next_day:close(next_day['form'],d['fitness']-d['fatigue'])
        stress=r['selected']['stress'];df=stress*(1-math.exp(-1/42));da=stress*(1-math.exp(-1/7))
        close(d['fitness']-(prev['fitness']*math.exp(-1/42)+(d['stress']-stress)*(1-math.exp(-1/42))),df)
        close(d['fatigue']-(prev['fatigue']*math.exp(-1/7)+(d['stress']-stress)*(1-math.exp(-1/7))),da)
        vendor=ref.get(r['day']);vprev=ref.get((date.fromisoformat(r['day'])-timedelta(days=1)).isoformat())
        external=None
        if vendor and vprev:
            external=dict(stress=float(vendor['finalStressScore']),fitness=float(vendor['ctl']),fatigue=float(vendor['atl']),form=float(vendor['tsb']),
                fitness_change=float(vendor['ctl'])-float(vprev['ctl']),fatigue_change=float(vendor['atl'])-float(vprev['atl']))
        examples.append(dict(labels=sorted(labels),ride=r,before_ride=old[identity],day={k:d[k] for k in ('day','stress','fitness','fatigue','form','contributors','unscored')},
            before_day={k:old_days[r['day']][k] for k in ('stress','fitness','fatigue','form')},
            fitness_change=d['fitness']-prev['fitness'],fatigue_change=d['fatigue']-prev['fatigue'],
            next_day_form=next_day['form'] if next_day else None,
            isolated_ride_effect=dict(fitness=df,fatigue=da,next_day_form=df-da),reference_only=external))
    # Real-day direction/shape evidence, without requiring numerical vendor parity.
    external_directions=Counter()
    for x in examples:
        if x['reference_only']:
            for key in ('fitness','fatigue'):
                external_directions[key+'_same_direction']+=direction(x[key+'_change'])==direction(x['reference_only'][key+'_change'])
                external_directions[key+'_comparisons']+=1
    scored_summary=[r for r in rides if r['selected']['method']=='hr' and r['hr'].get('evidence_kind')=='summary']
    report=dict(version=data['version'],source_policy=data['hr_source_policy'],as_of=as_of.isoformat(),
        before_coverage=before['data']['coverage'],after_coverage=data['coverage'],
        changed_numeric_rides=len(changed),newly_scored_rides=sum(old[r['activity_id']]['selected']['stress'] is None for r in changed),
        partial_power_replaced_by_summary=sum(old[r['activity_id']]['selected']['status']=='partial' for r in changed),
        changed_summary_source_counts=dict(Counter(r['hr']['source']['format'] for r in changed)),
        selected_summary_sources=dict(Counter(r['hr']['source']['format'] for r in scored_summary)),
        independent_raw_summary_formula_checks=source_checks,power_candidates_unchanged=len(rides),
        representative_sessions=len(examples),representative_labels=sorted({label for x in examples for label in x['labels']}),
        mandatory_regression_passed=True,all_three_recent_outdoor_summaries_scored=True,
        recent_windows=cohorts,external_direction_checks=dict(external_directions),
        current_model_change={k:data['days'][-1][k]-before['data']['days'][-1][k] for k in ('fitness','fatigue','form')},
        limitations=['Reported summary mean may cover only the recorded portion; active coverage and pause semantics unverified.',
                    'Partial HR is not selected. Unscored historical outdoor rides remain unavailable.',
                    'Representative load labels are relative to the retained window, not physiological classifications.',
                    'Vendor results are a behavioral comparison, never a score target or production input.'])
    return report,dict(examples=examples,changed_rides=changed,after=data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('data-dir','before','cases','reference','aggregate-output','private-output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--as-of',required=True);a=p.parse_args()
    reference,_=read_reference(a.reference)
    with Store(a.data_dir) as store:
        report,private=verify(store,json.loads(a.before.read_text()),json.loads(a.cases.read_text()),datetime.fromisoformat(a.as_of),reference)
    for path,value in [(a.aggregate_output,report),(a.private_output,private)]:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
