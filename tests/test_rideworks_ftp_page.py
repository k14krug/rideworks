"""Synthetic FTP comparison and form security; no default or personal store."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from rideworks.store import Store
from rideworks.web import Application
from rideworks.ftp_page import comparison
from rideworks.ftp_history import snapshot
from rideworks.ftp_history import add_entry
from rideworks.performance import rebuild_performance
from rideworks.training_state import calculate_ride, ftp_on, ride_results, training_state
from rideworks.planning import plan
from rideworks.history import presentation
from ftp_fixture import seed_ftp
from fit_fixture import make_fit


class FTPPageTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.target = Path(temp.name)/'store'
        self.app = Application(self.target)
        self.app.settings.port = 8765

    def seed(self):
        with Store(self.target) as store:
            seed_ftp(store,[('2020-01-01',190),('2020-06-01',250),('2020-12-31',220)])

    def submit(self, **changes):
        values = dict(nonce=self.app.settings.nonce, revision='0', date='2020-03-01', watts='210')
        values.update(changes)
        return self.app.post('/performance/ftp/add',urlencode(values).encode(),'http://127.0.0.1:8765')

    def test_empty_page_valid_and_manual_form_present(self):
        status,kind,body=self.app.get('/performance/ftp')
        self.assertEqual(status,200);self.assertEqual(kind,'text/html')
        self.assertIn(b'"rows":[]',body)
        self.assertIn(b'id="ftp-add"',body)
        self.assertIn(b'America/Los_Angeles',body)
        self.assertEqual(self.submit()[0],400)
        with Store(self.target) as store:self.assertEqual(snapshot(store)['rows'],[])

    def test_rounding_exact_comparison_calendar_and_uncertain_boundaries(self):
        self.seed()
        def point(i, raw, stamp='2020-03-02T00:30:00+00:00', absolute=True, day='2020-03-02'):
            return dict(activity_id=str(i),title='Synthetic',average_watts=raw,start_time=stamp,absolute_time=absolute,date_day=day)
        evidence=dict(points=[point(1,200),point(2,200.01),point(3,190),point(4,270,absolute=False,day='2020-06-01'),point(5,270,absolute=False,day='2019-12-20'),point(6,270,absolute=False,day='2020-03-02')],pending=2,missing_dates=1)
        with Store(self.target) as store, patch('rideworks.ftp_page.performance_history',return_value=evidence):
            result=comparison(store)
        a,b,c,d,e,f=result['points']
        self.assertEqual(a['date'],'2020-03-01');self.assertEqual(a['category'],'below')
        self.assertEqual(b['category'],'above');self.assertEqual(b['watts'],.95*200.01)
        self.assertEqual(c['watts'],180.5);self.assertEqual(c['proposed'],181)
        self.assertEqual(d['category'],'unavailable');self.assertEqual(d['ftp']['status'],'date_uncertain')
        self.assertEqual(e['category'],'unavailable');self.assertEqual(f['category'],'above')
        self.assertEqual(result['pending'],2)

    def test_save_stale_collision_and_security_preserve_history(self):
        self.seed()
        with Store(self.target) as store: before=snapshot(store)
        revision=str(before['revision'])
        self.assertEqual(self.submit(revision=revision,nonce='bad')[0],403)
        body=urlencode(dict(nonce=self.app.settings.nonce,revision=revision,date='2020-03-01',watts='210')).encode()
        self.assertEqual(self.app.post('/performance/ftp/add',body,'https://evil.example')[0],403)
        self.assertEqual(self.submit(revision=revision)[0],303)
        with Store(self.target) as store: after=snapshot(store)
        self.assertEqual(len(after['rows']),4)
        status,headers,error=self.submit(revision=revision,date='2020-04-01')
        self.assertEqual(status,400);self.assertIn('text/html',headers['Content-Type']);self.assertIn(b'changed',error)
        self.assertIn(b'2020-04-01',error)
        self.assertEqual(self.submit(revision=str(after['revision']))[0],400)
        for value in ['1.5','0','-1','NaN','99999999999999999999']:
            self.assertEqual(self.submit(revision=str(after['revision']),date='2020-04-01',watts=value)[0],400)
        with Store(self.target) as store:self.assertEqual(snapshot(store),after)
        self.assertIn(b'210',self.app.get('/performance/ftp')[2])

    def test_manual_new_latest_via_secure_form_without_qualifying_ride(self):
        self.seed()
        with Store(self.target) as store:
            before=snapshot(store)
            self.assertEqual(ftp_on(before['rows'],'2021-01-15')['value'],220)
        # The form posts a manual value; no performance result or test ride is required.
        status,headers,body=self.submit(revision=str(before['revision']),
                                        date='2021-02-01',watts='160')
        self.assertEqual(status,303)
        self.assertEqual(headers['Location'],'/performance/ftp')
        with Store(self.target) as store:
            after=snapshot(store)
            self.assertEqual(after['revision'],before['revision']+1)
            self.assertNotEqual(after['signature'],before['signature'])
            self.assertEqual(len(after['rows']),len(before['rows'])+1)
            self.assertEqual(ftp_on(after['rows'],'2021-01-31')['value'],220)
            self.assertEqual(ftp_on(after['rows'],'2021-02-01')['value'],160)
            self.assertEqual(ftp_on(after['rows'],'2026-10-27')['value'],160)
            self.assertIsNone(after['rows'][-1]['effective_until_date_exclusive'])
            self.assertEqual(after['rows'][:-2],before['rows'][:-1])
        status,kind,page=self.app.get('/performance/ftp')
        self.assertEqual(status,200)
        self.assertIn(b'2021-02-01',page)
        self.assertIn(b'160',page)
        self.assertIn(b'Add an FTP value',page)
        self.assertEqual(self.submit(revision=str(after['revision']),
                                     date='2021-02-01',watts='180')[0],400)
        self.assertEqual(self.submit(revision=str(before['revision']),
                                     date='2021-03-01',watts='150')[0],400)
        with Store(self.target) as store:self.assertEqual(snapshot(store),after)

    def test_new_latest_ftp_reclassifies_ride_and_recalculates_training_state_and_plan(self):
        as_of=datetime(2024,11,10,12,tzinfo=timezone.utc)
        start=int(datetime(2024,11,8,11,33,20,tzinfo=timezone.utc).timestamp())
        with Store(self.target) as store:
            seed_ftp(store,[('2024-11-01',200),('2024-11-07',200)])
            seed_path=self.target.parent/'after-last.fit'
            seed_path.write_bytes(make_fit(powers=[200]*1200,heart_rates=[143]*1200,
                timestamps=range(start,start+1200),elapsed=1200,timer=1200,
                event_timestamps=(start,start+1200),session_timestamp=start+1200))
            store.import_fit(seed_path)
            rebuild_performance(store)
            activity_id=presentation(store.activity_history()[0])['activity_id']
            previous=snapshot(store)
            before_state=training_state(store,'America/Los_Angeles',as_of=as_of)
            before_plan=plan(store,'America/Los_Angeles',as_of=as_of)
            before_comparison=next(p for p in comparison(store)['points'] if p['activity_id']==activity_id)
            before_ride=next(r for day in before_state['days'] for r in day['rides']
                             if r['activity_id']==activity_id)
            before_cache=store.connection.execute(
                'SELECT input_signature FROM training_stress_cache WHERE activity_id=?',
                (activity_id,)).fetchone()['input_signature']
            self.assertEqual(before_comparison['category'],'below')
            self.assertEqual(before_plan['history'][0]['ftp']['value'],200)
            self.assertEqual(before_ride['ftp']['value'],200)

            updated=add_entry(store,'2024-11-08',160,expected_revision=previous['revision'])
            self.assertEqual(ftp_on(updated['rows'],'2024-11-07')['value'],200)
            self.assertEqual(ftp_on(updated['rows'],'2024-11-08')['value'],160)
            self.assertEqual(updated['rows'][-1]['effective_until_date_exclusive'],None)
            after_state=training_state(store,'America/Los_Angeles',as_of=as_of)
            after_plan=plan(store,'America/Los_Angeles',as_of=as_of)
            after_comparison=next(p for p in comparison(store)['points'] if p['activity_id']==activity_id)
            after_ride=next(r for day in after_state['days'] for r in day['rides']
                            if r['activity_id']==activity_id)
            after_cache=store.connection.execute(
                'SELECT input_signature FROM training_stress_cache WHERE activity_id=?',
                (activity_id,)).fetchone()['input_signature']
            self.assertEqual(after_comparison['category'],'above')
            self.assertEqual(after_plan['history'][0]['ftp']['value'],160)
            self.assertEqual(after_ride['ftp']['value'],160)
            self.assertNotEqual(before_cache,after_cache)
            self.assertGreater(after_ride['selected']['stress'],before_ride['selected']['stress'])

    def test_reading_page_and_concurrent_ftp_write_keep_snapshot_without_locking_writer(self):
        self.seed()
        entered,release=Event(),Event()
        original=dict(points=[],pending=0,missing_dates=0)
        def slow_performance(_store):
            entered.set()
            self.assertTrue(release.wait(5),'test release timed out')
            return original
        result=[]
        with patch('rideworks.ftp_page.performance_history',side_effect=slow_performance):
            thread=Thread(target=lambda:result.append(self.app.get('/performance/ftp')))
            thread.start()
            self.assertTrue(entered.wait(2),'GET did not reach its long calculation')
            with Store(self.target) as writer:
                writer.connection.execute('PRAGMA busy_timeout=200')
                before=snapshot(writer)
                changed=add_entry(writer,'2020-03-01',205,expected_revision=before['revision'])
            release.set();thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0][0],200)
        # The in-flight page stays on its original read snapshot while the
        # concurrent writer commits; a later request observes the new entry.
        self.assertIn(b'2020-01-01',result[0][2])
        self.assertNotIn(b'2020-03-01',result[0][2])
        with Store(self.target) as reader:
            self.assertEqual(snapshot(reader),changed)
            self.assertEqual(reader.connection.execute('PRAGMA journal_mode').fetchone()[0],'wal')

    def test_cold_multiride_get_batches_cache_writes_before_concurrent_history_change(self):
        seed_paths=[]
        with Store(self.target) as store:
            seed_ftp(store,[('2000-01-01',200),('2030-01-01',200)])
            for index,start in enumerate((1100000000,1100086400)):
                seed_path=self.target.parent/f'synthetic-{index}.fit'
                seed_path.write_bytes(make_fit(powers=[200+index]*1200,heart_rates=[143]*1200,
                    timestamps=range(start,start+1200),elapsed=1200,timer=1200,
                    event_timestamps=(start,start+1200),session_timestamp=start+1200))
                seed_paths.append(seed_path)
                store.import_fit(seed_path)
            rebuild_performance(store)
        app=Application(self.target);entered,release=Event(),Event();calls=[];result=[];failures=[]
        from rideworks.training_state import calculate_ride as calculate
        def pause_after_calculation(*args,**kwargs):
            value=calculate(*args,**kwargs);calls.append(1)
            if len(calls)==2:
                entered.set()
                if not release.wait(5):raise AssertionError('test release timed out')
            return value
        def load():
            try:result.append(app.get('/training-state?tz=America%2FLos_Angeles'))
            except Exception as exc:failures.append(exc)
        started=__import__('time').perf_counter()
        with patch('rideworks.training_state.calculate_ride',side_effect=pause_after_calculation):
            thread=Thread(target=load);thread.start()
            self.assertTrue(entered.wait(5),'cold page did not finish the second ride calculation')
            with Store(self.target) as reader:
                # The first ride's calculation has finished, but deferred
                # writes mean no partial cache batch has acquired WAL's writer slot.
                self.assertEqual(reader.connection.execute('SELECT COUNT(*) FROM training_stress_cache').fetchone()[0],0)
            with Store(self.target) as writer:
                before=snapshot(writer)
                writer_started=__import__('time').perf_counter()
                updated=add_entry(writer,'2003-01-01',250,expected_revision=before['revision'])
                writer_elapsed=__import__('time').perf_counter()-writer_started
            release.set();thread.join(10)
        elapsed=__import__('time').perf_counter()-started
        self.assertFalse(thread.is_alive());self.assertEqual(failures,[])
        self.assertEqual(result[0][0],200);self.assertGreaterEqual(len(calls),2)
        self.assertEqual(updated['rows'][1]['ftp_watts'],250)
        body=result[0][2]
        self.assertIn(b'250',body)
        self.assertLess(elapsed,10)
        self.assertGreaterEqual(len(calls),4,'stale snapshot is discarded and both rides recalculate after retry')
        with Store(self.target) as store:
            cached=store.connection.execute('SELECT input_signature,result_json FROM training_stress_cache ORDER BY activity_id').fetchall()
            self.assertEqual(len(cached),2)
            self.assertTrue(all(r['input_signature'] and __import__('json').loads(r['result_json'])['ftp']['value']==250 for r in cached))
        self.concurrency_metrics={'cold_get_seconds':round(elapsed,4),
            'concurrent_ftp_write_seconds':round(writer_elapsed,4),
            'calculation_attempts':len(calls)}

    def test_plan_get_defers_training_and_classification_cache_batches(self):
        with Store(self.target) as store:
            seed_ftp(store,[('2000-01-01',200),('2030-01-01',200)])
            for index,start in enumerate((1100000000,1100086400)):
                seed_path=self.target.parent/f'plan-{index}.fit'
                seed_path.write_bytes(make_fit(powers=[200+index]*1200,heart_rates=[143]*1200,
                    timestamps=range(start,start+1200),elapsed=1200,timer=1200,
                    event_timestamps=(start,start+1200),session_timestamp=start+1200))
                store.import_fit(seed_path)
            rebuild_performance(store)
        app=Application(self.target);entered,release=Event(),Event();calls=[];result=[];failures=[]
        from rideworks.planning import classify_activity as classify
        def pause_second_classification(*args,**kwargs):
            value=classify(*args,**kwargs);calls.append(1)
            if len(calls)==2:
                entered.set()
                if not release.wait(5):raise AssertionError('test release timed out')
            return value
        def load():
            try:result.append(app.get('/plan?plan_tz=America%2FLos_Angeles'))
            except Exception as exc:failures.append(exc)
        started=__import__('time').perf_counter()
        with patch('rideworks.planning.classify_activity',side_effect=pause_second_classification):
            thread=Thread(target=load);thread.start()
            self.assertTrue(entered.wait(5),'Plan did not reach its second classification calculation')
            with Store(self.target) as reader:
                self.assertEqual(reader.connection.execute('SELECT COUNT(*) FROM training_stress_cache').fetchone()[0],0)
                self.assertEqual(reader.connection.execute('SELECT COUNT(*) FROM planning_classification_cache').fetchone()[0],0)
            with Store(self.target) as writer:
                before=snapshot(writer)
                write_started=__import__('time').perf_counter()
                updated=add_entry(writer,'2003-01-01',250,expected_revision=before['revision'])
                write_elapsed=__import__('time').perf_counter()-write_started
            release.set();thread.join(10)
        elapsed=__import__('time').perf_counter()-started
        self.assertFalse(thread.is_alive());self.assertEqual(failures,[])
        self.assertEqual(result[0][0],200)
        self.assertLess(write_elapsed,1,'normal FTP write commits while Plan calculates rides')
        self.assertGreaterEqual(len(calls),4,'stale Plan snapshot is retried after cache-batch upgrade')
        with Store(self.target) as store:
            stress=store.connection.execute('SELECT input_signature,result_json FROM training_stress_cache ORDER BY activity_id').fetchall()
            classifications=store.connection.execute('SELECT input_signature,result_json FROM planning_classification_cache ORDER BY activity_id').fetchall()
            self.assertEqual(len(stress),2);self.assertEqual(len(classifications),2)
            self.assertTrue(all(r['input_signature'] and __import__('json').loads(r['result_json'])['ftp']['value']==250 for r in stress))
            self.assertTrue(all(r['input_signature'] for r in classifications))
        self.planning_metrics={'cold_plan_get_seconds':round(elapsed,4),
            'concurrent_ftp_write_seconds':round(write_elapsed,4),
            'classification_attempts':len(calls)}

    def test_home_get_finishes_plan_batch_before_training_summary_and_allows_ftp_write(self):
        self._home_get_allows_ftp_write(invalidated=False)

    def test_home_get_allows_ftp_write_after_existing_stress_and_plan_caches_are_invalidated(self):
        self._home_get_allows_ftp_write(invalidated=True)

    def test_home_get_allows_ftp_write_during_post_plan_relative_effort_with_cold_caches(self):
        self._home_get_allows_ftp_write(invalidated=False,pause_stage='relative_effort')

    def test_home_get_allows_ftp_write_during_post_plan_relative_effort_with_invalidated_caches(self):
        self._home_get_allows_ftp_write(invalidated=True,pause_stage='relative_effort')

    def test_home_get_allows_ftp_write_after_response_render_with_cold_caches(self):
        self._home_get_allows_ftp_write(invalidated=False,pause_stage='response')

    def test_home_get_allows_ftp_write_after_response_render_with_invalidated_caches(self):
        self._home_get_allows_ftp_write(invalidated=True,pause_stage='response')

    def test_pending_stress_results_reuse_requires_current_ftp_signature(self):
        with Store(self.target) as store:
            seed_ftp(store,[('2000-01-01',200),('2030-01-01',200)])
            start=1100000000
            source=self.target.parent/'pending.fit'
            source.write_bytes(make_fit(powers=[200]*1200,heart_rates=[143]*1200,
                timestamps=range(start,start+1200),elapsed=1200,timer=1200,
                event_timestamps=(start,start+1200),session_timestamp=start+1200))
            store.import_fit(source)
            pending=[]
            with patch('rideworks.training_state.calculate_ride',wraps=calculate_ride) as score:
                first,_=ride_results(store,'America/Los_Angeles',cache_writes=pending)
                self.assertEqual(score.call_count,1)
                reused,context=ride_results(store,'Asia/Tokyo',cache_writes=pending)
                self.assertEqual(score.call_count,1,'same signature reuses pending stress without recalculation')
                self.assertEqual(reused[0]['selected'],first[0]['selected'])
                stamp=presentation(store.activity_history()[0])['start_time']
                self.assertEqual(reused[0]['day'],datetime.fromisoformat(stamp).astimezone(ZoneInfo('Asia/Tokyo')).date().isoformat())
                self.assertEqual(context['timezone'],'Asia/Tokyo')
                before=snapshot(store)
                add_entry(store,'2003-01-01',250,expected_revision=before['revision'])
                updated,_=ride_results(store,'America/Los_Angeles',cache_writes=pending)
                self.assertEqual(score.call_count,2,'changed FTP invalidates a pending result too')
                self.assertEqual(first[0]['ftp']['value'],200)
                self.assertEqual(updated[0]['ftp']['value'],250)
            self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM training_stress_cache').fetchone()[0],0,
                             'all three scans leave cache writes deferred')

    def _home_get_allows_ftp_write(self, *, invalidated, pause_stage='classification'):
        with Store(self.target) as store:
            seed_ftp(store,[('2000-01-01',200),('2030-01-01',200)])
            for index,start in enumerate((1100000000,1100086400)):
                seed_path=self.target.parent/f'home-{index}.fit'
                seed_path.write_bytes(make_fit(powers=[200+index]*1200,heart_rates=[143]*1200,
                    timestamps=range(start,start+1200),elapsed=1200,timer=1200,
                    event_timestamps=(start,start+1200),session_timestamp=start+1200))
                store.import_fit(seed_path)
            rebuild_performance(store)
            if invalidated:
                plan(store,'America/Los_Angeles')
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM training_stress_cache').fetchone()[0],2)
                self.assertEqual(store.connection.execute('SELECT COUNT(*) FROM planning_classification_cache').fetchone()[0],2)
                # A changed timeline signature invalidates both existing cache
                # sets even when the extra historical setting has equal watts.
                before=snapshot(store)
                add_entry(store,'2001-01-01',200,expected_revision=before['revision'])
        app=Application(self.target);entered,release=Event(),Event();calls=[];result=[];failures=[]
        from rideworks.planning import classify_activity as classify
        from rideworks.relative_effort import for_store as rate_effort
        render_page=app.page
        def pause():
            entered.set()
            if not release.wait(5):raise AssertionError('test release timed out')
        def pause_second_classification(*args,**kwargs):
            value=classify(*args,**kwargs);calls.append(1)
            if pause_stage=='classification' and len(calls)==2:
                pause()
            return value
        def pause_relative_effort(*args,**kwargs):
            value=rate_effort(*args,**kwargs)
            if pause_stage=='relative_effort' and not entered.is_set():
                self.assertEqual(len(calls),2,'Relative Effort runs after Plan classifications')
                pause()
            return value
        def pause_response(*args,**kwargs):
            value=render_page(*args,**kwargs)
            if pause_stage=='response' and not entered.is_set():
                self.assertEqual(len(calls),2,'response is built after Plan classifications')
                pause()
            return value
        def load():
            try:result.append(app.get('/'))
            except Exception as exc:failures.append(exc)
        started=__import__('time').perf_counter()
        with patch('rideworks.planning.classify_activity',side_effect=pause_second_classification), \
             patch('rideworks.relative_effort.for_store',side_effect=pause_relative_effort), \
             patch.object(app,'page',side_effect=pause_response), \
             patch('rideworks.training_state.calculate_ride',wraps=calculate_ride) as score:
            thread=Thread(target=load);thread.start()
            def finish():
                release.set();thread.join(10)
            self.addCleanup(finish)
            self.assertTrue(entered.wait(5),'Home did not reach the '+pause_stage+' calculation')
            with Store(self.target) as reader:
                self.assertEqual(reader.connection.execute('SELECT COUNT(*) FROM training_stress_cache').fetchone()[0],2 if invalidated else 0)
                self.assertEqual(reader.connection.execute('SELECT COUNT(*) FROM planning_classification_cache').fetchone()[0],2 if invalidated else 0)
            with Store(self.target) as writer:
                writer.connection.execute('PRAGMA busy_timeout=200')
                before=snapshot(writer)
                write_started=__import__('time').perf_counter()
                updated=add_entry(writer,'2003-01-01',250,expected_revision=before['revision'])
                write_elapsed=__import__('time').perf_counter()-write_started
            release.set();thread.join(10)
            self.assertEqual(score.call_count,4,'each ride is scored once per coherent attempt, including the retry')
        elapsed=__import__('time').perf_counter()-started
        self.assertFalse(thread.is_alive());self.assertEqual(failures,[])
        self.assertEqual(result[0][0],200)
        self.assertLess(write_elapsed,1,'FTP write commits during Home '+pause_stage)
        self.assertGreaterEqual(len(calls),4,'stale Home snapshot is retried after cache-batch upgrade')
        with Store(self.target) as store:
            stress=store.connection.execute('SELECT input_signature,result_json FROM training_stress_cache ORDER BY activity_id').fetchall()
            classifications=store.connection.execute('SELECT input_signature,result_json FROM planning_classification_cache ORDER BY activity_id').fetchall()
            self.assertEqual(len(stress),2);self.assertEqual(len(classifications),2)
            self.assertTrue(all(r['input_signature'] and __import__('json').loads(r['result_json'])['ftp']['value']==250 for r in stress))
            self.assertTrue(all(r['input_signature'] for r in classifications))
        self.home_metrics={'cold_home_get_seconds':round(elapsed,4),
            'concurrent_ftp_write_seconds':round(write_elapsed,4),
            'classification_attempts':len(calls)}

    def test_new_earliest_ftp_rebuilds_stress_and_planning_from_prehistory_ride(self):
        as_of=datetime(2024,11,10,12,tzinfo=timezone.utc)
        start=int(datetime(2024,11,8,11,33,20,tzinfo=timezone.utc).timestamp())
        with Store(self.target) as store:
            seed_ftp(store,[('2024-11-09',200),('2030-01-01',200)])
            seed_path=self.target.parent/'prehistory.fit'
            seed_path.write_bytes(make_fit(powers=[200]*1200,heart_rates=[143]*1200,
                timestamps=range(start,start+1200),elapsed=1200,timer=1200,
                event_timestamps=(start,start+1200),session_timestamp=start+1200))
            store.import_fit(seed_path)
            rebuild_performance(store)
            original=snapshot(store)['rows']
            activity_id=presentation(store.activity_history()[0])['activity_id']
            before_state=training_state(store,'America/Los_Angeles',as_of=as_of)
            before_day=next(day for day in before_state['days'] if any(r['activity_id']==activity_id for r in day['rides']))
            before_ride=next(r for r in before_day['rides'] if r['activity_id']==activity_id)
            before_comparison=next(p for p in comparison(store)['points'] if p['activity_id']==activity_id)
            self.assertEqual(before_comparison['category'],'unavailable')
            before_plan=plan(store,'America/Los_Angeles',as_of=as_of)
            self.assertEqual(len(before_plan['history']),1)
            self.assertEqual(before_plan['history'][0]['ftp']['status'],'unknown_prehistory')
            before_stress=store.connection.execute('SELECT input_signature,result_json FROM training_stress_cache WHERE activity_id=?',(activity_id,)).fetchone()
            before_class=store.connection.execute('SELECT input_signature,result_json FROM planning_classification_cache WHERE activity_id=?',(activity_id,)).fetchone()
            self.assertIsNotNone(before_stress);self.assertIsNotNone(before_class)
            before_result=__import__('json').loads(before_stress['result_json'])
            self.assertEqual(before_result['power']['reason'],'ftp_unavailable')
            after_history=add_entry(store,'2024-11-08',190,expected_revision=snapshot(store)['revision'])
            self.assertEqual(ftp_on(after_history['rows'],'2024-11-07')['status'],'unknown_prehistory')
            self.assertEqual(ftp_on(after_history['rows'],'2024-11-08')['value'],190)
            for row in original:self.assertIn(row,after_history['rows'])
            after_state=training_state(store,'America/Los_Angeles',as_of=as_of)
            after_day=next(day for day in after_state['days'] if any(r['activity_id']==activity_id for r in day['rides']))
            after_plan=plan(store,'America/Los_Angeles',as_of=as_of)
            after_ride=next(r for r in after_day['rides'] if r['activity_id']==activity_id)
            after_comparison=next(p for p in comparison(store)['points'] if p['activity_id']==activity_id)
            self.assertEqual(after_comparison['category'],'below')
            self.assertEqual(after_comparison['watts'],190)
            self.assertEqual(after_ride['ftp']['value'],190)
            self.assertEqual(after_ride['selected']['status'],'calculated')
            self.assertEqual(after_ride['selected']['method'],'power')
            self.assertGreater(after_ride['selected']['stress'],0)
            self.assertEqual(after_day['day'],'2024-11-08')
            self.assertNotEqual(before_ride['selected']['method'],after_ride['selected']['method'])
            self.assertNotEqual(before_ride['selected']['stress'],after_ride['selected']['stress'])
            self.assertNotEqual((before_day['stress'],before_day['fitness'],before_day['fatigue']),
                                (after_day['stress'],after_day['fitness'],after_day['fatigue']))
            self.assertEqual(after_plan['history'][0]['ftp']['value'],190)
            after_stress=store.connection.execute('SELECT input_signature,result_json FROM training_stress_cache WHERE activity_id=?',(activity_id,)).fetchone()
            after_class=store.connection.execute('SELECT input_signature,result_json FROM planning_classification_cache WHERE activity_id=?',(activity_id,)).fetchone()
            self.assertNotEqual(before_stress['input_signature'],after_stress['input_signature'])
            self.assertNotEqual(before_class['input_signature'],after_class['input_signature'])
            self.assertEqual(__import__('json').loads(after_stress['result_json'])['ftp']['value'],190)
