/* Run through Playwright CLI; inject CASE_INPUT locally, never private routes. */
async page => {
  const config=CASE_INPUT;
  let checks=0;const errors=[],geometry=[],validRoutes=new Set();
  const check=(v,m)=>{checks++;if(!v)throw new Error(m);};
  page.on('pageerror',e=>errors.push(e.name));
  const money=v=>v===null?'Unavailable':v.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})+' mi';
  const old=await page.context().newPage();
  for(const width of [1440,1024,768,390,320]) {
    await page.setViewportSize({width,height:1080});await old.setViewportSize({width,height:1080});
    const response=await page.goto(config.base+'/?home_tz=America%2FLos_Angeles');
    await page.waitForLoadState('networkidle');check(response.status()===200,'Home route');
    await old.goto(config.baseline+'/?home_tz=America%2FLos_Angeles');await old.waitForLoadState('networkidle');
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no Home horizontal overflow');
    check(await page.locator('h1').count()===1,'one Home title');
    const ids=await page.locator('[id]').evaluateAll(ns=>ns.map(n=>n.id));
    check(ids.length===new Set(ids).size,'unique IDs');
    check(await page.locator('.home-quick-fact').count()===4,'four distinct quick facts');
    const data=JSON.parse(await page.locator('#dashboard-data').textContent());
    check(await page.locator('#home-this-week strong').textContent()===money(data.this_week.miles),'This Week exact mileage');
    check(await page.locator('#home-last7 strong').textContent()===money(data.last7.miles),'Last 7 exact mileage');
    for(const name of ['current','latest']) {
      const point=data.performance[name];
      check(await page.locator('#home-'+name+' strong').textContent()===(point?point.rounded_watts+' W':'Unavailable'),'power quick fact exact');
      if(point)check(await page.locator('#home-'+name+' a').getAttribute('href')==='/activities/'+point.activity_id,'original power contributor');
    }
    const rec=await page.locator('.next-recommended').boundingBox(),quick=await page.locator('.home-summary').boundingBox();
    const prior=await old.locator('.next-recommended').boundingBox();
    const recent=await page.locator('.home-recent').boundingBox();
    check(await page.locator('.home-lead').evaluate(n=>n.children[0].classList.contains('home-summary')&&n.children[1].classList.contains('next-recommended')),'facts first in actual DOM');
    const leadLinks=await page.locator('.home-lead a').all();
    if(leadLinks.length)await leadLinks[0].focus();
    for(let i=0;i<leadLinks.length;i++) {
      check(await leadLinks[i].evaluate(n=>n===document.activeElement),'lead keyboard follows DOM order');
      if(i+1<leadLinks.length)await page.keyboard.press('Tab');
    }
    const accents=await page.locator('.home-summary, .home-lead > .next-recommended, .home-recent, .home-training, .home-performance, .home-mileage, .home-goal-progress, .home-supporting').evaluateAll(ns=>ns.map(n=>{
      const s=getComputedStyle(n);return {next:n.classList.contains('next-recommended'),width:s.borderLeftWidth,color:s.borderLeftColor,style:s.borderLeftStyle,radius:s.borderTopLeftRadius};
    }));
    check(accents.length===8,'eight main cards accented');
    for(const accent of accents) {
      check(accent.width===(accent.next?'4px':'3px'),'single restrained main-card edge');
      check(accent.color==='rgb(37, 99, 235)'&&accent.style==='solid'&&accent.radius==='14px','palette blue and rounded main-card edge');
    }
    check(await page.locator('.home-quick-fact, .home-supporting details, .next-recommended .plan-completed, .home-chart').evaluateAll(ns=>ns.every(n=>{
      const s=getComputedStyle(n);return parseFloat(s.borderLeftWidth)===0||s.borderLeftColor!=='rgb(37, 99, 235)';
    })),'no nested blue stripes');
    check(rec.y<prior.y,'next ride closer to top');
    check(rec.y+rec.height<=recent.y,'recommendation above recent rides');
    if(width===1440) {
      check(rec.y<220 && Math.abs(rec.y-quick.y)<1,'recommendation and quick facts above desktop fold');
      check(quick.x+quick.width<rec.x&&rec.width>quick.width,'facts left and wider recommendation right');
    } else check(quick.y+quick.height<rec.y,'stacked facts above recommendation');
    if(width<=620) {
      const boxes=await page.locator('.home-quick-fact').evaluateAll(ns=>ns.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y};}));
      check(boxes[0].y===boxes[1].y&&boxes[2].y===boxes[3].y&&boxes[2].y>boxes[0].y,'phone 2 by 2 facts');
      check(await page.locator('.home-recent-table tr').evaluateAll(ns=>ns.every(n=>getComputedStyle(n).display==='block')),'readable stacked recent rows');
      check(await page.locator('.home-recent-row td:not(:nth-child(2))').evaluateAll(ns=>ns.every(n=>getComputedStyle(n,'::before').content.includes(n.dataset.label))),'visible mobile source-field labels');
    }
    const header=await page.locator('.home-heading').boundingBox();
    geometry.push({width,headerHeight:header.height,factsTop:quick.y,factsWidth:quick.width,recommendationTop:rec.y,recommendationWidth:rec.width,priorRecommendationTop:prior.y,recentTop:recent.y});
    check(await page.locator('.home-recent-row').count()===data.recent.length,'all recent rows retained');
    for(const row of data.recent) {
      const el=page.locator('.home-recent-row[data-activity-id="'+row.activity_id+'"]');
      check(await el.locator('a').getAttribute('href')==='/activities/'+row.activity_id,'recent source link');
      check(await el.locator('[data-label="Distance"]').textContent()===money(row.distance===null?null:row.distance/1609.344),'recent exact distance');
      check(await el.locator('.home-avg-power').textContent()===(row.average_power===null?'Unavailable':row.average_power.toLocaleString('en-US',{maximumSignificantDigits:6})+' W'),'source-supplied average power');
    }
    const before=await old.locator('.next-recommended').textContent(),after=await page.locator('.next-recommended').textContent();
    check(before===after,'next ride all content unchanged');
    const plan=await page.context().newPage();await plan.goto(config.base+'/plan?plan_tz=America%2FLos_Angeles');await plan.waitForLoadState('networkidle');
    const expected=JSON.parse(await plan.locator('#plan-data').textContent());
    check(await page.locator('.next-recommended').getAttribute('data-next-day')===expected.next_ride.day,'same-clock Plan next date');
    for(const [selector,key] of [['.recommended-type','category'],['.recommended-reason','reason']])check(await page.locator('.next-recommended '+selector).textContent()===expected.next_ride[key],'same Plan advice');
    check((await page.locator('.next-recommended .recommended-target').textContent())===expected.next_ride.duration+' · '+expected.next_ride.power,'same Plan duration/power');
    if(expected.today_actual.length)check(expected.next_ride.day>expected.today,'next future ride after completed today');
    await plan.close();
    check(await page.locator('.home-training').textContent()===await old.locator('.home-training').textContent(),'Training State values/meaning retained');
    check(await page.locator('.home-goal-progress').textContent().then(t=>t.includes(data.target_miles===null?'Set annual goal':'Annual target:')),'goal or honest no-goal state');
    const bars=page.locator('#home-mileage-chart [data-week]');check(await bars.count()===12,'twelve accepted mileage weeks');
    check(await page.locator('#home-mileage-chart .home-mileage-current').count()===1,'current partial-week outline');
    for(let i=0;i<12;i++) {
      check(await bars.nth(i).getAttribute('data-mileage-value')===money(data.weekly_goal[i].bar_miles),'raw actual bar value');
      await bars.nth(i).focus();check(await page.locator('#mileage-tooltip').isVisible(),'keyboard mileage inspection');
      check(await page.locator('#mileage-tooltip').textContent()===money(data.weekly_goal[i].bar_miles),'keyboard source value');
      await page.keyboard.press('Escape');check(await page.locator('#mileage-tooltip').isHidden(),'Escape dismisses');
    }
    for(const dot of await page.locator('#home-mileage-chart [data-needed-week]').all()) {
      const start=await dot.getAttribute('data-needed-week');
      const week=data.weekly_goal.find(w=>w.start===start);
      await dot.focus();check(await page.locator('#mileage-tooltip').textContent()===money(week.needed_miles_per_week),'needed-line keyboard source value');
      await dot.locator('.home-mileage-hit').hover();check(await page.locator('#mileage-tooltip').textContent()===money(week.needed_miles_per_week),'needed-line pointer source value');
    }
    const hits=page.locator('#home-mileage-chart [data-week] .home-mileage-hit');
    const box=await hits.last().boundingBox();await hits.last().hover({position:{x:1,y:box.height-2}});
    check(await page.locator('#mileage-tooltip').textContent()===money(data.this_week.miles),'actual pointer source value');
    await page.mouse.move(0,0);
    for(const link of await page.locator('.home-redesign a').all()) {
      const href=await link.getAttribute('href');
      if(!validRoutes.has(href)) {
        const response=await page.request.get(config.base+href);
        check(response.status()===200,'real Home destination');
        if(href.includes('#'))check((await response.text()).includes('id="'+href.split('#')[1]+'"'),'real fragment target');
        validRoutes.add(href);
      }
      await link.focus();check(await link.evaluate(n=>n===document.activeElement),'links keyboard focus');
    }
    for(const disclosure of await page.locator('.home-supporting details').all()) {
      check(await disclosure.evaluate(n=>!n.open),'supporting details collapsed initially');
      await disclosure.locator('summary').click();check(await disclosure.evaluate(n=>n.open),'semantic disclosure opens');
    }
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'expanded evidence no overflow');
    for(const d of await page.locator('.home-supporting details').all())await d.evaluate(n=>n.open=false);
    await page.evaluate(()=>scrollTo(0,0));
    await page.screenshot({path:'output/playwright/home-ui-01-'+config.source+'-after-'+width+'.png',fullPage:true});
    await old.screenshot({path:'output/playwright/home-ui-01-'+config.source+'-before-'+width+'.png',fullPage:true});
  }
  await old.close();
  const context=await page.context().browser().newContext({viewport:{width:320,height:844},hasTouch:true,timezoneId:'America/Los_Angeles',reducedMotion:'reduce'});
  const touch=await context.newPage();await touch.goto(config.base+'/?home_tz=America%2FLos_Angeles');await touch.waitForLoadState('networkidle');
  const hit=touch.locator('#home-mileage-chart [data-week] .home-mileage-hit').last();await hit.scrollIntoViewIfNeeded();const box=await hit.boundingBox();
  await touch.touchscreen.tap(box.x+1,box.y+box.height-2);
  check(await touch.locator('#mileage-tooltip').textContent()===await hit.locator('..').getAttribute('data-mileage-value'),'actual touch displays original mileage');
  check(await touch.locator('#mileage-tooltip').isVisible(),'touch inspection visible');
  await context.close();check(errors.length===0,'no JavaScript errors');
  return {checks,source:config.source,widths:[1440,1024,768,390,320],geometry,touch:true,errors};
}
