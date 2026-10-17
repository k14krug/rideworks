"""Synthetic scientific checks for P4-01's unaccepted candidate policies."""
import csv
from datetime import date, timedelta
import math
from pathlib import Path
import tempfile
import unittest
from tools.research_training_state_ftp import (
    read_ftp, lookup, resolved_ftp, segments, metrics, timer_intervals, daily_models, METRICS)


class DatedFTPResearchTests(unittest.TestCase):
    def test_synthetic_source_intervals_and_no_backfill(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'synthetic.csv'
            source.write_text('effective_from_date,effective_until_date_exclusive,ftp_watts\n'
                              '2020-01-01,2020-02-01,200\n2020-02-01,2020-03-01,210\n2020-03-01,,210\n')
            history=read_ftp(source,expected_count=3)
        self.assertEqual(len(history),3)
        self.assertIsNone(lookup(history,date(2019,12,31)))
        for i,row in enumerate(history):
            self.assertIs(lookup(history,row['start']),row)
            if i:
                self.assertIs(lookup(history,row['start']-timedelta(days=1)),history[i-1])
        self.assertIs(lookup(history,date(2099,1,1)),history[-1])
        self.assertEqual(history[1]['watts'],history[2]['watts'])
        self.assertNotEqual(history[1]['start'],history[2]['start'])

    def test_bad_intervals_stop_instead_of_sorting_or_repairing(self):
        cases=[
            [('2020-01-01','2020-01-03',200),('2020-01-02','',210)],
            [('2020-01-01','2020-01-02',0),('2020-01-02','',210)],
            [('2020-01-02','2020-01-02',200),('2020-01-02','',210)],
            [('2020-01-01','2020-01-02',200),('2020-01-02','2020-01-03',210)],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ftp.csv'
            for rows in cases:
                with path.open('w') as f:
                    w=csv.writer(f);w.writerow(['effective_from_date','effective_until_date_exclusive','ftp_watts']);w.writerows(rows)
                with self.assertRaises(ValueError):read_ftp(path,expected_count=2)

    def test_unknown_timezone_boundary_withheld_not_reassigned(self):
        history=[dict(start=date(2020,1,1),end=date(2020,2,1),watts=200),
                 dict(start=date(2020,2,1),end=None,watts=210)]
        selected,uncertain=resolved_ftp(history,date(2020,2,1),False)
        self.assertIs(selected,history[1]);self.assertTrue(uncertain)
        self.assertFalse(resolved_ftp(history,date(2020,2,1),True)[1])
        self.assertFalse(resolved_ftp(history,date(2020,2,3),False)[1])
        self.assertTrue(resolved_ftp(history,date(2019,12,31),False)[1])
        self.assertEqual(resolved_ftp(history,None,False),(None,False))

    def test_gaps_and_missing_split_without_interpolation(self):
        times=list(range(600))+list(range(900,1500));powers=[100]*600+[300]*600
        before=(times[:],powers[:]);parts,error=segments(times,powers)
        self.assertIsNone(error);self.assertEqual(list(map(len,parts)),[600,600])
        result=metrics(parts,powers,200,600)
        self.assertEqual(result['seconds'],1200);self.assertEqual(result['work_kj'],240)
        self.assertAlmostEqual(result['stress'],600/36*((100/200)**2+(300/200)**2))
        self.assertGreater(result['pooled_stress'],result['stress'])
        self.assertEqual((times,powers),before)
        powers[500]=None
        parts,_=segments(times,powers)
        self.assertEqual(list(map(len,parts)),[500,99,600])
        self.assertEqual(metrics(parts,powers,200,600)['seconds'],600)

    def test_duplicate_timestamp_excludes_all_occurrences(self):
        times=[0,1,1,2,3];powers=[100,999,100,100,100]
        parts,_=segments(times,powers)
        self.assertEqual(parts,[[0],[3,4]])
        self.assertEqual(times,[0,1,1,2,3])
        self.assertEqual(segments([0,2,1],[100]*3),([], 'backwards_timestamps'))
        self.assertEqual(segments([0,.5,1],[100]*3),([], 'subsecond_timestamps_unsupported'))

    def test_invalid_and_missing_power_never_become_zero(self):
        for bad in (None,-1,math.nan,math.inf,True):
            parts,_=segments([0,1,2],[100,bad,100])
            self.assertEqual(parts,[[0],[2]])
        parts,_=segments(list(range(600)),[0]*600)
        self.assertEqual(metrics(parts,[0]*600,200,600)['stress'],0)
        self.assertIsNone(metrics(parts,[0]*600,None,600)['stress'])
        self.assertIsNone(metrics([],[],200,600)['stress'])

    def test_short_segment_threshold_has_visible_omission(self):
        times=list(range(599))+list(range(700,1300));power=[200]*1199
        parts,_=segments(times,power)
        self.assertEqual(metrics(parts,power,200,600)['seconds'],600)
        self.assertEqual(metrics(parts,power,200,30)['seconds'],1199)
        self.assertAlmostEqual(metrics(parts,power,200,600)['stress'],100/6)

    def test_timer_stop_boundary_and_pause_do_not_consume_missing_power(self):
        times=list(range(1201));powers=[200]*1200+[None]
        parts,_=segments(times,powers,[(0,1200)])
        self.assertEqual(sum(map(len,parts)),1200)
        self.assertAlmostEqual(metrics(parts,powers,200,600)['stress'],100/3)
        parts,_=segments(times,powers,[(0,600),(700,1200)])
        self.assertEqual(list(map(len,parts)),[600,500])
        # Missing active second remains missing; no tolerance repairs it.
        powers[100]=None
        parts,_=segments(times,powers,[(0,1200)])
        self.assertEqual(sum(map(len,parts)),1199)

    def test_timer_event_pairs_require_explicit_stop_and_restart(self):
        def event(second,kind):
            return dict(timestamp=f'2020-01-01T00:00:{second:02d}+00:00',event='timer',event_type=kind)
        ev=[event(0,'start'),event(10,'stop'),event(20,'start'),event(30,'stop_all')]
        intervals,error=timer_intervals(ev)
        self.assertIsNone(error);self.assertEqual([b-a for a,b in intervals],[10,10])
        for changed in (ev[:-1],ev[1:],ev+[event(40,'start')],[event(0,'start'),event(1,'start')]):
            self.assertIsNone(timer_intervals(changed)[0])

    def test_daily_unknowns_and_units_and_window_boundaries(self):
        base=dict(kind='Virtual Ride',eligible=True,dated_ftp={},best20=200,duration=3600,
                  **{key:None for key in METRICS})
        rows=[base|dict(day='2020-01-01',segment_work_kj=720,matched_work_kj=720,stress600=100),
              base|dict(day='2020-01-03',segment_work_kj=0,matched_work_kj=0,stress600=0)]
        days=daily_models(rows,date(2020,2,12))
        self.assertIsNone(days[1]['stress600']);self.assertTrue(days[1]['no_record'])
        self.assertEqual(days[2]['stress600'],0);self.assertFalse(days[2]['no_record'])
        self.assertEqual(days[6]['window7']['stress600']['subtotal'],100)
        self.assertEqual(days[7]['window7']['stress600']['subtotal'],0)
        self.assertIsNone(days[10]['window7']['stress600']['subtotal'])
        self.assertEqual(days[41]['window42']['stress600']['subtotal'],100)
        self.assertEqual(days[42]['window42']['stress600']['subtotal'],0)
        self.assertEqual(days[6]['window7']['segment_work_kj']['subtotal'],720)
        self.assertTrue(all(d['industry_unknown_seed']['ctl'] is None for d in days))


if __name__=='__main__':unittest.main()
