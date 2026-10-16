#!/usr/bin/env python3
"""Cross-page fixed-clock content/model parity; snapshots are private local files."""
import argparse
from contextlib import ExitStack
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from unittest.mock import patch
from zoneinfo import ZoneInfo


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


class Evidence(HTMLParser):
    """Keep content, destinations, controls and data; allow visual DOM regrouping."""
    def __init__(self):
        super().__init__();self.stack=[];self.records=[];self.payloads={}

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if attrs.get('name')=='nonce':attrs['value']='NONCE'
        if tag in ('input','img','br','meta','link','hr'):
            if tag=='input':self.records.append((tag,attrs,''))
        else:self.stack.append((tag,attrs,[]))

    def handle_data(self,text):
        for _,_,parts in self.stack:parts.append(text)

    def handle_endtag(self,tag):
        i=next((i for i in range(len(self.stack)-1,-1,-1) if self.stack[i][0]==tag),None)
        if i is None:return
        _,attrs,parts=self.stack[i];text=' '.join(''.join(parts).split())
        attrs={k:v for k,v in attrs.items() if k not in ('class','style')}
        if tag=='script' and attrs.get('type')=='application/json':
            self.payloads[attrs.get('id')]=json.loads(''.join(parts))
        elif tag in ('h1','h2','h3','p','a','span','time','strong','dt','dd','summary','label','select','option','button','code','pre','form'):
            self.records.append((tag,attrs,text))
        del self.stack[i:]

    def result(self):
        return dict(content=sorted(self.records,key=lambda v:json.dumps(v,sort_keys=True)),payloads=self.payloads)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--compare',action='store_true')
    p.add_argument('--output',type=Path)
    a=p.parse_args();sys.path.insert(0,str(a.code_root.resolve()))
    from rideworks.store import Store
    from rideworks.dashboard import dashboard
    from rideworks.planning import plan
    from rideworks.training_state import training_state
    from rideworks.performance import performance_history
    from rideworks.performance_view import performance_view
    from rideworks.power_curve import comparison
    from rideworks.settings import Settings
    from rideworks.web import Application
    state=dict(pages={},models={},tables={},artifacts=[])
    app=Application(a.data_dir,settings_factory=lambda root:Settings(root,credentials=lambda:('1','synthetic-configuration')))
    app.settings.nonce='NONCE'
    with Store(a.data_dir) as store:
        for zone in ('America/Los_Angeles','Asia/Tokyo'):
            for stamp in ('2026-10-12T08:00:00-07:00','2026-10-12T18:00:00-07:00','2026-01-01T00:30:00+00:00'):
                asof=datetime.fromisoformat(stamp);key=zone+' '+stamp
                home=dashboard(store,zone,as_of=asof);advisor=plan(store,zone,as_of=asof)
                training=training_state(store,zone,as_of=asof);history=performance_history(store)
                view=performance_view(history['points'],as_of=asof)
                curves=comparison(store,as_of=asof,zone=ZoneInfo(zone))
                state['models'][key]=dict(home=digest(home),plan=digest(advisor),training=digest(training),performance=digest(history),view=digest(view),curves=digest(curves))
                with ExitStack() as patches:
                    for target,value in (
                        ('rideworks.home.dashboard',home),('rideworks.planning.plan',advisor),
                        ('rideworks.planning_page.plan',advisor),('rideworks.training_state_page.training_state',training),
                        ('rideworks.performance_view.performance_view',view),('rideworks.power_curve_page.comparison',curves)):
                        patches.enter_context(patch(target,return_value=value))
                    for name,route in (('activities','/activities?tz='),('performance','/performance?curve_tz='),
                                       ('training','/training-state?tz='),('plan','/plan?plan_tz='),('settings','/settings?tz='),('home','/?home_tz=')):
                        status,_,body=app.get(route+zone);assert status==200
                        parsed=Evidence();parsed.feed(body.decode());state['pages'][key+' '+name]=parsed.result()
        tables=[r[0] for r in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            state['tables'][table]=digest(sorted([tuple(r) for r in store.connection.execute('SELECT * FROM "'+table+'"')],key=repr))
        for name,expected,size in store.connection.execute('SELECT stored_path,sha256,byte_size FROM sources UNION ALL SELECT stored_path,sha256,byte_size FROM export_snapshots'):
            path=a.data_dir/name;assert sha256(path.read_bytes()).hexdigest()==expected and path.stat().st_size==size
            state['artifacts'].append((expected,size,path.stat().st_mtime_ns))
        assert store.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not store.connection.execute('PRAGMA foreign_key_check').fetchall()
    state['references']={name:sha256((a.code_root/name).read_bytes()).hexdigest() for name in (
        'data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv',)}
    state=json.loads(json.dumps(state,default=str))
    if a.compare:
        before=json.loads(a.snapshot.read_text())
        if state!=before:a.snapshot.with_suffix('.after.json').write_text(json.dumps(state,sort_keys=True))
        for key in state:assert state[key]==before[key],'Cross-page preservation mismatch: '+key
    else:a.snapshot.write_text(json.dumps(state,sort_keys=True))
    report=dict(page_states=len(state['pages']),fixed_clock_cases=len(state['models']),timezones=2,
        page_text_links_controls_json_equal=a.compare,accepted_models_equal=a.compare,
        source_tables=len(tables),original_artifacts=len(state['artifacts']),all_tables_equal=a.compare,
        original_hashes_sizes_mtimes_equal=a.compare,approved_references_equal=a.compare,
        integrity='ok',foreign_key_violations=0)
    if a.output:a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
