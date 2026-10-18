"""Annual target-pace display uses the configured goal and calendar year."""
from unittest import TestCase

from rideworks.home import annual_goal_meter, pace
from rideworks.dashboard import goal_progress


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

    def test_behind_pace_marker_matches_dashboard_arithmetic(self):
        goal = goal_progress(2026, '2026-10-17', 1651.9, '2200')
        markup = annual_goal_meter(goal)
        actual = 100 * goal['actual_miles'] / goal['target_miles']
        target = 100 * goal['target_to_date'] / goal['target_miles']
        self.assertIn(f'data-actual-percent="{actual:.4f}"', markup)
        self.assertIn(f'data-target-pace-percent="{target:.4f}"', markup)
        self.assertIn(f'style="left:{actual:.4f}%;width:{target-actual:.4f}%"', markup)
        self.assertIn('home-goal-pace-gap-behind', markup)
        self.assertIn(f'style="left:{target:.4f}%"', markup)
        self.assertIn('Target pace today:', markup)
        self.assertIn('aria-label="Annual mileage progress"', markup)

    def test_ahead_of_pace_marker_and_shaded_ahead_segment(self):
        goal = goal_progress(2026, '2026-10-17', 1800, '2200')
        markup = annual_goal_meter(goal)
        pace_pct = 100 * goal['target_to_date'] / goal['target_miles']
        actual_pct = 100 * goal['actual_miles'] / goal['target_miles']
        self.assertIn('home-goal-pace-gap-ahead', markup)
        self.assertIn(f'style="left:{pace_pct:.4f}%;width:{actual_pct-pace_pct:.4f}%"', markup)
        self.assertIn(f'style="left:{pace_pct:.4f}%"', markup)

    def test_exactly_on_pace_has_marker_without_false_gap(self):
        goal = goal_progress(2024, '2024-02-29', 60, '366')
        markup = annual_goal_meter(goal)
        self.assertIn('data-actual-percent="16.3934"', markup)
        self.assertIn('data-target-pace-percent="16.3934"', markup)
        self.assertIn('class="home-goal-pace-marker"', markup)
        self.assertNotIn('home-goal-pace-gap-', markup)

    def test_completed_or_exceeded_goal_keeps_track_and_marker_bounded(self):
        goal = goal_progress(2026, '2026-10-17', 2450, '2200')
        markup = annual_goal_meter(goal)
        self.assertIn('data-actual-percent="100.0000"', markup)
        self.assertIn('value="2200.0" max="2200.0"', markup)
        self.assertIn('home-goal-pace-gap-ahead', markup)
        self.assertNotIn('left:111.', markup)
        year_end = goal_progress(2026, '2026-12-31', 2200, '2200')
        self.assertIn('data-target-pace-percent="100.0000"', annual_goal_meter(year_end))

    def test_leap_year_marker_uses_366_days_not_365(self):
        goal = goal_progress(2024, '2024-02-29', 100, '2200')
        markup = annual_goal_meter(goal)
        self.assertIn(f'data-target-pace-percent="{100*60/366:.4f}"', markup)
