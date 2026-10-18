"""Home dashboard compact recent-ride selection regression."""
from datetime import datetime, timezone
from unittest import TestCase

from rideworks.dashboard import mileage
from rideworks.home import recent_ride_link


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

    def test_recent_effort_indicator_keeps_title_and_is_usable_from_link(self):
        row = dict(activity_id='ride-42', title='Race & Recovery <Zwift>')
        rated = recent_ride_link(row, {'status':'available', 'category':'Very High',
                                      'slug':'very-high'})
        self.assertIn('class="home-effort-dot effort-very-high"', rated)
        self.assertIn('title="Relative effort: Very High"', rated)
        self.assertIn('aria-label="Race &amp; Recovery &lt;Zwift&gt; · Relative effort: Very High"', rated)
        self.assertIn('href="/activities/ride-42"', rated)
        self.assertIn('Race &amp; Recovery &lt;Zwift&gt;</a>', rated)
        self.assertIn('aria-hidden="true"', rated)
        self.assertNotIn('151 W', rated)

    def test_unrated_indicator_is_neutral_and_accessible(self):
        row = dict(activity_id='ride-43', title='Easy Ride')
        for rating in (None, {'status':'unavailable', 'reason':'insufficient_history'}):
            with self.subTest(rating=rating):
                html = recent_ride_link(row, rating)
                self.assertIn('class="home-effort-dot effort-unavailable"', html)
                self.assertIn('title="Relative effort: Not rated"', html)
                self.assertIn('Easy Ride · Relative effort: Not rated', html)
                self.assertEqual(html.count('home-effort-dot'), 1)
