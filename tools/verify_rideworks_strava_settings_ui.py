#!/usr/bin/env python3
"""Actual Chromium Settings/OAuth/restart acceptance, entirely synthetic and local."""
import argparse
import csv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'tests'))
from fit_fixture import make_fit
from rideworks.config import ConfigurationError
from rideworks.errors import RideWorksError
from rideworks.performance import rebuild_performance, performance_history
from rideworks.settings import Settings
from rideworks.store import Store
from rideworks.strava import ApiClient, TokenFile
from rideworks.web import create_server
from verify_rideworks_strava_ui import verify as verify_reviews


def browser(code, session):
    result = subprocess.run(['npx', '--offline', '--yes', '--package', '@playwright/cli',
                             'playwright-cli', '-s='+session, 'run-code', code], capture_output=True, text=True)
    if result.returncode or '### Error' in result.stdout:
        (ROOT/'output/playwright/p2-05-settings-error.log').write_text(result.stdout+result.stderr)
        raise RuntimeError('Chromium Settings check failed; inspect ignored output/playwright/p2-05-settings-error.log')
    return json.loads(result.stdout.split('### Result\n', 1)[1].split('### Ran Playwright code', 1)[0])


def fixture(root):
    assert not root.exists(), 'Use a fresh disposable synthetic store'
    now = int(time.time())
    with Store(root) as store:
        for offset, watts in ((-172800, 180), (-86400, 120)):
            raw = now+offset-631065600
            path = root/f'synthetic-{watts}.fit'
            path.write_bytes(make_fit(powers=[watts]*1200, heart_rates=[100]*1200,
                                     timestamps=range(raw, raw+1200), session_start_time=raw,
                                     session_timestamp=raw+1200, elapsed=1200, timer=1200))
            current = store.import_fit(path)
        start = store.get_source(current['source_id'])['summary']['start_time']
        export = root/'synthetic-export'; (export/'activities').mkdir(parents=True)
        (export/'activities/synthetic.fit').write_bytes(path.read_bytes())
        with (export/'activities.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Activity ID', 'Activity Name', 'Activity Type', 'Activity Date', 'Filename'])
            writer.writerow(['1', 'Synthetic export title', 'Virtual Ride', datetime.fromisoformat(start).strftime('%b %d, %Y, %I:%M:%S %p'), 'activities/synthetic.fit'])
        store.import_strava_export(export)
        rebuild_performance(store)  # Synthetic fixture setup only.
        original = store.get_source(current['source_id'])
    observations = [dict(id=1, name='Synthetic API enriched ride', type='Ride', sport_type='VirtualRide',
                         start_date=start, elapsed_time=1200, distance=0, average_watts=999),
                    dict(id=2, name='Synthetic API-only ride', type='Ride', sport_type='VirtualRide',
                         start_date=datetime.fromtimestamp(now-3600, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         elapsed_time=1200, distance=1000, average_watts=999)]
    return observations, current, original


def verify(root, session):
    observations, current, original = fixture(root)
    configured = False
    requests = []
    def credentials():
        if not configured:
            raise ConfigurationError('Synthetic credentials missing')
        return '123', 'synthetic-only-client-secret'
    class Response(BytesIO):
        status = 200
        headers = {}
    class FakeHTTP:
        def open(self, request, timeout):
            requests.append(request)
            path = urlsplit(request.full_url).path
            if path == '/oauth/token':
                result = dict(access_token='synthetic-only-access', refresh_token='synthetic-only-refresh',
                              expires_at=int(time.time())+7200, athlete={'id':42}, scope='activity:read_all')
            elif path == '/api/v3/athlete/activities':
                time.sleep(.75)  # Allows the real browser to verify disabled action controls.
                result = observations
            elif path.startswith('/api/v3/activities/') and path.endswith('/streams'):
                result = {}  # P2-05 regression fixture intentionally has no optional streams.
            elif path == '/oauth/revoke':
                result = {}
            else:
                raise AssertionError('Unexpected synthetic endpoint')
            return Response(json.dumps(result).encode())
    def settings_factory(data_dir):
        return Settings(data_dir, credentials=credentials, client_factory=lambda values: ApiClient(values, opener=FakeHTTP()))
    def start(port=0):
        server = create_server(root, port, settings_factory=settings_factory)
        thread = threading.Thread(target=server.serve_forever); thread.start()
        return server, thread
    def stop(server, thread):
        server.shutdown(); thread.join(); server.server_close()
    server, thread = start()
    port = server.server_port
    base = f'http://127.0.0.1:{port}'
    prefix = 'async(page)=>{ const base='+json.dumps(base)+";const check=(v,m)=>{if(!v)throw new Error(m);};"
    prefix += """
      const settingsReady=async()=>{
        await page.waitForFunction(()=>location.pathname==='/settings'&&new URL(location.href).searchParams.get('tz')===Intl.DateTimeFormat().resolvedOptions().timeZone);
        await page.waitForSelector('#target-miles');
      };
    """
    def run(code):
        return browser(prefix+code+'}', session)
    try:
        run("""
          await page.unrouteAll({behavior:'wait'});
          await page.goto(base+'/');await page.getByRole('navigation',{name:'Main'}).getByRole('link',{name:'Settings',exact:true}).click();await settingsReady();
          check(await page.locator('#strava-credentials').textContent()==='Missing','Missing credentials state');
          check(await page.getByRole('button',{name:'Connect Strava',exact:true}).count()===0,'Invalid Connect action');
          check(await page.locator('#strava-connection').textContent()==='Not connected','Initial state');return true;
        """)
        configured = True
        run("""
          await page.goto(base+'/settings');await settingsReady();check(await page.locator('#strava-credentials').textContent()==='Configured','Configured state');
          await page.route(base+'/settings/strava/connect',async route=>{
            const response=await route.fetch({maxRedirects:0});check(response.status()===303,'OAuth redirect response');
            const auth=new URL(response.headers().location);check(auth.origin==='https://www.strava.com'&&auth.pathname==='/oauth/authorize','Authorization endpoint');check(auth.searchParams.get('scope')==='activity:read_all','Scope');
            check(auth.searchParams.get('redirect_uri')===base+'/strava/callback','Already-running callback');
            const callback=auth.searchParams.get('redirect_uri')+'?'+new URLSearchParams({state:auth.searchParams.get('state'),error:'access_denied'});
            await route.fulfill({status:200,contentType:'text/html',headers:{'Cache-Control':'no-store'},body:'<a href="'+callback.replaceAll('&','&amp;')+'">Decline synthetic authorization</a>'});
          });
          await page.getByRole('button',{name:'Connect Strava',exact:true}).click();
          await page.getByRole('link',{name:'Decline synthetic authorization'}).click();
          await settingsReady();check(await page.locator('#strava-connection').textContent()==='Authorization needs attention','Declined state');
          await page.unroute(base+'/settings/strava/connect');
          await page.route(base+'/settings/strava/connect',async route=>{
            const response=await route.fetch({maxRedirects:0});check(response.status()===303,'OAuth redirect response');
            const auth=new URL(response.headers().location);check(auth.origin==='https://www.strava.com'&&auth.pathname==='/oauth/authorize','Authorization endpoint');
            const callback=auth.searchParams.get('redirect_uri')+'?'+new URLSearchParams({state:auth.searchParams.get('state'),code:'synthetic-only-code',scope:'activity:read_all'});
            await route.fulfill({status:200,contentType:'text/html',headers:{'Cache-Control':'no-store'},body:'<a href="'+callback.replaceAll('&','&amp;')+'">Grant synthetic authorization</a>'});
          });
          await page.getByRole('button',{name:'Reconnect Strava',exact:true}).click();
          await page.getByRole('link',{name:'Grant synthetic authorization'}).click();
          await settingsReady();check(await page.locator('#strava-connection').textContent()==='Connected','OAuth Connected state');
          check(!page.url().includes('code='),'Callback code remains active');
          await page.screenshot({path:'output/playwright/p2-05-settings-connected.png',fullPage:true});
          const disabled=page.waitForFunction(()=>{
            const buttons=[...document.querySelectorAll('.strava-actions button')];
            return buttons.length>0&&buttons.every(b=>b.disabled);
          });
          await Promise.all([disabled,page.getByRole('button',{name:'Sync now',exact:true}).click()]);
          await settingsReady();await page.waitForSelector('#strava-outcome');
          check(await page.locator('#strava-outcome').textContent()==='1 new · 1 enriched · 0 unchanged','Initial counts');
          check(await page.locator('.performance-update').count()===0,'Routine sync must converge Performance');
          check((await page.locator('#performance-sync-outcome').textContent()).includes('Performance updated'),'Automatic update outcome');
          check(await page.locator('#strava-last-sync time').count()===1,'Sync time');
          check(!(await page.locator('#strava-last-sync').textContent()).includes('(GMT'),'Date suffix');
          const markup=await page.content();check(!/synthetic-only-(access|refresh|client-secret|code)/.test(markup),'Secret markup');
          check(await page.evaluate(()=>localStorage.length===0&&sessionStorage.length===0),'Browser secret storage');
          await page.setViewportSize({width:390,height:844});
          check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Settings phone overflow');
          await page.screenshot({path:'output/playwright/p2-05-settings-phone.png',fullPage:true});
          await page.getByRole('navigation',{name:'Main'}).getByRole('link',{name:'Activities',exact:true}).click();await page.waitForSelector('.activity-row');
          check(await page.locator('.activity-row').count()===3,'Activities need restart to update');
          check(await page.locator('.activity-row h2').first().textContent()==='Synthetic API-only ride','New API date not sorted first');return true;
        """)
        with Store(root) as store:
            assert store.get_source(current['source_id']) == original
            assert store.connection.execute('SELECT COUNT(*) FROM strava_api_sources').fetchone()[0] == 2
            thin = store.connection.execute("SELECT activity_id FROM strava_api_activities WHERE external_id='2'").fetchone()[0]
            links = dict(rich='/activities/'+current['activity_id'], thin='/activities/'+thin)
            (ROOT/'output/playwright/p2-05-synthetic-links.json').write_text(json.dumps(links))
            before = [tuple(row) for row in store.connection.execute('SELECT * FROM performance_history ORDER BY activity_id')]
        reviews = verify_reviews(port, session)
        for zone in ('America/Los_Angeles', 'Asia/Tokyo'):
            local = datetime.fromisoformat(observations[1]['start_date'].replace('Z', '+00:00')).astimezone(ZoneInfo(zone))
            expected = local.strftime('%b %-d, %Y, %-I:%M %p')
            run('''
              const context=await page.context().browser().newContext({timezoneId:ZONE,locale:'en-US'});
              const local=await context.newPage();try{
                await local.goto(base+'/activities?tz='+encodeURIComponent(ZONE));await local.waitForSelector('.activity-row time');
                const first=local.locator('.activity-row').first();
                check(await first.locator('h2').textContent()==='Synthetic API-only ride','Z date newest ordering');
                check((await first.locator('time').textContent()).replaceAll('\\u202f',' ')===EXPECTED,'Local API Date display');
                check(await first.locator('time').getAttribute('data-local-day')===DAY,'Local API calendar day');
                await local.goto(base+'/activities?sort=oldest&tz='+encodeURIComponent(ZONE));await local.waitForSelector('.activity-row');
                check(await local.locator('.activity-row h2').last().textContent()==='Synthetic API-only ride','Z date oldest ordering');
              }finally{await context.close();}return true;
            '''.replace('ZONE', json.dumps(zone)).replace('EXPECTED', json.dumps(expected)).replace('DAY', json.dumps(local.date().isoformat())))
        run('''
          for(const path of ['/settings','/','/performance',RICH]){
            await page.goto(base+path);check(await page.locator('.performance-update').count()===0,'Routine banner');
          }return true;
        '''.replace('RICH', json.dumps(links['rich'])))
        stop(server, thread)
        token_file = TokenFile(root); token = token_file.read(); token['expires_at'] = int(time.time()); token_file.save(token)
        server, thread = start(port)
        run("""
          await page.setViewportSize({width:1448,height:1086});await page.goto(base+'/settings');await settingsReady();
          check(await page.locator('#strava-connection').textContent()==='Connected','Restart lost connection');
          check(await page.locator('#strava-outcome').textContent()==='1 new · 1 enriched · 0 unchanged','Restart lost outcome');
          await page.getByRole('button',{name:'Sync now',exact:true}).click();await settingsReady();await page.waitForSelector('#strava-outcome');
          check(await page.locator('#strava-outcome').textContent()==='0 new · 0 enriched · 2 unchanged','Restart rerun');
          await page.screenshot({path:'output/playwright/p2-05-settings-rerun.png',fullPage:true});
          check(await page.locator('.performance-update').count()===0,'Restart left routine banner');
          check((await page.locator('#performance-sync-outcome').textContent()).includes('Performance is current'),'Unnecessary rebuild');return true;
        """)
        with Store(root) as store:
            assert before == [tuple(row) for row in store.connection.execute('SELECT * FROM performance_history ORDER BY activity_id')]
        observations[1]['name']='Synthetic changed API-only ride'
        with patch('rideworks.performance.evaluate', side_effect=RideWorksError('Synthetic rebuild failure')):
            run("""
              await page.getByRole('button',{name:'Sync now',exact:true}).click();await settingsReady();
              check((await page.locator('#performance-sync-outcome').textContent()).includes('Performance update incomplete'),'Sync rebuild failure outcome');
              check(await page.locator('.performance-update').count()===1,'Failed rebuild dismissed exception');
              await page.getByRole('button',{name:'Retry Performance update',exact:true}).click();await settingsReady();
              check((await page.locator('#strava-notice').textContent()).includes('Performance update incomplete'),'Manual retry failure');return true;
            """)
        with Store(root) as store:
            assert before == [tuple(row) for row in store.connection.execute('SELECT * FROM performance_history ORDER BY activity_id')]
            assert store.connection.execute('SELECT COUNT(*) FROM strava_api_sources').fetchone()[0]==3
            assert store.connection.execute('SELECT successful_at FROM strava_sync_state').fetchone()[0]>0
            assert performance_history(store)['pending']>0
        stop(server,thread);server,thread=start(port)
        run("""
          await page.goto(base+'/settings');await settingsReady();check(await page.locator('.performance-update').count()===1,'Restart lost exception banner');
          await page.getByRole('button',{name:'Sync now',exact:true}).click();await settingsReady();
          check(await page.locator('.performance-update').count()===0,'Later sync did not retry Performance');
          check((await page.locator('#performance-sync-outcome').textContent()).includes('Performance updated'),'Retry sync result');
          await page.getByRole('button',{name:'Disconnect',exact:true}).click();await settingsReady();
          check(await page.locator('#strava-connection').textContent()==='Not connected','Disconnect state');
          await page.getByRole('navigation',{name:'Main'}).getByRole('link',{name:'Activities',exact:true}).click();await page.waitForSelector('.activity-row');
          check(await page.locator('.activity-row').count()===3,'Disconnect deleted history');
          await page.unrouteAll({behavior:'wait'});return true;
        """)
        assert not token_file.path.exists()
        forms = [parse_qs(request.data.decode()) for request in requests if urlsplit(request.full_url).path == '/oauth/token']
        assert forms[-1]['grant_type'] == ['refresh_token']
        assert forms[-1]['refresh_token'] == ['synthetic-only-refresh']
        with Store(root) as store:
            assert store.connection.execute('SELECT COUNT(*) FROM activities').fetchone()[0] == 3
            assert store.connection.execute('SELECT COUNT(*) FROM strava_api_sources').fetchone()[0] == 3
            assert performance_history(store)['pending'] == 0
            assert store.get_source(current['source_id']) == original
            assert store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not store.connection.execute('PRAGMA foreign_key_check').fetchall()
        return dict(status='passed', mode='synthetic_fake_http_actual_chromium', settings_navigation=True,
                    missing_configured_connected_attention=True, oauth_decline_reconnect_clean_url=True,
                    same_running_server_callback=True, buttons_disabled_during_sync=True,
                    compact_outcome_and_local_time=True, activities_update_without_restart=True,
                    no_browser_secrets=True, desktop_phone_no_overflow=True,
                    server_restart_connected_and_outcome_persist=True, near_expiry_refresh=True,
                    rerun_new_activities=0, rerun_new_observations=0, rerun_unchanged=2,
                    disconnect_retains_history=True, native_evidence_unchanged=True,automatic_performance_convergence=True,
                    exception_persists_after_restart=True,failed_sync_rebuild_preserves_history_and_sources=True,
                    later_unchanged_sync_retries=True,manual_retry_action=True,new_api_first_in_newest=True,
                    los_angeles_tokyo_api_date_and_newest_oldest=True,exception_only_banner=True,
                    activity_review_regression=reviews)
    finally:
        stop(server, thread)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-dir', type=Path, required=True)
    parser.add_argument('--session', default='rideworks-p2-05')
    args = parser.parse_args()
    print(json.dumps(verify(args.synthetic_dir, args.session), indent=2))
