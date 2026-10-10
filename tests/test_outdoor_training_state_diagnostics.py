"""Diagnostic alternatives stay separate from unchanged production HR policy."""
from unittest import TestCase
from tools.diagnose_outdoor_training_state import observed_segments, screens, file_evidence
from rideworks.training_state import DEFAULT_HR, HR_COVERAGE, hr_stream


class DiagnosticTests(TestCase):
    def test_partial_intervals_do_not_bridge_missing_recording_or_claim_active_time(self):
        times=list(range(600))+list(range(1200,1800))
        result=observed_segments(times,[143]*len(times),[],{})
        self.assertEqual(result['represented_seconds'],1200)
        self.assertEqual(result['unrepresented_recording_seconds'],600)
        self.assertAlmostEqual(result['stress'],100/3)
        self.assertIsNone(result['known_uncovered_timer_seconds'])
        self.assertFalse(result['timer_boundaries_verified'])
        self.assertIn('unverified',result['scope'])
        self.assertIsNone(observed_segments([0,1,1],[143]*3,[],{})['stress'])
        self.assertIsNone(observed_segments(list(range(599)),[143]*599,[],{})['stress'])

    def test_duplicate_timestamp_bins_excluded_and_split_without_choosing_values(self):
        times=list(range(600))+[600,600]+list(range(601,1201))
        hrs=[143]*600+[90,155]+[143]*600
        result=observed_segments(times,hrs,[],{})
        self.assertEqual(result['duplicate_timestamp_records_excluded'],2)
        self.assertEqual(result['represented_seconds'],1200)
        self.assertEqual(result['unrepresented_recording_seconds'],1)
        self.assertAlmostEqual(result['stress'],100/3)
        self.assertEqual(len(result['segments']),2)
        self.assertEqual(observed_segments([0,2,1],[143]*3,[],{})['reason'],'invalid_timing')

    def test_unresolved_timer_and_missing_hr_never_manufacture_scope(self):
        event=dict(event='timer',event_type='start',timestamp='2026-01-01T00:00:00+00:00')
        self.assertEqual(observed_segments(list(range(1200)),[143]*1200,[event],{})['reason'],'unresolved_timer')
        self.assertIsNone(observed_segments(list(range(1200)),[None]*1200,[],{})['stress'])

    def test_sensitivity_isolated_and_asymmetry_only(self):
        alternatives=screens();kwargs=dict(settings=DEFAULT_HR,source=dict(format='synthetic'),duration=600)
        times=list(range(601));hrs=[143]*601
        self.assertIsNone(hr_stream(times,hrs,**kwargs)['stress'])
        self.assertIsNone(alternatives['coverage_0.9'](times,hrs,**kwargs)['stress'])
        self.assertAlmostEqual(alternatives['symmetric_1_percent'](times,hrs,**kwargs)['stress'],100/6)
        self.assertIsNone(hr_stream(times,hrs,**kwargs)['stress'])
        self.assertEqual(hr_stream.__globals__['HR_COVERAGE'],HR_COVERAGE)
        hrs=[143]*1000;hrs[400:425]=[None]*25;times=list(range(1000));kwargs['duration']=1000
        self.assertIsNone(hr_stream(times,hrs,**kwargs)['stress'])
        self.assertIsNotNone(alternatives['coverage_0.95'](times,hrs,**kwargs)['stress'])
        self.assertIsNone(hr_stream(times,hrs,**kwargs)['stress'])

    def test_multi_lap_summary_is_evidence_without_supported_duration_pair(self):
        native=dict(source=dict(source_id='synthetic',content_format='TCX'),extraction={},
                    summary={},events=[],records=[],xml_context=dict(lap_summaries=[
                        dict(avg_heart_rate=130,total_time_seconds=600),dict(avg_heart_rate=140,total_time_seconds=600)]))
        evidence=file_evidence(native,screens())
        self.assertTrue(evidence['hr_summary_present'])
        self.assertEqual(evidence['lap_hr_summary_count'],2)
        self.assertIsNone(evidence['source_active_duration'])
        self.assertIsNone(evidence['summary_fallback']['stress'])
