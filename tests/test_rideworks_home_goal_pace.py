"""Annual target-pace display uses the configured goal and calendar year."""
from unittest import TestCase

from rideworks.home import pace


class HomeGoalPaceTests(TestCase):
    def test_behind_original_annual_target_pace(self):
        self.assertEqual(pace(-96.1, 2200, 365),
                         '96.1 mi behind target pace (42.2 mi/week)')

    def test_ahead_and_exactly_on_target(self):
        self.assertEqual(pace(12.34, 2200, 365),
                         '12.3 mi ahead of target pace (42.2 mi/week)')
        self.assertEqual(pace(0, 2200, 365),
                         'On target pace (42.2 mi/week)')

    def test_different_goal_and_leap_year(self):
        self.assertEqual(pace(-5, 1500, 365),
                         '5.0 mi behind target pace (28.8 mi/week)')
        self.assertEqual(pace(-5, 2200, 366),
                         '5.0 mi behind target pace (42.1 mi/week)')
