/* Synthetic preview servers: baseline :18861, current :18862. Run with Playwright CLI. */
async page => {
 const old=await page.context().newPage(), out=[];
 for(const width of [1440,1280,1100,768,740,620,390,320]) {
  await page.setViewportSize({width,height:1080}); await old.setViewportSize({width,height:1080});
  await page.goto('http://127.0.0.1:18862/?home_tz=UTC'); await old.goto('http://127.0.0.1:18861/?home_tz=UTC');
  await page.waitForLoadState('networkidle'); await old.waitForLoadState('networkidle');
  const measure=async p=>p.evaluate(()=>{const card=document.querySelector('.home-recent'), list=card.querySelector('.home-recent-list'), r=card.getBoundingClientRect(), lr=list.getBoundingClientRect(), rows=[...card.querySelectorAll('.home-recent-row')]; return {card:[r.width,r.height], visible:rows.filter(n=>{const b=n.getBoundingClientRect();return b.top>=lr.top-1&&b.bottom<=lr.bottom+1}).length,rowHeights:rows.slice(0,6).map(n=>n.getBoundingClientRect().height),overflow:document.documentElement.scrollWidth>innerWidth, cells:rows.slice(0,6).flatMap(n=>[...n.cells].filter(c=>c.scrollWidth>c.clientWidth+1).map(c=>c.dataset.label)),header:[...card.querySelectorAll('th')].filter(n=>n.scrollWidth>n.clientWidth+1).map(n=>n.innerText), values:rows.map(n=>n.querySelector('.home-race-power')?.textContent).filter(Boolean)};});
  const before=await measure(old),after=await measure(page);
  const fields = p => p.locator('.home-recent-row').evaluateAll(rows => rows.map(row => ({id:row.dataset.activityId, fields:[...row.cells].slice(0,6).map(cell=>cell.textContent), link:row.querySelector('a').getAttribute('href')})));
  if(JSON.stringify(await fields(page))!==JSON.stringify(await fields(old))) throw Error('existing fields or links changed');
  if(!after.values.includes('169 W') || !after.values.includes('0 W') || !after.values.includes('—')) throw Error('synthetic race and nonrace values');
  if(after.overflow||after.cells.length||after.header.length) throw Error(JSON.stringify({width,before,after}));
  if(width>1100 && (Math.abs(before.card[0]-after.card[0])>1||Math.abs(before.card[1]-after.card[1])>1||after.visible<before.visible)) throw Error('desktop geometry '+JSON.stringify({width,before,after}));
  if(width<=900 && !await page.locator('.home-race-power').first().evaluate(n=>getComputedStyle(n,'::before').content.includes('Race Avg W'))) throw Error('mobile label');
  await page.screenshot({path:`output/playwright/home-ui-06-${width}.png`});
  out.push({width,before,after});
 }
 await old.close(); return out;
}
