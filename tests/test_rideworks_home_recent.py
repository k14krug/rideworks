"""Home dashboard compact recent-ride selection regression."""
from datetime import datetime, timezone
from unittest import TestCase

from rideworks.dashboard import mileage


class HomeRecentTests(TestCase):
    def test_last_seven_rides_not_last_seven_calendar_days(self):
        rows = [
            dict(activity_id=f'ride-{i:02}', activity_type='Virtual Ride',
                 start_time=f'2026-10-{i:02}T12:00:00+00:00',
                 absolute_time=True, date_key=f'2026-10-{i:02}T12:00:00+00:00',
                 distance=1609.344, distance_source={'context': 'FIT session'})
            for i in range(1, 9)
        ]
        rows.append(dict(rows[0], activity_id='run', activity_type='Run'))
        snapshot = mileage(rows, 'UTC', as_of=datetime(2026, 10, 17, tzinfo=timezone.utc))
        self.assertEqual([row['activity_id'] for row in snapshot['recent']],
                         [f'ride-{i:02}' for i in range(8, 1, -1)])
        self.assertEqual(snapshot['diagnostics']['cycling_activities'], 8)
