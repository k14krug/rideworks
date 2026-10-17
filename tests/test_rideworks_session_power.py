"""Approved production session estimates: scope, source order and cache changes."""
from datetime import datetime,timezone
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from rideworks.store import Store
from rideworks.strava_api import apply_observations,normalize
from rideworks.strava_streams import persist
from rideworks.training_state import (SESSION_PARAMETERS,choose_session_power,session_power_candidate,
    session_distribution,session_buffer_fourths,selected_stress,training_state,calculate_ride)

FTP=dict(value=200,status='available')
API=dict(format='Strava API stream',device_watts=True)


def candidate(times=None,powers=None,**changes):
    times=list(range(1800)) if times is None else times
    powers=[200]*len(times) if powers is None else powers
    return session_power_candidate(times,powers,**(dict(duration=1800,elapsed_duration=1800,ftp=FTP,source=API)|changes))


class SessionPowerTests(TestCase):
    def test_reference_time_buffer_emission_and_unrounded_formula(self):
        points=[(i,100 if i<600 else 300) for i in range(1800)]
        # Independent literal batching, including the reference check-before-add.
        batch=[];clock=0;means=[]
        for i in range(1,len(points)):
            batch.append(points[i][1])
            if clock>=30:
                means.append(sum(batch)/len(batch));batch=[];clock=0
            clock+=points[i][0]-points[i-1][0]
        expected=(sum(x**4 for x in means)/len(means))**.25
        result=candidate(powers=[p for t,p in points])
        self.assertAlmostEqual(result['weighted_power'],expected)
        self.assertAlmostEqual(result['stress'],50*(expected/200)**2)
        self.assertEqual(result['buffer_count'],len(means));self.assertEqual(result['samples_invented'],0)
        self.assertFalse(result['whole_session_verified'])
        self.assertNotIn('observed_work_kj',result)

    def test_distribution_exact_windows_edges_and_equal_fraction_counterexample(self):
        dispersed=[i for i in range(3600) if i<600 or i%5!=0]
        clustered=[i for i in range(3600) if not 1200<=i<1800]
        self.assertEqual(len(dispersed),len(clustered))
        self.assertTrue(session_distribution(dispersed,[(0,3600)])['passes'])
        self.assertEqual(session_distribution(clustered,[(0,3600)])['reason'],'concentrated_recording_omission')
        times=[i for i in range(1000) if not 267<=i<400 and i%7!=0]
        result=session_distribution(times,[(0,1000)])
        self.assertEqual(result['worst_window_observed_seconds'],min(sum(s<=i<s+300 for i in times) for s in range(701)))
        for times in [list(range(600,3600)),list(range(3000))]:
            self.assertEqual(session_distribution(times,[(0,3600)])['reason'],'concentrated_recording_omission')

    def test_eligible_imperfect_power_precedes_higher_hr_without_adding_or_filling(self):
        times=[i for i in range(1800) if not 850<=i<950]
        result=candidate(times);power=dict(status='partial',stress=40,scope='observed segments')
        selected=selected_stress(power,dict(stress=120,scope='HR estimate'),result)
        self.assertEqual(selected['method'],'session_power');self.assertEqual(selected['stress'],50)
        self.assertEqual(result['observed_watt_bins'],1700)
        self.assertEqual(result['representativeness']['longest_omission_seconds'],100)
        self.assertEqual(result['samples_invented'],0)
        self.assertIn('unverified',selected['scope'])

    def test_complete_corrected_and_ineligible_session_fallbacks(self):
        estimate=candidate()
        for status in ['calculated','corrected_estimate']:
            selected=selected_stress(dict(status=status,stress=17,scope='recorded interval'),dict(stress=90),estimate)
            self.assertEqual(selected['method'],'power');self.assertEqual(selected['stress'],17)
        bad=candidate(list(range(600)),duration=1800,elapsed_duration=1800)
        power=dict(status='partial',stress=17,scope='observed segments')
        self.assertEqual(selected_stress(power,dict(stress=90,scope='HR estimate'),bad)['method'],'hr')
        self.assertEqual(selected_stress(power,dict(stress=None),bad)['stress'],17)
        self.assertIsNone(selected_stress(dict(status='unavailable'),dict(stress=None),bad)['stress'])

    def test_known_omitted_effort_overrides_a_passing_distribution_screen(self):
        times=[i for i in range(1800) if not 700<=i<730]
        unknown=candidate(times);known=candidate(times,known_omitted_effort=True)
        self.assertIsNotNone(unknown['stress']);self.assertTrue(known['representativeness']['passes'])
        self.assertEqual(known['reason'],'known_omitted_workout_effort')

    def test_moving_duration_does_not_hide_missing_elapsed_time_and_null_watts(self):
        r=candidate(list(range(1200)),duration=1200,elapsed_duration=3600)
        self.assertEqual(r['reason'],'insufficient_distributed_observations')
        powers=[200]*1800;powers[700:800]=[None]*100
        result=candidate(powers=powers)
        self.assertEqual(result['missing_watt_samples_excluded'],100)
        self.assertEqual(result['observed_watt_bins'],1700);self.assertAlmostEqual(result['stress'],50)
        # Matching end sample does not count beyond the source elapsed endpoint.
        result=candidate(list(range(1801)))
        self.assertEqual(result['representativeness']['observed_seconds'],1800)

    def test_invalid_pairing_timing_watts_duration_and_ftp(self):
        for times,powers,changes in [([],[],{}),([0,1,1],[200]*3,{}),([0,2,1],[200]*3,{}),
            ([0,1],[200],{}),(None,[200]*1799+[float('nan')],{}),
            (None,None,dict(duration=1802)),(None,None,dict(ftp=dict(value=None))),
            (None,None,dict(timeline_start=None))]:
            self.assertIsNone(candidate(times,powers,**changes)['stress'])
        self.assertEqual(candidate(list(range(600)))['reason'],'insufficient_distributed_observations')
        # Dense dispersed recording cannot meet the required contiguous floor.
        times=[i for i in range(1800) if i%10!=0]
        self.assertEqual(candidate(times)['reason'],'no_accepted_600_second_observed_segment')

    def test_verified_pauses_exclude_nonzero_points_and_reset_weighting(self):
        stamp=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        events=[dict(event='timer',event_type=kind,timestamp=stamp(t)) for t,kind in [(0,'start'),(900,'stop_all'),(1500,'start'),(2400,'stop_all')]]
        summary=dict(start_time=stamp(0),timestamp=stamp(2400),total_timer_time=1800,total_elapsed_time=2400)
        result=candidate(list(range(2400)),[100]*900+[600]*600+[300]*900,elapsed_duration=2400,events=events,summary=summary)
        fourths=session_buffer_fourths(list(zip(range(900),[100]*900)))+session_buffer_fourths(list(zip(range(1500,2400),[300]*900)))
        weighted=(sum(fourths)/len(fourths))**.25
        self.assertAlmostEqual(result['weighted_power'],weighted)
        self.assertEqual(result['known_pause_samples_excluded'],600);self.assertEqual(result['representativeness']['observed_fraction'],1)
        self.assertTrue(result['timer_boundaries_verified'])
        self.assertEqual(candidate(list(range(2400)),elapsed_duration=2400,events=events[:-1],summary=summary)['reason'],'contradictory_or_unresolved_timer')
        self.assertEqual(candidate(list(range(2400)),duration=1900,elapsed_duration=2400,events=events,summary=summary)['reason'],'timer_reported_duration_conflict')
        # Paired events with unsupported summary boundaries cannot compress time.
        summary['start_time']=stamp(-600)
        result=candidate(list(range(2400)),[100]*900+[600]*600+[300]*900,elapsed_duration=3000,
            events=events,summary=summary,timeline_start=-600)
        self.assertFalse(result['timer_boundaries_verified'])
        self.assertIsNone(result['stress']);self.assertIn('elapsed timeline',result['distribution_time_basis'])

    def test_competing_sources_do_not_select_larger_or_only_eligible_session(self):
        a=candidate();b=candidate(powers=[250]*1800)
        self.assertEqual(choose_session_power([a,b],dict(reason=None),FTP)['reason'],'multiple_eligible_session_power_sources')
        self.assertEqual(choose_session_power([a],dict(reason='multiple_usable_power_sources'),FTP)['reason'],'conflicting_recorded_power_sources')

    def test_session_policy_parameters_and_version_invalidate_cache_then_reuse(self):
        with tempfile.TemporaryDirectory() as directory,Store(directory) as store:
            from ftp_fixture import seed_ftp
            seed_ftp(store)
            item=dict(id=123,name='Synthetic virtual workout',type='VirtualRide',sport_type='VirtualRide',
                start_date='2026-10-01T12:00:00Z',elapsed_time=1800,moving_time=1800,
                device_watts=True,has_heartrate=True,average_heartrate=120)
            apply_observations(store,[normalize(item)],321,1791500000)
            times=[i for i in range(1800) if not 800<=i<900]
            def stream(values):return dict(data=values,original_size=len(values),resolution='high',series_type='time')
            persist(store,123,dict(time=stream(times),watts=stream([200]*len(times))))
            now=datetime(2026,10,9,tzinfo=timezone.utc)
            with patch('rideworks.training_state.VERSION','training-state-v3'):
                training_state(store,'UTC',as_of=now)
            with patch('rideworks.training_state.calculate_ride',wraps=calculate_ride) as calculate:
                data=training_state(store,'UTC',as_of=now);self.assertEqual(calculate.call_count,1)
            self.assertEqual(data['days'][0]['rides'][0]['selected']['status'],'session_estimate')
            with patch('rideworks.training_state.calculate_ride',side_effect=AssertionError('cache must be reused')):
                self.assertEqual(data,training_state(store,'UTC',as_of=now))
            with patch('rideworks.training_state.SESSION_PARAMETERS',SESSION_PARAMETERS|dict(local_floor=.9)):
                with patch('rideworks.training_state.calculate_ride',wraps=calculate_ride) as calculate:
                    changed=training_state(store,'UTC',as_of=now);self.assertEqual(calculate.call_count,1)
                self.assertEqual(changed['days'][0]['rides'][0]['selected']['method'],'hr')
