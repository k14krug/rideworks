/* Source-neutral fixture: actual touchscreen navigation and grouped controls. */
async page => {
  const base=CASE_INPUT;let checks=0;
  const check=(v,m)=>{checks++;if(!v)throw Error(m);};
  for(const width of [390,320]) {
    const context=await page.context().browser().newContext({viewport:{width,height:844},hasTouch:true,timezoneId:'America/Los_Angeles'});
    const touch=await context.newPage();await touch.goto(base+'/performance?curve_tz=America%2FLos_Angeles');await touch.waitForLoadState('networkidle');
    await touch.locator('[data-view="monthly"]').tap();
    const data=JSON.parse(await touch.locator('#performance-points').textContent());
    const index=Number(await touch.locator('#performance-readout').getAttribute('data-point-index'));
    check(await touch.locator('#performance-watts').textContent()===data[index].rounded_watts+' W','touch source watts before selection');
    await touch.locator('#performance-chart').scrollIntoViewIfNeeded();
    const point=await touch.locator('#performance-chart').evaluate(c=>{
      const marker=c.querySelector('.performance-selected'),p=c.createSVGPoint();p.x=+marker.getAttribute('cx');p.y=+marker.getAttribute('cy');
      const q=p.matrixTransform(c.getScreenCTM());return {x:q.x,y:q.y};
    });
    await touch.touchscreen.tap(point.x,point.y);await touch.waitForURL(url=>url.pathname==='/activities/'+data[index].activity_id);
    check(await touch.locator('#chart-svg').count()===1,'touch opens genuine source chart');
    await touch.goto(base+'/activities?tz=America%2FLos_Angeles');await touch.waitForLoadState('networkidle');
    const link=touch.locator('.activity-row').first(),href=await link.getAttribute('href');await link.tap();
    await touch.waitForURL(url=>url.pathname===new URL(href,base).pathname);check(await touch.locator('h1').count()===1,'touch activity row navigation');
    await touch.goto(base+'/settings?tz=America%2FLos_Angeles');await touch.waitForLoadState('networkidle');
    const goal=touch.getByLabel('Annual target (miles)',{exact:true});await goal.tap();
    check(await goal.evaluate(n=>n===document.activeElement),'touch goal input');
    const button=touch.getByRole('button',{name:'Save annual goal',exact:true});
    check((await button.boundingBox()).height>=38,'usable goal action target');
    check(await touch.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'touch settings no overflow');
    await context.close();
  }
  return {checks,touchscreen:true,history_contributor:true,activity_rows:true,settings:true,widths:[390,320]};
}
