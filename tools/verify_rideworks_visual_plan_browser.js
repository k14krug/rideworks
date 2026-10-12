/* Use generated disposable before/completed fixtures; this exercises saved controls. */
async page => {
  const cases=CASE_INPUT;let checks=0;const errors=[];
  const check=(v,m)=>{checks++;if(!v)throw Error(m);};page.on('pageerror',e=>errors.push(e.name));
  for(const scenario of cases) {
    const base=scenario.base;
    const open=async path=>{const r=await page.goto(base+path);await page.waitForLoadState('networkidle');check(r.status()===200,'Plan flow route');};
    const read=async()=>JSON.parse(await page.locator('#plan-data').textContent());
    const displayed=async()=>page.locator('.next-recommended').evaluate(n=>({day:n.dataset.nextDay,category:n.querySelector('.recommended-type').textContent,target:n.querySelector('.recommended-target').textContent,reason:n.querySelector('.recommended-reason').textContent}));
    await open('/plan?plan_tz=America%2FLos_Angeles');const initial=await read(),original=await displayed();
    check(initial.days.filter(d=>d.hard).length===3,'three hard dates');
    check(await page.locator('.plan-milestone').count()===3,'three milestone links');
    check(initial.today_actual.length===(scenario.completed?1:0),'correct actual completion state');
    check(scenario.completed?initial.next_ride.day>initial.today:initial.next_ride.day===initial.today,'next date before/after ride');
    if(!scenario.completed) {
      await page.getByRole('button',{name:'I plan to do this',exact:true}).click();await page.waitForLoadState('networkidle');
      check(await page.locator('.plan-intent-note').textContent().then(t=>t.includes('Recorded intent: '+initial.next_ride.category)),'intent persists separately');
    }
    await page.getByLabel('Legs today').selectOption('heavy');await page.getByRole('button',{name:'Update',exact:true}).click();await page.waitForLoadState('networkidle');
    check((await read()).next_ride.category==='Recovery','heavy feedback downgrade');
    const heavy=await displayed();await open('/?home_tz=America%2FLos_Angeles');
    check(JSON.stringify(await displayed())===JSON.stringify(heavy),'shared Home/Plan advice');
    await open('/plan?plan_tz=America%2FLos_Angeles');await page.getByLabel('Legs today').selectOption('unknown');
    await page.getByRole('button',{name:'Update',exact:true}).click();await page.waitForLoadState('networkidle');
    check(JSON.stringify(await displayed())===JSON.stringify(original),'feedback reset restores recommendation');
    if(await page.getByRole('button',{name:'Confirm this was a race',exact:true}).count()) {
      const ride=(await read()).recent_uncertain.find(r=>r.classification.title_hint==='Race');
      await page.getByRole('button',{name:'Confirm this was a race',exact:true}).click();await page.waitForLoadState('networkidle');
      check((await read()).recent_hard_dates===initial.recent_hard_dates+1,'source correction affects hard count');
      const history=page.locator('.plan-history');await history.locator('summary').click();
      const form=page.locator('form.plan-correction').filter({has:page.locator('input[name="activity_id"][value="'+ride.activity_id+'"]')});
      await form.locator('select').selectOption('automatic');await form.getByRole('button',{name:'Save category',exact:true}).click();await page.waitForLoadState('networkidle');
      check((await read()).recent_hard_dates===initial.recent_hard_dates,'source inference restored');
    }
    for(const width of [1440,1024,768,390,320]) {
      await page.setViewportSize({width,height:1080});
      check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Plan flow responsive');
      for(const milestone of await page.locator('.plan-milestone').all()) {
        const href=await milestone.getAttribute('href');await milestone.click();
        check(await page.locator(href).isVisible(),'milestone jumps to real day');
      }
      await page.getByLabel('Legs today').focus();await page.keyboard.press('Tab');
      check(await page.getByRole('button',{name:'Update',exact:true}).evaluate(n=>document.activeElement===n),'feedback keyboard order');
      await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'output/playwright/rollout-plan-'+scenario.name+'-'+width+'.png',fullPage:true});
    }
  }
  check(errors.length===0,'no Plan JavaScript errors');
  return {checks,scenarios:cases.map(s=>s.name),intent:true,feedback:true,classification:true,home_parity:true,widths:[1440,1024,768,390,320],errors};
}
