/* CLI run-code template. CASE_INPUT is injected locally; private captures stay ignored. */
async (page) => {
  const config = CASE_INPUT;
  let checks = 0;
  const errors = [];
  const check = (v,m) => { checks++; if (!v) throw new Error(m); };
  page.on('pageerror', e => errors.push(e.name));
  page.on('console', m => { if(m.type()==='error') errors.push('console error'); });
  const open = async path => {
    const response = await page.goto(config.base+path+'?plan_tz=America%2FLos_Angeles&curve_tz=America%2FLos_Angeles');
    check(response.status()===200,'real review route');
    await page.waitForLoadState('networkidle');
  };
  const signals = async () => {
    const native = await page.locator('#native-records').count();
    const selector = native ? '#native-records' : '#api-stream-samples';
    if(!await page.locator(selector).count()) return null;
    return {native,selector,data:JSON.parse(await page.locator(selector).textContent())};
  };
  const verifyReadout = async source => {
    const attr = source.native ? 'data-record-index' : 'data-sample-index';
    const key = source.native ? 'record_index' : 'sample_index';
    const index = Number(await page.locator('#sample-readout').getAttribute(attr));
    const record = source.data.find(r => r[key]===index);
    check(Boolean(record),'selected original sample exists');
    const text = await page.locator('#sample-readout').textContent();
    for(const [signal,label,unit,toggle] of [['power','Power','W','#toggle-power'],['heart_rate','Heart rate','bpm','#toggle-hr']]) {
      const shown = await page.locator(toggle).isChecked();
      const value = shown ? record[signal]===null ? 'Unavailable' : record[signal]+' '+unit : 'Hidden';
      check(text.includes(label+' '+value),'sample readout retains source value/visibility');
    }
  };
  for(const item of config.cases) {
    for(const width of item.capture ? [1440,1024,768,390,320] : [1440,320]) {
      await page.setViewportSize({width,height:1080});
      await open(item.path);
      check(await page.locator('h1').count()===1,'single activity title');
      check(await page.locator('.review-hero .metric').count()===4,'four real summary metrics');
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no horizontal overflow');
      const ids = await page.locator('[id]').evaluateAll(nodes=>nodes.map(n=>n.id));
      check(ids.length===new Set(ids).size,'unique HTML IDs');
      const nav = page.locator('.review-section-nav a');
      check(await nav.count()===5,'five accessible real section links');
      for(const link of await nav.all()) {
        const href=await link.getAttribute('href');
        check(await page.locator(href).count()===1,'valid section target');
        await link.click();
        const target = await page.locator(href).boundingBox();
        const sticky = await page.locator('.review-section-nav').boundingBox();
        const header = await page.locator('.app-header').boundingBox();
        check(target.y>=header.height-2 && (sticky.y>header.height+1 || target.y>=sticky.y+sticky.height-2),item.mode+' '+width+' '+href+' clears header/sticky navigation');
        await link.focus();
        check(await link.evaluate(n=>n===document.activeElement),'section link keyboard focus');
      }
      const curve = await page.locator('#power-curve-panel').boundingBox();
      const wrapper = await page.locator('.activity-review-redesign').boundingBox();
      check(Math.abs(curve.width-wrapper.width)<2,'Power Curve spans full content width');
      const overview = await page.locator('.review-layout').boundingBox();
      const context = await page.locator('.review-context-layout').boundingBox();
      const bests = await page.locator('#bests').boundingBox();
      check(overview.y+overview.height<=curve.y,'ride chart and summary first');
      check(curve.y+curve.height<=context.y,'Power Curve before Workout Context and Current next ride');
      check(context.y+context.height<=bests.y,'context cards before best efforts');
      check(await page.locator('.ride-summary dl').evaluateAll(nodes=>nodes.every(n=>getComputedStyle(n).display==='block')),'summary rows retain readable spacing at tablet widths');
      const source = await signals();
      if(source) {
        const chart = page.locator('#chart-svg');
        const box = await chart.boundingBox();
        check(box.height>=(width<=620 ? 300 : 350),'large legible ride chart');
        check(await page.locator('#toggle-power').isChecked() && await page.locator('#toggle-hr').isChecked(),'signals checked initially');
        const hasPower = source.data.some(r=>r.power!==null), hasHR = source.data.some(r=>r.heart_rate!==null);
        check(await page.locator('#toggle-power').isDisabled()===!hasPower,'missing power explicit');
        check(await page.locator('#toggle-hr').isDisabled()===!hasHR,'missing HR explicit');
        if(hasPower || hasHR) {
          await chart.focus(); await page.keyboard.press('Home'); await verifyReadout(source);
          await page.keyboard.press('End'); await verifyReadout(source);
          await page.keyboard.press('ArrowLeft'); await verifyReadout(source);
          if(hasPower) {
            const hrPath = hasHR ? await page.locator('.chart-hr').getAttribute('d') : null;
            const powerPath = await page.locator('.chart-power').getAttribute('d');
            await page.locator('#toggle-power').uncheck();
            check(await page.locator('.chart-power, .chart-power-area').count()===0,'toggle hides power line/area');
            check(await page.locator('#chart-svg .chart-point-power[visibility="visible"]').count()===0,'toggle hides power marker');
            if(hasHR) check(await page.locator('.chart-hr').getAttribute('d')===hrPath,'HR geometry unchanged by power toggle');
            await verifyReadout(source);
            await page.locator('#toggle-power').check();
            check(await page.locator('.chart-power').getAttribute('d')===powerPath,'power restores exact geometry');
          }
          if(hasHR) {
            await page.locator('#toggle-hr').uncheck();
            check(await page.locator('.chart-hr').count()===0,'toggle hides HR line');
            check(await page.locator('#chart-svg .chart-point-hr[visibility="visible"]').count()===0,'toggle hides HR marker');
            await verifyReadout(source); await page.locator('#toggle-hr').check();
          }
          if(hasPower && hasHR) {
            await page.locator('#toggle-power').uncheck(); await page.locator('#toggle-hr').uncheck();
            check((await chart.textContent()).includes('Select a signal'),'both hidden explicit');
            await page.locator('#toggle-power').check(); await page.locator('#toggle-hr').check();
          }
          await chart.scrollIntoViewIfNeeded();
          const hover=await chart.boundingBox();
          await page.mouse.move(hover.x+hover.width*.5,hover.y+100); await verifyReadout(source);
          await chart.dispatchEvent('pointerdown',{pointerType:'touch',clientX:hover.x+hover.width*.3,clientY:hover.y+100});
          await verifyReadout(source);
          const raw = await page.locator(source.selector).textContent();
          await page.setViewportSize({width:width+1,height:1080}); await page.waitForTimeout(50);
          await verifyReadout(source);
          check(await page.locator(source.selector).textContent()===raw,'redraw preserves original sample JSON');
          await page.setViewportSize({width,height:1080});
        } else {
          check(await page.locator('.chart-power,.chart-hr').count()===0,'no fabricated empty signals');
          check((await chart.textContent()).includes('unavailable'),'empty plot explained');
        }
      } else {
        check(await page.locator('#chart-svg').count()===0,'thin review has no invented plot');
        check(await page.locator('.review-unavailable').isVisible(),'thin source limitation visible');
      }
      const payload=JSON.parse(await page.locator('#power-curve-data').textContent());
      check(await page.locator('#curve-b').inputValue()==='six','exact previous-six-week default');
      for(const name of ['six','year','all']) {
        await page.locator('#curve-b').selectOption(name);
        const hasCurve=payload.series.ride.points.length>0 || payload.series[name].points.length>0;
        check(await page.locator('#power-curve-chart').getAttribute('tabindex')===(hasCurve?'0':'-1'),'empty plot is not a phantom keyboard target');
        if(!hasCurve) check((await page.locator('#power-curve-chart').boundingBox()).height===0,'no giant empty plot for unsupported evidence');
        else check((await page.locator('#power-curve-chart').boundingBox()).height>=300,'baseline/current curve remains visible when supported');
        for(const point of payload.series[name].points) {
          check(point.activity.activity_id!==item.path.split('/').at(-1),'baseline excludes selected identity');
          check(Date.parse(point.activity.start_time)<Date.parse(payload.series[name].end_exclusive),'no same-start/future leakage');
        }
        if(payload.series.ride.points.length || payload.series[name].points.length) {
          await page.locator('#power-curve-chart').focus(); await page.keyboard.press('Home');
          const duration=Number(await page.locator('#power-curve-chart').getAttribute('data-duration'));
          for(const [key,series] of [['a','ride'],['b',name]]) {
            const point=payload.series[series].points.find(p=>p.duration_seconds===duration);
            check(await page.locator('#curve-'+key+'-watts').textContent()===(point?point.rounded_watts+' W':'Unavailable at this duration'),'exact evaluated curve readout');
            if(point) check(await page.locator('#curve-'+key+'-link').getAttribute('href')==='/activities/'+point.activity.activity_id,'correct real contributor route');
          }
        }
      }
      await page.locator('#curve-b').selectOption('six');
      check(await page.locator('#sources details[open]').count()===0,'evidence collapsed initially');
      for(const disclosure of await page.locator('#sources details').all()) {
        await disclosure.locator('summary').click();
        check(await disclosure.evaluate(n=>n.open),'semantic disclosure opens');
      }
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'expanded source identities wrap');
      for(const disclosure of await page.locator('#sources details').all()) await disclosure.evaluate(n=>n.open=false);
      for(const form of await page.locator('.plan-correction').all()) {
        check(await form.getAttribute('action')==='/plan/classification','classification action preserved');
        check(await form.locator('input[name="back"]').inputValue()==='activity','return to activity');
      }
      for(const link of await page.locator('.review-hero a[href="/activities"],.activity-plan-context a,.plan-open').all()) {
        const href=await link.getAttribute('href'); check((await page.request.get(config.base+href)).status()===200,'breadcrumb/Plan route valid');
      }
      if(item.capture) {
        await page.evaluate(()=>scrollTo(0,0));
        await page.screenshot({path:'output/playwright/ar-ui-01-'+config.prefix+'-'+item.mode+'-'+width+'.png',fullPage:true});
      }
    }
  }
  const rich=config.cases.find(c=>c.mode==='native') || config.cases.find(c=>c.mode==='api');
  const context=await page.context().browser().newContext({viewport:{width:320,height:844},hasTouch:true,timezoneId:'America/Los_Angeles',reducedMotion:'reduce'});
  const touch=await context.newPage();
  await touch.goto(config.base+rich.path+'?plan_tz=America%2FLos_Angeles'); await touch.waitForLoadState('networkidle');
  await touch.locator('#chart-svg').scrollIntoViewIfNeeded();
  const box=await touch.locator('#chart-svg').boundingBox();
  await touch.touchscreen.tap(box.x+box.width*.6,box.y+100);
  check(await touch.locator('#sample-readout').getAttribute('data-record-index')!==null || await touch.locator('#sample-readout').getAttribute('data-sample-index')!==null,'actual touchscreen selects source sample');
  await touch.locator('#power-curve-chart').scrollIntoViewIfNeeded();
  const curve=await touch.locator('#power-curve-chart').boundingBox();
  await touch.touchscreen.tap(curve.x+curve.width*.6,curve.y+100);
  check(Number(await touch.locator('#power-curve-chart').getAttribute('data-duration'))>0,'actual touchscreen exact curve anchor');
  await context.close();
  if(config.prefix==='synthetic') {
    await open(rich.path);
    await page.locator('.plan-correction select').selectOption('Recovery');
    await page.locator('.plan-correction button').click(); await page.waitForLoadState('networkidle');
    check((await page.locator('.activity-plan-context').textContent()).includes('Recovery · rider confirmed'),'live category form saves');
    check(new URL(page.url()).pathname===rich.path,'classification returns to selected activity');
    await page.locator('.plan-correction select').selectOption('automatic');
    await page.locator('.plan-correction button').click(); await page.waitForLoadState('networkidle');
    check(!(await page.locator('.activity-plan-context').textContent()).includes('rider confirmed'),'automatic classification restored');
  }
  check(errors.length===0,'no JavaScript or console errors');
  return {checks,modes:config.cases.map(c=>c.mode),widths:[1440,1024,768,390,320],touchscreen:true,errors};
}
