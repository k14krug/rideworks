from unittest import TestCase

from rideworks.home import recent_ride_link
from rideworks.strava_effort import score


class HomeEffortTests(TestCase):
    def test_numeric_score_preserves_title_and_accessibility(self):
        row = dict(activity_id='ride-42', title='Race & Recovery <Zwift>')
        html = recent_ride_link(row, score(110))
        self.assertIn('effort-score effort-very-high', html)
        self.assertIn('Strava Relative Effort: 110, Very High', html)
        self.assertIn('Race &amp; Recovery &lt;Zwift&gt;', html)
        self.assertIn('href="/activities/ride-42"', html)

    def test_unavailable_and_zero_are_distinct(self):
        row = dict(activity_id='ride-43', title='Easy Ride')
        self.assertIn('Strava Relative Effort unavailable', recent_ride_link(row, None))
        self.assertIn('Strava Relative Effort: 0, Very Light', recent_ride_link(row, score(0)))
