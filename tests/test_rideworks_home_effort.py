from unittest import TestCase

from rideworks.home import recent_ride_link


class HomeEffortTests(TestCase):
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
