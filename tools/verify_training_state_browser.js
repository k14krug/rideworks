async (page) => {
  const failures=[];let checks=0;
  const assert=(value,message)=>{checks++;if(!value)failures.push(message);};
  const read=async()=>await page.evaluate(()=>{
    const data=JSON.parse(document.querySelector('#training-state-data').textContent);
    const date=document.querySelector('#training-date').value;
    const day=data.days.find(d=>d.day===date);
    return {date,day,values:['fitness','fatigue','form'].map(k=>document.querySelector(`#training-${k}`).textContent),
      heading:document.querySelector('#training-day-heading').textContent,
      links:[...document.querySelectorAll('#training-day-detail article a')].map(a=>a.getAttribute('href')),
      width:document.documentElement.scrollWidth,viewport:innerWidth,
      sourceCount:document.querySelectorAll('#training-chart [data-series]').length};
  });
  const sync=async()=>{const x=await read();assert(x.heading.includes(x.date),'selected date/detail synchronization');
    for(let i=0;i<3;i++)assert(x.values[i]===x.day[['fitness','fatigue','form'][i]].toLocaleString(undefined,{minimumFractionDigits:1,maximumFractionDigits:1}),'selected numeric synchronization');
    assert(x.links.length===x.day.rides.length,'selected activity links match exact daily records');return x;};
  await page.setViewportSize({width:1280,height:900});
  await page.goto('http://127.0.0.1:8772/training-state');await page.waitForSelector('#training-date');
  await sync();
  for(const name of ['Fitness','Fatigue'])assert(await page.getByRole('checkbox',{name,exact:true}).isChecked(),name+' visible by default');
  assert(!(await page.getByRole('checkbox',{name:'Form',exact:true}).isChecked()),'Form hidden by default');
  assert((await read()).sourceCount===2,'initial chart renders Fitness and Fatigue only');
  const geometry=async(mobile)=>{
    const g=await page.locator('#training-chart').evaluate(c=>({height:c.clientHeight,viewHeight:c.viewBox.baseVal.height,
      plot: +c.dataset.plotBottom- +c.dataset.plotTop,strip:+c.dataset.stripBottom,
      cssHeight:c.getBoundingClientRect().height,zero:+c.querySelector('.training-zero').getAttribute('y1'),
      barTops:[...c.querySelectorAll('rect')].map(b=>+b.getAttribute('y')),
      paths:[...c.querySelectorAll('[data-series]')].map(p=>{const b=p.getBBox();return {top:b.y,bottom:b.y+b.height}}),
      bars:[...c.querySelectorAll('rect')].map(b=>+b.getAttribute('y')+ +b.getAttribute('height')),
      guide:+c.querySelector('.chart-cursor').getAttribute('y2'),scale:c.getScreenCTM().d}));
    assert(g.plot>=(mobile?360:560)&&g.plot<=(mobile?440:640),'actual trend plot CSS height');
    assert(g.height===g.viewHeight,'SVG vertical units map to CSS pixels');
    assert(g.cssHeight===g.height,'chart height is actual visible CSS height');
    assert(Math.abs(g.scale-1)<1e-7,'narrow SVG avoids aspect-ratio shrinking of actual plot');
    assert(g.guide===g.strip+10&&g.strip<g.height-12,'guide spans aligned plot and strip');
    assert(g.paths.every(p=>p.top>=24&&p.bottom<=25+g.plot+1),'all curves within actual plot');
    assert(g.bars.every(b=>Math.abs(b-g.strip)<1e-8),'stress bars share strip baseline');
    assert(g.barTops.every(t=>t>=25+g.plot+55),'stress strip remains below trend plot');
    assert(g.zero>=25&&g.zero<=25+g.plot,'Form zero reference remains inside plot');
  };
  await geometry(false);
  for(const name of ['Fitness','Fatigue','Form']){await page.getByRole('checkbox',{name,exact:true}).uncheck();}
  assert((await read()).sourceCount===0,'all line toggles off');
  for(const name of ['Fitness','Fatigue','Form']){await page.getByRole('checkbox',{name,exact:true}).check();}
  assert((await read()).sourceCount===3,'all line toggles on');
  for(const name of ['6 weeks','3 months','12 months','All history']){await page.getByRole('button',{name,exact:true}).click();await sync();}
  const targets=await page.evaluate(()=>{const d=JSON.parse(document.querySelector('#training-state-data').textContent).days;
    return {multi:d.findLast(p=>p.rides.length>1)?.day,missing:d.findLast(p=>p.unscored)?.day,noRecord:d.findLast(p=>p.no_record)?.day,summary:d.findLast(p=>p.rides.some(r=>r.selected.method==='hr'&&r.hr.evidence_kind==='summary'&&r.hr.stream_rejections.length))?.day};});
  for(const [kind,date] of Object.entries(targets)){assert(!!date,kind+' fixture present');if(!date)continue;
    await page.locator('#training-date').fill(date);await page.locator('#training-date').dispatchEvent('change');const x=await sync();
    if(kind==='summary')assert((await page.locator('#training-day-detail').textContent()).includes('HR summary estimate')&&(await page.locator('#training-day-detail').textContent()).includes('unverified'),'summary fallback label and uncertainty in persistent inspection');
    if(kind==='multi')assert(x.links.length>1,'multi-ride day links');
    if(kind==='missing')assert((await page.locator('#training-day-detail').textContent()).includes('unavailable'),'unscored evidence remains unavailable');
    if(kind==='noRecord')assert((await page.locator('#training-day-detail').textContent()).includes('rest is not established'),'no-record is not rest');
  }
  const hover=async(date,region='trend')=>{
    const point=await page.evaluate(({date,region})=>{
      const chart=document.querySelector('#training-chart'),days=JSON.parse(document.querySelector('#training-state-data').textContent).days;
      const first=days.findIndex(d=>d.day===document.querySelector('#training-date').min),i=days.findIndex(d=>d.day===date);
      const p=chart.createSVGPoint();p.x=45+(chart.viewBox.baseVal.width-60)*(i-first)/Math.max(1,days.length-1-first);p.x+=i===first?.01:i===days.length-1?-.01:0;
      p.y=region==='strip'?+chart.dataset.stripBottom-25:(+chart.dataset.plotTop+ +chart.dataset.plotBottom)/2;
      const screen=p.matrixTransform(chart.getScreenCTM());return {x:screen.x,y:screen.y};
    },{date,region});
    await page.mouse.move(point.x,point.y);await page.locator('#training-tooltip').waitFor({state:'visible'});
    const t=await page.locator('#training-tooltip').evaluate(el=>({day:el.dataset.day,text:el.textContent,
      x:el.getBoundingClientRect().x,y:el.getBoundingClientRect().y,w:el.offsetWidth,h:el.offsetHeight}));
    assert(t.day===date,'hover exact nearest day');
    assert(t.x>=7&&t.y>=7&&t.x+t.w<=1280-7&&t.y+t.h<=900-7,'hover fits viewport edges');
    assert(Math.min(Math.abs(t.x-point.x),Math.abs(t.x+t.w-point.x))<=15,'tooltip near cursor horizontally');
    assert(await page.locator('.training-hover-guide').getAttribute('visibility')==='visible','vertical hover guide visible');
    const expected=await page.evaluate(date=>JSON.parse(document.querySelector('#training-state-data').textContent).days.find(d=>d.day===date),date);
    for(const k of ['fitness','fatigue','form'])assert(t.text.includes(expected[k].toLocaleString(undefined,{minimumFractionDigits:1,maximumFractionDigits:1})),'hover '+k+' exact numeric value');
    assert(t.text.includes('start of day'),'hover Form timing');
    assert(t.text.includes(expected.rides.length+' recorded'),'hover ride count');
    for(const ride of expected.rides){
      assert(t.text.includes(ride.title),'hover full ride title');
      const candidate=ride.selected.method==='hr'?ride.hr:ride.power;
      if(candidate.source?.format)assert(t.text.includes(candidate.source.format),'hover selected source format');
    }
    if(expected.rides.some(r=>r.selected.method==='hr'&&r.hr.evidence_kind==='summary')){
      assert(t.text.includes('HR summary estimate'),'hover summary estimate label');
      assert(t.text.includes('active coverage and pause treatment unverified'),'hover summary uncertainty');
    }
    if(expected.unscored)assert(t.text.includes('Stress unavailable'),'hover missing stress explicit');
    return point;
  };
  for(const name of ['6 weeks','3 months','12 months','All history']){
    await page.getByRole('button',{name,exact:true}).click();await page.locator('#training-chart').scrollIntoViewIfNeeded();
    await page.waitForTimeout(80);
    await geometry(false);
    const edges=await page.evaluate(()=>({first:document.querySelector('#training-date').min,last:document.querySelector('#training-date').max}));
    const selected=await page.locator('#training-date').inputValue();
    await hover(edges.first);await hover(edges.last,'strip');
    assert(await page.locator('#training-date').inputValue()===selected,'hover preserves selected date in '+name);
    await page.mouse.move(5,5);assert(!await page.locator('#training-tooltip').isVisible(),'mouseleave dismisses overlay');
    assert(await page.locator('.training-hover-guide').getAttribute('visibility')==='hidden','mouseleave dismisses hover guide');
  }
  for(const date of Object.values(targets)){
    const point=await hover(date,'strip');await page.mouse.click(point.x,point.y);await sync();
    await page.mouse.move(5,5);assert(!await page.locator('#training-tooltip').isVisible(),'click overlay dismissed on leave');
    assert(await page.locator('#training-date').inputValue()===date,'clicked selection persists after leave');
  }
  const longest=await page.evaluate(()=>JSON.parse(document.querySelector('#training-state-data').textContent).days.filter(d=>d.rides.length).sort((a,b)=>Math.max(...b.rides.map(r=>r.title.length))-Math.max(...a.rides.map(r=>r.title.length)))[0].day);
  await hover(longest);await page.mouse.move(5,5);
  await page.locator('#training-chart').focus();await page.keyboard.press('Home');await sync();
  await page.keyboard.press('ArrowRight');await sync();
  assert(await page.locator('#training-tooltip').getAttribute('data-day')===await page.locator('#training-date').inputValue(),'keyboard tooltip date equivalence');
  await page.keyboard.press('Escape');assert(!await page.locator('#training-tooltip').isVisible(),'Escape dismisses tooltip');
  await page.keyboard.press('End');await sync();
  await page.locator('#training-date').fill(targets.multi);await page.locator('#training-date').dispatchEvent('change');
  await page.locator('#training-day-detail details summary').first().click();
  assert((await page.locator('#training-day-detail pre').first().textContent()).includes('method'),'source calculation inspection');
  const url=await page.locator('#training-day-detail article a').first().getAttribute('href');
  await page.goto('http://127.0.0.1:8772'+url);assert((await page.title()).includes('RideWorks'),'stable Activity Review route');
  for(const route of ['/','/performance','/activities']){await page.goto('http://127.0.0.1:8772'+route);assert((await page.title()).includes('RideWorks'),'retained route '+route);}
  await page.goto('http://127.0.0.1:8772/training-state');await page.waitForSelector('#training-date');
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'All history',exact:true}).click();
  await geometry(true);
  await sync();const x=await read();assert(x.width<=x.viewport,'phone has no horizontal overflow');
  await page.locator('#training-chart').focus();
  for(const key of ['Home','End']){
    await page.keyboard.press(key);await sync();await page.waitForTimeout(80);
    const t=await page.locator('#training-tooltip').boundingBox();
    assert(!!t,'phone keyboard overlay visible');
    assert(t&&t.x>=7&&t.y>=7&&t.x+t.width<=383&&t.y+t.height<=837,'phone overlay fits after date change');
  }
  await page.evaluate(()=>window.scrollBy(0,40));await page.waitForTimeout(80);
  assert(await page.locator('#training-tooltip').isVisible(),'focused keyboard inspection survives chart scrolling');
  const box=await page.locator('#training-chart').boundingBox();await page.mouse.click(box.x+box.width*.7,box.y+box.height*.4);await sync();
  await page.screenshot({path:'output/playwright/p4-02-phone-final.png',fullPage:true});
  await page.setViewportSize({width:320,height:844});await page.getByRole('button',{name:'3 months',exact:true}).click();
  await geometry(true);assert((await read()).width<=320,'small phone has no horizontal overflow');
  for(const width of [320,390]){
    await page.setViewportSize({width,height:844});
    for(const range of ['3 months','12 months']){
      await page.getByRole('button',{name:range,exact:true}).click();await geometry(true);
      await page.locator('#training-chart').scrollIntoViewIfNeeded();
      const point=await page.locator('#training-chart').evaluate(c=>{
        const ds=JSON.parse(document.querySelector('#training-state-data').textContent).days;
        const first=ds.findIndex(d=>d.day===document.querySelector('#training-date').min);
        const i=first+Math.floor((ds.length-1-first)*.6),p=c.createSVGPoint();
        p.x=45+(c.viewBox.baseVal.width-60)*(i-first)/(ds.length-1-first);
        p.y=(+c.dataset.plotTop+ +c.dataset.plotBottom)/2;
        const s=p.matrixTransform(c.getScreenCTM());return {x:s.x,y:s.y,date:ds[i].day};
      });
      await page.mouse.move(point.x,point.y);
      assert(await page.locator('#training-tooltip').getAttribute('data-day')===point.date,'narrow trend exact hover date');
      await page.evaluate(()=>window.scrollBy(0,1));await page.waitForTimeout(80);
      assert(!await page.locator('#training-tooltip').isVisible(),'pointer inspection dismisses on scroll');
      point.y-=1;
      await page.mouse.click(point.x,point.y);await sync();
      assert(await page.locator('#training-date').inputValue()===point.date,'narrow pointer date selection');
      await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowLeft');await sync();
      assert(await page.locator('#training-date').inputValue()===point.date,'narrow keyboard exact date after resize');
      await page.locator('#training-chart').blur();await page.evaluate(()=>window.scrollTo(0,0));
      await page.screenshot({path:`output/playwright/p4-02-second-height-${width}-${range==='3 months'?'90':'365'}-private.png`,fullPage:true});
    }
  }
  await page.setViewportSize({width:1280,height:900});await page.getByRole('button',{name:'3 months',exact:true}).click();await sync();
  await page.screenshot({path:'output/playwright/p4-02-desktop-final.png',fullPage:true});
  for(const width of [320,390]){
    const context=await page.context().browser().newContext({viewport:{width,height:844},hasTouch:true,isMobile:true,timezoneId:'America/Los_Angeles'});
    const touchPage=await context.newPage();await touchPage.goto('http://127.0.0.1:8772/training-state');await touchPage.waitForSelector('#training-date');
    for(const range of ['3 months','12 months']){
      await touchPage.getByRole('button',{name:range,exact:true}).click();await touchPage.locator('#training-chart').scrollIntoViewIfNeeded();
      for(const region of ['trend','strip']){
        const point=await touchPage.locator('#training-chart').evaluate((c,region)=>{
          const ds=JSON.parse(document.querySelector('#training-state-data').textContent).days;
          const first=ds.findIndex(d=>d.day===document.querySelector('#training-date').min);
          const i=first+Math.floor((ds.length-1-first)*(region==='trend'?.35:.7)),p=c.createSVGPoint();
          p.x=45+(c.viewBox.baseVal.width-60)*(i-first)/(ds.length-1-first);
          p.y=region==='trend'?(+c.dataset.plotTop+ +c.dataset.plotBottom)/2:+c.dataset.stripBottom-25;
          const s=p.matrixTransform(c.getScreenCTM());return {x:s.x,y:s.y,date:ds[i].day};
        },region);
        await touchPage.touchscreen.tap(point.x,point.y);
        assert(await touchPage.locator('#training-date').inputValue()===point.date,'touch exact date on '+region);
        assert((await touchPage.locator('#training-day-heading').textContent()).includes(point.date),'touch synchronizes selected-day details');
        assert(await touchPage.locator('#training-tooltip').getAttribute('data-day')===point.date,'touch tooltip exact date');
      }
    }
    await context.close();
  }
  if(failures.length)throw new Error(JSON.stringify({checks,failures}));
  return {checks,passed:true,ranges:4,lineToggles:3,multiRide:true,unscored:true,noRecord:true,keyboard:true,phone:true,touch:true,stableReview:true,floatingHover:true,hoverPersistence:true,hoverAllRanges:true};
}
