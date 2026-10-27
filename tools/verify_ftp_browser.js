/* Run with Playwright CLI --filename against a private, disposable copy only.
   Default base is the isolated FTP-01 preview; no private titles/IDs are printed. */
async page => {
  const base=new URL(page.url()).origin;
  let checks=0; const errors=[];
  const check=(ok,why)=>{checks++;if(!ok)throw new Error(why);};
  page.on('pageerror',e=>errors.push(e.name));
  await page.goto(base+'/performance/ftp');await page.evaluate(()=>sessionStorage.removeItem('rideworks-ftp-chart'));await page.reload(); await page.waitForSelector('.ftp-entry');
  await page.locator('#ftp-reset').click();
  const original=JSON.parse(await page.locator('#ftp-data').textContent());
  const historyDates=original.rows.map(r=>r.effective_from_date).concat(original.points.map(p=>p.date)).sort();
  check(original.rows.length>1,'seeded private history');
  check(await page.locator('#ftp-navigator').isVisible(),'range navigator is visible');
  check(await page.locator('#ftp-from').inputValue()===historyDates[0],'navigator starts at full history');
  check(await page.locator('#ftp-to').inputValue()===historyDates.at(-1),'navigator ends at full history');
  check(await page.locator('.ftp-entry').count()===original.rows.length,'one marker per true entry');
  check(await page.locator('.ftp-dot').count()===original.points.length,'all eligible dated points');
  check(await page.locator('.ftp-dot').first().getAttribute('r')==='2.7','ride dots use reduced visual size');
  check(await page.locator('.ftp-hit').first().getAttribute('r')==='10','reduced dots retain practical pointer target');
  for(const c of ['above','below','unavailable']) {
    check(await page.locator('.ftp-dot.'+c).count()===original.points.filter(p=>p.category===c).length,'category count');
    await page.locator(`[data-category="${c}"]`).uncheck();
    check(await page.locator('.ftp-dot.'+c).count()===0,'category hidden');
    await page.locator(`[data-category="${c}"]`).check();
  }
  const prehistory=original.points.find(p=>p.ftp.status==='unknown_prehistory');
  if(prehistory) {
    const sameDay=original.points.filter(p=>p.date===prehistory.date);
    await page.locator('#ftp-from').fill(prehistory.date);await page.locator('#ftp-to').fill(prehistory.date);await page.locator('#ftp-range button').first().click();
    await page.locator('#ftp-rides button').nth(sameDay.findIndex(p=>p.activity_id===prehistory.activity_id)).click();
    check(await page.locator('#ftp-date').inputValue()===prehistory.date,'prehistory ride suggests its athlete calendar date');
    check((await page.locator('#ftp-preview').textContent()).includes('New earliest setting'),'prehistory ride previews an earliest entry');
    check((await page.locator('#ftp-preview').textContent()).includes('remains unknown before'),'preview preserves unknown time before new date');
    await page.locator('#ftp-cancel').click();
  }
  const uncertain=original.points.find(p=>p.ftp.status==='date_uncertain');
  if(uncertain) {
    const sameDay=original.points.filter(p=>p.date===uncertain.date);
    await page.locator('#ftp-from').fill(uncertain.date);await page.locator('#ftp-to').fill(uncertain.date);await page.locator('#ftp-range button').first().click();
    await page.locator('#ftp-rides button').nth(sameDay.findIndex(p=>p.activity_id===uncertain.activity_id)).click();
    check(await page.locator('#ftp-date').inputValue()==='','timezone-uncertain selection requires deliberate effective-date confirmation');
    check((await page.locator('#ftp-selection').textContent()).includes('Choose and confirm'),'uncertain-date selection explains manual confirmation');
    await page.locator('#ftp-date').fill(uncertain.date);
    check(await page.locator('#ftp-date').inputValue()===uncertain.date,'owner can confirm the source calendar date');
    await page.locator('#ftp-cancel').click();
  }
  // The draggable overview window, exact date fields and active FTP draft stay in sync.
  await page.locator('#ftp-reset').click();
  await page.locator('#ftp-from').fill(original.points[Math.floor(original.points.length/2)].date);
  await page.locator('#ftp-to').fill(original.rows.map(r=>r.effective_from_date).concat(original.points.map(p=>p.date)).sort().at(-1));
  await page.locator('#ftp-range button').first().click();
  await page.locator('#ftp-date').fill('2020-02-02');await page.locator('#ftp-watts').fill('217');
  const window=await page.locator('.ftp-nav-selection').boundingBox();
  await page.mouse.move(window.x+window.width*.55,window.y+window.height/2);await page.mouse.down();
  await page.mouse.move(window.x+window.width*.62,window.y+window.height/2,{steps:4});await page.mouse.up();
  check(await page.locator('#ftp-from').inputValue()!==original.points.map(p=>p.date).sort()[0],'dragging overview window pans visible date range');
  check(await page.locator('#ftp-date').inputValue()==='2020-02-02'&&await page.locator('#ftp-watts').inputValue()==='217','range interaction preserves in-progress FTP draft');
  check(await page.locator('.ftp-nav-left').getAttribute('role')==='slider','navigator start handle is keyboard accessible');
  const fullFirst=historyDates[0],fullLast=historyDates.at(-1);
  const asDay=d=>Math.floor(Date.parse(`${d}T00:00:00Z`)/86400000),plusDay=(d,n)=>new Date(Date.parse(`${d}T00:00:00Z`)+n*86400000).toISOString().slice(0,10);
  const left=page.locator('.ftp-nav-left'),right=page.locator('.ftp-nav-right');
  await page.locator('#ftp-reset').click();
  check(await left.getAttribute('aria-valuenow')===String(asDay(fullFirst))&&await left.getAttribute('aria-valuetext')===fullFirst,'start slider exposes numeric value and readable date');
  check(await right.getAttribute('aria-valuemin')===String(asDay(fullFirst))&&await right.getAttribute('aria-valuemax')===String(asDay(fullLast))&&await right.getAttribute('aria-valuetext')===fullLast,'end slider exposes current numeric range and readable date');
  await left.focus();await page.keyboard.press('ArrowLeft');check(await page.locator('#ftp-from').inputValue()===fullFirst,'full-range start clamps at lower bound');
  await page.keyboard.press('ArrowRight');check(await page.locator('#ftp-from').inputValue()===plusDay(fullFirst,1),'start ArrowRight advances exactly one date');
  await page.keyboard.press('Home');check(await page.locator('#ftp-from').inputValue()===fullFirst,'start Home selects full-history bound');
  await page.keyboard.press('End');check(await page.locator('#ftp-from').inputValue()===fullLast&&await page.locator('#ftp-to').inputValue()===fullLast,'start End clamps to the inclusive end date');
  check(await left.getAttribute('aria-valuenow')===String(asDay(fullLast))&&await left.getAttribute('aria-valuemax')===String(asDay(fullLast))&&await left.getAttribute('aria-valuetext')===fullLast,'start slider constraints update at inclusive end');
  await left.focus();await page.keyboard.press('Home');await right.focus();await page.keyboard.press('Home');
  check(await page.locator('#ftp-to').inputValue()===fullFirst,'end Home preserves a valid one-day range');
  check(await left.getAttribute('aria-valuemax')===String(asDay(fullFirst))&&await right.getAttribute('aria-valuemin')===String(asDay(fullFirst))&&await right.getAttribute('aria-valuemax')===String(asDay(fullLast)),'one-day slider constraints update with selected range');
  await left.focus();await page.keyboard.press('ArrowLeft');check(await page.locator('#ftp-from').inputValue()===fullFirst,'one-day start clamps under ArrowLeft');
  await page.keyboard.press('ArrowRight');check(await page.locator('#ftp-from').inputValue()===fullFirst,'one-day start clamps under ArrowRight');
  await page.keyboard.press('Home');check(await page.locator('#ftp-from').inputValue()===fullFirst,'one-day start Home remains on its only date');
  await page.keyboard.press('End');check(await page.locator('#ftp-from').inputValue()===fullFirst,'one-day start End remains on its only date');
  await right.focus();
  await page.keyboard.press('ArrowLeft');check(await page.locator('#ftp-to').inputValue()===fullFirst,'one-day end clamps under ArrowLeft');
  await page.keyboard.press('ArrowRight');check(await page.locator('#ftp-to').inputValue()===plusDay(fullFirst,1),'one-day end ArrowRight advances exactly one date');
  await page.keyboard.press('End');check(await page.locator('#ftp-to').inputValue()===fullLast,'end End selects full-history bound');
  await page.keyboard.press('ArrowLeft');check(await page.locator('#ftp-to').inputValue()===plusDay(fullLast,-1),'end ArrowLeft retreats exactly one date');
  const middle=original.points[Math.floor(original.points.length/2)].date;
  await page.locator('#ftp-from').fill(plusDay(middle,-3));await page.locator('#ftp-to').fill(plusDay(middle,3));await page.locator('#ftp-range button').first().click();
  await left.focus();await page.keyboard.press('ArrowLeft');check(await page.locator('#ftp-from').inputValue()===plusDay(middle,-4),'middle start ArrowLeft moves one date');
  await page.keyboard.press('ArrowRight');check(await page.locator('#ftp-from').inputValue()===plusDay(middle,-3),'middle start ArrowRight moves one date');
  await right.focus();await page.keyboard.press('ArrowLeft');check(await page.locator('#ftp-to').inputValue()===plusDay(middle,2),'middle end ArrowLeft moves one date');
  await page.keyboard.press('ArrowRight');check(await page.locator('#ftp-to').inputValue()===plusDay(middle,3),'middle end ArrowRight moves one date');
  check(await right.getAttribute('aria-valuenow')===String(asDay(plusDay(middle,3)))&&await right.getAttribute('aria-valuetext')===plusDay(middle,3),'end slider value updates after keyboard movement');
  await page.keyboard.press('Home');check(await page.locator('#ftp-to').inputValue()===plusDay(middle,-3),'middle end Home selects one-day minimum');
  await page.keyboard.press('End');check(await page.locator('#ftp-to').inputValue()===fullLast,'middle end End selects full-history bound');
  // SVG track occupies x=60..970 within its 0..1000 viewBox. Dragging to
  // those exact track edges must reach the complete history bounds.
  await page.locator('#ftp-from').fill(plusDay(middle,-180));await page.locator('#ftp-to').fill(plusDay(middle,180));await page.locator('#ftp-range button').first().click();
  await page.locator('#ftp-navigator').scrollIntoViewIfNeeded();
  const navBox=await page.locator('#ftp-navigator').boundingBox();
  let handleBox=await left.boundingBox();await page.mouse.move(handleBox.x+handleBox.width/2,handleBox.y+handleBox.height/2);await page.mouse.down();
  await page.mouse.move(navBox.x+navBox.width*.06,navBox.y+navBox.height/2);await page.mouse.up();
  check(await page.locator('#ftp-from').inputValue()===fullFirst,`left drag reaches x=60 bound; got ${await page.locator('#ftp-from').inputValue()} expected ${fullFirst}`);
  handleBox=await right.boundingBox();await page.mouse.move(handleBox.x+handleBox.width/2,handleBox.y+handleBox.height/2);await page.mouse.down();
  await page.mouse.move(navBox.x+navBox.width*.97,navBox.y+navBox.height/2);await page.mouse.up();
  check(await page.locator('#ftp-to').inputValue()===fullLast,`right drag reaches x=970 bound; got ${await page.locator('#ftp-to').inputValue()} expected ${fullLast}`);
  await page.locator('#ftp-reset').click();
  await page.locator('#ftp-cancel').click();await page.locator('#ftp-reset').click();
  // Touch selection and browser timezone must not shift athlete-calendar dates.
  const mobileContext=await page.context().browser().newContext({viewport:{width:390,height:844},hasTouch:true,timezoneId:'Asia/Tokyo'});
  const touch=await mobileContext.newPage();await touch.goto(base+'/performance/ftp');
  const touchPoint=original.points.find(p=>p.ftp.status!=='date_uncertain');
  const touchSame=original.points.filter(p=>p.date===touchPoint.date);
  await touch.locator('#ftp-from').fill(touchPoint.date);await touch.locator('#ftp-to').fill(touchPoint.date);await touch.locator('#ftp-range button').first().tap();
  await touch.locator('#ftp-rides button').nth(touchSame.findIndex(p=>p.activity_id===touchPoint.activity_id)).tap();
  check(await touch.locator('#ftp-date').inputValue()===touchPoint.date,'touch list date independent of browser timezone');
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
  // A manual latest-date value is permitted without selecting any ride.
  const later=plusDay(original.rows.at(-1).effective_from_date,1);
  await page.locator('#ftp-date').fill(later);await page.locator('#ftp-watts').fill('160');
  check(!(await page.locator('#ftp-save').isDisabled()),'after-last manual date enables Save');
  check((await page.locator('#ftp-preview').textContent()).includes('New latest setting'),'after-last preview explains its new interval');
  check((await page.locator('#ftp-preview').textContent()).includes('until another entry'),'after-last preview explains open-ended FTP');
  await page.locator('#ftp-cancel').click();
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
