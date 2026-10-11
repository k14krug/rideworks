async (page) => {
  const base=new URL(page.url()).origin;let checks=0;
  const check=(v,m)=>{checks++;if(!v)throw new Error(m);};
  await page.setViewportSize({width:1440,height:1080});
  await page.goto(base+'/performance?curve_tz=America%2FLos_Angeles');await page.waitForLoadState('networkidle');
  for(const name of ['All','Monthly best','Yearly best','Trend + rides']) {
    await page.getByRole('button',{name,exact:true}).click();
    check(await page.locator('#performance-chart').isVisible(),'original Performance controls preserved');
  }
  await page.goto(base+'/?home_tz=America%2FLos_Angeles');await page.waitForLoadState('networkidle');
  check(await page.locator('#home-mileage-chart').count()===1,'Home mileage');
  check(await page.locator('.next-recommended').count()===1,'Home next ride');
  await page.goto(base+'/plan?plan_tz=America%2FLos_Angeles');await page.waitForLoadState('networkidle');
  check(await page.locator('.plan-milestone').count()===3,'three planning hard milestones');
  await page.goto(base+'/training-state?tz=America%2FLos_Angeles');await page.waitForLoadState('networkidle');
  check(await page.locator('#training-chart').isVisible(),'Training State chart retained');
  check((await page.locator('#training-fitness').textContent()).length>0,'Training State values');
  await page.goto(base+'/performance?curve=1');await page.waitForLoadState('networkidle');
  const curves=JSON.parse(await page.locator('#power-curve-data').textContent());
  const native=curves.series.all.points.find(p=>p.source.content_format==='FIT');
  check(Boolean(native),'representative native contributor');
  await page.goto(base+'/activities/'+native.activity.activity_id+'?plan_tz=America%2FLos_Angeles');
  await page.waitForLoadState('networkidle');
  check(await page.locator('.activity-review-redesign > #power-curve-panel').count()===1,'native curve across full review width');
  check(await page.locator('#chart-svg').count()===1,'native stream chart retained');
  const ctx=await page.context().browser().newContext({viewport:{width:390,height:844},hasTouch:true,timezoneId:'America/Los_Angeles'});
  const touch=await ctx.newPage();await touch.goto(base+'/performance?curve=1');await touch.waitForLoadState('networkidle');
  await touch.locator('#power-curve-chart').waitFor({state:'visible'});
  const box=await touch.locator('#power-curve-chart').boundingBox();
  await touch.touchscreen.tap(box.x+box.width*.6,box.y+100);
  check(Number(await touch.locator('#power-curve-chart').getAttribute('data-duration'))>0,'actual Chromium touchscreen selection');
  await touch.locator('#curve-b-link').tap();await touch.waitForURL(url=>url.pathname.startsWith('/activities/'));
  await touch.locator('#power-curve-panel').waitFor({state:'visible'});
  check(await touch.locator('#power-curve-panel').isVisible(),'touch contributor link');
  await ctx.close();return {checks,touchscreen:true,accepted_pages:true,native_review:true};
}
