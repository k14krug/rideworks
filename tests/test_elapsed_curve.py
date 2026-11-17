"""Independent elapsed power examples and boundary policies."""
import unittest
from datetime import datetime, timezone
from rideworks.elapsed_curve import calculate

START=datetime(2026,1,1,tzinfo=timezone.utc)

class ElapsedMath(unittest.TestCase):
    def calc(self,n,items,pauses=(),durations=()):
        return calculate(n,items,start=START,pauses=pauses,durations=list(durations))

    def test_verified_pause_full_endpoint(self):
        samples=[(i,200) for i in range(6000) if not 2700<=i<3300]
        p=self.calc(6000,samples,[(2700,3300)])['points'][-1]
        self.assertEqual((p['average_watts'],p['observed_seconds'],p['pause_seconds']),(180,5400,600))

    def test_fractional_and_terminal(self):
        p=self.calc(2.5,[(0,100),(1,200),(2,300),(2.5,999)])['points'][-1]
        self.assertEqual((p['average_watts'],p['observed_seconds']),(180,2.5))
        p=self.calc(2,[(0,100),(1,200),(2,999)])['points'][-1]
        self.assertEqual(p['average_watts'],150)

    def test_verified_pause_and_one_second_repair(self):
        missing=set(range(2000,2300)) | {3000}
        r=self.calc(6553,[(i,100) for i in range(6553) if i not in missing],[(2000,2300)])
        p=r['points'][-1]
        self.assertEqual((p['observed_seconds'],p['pause_seconds'],p['estimated_seconds'],p['unknown_seconds']),(6252,300,1,0))
        self.assertEqual(p['sum_watts'],625300)
        self.assertAlmostEqual(p['average_watts'],625300/6553)

    def test_standard_window_with_pause_estimate_and_unknown(self):
        missing=set(range(20,30)) | {40,60,61}
        p=self.calc(100,[(i,100) for i in range(100) if i not in missing],[(20,30)])['points'][-1]
        self.assertEqual((p['observed_seconds'],p['pause_seconds'],p['estimated_seconds'],p['unknown_seconds']),(87,10,1,2))
        self.assertEqual((p['sum_watts'],p['average_watts']),(8800,88))
        self.assertAlmostEqual(p['coverage'],87/90)

    def test_coverage_and_fallback(self):
        for observed in (89,90,94,95):
            r=self.calc(100,[(i,100) for i in range(observed)])
            endpoint=next((p for p in r['points'] if p['duration_seconds']==100),None)
            self.assertEqual(bool(endpoint),observed>=90)
            self.assertIsNone(r['minimum'])
        for observed,standard in ((899,False),(900,True),(949,True),(950,True)):
            r=self.calc(1000,[(i,100) for i in range(observed)])
            self.assertEqual(bool(r['points']),standard)
            self.assertIsNone(r['minimum'])

    def test_one_second_repair_and_no_fallback_interpolation(self):
        for n in (19,20):
            samples=[(i,100 if i<10 else 200) for i in range(n) if i!=10]
            r=self.calc(n,samples)
            p=r['points'][-1];self.assertEqual((p['estimated_seconds'],p['unknown_seconds']),(1,0))
            if n==20:self.assertEqual(p['sum_watts'],2950)

    def test_large_api_example(self):
        missing=set(range(1480,1801)) | set(range(1827,1881)) | {5055}
        r=self.calc(6553,[(i,100) for i in range(6553) if i not in missing])
        p=r['points'][-1];self.assertEqual((p['observed_seconds'],p['unknown_seconds'],p['estimated_seconds'],p['pause_seconds']),(6177,375,1,0))
        self.assertAlmostEqual(p['average_watts'],617800/6553)

    def test_boundary_and_interior_conflict(self):
        r=self.calc(5,[(0,100),(1,100),(2,200),(4,200)],[(2,4)])
        p=r['points'][-1];self.assertEqual((p['pause_seconds'],p['sum_watts']),(2,400))
        r=self.calc(5,[(0,100),(1,100),(2,200),(3,100),(4,200)],[(2,4)])
        p=r['points'][-1];self.assertEqual((p['pause_seconds'],p['sum_watts']),(0,700))
        self.assertIn('power_inside_pause',p['timer_conflicts'])

    def test_strict_vs_elapsed(self):
        from datetime import timedelta
        from rideworks.power_curve import mmp
        samples=[(i,100 if i<1200 else 200) for i in range(2400) if i!=1200]
        r=self.calc(2400,samples,[(1200,1201)],[1200])
        p=next(p for p in r['points'] if p['duration_seconds']==1200)
        self.assertEqual(p['sum_watts'],239800)
        rows=[dict(record_index=i,power=w,timestamp=(START+timedelta(seconds=t)).isoformat()) for i,(t,w) in enumerate(samples)]
        strict=mmp(rows,durations=[1200])['points'][0]
        self.assertEqual(strict['average_watts'],100)
        self.assertTrue(any(p['duration_seconds']==2400 for p in r['points']))
        self.assertFalse(mmp(rows,durations=[2400])['points'])

    def test_invalid_timestamp(self):
        for samples in ([(0,1),(0,2)],[(1,1),(0,2)],[(0.5,1)],[(3,1)],[(0,-1)]):
            self.assertIsNotNone(self.calc(2,samples)['reason'])

    def test_measured_zero_and_unknown_are_distinct(self):
        p=self.calc(100,[(i,0 if i==0 else 100) for i in range(100) if i not in range(50,60)])['points'][-1]
        self.assertEqual((p['observed_seconds'],p['unknown_seconds'],p['estimated_seconds'],p['sum_watts']),(90,10,0,8900))
        self.assertEqual(p['coverage'],.9)

    def test_small_independent_oracle(self):
        data=[100,None,300,50,None,None,120,90,80,40,80,60,20,30,40,0,10,50,60,70,80]
        samples=[(i,p) for i,p in enumerate(data) if p is not None]
        result=self.calc(len(data),samples,durations=range(1,10))
        for d in range(1,10):
            candidates=[]
            for start in range(len(data)-d+1):
                obs=total=0
                for j in range(start,start+d):
                    if data[j] is not None:obs+=1;total+=data[j]
                    elif j>0 and j+1<len(data) and data[j-1] is not None and data[j+1] is not None:total+=(data[j-1]+data[j+1])/2
                if obs and obs/d>=.90:candidates.append((total,start))
            actual=next((p for p in result['points'] if p['duration_seconds']==d),None)
            if not candidates:self.assertIsNone(actual)
            else:
                expected=max(candidates,key=lambda x:(x[0],-x[1]));self.assertEqual((actual['sum_watts'],actual['start_offset']),expected)

