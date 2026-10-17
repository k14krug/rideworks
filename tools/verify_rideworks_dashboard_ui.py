#!/usr/bin/env python3
"""Chromium Phase 3 acceptance: live review store or fresh synthetic fake HTTP."""
import argparse
import csv
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from fit_fixture import make_fit
from rideworks.errors import RideWorksError
from rideworks.goals import set_annual_goal
from rideworks.performance import rebuild_performance
from rideworks.settings import Settings
from rideworks.store import Store, artifact_integrity
from rideworks.dashboard import dashboard
from rideworks.strava import ApiClient, TokenFile, sync
from rideworks.web import create_server
from compare_rideworks_strava_streams import fingerprint
from verify_rideworks_dashboard import verify as independent
from verify_rideworks_strava_settings_ui import browser


def fixture(root):
    assert not root.exists(),'Use a fresh disposable synthetic store'
    now=int(time.time());export=root/'export'
    with Store(root) as store:
        export.mkdir();(export/'activities').mkdir()
        for age,power,metres in ((3,150,1609.34),(2,180,3218.68),(1,120,1609.34)):
            raw=now-age*86400-631065600
            blob=make_fit(powers=[power]*1200,heart_rates=[100]*1200,timestamps=range(raw,raw+1200),
                session_start_time=raw,session_timestamp=raw+1200,elapsed=1200,timer=1200,distance=metres,avg_power=power)
            source=export/'activities'/f'synthetic-{age}.fit';source.write_bytes(blob)
            current=store.import_fit(source)
        start=store.get_source(current['source_id'])['summary']['start_time']
        with (export/'activities.csv').open('w',newline='') as stream:
            writer=csv.writer(stream)
            writer.writerow(['Activity ID','Activity Name','Activity Type','Activity Date','Filename','Distance','Average Watts'])
            writer.writerow(['1','Synthetic file overlap','Virtual Ride',start,'activities/synthetic-1.fit','99999','999'])
            writer.writerow(['99','Synthetic CSV-only ride','Virtual Ride',datetime.fromtimestamp(now-4*86400,timezone.utc).isoformat(),'','99999','999'])
        store.import_strava_export(export);rebuild_performance(store)
        TokenFile(root).save(dict(access_token='synthetic-access',refresh_token='synthetic-refresh',
            expires_at=now+7200,athlete_id=42,scope='activity:read_all'))
    observations=[dict(id=1,name='Synthetic API overlap title',type='Ride',sport_type='VirtualRide',start_date=start,
                    elapsed_time=1200,distance=99999,device_watts=True,average_watts=999),
        dict(id=2,name='Synthetic API Virtual Ride',type='Ride',sport_type='VirtualRide',
             start_date=datetime.fromtimestamp(now-3600,timezone.utc).isoformat(),elapsed_time=1200,distance=1609.344,device_watts=True,average_watts=88.5),
        dict(id=3,name='Synthetic outdoor Ride',type='Ride',sport_type='Ride',
             start_date=datetime.fromtimestamp(now-1800,timezone.utc).isoformat(),elapsed_time=1200,distance=3218.688,device_watts=False,average_watts=100),
        dict(id=4,name='Synthetic Run excluded',type='Run',sport_type='Run',
             start_date=datetime.fromtimestamp(now-1200,timezone.utc).isoformat(),elapsed_time=600,distance=99999)]
    class Response(BytesIO):
        status=200;headers={}
    class FakeHTTP:
        def open(self,request,timeout):
            path=urlsplit(request.full_url).path
            if path=='/api/v3/athlete/activities':value=observations
            elif path.endswith('/streams'):
                item=lambda values:dict(data=values,resolution='high',original_size=len(values),series_type='time')
                value=dict(time=item(list(range(1200))),heartrate=item([100]*1200))
                if path.split('/')[-2]=='2':value['watts']=item([210]*1200)
            else:raise AssertionError('Unexpected synthetic endpoint')
            return Response(json.dumps(value).encode())
    factory=lambda root:Settings(root,credentials=lambda:('123','synthetic-secret'),
                                  client_factory=lambda credentials:ApiClient(credentials,opener=FakeHTTP()))
    return factory,observations


