/* Run through Playwright CLI with source-neutral CASE_INPUT scenario URLs. */
async page => {
  const cases=CASE_INPUT;let checks=0;
  const check=(v,m)=>{checks++;if(!v)throw Error(m);};
  const lum=color=>color.match(/\d+/g).slice(0,3).map(v=>+v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  const contrast=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
  for(const scenario of cases)for(const width of [1440,1024,768,390,320]) {
    await page.setViewportSize({width,height:1080});
    const response=await page.goto(scenario.base+'/?home_tz=America%2FLos_Angeles');await page.waitForLoadState('networkidle');
    check(response.status()===200,'scenario Home available');
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'scenario no overflow');
    check(await page.locator('.home-quick-fact').evaluateAll(ns=>ns.every(n=>n.scrollWidth<=n.clientWidth+1)),'fact names/numbers contained');
    const summary=await page.locator('.home-summary').boundingBox(),next=await page.locator('.next-recommended').boundingBox();
    check(width===1440?summary.x+summary.width<next.x&&Math.abs(summary.y-next.y)<1:summary.y+summary.height<next.y,'scenario facts precede recommendation');
    check(await page.locator('.home-chart').evaluateAll(ns=>ns.every(n=>{
      const r=n.getBoundingClientRect(),p=n.closest('.panel').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right+1&&r.top>=p.top&&r.bottom<=p.bottom+1;
    })),'charts contained in their cards');
    check(await page.locator('.home-chart text').evaluateAll(ns=>ns.every(n=>{
      const r=n.getBoundingClientRect(),p=n.closest('.panel').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right+1;
    })),'chart labels remain inside cards');
    for(const colors of await page.locator('.home-quick-fact h2, .home-quick-fact strong, .home-redesign a').evaluateAll(ns=>ns.filter(n=>n.closest('.panel')).map(n=>({text:getComputedStyle(n).color,background:getComputedStyle(n.closest('.panel')).backgroundColor})))) {
      check(contrast(colors.text,colors.background)>=4.5,'normal text contrast');
    }
    const edge=await page.locator('.home-summary').evaluate(n=>({color:getComputedStyle(n).borderLeftColor,background:getComputedStyle(n).backgroundColor}));
    check(contrast(edge.color,edge.background)>=3,'blue edge contrast');
    if(scenario.longFacts) {
      check(await page.locator('#home-this-week strong').textContent().then(t=>t.includes('12,')),'large generated mileage displayed');
      check(await page.locator('#home-latest a').textContent().then(t=>t.length>300),'long generated contributor displayed');
    }
    if(scenario.name==='empty') {
      check(await page.locator('.metric-unavailable').count()===2,'honest missing power facts');
      check(await page.locator('#home-this-week strong, #home-last7 strong').allTextContents().then(v=>v.every(t=>t==='0.0 mi')),'empty history keeps supported zero mileage');
    }
    await page.screenshot({path:'output/playwright/home-owner-'+scenario.name+'-'+width+'.png',fullPage:true});
  }
  return {checks,scenarios:cases.map(s=>s.name),widths:[1440,1024,768,390,320],contrast:true,overflow:false};
}
