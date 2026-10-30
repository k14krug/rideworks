/* Run against tools/preview_relative_effort.py on port 18874 via Playwright. */
async page => {
  const base = 'http://127.0.0.1:18874';
  const widths = [1440, 1024, 850, 768, 650, 390, 320];
  const errors = [], geometry = [];
  let checks = 0;
  const check = (v, m) => { checks++; if (!v) throw new Error(m); };
  page.on('pageerror', e => errors.push(e.name));
  const open = async path => {
    const response = await page.goto(base + path);
    check(response.status() === 200, 'route ' + path.split('?')[0]);
    await page.waitForLoadState('networkidle');
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'no page overflow');
  };
  for (const width of widths) {
    await page.setViewportSize({width, height: 900});
    await open('/');
    const home = await page.locator('.home-recent-row:not([hidden])').evaluateAll(ns => ns.map(n => {
      const s = n.querySelector('.effort-score'), link = n.querySelector('.home-recent-ride');
      return {href:link.getAttribute('href'), label:s.getAttribute('aria-label'), color:getComputedStyle(s).color,
        titleLeft:link.getBoundingClientRect().left, effortLeft:s.getBoundingClientRect().left};
    }));
    check(home.length >= 6, 'at least six recent activities');
    check(home.every(x => Math.abs(x.titleLeft - home[0].titleLeft) < 1 && Math.abs(x.effortLeft - home[0].effortLeft) < 1), 'Home title and effort columns align');
    const recent = await page.locator('.home-recent').evaluate(card => {
      const list = card.querySelector('.home-recent-list');
      const rows = [...card.querySelectorAll('.home-recent-row')];
      const visible = rows.filter(row => !row.hidden);
      const listBounds = list.getBoundingClientRect(), cardBounds = card.getBoundingClientRect();
      const style = getComputedStyle(card);
      const limit = (innerWidth > 1100 ? cardBounds.bottom : cardBounds.top + (innerWidth <= 620 ? 1036 : 495))
        - parseFloat(style.paddingBottom) - parseFloat(style.borderBottomWidth);
      const next = rows.find(row => row.hidden);
      if (next) next.hidden = false;
      const nextExceeds = !next || next.getBoundingClientRect().bottom > limit - 1;
      if (next) next.hidden = true;
      return {height:cardBounds.height, visible:visible.length,
        allComplete:visible.every(row => row.getBoundingClientRect().bottom <= listBounds.bottom + 1),
        ordered:rows.every((row, i) => i < visible.length ? !row.hidden : row.hidden), nextExceeds,
        typeLine:rows.some(row => row.querySelector('td[data-label="Ride"] > span')),
        companion:document.querySelector('.home-companions').getBoundingClientRect().height};
    });
    check(recent.allComplete && recent.ordered && !recent.typeLine && recent.nextExceeds, 'complete and maximally fitted rows');
    if (width > 1100) check(Math.abs(recent.height - recent.companion) < 1, 'recent card matches companion height');
    else check(recent.height <= (width <= 620 ? 1036 : 495) + 1, 'recent card height');
    check(await page.locator('#home-annual-chart, #home-power-chart, #home-fitness-chart').count() === 3, 'Home charts');
    check((await page.locator('.home-annual-goal').innerText()).includes('2,200'), 'annual goal');
    if (width === 1440) {
      const a = await page.locator('.home-goal-progress').boundingBox();
      const b = await page.locator('.home-mileage').boundingBox();
      check(a.height <= b.height + 1, 'annual card fits');
    }
    await open('/activities');
    const list = await page.locator('.activity-row').evaluateAll(ns => ns.map(n => {
      const s = n.querySelector('.effort-score');
      return {href:n.getAttribute('href'), label:s.getAttribute('aria-label'), color:getComputedStyle(s).color,
        titleWidth:n.querySelector('h2').getBoundingClientRect().width,
        titleLeft:n.querySelector('h2').getBoundingClientRect().left, effortLeft:s.getBoundingClientRect().left};
    }));
    check(list.every(x => Math.abs(x.titleLeft - list[0].titleLeft) < 1 && Math.abs(x.effortLeft - list[0].effortLeft) < 1), 'Activities title and effort columns align');
    for (const h of home) {
      const entry = list.find(x => x.href === h.href);
      check(!!entry && entry.label === h.label && entry.color === h.color, 'Home and Activities agree');
    }
    const minTitle = Math.min(...list.map(x => x.titleWidth));
    check(minTitle >= 150, 'usable title width');
    const samples = [list.find(x => x.label.startsWith('Strava Relative Effort:')), list.find(x => x.label.endsWith('unavailable'))];
    check(samples.every(Boolean), 'rated and missing samples');
    for (const item of samples) {
      await open(item.href);
      const card = page.locator('.relative-effort-card');
      const s = card.locator('.effort-score');
      check(await s.getAttribute('aria-label') === item.label, 'Review score agreement');
      check(await s.evaluate(n => getComputedStyle(n).color) === item.color, 'Review color agreement');
      check((await card.innerText()).includes('Strava'), 'Strava source disclosure');
      check(await card.locator('.effort-meter').count() === 0, 'no fabricated breakdown');
      check(await page.locator('.review-section-nav a').count() === 5, 'review navigation');
    }
    geometry.push({width, recentRows:recent.visible, recentHeight:Math.round(recent.height), minTitle:Math.round(minTitle)});
  }
  await page.setViewportSize({width:1440, height:900});
  await open('/');
  await page.locator('.home-recent-ride').first().evaluate(link => {
    link.append(document.createTextNode(' Synthetic long title '.repeat(12)));
    window.dispatchEvent(new Event('resize'));
  });
  for (const width of [390, 320, 850, 1440]) {
    await page.setViewportSize({width, height:900});
    await page.evaluate(() => window.dispatchEvent(new Event('resize')));
    await page.waitForTimeout(100);
    check(await page.locator('.home-recent-list').evaluate(list => {
      const rows = [...list.querySelectorAll('.home-recent-row')], visible = rows.filter(row => !row.hidden);
      const bottom = list.getBoundingClientRect().bottom;
      return visible.length > 0 && !rows[0].hidden && visible.every(row => row.getBoundingClientRect().bottom <= bottom + 1)
        && rows.slice(visible.length).every(row => row.hidden);
    }), 'long title and resize preserve complete ordered rows');
  }
  for (const path of ['/training-state','/plan','/performance','/settings']) await open(path);
  check(errors.length === 0, 'no browser script errors');
  return {checks, widths, geometry, errors};
}
