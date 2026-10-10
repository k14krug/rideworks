"""Candidate methodology checks, explicitly outside production selection."""
from datetime import datetime,timezone
from unittest import TestCase
from tools.evaluate_training_state_session_power import distribution_screen,estimate,reference_np,synthetic_cases


class SessionPowerEvaluationTests(TestCase):
    def test_constant_reference_and_session_formula_no_generated_samples(self):
        result=estimate(list(range(3600)),[200]*3600,duration=3600,elapsed_duration=3600,ftp=200)
        self.assertEqual(reference_np(list(range(3600)),[200]*3600),200)
        self.assertEqual(result['stress'],100);self.assertEqual(result['samples_invented'],0)
        self.assertFalse(result['whole_session_verified']);self.assertEqual(result['status'],'diagnostic_estimate')

    def test_batch_time_emission_is_not_rolling_np_or_interpolation(self):
        t=list(range(1200));p=[100+(i*13)%251 for i in t]
        gap_times=t[:615]+[x+133 for x in t[615:]]
        a=reference_np(t,p);b=reference_np(gap_times,p)
        self.assertNotEqual(a,b)
        r=estimate(gap_times,p,duration=1200,elapsed_duration=1333,ftp=200)
        self.assertEqual(r['samples_invented'],0);self.assertTrue(r['limitations'])

    def test_missing_invalid_and_conflicting_durations_excluded(self):
        kwargs=dict(duration=1200,elapsed_duration=1200,ftp=200)
        for times,powers,changes in [(list(range(1200)),[None]*1200,{}),
            ([0,1,1],[200]*3,{}),(list(range(1200)),[200]*1200,dict(duration=1202)),
            (list(range(1200)),[200]*1200,dict(ftp=None))]:
            self.assertIsNone(estimate(times,powers,**(kwargs|changes))['stress'])
        powers=[200]*1200;powers[600]=None
        result=estimate(list(range(1200)),powers,**kwargs)
        self.assertEqual(result['missing_watt_samples_excluded'],1)
        self.assertAlmostEqual(result['stress'],100/3)
        self.assertEqual(result['samples_invented'],0)

    def test_sparse_cannot_claim_representative_seconds_from_high_fraction(self):
        rows={r['case']:r for r in synthetic_cases()}
        self.assertIsNone(rows['uniform_sparse']['estimate']['stress'])
        self.assertIsNone(rows['clustered_sparse']['estimate']['stress'])
        self.assertEqual(rows['missing_hard']['observed_fraction'],rows['missing_recovery']['observed_fraction'])
        self.assertNotEqual(rows['missing_hard']['relative_error_against_complete'],rows['missing_recovery']['relative_error_against_complete'])
        self.assertTrue(rows['high_density_missing_hard']['known_missing_hard_interval'])
        self.assertIn('proposed_selection_exception',rows['high_density_missing_hard'])

    def test_verified_pause_excluded_and_timer_conflict_rejected(self):
        r=next(r for r in synthetic_cases() if r['case']=='verified_pause_with_nonzero_samples')['estimate']
        self.assertEqual(r['known_pause_samples_excluded'],60);self.assertEqual(r['timer_intervals'],2)
        self.assertNotEqual(r['literal_reference_stress'],r['stress'])
        stamp=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        events=[dict(event='timer',event_type='start',timestamp=stamp(0))]
        r=estimate(list(range(1200)),[200]*1200,duration=1200,elapsed_duration=1200,ftp=200,events=events)
        self.assertEqual(r['reason'],'contradictory_or_unresolved_timer')
        events.append(dict(event='timer',event_type='stop_all',timestamp=stamp(1200)))
        summary=dict(start_time=stamp(0),timestamp=stamp(1440),total_timer_time=1200,total_elapsed_time=1440)
        r=estimate(list(range(1440)),[200]*1200+[600]*240,duration=1200,elapsed_duration=1440,ftp=200,events=events,summary=summary)
        self.assertEqual(r['known_pause_samples_excluded'],240)
        self.assertAlmostEqual(r['stress'],100/3)
        self.assertEqual(r['representativeness']['observed_fraction'],1)

    def test_equal_sample_fractions_different_distribution(self):
        rows={r['case']:r for r in synthetic_cases()}
        distributed=rows['distributed_omissions'];clustered=rows['same_fraction_concentrated_omissions']
        self.assertEqual(distributed['observed_fraction'],clustered['observed_fraction'])
        self.assertIsNotNone(distributed['estimate']['stress'])
        self.assertEqual(clustered['estimate']['reason'],'concentrated_recording_omission')
        self.assertEqual(rows['one_600_second_segment']['estimate']['reason'],'insufficient_distributed_observations')
        for case in ('missing_start','missing_end'):
            self.assertEqual(rows[case]['estimate']['reason'],'concentrated_recording_omission')

    def test_sliding_screen_matches_independent_bin_counts(self):
        times=[i for i in range(1000) if not 267<=i<400 and i%7!=0]
        result=distribution_screen(times,[(0,1000)])
        expected=min(sum(s<=t<s+300 for t in times) for s in range(701))
        self.assertEqual(result['worst_window_observed_seconds'],expected)
        self.assertEqual(result['observed_seconds'],len(times))
        # Fixed aligned blocks can conceal a hole straddling their boundary.
        times=[i for i in range(1200) if not 225<=i<375]
        result=distribution_screen(times,[(0,1200)],local_floor=.6)
        self.assertEqual(result['worst_window_observed_fraction'],.5)
        self.assertFalse(result['passes'])

    def test_screen_is_not_evidence_of_unknown_gap_intensity(self):
        rows={r['case']:r for r in synthetic_cases()}
        known=rows['missing_hard']['estimate'];unknown=rows['unknown_hard_omission']['estimate']
        self.assertTrue(known['representativeness']['passes'])
        self.assertEqual(known['reason'],'known_omitted_workout_effort')
        self.assertIsNotNone(unknown['stress']);self.assertFalse(unknown['representativeness']['representativeness_proven'])
        self.assertIn('unknown gap intensity',' '.join(unknown['limitations']))

    def test_elapsed_axis_and_verified_pause_axis_are_distinct(self):
        times=list(range(1200))
        # Moving duration cannot conceal an entirely unrecorded elapsed ending.
        result=estimate(times,[200]*1200,duration=1200,elapsed_duration=3600,ftp=200)
        self.assertEqual(result['representativeness']['observed_fraction'],1/3)
        self.assertIsNone(result['stress'])
        result=distribution_screen(list(range(600))+list(range(1800,2400)),[(0,600),(1800,2400)])
        self.assertTrue(result['passes']);self.assertEqual(result['timeline_seconds'],1200)
        self.assertEqual(result['longest_omission_seconds'],0)

    def test_inclusive_thresholds_and_nonzero_source_origin(self):
        times=[i for i in range(1000) if not 300<=i<450]
        self.assertTrue(distribution_screen(times,[(0,1000)])['passes'])
        times.remove(450)
        self.assertFalse(distribution_screen(times,[(0,1000)])['passes'])
        times=list(range(600,1800))
        result=estimate(times,[200]*1200,duration=1200,elapsed_duration=1200,ftp=200,timeline_start=600)
        self.assertIsNotNone(result['stress'])
        self.assertEqual(estimate(times,[200]*1200,duration=1200,elapsed_duration=1200,ftp=200)['reason'],'power_outside_reported_elapsed_timeline')
