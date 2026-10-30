"""Synthetic source and boundary checks for the Home Training Overview."""
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from ftp_fixture import seed_ftp
from rideworks.dashboard import dashboard, mileage
from rideworks.ftp_history import add_entry, snapshot
from rideworks.home import home_page, training_overview
from rideworks.store import Store
from rideworks.training_state import daily_series


def periods(last=10, previous=4, today='2026-01-03'):
    return dict(today=today, last7=dict(miles=last, distance_unavailable=0),
                prior7=dict(miles=previous, distance_unavailable=0))


class OverviewTests(TestCase):
    def test_fitness_uses_existing_daily_model_and_signed_changes(self):
        ride = dict(day='2025-12-20', activity_id='synthetic',
                    selected=dict(stress=80, status='calculated'), power={})
        days = daily_series([ride], '2026-01-03')
        latest = days[-1]
        html = training_overview(periods(), dict(days=days), dict(value=200))
        self.assertIn(f'<strong>{latest["fitness"]:.1f}</strong>', html)
        self.assertIn(f'{latest["changes7"]["fitness"]:+.1f} points vs. 7 days ago', html)
        for change, expected in ((2.5, '+2.5'), (-2.5, '-2.5'), (0.0, '0.0'), (None, 'unavailable')):
            day = dict(day='2026-01-03', fitness=12.3, changes7=dict(fitness=change))
            result = training_overview(periods(), dict(days=[day]), dict(value=None))
            self.assertIn(expected, result)
        early = daily_series([dict(ride, day='2026-01-01')], '2026-01-03')
        self.assertIn('7-day change unavailable', training_overview(periods(), dict(days=early), dict(value=None)))
        self.assertIn('Early history provisional', training_overview(periods(), dict(days=early), dict(value=None)))

    def test_stale_and_future_fitness_are_not_mislabeled_as_current(self):
        days = [dict(day='2026-01-02', fitness=9, changes7=dict(fitness=-1)),
                dict(day='2026-01-04', fitness=99, changes7=dict(fitness=3))]
        html = training_overview(periods(), dict(days=days), dict(value=None))
        self.assertIn('<strong>9.0</strong>', html)
        self.assertIn('As of 2026-01-02 · -1.0 points vs. 7 days earlier', html)
        self.assertNotIn('<strong>99.0</strong>', html)
        html = training_overview(periods(), dict(days=[]), dict(value=None))
        self.assertIn('7-day change unavailable', html)
        self.assertEqual(html.count('class="metric-unavailable"'), 2)

    def test_mileage_year_boundary_missing_and_zero_prior(self):
        rows = [dict(activity_id='a', start_time='2026-01-02T12:00:00+00:00', absolute_time=True,
                     date_key='2026-01-02', activity_type='Ride', distance=3*1609.344,
                     distance_source={'context':'FIT session'}),
                dict(activity_id='b', start_time='2025-12-25T12:00:00+00:00', absolute_time=True,
                     date_key='2025-12-25', activity_type='Ride', distance=2*1609.344,
                     distance_source={'context':'FIT session'})]
        data = mileage(rows, 'UTC', as_of=datetime(2026, 1, 3, 12, tzinfo=timezone.utc))
        html = training_overview(data, dict(days=[]), dict(value=None))
        self.assertIn('<strong>3.0 mi</strong>', html)
        self.assertIn('+1.0 mi vs. previous 7 days', html)
        self.assertIn('+10.0 mi vs. previous 7 days', training_overview(periods(10, 0), dict(days=[]), dict(value=None)))
        self.assertIn('-4.0 mi vs. previous 7 days', training_overview(periods(0, 4), dict(days=[]), dict(value=None)))
        self.assertIn('0.0 mi vs. previous 7 days', training_overview(periods(0, 0), dict(days=[]), dict(value=None)))
        self.assertIn('comparison unavailable', training_overview(periods(None, 0), dict(days=[]), dict(value=None)))
        self.assertIn('comparison unavailable', training_overview(periods(2, None), dict(days=[]), dict(value=None)))
        data = periods(10, 4); data['prior7']['distance_unavailable'] = 1
        self.assertIn('Some distances unavailable', training_overview(data, dict(days=[]), dict(value=None)))

    def test_home_uses_effective_recorded_ftp_at_athlete_calendar_boundary(self):
        with TemporaryDirectory() as directory, Store(directory) as store:
            def render(when):
                data = dashboard(store, 'UTC', as_of=when)
                with patch('rideworks.home.dashboard', return_value=data):
                    return home_page(store, 'home_tz=UTC').split('id="home-ftp"')[1].split('</div>')[0]
            before = datetime(2026, 1, 2, 7, 59, tzinfo=timezone.utc)
            boundary = datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)
            self.assertIn('Unavailable', render(before))
            seed_ftp(store, [('2026-01-02', 211)])
            self.assertIn('Unavailable', render(before))
            self.assertIn('<strong>211 W</strong>', render(boundary))
            add_entry(store, '2026-02-01', 230, expected_revision=snapshot(store)['revision'])
            self.assertIn('<strong>211 W</strong>', render(boundary))
            self.assertIn('<strong>230 W</strong>', render(datetime(2026, 2, 1, 8, tzinfo=timezone.utc)))
            self.assertIn('/performance/ftp', render(boundary))
