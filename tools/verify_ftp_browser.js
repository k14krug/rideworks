/* Run with Playwright CLI --filename against a private, disposable copy only.
   Default base is the isolated FTP-01 preview; no private titles/IDs are printed. */
async page => {
  const base='http://127.0.0.1:8875';
  let checks=0; const errors=[];
  const check=(ok,why)=>{checks++;if(!ok)throw new Error(why);};
  page.on('pageerror',e=>errors.push(e.name));
  await page.goto(base+'/performance/ftp'); await page.waitForSelector('.ftp-entry');
  await page.locator('#ftp-reset').click();
  const original=JSON.parse(await page.locator('#ftp-data').textContent());
  check(original.rows.length>1,'seeded private history');
  check(await page.locator('.ftp-entry').count()===original.rows.length,'one marker per true entry');
  check(await page.locator('.ftp-dot').count()===original.points.length,'all eligible dated points');
  for(const c of ['above','below','unavailable']) {
    check(await page.locator('.ftp-dot.'+c).count()===original.points.filter(p=>p.category===c).length,'category count');
    await page.locator(`[data-category="${c}"]`).uncheck();
    check(await page.locator('.ftp-dot.'+c).count()===0,'category hidden');
    await page.locator(`[data-category="${c}"]`).check();
  }
  // Touch selection and browser timezone must not shift athlete-calendar dates.
  const mobileContext=await page.context().browser().newContext({viewport:{width:390,height:844},hasTouch:true,timezoneId:'Asia/Tokyo'});
  const touch=await mobileContext.newPage();await touch.goto(base+'/performance/ftp');
  await touch.locator('#ftp-rides button').first().tap();
  check(await touch.locator('#ftp-date').inputValue()===original.points[0].date,'touch list date independent of browser timezone');
  await touch.locator('#ftp-cancel').tap();await touch.locator('.ftp-dot').first().tap({force:true});
  check((await touch.locator('#ftp-date').inputValue()).length===10,'touch dot selection');
  check(await touch.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'touch viewport fits');
  await mobileContext.close();
  const dates=new Set(original.rows.map(r=>r.effective_from_date));
  const selectable=original.points.filter(p=>p.date>original.rows[0].effective_from_date&&p.date<original.rows.at(-1).effective_from_date&&!dates.has(p.date));
  const chosen=selectable.find(p=>p.category==='below'); check(!!chosen,'gray selectable candidate');
  for(const category of ['above','below','unavailable']) {
    const candidate=original.points.find(p=>p.category===category);check(!!candidate,'category candidate exists');
    await page.locator('#ftp-from').fill(candidate.date);await page.locator('#ftp-to').fill(candidate.date);
    await page.locator('#ftp-range button').first().click();
    const filtered=original.points.filter(p=>p.date===candidate.date);
    check(await page.locator('.ftp-dot').count()===filtered.length,'single-day range');
    await page.locator('#ftp-rides button').nth(filtered.findIndex(p=>p.activity_id===candidate.activity_id)).focus();
    await page.keyboard.press('Enter');
    check(await page.locator('#ftp-date').inputValue()===candidate.date,'keyboard date selection');
    check(Number(await page.locator('#ftp-watts').inputValue())===candidate.proposed,'rounded suggestion');
    await page.locator('#ftp-watts').fill('217');
    await page.locator('.ftp-dot').first().dispatchEvent('pointerenter');
    check(await page.locator('#ftp-watts').inputValue()==='217','hover preserves draft');
    check((await page.locator('#ftp-selection a').getAttribute('href')).includes(candidate.activity_id),'Open Activity destination');
    await page.locator('#ftp-cancel').click();check(await page.locator('#ftp-date').inputValue()==='','cancel draft');
  }
  for(const width of [1440,768,390,320]) {
    await page.setViewportSize({width,height:1000});await page.locator('#ftp-reset').click();
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no document overflow at '+width);
    check(await page.locator('#ftp-chart').isVisible(),'responsive chart');
    const b=await page.locator('#ftp-chart').boundingBox();check(b.width<=width,'chart fits viewport');
  }
  await page.setViewportSize({width:1440,height:1000});
  // Duplicate-day preview never enables overwrite.
  await page.locator('#ftp-date').fill(original.rows[1].effective_from_date);await page.locator('#ftp-watts').fill('211');
  check(await page.locator('#ftp-save').isDisabled(),'duplicate date blocked');
  // A stale second tab must not silently save after another tab changes history.
  const stale=await page.context().newPage();await stale.goto(base+'/performance/ftp');
  await page.locator('#ftp-from').fill(chosen.date);await page.locator('#ftp-to').fill(chosen.date);
  await page.locator('#ftp-range button').first().click();
  await page.locator('#ftp-date').fill(chosen.date);await page.locator('#ftp-watts').fill(String(chosen.ftp.value-10));
  check(!(await page.locator('#ftp-save').isDisabled()),'valid manual insertion');
  check((await page.locator('#ftp-preview').textContent()).includes('exclusive'),'interval consequence preview');
  await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.locator('#ftp-save').click()]);
  await page.waitForSelector('#ftp-data',{state:'attached'});
  const after=JSON.parse(await page.locator('#ftp-data').textContent());
  check(after.rows.length===original.rows.length+1,'saved one entry');
  check(original.rows.every(r=>after.rows.some(n=>r.effective_from_date===n.effective_from_date&&r.ftp_watts===n.ftp_watts)),'existing rows unchanged');
  check(after.revision===original.revision+1,'revision advanced');
  check(await page.locator('#ftp-from').inputValue()===chosen.date,'range retained after save');
  check(after.points.some(p=>p.activity_id===chosen.activity_id&&p.ftp.value===chosen.ftp.value-10),'comparison refreshed');
  await stale.locator('#ftp-date').fill(chosen.date);await stale.locator('#ftp-watts').fill('210');
  const response=await Promise.all([stale.waitForNavigation({waitUntil:'domcontentloaded'}),stale.locator('#ftp-save').click()]);
  check(response[0].status()===400,'stale tab rejected');
  check((await stale.locator('#ftp-message').textContent()).includes('changed'),'stale error visible');
  check(await stale.locator('#ftp-date').inputValue()===chosen.date,'stale draft retained');
  check(JSON.parse(await stale.locator('#ftp-data').textContent()).revision===after.revision,'stale rejection did not mutate');
  await stale.close();
  for(const route of ['/', '/performance', '/training-state', '/plan', '/activities/'+chosen.activity_id]) {
    const r=await page.goto(base+route,{timeout:120000});check(r.status()===200,'cross-page route');
    check(await page.locator('main').isVisible(),'cross-page render');
  }
  await page.goto(base+'/performance/ftp');await page.locator('#ftp-reset').click();
  check(JSON.parse(await page.locator('#ftp-data').textContent()).revision===after.revision,'reload persistence');
  check(errors.length===0,'no JavaScript errors');
  return {checks,eligible_points:original.points.length,initial_entries:original.rows.length,final_entries:after.rows.length,categories:Object.fromEntries(['above','below','unavailable'].map(c=>[c,original.points.filter(p=>p.category===c).length])),widths:[1440,768,390,320],result:'PASS'};
}
