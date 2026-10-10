#!/usr/bin/env python3
"""Reference-only comparison; private date-level output, safe aggregate report.

The exact approved export is integrity-bound. No result is imported, seeded or
used for production source/athlete-state decisions. Final 14 projections excluded.
"""
import argparse
import csv
from datetime import date,datetime,timedelta
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rideworks.store import Store
from rideworks.training_state import training_state

EXPECTED_SHA='407cc7ac2105d5d0c5c8ce4c90775adcb7733957157c2dad6aaa0af05f1ebfb1'
EXPECTED_SIZE=496966


def read_reference(path):
    payload=path.read_bytes()
    if len(payload)!=EXPECTED_SIZE or hashlib.sha256(payload).hexdigest()!=EXPECTED_SHA:
        raise ValueError('Elevate reference integrity mismatch')
    with path.open(newline='') as f:
        reader=csv.DictReader(f); rows=list(reader)
    if len(rows)!=5925 or any(None in r for r in rows):raise ValueError('Malformed Elevate reference')
    days=[date.fromisoformat(r['date']) for r in rows]
    if any(b!=a+timedelta(days=1) for a,b in zip(days,days[1:])):raise ValueError('Nonconsecutive reference dates')
    completed,projections=rows[:-14],rows[-14:]
    if completed[-1]['date']!='2026-10-09' or projections[0]['date']!='2026-10-10':raise ValueError('Unexpected reference cutoff')
    return completed,projections


def compare(data,reference):
    # Verify only the export's arithmetic from its own rounded selected stress.
    ctl=atl=0.;errors={key:[] for key in ('ctl','atl','tsb')}
    for row in reference:
        tsb=ctl-atl;score=float(row['finalStressScore'] or 0)
        ctl=ctl*math.exp(-1/42)+score*(1-math.exp(-1/42))
        atl=atl*math.exp(-1/7)+score*(1-math.exp(-1/7))
        for key,value in [('ctl',ctl),('atl',atl),('tsb',tsb)]:
            errors[key].append(value-float(row[key] or 0))
    refs={r['date']:r for r in reference};pairs=[]
    for row in data['days']:
        if row['day'] not in refs:continue
        vendor=refs[row['day']]
        pairs.append(dict(day=row['day'],rideworks={k:row[k] for k in ('stress','fitness','fatigue','form','unscored')},
                          elevate=dict(stress=float(vendor['finalStressScore'] or 0),fitness=float(vendor['ctl'] or 0),
                                       fatigue=float(vendor['atl'] or 0),form=float(vendor['tsb'] or 0))))
    def stats(values):
        return dict(n=len(values),mean_signed_difference=math.fsum(values)/len(values),
                    mean_absolute_difference=math.fsum(abs(v) for v in values)/len(values),max_absolute_difference=max(map(abs,values)))
    aggregate=dict(reference_bytes=EXPECTED_SIZE,reference_sha256=EXPECTED_SHA,completed_reference_rows=len(reference),
                   projected_rows_excluded=14,overlap_days=len(pairs),
                   exported_arithmetic_reproduction={k:stats(v) for k,v in errors.items()},
                   rideworks_minus_elevate={k:stats([p['rideworks'][k]-p['elevate'][k] for p in pairs]) for k in ('stress','fitness','fatigue','form')},
                   interpretation='Arithmetic sanity and external disagreement, not source truth, calibration or physiological validation')
    # Latest day, a multi-ride day and a recent unscored day are local-only examples.
    targets=[data['days'][-1]['day'],next(r['day'] for r in reversed(data['days']) if len(r['rides'])>1),
             next(r['day'] for r in reversed(data['days']) if r['unscored'])]
    examples=[p for p in pairs if p['day'] in targets]
    return aggregate,dict(examples=examples,all_overlap_days=pairs)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--as-of',required=True)
    p.add_argument('--private-output',type=Path,required=True);p.add_argument('--aggregate-output',type=Path,required=True)
    a=p.parse_args();ref,projections=read_reference(a.reference)
    with Store(a.data_dir) as store:data=training_state(store,'America/Los_Angeles',as_of=datetime.fromisoformat(a.as_of))
    aggregate,private=compare(data,ref)
    a.private_output.parent.mkdir(parents=True,exist_ok=True);a.private_output.write_text(json.dumps(private,indent=2)+'\n')
    a.aggregate_output.parent.mkdir(parents=True,exist_ok=True);a.aggregate_output.write_text(json.dumps(aggregate,indent=2)+'\n')
    print(json.dumps(aggregate,indent=2))

if __name__=='__main__':main()
