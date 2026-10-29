/* Synthetic-only HOME-UI-03 Owner refinement, through Playwright CLI. */
async page => {
  const base='http://127.0.0.1:8791', previous='http://127.0.0.1:8792';
  const before=await page.context().newPage();
  let checks=0;
  const geometry=[],errors=[];
  const check=(value,message)=>{checks++;if(!value)throw new Error(message);};
  page.on('pageerror',error=>errors.push(error.name));
  for(const width of [1440,1024,768,390,320]) {
    await page.setViewportSize({width,height:1080});await before.setViewportSize({width,height:1080});
    await page.goto(base+'/?home_tz=America%2FLos_Angeles');await before.goto(previous+'/?home_tz=America%2FLos_Angeles');
    await Promise.all([page.waitForLoadState('networkidle'),before.waitForLoadState('networkidle')]);
    const card=page.locator('.home-goal-progress'),chart=page.locator('#home-annual-chart');
    const annual=await card.boundingBox(),weekly=await page.locator('.home-mileage').boundingBox();
    const oldWeekly=await before.locator('.home-mileage').boundingBox();
    const newChart=await chart.boundingBox(),oldChart=await before.locator('#home-annual-chart').boundingBox();
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no horizontal overflow');
    check(Math.abs(weekly.height-oldWeekly.height)<.5,'Mileage Progress height unchanged');
    if(width>1100) {
      check(Math.abs(annual.height-weekly.height)<.5,'annual and weekly card heights match');
      check(Math.abs(annual.y-weekly.y)<.5,'bottom-row cards align');
      check(newChart.height>oldChart.height,'chart is taller');
    }
    check(await card.locator(':scope > strong').count()===0,'duplicate YTD headline removed');
    check(await card.locator('.home-annual-coverage').count()===0,'coverage paragraph removed');
    check(await card.locator('.home-annual-goal').evaluate(n=>n.previousElementSibling.classList.contains('home-annual-legend')),'goal follows chart and legend');
    check(await card.locator('.home-annual-goal').boundingBox().then(b=>b.y>=newChart.y+newChart.height),'goal text below chart');
    check(await card.locator(':scope > *').evaluateAll(nodes=>{
      const parent=nodes[0].parentElement.getBoundingClientRect();
      return nodes.filter(n=>n.getClientRects().length).every(n=>{const r=n.getBoundingClientRect();return r.left>=parent.left&&r.right<=parent.right+.5&&r.bottom<=parent.bottom+.5;});
    }),'all content fits inside annual card');
    check(await chart.locator('text').evaluateAll(nodes=>nodes.every(n=>{
      const b=n.getBBox(),v=n.ownerSVGElement.viewBox.baseVal;
      return b.x>=0&&b.y>=0&&b.x+b.width<=v.width+.5&&b.y+b.height<=v.height+.5;
    })),'SVG labels not clipped');
    const data=JSON.parse(await page.locator('#dashboard-data').textContent());
    const oldData=JSON.parse(await before.locator('#dashboard-data').textContent());
    check(JSON.stringify(data)===JSON.stringify(oldData),'all dashboard source data unchanged');
    const month=Number(data.today.slice(5,7)),first=Math.max(1,month-3);
    const starts=data.annual_series.filter(s=>s.points.length&&s.points.at(-1).day>=`${s.year}-${String(first).padStart(2,'0')}-01`)
      .map(s=>s.points.filter(p=>p.day<=`${s.year}-${String(first).padStart(2,'0')}-01`).at(-1)?.miles??0);
    check(Math.abs(Number(await chart.getAttribute('data-y-min'))-Math.min(...starts))<1e-8,'Y-axis floor equals smallest starting value');
    check(Number(await chart.getAttribute('data-y-min'))>0,'synthetic floor is not zero');
    check(await card.locator('.home-annual-legend-0').textContent()===data.year+data.ytd.miles.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})+' mi YTD','current YTD remains in legend');
    check(await chart.locator('desc').textContent().then(t=>t.includes('history may be incomplete')),'coverage remains accessible');
    for(const selector of ['.home-summary','.next-recommended','.home-recent','.home-training','.home-performance','.home-mileage','.home-supporting']) {
      check(await page.locator(selector).innerHTML()===await before.locator(selector).innerHTML(),selector+' markup preserved');
    }
    const endpoint=chart.locator('[data-annual-value]').last();
    await endpoint.focus();check(await page.locator('#annual-tooltip').isVisible(),'keyboard endpoint readout');
    await page.keyboard.press('Escape');check(await page.locator('#annual-tooltip').isHidden(),'Escape dismisses endpoint readout');
    await endpoint.blur();
    await page.mouse.move(0,0);await endpoint.hover();
    check(await page.locator('#annual-tooltip').isVisible(),'real pointer hover displays endpoint');
    check(await page.locator('#annual-tooltip').textContent()===await endpoint.getAttribute('data-annual-value'),'pointer readout shows actual source value');
    await page.mouse.move(0,0);check(await page.locator('#annual-tooltip').isHidden(),'pointer leave dismisses');
    const week=page.locator('#home-mileage-chart [data-mileage-value]').first();
    await week.focus();check(await page.locator('#mileage-tooltip').isVisible(),'weekly chart tooltip preserved');
    await page.keyboard.press('Escape');await week.blur();
    geometry.push({width,weeklyHeight:weekly.height,annualHeight:annual.height,chartHeight:newChart.height,previousChartHeight:oldChart.height});
    await page.locator('.home-progress-layout').screenshot({path:`output/playwright/home-ui03-refinement-${width}.png`});
  }
  // Full-page routes and Settings remain the existing renderers.
  for(const route of ['/activities','/training-state','/performance','/plan','/settings?tz=America%2FLos_Angeles#annual-goal']) {
    check((await page.request.get(base+route)).status()===200,'working destination '+route);
  }
  check(errors.length===0,'no JavaScript errors');
  await before.close();
  return {checks,geometry,widths:[1440,1024,768,390,320],physicalPointerHover:true,errors};
}
