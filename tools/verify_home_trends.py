#!/usr/bin/env python3
"""Fixed-clock HOME-UI-02 synthetic preview and before/after preservation checks.

Use only a disposable store made by tools/preview_home.py. No network sync.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--code-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--compare',action='store_true')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--serve-port',type=int)
    parser.add_argument('--browser-session')
    parser.add_argument('--base',default='http://127.0.0.1:8791')
    parser.add_argument('--baseline',default='http://127.0.0.1:8792')
    args=parser.parse_args()
    sys.path.insert(0,str(args.code_root.resolve()))
    from rideworks.dashboard import dashboard
    from rideworks.home import home_page
    from rideworks.planning import plan
    from rideworks.performance import performance_history
    from rideworks.store import Store
    from rideworks.settings import Settings
    from rideworks.training_state import training_state
    from rideworks.web import Application, create_server

    # Load the actual page modules before patching their imported clocks.
    settings=lambda root: Settings(root,credentials=lambda:None)
    app=Application(args.data_dir,settings_factory=settings)
    routes=('/', '/activities', '/training-state', '/performance', '/plan', '/settings')
    for route in routes:
        assert app.get(route)[0]==200, route
    fixed=datetime(2026,10,28,18,tzinfo=timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    with ExitStack() as stack:
        for name,module in list(sys.modules.items()):
            if name.startswith('rideworks.') and getattr(module,'datetime',None) is datetime:
                stack.enter_context(patch.object(module,'datetime',Clock))
        if args.browser_session:
            from rideworks.home import power_chart
            from rideworks.goals import browser_zone
            from rideworks.training_state_page import training_home
            with Store(args.data_dir) as store:
                training=training_state(store,'America/Los_Angeles',as_of=fixed)
                variants=[]
                for name,days in [('flat',[('2026-10-26',8),('2026-10-27',8),('2026-10-28',8)]),
                                  ('single',[('2026-10-28',3)]),('empty',[]),
                                  ('sparse',[('2026-10-20',4),('2026-10-22',None),('2026-10-27',6)]),
                                  ('decreasing',[('2026-10-26',30),('2026-10-27',20),('2026-10-28',10)])]:
                    data=dict(today='2026-10-28',days=[dict(day=d,fitness=v) for d,v in days])
                    with patch('rideworks.training_state_page.training_state',return_value=data):
                        variants.append(dict(name=name,html=training_home(store,'America/Los_Angeles')))
                data=dashboard(store,'America/Los_Angeles',as_of=fixed)['performance']
                card=re.search(r'<section class="panel home-performance\b.*?</section>',app.get('/')[2].decode(),re.S)[0]
                power_variants=[]
                for name,values in [('empty',data|dict(current=None,rolling=[])),('expired',data|dict(current=None))]:
                    # Replace just the chart in a real Home card for layout tests.
                    html=re.sub(r'<svg\b.*?</svg>',power_chart(values,browser_zone('America/Los_Angeles')),card,flags=re.S)
                    power_variants.append(dict(name=name,html=html))
            config=dict(base=args.base,baseline=args.baseline,variants=variants,powerVariants=power_variants,
                        fitness=dict(day=training['days'][-1]['day'],value=training['days'][-1]['fitness']))
            source=(Path(__file__).with_name('verify_home_trends_browser.js')).read_text().replace('CASE_INPUT',json.dumps(config))
            Path('output/playwright').mkdir(parents=True,exist_ok=True)
            result=subprocess.run(['playwright-cli','-s='+args.browser_session,'run-code',source],capture_output=True,text=True)
            if result.returncode or '### Error' in result.stdout:
                Path('output/playwright/home-ui-02-error.log').write_text(result.stdout+result.stderr)
                raise RuntimeError('Browser check failed; see output/playwright/home-ui-02-error.log')
            report=json.loads(result.stdout.split('### Result\n',1)[1].split('### Ran Playwright code',1)[0])
            if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report))
            return
        if args.serve_port:
            with create_server(args.data_dir,args.serve_port,settings_factory=settings) as server:
                print(f'Synthetic fixed-clock preview: http://127.0.0.1:{server.server_port}',flush=True)
                server.serve_forever()
            return
        if args.snapshot is None:
            parser.error('Specify --snapshot or --serve-port')
        state=dict(cases={},tables={},artifacts=[])
        with Store(args.data_dir) as store:
            for zone in ('America/Los_Angeles','Asia/Tokyo'):
                for stamp in ('2026-10-28T18:00:00+00:00','2026-01-01T00:30:00+00:00','2024-08-31T18:00:00+00:00'):
                    fixed=datetime.fromisoformat(stamp)
                    data=dashboard(store,zone,as_of=fixed)
                    training=training_state(store,zone,as_of=fixed)
                    advisor=plan(store,zone,as_of=fixed)
                    with patch('rideworks.home.dashboard',return_value=data),patch('rideworks.training_state_page.training_state',return_value=training),patch('rideworks.planning.plan',return_value=advisor):
                        home=home_page(store,'home_tz='+zone)
                    # Only these two cards intentionally change. Everything else,
                    # including the dashboard JSON and mileage SVG, must match.
                    home=re.sub(r'<section class="panel home-(training|performance)\b.*?</section>','',home,flags=re.S)
                    pages={route:app.get(route+('?home_tz=' if route=='/' else '?plan_tz=' if route=='/plan' else '?tz=')+zone)[2].decode() for route in routes if route!='/'}
                    pages={route:re.sub(r'name="nonce" value="[^"]*"','name="nonce" value="NORMALIZED"',html) for route,html in pages.items()}
                    state['cases'][zone+' '+stamp]=dict(home=digest(home),pages={r:digest(h) for r,h in pages.items()},
                        dashboard=digest(data),training=digest(training),planning=digest(advisor),performance=digest(performance_history(store)))
            for row in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                name=row[0]
                state['tables'][name]=digest(sorted([tuple(r) for r in store.connection.execute('SELECT * FROM "'+name+'"')],key=repr))
            for name,expected,size in store.connection.execute('SELECT stored_path,sha256,byte_size FROM sources UNION ALL SELECT stored_path,sha256,byte_size FROM export_snapshots'):
                path=args.data_dir/name
                assert sha256(path.read_bytes()).hexdigest()==expected and path.stat().st_size==size
                state['artifacts'].append([expected,size,path.stat().st_mtime_ns])
            assert store.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not store.connection.execute('PRAGMA foreign_key_check').fetchall()
        if args.compare:
            before=json.loads(args.snapshot.read_text())
            for key in state:
                assert state[key]==before[key], 'Preservation mismatch: '+key
        else:
            args.snapshot.write_text(json.dumps(state,indent=2)+'\n')
        report=dict(fixed_clock_cases=len(state['cases']),timezones=2,compared=args.compare,
                    unchanged_home_outside_two_cards=args.compare,unchanged_full_pages=args.compare,
                    unchanged_models=args.compare,unchanged_tables=len(state['tables']),
                    unchanged_original_artifacts=len(state['artifacts']),integrity='ok',foreign_key_violations=0)
        if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))


if __name__=='__main__':main()
