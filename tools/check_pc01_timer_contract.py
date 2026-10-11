#!/usr/bin/env python3
"""Read-only PC-01 preflight: accepted best-20 versus retained FIT timer scope.

This diagnostic evaluates two boundary interpretations, not a new product rule.
Only aggregate counts go to stdout. Optional detailed evidence is local-only.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rideworks.analysis import best_20_minute_power
from rideworks.performance import POLICY
from rideworks.training_state import timer_scope


def independent_window(records, intervals=None, *, include_stop=False, duration=1200):
    """Independent integer prefix-sum oracle; never repair samples or timing.

    Without timer scope, match the existing observed-sample contract. With
    scope, either require [t,t+1) inside an active interval, or allow samples
    at both event endpoints. Both prevent stitching distinct active intervals.
    The endpoint-inclusive case isolates contradictions from stop-bin policy.
    """
    sums, invalid, edges, groups = [0], [0], [0], []
    stamps = [datetime.fromisoformat(r['timestamp']).timestamp()
              if r['timestamp'] is not None else None for r in records]
    for i, (record, stamp) in enumerate(zip(records, stamps)):
        power = record['power']
        if power is not None and (type(power) is not int or power < 0):
            raise ValueError('Invalid native power')
        group = 0 if intervals is None else next(
            (j for j, (start, end) in enumerate(intervals)
             if stamp is not None and start <= stamp
             and (stamp <= end if include_stop else stamp + 1 <= end)), None)
        groups.append(group)
        sums.append(sums[-1] + (power if power is not None else 0))
        invalid.append(invalid[-1] + (stamp is None or power is None or group is None))
        broken = i > 0 and (stamp is None or stamps[i-1] is None
                           or stamp - stamps[i-1] != 1 or group != groups[i-1])
        edges.append(edges[-1] + broken)
    best, position, count = None, None, 0
    for start in range(len(records) - duration + 1):
        end = start + duration
        if invalid[end] != invalid[start] or edges[end] != edges[start+1]:
            continue
        count += 1
        total = sums[end] - sums[start]
        if best is None or total > best:
            best, position = total, start
    return dict(sum_watts=best, start_position=position, eligible_window_count=count)


def check(data_dir, private_output=None):
    path = (Path(data_dir) / 'rideworks.sqlite3').resolve()
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    counts, private = Counter(), []
    try:
        connection.execute('BEGIN')
        for saved in connection.execute(
                'SELECT * FROM performance_history WHERE policy=? AND method=? AND duration_seconds=1200',
                (POLICY, 'best-average-power-v1')):
            result = json.loads(saved['result_json'])
            if not result['eligible'] or not result.get('extraction_id'):
                continue
            counts['eligible_native'] += 1
            key = result['extraction_id']
            current = connection.execute('SELECT source_id FROM extractions WHERE extraction_id=?', (key,)).fetchone()
            if current is None or current[0] != result['source_id']:
                raise ValueError('Cached native extraction is not current')
            records = [dict(r) for r in connection.execute(
                'SELECT * FROM records WHERE extraction_id=? ORDER BY record_index', (key,))]
            oracle = independent_window(records)
            native = best_20_minute_power(records, activity_id=result['activity_id'],
                                         source_id=result['source_id'], extraction_id=key)
            for field in ('average_watts', 'rounded_watts', 'start_record_index',
                          'end_exclusive_record_index', 'eligible_window_count'):
                if native[field] != result[field]:
                    raise ValueError('Accepted cache/native parity failed')
            if (oracle['sum_watts'] / 1200 != result['average_watts']
                    or records[oracle['start_position']]['record_index'] != result['start_record_index']
                    or oracle['eligible_window_count'] != result['eligible_window_count']):
                raise ValueError('Independent oracle/native parity failed')
            counts['accepted_native_oracle_parity'] += 1
            events = [dict(r) for r in connection.execute(
                'SELECT * FROM events WHERE extraction_id=? ORDER BY source_order', (key,))]
            summary = dict(connection.execute('SELECT * FROM sessions WHERE extraction_id=?', (key,)).fetchone())
            intervals, problem, verified = timer_scope(events, summary)
            counts['verified_timer' if verified else problem] += 1
            if intervals is None:
                continue
            counts['paired_timer'] += 1
            counts['multiple_active_intervals'] += len(intervals) > 1
            for boundary in ('half_open', 'endpoint_inclusive'):
                scoped = independent_window(records, intervals, include_stop=boundary == 'endpoint_inclusive')
                if scoped['sum_watts'] == oracle['sum_watts']:
                    if scoped['start_position'] != oracle['start_position']:
                        counts[boundary + '_earliest_tie_changes'] += 1
                    continue
                category = 'verified' if verified else 'summary_unverified'
                counts[boundary + '_' + category + '_value_changes'] += 1
                start = oracle['start_position']
                window = records[start:start+1200]
                window_times = [datetime.fromisoformat(r['timestamp']).timestamp() for r in window]
                after_stop = sum(t > intervals[-1][1] for t in window_times)
                private.append(dict(activity_id=result['activity_id'], extraction_id=key,
                                    source_id=result['source_id'], boundary=boundary,
                                    timer_verified=verified, timer_problem=problem,
                                    accepted=oracle, timer_scoped=scoped,
                                    accepted_window_samples_after_last_stop=after_stop,
                                    summary=summary, timer_events=events))
                if after_stop:
                    counts[boundary + '_accepted_window_samples_after_last_stop'] += after_stop
        integrity = connection.execute('PRAGMA integrity_check').fetchone()[0]
        foreign_keys = len(connection.execute('PRAGMA foreign_key_check').fetchall())
        if integrity != 'ok' or foreign_keys:
            raise ValueError('Source integrity check failed')
        if private_output is not None:
            private_output = Path(private_output)
            private_output.parent.mkdir(parents=True, exist_ok=True)
            private_output.write_text(json.dumps(private, indent=2) + '\n')
        return dict(policy=POLICY, method='best-average-power-v1', read_only=True,
                    counts=dict(sorted(counts.items())), integrity=integrity,
                    foreign_key_violations=foreign_keys)
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--private-output', type=Path, help='Local-only per-source evidence; never commit')
    parser.add_argument('--aggregate-output', type=Path)
    args = parser.parse_args()
    aggregate = check(args.data_dir, args.private_output)
    payload = json.dumps(aggregate, indent=2) + '\n'
    if args.aggregate_output:
        args.aggregate_output.parent.mkdir(parents=True, exist_ok=True)
        args.aggregate_output.write_text(payload)
    print(payload, end='')


if __name__ == '__main__':
    main()
