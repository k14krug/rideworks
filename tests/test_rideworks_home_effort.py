from unittest import TestCase

from rideworks.home import recent_ride_link


class HomeEffortTests(TestCase):
    def test_ride_link_preserves_title_and_escapes_markup(self):
        row = dict(activity_id='ride-42', title='Race & Recovery <Zwift>')
        html = recent_ride_link(row)
        self.assertIn('Race &amp; Recovery &lt;Zwift&gt;', html)
        self.assertIn('href="/activities/ride-42"', html)
