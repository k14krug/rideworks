/* Synthetic-only Chromium contract checks. Run with playwright-cli run-code. */
async page => {
  const base=new URL(page.url()).origin, checks=[];
  const check=(ok,name)=>{checks.push(name);if(!ok)throw new Error(name);};
  const point=(d,w,id)=>({duration_seconds:d,average_watts:w,rounded_watts:w,coverage:1,
    observed_seconds:d,pause_seconds:0,estimated_seconds:0,unknown_seconds:0,result_kind:'elapsed_power',
    activity:{activity_id:id,title:'Synthetic '+id,start_time:'2026-01-01T00:00:00+00:00',absolute_time:true}});
  const series=(points,anchors)=>({points,anchors,count:points.length?1:0,start:null,end_exclusive:null});
  const sample=(ride,comparison,anchorsA,anchorsB,end,min=null)=>({mode:'activity',calendar_timezone:'UTC',pending:0,
    current_reason:null,ambiguous_durations:[],elapsed_duration:end,endpoint_coverage:.94,minimum:min,
    series:{ride:series(ride,anchorsA),six:series(comparison,anchorsB),year:series(comparison,anchorsB),all:series([],[])}});
  async function open(data,width=1000) {
    const p=await page.context().newPage();await p.setViewportSize({width,height:800});await p.goto(base+'/static/style.css');
    await p.setContent(`<html><head><link rel="stylesheet" href="${base}/static/style.css"></head><body class="activity-review-redesign"><section id="power-curve-panel" data-curve-activity="true"><p id="curve-a-bounds"></p><p id="curve-b-bounds"></p><select id="curve-b"><option value="six">Six</option><option value="year">Year</option><option value="all">All</option></select><div class="elapsed-plot" id="elapsed-plot"><svg id="power-curve-chart" tabindex="0"></svg><section id="elapsed-inspector" class="elapsed-inspector" hidden><div><strong id="elapsed-duration"></strong><span id="elapsed-delta" hidden></span><button id="elapsed-unpin" hidden>Unpin</button></div><div id="elapsed-series-a"></div><div id="elapsed-series-b"></div><details id="elapsed-recording-details" hidden><summary>Recording details</summary><div id="elapsed-recording-content"></div></details></section></div><p id="curve-empty"></p><p id="elapsed-endpoint-status"></p><p id="curve-help"></p><span id="elapsed-announcement"></span><script id="power-curve-data" type="application/json">${JSON.stringify(data)}</script></section></body></html>`);
    await p.addScriptTag({url:base+'/static/elapsed_power_curve.js'});await p.waitForTimeout(100);return p;
  }
  let p=await open(sample([point(1,200,'one'),point(10,100,'one'),point(30,80,'one')],[point(1,190,'two'),point(10,100,'two'),point(30,90,'two')],[1,10,20,30],[1,10,20,30],30));
  check(await p.locator('#elapsed-inspector').isHidden(),'hidden preview starts unfocusable');
  let svg=p.locator('#power-curve-chart');await svg.focus();await p.keyboard.press('Home');
  let edgeBox=await p.locator('#elapsed-inspector').boundingBox(),edgePlot=await p.locator('#elapsed-plot').boundingBox();
  check(edgeBox.x>=edgePlot.x&&edgeBox.x+edgeBox.width<=edgePlot.x+edgePlot.width,'first edge inspector fits');
  check((await p.locator('#elapsed-delta').innerText()).includes('+10 W'),'positive delta');
  check((await p.locator('#elapsed-delta').getAttribute('aria-label'))==='This ride minus comparison: +10 watts','accessible delta direction');
  check(!(await p.locator('#elapsed-duration').innerText()).includes('('),'no raw seconds repetition');
  check(await p.locator('#elapsed-series-a a').count()===0,'no self link');
  check(!(await p.locator('#elapsed-series-a').innerText()).includes('Synthetic one'),'no current title');
  check((await p.locator('#elapsed-series-b a').innerText())==='Synthetic two','winner title is link');
  check(!(await p.locator('#elapsed-inspector').innerText()).includes('% observed'),'no standard coverage line');
  check(await p.locator('#elapsed-recording-details').isHidden(),'details hidden before pin');
  await p.keyboard.press('Enter');check(await p.locator('#elapsed-recording-details').isVisible(),'details available pinned');
  check(!(await p.locator('#elapsed-recording-details').getAttribute('open')),'details initially collapsed');
  await p.locator('#elapsed-recording-details summary').click();check((await p.locator('#elapsed-recording-content').innerText()).includes('100.00% observed'),'coverage in details');
  check(await p.locator('#elapsed-unpin').isVisible(),'details do not unpin');
  await svg.focus();await p.keyboard.press('Enter');
  for(let i=0;i<1;i++)await p.keyboard.press('ArrowRight');check((await p.locator('#elapsed-delta').innerText()).includes('0 W'),'zero delta');
  check(await svg.getAttribute('data-duration')==='10','decorative tick not selected as data');
  await p.keyboard.press('Enter');check(await p.locator('#elapsed-recording-details').getAttribute('open')===null,'selection change resets details');await p.keyboard.press('Enter');
  await p.keyboard.press('ArrowRight');check((await p.locator('#elapsed-series-a').innerText()).includes('Unavailable'),'unsupported anchor inspectable');check(await p.locator('#elapsed-delta').isHidden(),'unavailable result has no delta');
  const paths=await p.locator('.curve-line').evaluateAll(es=>es.map(e=>e.getAttribute('d')));check(paths.every(s=>(s.match(/M/g)||[]).length===2),'no bridge across unsupported anchor');
  await p.keyboard.press('End');check((await p.locator('#elapsed-delta').innerText()).includes('−10 W'),'negative delta');
  edgeBox=await p.locator('#elapsed-inspector').boundingBox();edgePlot=await p.locator('#elapsed-plot').boundingBox();check(edgeBox.x>=edgePlot.x&&edgeBox.x+edgeBox.width<=edgePlot.x+edgePlot.width,'last edge inspector fits');
  check(await p.locator('#elapsed-series-b a').getAttribute('href')==='/activities/two','winner link');
  const label=await p.locator('#elapsed-duration').innerText();check(label.includes('30 s'),'short endpoint exact');
  await p.close();
  p=await open(sample([point(1,100,'one')],[],[1],[],1));svg=p.locator('#power-curve-chart');await svg.focus();await p.keyboard.press('End');check((await p.locator('#elapsed-duration').innerText()).includes('1 s'),'single-point domain');check(!(await svg.innerHTML()).includes('NaN'),'single-point finite');await p.close();
  p=await open(sample([point(60.12345678,100,'one')],[],[60.12345678],[],60.12345678));svg=p.locator('#power-curve-chart');await svg.focus();await p.keyboard.press('End');check((await p.locator('#elapsed-duration').innerText()).includes('1:00.12345678'),'fractional endpoint precision');check((await svg.innerHTML()).includes('1:00.12345678'),'fractional endpoint tick');await p.close();
  p=await open(sample([point(3600,100,'one')],[point(3600,110,'two'),point(7200,90,'three')],[3600],[3600,7200],3600));svg=p.locator('#power-curve-chart');await svg.focus();await p.keyboard.press('Home');check((await p.locator('#elapsed-duration').innerText())==='1:00:00','selected endpoint with longer comparison');
  const d=await svg.evaluate(e=>({width:e.clientWidth,cx:Number(e.querySelector('.curve-anchor-a').getAttribute('cx'))}));const expected=48+Math.sqrt(.5)*(d.width-16-48);check(Math.abs(d.cx-expected)<.1,'square-root mapping');await p.keyboard.press('End');check((await p.locator('#elapsed-series-a').innerText()).includes('Unavailable'),'longer comparison no fabricated current');check((await p.locator('#elapsed-series-b').innerText()).includes('Synthetic three'),'longer comparison attribution');await p.close();
  const minimum={...point(100,94,'one'),coverage:.94,unknown_seconds:6,result_kind:'recorded_power_minimum'};
  p=await open(sample([point(60,100,'one')],[point(100,120,'two')],[60,100],[100],100,minimum));svg=p.locator('#power-curve-chart');await svg.focus();await p.keyboard.press('End');check((await p.locator('#elapsed-series-a').innerText()).includes('recorded-power minimum'),'minimum label');check(await p.locator('#elapsed-delta').isHidden(),'minimum has no delta');check(await p.locator('.curve-minimum-marker').count()>=1,'minimum marker');check((await p.locator('#elapsed-series-b').innerText()).includes('120 W'),'exact baseline shown');await p.close();
  p=await open(sample([point(60,100,'one')],[],[60,100],[],100));svg=p.locator('#power-curve-chart');check((await p.locator('#elapsed-endpoint-status').innerText()).includes('unavailable'),'unsupported endpoint visible');await svg.focus();await p.keyboard.press('End');check((await p.locator('#elapsed-series-a').innerText()).includes('Unavailable'),'unsupported endpoint inspector');await p.close();
  const a={...point(60,150,'one'),coverage:.95,observed_seconds:57,pause_seconds:2,estimated_seconds:1,unknown_seconds:2};
  const b={...point(60,120,'two'),coverage:.98,observed_seconds:59,pause_seconds:1,estimated_seconds:2,unknown_seconds:3};
  const rich=sample([a],[b],[60],[60],60);rich.series.year=series([{...point(60,110,'other'),coverage:.91,observed_seconds:55}],[60]);
  p=await open(rich);svg=p.locator('#power-curve-chart');await svg.focus();await p.keyboard.press('End');
  for(const key of ['a','b']) {const t=await p.locator('#elapsed-series-'+key).innerText();check(t.includes('Paused')&&t.includes('estimated')&&t.includes('unknown, assumed zero')&&!t.includes('% observed'),key+' conditional assumptions');}
  await p.keyboard.press('Enter');await p.locator('#elapsed-recording-details summary').click();const disclosure=await p.locator('#elapsed-recording-content').innerText();check(disclosure.includes('95.00% observed')&&disclosure.includes('98.00% observed')&&disclosure.includes('57 s observed')&&disclosure.includes('59 s observed'),'both series detail evidence');
  await p.locator('#curve-b').selectOption('year');check(await p.locator('#elapsed-recording-details').isHidden(),'period change clears disclosure');
  await svg.focus();await p.keyboard.press('End');await p.keyboard.press('Enter');check(await p.locator('#elapsed-recording-details').getAttribute('open')===null,'new pin resets disclosure');
  await p.locator('#elapsed-recording-details summary').click();const changed=await p.locator('#elapsed-recording-content').innerText();check(changed.includes('91.00% observed')&&!changed.includes('98.00% observed'),'period change removes stale details');await p.close();
  const long={...point(60,110,'long'),activity:{...point(60,110,'long').activity,title:'Synthetic long ride name '.repeat(14)}};
  p=await open(sample([point(60,100,'one')],[long],[60],[60],60));svg=p.locator('#power-curve-chart');await svg.focus();await p.keyboard.press('End');await p.keyboard.press('Enter');
  const desktop=(await p.locator('#elapsed-inspector').boundingBox()).width;check(desktop===385,'desktop inspector widened by 50 px');
  await p.locator('#elapsed-recording-details summary').click();
  for(const width of [390,320]) {await p.setViewportSize({width,height:800});await p.waitForTimeout(50);const box=await p.locator('#elapsed-inspector').boundingBox(),plot=await p.locator('#elapsed-plot').boundingBox();check(box.x>=plot.x&&box.x+box.width<=plot.x+plot.width+1&&box.y+box.height<=plot.y+plot.height+1,'expanded details fit '+width);check(plot.height-box.height>=119,'usable plot target '+width);check(await p.locator('#elapsed-inspector').evaluate(e=>e.scrollWidth<=e.clientWidth),'inspector text wraps '+width);check(!(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth)),'no page overflow '+width);check(await p.locator('#elapsed-unpin').isVisible(),'resize retains pin '+width);}
  await p.close();
  p=await open(sample([],[],[],[],null));check(await p.locator('#power-curve-chart').getAttribute('tabindex')==='-1','empty chart unfocusable');check(await p.locator('#elapsed-inspector').isHidden(),'empty hidden inspector');await p.close();
  const pending=sample([],[],[],[],null);pending.pending=1;pending.current_reason='profile_update_required';p=await open(pending);check((await p.locator('#curve-empty').innerText()).includes('update'),'pending message');await p.close();
  return {checks:checks.length,passed:checks};
}
