"""Relative Effort: previous 42 calendar days, load-first percentile labels."""
from datetime import date, timedelta
from unittest import TestCase
from unittest.mock import patch

from rideworks.relative_effort import (MIN_COMPARISONS, classify, card, chip,
                                       for_store, VERSION)


def ride(identity, day, stress, hours=1, status='calculated', *, unknown=False):
    method = {'calculated':'power', 'corrected_estimate':'power',
              'session_estimate':'session_power', 'hr_estimate':'hr',
              'partial':'power','unavailable':None}[status]
    return dict(activity_id=str(identity), day=day, timezone_unknown=unknown,
        selected=dict(method=method, status=status, stress=stress),
        power=dict(intervals=[dict(seconds=hours*3600)]),
        session_power=dict(duration_seconds=hours*3600),
        hr=dict(active_seconds=hours*3600))


def comparison_rides(day=date(2026, 10, 17)):
    return [ride(i, (day - timedelta(days=6-i)).isoformat(), (i+1)*10)
            for i in range(6)]


class RelativeEffortTests(TestCase):
    def test_requires_six_earlier_qualifying_rides(self):
        sample = comparison_rides()
        sample.append(ride('current','2026-10-17',35))
        scores=classify(sample)
        self.assertEqual(scores['5']['status'],'unavailable')
        self.assertEqual(scores['5']['reason'],'insufficient_history')
        self.assertEqual(scores['current']['status'],'available')
        self.assertEqual(scores['current']['comparisons'],MIN_COMPARISONS)
        self.assertEqual(scores['current']['version'], VERSION)

    def test_short_intense_workout_boosts_one_band_only(self):
        sample=comparison_rides()+[ride('short','2026-10-17',30,.25)]
        result=classify(sample)['short']
        self.assertEqual((result['load_category'],result['intensity_category'],result['category']),
                         ('Moderate','Very High','High'))
        self.assertEqual(result['stress_per_hour'],120)
        self.assertAlmostEqual(result['load_percentile'],2.5/6)

    def test_long_endurance_keeps_very_high_load_rating(self):
        sample=comparison_rides()+[ride('long','2026-10-17',80,4)]
        result=classify(sample)['long']
        self.assertEqual((result['load_category'],result['intensity_category'],result['category']),
                         ('Very High','Light','Very High'))

    def test_42_day_boundary_ignores_same_day_future_and_unknown_dates(self):
        target=date(2026,10,17)
        sample=[ride('old',(target-timedelta(days=43)).isoformat(),999),
                ride('edge',(target-timedelta(days=42)).isoformat(),10)]
        for i in range(5):
            sample.append(ride(str(i),(target-timedelta(days=5-i)).isoformat(),20))
        sample += [ride('current',target.isoformat(),30),
                   ride('same',target.isoformat(),900),
                   ride('tomorrow',(target+timedelta(days=1)).isoformat(),800),
                   ride('uncertain',(target-timedelta(days=1)).isoformat(),700,unknown=True)]
        classified=classify(sample)
        self.assertEqual(classified['current']['comparisons'],6)
        self.assertEqual(classified['same']['comparisons'],6)
        self.assertEqual(classified['current']['load_category'],'Very High')
        self.assertEqual(classified['uncertain']['reason'],'date_unknown')
        # On Oct 18, the Sep 5 boundary ride is now outside the 42-day window.
        self.assertEqual(classified['tomorrow']['comparisons'],7)

    def test_estimates_are_labeled_and_partial_is_excluded(self):
        sample=comparison_rides()
        sample.append(ride('hr','2026-10-17',55,1.5,status='hr_estimate'))
        sample.append(ride('partial','2026-10-16',900,1,status='partial'))
        sample.append(ride('session','2026-10-17',35,.5,status='session_estimate'))
        sample.append(ride('no_duration','2026-10-17',20,0))
        output=classify(sample)
        self.assertEqual(output['hr']['status'],'available')
        self.assertEqual(output['hr']['evidence_status'],'hr_estimate')
        self.assertEqual(output['hr']['comparisons'],6)
        self.assertEqual(output['session']['status'],'available')
        self.assertEqual(output['session']['stress_per_hour'],70)
        self.assertEqual(output['partial']['reason'],'partial_only')
        self.assertEqual(output['no_duration']['reason'],'active_duration_unavailable')

    def test_zero_stress_is_valid_not_missing(self):
        sample=comparison_rides()+[ride('zero','2026-10-17',0)]
        self.assertEqual(classify(sample)['zero']['category'],'Very Light')

    def test_equal_values_use_midrank_not_top_of_distribution(self):
        start=date(2026,10,10)
        sample=[ride(i,(start+timedelta(days=i)).isoformat(),50) for i in range(6)]
        sample.append(ride('current','2026-10-17',50))
        result=classify(sample)['current']
        self.assertEqual(result['load_percentile'],.5)
        self.assertEqual(result['intensity_percentile'],.5)
        self.assertEqual(result['category'],'Moderate')

    def test_both_surfaces_share_the_same_category_and_neutral_state(self):
        sample=comparison_rides()+[ride('current','2026-10-17',30,.25)]
        rating=classify(sample)['current']
        detail=card(rating)
        list_label=chip(rating)
        self.assertIn('Relative Effort',detail)
        self.assertIn('effort-high',detail)
        self.assertIn('effort-high',list_label)
        self.assertIn('Training load',detail)
        self.assertIn('Intensity',detail)
        self.assertIn('Compared with 6 qualifying rides',detail)
        self.assertIn('How this is rated',detail)
        self.assertIn('Not rated',card(None))
        self.assertIn('effort-unavailable',chip(None))

    def test_fixed_athlete_timezone_for_list_and_details(self):
        with patch('rideworks.relative_effort.ride_results',
                   return_value=(comparison_rides()+[ride('a','2026-10-17',40)],{})) as history:
            self.assertEqual(for_store(None)['a']['status'],'available')
        self.assertEqual(history.call_args.args[1],'America/Los_Angeles')