class ElapsedSourceAndCache(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from rideworks.store import Store
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'data');self.addCleanup(self.store.close)

    def api(self,identity,start,power,missing=()):
        from rideworks.strava_api import apply_observations, normalize
        from rideworks.strava_streams import persist
        def stream(data):return dict(data=data,original_size=len(data),resolution='high',series_type='time')
        offsets=[i for i in range(len(power)) if i not in missing]
        source=dict(id=identity,name='Synthetic',type='Ride',sport_type='VirtualRide',start_date=start.isoformat(),moving_time=len(power),elapsed_time=len(power),device_watts=True)
        apply_observations(self.store,[normalize(source)],999,int(start.timestamp()))
        persist(self.store,identity,dict(time=stream(offsets),watts=stream([power[i] for i in offsets])))
        return self.store.connection.execute('SELECT activity_id FROM strava_api_activities WHERE external_id=?',(str(identity),)).fetchone()[0]

    def test_fit_boundary_guard_validates_scope_and_preserves_offsets(self):
        from datetime import timedelta
        from unittest.mock import Mock
        from rideworks.elapsed_curve import native_candidate
        def run(offsets,duration,stop,timer, *, zero=False):
            def stamp(x):return (START+timedelta(seconds=x)).isoformat()
            records=[dict(timestamp=stamp(i),power=0 if zero and i==offsets[0] else 100) for i in offsets]
            native=dict(records=records,summary=dict(start_time=stamp(0),timestamp=stamp(duration),total_elapsed_time=duration,total_timer_time=timer),
                        events=[dict(event='timer',event_type='start',timestamp=stamp(0)),dict(event='timer',event_type='stop',timestamp=stamp(stop))])
            store=Mock();store.connection.execute.return_value.fetchone.return_value=(len(records),len(records));store.get_source.return_value=native
            meta=dict(source=dict(source_id='s',content_format='FIT'),extraction=dict(extraction_id='e',record_count=len(records),power_present=len(records)))
            return native_candidate(store,meta)
        clipped=run([i for i in range(10,110) if i!=50],1000,110,100,zero=True)
        self.assertEqual(clipped['scope_reason'],'fit_elapsed_bounds_not_supported')
        self.assertIsNone(clipped['duration_seconds'])
        self.assertEqual(clipped['grid_duration'],100)
        self.assertNotIn(100,clipped['anchors'])
        p=next(p for p in clipped['points'] if p['duration_seconds']==90)
        self.assertGreaterEqual(p['start_offset'],10)
        self.assertLessEqual(p['end_exclusive_offset'],110)
        self.assertEqual(p['source']['supported_end_offset'],110)
        full=run(list(range(10,190)),200,200,200)
        self.assertIsNone(full.get('scope_reason'))
        self.assertTrue(any(p['duration_seconds']==200 for p in full['points']))
        # A paired, verified timer that stops early does not corroborate the summary end.
        trailing=run(list(range(0,190)),200,190,190)
        self.assertEqual(trailing['scope_reason'],'fit_elapsed_bounds_not_supported')
        self.assertEqual(trailing['grid_duration'],190)
        self.assertEqual(run([0,1,1,2],1000,3,3)['reason'],'invalid_elapsed_timing')

    def test_rolling_calendar_periods_leap_and_winners(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        from rideworks.elapsed_curve import comparison,rebuild
        end=datetime(2024,2,29,12,tzinfo=timezone.utc)
        outside=self.api(71,datetime(2019,2,27,12,tzinfo=timezone.utc),[500]*60)
        five=self.api(72,datetime(2019,2,28,12,tzinfo=timezone.utc),[250]*60)
        two=self.api(73,datetime(2022,2,28,12,tzinfo=timezone.utc),[200]*60)
        current=self.api(74,end,[300]*60)
        rebuild(self.store)
        review=comparison(self.store,current)
        self.assertEqual(review['series']['two_year']['start'],'2022-02-28T12:00:00+00:00')
        self.assertEqual(review['series']['five_year']['start'],'2019-02-28T12:00:00+00:00')
        self.assertEqual(review['series']['two_year']['points'][0]['activity']['activity_id'],two)
        self.assertEqual(review['series']['five_year']['points'][0]['activity']['activity_id'],five)
        p=comparison(self.store,as_of=end,zone=ZoneInfo('UTC'))
        self.assertEqual(p['series']['five_year']['start'],'2019-02-28T12:00:00+00:00')
        self.assertEqual(p['series']['two_year']['points'][0]['activity']['activity_id'],two)
        self.assertEqual(p['series']['five_year']['points'][0]['activity']['activity_id'],five)
        self.assertEqual(p['series']['all']['points'][0]['activity']['activity_id'],outside)
        self.assertNotEqual(five,current)
        month_end=comparison(self.store,as_of=datetime(2024,3,31,12,tzinfo=timezone.utc))
        self.assertEqual(month_end['series']['two_year']['start'],'2022-03-31T12:00:00+00:00')
        west=comparison(self.store,as_of=datetime(2024,3,12,12,tzinfo=timezone.utc),zone=ZoneInfo('America/Los_Angeles'))
        self.assertEqual(west['series']['two_year']['start'],'2022-03-12T05:00:00-08:00')

    def test_cache_is_separate_and_excludes_off_grid_endpoint_from_history(self):
        from datetime import timedelta
        from rideworks.power_curve import rebuild_curves,curve_history
        from rideworks.elapsed_curve import comparison
        old=self.api(1,START,[100]*100,set(range(40,46)))
        new=self.api(2,START+timedelta(days=1),[200]*100)
        rebuild_curves(self.store)
        strict=curve_history(self.store)
        data=comparison(self.store,new)
        self.assertTrue(data['series']['ride']['points'])
        self.assertNotIn(100,[p['duration_seconds'] for p in data['series']['six']['points']])
        self.assertTrue(any(p['duration_seconds']==100 for p in comparison(self.store,old)['series']['ride']['points']))
        rebuild_curves(self.store,force=True)
        self.assertEqual(strict,curve_history(self.store))
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM elapsed_power_curve_profiles').fetchone()[0],2)

    def test_pending_stale_signature(self):
        from rideworks.elapsed_curve import comparison,rebuild
        old=self.api(3,START,[100]*100)
        rebuild(self.store)
        self.store.connection.execute("UPDATE elapsed_power_curve_profiles SET input_signature='stale'")
        p=comparison(self.store,old)
        self.assertEqual((p['pending'],p['current_reason']),(1,'profile_update_required'))
        self.assertFalse(p['series']['ride']['points'])

    def test_old_policy_cache_requires_rebuild(self):
        from rideworks.elapsed_curve import comparison,rebuild
        ride=self.api(8,START,[100]*100)
        rebuild(self.store)
        self.store.connection.execute("UPDATE elapsed_power_curve_profiles SET method='elapsed-power-v1'")
        before=comparison(self.store,ride)
        self.assertEqual(before['pending'],1)
        self.assertFalse(before['series']['ride']['points'])
        self.assertEqual(rebuild(self.store)['computed'],1)
        after=comparison(self.store,ride)
        self.assertEqual(after['pending'],0)
        self.assertTrue(after['series']['ride']['points'])

    def test_failed_rebuild_keeps_previous_and_retry_succeeds(self):
        from unittest.mock import patch
        from rideworks.elapsed_curve import rebuild
        self.api(7,START,[100]*100)
        rebuild(self.store)
        before=list(map(tuple,self.store.connection.execute('SELECT * FROM elapsed_power_curve_profiles')))
        with patch('rideworks.elapsed_curve.evaluate',side_effect=RuntimeError('synthetic interruption')):
            with self.assertRaises(RuntimeError):rebuild(self.store,force=True)
        self.assertEqual(before,list(map(tuple,self.store.connection.execute('SELECT * FROM elapsed_power_curve_profiles'))))
        self.assertEqual(rebuild(self.store,force=True)['computed'],1)

    def test_historical_boundary_and_ties(self):
        from datetime import timedelta
        from rideworks.elapsed_curve import comparison,rebuild
        self.api(11,START,[300]*60)
        inside=self.api(12,START+timedelta(days=1),[100]*60)
        current=self.api(13,START+timedelta(days=43),[200]*60)
        self.api(14,START+timedelta(days=43),[500]*60)
        rebuild(self.store)
        data=comparison(self.store,current)
        point=next(p for p in data['series']['six']['points'] if p['duration_seconds']==60)
        self.assertEqual(point['activity']['activity_id'],inside)
        self.assertEqual(point['rounded_watts'],100)

    def test_shared_period_results_and_strict_consumers(self):
        from datetime import timedelta
        from rideworks.elapsed_curve import comparison,rebuild
        from rideworks.power_curve import comparison as strict_comparison, curve_history
        old=self.api(31,START,[100]*120,{60})
        self.api(32,START+timedelta(hours=1),[100]*120,{60})
        later=self.api(33,START+timedelta(days=1),[50]*120)
        rebuild(self.store)
        strict_before=strict_comparison(self.store,as_of=START+timedelta(days=1))
        history_before=curve_history(self.store)
        review_before=comparison(self.store,later)
        performance=comparison(self.store,as_of=START+timedelta(days=1))
        for d in (20,90,120):
            activity_point=next(p for p in review_before['series']['six']['points'] if p['duration_seconds']==d)
            period_point=next(p for p in performance['series']['six']['points'] if p['duration_seconds']==d)
            self.assertEqual(activity_point,period_point)
            self.assertEqual(period_point['activity']['activity_id'],old)
        self.assertEqual(next(p for p in performance['series']['six']['points'] if p['duration_seconds']==120)['sum_watts'],12000)
        self.assertEqual(strict_before,strict_comparison(self.store,as_of=START+timedelta(days=1)))
        self.assertEqual(history_before,curve_history(self.store))
        self.assertEqual(review_before,comparison(self.store,later))

    def test_elapsed_period_excludes_off_grid_and_stale(self):
        from datetime import timedelta
        from rideworks.elapsed_curve import comparison,rebuild
        old=self.api(41,START,[300]*100,set(range(40,46)))
        self.api(42,START+timedelta(hours=1),[100]*101)
        rebuild(self.store)
        data=comparison(self.store,as_of=START+timedelta(days=1))
        points=data['series']['six']['points']
        self.assertFalse(any(p['duration_seconds'] in (100,101) for p in points))
        self.assertTrue(all(p['result_kind']=='elapsed_power' for p in points))
        self.store.connection.execute("UPDATE elapsed_power_curve_profiles SET input_signature='stale' WHERE activity_id=?",(old,))
        partial=comparison(self.store,as_of=START+timedelta(days=1))
        self.assertEqual(partial['pending'],1)
        self.assertTrue(partial['series']['six']['points'])
        self.assertTrue(all(p['rounded_watts']==100 for p in partial['series']['six']['points']))
        self.store.connection.execute("UPDATE elapsed_power_curve_profiles SET input_signature='stale'")
        pending=comparison(self.store,as_of=START+timedelta(days=1))
        self.assertEqual(pending['pending'],2)
        self.assertFalse(pending['series']['six']['points'])

    def test_elapsed_period_bounds_and_timezone(self):
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        from rideworks.elapsed_curve import comparison,rebuild
        asof=datetime(2026,1,1,6,tzinfo=timezone.utc)
        previous=self.api(51,asof-timedelta(days=84),[110]*60)
        six=self.api(52,asof-timedelta(days=42),[120]*60)
        self.api(53,asof,[999]*60)
        rebuild(self.store)
        west=comparison(self.store,as_of=asof,zone=ZoneInfo('America/Los_Angeles'))
        utc=comparison(self.store,as_of=asof)
        self.assertEqual(west['series']['six']['points'][0]['activity']['activity_id'],six)
        self.assertEqual(west['series']['previous']['points'][0]['activity']['activity_id'],previous)
        self.assertTrue(west['series']['ytd']['points'])
        self.assertFalse(utc['series']['ytd']['points'])

    def test_unrounded_winner_and_stable_ties(self):
        from datetime import timedelta
        from rideworks.elapsed_curve import envelope
        def profile(identity,when,value):
            return dict(activity=dict(activity_id=identity,start_time=when.isoformat(),absolute_time=True),duration_seconds=30,
                        points=[dict(duration_seconds=30,average_watts=value,rounded_watts=100)])
        profiles=[profile('z',START,100.1),profile('a',START,100.1),profile('later',START+timedelta(seconds=1),100.2)]
        end=START+timedelta(days=1)
        self.assertEqual(envelope(profiles,start=None,end=end)['points'][0]['activity']['activity_id'],'later')
        self.assertEqual(envelope(profiles[:2],start=None,end=end)['points'][0]['activity']['activity_id'],'a')

    def test_former_minimum_now_competes_at_common_anchor(self):
        from datetime import timedelta
        from rideworks.elapsed_curve import comparison,rebuild
        ride=self.api(61,START,[100]*120,set(range(50,62)))
        rebuild(self.store)
        p=next(p for p in comparison(self.store,as_of=START+timedelta(days=1))['series']['six']['points'] if p['duration_seconds']==120)
        self.assertEqual((p['activity']['activity_id'],p['rounded_watts'],p['coverage'],p['unknown_seconds']),(ride,90,.9,12))
        self.assertEqual(p['result_kind'],'elapsed_power')

    def test_competing_native_sources_fail_closed_and_block_api_fallback(self):
        from pathlib import Path
        from fit_fixture import make_fit
        from rideworks.elapsed_curve import evaluate
        api=self.api(21,START,[900]*60)
        for index,value in enumerate((100,200)):
            path=Path(self.temp.name)/('native'+str(index)+'.fit')
            t=1100000000
            path.write_bytes(make_fit(powers=[value]*60,heart_rates=[100]*60,timestamps=range(t,t+60),
                             max_hr=150+index,elapsed=59,timer=59,event_timestamps=(t,t+59),
                             session_timestamp=t+59,session_start_time=t))
            self.store.import_file(path,activity_id=api)
        result=evaluate(self.store,self.store.activity_history(api)[0])
        self.assertFalse(result['points'])
        self.assertIn(30,result['ambiguous_durations'])
        self.assertIsNone(result['minimum'])
