/* Synthetic-only HOME-UI-02 checks, executed through Playwright CLI. */
async page => {
  const config = CASE_INPUT;
  let checks = 0;
  const errors = [], geometry = [], variants = [];
  const check = (value, message) => { checks++; if (!value) throw new Error(message); };
  page.on('pageerror', error => errors.push(error.name));
  const baseline = await page.context().newPage();
  const inspect = async () => {
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'no horizontal page overflow');
    const charts = await page.locator('.home-trend-chart').all();
    for (const chart of charts) {
      const invalid = await chart.evaluate(svg => {
        const v = svg.viewBox.baseVal;
        return [...svg.querySelectorAll('text')].filter(n => {
          const b = n.getBBox();
          return b.x < 0 || b.y < 0 || b.x + b.width > v.width + .5 || b.y + b.height > v.height + .5;
        }).map(n => n.textContent);
      });
      check(invalid.length === 0, 'chart labels inside SVG: ' + JSON.stringify(invalid));
      const overlaps = await chart.evaluate(svg => {
        const labels = [...svg.querySelectorAll('text')].map(n => n.getBoundingClientRect());
        return labels.some((a,i) => labels.slice(i+1).some(b => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top));
      });
      check(!overlaps, 'axis and endpoint labels do not overlap');
      check(await chart.evaluate(svg => {
        const r = svg.getBoundingClientRect(), card = svg.closest('section').getBoundingClientRect();
        return r.left >= card.left && r.right <= card.right + .5 && r.top >= card.top && r.bottom <= card.bottom + .5;
      }), 'chart fits its card');
      check(await chart.getAttribute('role') === 'img', 'accessible static chart');
      check(await chart.locator(':scope > title').count() === 1 && await chart.locator(':scope > desc').count() === 1, 'chart title and evidence description');
    }
  };
  for (const width of [1440,1024,768,390,320]) {
    await page.setViewportSize({width,height:1080});
    await baseline.setViewportSize({width,height:1080});
    check((await page.goto(config.base+'/?home_tz=America%2FLos_Angeles')).status() === 200, 'Home route');
    await baseline.goto(config.baseline+'/?home_tz=America%2FLos_Angeles');
    await Promise.all([page.waitForLoadState('networkidle'),baseline.waitForLoadState('networkidle')]);
    await inspect();
    const recent = await page.locator('.home-recent').boundingBox();
    const stack = await page.locator('.home-companions').boundingBox();
    const training = await page.locator('.home-training').boundingBox();
    const power = await page.locator('.home-performance').boundingBox();
    if (width > 1100) {
      check(stack.x >= recent.x + recent.width, 'right column beside Recent Activities');
      check(Math.abs(stack.y - recent.y) < 1 && Math.abs(stack.height - recent.height) < 1, 'combined card height aligns with Recent Activities');
      check(training.y + training.height < power.y, 'Training State above Performance');
    } else if (width <= 620) {
      check(recent.y + recent.height < training.y && training.y + training.height < power.y, 'mobile cards in reading order');
    } else {
      check(stack.y >= recent.y + recent.height && training.x < power.x, 'preserve tablet two-card row');
    }
    geometry.push({width,recentHeight:recent.height,companionHeight:stack.height,trainingHeight:training.height,powerHeight:power.height});
    const data = JSON.parse(await page.locator('#dashboard-data').textContent());
    check(data.performance.current.rounded_watts !== data.performance.latest.rounded_watts, 'synthetic case distinguishes best from latest');
    check(await page.locator('#home-power-chart .home-chart-endpoint text').textContent() === data.performance.current.rounded_watts+' W', 'rolling-best endpoint');
    check(await page.locator('#home-current strong').textContent() === data.performance.current.rounded_watts+' W', 'current quick fact preserved');
    check(await page.locator('#home-latest strong').textContent() === data.performance.latest.rounded_watts+' W', 'latest quick fact preserved');
    check(Number(await page.locator('#home-fitness-chart .home-chart-endpoint').getAttribute('data-value')) === config.fitness.value, 'exact Fitness source endpoint');
    check(await page.locator('#home-fitness-chart .home-chart-endpoint').getAttribute('data-day') === config.fitness.day, 'Fitness endpoint date');
    check(!(await page.locator('.home-training').textContent()).includes('Fatigue'), 'no Fatigue summary');
    check(!(await page.locator('.home-training').textContent()).includes('Form'), 'no Form summary');
    for (const selector of ['.home-summary','.next-recommended','.home-recent','.home-mileage','.home-goal-progress','.home-supporting']) {
      check(await page.locator(selector).textContent() === await baseline.locator(selector).textContent(), selector+' content preserved');
    }
    for (const [selector,href] of [['.home-training a','/training-state'],['.home-performance .home-panel-heading a','/performance']]) {
      const link = page.locator(selector);
      check(await link.getAttribute('href') === href, 'full page destination');
      await link.focus();
      check(await link.evaluate(n => n === document.activeElement), 'card link keyboard focus');
      check((await page.request.get(config.base+href)).status() === 200, 'card destination loads');
    }
    await page.evaluate(() => document.activeElement.blur());
    await page.locator('.home-layout').screenshot({path:'output/playwright/home-ui-02-layout-'+width+'.png'});
    await page.locator('.home-companions').screenshot({path:'output/playwright/home-ui-02-trends-'+width+'.png'});
    for (const variant of config.variants) {
      await page.locator('.home-training').evaluate((node,html) => {node.outerHTML=html;},variant.html);
      await inspect();
      variants.push({width,name:variant.name});
    }
    for (const variant of config.powerVariants) {
      await page.locator('.home-performance').evaluate((node,html) => {node.outerHTML=html;},variant.html);
      await inspect();
      check(await page.locator('#home-power-chart .home-chart-endpoint').count() === 0, 'no stale or invented power endpoint');
      variants.push({width,name:'power-'+variant.name});
    }
  }
  // All full-page text/markup is checked by the Python fixed-clock comparison.
  // Also compare actual browser styles and exercise the existing chart controls.
  const styles = async target => target.locator('main *').evaluateAll(nodes => nodes.map(n => {
    const s=getComputedStyle(n);
    return [n.tagName,n.getAttribute('class'),s.display,s.color,s.fontSize,s.fontWeight,s.padding,s.borderWidth,s.borderRadius];
  }));
  for (const width of [1440,1024,768,390,320]) {
    await page.setViewportSize({width,height:1080});await baseline.setViewportSize({width,height:1080});
    for (const route of ['/training-state','/performance']) {
      await page.goto(config.base+route);await baseline.goto(config.baseline+route);
      await Promise.all([page.waitForLoadState('networkidle'),baseline.waitForLoadState('networkidle')]);
      check(JSON.stringify(await styles(page)) === JSON.stringify(await styles(baseline)), 'full page styles unchanged: '+route+' at '+width);
      if (route === '/training-state') {
        await page.locator('input[data-line="form"]').check();
        check(await page.locator('input[data-line="form"]').isChecked(), 'full Training State Form toggle works');
        await page.locator('#training-chart').focus();await page.keyboard.press('Home');await page.keyboard.press('End');
        check(await page.locator('#training-chart-readout').textContent().then(Boolean), 'Training State keyboard readout');
      } else {
        await page.locator('[data-curve-mode="curve"]').click();
        check(await page.locator('#power-curve-chart').isVisible(), 'full Performance Power Curve mode');
        await page.locator('[data-curve-mode="history"]').click();
        check(await page.locator('#performance-history-mode').isVisible(), 'full Performance history mode');
      }
    }
  }
  check(errors.length === 0, 'no browser JavaScript errors');
  await baseline.close();
  await page.goto(config.base+'/?home_tz=America%2FLos_Angeles');
  return {checks,widths:[1440,1024,768,390,320],geometry,variants,fullPageStyleComparisons:10,errors};
}
