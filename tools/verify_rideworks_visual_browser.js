/* Playwright CLI template; CASE_INPUT contains only local server/source config. */
async page => {
  const config=CASE_INPUT;let checks=0;const errors=[],geometry=[];
  const check=(v,m)=>{checks++;if(!v)throw Error(m);};
  page.on('pageerror',e=>errors.push(e.name));
  const routes=[
    ['activities','/activities?tz=America%2FLos_Angeles','activities-redesign'],
    ['performance-history','/performance?curve_tz=America%2FLos_Angeles','performance-redesign'],
    ['performance-curves','/performance?curve=1&curve_tz=America%2FLos_Angeles','performance-redesign'],
    ['training','/training-state?tz=America%2FLos_Angeles','training-redesign'],
    ['plan','/plan?plan_tz=America%2FLos_Angeles','plan-redesign'],
    ['settings','/settings?tz=America%2FLos_Angeles','settings-redesign']];
  for(const width of [1440,1024,768,390,320]) {
    await page.setViewportSize({width,height:1080});
    for(const [name,path,scope] of routes) {
      const response=await page.goto(config.base+path);await page.waitForLoadState('networkidle');
      check(response.status()===200,'page route available');
      check(await page.locator('.rw-page.'+scope).count()===1,'explicit page scope');
      check(await page.locator('h1').count()===1,'one page title');
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no page overflow');
      const ids=await page.locator('[id]').evaluateAll(ns=>ns.map(n=>n.id));
      check(ids.length===new Set(ids).size,'unique control and section IDs');
      const main=page.locator('.rw-page');
      check(await main.evaluate(n=>getComputedStyle(n).color==='rgb(19, 43, 72)'),'shared ink palette');
      const heading=await page.locator('main header').first().boundingBox();
      check(heading.height<=(width<=620?150:100),'compact page header');
      const panels=await main.locator('.panel').evaluateAll(ns=>ns.filter(n=>n.getBoundingClientRect().width>0).map(n=>{
        const s=getComputedStyle(n);return {nested:!!n.parentElement.closest('.panel'),left:s.borderLeftWidth,color:s.borderLeftColor,radius:s.borderTopLeftRadius,classes:n.className};
      }));
      for(const panel of panels) {
        if(!panel.nested)check(panel.radius==='14px','rounded main card');
        if(panel.color==='rgb(37, 99, 235)'&&parseFloat(panel.left)>1)check(!panel.nested&&['3px','4px'].includes(panel.left),'restrained standalone blue edge');
      }
      check(await main.locator('input:not([type="hidden"]),select,button').evaluateAll(ns=>ns.filter(n=>n.getBoundingClientRect().width>0).every(n=>{
        const r=n.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1;
      })),'controls fit viewport');
      for(const link of await main.locator('a').all()) {
        if(!await link.isVisible())continue;
        await link.focus();check(await link.evaluate(n=>document.activeElement===n),'working keyboard focus');
        check(await link.evaluate(n=>parseFloat(getComputedStyle(n).outlineWidth)>=2),'visible link focus');
      }
      if(name==='activities') {
        const activityRows=page.locator('.activity-row');
        if(await activityRows.count()) {
          check(await activityRows.count()===await page.locator('.activity-row .row-effort .effort-pill').count(),'Each activity has a Relative Effort label or honest unrated state');
        }
        if(width<=620&&await activityRows.count()) {
          check(await page.locator('.row-effort').first().evaluate(n=>getComputedStyle(n,'::before').content.includes('Relative effort')),'mobile Relative Effort label');
        }
        if(width<=620&&await page.locator('.activity-row').count()) {
          check(await page.locator('.activity-row').first().evaluate(n=>getComputedStyle(n).gridTemplateColumns.split(' ').length===1),'stacked mobile activity rows');
          check(await page.locator('.row-date').first().evaluate(n=>getComputedStyle(n,'::before').content.includes('Date')),'mobile date label');
          check(await page.locator('.list-metrics span').first().evaluate(n=>getComputedStyle(n,'::before').content.includes('Distance')),'mobile distance label');
        }
      }
      if(name==='performance-history'&&await page.locator('#performance-chart').count()) {
        const data=JSON.parse(await page.locator('#performance-points').textContent());
        const index=Number(await page.locator('#performance-readout').getAttribute('data-point-index'));
        if(Number.isInteger(index)&&data[index]) {
          check(await page.locator('#performance-watts').textContent()===data[index].rounded_watts+' W','exact history readout');
          check(await page.locator('#performance-activity').getAttribute('href')==='/activities/'+data[index].activity_id,'exact history contributor');
        }
        check((await page.locator('#performance-chart').boundingBox()).height>=310,'history chart height retained');
      }
      if(name==='performance-curves') {
        check(await page.locator('#power-curve-panel').isVisible(),'Power Curve remains available');
        check(await page.locator('#curve-a').count()===1&&await page.locator('#curve-b').count()===1,'both comparison selectors');
      }
      if(name==='training'&&await page.locator('#training-chart').count()) {
        const shape=await page.locator('#training-chart').evaluate(n=>({height:n.clientHeight,plot:+n.dataset.plotBottom- +n.dataset.plotTop,scale:n.getScreenCTM().d}));
        check(shape.plot===(width<=700?400:600),'accepted 600/400px training plot');
        check(Math.abs(shape.scale-1)<1e-7,'training plot not aspect-ratio shrunk');
      }
      if(name==='plan') {
        const data=JSON.parse(await page.locator('#plan-data').textContent());
        check(await page.locator('.next-recommended').getAttribute('data-next-day')===data.next_ride.day,'recommendation date retained');
        check(await page.locator('.plan-milestone').count()===3,'three hard-day milestones');
        check(await page.locator('.next-recommended').evaluate(n=>getComputedStyle(n).borderLeftWidth==='4px'),'recommendation 4px edge');
        if(data.today_actual.length)check(await page.locator('.plan-summary > .plan-completed').evaluate(n=>getComputedStyle(n).borderLeftColor==='rgb(16, 185, 129)'),'completed semantic green edge');
      }
      if(name==='settings') {
        check(await page.locator('#strava-connection').isVisible(),'connection state visible');
        check(await page.getByLabel('Annual target (miles)',{exact:true}).isVisible(),'goal control retained');
        check(await page.locator('form[data-settings-action]').evaluateAll(ns=>ns.every(n=>n.querySelector('input[name="nonce"]'))),'Settings request protection retained');
      }
      for(const disclosure of await main.locator('details').all()) {
        if(!await disclosure.isVisible())continue;
        await disclosure.evaluate(n=>n.open=true);
      }
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'expanded source evidence fits');
      for(const disclosure of await main.locator('details').all())await disclosure.evaluate(n=>n.open=false);
      await page.evaluate(()=>{document.activeElement.blur();scrollTo(0,0);});
      await page.screenshot({path:'output/playwright/rollout-'+config.source+'-after-'+name+'-'+width+'.png',fullPage:true});
      geometry.push({name,width,headerHeight:heading.height});
    }
  }
  // GET-only Activities flows also run against retained real sources.
  await page.goto(config.base+'/activities?type=all&tz=America%2FLos_Angeles');await page.waitForLoadState('networkidle');
  const first=await page.locator('.activity-row').evaluateAll(ns=>ns.map(n=>n.getAttribute('href')));
  if(await page.locator('a[rel="next"]').count()) {
    await page.locator('a[rel="next"]').click();await page.waitForLoadState('networkidle');
    const second=await page.locator('.activity-row').evaluateAll(ns=>ns.map(n=>n.getAttribute('href')));
    check(second.every(h=>!first.includes(h)),'distinct activity pages');
    await page.locator('a[rel="prev"]').click();await page.waitForLoadState('networkidle');
    check(JSON.stringify(await page.locator('.activity-row').evaluateAll(ns=>ns.map(n=>n.getAttribute('href'))))===JSON.stringify(first),'previous activity page restored');
  }
  for(const value of ['oldest','duration','distance']) {
    await page.getByRole('combobox',{name:'Sort',exact:true}).selectOption(value);await page.getByRole('button',{name:'Apply',exact:true}).click();await page.waitForLoadState('networkidle');
    const order=await page.locator('.activity-row').evaluateAll(ns=>ns.map(n=>n.getAttribute('href')));
    await page.reload();await page.waitForLoadState('networkidle');
    check(JSON.stringify(order)===JSON.stringify(await page.locator('.activity-row').evaluateAll(ns=>ns.map(n=>n.getAttribute('href')))),'stable activity sorting');
  }
  const types=await page.getByRole('combobox',{name:'Activity type',exact:true}).locator('option').evaluateAll(ns=>ns.map(n=>n.value));
  for(const type of ['Ride','Virtual Ride','Run'].filter(t=>types.includes(t))) {
    await page.getByRole('combobox',{name:'Activity type',exact:true}).selectOption(type);
    await page.getByRole('button',{name:'Apply',exact:true}).click();await page.waitForLoadState('networkidle');
    check(await page.locator('.row-type').allTextContents().then(ts=>ts.every(t=>t===type||t.startsWith(type+' ·'))),'activity type filter');
  }
  await page.getByRole('combobox',{name:'Activity type',exact:true}).selectOption('all');
  await page.getByRole('button',{name:'Apply',exact:true}).click();await page.waitForLoadState('networkidle');
  if(await page.locator('.activity-row time[datetime]').count()) {
    const stamp=await page.locator('.activity-row time[datetime]').first().getAttribute('datetime');
    if(/(?:Z|[+-]\d\d:\d\d)$/.test(stamp)) {
      const day=await page.evaluate(stamp=>{
        const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Los_Angeles',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(stamp));
        return ['year','month','day'].map(k=>parts.find(p=>p.type===k).value).join('-');
      },stamp);
      const expected=await page.locator('.activity-row').first().getAttribute('href');
      await page.getByLabel('From',{exact:true}).fill(day);await page.getByLabel('To',{exact:true}).fill(day);
      await page.getByRole('button',{name:'Apply',exact:true}).click();await page.waitForLoadState('networkidle');
      check(await page.locator('.activity-row').evaluateAll((ns,expected)=>ns.some(n=>n.getAttribute('href')===expected),expected),'local activity date filter');
      await page.getByLabel('From',{exact:true}).fill('');await page.getByLabel('To',{exact:true}).fill('');
      await page.getByRole('button',{name:'Apply',exact:true}).click();await page.waitForLoadState('networkidle');
    }
  }
  if(first.length) {
    const title=await page.locator('.row-identity h2').first().textContent();
    await page.getByLabel('Title search',{exact:true}).fill(title);await page.getByRole('button',{name:'Apply',exact:true}).click();await page.waitForLoadState('networkidle');
    check(await page.locator('.row-identity h2').allTextContents().then(ts=>ts.every(t=>t.toLowerCase().includes(title.toLowerCase()))),'source title filter');
  }
  await page.goto(config.base+'/activities?q=synthetic-no-such-ride-visual-check&tz=America%2FLos_Angeles');await page.waitForLoadState('networkidle');
  check(await page.locator('.activity-row').count()===0,'honest no-match state');
  check(await page.locator('h2').textContent().then(t=>/No matching|Import your first/.test(t)),'no-match guidance retained');
  const missing=await page.goto(config.base+'/activities/00000000-0000-0000-0000-000000000000');
  check(missing.status()===404,'normal missing-activity route');
  check(await page.getByRole('link',{name:'Activities',exact:true}).count()>=1,'missing-activity recovery link');
  check(errors.length===0,'no page JavaScript errors');
  return {checks,source:config.source,routes:routes.length,widths:[1440,1024,768,390,320],geometry,errors};
}
