#!/usr/bin/env python3
"""Exercise a manual FTP insertion only on a deliberately supplied private copy."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_ftp_history_private import inventory
from rideworks.ftp_history import add_entry, bootstrap, snapshot
from rideworks.store import Store
from rideworks.training_state import training_state
from rideworks.planning import plan, activity_context
from rideworks.performance import performance_history


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('data-dir','protected-store','source','mirror','report'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();root=a.data_dir.resolve()
    assert root!=a.protected_store.resolve(), 'Refusing protected store'
    before=inventory(root);asof=datetime.fromisoformat('2026-10-15T12:00:00-07:00');zone='America/Los_Angeles'
    with Store(root) as s:
        original=snapshot(s);base=training_state(s,zone,as_of=asof);power=performance_history(s)
        plan(s,zone,as_of=asof)
        dates={r['effective_from_date'] for r in original['rows']}
        rides={r['activity_id']:r for d in base['days'] for r in d['rides']}
        candidate=next(r for r in reversed(list(rides.values())) if r['ftp']['value'] and
                       not r['timezone_unknown'] and r['ftp']['calendar_date'] not in dates and
                       original['rows'][0]['effective_from_date']<r['ftp']['calendar_date']<original['rows'][-1]['effective_from_date'] and
                       r['selected']['method'] in ('power','session_power'))
        day=candidate['ftp']['calendar_date'];watts=max(1,candidate['ftp']['value']-10)
        changed=add_entry(s,day,watts,expected_revision=original['revision'])
        assert {(r['effective_from_date'],r['ftp_watts']) for r in original['rows']} < {(r['effective_from_date'],r['ftp_watts']) for r in changed['rows']}
        t=perf_counter();after=training_state(s,zone,as_of=asof);cold=perf_counter()-t
        afterrides={r['activity_id']:r for d in after['days'] for r in d['rides']}
        checks=0
        for identity,old in rides.items():
            new=afterrides[identity]
            assert new['hr']==old['hr']
            assert new['power'].get('observed_work_kj')==old['power'].get('observed_work_kj')
            if old['ftp']['value'] and new['ftp']['value'] and old['ftp']['value']!=new['ftp']['value']:
                ratio=(old['ftp']['value']/new['ftp']['value'])**2
                for category in ('power','session_power'):
                    a_score=old.get(category,{}).get('stress');b_score=new.get(category,{}).get('stress')
                    if a_score is not None:
                        assert math.isclose(b_score,a_score*ratio,rel_tol=1e-10);checks+=1
        assert checks>0
        # Independent exponential convolution, including propagation past the interval.
        for i,d in enumerate(after['days']):
            for name,tau in [('fitness',42),('fatigue',7)]:
                expected=(1-math.exp(-1/tau))*math.fsum(x['stress']*math.exp(-(i-j)/tau) for j,x in enumerate(after['days'][:i+1]))
                assert math.isclose(d[name],expected,rel_tol=1e-10,abs_tol=1e-9)
        assert base['days'][-1]['fitness']!=after['days'][-1]['fitness']
        assert performance_history(s)==power
        advisor=plan(s,zone,as_of=asof)
        assert advisor['ftp_source_sha256']==changed['signature']
        context=activity_context(s,candidate['activity_id'],as_of=asof)
        assert context['classification']['category']
        revision=changed['revision']
    replay=bootstrap(root,a.source,a.mirror)
    assert not replay['imported'] and replay['revision']==revision and replay['rows']==changed['rows']
    with Store(root) as s:
        t=perf_counter();warm=training_state(s,zone,as_of=asof);warm_seconds=perf_counter()-t
        assert warm==after
    assert inventory(root)==before
    report=dict(existing_entries_preserved=len(original['rows']),new_entries=len(changed['rows']),inverse_square_checks=checks,
                independent_daily_convolution=True,unchanged_hr_work_power=True,cache_restart_parity=True,
                bootstrap_replay_preserves_insert=True,noncache_tables_and_artifacts_preserved=True,
                cold_seconds=cold,warm_seconds=warm_seconds)
    a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
