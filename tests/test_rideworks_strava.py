"""Synthetic OAuth/API evidence tests. No automated calls to Strava."""
from contextlib import redirect_stdout, redirect_stderr
import copy
import csv
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit

from fit_fixture import make_fit
from rideworks.__main__ import main
from rideworks.config import strava_credentials, ConfigurationError
from rideworks.history import browse, presentation
from rideworks.performance import performance_history, rebuild_performance
from rideworks.store import Store
from rideworks import store as store_module
from rideworks.strava import (ApiClient, ApiError, AuthenticationError, TokenFile,
                              callback_values, connect, disconnect, exhausted, rate_state, sync)
from rideworks.strava_api import SyncError, apply_observations, normalize, sync_window
from rideworks.web import Application

CREDS=('123','synthetic-client-secret')


class Response(io.BytesIO):
    status=200
    def __init__(self,value,headers=None):
        super().__init__(json.dumps(value).encode() if not isinstance(value,bytes) else value)
        self.headers=headers or {}


class FakeHTTP:
    def __init__(self,*responses):self.responses=list(responses);self.requests=[]
    def open(self,request,timeout):
        self.requests.append(request)
        assert timeout==20
        result=self.responses.pop(0)
        if isinstance(result,Exception):raise result
        return result


class StravaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=Store(self.root/'data');self.addCleanup(self.store.close)
        self.file=self.root/'native.fit'
        self.file.write_bytes(make_fit(powers=[120]*1200,heart_rates=[100]*1200,timestamps=range(1100000000,1100001200),
                                      session_start_time=1100000000,session_timestamp=1100001200,elapsed=1200,timer=1200))
        self.native=self.store.import_fit(self.file)
        self.start=datetime.fromisoformat(self.store.get_source(self.native['source_id'])['summary']['start_time'])
        self.now=int(self.start.timestamp())+86400
        self.export=self.root/'export';(self.export/'activities').mkdir(parents=True)
        (self.export/'activities/native.fit').write_bytes(self.file.read_bytes())
        with (self.export/'activities.csv').open('w',newline='') as stream:
            writer=csv.writer(stream)
            writer.writerow(['Activity ID','Activity Name','Activity Type','Activity Date','Filename'])
            writer.writerow(['1','Export title','Virtual Ride',self.start.strftime('%b %d, %Y, %I:%M:%S %p'),'activities/native.fit'])
        self.store.import_strava_export(self.export)
        rebuild_performance(self.store)
        self.tokens=TokenFile(self.store.data_dir)
        self.tokens.save(dict(access_token='synthetic-access',refresh_token='synthetic-refresh',
                              expires_at=self.now+7200,athlete_id=321,scope='activity:read_all'))

    def observation(self,identity=1,seconds=0,**changes):
        return dict(id=identity,name='API title',type='Ride',sport_type='VirtualRide',
                    start_date=(self.start+timedelta(seconds=seconds)).isoformat(),
                    elapsed_time=1200,moving_time=1200,distance=0,average_watts=999,
                    device_watts=True,athlete={'id':321},map={'summary_polyline':'unnecessary'},
                    start_latlng=[1,2],description='unnecessary',**changes)

    def client(self,*responses):
        http=FakeHTTP(*responses);client=ApiClient(CREDS,opener=http)
        client.streams=lambda access,identity:{}  # These tests isolate metadata; stream HTTP is covered separately.
        return client,http

    def count(self,table):return self.store.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]

    def test_allowlist_excludes_locations_social_notes_profile_and_validates_shapes(self):
        values=normalize(self.observation());self.assertNotIn('athlete',values);self.assertNotIn('map',values)
        for field in ('start_latlng','description'):self.assertNotIn(field,values)
        for changes in ({'id':True},{'distance':float('nan')},{'elapsed_time':-1},{'start_date':'2024-01-01'},
                        {'name':['bad']},{'device_watts':1}):
            item=self.observation();item.update(changes)
            with self.subTest(changes=changes),self.assertRaises(SyncError):normalize(item)

    def test_oauth_state_scope_duplicate_parameters_and_declined_access_rejected(self):
        good=dict(state='expected',code='synthetic-code',scope='read,activity:read_all')
        self.assertEqual(callback_values(urlencode(good),'expected'),('synthetic-code',['activity:read_all','read']))
        for change in ({'state':'bad'},{'scope':'read'},{'error':'access_denied'},{'code':''}):
            with self.subTest(change=change),self.assertRaises(AuthenticationError):callback_values(urlencode(good|change),'expected')
        with self.assertRaises(AuthenticationError):callback_values(urlencode(good)+'&state=expected','expected')

    def test_connect_real_loopback_callback_fake_exchange_scope_athlete_and_private_tokens(self):
        response=dict(access_token='new-fake-access',refresh_token='new-fake-refresh',expires_at=self.now+7200,
                      athlete={'id':321},scope='read activity:read_all')
        client,http=self.client(Response(response));threads=[]
        def browser(url):
            query=parse_qs(urlsplit(url).query)
            self.assertEqual(query['scope'],['activity:read_all']);self.assertNotIn(CREDS[1],url)
            callback=urlsplit(query['redirect_uri'][0]);self.assertEqual(callback.hostname,'127.0.0.1')
            def send():
                connection=HTTPConnection(callback.hostname,callback.port,timeout=5)
                connection.request('GET',callback.path+'?'+urlencode(dict(state=query['state'][0],code='synthetic-code',scope='read,activity:read_all')))
                r=connection.getresponse();self.assertEqual(r.status,200);r.read();connection.close()
            thread=threading.Thread(target=send);threads.append(thread);thread.start()
        with redirect_stderr(io.StringIO()) as output:
            result=connect(self.store,client,port=0,timeout=5,open_browser=browser)
        for thread in threads:thread.join()
        self.assertEqual(result,{'status':'connected','scope':'activity:read_all'})
        self.assertEqual(self.tokens.read()['athlete_id'],321)
        self.assertEqual(self.tokens.read()['granted_scopes'],['activity:read_all','read'])
        self.assertEqual(self.tokens.path.stat().st_mode&0o777,0o600)
        self.assertNotIn(response['access_token'],output.getvalue());self.assertNotIn(response['refresh_token'],json.dumps(result))
        self.assertEqual(parse_qs(http.requests[0].data.decode())['grant_type'],['authorization_code'])

    def test_refresh_rotation_atomic_and_newest_token_used_after_later_page_failure(self):
        state=self.tokens.read();state['expires_at']=self.now;self.tokens.save(state)
        rotated=dict(access_token='rotated-fake-access',refresh_token='rotated-fake-refresh',expires_at=self.now+7200)
        client,http=self.client(Response(rotated),HTTPError('https://www.strava.com/',503,'private error',{},None))
        with patch('rideworks.strava.os.replace',wraps=os.replace) as replace,self.assertRaises(ApiError):sync(self.store,client,now=self.now)
        self.assertEqual(replace.call_count,1);self.assertEqual(self.tokens.read()['refresh_token'],'rotated-fake-refresh')
        self.assertEqual(http.requests[-1].get_header('Authorization'),'Bearer rotated-fake-access')
        self.assertEqual(self.count('strava_sync_state'),0)
        state=self.tokens.read();state['expires_at']=self.now;self.tokens.save(state)
        client,http=self.client(Response(rotated),Response([]));sync(self.store,client,now=self.now)
        self.assertEqual(parse_qs(http.requests[0].data.decode())['refresh_token'],['rotated-fake-refresh'])

    def test_invalid_token_disconnects_without_deleting_history_or_retry(self):
        client,http=self.client(HTTPError('https://www.strava.com/',401,'synthetic-access private',{},None))
        with self.assertRaises(AuthenticationError) as error:sync(self.store,client,now=self.now)
        self.assertFalse(self.tokens.path.exists());self.assertEqual(self.count('activities'),1)
        self.assertEqual(len(http.requests),1);self.assertNotIn('synthetic-access',str(error.exception))

    def test_invalid_refresh_and_failed_rotation_never_reuse_stale_token(self):
        state=self.tokens.read();state['expires_at']=self.now;self.tokens.save(state)
        client,http=self.client(HTTPError('https://www.strava.com/oauth/token',400,'secret',{},None))
        with self.assertRaises(AuthenticationError):sync(self.store,client,now=self.now)
        self.assertFalse(self.tokens.path.exists());self.assertEqual(len(http.requests),1)
        self.tokens.save(state)
        client,http=self.client(Response(dict(access_token='new-fake',refresh_token='newest-fake',expires_at=self.now+7200)))
        with patch('rideworks.strava.os.replace',side_effect=OSError('private path')),self.assertRaises(AuthenticationError):sync(self.store,client,now=self.now)
        self.assertFalse(self.tokens.path.exists());self.assertEqual(len(http.requests),1)
        self.assertEqual(self.count('strava_sync_state'),0)

    def test_unexpected_athlete_or_out_of_window_response_rolls_back(self):
        for item in (self.observation()|{'athlete':{'id':999}},self.observation(seconds=2*86400)):
            client,http=self.client(Response([item]))
            with self.assertRaises(SyncError):sync(self.store,client,now=self.now)
            self.assertEqual(self.count('strava_api_sources'),0);self.assertEqual(self.count('strava_sync_state'),0)

    def test_initial_window_latest_export_day_later_checkpoint_and_missing_boundary(self):
        window=sync_window(self.store,321,self.now)
        expected=datetime.combine(self.start.date()-timedelta(days=3),datetime.min.time(),timezone.utc)
        self.assertEqual(window['after'],int(expected.timestamp()))
        client,_=self.client(Response([]));sync(self.store,client,now=self.now)
        self.assertEqual(sync_window(self.store,321,self.now+60)['after'],self.now-3*86400)
        with self.assertRaises(SyncError):sync_window(self.store,999,self.now+60)
        self.store.connection.execute('DELETE FROM strava_sync_state');self.store.connection.execute('DELETE FROM export_row_locations');self.store.connection.execute('DELETE FROM strava_export_sources')
        client,http=self.client(Response([]))
        with self.assertRaises(SyncError):sync(self.store,client,now=self.now)
        self.assertEqual(http.requests,[])

    def test_multi_page_short_end_and_empty_page(self):
        page=[self.observation(identity=i+2,seconds=i+1) for i in range(100)]
        client,http=self.client(Response(page),Response([]))
        result=sync(self.store,client,now=self.now)
        self.assertEqual(result['pages_requested'],2);self.assertEqual(result['api_activities_observed'],100)
        self.assertEqual(result['new_activities'],100)
        self.assertEqual([parse_qs(urlsplit(r.full_url).query)['page'] for r in http.requests],[['1'],['2']])
        self.assertTrue(all(r.get_header('Authorization')=='Bearer synthetic-access' and 'synthetic-access' not in r.full_url for r in http.requests))

    def test_later_page_failure_and_exhausted_limit_apply_nothing(self):
        page=[self.observation(identity=i+2,seconds=i+1) for i in range(100)]
        for second in (HTTPError('https://www.strava.com/',429,'secret',{'X-RateLimit-Limit':'200,2000','X-RateLimit-Usage':'200,201'},None),Response([{'bad':'shape'}])):
            client,http=self.client(Response(page),second)
            with self.assertRaises(SyncError):sync(self.store,client,now=self.now)
            self.assertEqual(self.count('activities'),1);self.assertEqual(self.count('strava_api_sources'),0)
            self.assertEqual(self.count('strava_sync_state'),0);self.assertEqual(len(http.requests),2)
        client,http=self.client(Response(page,{'X-ReadRateLimit-Limit':'100,1000','X-ReadRateLimit-Usage':'100,101'}))
        with self.assertRaises(ApiError):sync(self.store,client,now=self.now)
        self.assertEqual(len(http.requests),1);self.assertEqual(self.count('strava_sync_state'),0)

    def test_rate_headers_https_timeout_redirect_and_json_limit(self):
        self.assertTrue(exhausted(rate_state({'X-RateLimit-Limit':'200,2000','X-RateLimit-Usage':'200,300'})))
        for body in (b'not JSON',b'x'*(2*1024*1024+1)):
            client,_=self.client(Response(body))
            with self.assertRaises(SyncError):client.activities('fake',dict(after=1,before=2),1)
        client,http=self.client()
        with self.assertRaises(SyncError):client.request('GET','http://www.strava.com/api/v3/athlete/activities',token='fake')
        self.assertEqual(http.requests,[])
        client,_=self.client(URLError('synthetic-client-secret'))
        with self.assertRaises(SyncError) as error:client.activities('fake',dict(after=1,before=2),1)
        self.assertNotIn('synthetic-client-secret',str(error.exception))
        from rideworks.strava import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'redirect',{},'https://untrusted.invalid'))

    def test_established_identity_enrichment_preserves_fit_and_converges_history(self):
        before=self.store.get_source(self.native['source_id']);rows=list(self.store.connection.execute('SELECT * FROM performance_history'))
        client,_=self.client(Response([self.observation()]))
        with patch.object(Store,'import_strava_export',side_effect=AssertionError('archive')),patch.object(Store,'reextract',side_effect=AssertionError('reparse')),patch('rideworks.performance.rebuild_performance',wraps=rebuild_performance) as rebuilt:
            report=sync(self.store,client,now=self.now)
        self.assertEqual(report['new_activities'],0);self.assertEqual(report['existing_activities_enriched'],1)
        self.assertEqual(self.store.get_source(self.native['source_id']),before)
        self.assertEqual(rebuilt.call_count,1);self.assertEqual(report['performance_update'],'updated')
        self.assertEqual(performance_history(self.store)['pending'],0)
        self.assertEqual(performance_history(self.store)['points'][0]['rounded_watts'],120)
        row=presentation(self.store.activity_history()[0]);self.assertEqual(row['title'],'API title')
        html=Application(self.store.data_dir).get('/activities/'+self.native['activity_id'])[2].decode()
        self.assertIn('API title',html);self.assertIn('Export title',html);self.assertIn('FIT session source evidence',html)
        self.assertIn('class="best-value">120 W',html);self.assertNotIn('class="performance-update"',html)

    def test_api_only_thin_native_excluded_and_local_dates_filters_work(self):
        client,_=self.client(Response([self.observation(identity=2,seconds=3600)]));sync(self.store,client,now=self.now)
        row=next(presentation(s) for s in self.store.activity_history() if s['activity']['activity_id']!=self.native['activity_id'])
        self.assertEqual(row['title_origin'],'Strava API source title');self.assertEqual(row['duration'],1200)
        html=Application(self.store.data_dir).get('/activities/'+row['activity_id'])[2].decode()
        self.assertIn('Strava API metadata',html);self.assertIn('Average watts (W)',html)
        self.assertNotIn('native-records',html);self.assertNotIn('recent-context-title',html)
        self.assertNotIn('unnecessary',html)
        self.assertEqual(browse(self.store,'q=API&type=cycling&tz=America%2FLos_Angeles')['count'],1)
        rebuild_performance(self.store)
        result=next(r for r in performance_history(self.store)['results'] if r['activity_id']==row['activity_id'])
        self.assertFalse(result['eligible']);self.assertEqual(result['reason'],'api_power_stream_unavailable')

    def test_identical_rerun_changed_title_type_and_reverting_observation_are_idempotent(self):
        item=self.observation();client,_=self.client(Response([item]));sync(self.store,client,now=self.now)
        before=self.store.activity_history()
        with Store(self.store.data_dir) as restarted:
            client,_=self.client(Response([item]));report=sync(restarted,client,now=self.now+1)
            self.assertEqual(report['unchanged_observations'],1);self.assertEqual(report['new_observations'],0)
            self.assertEqual(restarted.activity_history(),before)
        changed=item|dict(name='Changed API title',sport_type='Ride')
        client,_=self.client(Response([changed]));sync(self.store,client,now=self.now+2)
        self.assertEqual(presentation(self.store.activity_history()[0])['activity_type'],'Ride')
        self.assertEqual(self.count('strava_api_sources'),2)
        client,_=self.client(Response([item]));sync(self.store,client,now=self.now+3)
        self.assertEqual(self.count('strava_api_sources'),2)
        self.assertEqual(presentation(self.store.activity_history()[0])['title'],'API title')
        self.assertEqual(self.store.connection.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.store.connection.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_unique_strong_local_match_and_ambiguous_match_never_forced(self):
        self.store.connection.execute('DELETE FROM export_row_locations');self.store.connection.execute('DELETE FROM strava_export_sources')
        values=normalize(self.observation())
        result=apply_observations(self.store,[values],321,self.now)
        self.assertEqual(result['strong_local_matches'],1);self.assertEqual(self.count('activities'),1)
        # Separate synthetic store with two files whose multiple facts agree.
        with Store(self.root/'ambiguous') as other:
            other.import_fit(self.file)
            altered=self.root/'alternative.fit'
            # Different valid power evidence, same start/classification/duration.
            altered.write_bytes(make_fit(powers=[121]*1200,heart_rates=[100]*1200,timestamps=range(1100000000,1100001200),
                                        session_start_time=1100000000,session_timestamp=1100001200,elapsed=1200,timer=1200))
            other.import_fit(altered)
            report=apply_observations(other,[values],321,self.now)
            self.assertEqual(report['ambiguous_new_associations'],1);self.assertEqual(report['new_activities'],1)
            self.assertEqual(other.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0],3)

    def test_title_alone_or_conflicting_duration_never_matches(self):
        self.store.connection.execute('DELETE FROM export_row_locations');self.store.connection.execute('DELETE FROM strava_export_sources')
        result=apply_observations(self.store,[normalize(self.observation()|{'elapsed_time':900})],321,self.now)
        self.assertEqual(result['new_activities'],1);self.assertEqual(result['strong_local_matches'],0)

    def test_transaction_failure_rolls_back_sources_and_checkpoint(self):
        values=normalize(self.observation())
        self.store.connection.execute("CREATE TRIGGER fail_sync BEFORE INSERT ON strava_sync_state BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.Error):apply_observations(self.store,[values],321,self.now)
        self.assertEqual(self.count('activities'),1);self.assertEqual(self.count('strava_api_sources'),0)
        self.assertEqual(self.count('strava_sync_state'),0)

    def test_disconnect_uses_basic_revoke_and_clears_even_when_remote_unavailable(self):
        client,http=self.client(Response(b''));report=disconnect(self.store,client)
        self.assertEqual(report['remote_revocation'],'revoked');self.assertFalse(self.tokens.path.exists())
        self.assertTrue(http.requests[0].get_header('Authorization').startswith('Basic '))
        self.assertEqual(http.requests[0].full_url,'https://www.strava.com/oauth/revoke')
        self.assertEqual(self.count('activities'),1)
        self.tokens.save(dict(access_token='fake',refresh_token='fake',expires_at=self.now,athlete_id=321,scope='activity:read_all'))
        client,_=self.client(URLError('secret'));self.assertEqual(disconnect(self.store,client)['status'],'disconnected')
        self.assertFalse(self.tokens.path.exists())

    def test_config_credential_precedence_and_safe_cli_error_and_disconnect_without_credentials(self):
        template=(Path(__file__).resolve().parents[1]/'.env.example').read_text()
        (self.root/'.env').write_text(template)
        with self.assertRaises(ConfigurationError):strava_credentials(repo_root=self.root,environ={})
        configured=template.replace('STRAVA_CLIENT_ID=\n','STRAVA_CLIENT_ID=456\n').replace('STRAVA_CLIENT_SECRET=\n','STRAVA_CLIENT_SECRET="file-secret"\n')
        (self.root/'.env').write_text(configured)
        self.assertEqual(strava_credentials(repo_root=self.root,environ={}),('456','file-secret'))
        self.assertEqual(strava_credentials(repo_root=self.root,environ={'STRAVA_CLIENT_ID':'789','STRAVA_CLIENT_SECRET':'environment-secret'}),('789','environment-secret'))
        with patch.dict(os.environ,{},clear=True),patch('rideworks.config.repository_root',return_value=self.root/'missing'),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--data-dir',str(self.store.data_dir),'sync-strava']),1)
            self.assertEqual(json.loads(output.getvalue())['status'],'failed')
        self.assertNotIn('environment-secret',output.getvalue())
        with patch.dict(os.environ,{},clear=True),patch('rideworks.config.repository_root',return_value=self.root/'missing'),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--data-dir',str(self.store.data_dir),'strava-disconnect']),0)
        self.assertFalse(self.tokens.path.exists())

    def test_schema4_migration_failure_atomic_and_success_preserves_native_evidence(self):
        root=self.root/'schema4'
        with patch('rideworks.store.MIGRATION_5',''):
            with Store(root) as old:
                native=old.import_fit(self.file);before=old.get_source(native['source_id'])
                self.assertEqual(old.connection.execute('PRAGMA user_version').fetchone()[0],4)
        broken=store_module.MIGRATION_5.replace('PRAGMA user_version = 5;','INSERT INTO nonexistent VALUES (1);')
        with patch('rideworks.store.MIGRATION_5',broken),self.assertRaises(sqlite3.Error):Store(root)
        with sqlite3.connect(root/'rideworks.sqlite3') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],4)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='strava_api_sources'").fetchone()[0],0)
        with Store(root) as migrated:
            self.assertEqual(migrated.get_source(native['source_id']),before)
            self.assertEqual(migrated.connection.execute('PRAGMA user_version').fetchone()[0],8)


if __name__=='__main__':unittest.main()
