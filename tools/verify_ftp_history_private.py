#!/usr/bin/env python3
"""FTP-01 fixed-clock private-copy verification; snapshots never belong in Git.

Run snapshot with the old code root on a private copy, then compare with new
code after explicit bootstrap of another copy. This tool never opens a live
store: --data-dir must differ from --protected-store (required).
"""
import argparse
from contextlib import ExitStack
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from time import perf_counter
from unittest.mock import patch


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def normalized(value):
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, dict):
        # Only storage provenance changes. Do not remove numerical/evidence data.
        omitted = {'ftp_source_sha256', 'ftp_history_signature', 'ftp_history_revision'}
        if 'calendar_timezone' in value and 'interval' in value:
            omitted.add('source')
        return {k: normalized(v) for k, v in value.items() if k not in omitted}
    return value


def inventory(root):
    with sqlite3.connect((root / 'rideworks.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        tables = {}
        for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            if table in ('training_stress_cache', 'planning_classification_cache', 'ftp_history', 'ftp_history_state'):
                continue
            quoted = '"' + table.replace('"', '""') + '"'
            tables[table] = digest(sorted(db.execute('SELECT * FROM ' + quoted).fetchall(), key=repr))
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    artifacts = {}
    for path in sorted((root / 'originals').rglob('*')):
        if path.is_file():
            artifacts[str(path.relative_to(root))] = (path.stat().st_size, sha256(path.read_bytes()).hexdigest())
    return dict(tables=tables, artifacts=artifacts)


def capture(root):
    from rideworks.store import Store
    from rideworks.training_state import training_state
    from rideworks.planning import plan, activity_context
    from rideworks.performance import performance_history
    from rideworks.power_curve import comparison
    from rideworks.home import home_page
    from rideworks.dashboard import dashboard
    from rideworks.training_state_page import training_page
    from rideworks.planning_page import plan_page, activity_panels
    from zoneinfo import ZoneInfo
    state = {'models': {}, 'page_checks': 0, 'seconds': {}}
    with Store(root) as store:
        for zone, stamp in [('America/Los_Angeles', '2026-10-15T12:00:00-07:00'),
                            ('Asia/Tokyo', '2026-01-01T00:30:00+00:00')]:
            asof = datetime.fromisoformat(stamp); key = zone + ' ' + stamp
            t = perf_counter(); training = training_state(store, zone, as_of=asof)
            state['seconds'][key] = perf_counter() - t
            advisor = plan(store, zone, as_of=asof)
            history = performance_history(store)
            home = dashboard(store, zone, as_of=asof)
            contexts = {p['activity_id']: activity_context(store, p['activity_id'], as_of=asof)
                        for p in history['points'][-3:]}
            state['models'][key] = normalized(dict(training=training, planning=advisor, home=home,
                performance=history, curves=comparison(store, as_of=asof, zone=ZoneInfo(zone)), activity_context=contexts))
            with ExitStack() as stack:
                for target, value in [('rideworks.home.dashboard', home),
                                      ('rideworks.training_state_page.training_state', training),
                                      ('rideworks.planning.plan', advisor)]:
                    stack.enter_context(patch(target, return_value=value))
                for render, query in [(home_page, 'home_tz=' + zone), (training_page, 'tz=' + zone), (plan_page, 'tz=' + zone)]:
                    html = render(store, query)
                    assert '<main>' in html and 'RideWorks' in html
                    state['page_checks'] += 1
        # Same fixed snapshot must give identical warm-cache results.
        asof = datetime.fromisoformat('2026-10-15T12:00:00-07:00')
        t = perf_counter(); warm = training_state(store, 'America/Los_Angeles', as_of=asof)
        state['seconds']['warm'] = perf_counter() - t
        assert normalized(warm) == state['models']['America/Los_Angeles 2026-10-15T12:00:00-07:00']['training']
    return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir', type=Path, required=True)
    p.add_argument('--protected-store', type=Path, required=True)
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--compare', action='store_true')
    p.add_argument('--report', type=Path)
    args = p.parse_args(); root = args.data_dir.resolve()
    assert root != args.protected_store.resolve(), 'Refusing protected store'
    assert (root / 'rideworks.sqlite3').is_file(), 'Supply an existing private copy'
    sys.path.insert(0, str(args.code_root.resolve()))
    before = inventory(root); state = capture(root); after = inventory(root)
    assert before == after, 'Non-cache state or original artifact changed'
    state['inventory'] = after
    if args.compare:
        prior = json.loads(args.snapshot.read_text())
        # JSON roundtrip normalizes tuple/list representations in inventories.
        state = json.loads(json.dumps(state))
        if prior['models'] != state['models']:
            args.snapshot.with_suffix('.after.json').write_text(json.dumps(state))
            raise AssertionError('Model parity failed; inspect private snapshot, no private details printed')
        assert prior['inventory'] == state['inventory'], 'Preserved tables/artifacts differ'
        report = dict(model_scenarios=len(state['models']), page_render_checks=state['page_checks'],
                      tables_preserved=len(after['tables']), artifacts_preserved=len(after['artifacts']),
                      numerical_parity=True, warm_cache_parity=True, integrity='ok', seconds=state['seconds'])
        if args.report: args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    else:
        args.snapshot.write_text(json.dumps(state))
        print(json.dumps(dict(snapshot='written privately', scenarios=len(state['models']), seconds=state['seconds'])))


if __name__ == '__main__':
    main()
