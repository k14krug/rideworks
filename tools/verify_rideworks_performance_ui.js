// Actual browser acceptance; private sample metadata stays inside the browser.
async (page) => {
  const base = BASE_URL, expected = EXPECTED_COUNT;
  const check=(condition,message)=>{if(!condition)throw new Error(message);};
  await page.goto(base+'/activities');
  await page.getByRole('navigation',{name:'Main',exact:true}).getByRole('link',{name:'Performance',exact:true}).click();
  await page.waitForSelector('.performance-trend');
  const points=await page.locator('#performance-points').evaluate(node=>JSON.parse(node.textContent));
  const view=await page.locator('#performance-view').evaluate(node=>JSON.parse(node.textContent));
  check(points.length===expected,'Payload omits eligible history');
  check(await page.locator('nav a[aria-current="page"]').textContent()==='Performance','Active navigation is wrong');
  check(points.every(p=>p.classification.activity_type==='Virtual Ride'),'Excluded activity in chart');
  check(await page.locator('#native-records').count()===0,'Native streams in Performance');
  const html=await page.content();
  for(const token of ['stored_path','latitude','longitude','native_records']) check(!html.includes(token),'Private/native evidence in page');
  const verifyReadout=async p=>{
    const index=Number(await p.locator('#performance-readout').getAttribute('data-point-index'));
    check(await p.locator('#performance-activity').textContent()===points[index].title,'Source title differs');
    check(await p.locator('#performance-watts').textContent()===points[index].rounded_watts+' W','Watts differ');
    check(await p.locator('#performance-activity').getAttribute('href')==='/activities/'+points[index].activity_id,'Route differs');
    return index;
  };
  const chart=page.locator('#performance-chart');
  check(await chart.getAttribute('data-view')==='rolling'&&await chart.getAttribute('data-range')==='1yr','Wrong default view');
  check(await page.locator('[data-mode]').count()===0,'Obsolete history tabs remain');
  check(await page.locator('.performance-modes').count()===1,'Accepted PC-01 mode navigation remains');
  const future=page.locator('.performance-future');
  check(await future.getAttribute('open')===null,'Future candidates should be subordinate/collapsed');
  check((await future.textContent()).includes('not implemented features or delivery commitments'),'Future direction implies implemented features');
  check(await page.locator('.performance-point').count()===0,'Default chart is noisy ride scatter');
  check(await verifyReadout(page)===view.summaries.current,'Default selected result is not recent meaningful evidence');
  for(const key of ['current','latest','year','lifetime']) {
    const card=page.locator('[data-summary="'+key+'"]');
    check(Number(await card.getAttribute('data-point-index'))===view.summaries[key],'Summary context differs');
    check((await card.textContent()).includes(String(points[view.summaries[key]].rounded_watts)),'Summary watts missing');
  }
  const periodOracle=async (probe, fixturePoints, aggregation, cutoff, asOf)=>probe.evaluate(({points,aggregation,cutoff,asOf})=>{
    const formatter=new Intl.DateTimeFormat('en-US',{year:'numeric',month:'2-digit'});
    const candidates=points.map((p,i)=>({p,i})).filter(({p})=>{
      const stamp=Date.parse(p.absolute_time?p.start_time:p.date_key+'Z');
      return stamp>=cutoff&&stamp<=asOf;
    }).sort((a,b)=>b.p.average_watts-a.p.average_watts||a.p.date_key.localeCompare(b.p.date_key)||a.p.activity_id.localeCompare(b.p.activity_id));
    const winners=new Map();
    for(const {p,i} of candidates){
      const parts=p.absolute_time?Object.fromEntries(formatter.formatToParts(new Date(p.start_time)).map(part=>[part.type,part.value]))
        :{year:p.date_day.slice(0,4),month:p.date_day.slice(5,7)};
      const period=parts.year+(aggregation==='monthly'?'-'+parts.month:'');
      if(!winners.has(period))winners.set(period,i);
    }
    return [...winners].sort(([a],[b])=>a.localeCompare(b)).map(([period,index])=>({period,index}));
  },{points:fixturePoints,aggregation,cutoff,asOf});
  const inspectPeriodView=async (probe, fixturePoints, aggregation, cutoff, asOf)=>{
    const oracle=await periodOracle(probe,fixturePoints,aggregation,cutoff,asOf);
    const actual=await probe.locator('.performance-period-best').evaluateAll(nodes=>nodes.map(n=>({period:n.dataset.period,index:Number(n.dataset.pointIndex)})));
    check(JSON.stringify(actual)===JSON.stringify(oracle),'Period winners differ from independent raw maxima');
    check(await probe.locator('.performance-period-stem, #performance-chart rect').count()===0,'Period series uses stems or bars');
    const segments=await probe.locator('.performance-period-line').evaluateAll(nodes=>nodes.flatMap(node=>
      [...node.getAttribute('d').matchAll(/([ML])([^ML]+)/g)].map(match=>({command:match[1],coords:match[2].trim().split(',').map(Number)}))));
    const marks=await probe.locator('.performance-period-best').evaluateAll(nodes=>nodes.map(node=>[Number(node.getAttribute('cx')),Number(node.getAttribute('cy'))]));
    check(segments.length===oracle.length,'Period line omits markers or connects extra observations');
    oracle.forEach((item,i)=>{
      let adjacent=false;
      if(i){
        const previous=oracle[i-1].period;
        const next=new Date(previous+(aggregation==='monthly'?'-01T00:00:00Z':'-01-01T00:00:00Z'));
        if(aggregation==='monthly')next.setUTCMonth(next.getUTCMonth()+1);else next.setUTCFullYear(next.getUTCFullYear()+1);
        adjacent=next.toISOString().slice(0,aggregation==='monthly'?7:4)===item.period;
      }
      check(segments[i].command===(adjacent?'L':'M'),'Line bridges a missing calendar period or breaks consecutive evidence');
      check(segments[i].coords.every((coordinate,j)=>Math.abs(coordinate-marks[i][j])<.000001),'Line does not follow contributing ride markers');
    });
    const selected=Number(await probe.locator('#performance-readout').getAttribute('data-point-index'));
    if(oracle.length)check(selected===oracle.at(-1).index,'Period view does not default to recent meaningful best');
    else {
      check(await probe.locator('#performance-readout').getAttribute('data-point-index')==='','Empty period invents a selected result');
      check(await probe.locator('#performance-activity').getAttribute('href')===null,'Empty range opens an invented Activity');
      check(await probe.locator('#performance-watts').textContent()==='Unavailable','Empty range is fabricated zero');
    }
    return oracle;
  };
  for(const key of ['3mo','6mo','1yr','3yr','all']) {
    await page.locator('[data-range="'+key+'"]').click();
    const cutoff=key==='all'?-Infinity:Date.parse(view.range_starts[key]);
    const expectedCount=points.filter(p=>Date.parse(p.start_time)>=cutoff&&Date.parse(p.start_time)<=Date.parse(view.as_of)).length;
    for(const aggregation of ['rolling','monthly','yearly']) {
      await page.locator('.performance-views [data-view="'+aggregation+'"]').click();
      check(Number(await chart.getAttribute('data-visible-rides'))===expectedCount,'Range count differs');
      if(aggregation==='rolling')check(await page.locator('.performance-trend').count()===1,'Range loses primary trend');
      else {
        const oracle=await inspectPeriodView(page,points,aggregation,cutoff,Date.parse(view.as_of));
        await chart.focus();await page.keyboard.press('Home');check(await verifyReadout(page)===oracle[0].index,'Period Home failed');
        await page.keyboard.press('End');check(await verifyReadout(page)===oracle.at(-1).index,'Period End failed');
        await page.keyboard.press('Enter');await page.waitForURL(base+'/activities/'+points[oracle.at(-1).index].activity_id);
        await page.goBack();await page.waitForSelector('.performance-period-best');
        check(await chart.getAttribute('data-view')===aggregation&&await chart.getAttribute('data-range')===key,'Range/View state lost on back');
        await page.locator('[data-evidence="rides"]').click();
        check(await page.locator('.performance-point').count()===expectedCount,'Period view omits supporting rides');
        await inspectPeriodView(page,points,aggregation,cutoff,Date.parse(view.as_of));
        await page.locator('[data-evidence="trend"]').click();
      }
    }
  }
  await page.getByText('Eligible ride results',{exact:false}).last().click();
  const seen=new Set();
  while(true) {
    const indexes=await page.locator('#performance-rides tr').evaluateAll(nodes=>nodes.map(n=>Number(n.dataset.pointIndex)));
    check(indexes.length<=30,'Unbounded evidence table');indexes.forEach(i=>seen.add(i));
    if(await page.locator('#performance-rides-next').isDisabled())break;
    await page.locator('#performance-rides-next').click();
  }
  check(seen.size===expected,'Complete supporting history is not inspectable');
  await page.locator('.performance-views [data-view="rolling"]').click();
  await page.locator('[data-evidence="rides"]').click();
  check(await page.locator('.performance-point').count()===expected,'All-range ride evidence omits points');
  check(await page.locator('.performance-trend').count()===1,'Ride evidence removes primary trend');
  for(const i of [0,Math.floor(points.length/2),points.length-1]) {
    const box=await page.locator('.performance-point').nth(i).boundingBox();
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await verifyReadout(page);
  }
  await chart.focus();await page.keyboard.press('Home');check(await verifyReadout(page)===0,'Ride Home failed');
  for(let i=0;i<Math.floor(points.length/2);i++)await page.keyboard.press('ArrowRight');
  check(await verifyReadout(page)===Math.floor(points.length/2),'Middle keyboard failed');
  await page.keyboard.press('End');check(await verifyReadout(page)===points.length-1,'Ride End failed');
  await page.keyboard.press('Enter');await page.waitForURL(base+'/activities/'+points.at(-1).activity_id);
  check(await page.locator('h1').textContent()===points.at(-1).title,'Activity title differs');
  await page.goBack();await page.waitForSelector('.performance-point');
  const box=await page.locator('.performance-point').last().boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);
  const pointerRoute=await page.locator('#performance-activity').getAttribute('href');
  await page.mouse.click(box.x+box.width/2,box.y+box.height/2);await page.waitForURL(base+pointerRoute);
  await page.goBack();await page.waitForSelector('.performance-point');
  await page.getByText('Selected result provenance',{exact:true}).click();
  check((await page.locator('#performance-point-context').textContent()).includes('Extraction ID'),'Provenance missing');
  await page.getByText('Eligibility & method',{exact:true}).click();
  const policy=await page.locator('.performance-policy').textContent();
  check(policy.includes('best-average-power-v1')&&policy.includes('Outdoor Ride power remains excluded')&&policy.includes('never substitute'),'Trust explanation missing');
  const fixtureTimes=['2023-12-31T16:30:00+00:00','2024-01-01T07:30:00+00:00','2024-01-15T12:00:00+00:00',
    '2024-01-20T12:00:00+00:00','2024-02-01T07:30:00+00:00','2024-02-29T08:00:00+00:00',
    '2024-03-01T00:30:00+00:00','2024-03-01T01:00:00','2024-04-01T12:00:00+00:00','2024-06-01T00:00:00+00:00'];
  const fixtureWatts=[100,200.1,200.2,200.2,300,50,0,60,0,999];
  const fixturePoints=fixtureTimes.map((stamp,i)=>({...points[0],activity_id:'synthetic-'+i,title:'Synthetic period evidence',
    start_time:stamp,date_key:stamp.replace('+00:00',''),date_day:stamp.slice(0,10),absolute_time:i!==7,
    average_watts:fixtureWatts[i],rounded_watts:Math.floor(fixtureWatts[i]+.5)}));
  const fixtureView={...view,as_of:'2024-05-01T12:00:00+00:00',rolling:[],
    range_starts:{...view.range_starts,'3mo':'2024-02-15T00:00:00+00:00','6mo':'2024-04-15T00:00:00+00:00'}};
  for(const zone of ['America/Los_Angeles','Asia/Tokyo']) {
    const context=await page.context().browser().newContext({timezoneId:zone,viewport:{width:1448,height:1086}});
    try {
      const probe=await context.newPage();await probe.goto(base+'/performance');await probe.waitForSelector('.performance-trend');
      const index=Number(await probe.locator('#performance-readout').getAttribute('data-point-index'));
      const expectedDate=await probe.evaluate(p=>new Intl.DateTimeFormat(undefined,{year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(p.start_time)),points[index]);
      check(await probe.locator('#performance-date').textContent()===expectedDate,'Date is not browser-local');
      await probe.locator('[data-range="all"]').click();
      for(const aggregation of ['monthly','yearly']) {
        await probe.locator('.performance-views [data-view="'+aggregation+'"]').click();
        await inspectPeriodView(probe,points,aggregation,-Infinity,Date.parse(view.as_of));
      }
      let fixtureHtml=html.replace(/(<script id="performance-points" type="application\/json">)[\s\S]*?(<\/script>)/,
        (_,start,end)=>start+JSON.stringify(fixturePoints)+end).replace(/(<script id="performance-view" type="application\/json">)[\s\S]*?(<\/script>)/,
        (_,start,end)=>start+JSON.stringify(fixtureView)+end);
      // PC-01 adds curve_tz through a redirect. Keep the same fixture across
      // that query change, without intercepting /static/performance.js.
      await probe.route(url=>url.origin===new URL(base).origin&&url.pathname==='/performance',route=>route.fulfill({status:200,contentType:'text/html',body:fixtureHtml}));
      await probe.goto(base+'/performance');await probe.waitForSelector('#performance-chart[data-view="rolling"]');
      for(const range of ['all','3mo','6mo']) {
        await probe.locator('[data-range="'+range+'"]').click();
        for(const aggregation of ['monthly','yearly']) {
          await probe.locator('.performance-views [data-view="'+aggregation+'"]').click();
          await inspectPeriodView(probe,fixturePoints,aggregation,range==='all'?-Infinity:Date.parse(fixtureView.range_starts[range]),Date.parse(fixtureView.as_of));
        }
      }
      // Sparse periods prove real breaks: missing months, missing years, and
      // a December/January connection, using only disposable browser fixtures.
      const gapPoints=[fixturePoints[0],fixturePoints[2],fixturePoints[7]].map(p=>({...p}));
      Object.assign(gapPoints[0],{start_time:'2023-12-15T12:00:00+00:00',date_key:'2023-12-15T12:00:00',date_day:'2023-12-15'});
      for(const year of [2019,2021])gapPoints.unshift({...fixturePoints[0],activity_id:'gap-'+year,
        start_time:year+'-09-15T12:00:00+00:00',date_key:year+'-09-15T12:00:00',date_day:year+'-09-15'});
      fixtureHtml=html.replace(/(<script id="performance-points" type="application\/json">)[\s\S]*?(<\/script>)/,
        (_,start,end)=>start+JSON.stringify(gapPoints)+end).replace(/(<script id="performance-view" type="application\/json">)[\s\S]*?(<\/script>)/,
        (_,start,end)=>start+JSON.stringify(fixtureView)+end);
      await probe.goto(base+'/performance');await probe.waitForSelector('#performance-chart[data-view="rolling"]');
      await probe.locator('[data-range="all"]').click();
      for(const aggregation of ['monthly','yearly']){
        await probe.locator('.performance-views [data-view="'+aggregation+'"]').click();
        await inspectPeriodView(probe,gapPoints,aggregation,-Infinity,Date.parse(fixtureView.as_of));
        const commands=await probe.locator('.performance-period-line').getAttribute('d');
        check((commands.match(/M/g)||[]).length>1&&commands.includes('L'),'Sparse fixture did not exercise both breaks and continuity');
      }
    } finally {await context.close();}
  }
  await page.goto(base+'/performance');await page.waitForSelector('.performance-trend');
  for(const [width,height] of [[1448,1086],[1024,900],[390,844]]) {
    await page.setViewportSize({width,height});
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Responsive horizontal overflow');
    check((await chart.boundingBox()).height>=300,'Responsive chart is decorative/tiny');
    for(const aggregation of ['rolling','monthly','yearly']) {
      await page.locator('.performance-views [data-view="'+aggregation+'"]').click();
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'View horizontal overflow');
    }
  }
  await page.locator('.performance-views [data-view="rolling"]').click();
  await page.screenshot({path:'output/playwright/p2-03-performance-phone.png',fullPage:true});
  await page.setViewportSize({width:1448,height:1086});
  await page.screenshot({path:'output/playwright/p2-03-performance-desktop.png',fullPage:true});
  await page.locator('.performance-views [data-view="monthly"]').click();
  await page.screenshot({path:'output/playwright/p2-03-monthly-desktop.png',fullPage:true});
  await page.locator('.performance-views [data-view="yearly"]').click();await page.locator('[data-range="all"]').click();
  await page.screenshot({path:'output/playwright/p2-03-yearly-desktop.png',fullPage:true});
  await page.goto(base+'/performance');await page.waitForSelector('.performance-trend');
  return {result:'passed',browser:'Chromium',payload_eligible_results:points.length,all_range_ride_points:points.length,
    default_rolling_one_year:true,rolling_line_dominant:true,single_performance_surface:true,all_range_view_combinations:true,
    summaries_and_freshness:true,monthly_yearly_bests_independently_verified:true,synthetic_calendar_raw_tie_range_tests:true,
    monthly_yearly_lines_with_markers:true,missing_month_year_breaks_verified:true,
    supporting_rides_in_all_views:true,future_candidates_secondary:true,complete_paged_evidence:true,
    first_middle_last_pointer:true,keyboard_inspection:true,point_activity_and_back:true,
    source_title_date_watts:true,eligibility_provenance:true,local_date_zones:['America/Los_Angeles','Asia/Tokyo'],
    desktop_tablet_phone_no_overflow:true,no_native_stream_payload:true};
}
