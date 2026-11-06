#!/usr/bin/env python3
"""Disposable synthetic Race Results preview with no external API calls."""

import argparse
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'tests'))

from fit_fixture import make_fit
from rideworks import race_results
from rideworks.store import Store
from rideworks.web import create_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--port', type=int, default=18893)
    args = parser.parse_args()
    if (args.data_dir / 'rideworks.sqlite3').exists():
        parser.error('Synthetic preview requires a new empty store.')
    rows = [
        {'date': '2024-11-08', 'start_time': '11:33', 'event': 'Synthetic Race',
         'race_group': '0-210', 'finish': 9, 'avg_watts': 161, 'race_score': 184, 'race_score_change': 0},
        {'date': '2024-11-08', 'start_time': '11:33', 'event': 'Synthetic Wrapped Title',
         'race_group': '160-270', 'finish': 5, 'avg_watts': 175, 'race_score': None, 'race_score_change': None},
        {'date': '2024-11-08', 'start_time': '11:33', 'event': 'Synthetic Downward Score',
         'race_group': '0-210', 'finish': 3, 'avg_watts': 200, 'race_score': 180, 'race_score_change': -5},
    ]
    with tempfile.TemporaryDirectory() as temp:
        fit = Path(temp) / 'synthetic.fit'
        fit.write_bytes(make_fit(avg_power=233))
        with Store(args.data_dir) as store:
            store.import_fit(fit)
    with patch.object(race_results, 'extract', return_value=(rows, {'input_tokens': 100, 'output_tokens': 20})):
        with create_server(args.data_dir, port=args.port) as server:
            print(f'Synthetic-only preview: http://127.0.0.1:{server.server_port}/ (Ctrl+C to stop)', flush=True)
            server.serve_forever()


if __name__ == '__main__':
    main()
