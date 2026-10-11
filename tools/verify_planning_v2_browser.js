/* Actual Owner post-sync case; operate only on its disposable review copy. */
async (page) => {
  const base=new URL(page.url()).origin;
  let assertions=0;const errors=[];
  page.on('pageerror',e=>errors.push(e.name));
  const check=(v,m)=>{assertions++;if(!v)throw new Error(m);};
  async function open(path) {
    const response=await page.goto(base+path);check(response.status()===200,'route status');
    await page.waitForLoadState('networkidle');
  }
  const data=async()=>JSON.parse(await page.locator('#plan-data').textContent());
  const next=async()=>page.locator('.next-recommended').evaluate(el=>({day:el.dataset.nextDay,
    content:['recommended-type','recommended-target','recommended-reason'].map(c=>el.querySelector('.'+c).textContent)}));
  async function horizon() {
    const p=await data();const hard=p.days.filter(d=>d.hard);
    check(hard.length===3,'three future hard recommendations');
    check(p.days.at(-1).hard_number===3,'ends on hard three');
    check(await page.locator('.plan-milestone').count()===3,'three prominent milestones');
    check(await page.locator('.plan-day').count()===p.days.length-1,'complete future rotation, today completed separately');
    check(await page.locator('.plan-hard').count()===3,'hard daily cards emphasized');
    for (const r of hard) {
      const milestone=page.locator('.plan-milestone').nth(r.hard_number-1);
      check(await milestone.locator('time').getAttribute('datetime')===r.day,'milestone date equals chronology');
      check(await milestone.locator('h3').textContent()===r.category,'milestone type equals chronology');
    }
    check(!(await page.locator('.plan-days').textContent()).includes('Conditional on sync'),'no repeated generic daily warning');
    check(await page.locator('.plan-low-group').count()>0,'grouped low-intensity dates');
    check(p.next_ride.day==='2026-10-11' && p.next_ride.category==='Race','actual post-sync next date/type');
    check(p.days[0].day==='2026-10-10'&&!p.days[0].hard,'performed day not upcoming quality');
    check(p.today_actual.length===1 && p.today_actual[0].classification.category==='Recovery','actual recovery source');
    for (const day of ['2026-10-08','2026-10-09']) {
      check(p.recent_days.find(r=>r.day===day).state.includes('assumed rest'),'two prior synced no-ride dates');
    }
    return p;
  }
  await page.setViewportSize({width:1440,height:1080});await open('/plan');
  const original=await horizon();const planned=await next();
  check(await page.locator('.plan-summary > .plan-completed').count()===1,'completed card separated');
  const positions=await page.locator('.plan-summary').evaluate(el=>[...el.children].map(c=>({x:c.offsetLeft,y:c.offsetTop})));
  check(positions.length===2 && positions[0].y===positions[1].y && positions[0].x<positions[1].x,'two headline cards match reference hierarchy');
  const milestones=await page.locator('.plan-milestone').evaluateAll(items=>items.map(e=>e.getBoundingClientRect().top));
  check(new Set(milestones).size===1,'desktop milestone columns');
  check(await page.locator('.plan-quick-race').count()===1,'single visible race exception with quick confirmation');
  await page.screenshot({path:'output/playwright/p501-v2-plan-desktop.png',fullPage:true});
  await page.getByRole('link',{name:'Home',exact:true}).click();await page.waitForLoadState('networkidle');
  check(JSON.stringify(await next())===JSON.stringify(planned),'Home Plan exact shared next date/type/target/reason');
  check(await page.locator('.plan-completed').count()===1,'Home completed-today context');
  check(await page.locator('.home-recent-row').count()>0,'Home recent rides retained');
  check(await page.locator('#home-mileage-chart').count()===1,'mileage retained');
  check(await page.locator('.home-training').count()===1,'Training State retained');
  check((await next()).day!=='2026-10-10','no same-day primary second ride');
  await page.screenshot({path:'output/playwright/p501-v2-home-desktop.png'});
  const completed=original.today_actual[0].activity_id;
  await open('/activities/'+completed);
  check(JSON.stringify(await next())===JSON.stringify(planned),'current Activity Review same live next');
  check(await page.locator('#review-next-heading').textContent()==='Next Recommended Ride','latest review label');
  check(await page.locator('.activity-plan-context').textContent().then(t=>t.includes('No recorded intent')),'intent not fabricated');
  const placement=await page.locator('.next-recommended').evaluate(el=>({plan:el.getBoundingClientRect().bottom,curve:document.querySelector('#power-curve-panel')?.getBoundingClientRect().top}));
  check(placement.curve && placement.plan<placement.curve,'next ride in overview before full-width curve');
  await page.screenshot({path:'output/playwright/p501-v2-review-desktop.png'});
  await open('/activities/'+original.latest_hard.activity_id);
  check(await page.locator('#review-next-heading').textContent()==='Current next ride','historic review live current label');
  check(JSON.stringify(await next())===JSON.stringify(planned),'historic review does not reconstruct old next plan');
  await open('/plan');
  await page.getByLabel('Legs today').selectOption('heavy');
  await page.getByRole('button',{name:'Update',exact:true}).click();await page.waitForLoadState('networkidle');
  check((await data()).next_ride.category==='Recovery','heavy feedback downgrades next prospective ride');
  check((await data()).next_ride.day==='2026-10-11','heavy next remains future-dated');
  await page.getByLabel('Legs today').selectOption('unknown');
  await page.getByRole('button',{name:'Update',exact:true}).click();await page.waitForLoadState('networkidle');
  check(JSON.stringify(await next())===JSON.stringify(planned),'feedback reset restores next');
  const race=(await data()).recent_uncertain.find(r=>r.classification.title_hint==='Race');
  await page.getByRole('button',{name:'Confirm this was a race',exact:true}).click();await page.waitForLoadState('networkidle');
  check((await data()).recent_hard_dates===original.recent_hard_dates+1,'quick correction recomputes actual count');
  check(await page.locator('.plan-quick-race').count()===0,'race exception resolved');
  await horizon();
  await open('/activities/'+race.activity_id);
  check(await page.locator('.activity-plan-context strong').textContent()==='Race','correction distinct in actual Review');
  await page.locator('.activity-plan-context select').selectOption('automatic');
  await page.getByRole('button',{name:'Save category'}).click();await page.waitForLoadState('networkidle');
  await open('/plan');await horizon();
  check((await data()).recent_hard_dates===original.recent_hard_dates,'source inference restored');
  await page.getByLabel('Legs today').focus();await page.keyboard.press('Tab');
  check(await page.evaluate(()=>document.activeElement.textContent==='Update'),'keyboard form order');
  await page.locator('.plan-milestone').first().focus();await page.keyboard.press('Enter');
  check(new URL(page.url()).hash==='#hard-1','keyboard milestone jump');
  for (const width of [390,320]) {
    await page.setViewportSize({width,height:844});await open('/plan');
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'phone overflow');
    check(await page.getByLabel('Legs today').isVisible(),'phone controls');
    await horizon();
    await page.screenshot({path:`output/playwright/p501-v2-plan-${width}.png`,fullPage:true});
    await open('/activities/'+completed);
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Review phone overflow');
    check((await next()).day==='2026-10-11','phone current next');
    await page.screenshot({path:`output/playwright/p501-v2-review-${width}.png`,fullPage:true});
  }
  await page.setViewportSize({width:1440,height:1080});
  for (const route of ['/activities','/performance','/training-state','/settings']) {
    await open(route);check(await page.locator('h1').count()===1,'existing route');
  }
  await open('/plan');const repeat=(await data()).days;
  await page.reload();await page.waitForLoadState('networkidle');
  check(JSON.stringify((await data()).days)===JSON.stringify(repeat),'deterministic reload');
  check(errors.length===0,'no script errors');
  return {assertions,script_errors:errors,actual_post_sync:true,home_plan_review_parity:true,
    desktop_reference_hierarchy:true,mobile:[390,320],quick_race_correction:true,heavy_next_ride:true};
}
