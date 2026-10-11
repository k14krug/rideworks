#!/usr/bin/env python3
"""Private fixed-clock before/after review and accepted-model comparison.

Snapshots contain private review evidence and must stay in ignored local storage.
Only aggregate counts/equality flags may be published. --code-root permits a
detached baseline checkout, while using the same disposable retained-source store.
"""
import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from unittest.mock import patch


class Evidence(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.rows = []
        self.payloads = {}
        self.values = []
        self.context = []
        self.key = None

    def handle_starttag(self, tag, attrs):
        self.stack.append([tag, dict(attrs), []])

    def handle_endtag(self, tag):
        position = next((i for i in range(len(self.stack)-1, -1, -1) if self.stack[i][0] == tag), None)
        if position is None:
            return
        _, attrs, parts = self.stack[position]
        value = ' '.join(''.join(parts).split())
        if tag == 'dt':
            self.key = value
        if tag == 'dd':
            self.rows.append((self.key, value))
        if tag == 'script' and attrs.get('type') == 'application/json':
            self.payloads[attrs['id']] = json.loads(''.join(parts))
        if attrs.get('class') in ('best-value', 'window-context', 'recent-difference') or attrs.get('id') in ('recent-current-watts', 'recent-prior-watts'):
            self.values.append(value)
        if tag == 'div' and attrs.get('class') == 'metric':
            self.values.append(value)
        if tag == 'section' and attrs.get('class') in ('panel activity-plan-context', 'panel next-recommended'):
            self.context.append(value)
        del self.stack[position:]

    def handle_data(self, text):
        for element in self.stack:
            element[2].append(text)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-dir', type=Path, required=True)
    p.add_argument('--code-root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--compare', action='store_true')
    p.add_argument('--aggregate-output', type=Path)
    a = p.parse_args()
    sys.path.insert(0, str(a.code_root.resolve()))
    from rideworks.store import Store
    from rideworks.web import Application
    from rideworks.planning import plan
    from rideworks.training_state import training_state
    from rideworks.performance import performance_history
    from rideworks.history import presentation
    from rideworks.dashboard import dashboard

    asof = datetime.fromisoformat('2026-10-11T12:00:00-07:00')
    state = dict(reviews={}, sources={}, artifacts=[])
    zone = 'America/Los_Angeles'
    with Store(a.data_dir) as store:
        tables = [r[0] for r in store.connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for table in tables:
            state['sources'][table] = digest(sorted([tuple(r) for r in store.connection.execute('SELECT * FROM "'+table+'"')], key=repr))
        for table in ('sources', 'export_snapshots'):
            for name, expected, size in store.connection.execute('SELECT stored_path,sha256,byte_size FROM '+table):
                raw = (a.data_dir/name).read_bytes()
                assert sha256(raw).hexdigest() == expected and len(raw) == size
                state['artifacts'].append((expected, size, (a.data_dir/name).stat().st_mtime_ns))
        assert store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not store.connection.execute('PRAGMA foreign_key_check').fetchall()
        state['approved_references'] = {name: sha256((a.code_root/name).read_bytes()).hexdigest() for name in (
            'data/athlete/strava_ftp_history.csv', 'rideworks/data/strava_ftp_history.csv',
            'data/reference/elevate/fitness_trend_export.2026.10.9-15.58.52.csv')}
        state['models'] = { 'performance': digest(performance_history(store)),
                            'training': digest(training_state(store, zone, as_of=asof)),
                            'plan': digest(plan(store, zone, as_of=asof)),
                            'dashboard': digest(dashboard(store, zone, as_of=asof)) }
        # First representative of each combination, plus recent native/API rides.
        buckets = Counter()
        ids = []
        for activity in store.connection.execute('SELECT activity_id FROM activities ORDER BY created_at DESC'):
            row = presentation(store.activity_history(activity[0])[0])
            key = (row['activity_type'], tuple(sorted(s['source']['kind'] for s in row['sources'])))
            if buckets[key] < 2:
                ids.append(activity[0]); buckets[key] += 1
    app = Application(a.data_dir)
    with patch('rideworks.planning_page.plan', side_effect=lambda store, z: plan(store, z, as_of=asof)):
        for identity in ids:
            status, _, body = app.get('/activities/'+identity+'?plan_tz='+zone+'&curve_tz='+zone)
            assert status == 200
            evidence = Evidence(); evidence.feed(body.decode())
            state['reviews'][identity] = dict(rows=sorted(evidence.rows, key=repr), payloads=evidence.payloads,
                                               values=sorted(evidence.values), context=evidence.context)
    state = json.loads(json.dumps(state, default=str))
    if a.compare:
        before = json.loads(a.snapshot.read_text())
        # New thin-view hero metrics have no previous rendered counterpart.
        # Validate them against the explicit current API summary, or all-missing
        # when no supported summary is selected; existing rich values stay exact.
        from rideworks.web import duration, distance, sensor
        with Store(a.data_dir) as store:
            for identity, old in before['reviews'].items():
                if not old['values']:
                    row = presentation(store.activity_history(identity)[0])
                    api_only = all(s['source']['kind'] == 'strava_api' for s in row['sources'])
                    current = next((s for s in row['sources'] if s['source']['is_current']), None) if api_only else None
                    values = current['summary']['values'] if current else {}
                    expected = sorted(['Elapsed duration'+duration(values.get('elapsed_time')),
                        'Distance'+distance(values.get('distance')),
                        'Average power'+sensor(values.get('average_watts'), 'W'),
                        'Average heart rate'+sensor(values.get('average_heartrate'), 'bpm')])
                    assert state['reviews'][identity]['values'] == expected, 'Thin hero source mismatch'
                    old['values'] = expected
        for key in state:
            assert state[key] == before[key], 'Before/after mismatch: '+key
    else:
        a.snapshot.write_text(json.dumps(state, sort_keys=True))
    report = dict(review_modes_checked=len(ids), source_tables=len(tables), original_artifacts=len(state['artifacts']),
                  fixed_clock=asof.isoformat(), compared=a.compare, accepted_models_equal=a.compare,
                  raw_payloads_summaries_calculations_provenance_equal=a.compare, originals_preserved=True,
                  original_modification_times_equal=a.compare, approved_reference_hashes_equal=a.compare,
                  integrity='ok', foreign_key_violations=0)
    if a.aggregate_output:
        a.aggregate_output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
