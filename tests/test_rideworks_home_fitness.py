"""Home Training State uses the accepted daily Fitness series without recomputing it."""
from datetime import date, timedelta
import re
from unittest import TestCase
from unittest.mock import patch

from rideworks.training_state_page import home_fitness_chart, training_home


def days_ending(last, count, *, change=1.4):
    first = last - timedelta(days=count - 1)
    return [
        dict(day=(first + timedelta(days=i)).isoformat(),
             fitness=10.0 + .2 * i, fatigue=80.0, form=-50.0,
             changes7={'fitness': change if i >= 7 else None})
        for i in range(count)
    ]


class HomeFitnessChartTests(TestCase):
    def test_three_calendar_months_uses_exact_daily_fitness(self):
        days = days_ending(date(2026, 10, 17), 150)
        svg = home_fitness_chart(days)
        self.assertIn('data-range-start="2026-07-18"', svg)
        self.assertIn('data-range-end="2026-10-17"', svg)
        self.assertIn('data-point-count="92"', svg)
        points = re.search(r'<polyline[^>]+points="([^"]+)"', svg).group(1).split()
        self.assertEqual(len(points), 92)
        self.assertEqual(svg.count('data-series="fitness"'), 1)
        self.assertNotIn('fatigue', svg.casefold())
        self.assertNotIn('form', svg.casefold())
        self.assertIn('Current Fitness 39.8.', svg)
        first_y, last_y = float(points[0].split(',')[1]), float(points[-1].split(',')[1])
        self.assertGreater(first_y, last_y)

    def test_month_end_clamp_matches_full_training_state(self):
        days = days_ending(date(2024, 5, 31), 130)
        svg = home_fitness_chart(days)
        # Three calendar months before May 31 is Feb 29 (leap year).
        # Like the full-page 3-month view, the cutoff day is excluded.
        self.assertIn('data-range-start="2024-03-01"', svg)
        self.assertIn('data-range-end="2024-05-31"', svg)

    def test_one_day_renders_a_point_not_an_invented_trend(self):
        svg = home_fitness_chart(days_ending(date(2026, 10, 17), 1))
        self.assertIn('data-point-count="1"', svg)
        self.assertNotIn('<polyline', svg)
        self.assertIn('class="home-fitness-endpoint"', svg)

    def test_home_card_uses_exact_current_fitness_and_week_change(self):
        days = days_ending(date(2026, 10, 17), 92, change=-1.4)
        days[-1]['fitness'] = 29.9
        with patch('rideworks.training_state_page.training_state', return_value={'days': days}) as model:
            html = training_home(object(), 'America/Los_Angeles')
        model.assert_called_once()
        self.assertIn('<strong>29.9</strong>', html)
        self.assertIn('Current fitness', html)
        self.assertIn('↓ 1.4 from 7 days ago', html)
        self.assertIn('id="home-fitness-chart"', html)
        self.assertNotIn('Fatigue', html)
        self.assertNotIn('Form ', html)
        self.assertNotIn('Last 3 months', html)
        self.assertIn('href="/training-state"', html)

    def test_week_change_up_flat_and_unavailable(self):
        days = days_ending(date(2026, 10, 17), 8, change=1.4)
        with patch('rideworks.training_state_page.training_state', return_value={'days': days}):
            self.assertIn('↑ 1.4 from 7 days ago', training_home(None, 'UTC'))
        days[-1]['changes7']['fitness'] = -0.04
        with patch('rideworks.training_state_page.training_state', return_value={'days': days}):
            self.assertIn('No change from 7 days ago', training_home(None, 'UTC'))
        days[-1]['changes7']['fitness'] = None
        with patch('rideworks.training_state_page.training_state', return_value={'days': days}):
            self.assertIn('7-day change unavailable', training_home(None, 'UTC'))

    def test_no_scored_history_is_an_honest_empty_state(self):
        with patch('rideworks.training_state_page.training_state', return_value={'days': []}):
            html = training_home(None, 'UTC')
        self.assertIn('No usable training stress yet.', html)
        self.assertNotIn('home-fitness-chart', html)