def verify(root,session,*,baseline=None,synthetic=False,skip_sync=False):
    if synthetic:
        factory,observations=fixture(root)
        with Store(root) as store:before=fingerprint(store.connection)
        legacy=None;originals=None
    else:
        assert baseline and not baseline.exists(),'Use a fresh ignored schema-6 baseline'
        baseline.mkdir(parents=True,mode=0o700)
        replay=baseline/'schema6-replay';replay.mkdir()
        with sqlite3.connect(root/'rideworks.sqlite3') as db,sqlite3.connect(baseline/'accepted.sqlite3') as backup:
            initial_version=db.execute('PRAGMA user_version').fetchone()[0]
            assert initial_version in (6,7)
            db.backup(backup)
            with sqlite3.connect(replay/'rideworks.sqlite3') as copy:
                db.backup(copy)
                if initial_version==7:copy.execute('DROP TABLE annual_mileage_goals')
                copy.execute('PRAGMA user_version=6');copy.commit();legacy=fingerprint(copy)
        with Store(replay) as copy:
            migrated=fingerprint(copy.connection)
            assert all(migrated[k]==v for k,v in legacy.items())
            assert not copy.connection.execute('PRAGMA foreign_key_check').fetchall()
        originals={p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in (root/'originals').iterdir()}
        factory=Settings
        with Store(root) as store:
            before=fingerprint(store.connection)
            assert all(before[k]==v for k,v in legacy.items()),'Schema migration changed accepted evidence'
    with Store(root) as store:
        initial_goals=[tuple(r) for r in store.connection.execute('SELECT * FROM annual_mileage_goals ORDER BY year')]
        initial_targets={r[0]:r[1] for r in initial_goals}
        preserve_goal=not synthetic and bool(initial_goals)
        preserved={table:set(tuple(r) for r in store.connection.execute('SELECT * FROM '+table))
                   for table in ('activities','strava_api_sources','strava_stream_sources')}
        v1=[tuple(r) for r in store.connection.execute("SELECT * FROM performance_history WHERE policy='virtual-native-power-v1' ORDER BY activity_id")]
    observed=[]
    def capture(store,client):
        result=sync(store,client);observed.append(result);return result
    def start(port=0):
        server=create_server(root,port,settings_factory=factory)
        thread=threading.Thread(target=server.serve_forever);thread.start();return server,thread
    def stop(server,thread):server.shutdown();thread.join();server.server_close()
    server,thread=start();port=server.server_port;base=f'http://127.0.0.1:{port}'
    def run(code):
        return browser('async(page)=>{const base='+json.dumps(base)+";const check=(v,m)=>{if(!v)throw new Error(m);};"+code+'}',session)
    answers=[];goal_verified=False;failure_verified=False
    try:
        if synthetic:
            run("await page.goto(base+'/settings');await page.waitForSelector('#target-miles');return true;")
        if not skip_sync:
            with patch('rideworks.settings.sync',side_effect=capture):
                run("""await page.goto(base+'/settings');await page.waitForSelector('#target-miles');
                  await page.getByRole('button',{name:'Sync now',exact:true}).click();await page.waitForSelector('#performance-sync-outcome');
                  check(!(await page.locator('#performance-sync-outcome').textContent()).includes('incomplete'),'Normal sync convergence');
                  await page.goto(base+'/');await page.waitForSelector('#dashboard-data',{state:'attached'});
                  check(await page.locator('.performance-update').count()===0,'Routine banner');return true;""")
            assert len(observed)==1 and observed[0]['performance_update'] in ('updated','current')
        else:
            run("""await page.goto(base+'/settings');await page.waitForSelector('#target-miles');
              await page.goto(base+'/');await page.waitForSelector('#dashboard-data',{state:'attached'});
              check(await page.locator('.performance-update').count()===0,'Routine banner');return true;""")
        for zone in ('America/Los_Angeles','Asia/Tokyo'):
            data=run("""const context=await page.context().browser().newContext({timezoneId:ZONE,locale:'en-US'});
              const local=await context.newPage();try{
                await local.goto(base+'/');await local.waitForSelector('#dashboard-data',{state:'attached'});
                check(JSON.parse(await local.locator('#dashboard-data').textContent()).timezone==='America/Los_Angeles','Default athlete calendar');
                await local.goto(base+'/?home_tz='+encodeURIComponent(ZONE));await local.waitForSelector('#dashboard-data',{state:'attached'});
                const data=JSON.parse(await local.locator('#dashboard-data').textContent());
                check(data.timezone===ZONE,'Explicit timezone aggregation');
                const originals=GOALS;check(data.target_miles===(originals[data.year]??null),'Hidden default or replaced goal');
                check(await local.locator('.home-recent-row').count()===Math.min(7,data.diagnostics.cycling_activities),'Recent seven cycling Activities');
                check(await local.locator('.home-recent-row td[data-label="Ride"] span').count()===0,'Recent rides show title only');
                check(!(await local.locator('.next-recommended').textContent()).includes('Provisional'),'No provisional Home recommendation commentary');
                if(data.target_miles===null)check((await local.locator('.home-goal-progress').textContent()).includes('Set annual goal'),'No-goal path');
                if(data.goal){
                  const weekly=(data.goal.target_miles*7/data.goal.calendar_days_in_year).toFixed(1);
                  const goalText=await local.locator('.home-goal-progress').textContent();
                  check(goalText.includes('target pace ('+weekly+' mi/week)'),'Annual target pace uses actual goal and year length');
                  check(!goalText.includes('calendar pace'),'Old annual pace wording removed');
                }
                check(await local.locator('#home-ytd').count()===0,'Duplicate annual card');
                check((await local.locator('#home-this-week strong').textContent())===(data.this_week.miles===null?'Unavailable':data.this_week.miles.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})+' mi'),'Actual This Week Miles');
                check(await local.locator('.home-summary .home-quick-fact').count()===4,'Four compact quick facts');
                check(await local.locator('#home-recent-mileage #home-this-week').count()===1&&await local.locator('#home-recent-mileage #home-last7').count()===1,'Both submetrics inside Recent Mileage');
                const last7=data.last7.miles===null?'Unavailable':data.last7.miles.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})+' mi';
                check(await local.locator('#home-last7 strong').textContent()===last7,'Last 7 Days value');
                check(await local.locator('#home-mileage-chart [data-week]').count()===12,'Weekly buckets');
                for(const row of data.recent){
                  check(await local.locator('.home-recent-row[data-activity-id="'+row.activity_id+'"] a').getAttribute('href')==='/activities/'+row.activity_id,'Recent review link');
                  const expected=row.average_power===null?'Unavailable':row.average_power.toLocaleString('en-US',{maximumSignificantDigits:6})+' W';
                  check(await local.locator('.home-recent-row[data-activity-id="'+row.activity_id+'"] .home-avg-power').textContent()===expected,'Avg Pwr table');
                }
                await local.getByRole('link',{name:'View all Activities',exact:true}).click();await local.waitForSelector('.history-filters');
                check(new URL(local.url()).pathname==='/activities','Activities route');
                const links=await local.locator('.activity-row').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
                check(data.recent.every(r=>links.includes('/activities/'+r.activity_id)),'Recent Activities browser evidence');
                if(data.recent.length){
                  await local.getByLabel('Title search',{exact:true}).fill(data.recent[0].title.toUpperCase());
                  await local.getByRole('button',{name:'Apply',exact:true}).click();
                  check(await local.locator('.activity-row[href="/activities/'+data.recent[0].activity_id+'"]').count()===1,'Title search');
                  await local.getByLabel('Title search',{exact:true}).fill('');
                  await local.getByRole('combobox',{name:'Sort',exact:true}).selectOption('oldest');
                  await local.getByRole('button',{name:'Apply',exact:true}).click();
                  const first=await local.locator('.activity-row').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
                  if(await local.locator('a[rel="next"]').count()){
                    check(first.length===30,'Bounded browser page');await local.locator('a[rel="next"]').click();
                    const second=await local.locator('.activity-row').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
                    check(second.length===30&&second.every(id=>!first.includes(id)),'Pagination disjoint');
                    await local.locator('a[rel="prev"]').click();
                    check(JSON.stringify(await local.locator('.activity-row').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href'))))===JSON.stringify(first),'Previous page state');
                  }
                }
                await local.goto(base+'/?q=synthetic&sort=oldest&tz='+encodeURIComponent(ZONE));await local.waitForSelector('.history-filters');
                check(new URL(local.url()).pathname==='/activities','Old browser bookmark redirect');
                await local.goto(base+'/performance');
                const points=JSON.parse(await local.locator('#performance-points').textContent());
                const view=JSON.parse(await local.locator('#performance-view').textContent());
                for(const name of ['current','latest']){
                  const index=view.summaries[name];check((index===null?null:points[index].activity_id)===(data.performance[name]?.activity_id??null),'Performance summary reference');
                }
                return data;
              }finally{await context.close();}
            """.replace('ZONE',json.dumps(zone)).replace('GOALS',json.dumps(initial_targets)))
            with Store(root) as store:answers.append(independent(store,data))
        calendar_checks=[]
        with Store(root) as store:
            for stamp in ('2026-01-01T00:30:00+00:00','2026-01-01T12:00:00+00:00','2024-03-01T18:00:00+00:00'):
                for zone in ('America/Los_Angeles','Asia/Tokyo'):
                    check=independent(store,dashboard(store,zone,as_of=datetime.fromisoformat(stamp)))
                    calendar_checks.append(dict(timezone=zone,year=check['year'],periods_verified=check['periods_independently_verified'],
                        performance_event_times_verified=check['performance_event_times_verified']))
        if not preserve_goal:
            run("""await page.setViewportSize({width:1448,height:1086});await page.goto(base+'/settings');await page.waitForSelector('#target-miles');
          await page.locator('#target-miles').fill('1234.50');await page.getByRole('button',{name:'Save annual goal',exact:true}).click();
          await page.waitForSelector('#target-miles');check((await page.locator('#annual-goal-state').textContent()).includes('1234.50'),'Explicit goal retained');return true;""")
        goal_data=run("await page.goto(base+'/');await page.waitForSelector('#dashboard-data',{state:'attached'});return JSON.parse(await page.locator('#dashboard-data').textContent());")
        with Store(root) as store:answers.append(independent(store,goal_data))
        from decimal import Decimal
        display_target=format(Decimal(goal_data['target_miles']),',f')
        run("""check((await page.locator('.home-goal-progress').textContent()).includes(TARGET),'Goal progress target');
          check(await page.locator('#annual-mileage-progress').count()===1,'Mileage progress');
          check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Desktop overflow');
          await page.screenshot({path:DESKTOP,fullPage:true});
          await page.setViewportSize({width:390,height:844});check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Phone overflow');
          await page.screenshot({path:PHONE,fullPage:true});return true;
        """.replace('TARGET',json.dumps('Annual target: '+display_target+' mi')).replace('DESKTOP',json.dumps('output/playwright/p3-01-'+('synthetic' if synthetic else 'live')+'-desktop.png'))
           .replace('PHONE',json.dumps('output/playwright/p3-01-'+('synthetic' if synthetic else 'live')+'-phone.png')))
        tooltip_checks=run("""const data=JSON.parse(await page.locator('#dashboard-data').textContent());
          const chart=page.locator('#home-mileage-chart');
          check(await chart.locator('title,[title]').count()===0,'Delayed native mileage tooltip');
          check(await page.locator('#home-ytd').count()===0,'Duplicate annual goal card');
          const weekly=value=>value===null?'Unavailable':value.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})+' mi';
          const expected=data.goal?.needed_miles_per_week??null;
          const maximum=Math.max(0,...data.weekly_goal.flatMap(w=>[w.bar_miles,w.needed_miles_per_week]).filter(v=>v!==null))||1;
          check(await page.locator('#needed-weekly').textContent()==='Needed average: '+(expected===null?'Unavailable':weekly(expected)+'/week'),'Needed weekly display');
          const bars=chart.locator('[data-week]');check(await bars.count()===12,'Twelve chart bars');
          for(let i=0;i<12;i++){
            check(await bars.nth(i).getAttribute('data-bar-kind')==='actual','All bars are actual');
            check(await bars.nth(i).getAttribute('data-mileage-value')===weekly(data.weekly_goal[i].bar_miles),'Bar mileage');
            const geometry=await bars.nth(i).locator('.home-mileage-bar').evaluate(el=>({y:Number(el.getAttribute('y')),height:Number(el.getAttribute('height'))}));
            const height=120*(data.weekly_goal[i].bar_miles??0)/maximum;
            check(Math.abs(geometry.height-height)<0.001&&Math.abs(geometry.y-(140-height))<0.001,'Bar source geometry');
            const required=data.weekly_goal[i].needed_miles_per_week;
            const marker=chart.locator('[data-needed-week="'+data.weekly_goal[i].start+'"]');
            if(required===null)check(await marker.count()===0,'Unavailable required point');
            else {
              check(await marker.getAttribute('data-mileage-value')===weekly(required),'Required point value');
              const geometry=await marker.locator('.home-needed-point').evaluate(el=>({x:Number(el.getAttribute('cx')),y:Number(el.getAttribute('cy'))}));
              check(geometry.x===58+i*45&&Math.abs(geometry.y-(140-120*required/maximum))<0.001,'Required point source geometry');
            }
          }
          check(await bars.last().getAttribute('data-mileage-value')===weekly(data.this_week.miles),'Current bar matches This Week Miles');
          const point=chart.locator('[data-needed-week]').last();
          check(await point.getAttribute('data-mileage-value')===weekly(expected),'Current line endpoint');
          check(await chart.locator('.home-mileage-current').count()===1,'Distinct partial-week actual bar');
          check((await page.locator('#home-this-week strong').textContent())===weekly(data.this_week.miles),'Current card/bar agreement');
          check((await page.locator('.home-mileage-legend').textContent()).includes('Bars = actual miles')&&(await page.locator('.home-mileage-legend').textContent()).includes('Line = needed average/week'),'Actual/required legend');
          let checks=0;
          for(const width of [1448,390]){
            await page.setViewportSize({width,height:1086});
            check(await page.evaluate(()=>document.documentElement.scrollWidth===document.documentElement.clientWidth),'Responsive width');
            const week=await page.locator('#home-this-week').boundingBox(),last7=await page.locator('#home-last7').boundingBox();
            if(width===1448)check(Math.abs(week.y-last7.y)<1&&last7.x>=week.x+week.width,'Desktop submetrics side by side');
            else check(Math.abs(week.y-last7.y)<1&&last7.x>=week.x+week.width,'Phone mileage facts in compact 2 by 2 matrix');
            check(await page.locator('.home-summary .home-quick-fact').count()===4,'All four quick facts retained');
            const items=chart.locator('[data-mileage-value]');
            for(let i=0;i<await items.count();i++){
              const immediate=await items.nth(i).evaluate(el=>{
                const tip=document.querySelector('#mileage-tooltip');
                el.dispatchEvent(new PointerEvent('pointerenter',{clientX:100,clientY:100}));
                const enter=!tip.hidden&&tip.textContent===el.dataset.mileageValue;
                el.dispatchEvent(new PointerEvent('pointermove',{clientX:130,clientY:140}));
                const move=!tip.hidden&&tip.textContent===el.dataset.mileageValue;
                el.dispatchEvent(new PointerEvent('pointerleave'));
                const leave=tip.hidden;
                el.focus();const focus=!tip.hidden&&tip.textContent===el.dataset.mileageValue;
                el.blur();return {enter,move,leave,focus,blur:tip.hidden,text:el.dataset.mileageValue};
              });
              check(immediate.enter&&immediate.move&&immediate.leave&&immediate.focus&&immediate.blur,'Immediate pointer/focus lifecycle');
              check(/^([\\d,]+\\.\\d mi|Unavailable)$/.test(immediate.text),'Mileage-only tooltip');checks++;
            }
            // The required-line point can overlap the group's bounding-box
            // center. Hover the bar's own hit area away from that point.
            const barHit=bars.last().locator('.home-mileage-hit');
            const barBounds=await barHit.boundingBox();
            await barHit.hover({position:{x:1,y:barBounds.height-2}});
            check(await page.locator('#mileage-tooltip').isVisible(),'Actual pointer hover');
            check(await page.locator('#mileage-tooltip').textContent()===weekly(data.this_week.miles),'Actual bar hover value');
            const tip=await page.locator('#mileage-tooltip').boundingBox();
            check(tip.x>=0&&tip.x+tip.width<=await page.evaluate(()=>document.documentElement.clientWidth),'Tooltip clipping');
            await page.mouse.move(0,0);check(await page.locator('#mileage-tooltip').isHidden(),'Actual leave');
            await point.hover();check(await page.locator('#mileage-tooltip').isVisible(),'Actual required point hover');
            check(await page.locator('#mileage-tooltip').textContent()===weekly(expected),'Actual point value');
            await page.mouse.move(0,0);check(await page.locator('#mileage-tooltip').isHidden(),'Actual point leave');
            await bars.first().focus();await page.keyboard.press('Tab');
            check(await page.locator('#mileage-tooltip').textContent()===await page.evaluate(()=>document.activeElement.dataset.mileageValue),'Keyboard tab value');
            await page.keyboard.press('Escape');check(await page.locator('#mileage-tooltip').isHidden(),'Keyboard dismissal');
          }
          await page.setViewportSize({width:1448,height:1086});return checks;
        """)
        stop(server,thread);server,thread=start(port)
        restarted=run("await page.reload();await page.waitForSelector('#dashboard-data',{state:'attached'});return JSON.parse(await page.locator('#dashboard-data').textContent());")
        for name in ('ytd','last7','prior7','weeks','this_week','weekly_goal','goal','target_miles'):assert restarted[name]==goal_data[name]
        if not preserve_goal:
            run("""await page.goto(base+'/settings');await page.waitForSelector('#target-miles');
              check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Settings phone overflow');
              await page.locator('#target-miles').fill('5678.25');await page.getByRole('button',{name:'Save annual goal',exact:true}).click();
              await page.waitForSelector('#target-miles');check((await page.locator('#annual-goal-state').textContent()).includes('5678.25'),'Goal update');
              await page.getByRole('button',{name:'Clear annual goal',exact:true}).click();await page.waitForSelector('#target-miles');
              check((await page.locator('#annual-goal-state').textContent()).includes('No annual target set'),'Clear goal');
              await page.goto(base+'/');await page.waitForSelector('#dashboard-data',{state:'attached'});
              check(JSON.parse(await page.locator('#dashboard-data').textContent()).target_miles===null,'No goal after clear');return true;""")
            goal_verified=True
        if synthetic:
            with Store(root) as store:
                saved=[tuple(r) for r in store.connection.execute('SELECT * FROM performance_history ORDER BY activity_id,policy')]
                checkpoint=store.connection.execute('SELECT successful_at FROM strava_sync_state').fetchone()[0]
                source_count=store.connection.execute('SELECT COUNT(*) FROM strava_api_sources').fetchone()[0]
            observations[1]['name']='Synthetic changed Virtual Ride'
            with patch('rideworks.performance.evaluate',side_effect=RideWorksError('synthetic failure')),patch('rideworks.settings.sync',side_effect=capture):
                run("""await page.goto(base+'/settings');await page.waitForSelector('#target-miles');
                  await page.getByRole('button',{name:'Sync now',exact:true}).click();await page.waitForSelector('#performance-sync-outcome');
                  check((await page.locator('#performance-sync-outcome').textContent()).includes('incomplete'),'Failure outcome');
                  await page.goto(base+'/');await page.waitForSelector('#dashboard-data',{state:'attached'});
                  check(await page.locator('.performance-update').count()===1,'Home exception banner');
                  check(await page.getByRole('button',{name:'Retry Performance update',exact:true}).count()===1,'Home retry action');return true;""")
            with Store(root) as store:
                assert saved==[tuple(r) for r in store.connection.execute('SELECT * FROM performance_history ORDER BY activity_id,policy')]
                assert store.connection.execute('SELECT successful_at FROM strava_sync_state').fetchone()[0]>=checkpoint
                assert store.connection.execute('SELECT COUNT(*) FROM strava_api_sources').fetchone()[0]==source_count+1
            stop(server,thread);server,thread=start(port)
            run("await page.reload();await page.waitForSelector('#dashboard-data',{state:'attached'});check(await page.locator('.performance-update').count()===1,'Restart exception');return true;")
            with patch('rideworks.settings.sync',side_effect=capture):
                run("""await page.goto(base+'/settings');await page.waitForSelector('#target-miles');
                  await page.getByRole('button',{name:'Sync now',exact:true}).click();await page.waitForSelector('#performance-sync-outcome');
                  check((await page.locator('#performance-sync-outcome').textContent()).includes('Performance updated'),'Later unchanged sync recovery');
                  await page.goto(base+'/');await page.waitForSelector('#dashboard-data',{state:'attached'});
                  check(await page.locator('.performance-update').count()===0,'Home exception not cleared');return true;""")
            failure_verified=True
            data=run("return JSON.parse(await page.locator('#dashboard-data').textContent());")
            with Store(root) as store:answers.append(independent(store,data))
        run("await page.setViewportSize({width:1448,height:1086});return true;")
    finally:
        stop(server,thread)
        # Only remove our explicitly temporary review targets, including after failed browser checks.
        with Store(root) as store:
            if not preserve_goal:
                for row in store.connection.execute("SELECT year FROM annual_mileage_goals WHERE target_miles IN ('1234.50','5678.25')").fetchall():
                    set_annual_goal(store,row[0],None)
    with Store(root) as store:
        final_goals=[tuple(r) for r in store.connection.execute('SELECT * FROM annual_mileage_goals ORDER BY year')]
        assert final_goals==initial_goals
        after=fingerprint(store.connection)
        assert all(rows.issubset(set(tuple(r) for r in store.connection.execute('SELECT * FROM '+table))) for table,rows in preserved.items())
        assert v1==[tuple(r) for r in store.connection.execute("SELECT * FROM performance_history WHERE policy='virtual-native-power-v1' ORDER BY activity_id")]
        # Later accepted phases populate/invalidate these derived caches during
        # Home reads and the deliberate synthetic sync/failure/recovery flow.
        # They are not original source tables. Fixed-clock HOME-UI-01 parity
        # separately compares all tables when source inputs are unchanged.
        caches=('training_stress_cache','planning_classification_cache','power_curve_profiles')
        native=[k for k in before if k not in ('annual_mileage_goals','performance_history','activities','strava_sync_state',*caches) and not k.startswith(('strava_api_','strava_stream_'))]
        assert all(before[k]==after[k] for k in native)
        if originals:assert originals=={p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in store.originals.iterdir()}
        assert store.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not store.connection.execute('PRAGMA foreign_key_check').fetchall()
        artifact_count=0
        current_schema=store.connection.execute('PRAGMA user_version').fetchone()[0]
        for row in store.connection.execute('SELECT stored_path,sha256,byte_size FROM sources UNION SELECT stored_path,sha256,byte_size FROM export_snapshots'):
            assert artifact_integrity(store.data_dir/row[0])==(row[1],row[2])
            artifact_count+=1
    safe_sync=[{k:v for k,v in result.items() if k not in ('after','before')} for result in observed]
    return dict(status='passed',mode='synthetic' if synthetic else 'live',schema6_migration_accepted_tables_preserved=bool(legacy),
        schema_version=current_schema,native_export_tables_unchanged=True,originals_unchanged=True,
        migration_evidence='disposable_schema6_replay' if legacy else 'synthetic_current_schema_fixture',
        accepted_preverification_schema=initial_version if not synthetic else current_schema,
        schema6_existing_tables_replayed=len(legacy) if legacy else 0,source_observations_retained=True,
        v1_rows_unchanged=len(v1),original_artifact_hashes_verified=artifact_count,calendar_boundary_checks=calendar_checks,
        independent_checks=answers,home_activities_settings_routes=True,old_root_bookmark_redirect=True,
        goal_set_updated_cleared=goal_verified,no_goal_at_handoff=not final_goals,goal_restart_and_same_dashboard=True,
        preexisting_goals_preserved=preserve_goal,annual_goal_review_targets=initial_targets,
        desktop_phone_no_overflow=True,los_angeles_tokyo=True,recent_links_match_browser=True,
        performance_cards_match_page=True,normal_sync_reflected_on_home=not skip_sync,
        immediate_miles_only_tooltip_checks=tooltip_checks,tooltip_pointer_keyboard_desktop_phone=True,
        this_week_card_matches_current_actual_bar=True,all_bars_are_actual=True,required_line_current_endpoint_geometry=True,
        average_power_table_matches_source_payload=True,
        four_quick_facts_desktop_phone_matrix=True,
        read_only_live_rerun=skip_sync,activities_title_sort_pagination_verified=True,
        exception_failure_restart_later_sync_verified=failure_verified,
        sync_results=safe_sync,integrity=True,foreign_keys=True,phase_4_5_6_implemented=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--data-dir',type=Path);mode.add_argument('--synthetic-dir',type=Path)
    parser.add_argument('--baseline',type=Path);parser.add_argument('--session',default='rideworks-p3-01');parser.add_argument('--output',type=Path);parser.add_argument('--skip-sync',action='store_true')
    args=parser.parse_args()
    try:result=verify(args.synthetic_dir or args.data_dir,args.session,baseline=args.baseline,synthetic=bool(args.synthetic_dir),skip_sync=args.skip_sync)
    except Exception as error:
        print('Dashboard Chromium verification stopped ('+type(error).__name__+'); inspect ignored browser evidence privately.',file=sys.stderr)
        raise SystemExit(1) from None
    if args.output:
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status=result['status'],mode=result['mode'],aggregate_output_written=True)))
    else:print(json.dumps(result,indent=2))
