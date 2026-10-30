// Run with playwright-cli run-code --filename tools/verify_home_ui04.js.
// Ports are disposable Stores created by tools/preview_relative_effort.py and preview_home.py.
async page => {
  let checks = 0;
  const check = (condition, message) => { if (!condition) throw new Error(message); checks++; };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:18890/');
  const before = await page.locator('.next-recommended').innerText();
  const lowerBefore = await page.locator('.home-layout, .home-progress-layout').evaluateAll(nodes => nodes.map(n => n.innerText));
  await page.goto('http://127.0.0.1:18888/');
  check(await page.locator('.next-recommended').innerText() === before, 'Dynamic recommendation changed');
  check(JSON.stringify(await page.locator('.home-layout, .home-progress-layout').evaluateAll(nodes => nodes.map(n => n.innerText))) === JSON.stringify(lowerBefore), 'Lower card text changed');
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({width, height: 900});
    await page.reload();
    const layout = await page.evaluate(() => {
      const lead = document.querySelector('.home-lead');
      const summary = lead.querySelector('.home-summary');
      const recommendation = lead.querySelector('.next-recommended');
      const box = n => { const r = n.getBoundingClientRect(); return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width}; };
      const groups = [...summary.querySelectorAll('.home-overview-metric')];
      return {pageWidth:document.documentElement.clientWidth, pageScroll:document.documentElement.scrollWidth,
        summary:box(summary), recommendation:box(recommendation),
        groups:groups.map(n => ({...box(n), client:n.clientWidth, scroll:n.scrollWidth})),
        fitness:summary.querySelector('#home-fitness strong').textContent,
        chartFitness:document.querySelector('#home-fitness-chart .home-chart-endpoint')?.dataset.value,
        mileage:summary.querySelector('#home-last7 strong').textContent,
        data:JSON.parse(document.querySelector('#dashboard-data').textContent)};
    });
    check(layout.pageScroll <= layout.pageWidth + 1, `${width}: horizontal overflow`);
    check(layout.groups.length === 3 && layout.groups.every(g => g.scroll <= g.client + 1), `${width}: clipped metric`);
    check(layout.groups.every((g, i) => layout.groups.slice(0, i).every(p =>
      g.x >= p.right - 1 || g.y >= p.bottom - 1)), `${width}: overlapping metrics`);
    check(width <= 1100 ? layout.recommendation.y >= layout.summary.bottom - 1 : layout.recommendation.x >= layout.summary.right - 1, `${width}: top cards overlap`);
    if (width === 1440) check(Math.abs(layout.summary.width / (layout.summary.width + layout.recommendation.width) - .6) < .02, 'Desktop proportions');
    if (layout.chartFitness !== undefined) check(layout.fitness === Number(layout.chartFitness).toFixed(1), `${width}: Fitness differs from chart`);
    check(layout.mileage === `${layout.data.last7.miles.toLocaleString('en-US', {minimumFractionDigits:1, maximumFractionDigits:1})} mi`, `${width}: mileage differs from dashboard`);
    check(await page.locator('.home-summary a[href="/training-state"]').count() === 1 && await page.locator('.home-summary a[href="/performance/ftp"]').count() === 1, `${width}: missing links`);
    check(await page.locator('.home-summary').innerText().then(s => !s.includes('20-minute') && !s.includes('This Week')), `${width}: redundant facts`);
    check(await page.locator('.home-training, .home-performance, .home-recent, .home-mileage, .home-goal-progress, .home-diagnostics').count() === 6, `${width}: missing existing cards`);
  }
  await page.locator('.home-summary a[href="/performance/ftp"]').focus();
  check(await page.evaluate(() => document.activeElement.getAttribute('href')) === '/performance/ftp', 'FTP link not keyboard focusable');
  await page.goto('http://127.0.0.1:18889/');
  check(await page.locator('#home-fitness strong').innerText() === 'Unavailable', 'Missing Fitness must stay unavailable');
  check(await page.locator('#home-ftp strong').innerText() === 'Unavailable', 'Missing FTP must stay unavailable');
  check(await page.locator('#home-last7 strong').innerText() === '0.0 mi', 'Empty mileage is a supported zero');
  await page.setViewportSize({width:320, height:900});
  await page.locator('#home-last7 strong').evaluate(n => { n.textContent = '1,234.5 mi'; });
  for (const selector of ['#home-ftp strong', '#home-last7 strong']) {
    const lines = await page.locator(selector).evaluate(n => {
      const range = document.createRange(); range.selectNodeContents(n);
      return range.getClientRects().length;
    });
    check(lines === 1, `${selector}: long value wraps at 320px`);
  }
  await page.goto('http://127.0.0.1:18892/');
  const completedBefore = await page.locator('.next-recommended').textContent();
  const completedLinks = await page.locator('.plan-completed article a').evaluateAll(nodes => nodes.map(n => n.getAttribute('href')));
  check(completedLinks.length > 0, 'Completed-ride fixture is missing');
  await page.goto('http://127.0.0.1:18891/');
  const compact = text => text.replace(/\s+/g, ' ').trim();
  check(compact(await page.locator('.next-recommended').textContent()) === compact(completedBefore), 'Completed recommendation content changed');
  check(JSON.stringify(await page.locator('.plan-completed article a').evaluateAll(nodes => nodes.map(n => n.getAttribute('href')))) === JSON.stringify(completedLinks), 'Completed ride links changed');
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({width, height:900});
    await page.reload();
    const layout = await page.evaluate(() => {
      const box = s => document.querySelector(s).getBoundingClientRect();
      const summary = box('.home-summary'), recommendation = box('.next-recommended');
      return {pageWidth:document.documentElement.clientWidth, pageScroll:document.documentElement.scrollWidth,
        summary:{height:summary.height, bottom:summary.bottom}, recommendation:{height:recommendation.height, top:recommendation.top}};
    });
    check(layout.pageScroll <= layout.pageWidth + 1, `${width}: completed ride overflows`);
    check(width > 1100 ? layout.summary.height < layout.recommendation.height : layout.recommendation.top >= layout.summary.bottom - 1,
          `${width}: completed ride stretches or overlaps the overview`);
    check(await page.locator('.home-recommendation-icon svg').count() === 1 && await page.locator('.plan-completed article a').count() === completedLinks.length,
          `${width}: recommendation icon or completed ride link missing`);
  }
  check(errors.length === 0, `Browser errors: ${errors.join('; ')}`);
  return `${checks} synthetic HOME-UI-04 browser checks passed`;
}
