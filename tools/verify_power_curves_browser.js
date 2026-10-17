/* Run through playwright-cli run-code against an actual or synthetic review store.
   Screenshots stay ignored here; only synthetic captures may be copied to reports. */
async (page) => {
  const base=new URL(page.url()).origin;
  const synthetic=base.endsWith(':8783') || new URL(page.url()).searchParams.get('synthetic')==='1';
  const capture=synthetic?'synthetic':'private';
  let checks=0;const errors=[];
  page.on('pageerror',e=>errors.push(e.name));
  const check=(v,m)=>{checks++;if(!v)throw new Error(m);};
  const data=async()=>JSON.parse(await page.locator('#power-curve-data').textContent());
  const open=async(path)=> {
    const r=await page.goto(base+path);check(r.status()===200,'route status');
    await page.waitForLoadState('networkidle');
  };
  const focus=async()=>page.locator('#power-curve-chart').focus();
  async function effort() {
    const d=Number(await page.locator('#power-curve-chart').getAttribute('data-duration'));
    const p=await data();
    const keys=[p.mode==='activity'?'ride':await page.locator('#curve-a').inputValue(),await page.locator('#curve-b').inputValue()];
    check(Number.isInteger(d)&&d>0,'exact evaluated duration');
    for (let i=0;i<2;i++) {
      const item=p.series[keys[i]].points.find(q=>q.duration_seconds===d),key=i?'b':'a';
      const readout=await page.locator('#curve-'+key+'-watts').textContent();
      check(readout===(item?item.rounded_watts+' W':'Unavailable at this duration'),'exact watts or unavailable');
      if(item) {
        check(await page.locator('#curve-'+key+'-link').getAttribute('href')==='/activities/'+item.activity.activity_id,'correct contributor link');
        check((await page.locator('#curve-'+key+'-ride').textContent()).includes(item.activity.title),'correct contributor title');
      } else check(await page.locator('#curve-'+key+'-link').isHidden(),'no fabricated contributor');
    }
    return d;
  }
  async function axisMatches() {
    const p=await data();
    const keys=[p.mode==='activity'?'ride':await page.locator('#curve-a').inputValue(),await page.locator('#curve-b').inputValue()];
    const watts=keys.flatMap(key=>p.series[key].points.map(point=>point.average_watts));
    const chart=page.locator('#power-curve-chart');
    const actual=await chart.getAttribute('data-watts-min');
    if (!watts.length) {
      check(actual===null,'empty comparisons have no invented watt scale');
      return;
    }
    const expected=Math.max(0,Math.floor(Math.min(...watts)/50)*50);
    check(actual===String(expected),'lowest visible wattage rounds down to 50 W');
    check(Number(await chart.getAttribute('data-watts-max'))>=Math.max(...watts),'top wattage includes all visible curves');
    const labels=await chart.locator('text').allTextContents();
    check(labels.includes(String(expected)),'bottom gridline shows the actual nonzero baseline');
    const clipped=await chart.locator('.curve-anchor').evaluateAll(nodes=>nodes.some(n=>{
      const svg=n.ownerSVGElement;
      const limit=svg.viewBox.baseVal.height-46;
      return Number(n.getAttribute('cy'))<21.9 || Number(n.getAttribute('cy'))>limit+.1;
    }));
    check(!clipped,'both plotted curves remain inside the wattage scale');
  }
  await page.setViewportSize({width:1440,height:1080});
  await open('/performance');
  check(await page.locator('#performance-history-mode').isVisible(),'unchanged default history');
  check(await page.locator('#power-curve-panel').isHidden(),'curve initially hidden');
  const history=JSON.parse(await page.locator('#performance-points').textContent());
  check(history.length>0,'accepted 20-minute series present');
  await page.getByRole('button',{name:'Power Curve',exact:true}).click();
  check(await page.locator('#power-curve-chart').isVisible(),'curve displayed');
  check(await page.locator('.curve-line').count()===2,'distinguishable lines');
  check(await page.locator('#power-curve-chart').getAttribute('tabindex')==='0','focusable chart');
  const variants=['six','previous','ytd','last_year','all'];
  for(const a of variants) {
    await page.locator('#curve-a').selectOption(a);
    for(const b of variants) {
      await page.locator('#curve-b').selectOption(b);
      check(await page.locator('#curve-a').inputValue()===a,'A selection remains independent');
      check(await page.locator('#curve-b').inputValue()===b,'B independent');
      const p=await data();
      if(p.series[a].points.length||p.series[b].points.length) await effort();
      else check((await page.locator('#curve-empty').textContent()).includes('No qualifying'),'empty-period explanation');
      await axisMatches();
    }
  }
  await page.locator('#curve-a').selectOption('six');await page.locator('#curve-b').selectOption('all');
  let requests=0;const track=()=>requests++;page.on('request',track);
  await focus();await page.keyboard.press('Home');check(await effort()===1,'one-second endpoint');
  await page.keyboard.press('ArrowRight');check(await effort()===2,'arrow next exact anchor');
  await page.keyboard.press('End');check(await effort()>3600,'hour-plus endpoint supported');
  await page.keyboard.press('ArrowLeft');await effort();
  const box=await page.locator('#power-curve-chart').boundingBox();
  await page.mouse.move(box.x+box.width*.55,box.y+box.height*.55);await effort();
  await page.locator('#power-curve-chart').dispatchEvent('pointerdown',{pointerType:'touch',clientX:box.x+box.width*.3,clientY:box.y+80});await effort();
  check(requests===0,'hover/key/touch/period interaction causes no network/recompute');page.off('request',track);
  await page.screenshot({path:'output/playwright/pc01-'+capture+'-performance-desktop.png',fullPage:true});
  await page.getByRole('button',{name:'20-Minute History',exact:true}).click();
  check(await page.locator('#performance-chart').isVisible(),'accepted chart still works');
  check(JSON.stringify(JSON.parse(await page.locator('#performance-points').textContent()))===JSON.stringify(history),'20-minute series unchanged');
  await page.getByRole('button',{name:'Power Curve',exact:true}).click();await focus();await page.keyboard.press('Home');
  const expected=await page.locator('#curve-a-link').getAttribute('href');
  await page.keyboard.press('Enter');await page.waitForURL(url=>url.pathname===expected);await page.waitForLoadState('networkidle');
  check(new URL(page.url()).pathname===expected,'Enter opens contributing activity');
  check(await page.locator('#power-curve-panel').isVisible(),'Activity Review has curve');
  check(await page.locator('#curve-b').inputValue()==='six','Activity default previous six weeks');
  const ride=await data();
  const current=ride.series.ride.points[0]?.activity.activity_id;
  for(const key of ['six','year','all']) {
    await page.locator('#curve-b').selectOption(key);
    const series=ride.series[key];
    const end=new Date(series.end_exclusive).getTime();
    for(const point of series.points) {
      check(point.activity.activity_id!==current,'selected identity excluded');
      check(new Date(point.activity.start_time).getTime()<end,'historical baseline excludes every future/same-start ride');
      if(series.start)check(new Date(point.activity.start_time).getTime()>=new Date(series.start).getTime(),'inclusive lower historical boundary');
    }
    if(ride.series.ride.points.length||series.points.length)await effort();
    await axisMatches();
  }
  await page.locator('#curve-b').selectOption('six');
  check(await page.locator('#chart-svg').count()===1,'existing ride power/HR chart retained');
  check(await page.locator('.best-panel').count()===1,'existing best-20 context retained');
  await page.screenshot({path:'output/playwright/pc01-'+capture+'-activity-desktop.png',fullPage:true});
  const activityPath=new URL(page.url()).pathname;
  for(const width of [390,320]) {
    await page.setViewportSize({width,height:844});
    for(const route of [activityPath,'/performance?curve=1']) {
      await open(route);
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no mobile horizontal overflow');
      const box=await page.locator('#power-curve-chart').boundingBox();
      check(box.width>=200,'usable mobile plot width');await focus();await page.keyboard.press('Home');await effort();await axisMatches();
      await page.keyboard.press('Tab');
      check(await page.evaluate(()=>document.activeElement.tagName==='A'),'keyboard reaches source link');
      await page.locator('#power-curve-chart').dispatchEvent('pointerdown',{pointerType:'touch',clientX:box.x+box.width*.6,clientY:box.y+100});await effort();
      await page.screenshot({path:'output/playwright/pc01-'+capture+'-'+(route.startsWith('/performance')?'performance':'activity')+'-'+width+'.png',fullPage:true});
    }
  }
  await page.setViewportSize({width:1440,height:1080});
  for(const route of ['/','/activities','/plan','/training-state','/settings']) {
    await open(route);check((await page.locator('h1').textContent()).length>0,'accepted route renders');
  }
  if(synthetic) {
    await open('/performance?curve=1');
    const all=(await data()).series.all.points;
    const first=all[0],long=all.at(-1);
    check(first.activity.activity_id!==long.activity.activity_id,'period envelope switches contributors at crossings');
    await open('/activities/'+long.activity.activity_id);
    check((await data()).series.six.points.length===0,'honest empty prior baseline');
    check((await page.locator('#curve-empty').textContent()).includes('No qualifying rides'),'empty baseline explanation');
    // Open an ineligible outdoor source through the Activities list.
    await open('/activities');
    await page.getByRole('link',{name:'Synthetic outdoor ride — unavailable'}).click();
    await page.waitForLoadState('networkidle');
    check((await data()).series.ride.points.length===0,'outdoor unavailable');
    check((await page.locator('#curve-empty').textContent()).includes('Outdoor'),'honest outdoor reason');
    await focus();await page.keyboard.press('Home');check(await page.locator('#curve-b-link').isVisible(),'prior curve inspectable without current');
  }
  check(errors.length===0,'no browser JavaScript errors');
  return {checks,source:synthetic?'synthetic':'private',desktop:1440,mobile:[390,320],period_combinations:25,errors};
}
