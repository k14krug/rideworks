"""Source-neutral tests of the stop-report diagnostic, not curve acceptance."""
from datetime import datetime, timedelta, timezone
import unittest

from tools.check_pc01_timer_contract import independent_window
from rideworks.analysis import best_20_minute_power


def records(powers):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [dict(record_index=i, timestamp=(start+timedelta(seconds=i)).isoformat(), power=p)
            for i, p in enumerate(powers)]


class TimerContractTests(unittest.TestCase):
    def test_terminal_stop_sample_changes_half_open_result(self):
        rows = records([100]*1200 + [500])
        first = datetime.fromisoformat(rows[0]['timestamp']).timestamp()
        accepted = best_20_minute_power(rows, activity_id='synthetic', source_id='synthetic', extraction_id='synthetic')
        plain = independent_window(rows)
        scoped = independent_window(rows, [(first, first+1200)])
        inclusive = independent_window(rows, [(first, first+1200)], include_stop=True)
        self.assertEqual(plain['sum_watts']/1200, accepted['average_watts'])
        self.assertEqual(plain, inclusive)
        self.assertEqual(scoped['sum_watts'], 120000)
        self.assertNotEqual(scoped['sum_watts'], plain['sum_watts'])

    def test_samples_strictly_after_stop_change_both_interpretations(self):
        rows = records([100]*1200 + [1000]*120)
        first = datetime.fromisoformat(rows[0]['timestamp']).timestamp()
        plain = independent_window(rows)
        for inclusive in (False, True):
            scoped = independent_window(rows, [(first, first+1200)], include_stop=inclusive)
            self.assertLess(scoped['sum_watts'], plain['sum_watts'])

    def test_pause_boundary_never_stitches_active_intervals(self):
        rows = records([100]*1300)
        first = datetime.fromisoformat(rows[0]['timestamp']).timestamp()
        for inclusive in (False, True):
            scoped = independent_window(rows, [(first, first+650), (first+650, first+1300)], include_stop=inclusive)
            self.assertIsNone(scoped['sum_watts'])

    def test_zero_null_gaps_ties_and_invalid_power(self):
        rows = records([0]*8 + [None] + [2]*8)
        self.assertEqual(independent_window(rows, duration=5)['start_position'], 9)
        self.assertEqual(independent_window(records([0]*6), duration=5)['sum_watts'], 0)
        rows[12]['timestamp'] = rows[11]['timestamp']
        self.assertEqual(independent_window(rows, duration=5)['sum_watts'], 0)
        rows[0]['power'] = -1
        with self.assertRaises(ValueError):
            independent_window(rows)
