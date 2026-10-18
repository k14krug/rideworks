#!/usr/bin/env python3
"""Actual Chromium API chart/source/timing checks; private routes stay local."""
import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys
import threading
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rideworks.analysis import analyze_activity
from rideworks.performance import performance_history
from datetime import timedelta
from rideworks.store import Store
from rideworks.web import create_server, duration, distance, sensor
from rideworks.strava import TokenFile
from rideworks.strava_streams import enrich
from compare_rideworks_strava_streams import fingerprint, independent_best
from verify_rideworks_strava_settings_ui import browser


def verify(data_dir,links,session,port=8774,*,live=False):
    with Store(data_dir) as store:
        tables_before=fingerprint(store.connection)
        originals_before={p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in store.originals.iterdir()}
        baseline=performance_history(store)
        current=next(s for s in store.strava_stream_evidence(links['newest'].split('/')[-1]) if s['is_current'])
        stamp=datetime.fromisoformat(current['start_date'].replace('Z','+00:00'))
        native=analyze_activity(store,links['overlap'].split('/')[-1])
        native_points=len(native['native_records']);best=native['best_20_minute_power']['rounded_watts']
        offsets=current['streams']['time']['data']
        power=current['streams'].get('watts',{}).get('data',[None]*len(offsets))
        hr=current['streams'].get('heartrate',{}).get('data',[None]*len(offsets))
        expected=[dict(sample_index=i,time_offset=t,power=power[i],heart_rate=hr[i]) for i,t in enumerate(offsets)]
        graph_checks=[]
        for route in links['api_only']:
            observed=next(s for s in store.strava_stream_evidence(route.split('/')[-1]) if s['is_current'])
            times=observed['streams']['time']['data']
            watts=observed['streams'].get('watts',{}).get('data',[None]*len(times))
            hearts=observed['streams'].get('heartrate',{}).get('data',[None]*len(times))
            samples=[dict(sample_index=i,time_offset=t,power=watts[i],heart_rate=hearts[i]) for i,t in enumerate(times)]
            summary=next(e['summary']['values'] for e in store.get_activity(route.split('/')[-1])['sources']
                         if e['source']['kind']=='strava_api' and e['source']['is_current'])
            graph_checks.append(dict(route=route,count=len(times),first=times[0],last=times[-1],
                power_count=sum(v is not None for v in watts),hr_count=sum(v is not None for v in hearts),
                best20=independent_best(times,watts),
                performance_eligible=any(p['activity_id']==route.split('/')[-1] for p in baseline['points']),
                cards=[duration(summary.get('elapsed_time')),distance(summary.get('distance')),
                       sensor(summary.get('average_watts'),'W')],
                payload_hash=sha256(json.dumps(samples,separators=(',',':')).encode()).hexdigest()))
            if graph_checks[-1]['performance_eligible']:
                current_point=next(p for p in baseline['points'] if p['activity_id']==route.split('/')[-1])
                end=datetime.fromisoformat(current_point['start_time']);start=end-timedelta(days=42)
                previous=[p for p in baseline['points'] if p['activity_id']!=current_point['activity_id'] and p['absolute_time'] and start<datetime.fromisoformat(p['start_time'])<end]
                winner=min(previous,key=lambda p:(-p['average_watts'],datetime.fromisoformat(p['start_time']),p['activity_id']),default=None)
                graph_checks[-1]['prior_route']='/activities/'+winner['activity_id'] if winner else None
                graph_checks[-1]['current_watts']=current_point['rounded_watts']
    expected_hash=sha256(json.dumps(expected,separators=(',',':')).encode()).hexdigest()
    base=f'http://127.0.0.1:{port}'
    def run(code):
        return browser('async(page)=>{const base='+json.dumps(base)+";const check=(v,m)=>{if(!v)throw new Error(m);};"+code+'}',session)
    def start():
        server=create_server(data_dir,port);thread=threading.Thread(target=server.serve_forever);thread.start();return server,thread
    def stop(server,thread):server.shutdown();thread.join();server.server_close()
    server,thread=start()
    try:
        run('''
          await page.goto(base+NEWEST);await page.waitForSelector('.chart-power',{state:'attached'});
          check(await page.locator('#native-records').count()===0,'API evidence became native');
          const text=await page.locator('.chart-panel .source-caption').first().textContent();check(text.includes('Strava API stream evidence'),'Chart label');
          const samples=JSON.parse(await page.locator('#api-stream-samples').textContent());
          check(samples.length===COUNT,'Returned samples dropped/invented');
          const digest=await page.evaluate(async()=>{const samples=JSON.parse(document.querySelector('#api-stream-samples').textContent);
            const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(samples)));
            return [...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');});
          check(digest===HASH,'Returned source values/order differ in browser payload');
          check(samples[0].time_offset===FIRST&&samples.at(-1).time_offset===LAST,'Returned offsets altered');
          check(await page.locator('.chart-power').getAttribute('data-api-points')===String(POWER_COUNT),'Power samples changed');
          check(await page.locator('.chart-hr').getAttribute('data-api-points')===String(HR_COUNT),'HR samples changed');
          check(await page.locator('[data-native-points]').count()===0,'API points labelled native');
          await page.locator('#chart-svg').focus();await page.keyboard.press('Home');
          check(await page.locator('#sample-readout').getAttribute('data-sample-index')==='0','API inspection origin');
          await page.keyboard.press('End');check(await page.locator('#sample-readout').getAttribute('data-sample-index')===String(COUNT-1),'API inspection final sample');
          await page.locator('.stream-provenance summary').first().click();
          check((await page.locator('.stream-provenance').textContent()).includes('original_size'),'Metadata provenance');
          check((await page.locator('.stream-provenance').textContent()).includes('Retrieved at'),'Retrieval provenance');
          await page.locator('.stream-provenance summary').first().click();
          await page.screenshot({path:'output/playwright/strava-004-api-desktop.png',fullPage:true});
          await page.setViewportSize({width:390,height:844});check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'API phone overflow');
          await page.screenshot({path:'output/playwright/strava-004-api-phone.png',fullPage:true});
          await page.goto(base+OVERLAP);await page.waitForSelector('.chart-power',{state:'attached'});
          check(await page.locator('#api-stream-samples').count()===0,'FIT graph displaced');
          check(JSON.parse(await page.locator('#native-records').textContent()).length===NATIVE_COUNT,'Native chart changed');
          check(await page.locator('.best-value').textContent()===BEST+' W','FIT best20 changed');
          check(await page.locator('.stream-provenance').count()>=1,'Additional overlap evidence absent');
          check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'FIT phone overflow');return true;
        '''.replace('NEWEST',json.dumps(links['newest'])).replace('OVERLAP',json.dumps(links['overlap']))
          .replace('NATIVE_COUNT',str(native_points)).replace('POWER_COUNT',str(sum(v is not None for v in power)))
          .replace('HR_COUNT',str(sum(v is not None for v in hr))).replace('COUNT',str(len(offsets)))
          .replace('HASH',json.dumps(expected_hash)).replace('FIRST',str(offsets[0])).replace('LAST',str(offsets[-1])).replace('BEST',str(best)))
        for zone in ('America/Los_Angeles','Asia/Tokyo'):
            day=stamp.astimezone(ZoneInfo(zone)).date().isoformat()
            run('''
              const context=await page.context().browser().newContext({timezoneId:ZONE,locale:'en-US'});
              const local=await context.newPage();try{
                await local.goto(base+NEWEST);await local.waitForSelector('.chart-power',{state:'attached'});
                check(await local.locator('.ride-meta time').getAttribute('data-local-day')===DAY,'API chart local date');
                check(!(await local.locator('.ride-meta time').textContent()).includes('GMT'),'Compact chart date suffix');
                await local.locator('#chart-svg').focus();await local.keyboard.press('Home');
                check(!(await local.locator('#sample-readout').textContent()).includes('Invalid Date'),'API absolute mapping');
              }finally{await context.close();}return true;
            '''.replace('ZONE',json.dumps(zone)).replace('NEWEST',json.dumps(links['newest'])).replace('DAY',json.dumps(day)))
        stop(server,thread);server,thread=start()
        run('''
          await page.setViewportSize({width:1448,height:1086});await page.goto(base+NEWEST);await page.waitForSelector('.chart-power',{state:'attached'});
          check(await page.locator('#api-stream-samples').count()===1,'Restart lost API chart');
          await page.goto(base+'/performance');
          check(JSON.parse(await page.locator('#performance-points').textContent()).length===ELIGIBLE,'Trusted cohort changed');
          if(LIVE){
            await page.getByRole('button',{name:'Trend + rides',exact:true}).click();
            const data=JSON.parse(await page.locator('#performance-points').textContent());
            const index=data.findIndex(p=>'/activities/'+p.activity_id===NEWEST);check(index>=0,'API Performance point absent');
            const dot=page.locator('.performance-point[data-point-index="'+index+'"]');await dot.hover();
            check((await page.locator('#performance-point-context').textContent()).includes('API stream Source ID'),'Performance API source provenance');
            check(!(await page.locator('#performance-point-context').textContent()).includes('Extraction ID'),'Fake API extraction context');
            check((await page.locator('#performance-point-context').textContent()).includes('Returned-offset start'),'Performance API offset provenance');
            await page.getByRole('button',{name:'Monthly best',exact:true}).click();
            check(await page.locator('.performance-period-best').count()>0,'Monthly view');
            await page.getByRole('button',{name:'Yearly best',exact:true}).click();
            check(await page.locator('.performance-period-best').count()>0,'Yearly view');
            await page.getByRole('button',{name:'Rolling 42-day',exact:true}).click();
          }
          await page.goto(base+'/settings');check(await page.locator('#strava-connection').textContent()==='Connected','Restart lost connection');
          check(await page.locator('.performance-update').count()===0,'Streams staled Performance');
          for(const graph of GRAPHS){
            await page.goto(base+graph.route);await page.waitForSelector('.chart-power',{state:'attached'});
            check(await page.locator('#native-records').count()===0,'API graph claimed native');
            check(!(await page.locator('body').textContent()).includes('Trusted Performance'),'Absolute quality label');
            check(await page.locator('.performance-update').count()===0,'Current ineligible ride left a banner');
            check(await page.locator('.recent-context').count()===(graph.performance_eligible?1:0),'V2 six-week context eligibility');
            if(graph.performance_eligible){
              check(await page.locator('#recent-current-watts').textContent()===graph.current_watts+' W','Six-week current result');
              if(graph.prior_route)check(await page.locator('#recent-prior-activity').getAttribute('href')===graph.prior_route,'Independent six-week prior winner');
              check((await page.locator('#recent-context-details').textContent()).includes('Strava API stream'),'Six-week API provenance');
            }
            check((await page.locator('.chart-panel .source-caption').first().textContent()).includes('Strava API stream evidence'),'API graph source label');
            check(JSON.stringify(await page.locator('.metrics .metric strong').allTextContents())===JSON.stringify(graph.cards),'Summary card evidence');
            check(await page.locator('.metrics').evaluate(el=>!!(el.compareDocumentPosition(document.querySelector('.chart-panel'))&Node.DOCUMENT_POSITION_FOLLOWING)),'Cards must precede chart');
            check(await page.locator('.review-layout > .review-main .chart-panel').count()===1,'Normal review hierarchy');
            const accented = await page.locator('.review-hero, .review-main > .panel, .review-sidebar > .panel, .power-curve-panel, .review-context-layout > .panel, .review-best-efforts > .panel, .review-evidence').evaluateAll(cards => cards.map(card => {
              const style = getComputedStyle(card);
              return style.borderLeftWidth === '3px' && style.borderLeftColor === 'rgb(37, 99, 235)' && style.borderLeftStyle === 'solid';
            }));
            check(accented.length >= 5 && accented.every(Boolean),'Consistent blue left accents across Activity Details cards');
            check(await page.locator('.review-layout > .review-sidebar > .ride-summary').count()===1,'Ride summary side panel');
            check((await page.locator('.ride-summary .source-caption').textContent()).includes('Strava API summary evidence'),'Ride summary source label');
            check(!(await page.locator('.ride-summary').textContent()).includes('Timer duration'),'Invented FIT timer duration');
            const summaryRows=await page.locator('.ride-summary > dl > div').evaluateAll(rows=>Object.fromEntries(rows.map(r=>[r.querySelector('dt').textContent,r.querySelector('dd').textContent])));
            check(!('Elapsed duration' in summaryRows) && !('Distance' in summaryRows) && !('Average power' in summaryRows) && !('Ascent' in summaryRows),'No duplicated or Ascent Ride Summary values');
            check(summaryRows['Best 20-minute power']===(graph.best20?graph.best20.rounded_watts+' W':'Unavailable'),'Ride Summary uses same calculated ride-local best20');
            check(await page.locator('.review-sidebar > .relative-effort-card').count()===1,'Relative Effort directly below Ride Summary');
            check((await page.locator('.relative-effort-heading').textContent()).includes('Previous 42 days'),'History-relative window visible');
            check(await page.locator('.relative-effort-card .relative-effort-overall strong').count()===1,'Relative Effort category or explicit unrated state');
            const unrated=(await page.locator('.relative-effort-overall strong').textContent()).trim()==='Not rated';
            check(await page.locator('.relative-effort-card .effort-meter').count()===(unrated?0:2),'Two slim indicator bars for rated effort');
            check(await page.locator('.provenance[open]').count()===0,'Provenance must be secondary');
            const panel=page.locator('.api-best20');
            check((await panel.textContent()).includes('RideWorks-calculated from Strava API stream evidence'),'Local best20 provenance');
            check(await panel.getAttribute('data-best20-status')===(graph.best20?'available':'unavailable'),'Local best20 availability');
            check(await panel.locator('.best-value').textContent()===(graph.best20?graph.best20.rounded_watts+' W':'Unavailable'),'Local best20 watts');
            const details=await panel.locator('details dl > div').evaluateAll(rows=>Object.fromEntries(rows.map(r=>[r.querySelector('dt').textContent,r.querySelector('dd').textContent])));
            check(details['Method/version']==='best-average-power-v1','Local best20 method');
            check(!Object.keys(details).some(k=>/record indices|native samples|window start \(UTC\)/i.test(k)),'Invented native calculation context');
            if(graph.best20){
              check(Number(details['Samples in window'])===1200,'Complete local window');
              check(Number.parseFloat(details['Unrounded average'])===graph.best20.average_watts,'Raw local average');
              check(Number(details['Returned-offset start (inclusive, seconds)'])===graph.best20.start_elapsed,'Local window start');
              check(Number(details['Returned-offset end (exclusive, seconds)'])===graph.best20.end_exclusive_elapsed,'Local window end');
              check(Number(details['Eligible windows'])===graph.best20.eligible_window_count,'Local eligible windows');
            }else check((await panel.locator('.window-context').textContent()).length>0,'Unavailable reason');
            const samples=JSON.parse(await page.locator('#api-stream-samples').textContent());
            check(samples.length===graph.count&&samples[0].time_offset===graph.first&&samples.at(-1).time_offset===graph.last,'API graph sample count/offsets');
            const digest=await page.evaluate(async()=>{const samples=JSON.parse(document.querySelector('#api-stream-samples').textContent);
              const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(samples)));
              return [...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');});
            check(digest===graph.payload_hash,'API graph values/order');
            check(await page.locator('.chart-power').getAttribute('data-api-points')===String(graph.power_count),'API graph power count');
            check(await page.locator('.chart-hr').getAttribute('data-api-points')===String(graph.hr_count),'API graph HR count');
            await page.setViewportSize({width:390,height:844});check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'API review phone overflow');
            await page.setViewportSize({width:1448,height:1086});check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'API review desktop overflow');
          }
          return true;
        '''.replace('NEWEST',json.dumps(links['newest'])).replace('ELIGIBLE',str(len(baseline['points'])))
          .replace('LIVE',str(live).lower())
          .replace('GRAPHS',json.dumps(graph_checks)))
        with Store(data_dir) as store:
            assert performance_history(store)==baseline
            actual=next(s for s in store.strava_stream_evidence(links['newest'].split('/')[-1]) if s['is_current'])
            assert actual==current
            class ReuseOnly:
                stream_requests=0
                def streams(self,*args):raise AssertionError('Idempotent review rerun requested streams')
            identities=[r[0] for r in store.connection.execute('SELECT external_id FROM strava_api_activities WHERE activity_id IN ('+','.join('?' for _ in graph_checks)+')',
                       [g['route'].split('/')[-1] for g in graph_checks])]
            with TokenFile(data_dir).lock():reused=enrich(store,ReuseOnly(),'unused',identities)
            assert reused['stream_fetches']==0 and reused['stream_reused']==len(graph_checks)
            assert fingerprint(store.connection)==tables_before,'Review calculation changed persisted tables'
            assert originals_before=={p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in store.originals.iterdir()}
            assert store.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not store.connection.execute('PRAGMA foreign_key_check').fetchall()
        return dict(status='passed',mode='live' if live else 'synthetic',api_only_charts=len(links['api_only']),
                    complete_browser_payloads_verified=len(graph_checks),
                    source_labels_metadata=True,returned_offsets_and_samples_retained=True,power_hr_points_retained=True,
                    inspection_keyboard=True,no_native_or_absolute_trust_claim=True,fit_precedence_and_best20_unchanged=True,
                    normal_api_review_hierarchy=True,current_summary_cards_and_ride_summary=True,
                    local_best20_independently_verified=True,
                    qualifying_local_best20=sum(g['best20'] is not None for g in graph_checks),
                    unavailable_local_best20=sum(g['best20'] is None for g in graph_checks),
                    performance_eligible_api_reviews=sum(g['performance_eligible'] for g in graph_checks),
                    api_six_week_context_verified=True,exception_only_banner=True,
                    performance_api_provenance_and_views_verified=live,
                    restart_stream_requests=0,restart_reused=len(graph_checks),all_persisted_tables_unchanged=True,
                    originals_unchanged=True,integrity=True,foreign_keys=True,
                    overlap_streams_inspectable=True,los_angeles_tokyo_dates=True,desktop_phone_no_overflow=True,
                    restart_retains_graphs_and_connection=True,performance_unchanged_by_review=True,
                    performance_eligible=len(baseline['points']),performance_pending=baseline['pending'])
    finally:stop(server,thread)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True);parser.add_argument('--links',type=Path,default=Path('output/playwright/strava-004-review-links.json'))
    parser.add_argument('--session',default='rideworks-strava-004');parser.add_argument('--live',action='store_true')
    args=parser.parse_args();print(json.dumps(verify(args.data_dir,json.loads(args.links.read_text()),args.session,live=args.live),indent=2))
