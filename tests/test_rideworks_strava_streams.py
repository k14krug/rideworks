"""Synthetic Stage A stream access/comparison. No automated calls to Strava."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import test_rideworks_strava as fixture
from rideworks.strava import (ApiClient, ApiError, AuthenticationError, MAX_JSON, MAX_STREAM_JSON,
                              STREAM_KEYS, TokenFile, refreshed_connection)
from rideworks.strava_api import SyncError
from rideworks.strava_streams import parse_streams, review_best20

spec=importlib.util.spec_from_file_location('stream_comparison',Path(__file__).resolve().parents[1]/'tools/compare_rideworks_strava_streams.py')
comparison=importlib.util.module_from_spec(spec);spec.loader.exec_module(comparison)


def stream(data,**metadata):
    return dict(data=data,original_size=len(data),resolution='high',series_type='time')|metadata


class StreamTests(unittest.TestCase):
    def test_endpoint_keys_finite_timeout_bearer_and_dedicated_payload_limit(self):
        http=fixture.FakeHTTP(fixture.Response({'time':stream([0,1]),'watts':stream([0,120])}))
        client=ApiClient(fixture.CREDS,opener=http)
        client.streams('fake-stream-access','123')
        request=http.requests[0];url=urlsplit(request.full_url)
        self.assertEqual(url.scheme,'https');self.assertEqual(url.hostname,'www.strava.com')
        self.assertEqual(url.path,'/api/v3/activities/123/streams')
        self.assertEqual(parse_qs(url.query),dict(keys=[','.join(STREAM_KEYS)],key_by_type=['true']))
        self.assertEqual(request.get_header('Authorization'),'Bearer fake-stream-access')
        self.assertNotIn('fake-stream-access',request.full_url)
        for identity in (0,-1,True,'1/../../athlete','https://untrusted.example','1?keys=latlng'):
            with self.subTest(identity=identity),self.assertRaises(SyncError):client.streams('fake',identity)
        with self.assertRaises(SyncError):client.request('POST','https://www.strava.com/api/v3/activities/123/streams')
        payload={'time':stream([0])};payload['time']['unused']='x'*MAX_JSON
        http.responses.append(fixture.Response(payload));self.assertIn('time',client.streams('fake',123))
        http.responses.append(fixture.Response(b'x'*(MAX_STREAM_JSON+1)))
        with self.assertRaises(SyncError):client.streams('fake',123)

    def test_metadata_missing_optional_allowlist_zeros_nulls_and_original_values(self):
        for resolution in ('low','medium','high'):
            payload={'time':stream([0,2,7]),'watts':stream([0,None,100]),'moving':stream([False,True,None]),
                     'latlng':{'data':[[1,2]]}}
            payload['watts'].update(resolution=resolution,series_type='distance',original_size=10)
            result=parse_streams(payload)
            self.assertNotIn('latlng',result);self.assertNotIn('heartrate',result)
            self.assertEqual(result['watts'],payload['watts']);self.assertEqual(result['time']['data'],[0,2,7])
            self.assertEqual(result['moving']['data'],[False,True,None])

    def test_malformed_stream_shapes_and_nonfinite_values_fail_without_payload_echo(self):
        for payload in ([],{'time':None},{'time':stream([True])},{'time':stream([None])},
                        {'watts':stream([float('nan')])},{'heartrate':stream([float('inf')])},
                        {'cadence':stream([-1])},{'moving':stream([1])},{'watts':stream([2**53])},
                        {'time':dict(data=[0],original_size=True,resolution='high',series_type='time')},
                        {'time':dict(data=[0],original_size=1,resolution='invented',series_type='time')},
                        {'time':dict(data=[0],original_size=1,resolution='high',series_type='invented')},
                        {'time':dict(data=[0],original_size=1,resolution='high',series_type='time',type='private-secret')}):
            with self.subTest(payload=payload),self.assertRaises(SyncError) as error:parse_streams(payload)
            self.assertNotIn('private-secret',str(error.exception))

    def test_timing_reports_gaps_duplicates_backward_without_repair(self):
        self.assertEqual(comparison.timing([0,1,1,0,4])['delta_distribution'],{'-1':1,'0':1,'1':1,'4':1})
        self.assertEqual(comparison.timing([0,1,1,0,4])['gap_count'],1)
        self.assertEqual(parse_streams({'time':stream([0,1,1,0,4])})['time']['data'],[0,1,1,0,4])

    def test_independent_best20_complete_windows_zero_missing_gaps_and_earliest_ties(self):
        offsets=list(range(1201));values=[120]*1201
        best=comparison.independent_best(offsets,values)
        self.assertEqual((best['average_watts'],best['rounded_watts'],best['start_elapsed'],best['eligible_window_count']),(120,120,0,2))
        self.assertEqual(comparison.independent_best(list(range(1200)),[0]*1200)['average_watts'],0)
        self.assertIsNone(comparison.independent_best(list(range(1200)),[120]*1199+[None]))
        self.assertIsNone(comparison.independent_best(list(range(1199))+[1200],[120]*1200))
        self.assertIsNone(comparison.independent_best(list(range(0,2400,2)),[120]*1200))
        self.assertIsNone(comparison.independent_best([0],[120,120]))
        best=comparison.independent_best(list(range(1200)),[120]*600+[121]*600)
        self.assertEqual(best['rounded_watts'],121)

    def test_exact_timestamp_pairing_excludes_ambiguous_timestamps_and_counts_missing_zeros(self):
        origin=datetime(2024,1,1,tzinfo=timezone.utc)
        times=[origin+timedelta(seconds=i) for i in range(5)]
        result=comparison.signal_comparison(times,[0,100,None,50,101],times,[0,100,20,None,100])
        self.assertEqual(result['timestamp_pairs'],5);self.assertEqual(result['exact_matches'],2)
        self.assertEqual(result['missing_pattern_differences'],2);self.assertEqual(result['paired_both_zero'],1)
        self.assertEqual(result['first_mismatches'][0]['difference'],1)
        duplicate=comparison.signal_comparison([times[0],times[0]],[1,2],times,[0]*5)
        self.assertEqual(duplicate['timestamp_pairs'],0)
        duplicate=comparison.signal_comparison(times,[0]*5,[times[0],times[0]],[0,0])
        self.assertEqual(duplicate['timestamp_pairs'],0)

    def test_alignment_never_fits_a_shift_and_experimental_results_do_not_enroll_performance(self):
        origin=datetime(2024,1,1,tzinfo=timezone.utc)
        evidence=dict(summary={'start_time':origin.isoformat()},records=[dict(timestamp=(origin+timedelta(seconds=i)).isoformat(),power=120,heart_rate=100) for i in range(1200)])
        streams=parse_streams(dict(time=stream(list(range(1200))),watts=stream([120]*1200),heartrate=stream([100]*1200),cadence=stream([0]*1200)))
        exact=comparison.compare(streams,evidence,origin)
        self.assertEqual(exact['evidence_review_reasons'],[])
        self.assertEqual(exact['experimental_best20']['raw_difference_watts'],0)
        self.assertFalse(exact['experimental_best20']['trusted_performance_enrollment'])
        self.assertIn('not_comparable',exact['signals']['cadence']['status'])
        shifted=comparison.compare(streams,evidence,origin+timedelta(seconds=1))
        self.assertEqual(shifted['signals']['watts']['timestamp_pairs'],1199)
        self.assertTrue(shifted['evidence_review_reasons'])
        streams['watts']['data']=[120]*100
        result=comparison.compare(streams,evidence,origin)
        self.assertEqual(result['signals']['watts']['status'],'length_mismatch_not_paired')

    def test_stream_rate_limit_401_and_response_redirect_safety(self):
        for status in (401,429,302):
            http=fixture.FakeHTTP(HTTPError('https://www.strava.com/',status,'private-fake-token',{},None))
            client=ApiClient(fixture.CREDS,opener=http)
            with self.assertRaises(SyncError) as error:client.streams('fake',123)
            self.assertNotIn('private-fake-token',str(error.exception));self.assertEqual(len(http.requests),1)
        client.rate={'X-ReadRateLimit-Limit':[100,1000],'X-ReadRateLimit-Usage':[100,100]}
        with self.assertRaises(ApiError):client.streams('fake',123)
        self.assertEqual(len(http.requests),1)


class ApiReviewBest20Tests(unittest.TestCase):
    def observed(self, offsets, powers):
        return dict(source_id='synthetic-stream-source',summary_source_id='synthetic-summary-source',
                    streams=parse_streams(dict(time=stream(offsets),watts=stream(powers))))

    def test_exact_boundary_zero_tie_and_half_up_with_returned_bounds(self):
        best=review_best20(self.observed(list(range(17,1217)),[120]*600+[121]*600))
        self.assertEqual(best['status'],'available');self.assertEqual(best['average_watts'],120.5)
        self.assertEqual(best['rounded_watts'],121);self.assertEqual(best['eligible_window_count'],1)
        self.assertEqual((best['start_offset'],best['end_exclusive_offset'],best['sample_count']),(17,1217,1200))
        self.assertEqual(best['method'],'best-average-power-v1')
        self.assertNotIn('extraction_id',best);self.assertNotIn('start_record_index',best);self.assertNotIn('start_timestamp',best)
        zeros=review_best20(self.observed(list(range(1300)),[0]*1300))
        self.assertEqual((zeros['rounded_watts'],zeros['start_offset'],zeros['eligible_window_count']),(0,0,101))

    def test_raw_maximum_beats_earlier_equal_displayed_watts(self):
        best=review_best20(self.observed(list(range(1201)),[120]*1200+[121]))
        self.assertEqual(best['rounded_watts'],120);self.assertGreater(best['average_watts'],120)
        self.assertEqual(best['start_offset'],1)

    def test_gap_duplicate_backward_and_missing_invalidate_only_affected_windows(self):
        for offsets,powers,start in (([0]+list(range(5,1205)),[9999]+[100]*1200,5),
                                     ([0]+list(range(1200)),[9999]+[100]*1200,0),
                                     ([5]+list(range(1200)),[9999]+[100]*1200,0),
                                     (list(range(1201)),[None]+[100]*1200,1)):
            with self.subTest(start=start,first=offsets[:2]):
                best=review_best20(self.observed(offsets,powers))
                self.assertEqual(best['eligible_window_count'],1);self.assertEqual(best['average_watts'],100)
                self.assertEqual(best['start_offset'],start)

    def test_unavailable_never_repairs_absent_short_missing_or_downsampled_evidence(self):
        cases=[(dict(time=stream(list(range(1200)))),'watts_stream_missing'),
               (dict(watts=stream([120]*1200)),'time_missing'),
               (dict(time=stream([0,1]),watts=stream([120])),'signal_time_pairing_ambiguous'),
               (dict(time=stream([0,1]),watts=stream([120,120],resolution='low')),'signal_time_pairing_ambiguous'),
               (dict(time=stream(list(range(1199))),watts=stream([120]*1199)),'activity_shorter_than_required'),
               (dict(time=stream(list(range(0,2400,2))),watts=stream([120]*1200)),'no_complete_one_second_window'),
               (dict(time=stream(list(range(1200))),watts=stream([120]*1199+[None])),'incomplete_power')]
        for streams,reason in cases:
            best=review_best20(dict(source_id='fake',summary_source_id='fake',streams=parse_streams(streams)))
            self.assertEqual((best['status'],best['reason']),('unavailable',reason))
            self.assertIsNone(best['rounded_watts']);self.assertIsNone(best['start_offset'])

    def test_matches_independent_prefix_sum_verifier_across_multiple_segments(self):
        import random
        powers=[random.Random(i).randrange(0,301) for i in range(4900)]
        powers[1500]=None
        offsets=list(range(2500))+list(range(2513,4913))
        expected=comparison.independent_best(offsets,powers)
        best=review_best20(self.observed(offsets,powers))
        for actual,key in (('average_watts','average_watts'),('rounded_watts','rounded_watts'),
                           ('start_offset','start_elapsed'),('end_exclusive_offset','end_exclusive_elapsed'),
                           ('eligible_window_count','eligible_window_count')):
            self.assertEqual(best[actual],expected[key])


class ConnectionTests(unittest.TestCase):
    def setUp(self):fixture.StravaTests.setUp(self)

    def test_shared_rotation_persisted_before_first_stream_request_and_failure_does_not_roll_back(self):
        state=self.tokens.read();state['expires_at']=self.now;self.tokens.save(state)
        rotated=dict(access_token='new-fake-access',refresh_token='new-fake-refresh',expires_at=self.now+7200)
        http=fixture.FakeHTTP(fixture.Response(rotated),HTTPError('https://www.strava.com/',429,'private',{},None))
        client=ApiClient(fixture.CREDS,opener=http)
        with self.tokens.lock():
            current=refreshed_connection(self.tokens,client,now=self.now)
            self.assertEqual(self.tokens.read()['refresh_token'],'new-fake-refresh')
            with self.assertRaises(ApiError):client.streams(current['access_token'],123)
        self.assertEqual(http.requests[-1].get_header('Authorization'),'Bearer new-fake-access')
        self.assertEqual(self.tokens.read()['refresh_token'],'new-fake-refresh')
        self.assertEqual(self.store.connection.execute('SELECT COUNT(*) FROM strava_sync_state').fetchone()[0],0)

    def test_invalid_refresh_clears_the_single_shared_state(self):
        state=self.tokens.read();state['expires_at']=self.now;self.tokens.save(state)
        http=fixture.FakeHTTP(HTTPError('https://www.strava.com/oauth/token',400,'private',{},None))
        with self.tokens.lock(),self.assertRaises(AuthenticationError):
            refreshed_connection(self.tokens,ApiClient(fixture.CREDS,opener=http),now=self.now)
        self.assertFalse(self.tokens.path.exists())


class PersistenceTests(unittest.TestCase):
    observation=fixture.StravaTests.observation
    count=fixture.StravaTests.count

    def setUp(self):
        fixture.StravaTests.setUp(self)
        from rideworks.strava_api import apply_observations,normalize
        apply_observations(self.store,[normalize(self.observation()),normalize(self.observation(identity=2,seconds=60))],321,self.now)
        self.only=self.store.connection.execute("SELECT activity_id FROM strava_api_activities WHERE external_id='2'").fetchone()[0]
        self.payload=dict(time=stream([0,1,2,5]),watts=stream([0,120,None,130]),heartrate=stream([0,None,100,101]),cadence=stream([0,80,80,80]),moving=stream([False,True,True,True]))

    def test_versioned_idempotent_exact_evidence_restart_inspect_and_native_precedence(self):
        from rideworks.strava_streams import persist
        from rideworks.store import Store
        from rideworks.web import Application
        from rideworks.performance import performance_history
        before=performance_history(self.store);native=self.store.get_source(self.native['source_id'])
        result=persist(self.store,2,self.payload);self.assertTrue(result['usable']);self.assertTrue(result['new_stream_observation'])
        self.assertFalse(persist(self.store,2,self.payload)['new_stream_observation'])
        changed=json.loads(json.dumps(self.payload));changed['watts']['data'][1]=121
        self.assertTrue(persist(self.store,2,changed)['new_stream_observation'])
        rows=self.store.strava_stream_evidence(self.only);self.assertEqual(len(rows),2)
        self.assertEqual(sum(s['is_current'] for s in rows),1)
        self.assertEqual(rows[0]['streams']['time']['data'],[0,1,2,5])
        self.assertEqual(self.store.get_source(self.native['source_id']),native)
        self.assertEqual(performance_history(self.store),before)
        with Store(self.store.data_dir) as restarted:
            self.assertEqual(restarted.strava_stream_evidence(self.only),rows)
            compact=restarted.inspect(self.only);self.assertNotIn('streams',compact['strava_stream_sources'][0])
        app=Application(self.store.data_dir);html=app.get('/activities/'+self.only)[2].decode()
        self.assertIn('api-stream-samples',html);self.assertIn('Strava API stream evidence',html)
        self.assertNotIn('id="native-records"',html);self.assertIn('data-best20-status="unavailable"',html)
        persist(self.store,1,self.payload)
        rich=app.get('/activities/'+self.native['activity_id'])[2].decode()
        self.assertIn('id="native-records"',rich);self.assertIn('120 W',rich)
        self.assertNotIn('id="api-stream-samples"',rich);self.assertIn('stream-provenance',rich)
        self.assertEqual(self.store.get_source(self.native['source_id']),native)
        from rideworks.errors import RideWorksError
        with patch('rideworks.web.analyze_activity',side_effect=RideWorksError('Synthetic FIT analysis unavailable')):
            unavailable=app.get('/activities/'+self.native['activity_id'])[2].decode()
        self.assertNotIn('api-stream-samples',unavailable)  # Never switch a file-backed ride to API evidence.

    def test_normal_api_review_uses_current_summary_and_calculates_only_ride_local_result(self):
        from rideworks.strava_streams import persist
        from rideworks.strava_api import apply_observations,normalize
        from rideworks.web import Application
        from rideworks.performance import performance_history
        payload=dict(time=stream(list(range(100,1300))),watts=stream([120]*600+[121]*600),heartrate=stream([150]*1200))
        persist(self.store,2,payload)
        # A later summary supplies different averages; do not calculate/replace them from streams.
        summary=self.observation(identity=2,seconds=60)|dict(elapsed_time=2400,moving_time=2100,
            distance=1609.344,total_elevation_gain=30.48,average_watts=123,average_heartrate=111,
            max_watts=400,max_heartrate=160,average_cadence=80,kilojoules=555)
        apply_observations(self.store,[normalize(summary)],321,self.now+1)
        before=comparison.fingerprint(self.store.connection);history=performance_history(self.store)
        app=Application(self.store.data_dir)
        with patch('rideworks.performance.rebuild_performance',side_effect=AssertionError('Read-only review rebuilt history')):
            html=app.get('/activities/'+self.only)[2].decode()
        self.assertIn('data-best20-status="available"',html);self.assertIn('>121 W</strong>',html)
        self.assertIn('RideWorks-calculated from Strava API stream evidence',html)
        self.assertIn('>123 W</strong>',html);self.assertIn('>111 bpm</strong>',html);self.assertIn('>1.00 mi</strong>',html)
        self.assertIn('>40:00</strong>',html);self.assertIn('Moving duration',html);self.assertIn('>35:00</dd>',html)
        self.assertIn('>100 ft</dd>',html);self.assertIn('>555 kJ</dd>',html);self.assertIn('>400 W</dd>',html)
        self.assertLess(html.index('class="metrics"'),html.index('id="chart-title"'))
        self.assertLess(html.index('id="chart-title"'),html.index('class="panel best-panel api-best20"'))
        self.assertIn('class="panel ride-summary"',html);self.assertIn('Returned-offset start',html)
        self.assertNotIn('Timer duration',html);self.assertNotIn('<section class="recent-context"',html)
        self.assertNotIn('Record indices',html);self.assertNotIn('Native samples in window',html)
        self.assertNotIn('class="panel provenance" open',html)
        self.assertEqual(comparison.fingerprint(self.store.connection),before)
        self.assertEqual(performance_history(self.store),history)
        self.assertEqual(app.get('/activities/'+self.only)[2].decode(),html)

    def test_hr_only_summary_watts_never_substitute_for_missing_best20_and_metrics_stay_missing(self):
        from rideworks.strava_streams import persist
        from rideworks.strava_api import apply_observations,normalize
        from rideworks.web import Application
        apply_observations(self.store,[normalize(self.observation(identity=2,seconds=60)|dict(average_watts=333))],321,self.now+1)
        persist(self.store,2,dict(time=stream(list(range(1300))),heartrate=stream([100]*1300)))
        before=comparison.fingerprint(self.store.connection)
        html=Application(self.store.data_dir).get('/activities/'+self.only)[2].decode()
        self.assertIn('data-best20-status="unavailable"',html)
        self.assertIn('class="best-value">Unavailable',html);self.assertIn('No Strava watts stream',html)
        self.assertIn('>333 W</strong>',html);self.assertIn('>Unavailable</strong>',html)
        self.assertNotIn('<section class="recent-context"',html);self.assertEqual(comparison.fingerprint(self.store.connection),before)

    def test_pairing_missing_signals_and_unusable_stream_reasons_are_explicit(self):
        from rideworks.strava_streams import chart_reason,persist
        from rideworks.web import Application
        self.assertIsNone(chart_reason(parse_streams({'time':stream([0,2,8]),'heartrate':stream([0,None,100])})))
        for changes,reason in (({'time':stream([0,1,1,2])},'time_not_strictly_increasing'),
                               ({'watts':stream([1,2])},'signal_time_pairing_ambiguous'),
                               ({'watts':stream([1,2,3,4],resolution='low')},'signal_time_pairing_ambiguous')):
            payload=self.payload|changes;self.assertEqual(chart_reason(parse_streams(payload)),reason)
            persist(self.store,2,payload)
            html=Application(self.store.data_dir).get('/activities/'+self.only)[2].decode()
            self.assertIn('review-unavailable',html);self.assertNotIn('api-stream-samples',html)
        persist(self.store,2,{})
        self.assertIn('No usable Strava time stream',Application(self.store.data_dir).get('/activities/'+self.only)[2].decode())
        self.assertIsNone(chart_reason(parse_streams({'time':stream([0,5,10],resolution='low'), 'watts':stream([0,10,20],resolution='low')})))

    def test_summary_start_change_suppresses_old_mapping_until_new_fetch(self):
        from rideworks.strava_streams import persist
        from rideworks.strava_api import apply_observations,normalize
        from rideworks.web import Application
        persist(self.store,2,self.payload)
        apply_observations(self.store,[normalize(self.observation(identity=2,seconds=61))],321,self.now+1)
        evidence=self.store.strava_stream_evidence(self.only)[0]
        self.assertEqual(evidence['chart_unavailable_reason'],'start_context_changed')
        self.assertNotIn('api-stream-samples',Application(self.store.data_dir).get('/activities/'+self.only)[2].decode())
        persist(self.store,2,self.payload)
        self.assertEqual(self.count('strava_stream_sources'),2)
        self.assertIn('api-stream-samples',Application(self.store.data_dir).get('/activities/'+self.only)[2].decode())

    def test_recent_retry_is_bounded_and_reuses_usable_sources(self):
        from rideworks.strava_streams import enrich,recent_candidates,persist
        from rideworks.strava_api import apply_observations,normalize
        candidates=recent_candidates(self.store,dict(after=self.now-86400,before=self.now+60))
        self.assertEqual(candidates,['2'])
        persist(self.store,2,self.payload)
        http=fixture.FakeHTTP();client=ApiClient(fixture.CREDS,opener=http)
        result=enrich(self.store,client,'fake',candidates)
        self.assertEqual(result['stream_reused'],1);self.assertEqual(http.requests,[])
        self.assertEqual(recent_candidates(self.store,dict(after=self.now,before=self.now+60)),[])
        self.assertEqual(self.count('activities'),2)

    def test_stream_failure_does_not_rollback_metadata_and_retry_creates_no_duplicates(self):
        from rideworks.strava import sync
        self.store.connection.execute('DELETE FROM strava_stream_attempts')
        http=fixture.FakeHTTP(fixture.Response([self.observation(),self.observation(identity=2,seconds=60)]),
                              HTTPError('https://www.strava.com/',429,'private-fake-token',{},None))
        result=sync(self.store,ApiClient(fixture.CREDS,opener=http),now=self.now+1)
        self.assertEqual(result['status'],'completed');self.assertTrue(result['stream_rate_limited'])
        self.assertEqual(result['stream_failed'],1);self.assertEqual(result['stream_fetches'],1)
        self.assertEqual(self.store.connection.execute('SELECT successful_at FROM strava_sync_state').fetchone()[0],self.now+1)
        self.assertEqual(self.count('activities'),2)
        http=fixture.FakeHTTP(fixture.Response([self.observation(),self.observation(identity=2,seconds=60)]),fixture.Response(self.payload))
        result=sync(self.store,ApiClient(fixture.CREDS,opener=http),now=self.now+2)
        self.assertEqual(result['stream_enriched'],1);self.assertEqual(result['new_activities'],0)
        self.assertEqual(self.count('activities'),2)
        self.assertTrue(any('/streams?' in r.full_url for r in http.requests))

    def test_stream_401_clears_shared_authorization_after_committed_metadata(self):
        from rideworks.strava import sync
        http=fixture.FakeHTTP(fixture.Response([self.observation(),self.observation(identity=2,seconds=60)]),
                              HTTPError('https://www.strava.com/',401,'private-fake-token',{},None))
        result=sync(self.store,ApiClient(fixture.CREDS,opener=http),now=self.now+1)
        self.assertTrue(result['stream_authorization_attention']);self.assertFalse(self.tokens.path.exists())
        self.assertEqual(self.count('activities'),2);self.assertEqual(self.count('strava_sync_state'),1)

    def test_additive_schema5_upgrade_is_atomic_and_keeps_original_rows(self):
        import sqlite3
        from rideworks.store import Store
        import rideworks.store as module
        root=self.root/'schema5'
        with Store(root) as old:
            old.connection.execute("INSERT INTO activities VALUES('synthetic-activity','synthetic-created')")
            for table in ('strava_stream_current','strava_stream_attempts','strava_stream_sources'):
                old.connection.execute('DROP TABLE '+table)
            old.connection.execute('DROP TABLE training_stress_cache');old.connection.execute('DROP TABLE annual_mileage_goals')
            old.connection.execute('PRAGMA user_version=5')
        broken=module.MIGRATION_6.replace('PRAGMA user_version = 6;','INSERT INTO nonexistent VALUES(1);')
        with patch.object(module,'MIGRATION_6',broken),self.assertRaises(sqlite3.OperationalError):Store(root)
        with sqlite3.connect(root/'rideworks.sqlite3') as check:
            self.assertEqual(check.execute('PRAGMA user_version').fetchone()[0],5)
            self.assertEqual(check.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'strava_stream_%'").fetchone()[0],0)
        with Store(root) as migrated:
            self.assertEqual(migrated.connection.execute('PRAGMA user_version').fetchone()[0],8)
            self.assertEqual(tuple(migrated.connection.execute('SELECT * FROM activities').fetchone()),('synthetic-activity','synthetic-created'))
