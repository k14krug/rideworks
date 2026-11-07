#!/usr/bin/env python3
"""Disposable synthetic Race Results preview with no external API calls."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import zipfile
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'tests'))

from fit_fixture import make_fit
from test_rideworks_export import csv_bytes, row as export_row
from rideworks import race_results
from rideworks.store import Store
from rideworks.web import create_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18893)
    cases = parser.add_mutually_exclusive_group()
    cases.add_argument('--identity-case', action='store_true')
    cases.add_argument('--seam-case', action='store_true')
    args = parser.parse_args()
    if (args.data_dir / 'rideworks.sqlite3').exists():
        parser.error('Synthetic preview requires a new empty store.')
    rows = [
        {'date': '2024-11-08', 'start_time': '11:33', 'event': 'Stage 1 Hillcrest',
         'race_group': '0-210', 'finish': 9, 'avg_watts': 161, 'race_score': 184, 'race_score_change': 0},
        {'date': '2024-11-08', 'start_time': '11:38', 'event': 'Stage 2 Lakeview',
         'race_group': '160-270', 'finish': 5, 'avg_watts': 175, 'race_score': None, 'race_score_change': None},
    ]
    if args.seam_case:
        rows[0]['event'] = 'Stage 4 Loop de Loop'
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / 'synthetic.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr('activities.csv', csv_bytes([
                export_row('1', filename='activities/one.fit', title=rows[0]['event']),
                export_row('2', filename='activities/two.fit', title=rows[1]['event'])]))
            bundle.writestr('activities/one.fit', make_fit(avg_power=233))
            bundle.writestr('activities/two.fit', make_fit(avg_power=234,
                            session_start_time=1100000300, session_timestamp=1100000302))
        with Store(args.data_dir) as store:
            result = store.import_strava_export(archive)
            if result['failures']:
                raise RuntimeError('Synthetic activities could not be imported.')
    if args.identity_case:
        from test_race_sections import image
        old = dict(rows[1], date='2024-11-07')
        with Store(args.data_dir) as store, \
                patch.object(race_results, 'configuration', return_value=('', 'gpt-6-luna', 10_000_000)):
            old_import = race_results.stage_import(store, image(height=400), 'UTC',
                                                    extractor=lambda *_: ([old], None), mode='full')
            old_activity = next(activity['activity_id'] for activity in race_results.matching_activities(store)
                                if activity['title'] == rows[0]['event'])
            values = json.dumps(old)
            store.connection.execute('INSERT INTO race_results VALUES (?,?,?,?,?)',
                                     (old_activity, old_import, values, 'UTC', 'synthetic'))
            store.connection.execute('INSERT INTO race_result_history VALUES (?,?,?,?,?,?)',
                                     (str(uuid4()), old_activity, old_import, values, 'UTC', 'synthetic'))
    calls = 0

    def fake_extract(*_):
        nonlocal calls
        calls += 1
        if args.seam_case:
            output = ([rows[0], dict(rows[1], date=None)] if calls % 2 else
                      [dict(rows[0], date=None, event='Loop', avg_watts=None, race_score=None)])
        else:
            output = rows if calls % 2 else [dict(rows[1], avg_watts=180)]
        return output, {'input_tokens': 1000, 'output_tokens': 100, 'service_tier': 'default',
                        'input_tokens_details': {'cached_tokens': 200, 'cache_write_tokens': 100},
                        'output_tokens_details': {'reasoning_tokens': 80}}

    with patch.object(race_results, 'extract', side_effect=fake_extract), \
            patch.object(race_results, 'configuration', return_value=('synthetic-key', 'gpt-6-luna', 10_000_000)):
        with create_server(args.data_dir, port=args.port) as server:
            print(f'Synthetic-only preview: http://127.0.0.1:{server.server_port}/ (Ctrl+C to stop)', flush=True)
            server.serve_forever()


if __name__ == '__main__':
    main()
