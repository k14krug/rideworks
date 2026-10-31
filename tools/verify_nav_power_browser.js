/* Playwright run-code check against a disposable synthetic RideWorks Store. */
async page => {
  const base = page.url().split('/').slice(0, 3).join('/');
  const errors = [];
  let checks = 0;
  const check = (condition, message) => { checks++; if (!condition) throw Error(message); };
  const group = () => page.getByRole('group', {name:'Power'});
  const link = name => group().getByRole('link', {name, exact:true});
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base + '/activities');
  const activity = await page.locator('a[href^="/activities/"]').first().getAttribute('href');

  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({width, height:900});
    for (const [path, name, shown, hidden] of [
      ['/performance','20-Minute History','#performance-history-mode','#power-curve-panel'],
      ['/performance?curve=1','Power Curve','#power-curve-panel','#performance-history-mode']]) {
      await page.goto(base + path); await page.reload();
      check(await group().locator('[aria-current=page]').innerText() === name, 'direct/reloaded current view');
      check(await page.locator(shown).isVisible() && await page.locator(hidden).isHidden(), 'only requested view visible');
      check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'no horizontal overflow');
      check(await link('20-Minute History').isVisible() && await link('Power Curve').isVisible(), 'both links visible');
    }
  }

  await page.setViewportSize({width:1440, height:900});
  for (const path of ['/', '/activities', activity, '/training-state', '/plan', '/settings']) {
    for (const [name, target] of [['20-Minute History','/performance'], ['Power Curve','/performance?curve=1']]) {
      await page.goto(base + path);
      check(await group().locator('[aria-current=page]').count() === 0, 'other pages do not mark a Power child current');
      await link(name).click();
      check(page.url() === base + target && await group().locator('[aria-current=page]').innerText() === name, 'child navigation');
    }
  }

  await page.goto(base + '/performance?curve_tz=UTC');
  await page.getByRole('button', {name:'All', exact:true}).click();
  await page.getByRole('button', {name:'Yearly best'}).click();
  await link('Power Curve').click();
  await page.locator('#curve-a').selectOption('previous');
  await page.locator('#curve-b').selectOption('ytd');
  await link('20-Minute History').click();
  check(await page.getByRole('button', {name:'All', exact:true}).getAttribute('aria-pressed') === 'true', 'history range retained');
  check(await page.getByRole('button', {name:'Yearly best'}).getAttribute('aria-pressed') === 'true', 'history view retained');
  await link('Power Curve').click();
  check(await page.locator('#curve-a').inputValue() === 'previous' && await page.locator('#curve-b').inputValue() === 'ytd', 'curve selections retained');
  check(page.url().includes('curve_tz=UTC'), 'timezone preserved');
  await page.goBack();
  check(await group().locator('[aria-current=page]').innerText() === '20-Minute History', 'browser back');
  await page.goForward();
  check(await group().locator('[aria-current=page]').innerText() === 'Power Curve', 'browser forward');
  await page.reload();
  check(await page.locator('#power-curve-panel').isVisible(), 'curve URL reload');
  await page.locator('#curve-a').selectOption('six');
  await page.locator('#power-curve-chart').focus();
  await page.keyboard.press('Home');
  check(await page.locator('#power-curve-chart').getAttribute('data-duration') === '1', 'curve keyboard Home');
  await page.keyboard.press('ArrowRight');
  check(await page.locator('#power-curve-chart').getAttribute('data-duration') === '2', 'curve keyboard next anchor');
  await page.locator('#curve-a-link').click();
  check(await page.locator('#power-curve-panel').isVisible(), 'Activity Review curve');
  check(await page.locator('#curve-b').inputValue() === 'six', 'Activity Review default baseline');
  await page.locator('#curve-b').selectOption('year');
  check(await page.locator('#curve-b').inputValue() === 'year', 'Activity Review comparison');

  await page.goto(base + '/');
  await link('20-Minute History').focus(); await page.keyboard.press('Tab');
  const focus = await page.evaluate(() => ({text:document.activeElement.textContent,
    style:getComputedStyle(document.activeElement).outlineStyle, width:getComputedStyle(document.activeElement).outlineWidth}));
  check(focus.text === 'Power Curve' && focus.style !== 'none' && focus.width !== '0px', 'keyboard order and visible focus');
  await page.setViewportSize({width:1024, height:320});
  await page.reload();
  await page.getByRole('navigation', {name:'Main'}).getByRole('link', {name:'Settings'}).focus();
  check(await page.locator('.sidebar').evaluate(el => el.scrollHeight > el.clientHeight && el.scrollTop > 0), 'short sidebar scrolls to focus');
  check(errors.length === 0, 'no browser script errors');
  return {checks, viewports:[1440,1024,768,390,320], sourcePages:6, errors};
}
