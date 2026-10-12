#!/usr/bin/env python3
"""Fixed-clock Home/model parity; private snapshots stay in ignored storage."""
import argparse
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class Content(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.selected={}

    def handle_starttag(self, tag, attrs):
        self.stack.append((tag, dict(attrs), []))

    def handle_data(self, text):
        for _, _, parts in self.stack: parts.append(text)

    def handle_endtag(self, tag):
        i=next((i for i in range(len(self.stack)-1,-1,-1) if self.stack[i][0]==tag),None)
        if i is None: return
        _, attrs, parts=self.stack[i]
        key=attrs.get('id')
        # Exact values/source links remain separately verified by payload parity.
        if key in ('home-this-week','home-last7','home-current','home-latest'):
            text=' '.join(''.join(parts).split())
            # The duplicate latest comparison moved to supporting details.
            text=text.split('Latest eligible best-20')[0].strip()
            self.selected[key]=text
        if attrs.get('class') in ('panel next-recommended','panel home-training'):
            self.selected[attrs['class']]=' '.join(''.join(parts).split())
        if tag in ('dt','dd'):
            self.selected.setdefault('evidence',[]).append(' '.join(''.join(parts).split()))
        if tag=='p':
            text=' '.join(''.join(parts).split())
            if text.startswith(('Latest eligible best-20','The best-20 comparison uses')):
                # The prior page rendered the same comparison twice; preserve
                # its exact content once in the new supporting disclosure.
                self.selected.setdefault('comparison_text',[])
                if text not in self.selected['comparison_text']:
                    self.selected['comparison_text'].append(text)
        del self.stack[i:]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--compare',action='store_true')
    p.add_argument('--output',type=Path)
    a=p.parse_args();sys.path.insert(0,str(a.code_root.resolve()))
    from rideworks.store import Store
    from rideworks.home import home_page
    from rideworks.dashboard import dashboard
    from rideworks.planning import plan
    from rideworks.training_state import training_state
    from rideworks.performance import performance_history

    state={'pages':{},'models':{},'tables':{},'artifacts':[]}
    with Store(a.data_dir) as store:
        for zone in ('America/Los_Angeles','Asia/Tokyo'):
            for stamp in ('2026-10-11T08:00:00-07:00','2026-10-11T18:00:00-07:00','2026-01-01T00:30:00+00:00'):
                asof=datetime.fromisoformat(stamp);key=zone+' '+stamp
                data=dashboard(store,zone,as_of=asof)
                training=training_state(store,zone,as_of=asof)
                advisor=plan(store,zone,as_of=asof)
                state['models'][key]=dict(dashboard=digest(data),training=digest(training),plan=digest(advisor),performance=digest(performance_history(store)))
                with patch('rideworks.home.dashboard',return_value=data),patch('rideworks.training_state_page.training_state',return_value=training),patch('rideworks.planning.plan',return_value=advisor):
                    html=home_page(store,'home_tz='+zone)
                parsed=Content();parsed.feed(html)
                state['pages'][key]=dict(payload=json.loads(re.search(r'id="dashboard-data" type="application/json">(.*?)</script>',html,re.S)[1]),
                    charts={re.search(r'id="([^"]+)"',chart)[1]:chart for chart in re.findall(r'<svg class="home-chart".*?</svg>',html,re.S)},content=parsed.selected)
        tables=[r[0] for r in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            state['tables'][table]=digest(sorted([tuple(r) for r in store.connection.execute('SELECT * FROM "'+table+'"')],key=repr))
        for name,expected,size in store.connection.execute('SELECT stored_path,sha256,byte_size FROM sources UNION ALL SELECT stored_path,sha256,byte_size FROM export_snapshots'):
            path=a.data_dir/name
            assert sha256(path.read_bytes()).hexdigest()==expected and path.stat().st_size==size
            state['artifacts'].append((expected,size,path.stat().st_mtime_ns))
        assert store.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not store.connection.execute('PRAGMA foreign_key_check').fetchall()
    state['references']={name:sha256((a.code_root/name).read_bytes()).hexdigest() for name in (
        'data/athlete/strava_ftp_history.csv','rideworks/data/strava_ftp_history.csv',
        'data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv')}
    state=json.loads(json.dumps(state,default=str))
    if a.compare:
        before=json.loads(a.snapshot.read_text())
        if state!=before:
            # A failed comparison is evidence too; never publish this snapshot.
            a.snapshot.with_suffix('.after.json').write_text(json.dumps(state,sort_keys=True))
        for key in state: assert state[key]==before[key], 'Home before/after mismatch: '+key
    else: a.snapshot.write_text(json.dumps(state,sort_keys=True))
    report=dict(fixed_clock_cases=len(state['pages']),timezones=2,all_dashboard_payloads_equal=a.compare,
        chart_svg_values_geometry_links_equal=a.compare,recommendation_training_kpis_evidence_equal=a.compare,
        accepted_models_equal=a.compare,source_tables=len(tables),original_artifacts=len(state['artifacts']),
        all_tables_equal=a.compare,original_hashes_sizes_mtimes_equal=a.compare,approved_references_equal=a.compare,
        integrity='ok',foreign_key_violations=0)
    if a.output:a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
