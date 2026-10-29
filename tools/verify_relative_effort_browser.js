/* Run against the synthetic preview Store on port 18872 via Playwright. */
async page => {
  const base = 'http://127.0.0.1:18872';
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
    const home = await page.locator('.home-recent-row:not([hidden]) .home-recent-ride').evaluateAll(ns => ns.map(n => ({
      href:n.getAttribute('href'), label:n.getAttribute('aria-label').split('Relative effort: ')[1],
      color:getComputedStyle(n.querySelector('.home-effort-dot')).backgroundColor
    })));
    check(home.length >= 6, 'at least six recent activities');
    const recent = await page.locator('.home-recent').evaluate(card => {
      const list = card.querySelector('.home-recent-list');
      const rows = [...card.querySelectorAll('.home-recent-row')];
      const visible = rows.filter(row => !row.hidden);
      const listBounds = list.getBoundingClientRect();
      const cardBounds = card.getBoundingClientRect();
      const style = getComputedStyle(card);
      const limit = (innerWidth > 1100 ? cardBounds.bottom : cardBounds.top + (innerWidth <= 620 ? 1036 : 495))
        - parseFloat(style.paddingBottom) - parseFloat(style.borderBottomWidth);
      const next = rows.find(row => row.hidden);
      if (next) next.hidden = false;
      const nextExceeds = !next || next.getBoundingClientRect().bottom > limit - 1;
      if (next) next.hidden = true;
      return {
        height:cardBounds.height, visible:visible.length,
        allComplete:visible.every(row => row.getBoundingClientRect().bottom <= listBounds.bottom + 1),
        ordered:rows.every((row, i) => i < visible.length ? !row.hidden : row.hidden),
        nextExceeds,
        typeLine:rows.some(row => row.querySelector('td:nth-child(2) > span')),
        companion:document.querySelector('.home-companions').getBoundingClientRect().height
      };
    });
    check(recent.allComplete && recent.ordered && !recent.typeLine, 'complete ordered rows without ride-type lines');
    check(recent.nextExceeds, 'no additional complete row fits');
    if (width > 1100) check(Math.abs(recent.height - recent.companion) < 1, 'recent card matches companion height');
    else check(recent.height <= (width <= 620 ? 1036 : 495) + 1, 'recent card stays within prior height');
    check(home.some(x => x.label === 'Not rated') && home.some(x => x.label !== 'Not rated'), 'rated and unrated synthetic rides');
    check(await page.locator('#home-annual-chart, #home-power-chart, #home-fitness-chart').count() === 3, 'current Home charts');
    check((await page.locator('.home-annual-goal').innerText()).includes('2,200'), 'annual goal');
    if (width === 1440) {
      const a = await page.locator('.home-goal-progress').boundingBox();
      const b = await page.locator('.home-mileage').boundingBox();
      check(a.height <= b.height + 1, 'annual card fits');
    }
    await page.locator('.home-recent-ride').first().focus();
    check(await page.locator('.home-recent-ride').first().evaluate(n => n === document.activeElement), 'Home link focus');
    await open('/activities');
    const list = await page.locator('.activity-row').evaluateAll(ns => ns.map(n => ({
      href:n.getAttribute('href'), label:n.querySelector('.row-effort .effort-pill')?.textContent.trim(),
      color:getComputedStyle(n.querySelector('.effort-pill'),'::before').backgroundColor,
      titleWidth:n.querySelector('h2').getBoundingClientRect().width, height:n.getBoundingClientRect().height
    })));
    for (const h of home) {
      const entry = list.find(x => x.href === h.href);
      check(!!entry && entry.label === h.label && entry.color === h.color, 'Home and Activities agree');
    }
    const minTitle = Math.min(...list.map(x => x.titleWidth));
    check(minTitle >= 150, 'usable title width');
    for (const item of [home.find(x => x.label !== 'Not rated'), home.find(x => x.label === 'Not rated')]) {
      await open(item.href);
      const card = page.locator('.relative-effort-card');
      check(await card.locator('.relative-effort-overall strong').innerText() === item.label, 'Review category agreement');
      check(await card.locator('.relative-effort-context').innerText() !== '', 'rating context or unavailable reason');
      if (item.label !== 'Not rated') {
        check(await card.locator('.effort-component').count() === 2, 'load and intensity');
        const chart = page.locator('#chart-svg');
        check(await chart.count() === 1, 'Review chart present');
        await chart.focus(); await page.keyboard.press('Home');
        const readout = page.locator('#sample-readout');
        check((await readout.getAttribute('data-sample-index')) !== null ||
              (await readout.getAttribute('data-record-index')) !== null, 'keyboard chart readout');
      }
      await card.locator('summary').focus(); await page.keyboard.press('Enter');
      check(await card.locator('details').evaluate(n => n.open), 'keyboard explanation');
      check(await page.locator('.review-section-nav a').count() === 5, 'review navigation');
    }
    geometry.push({width, recentRows:recent.visible, recentHeight:Math.round(recent.height), minTitle:Math.round(minTitle), maxRowHeight:Math.round(Math.max(...list.map(x=>x.height)))});
  }
  await page.setViewportSize({width:1440, height:900});
  await open('/');
  await page.locator('.home-recent-ride').first().evaluate(link => {
    link.append(document.createTextNode(' Synthetic long title '.repeat(12)));
    window.dispatchEvent(new Event('resize'));
  });
  for (const width of [390, 320, 850, 1440]) {
    await page.setViewportSize({width, height:900});
    await page.waitForTimeout(100);
    check(await page.locator('.home-recent-list').evaluate(list => {
      const rows = [...list.querySelectorAll('.home-recent-row')];
      const visible = rows.filter(row => !row.hidden);
      const bottom = list.getBoundingClientRect().bottom;
      return visible.length > 0 && !rows[0].hidden &&
        visible.every(row => row.getBoundingClientRect().bottom <= bottom + 1) &&
        rows.slice(visible.length).every(row => row.hidden);
    }), 'long title and resize preserve complete ordered rows');
  }
  for (const path of ['/training-state','/plan','/performance','/settings']) await open(path);
  check(errors.length === 0, 'no browser script errors');
  return {checks, widths, geometry, errors};
}
