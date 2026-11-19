async page => {
  const base = 'http://127.0.0.1:18774';
  const ctx = page.context();
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: base});
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto(base + '/segments');
  const panel = page.getByRole('region', {name: 'Import history'});
  const paste = page.getByLabel('Paste My Results');
  const select = page.getByLabel('Watched segment');
  const watched = '9007199254740995';
  await select.selectOption(watched);
  const assert = (condition, label) => { if (!condition) throw Error(label); };
  const noOverflow = async () => assert(await panel.evaluate(card => {
    const x = card.getBoundingClientRect();
    return document.documentElement.scrollWidth <= innerWidth &&
      [...card.querySelectorAll('select,textarea')].every(el => {
        const field = el.getBoundingClientRect();
        return field.width > 0 && field.right <= x.right && field.left >= x.left;
      });
  }), 'card field overflow');

  const saved = page.locator('.segment-card').filter({has: page.getByRole('heading', {name: 'Synthetic Watched Loop'})});
  const summary = saved.getByText('View 102 saved efforts');
  await summary.waitFor();
  assert(!(await saved.locator('details').evaluate(e => e.open)), 'long history should start closed');
  await summary.click();
  assert(await saved.getByRole('row').count() === 103, 'date/time/source/ride columns and 102 effort rows');
  assert(await saved.getByRole('columnheader').allTextContents().then(a => a.join('/') === 'Date/Time/Source/Ride'), 'column headings');
  await summary.click();

  const source = await ctx.newPage();
  await source.goto(base + '/segments');
  await source.setContent('<table><tr><th>Rank</th><th>Name</th><th>Date</th><th>Speed</th><th>HR</th><th>Power</th><th>Time</th></tr>'
    + '<tr><td>1</td><td>Rider</td><td><a href="https://www.strava.com/activities/9007199254740993">Mar 9, 2024</a></td><td>21.5 mph</td><td>146 bpm</td><td>191 W</td><td>34:24</td></tr>'
    + '<tr><td>2</td><td>Rider</td><td><a href="https://example.invalid/activities/12">Mar 10, 2024</a></td><td></td><td></td><td></td><td>35:05</td></tr></table>');
  await source.bringToFront();
  await source.evaluate(() => {
    const range = document.createRange();
    range.selectNode(document.querySelector('table'));
    getSelection().removeAllRanges();
    getSelection().addRange(range);
  });
  await source.keyboard.press('Control+c');
  await page.bringToFront();
  const types = await page.evaluate(async () => (await navigator.clipboard.read()).flatMap(item => item.types));
  assert(types.includes('text/html') && types.includes('text/plain'), 'native rich clipboard types');
  await paste.focus();
  await page.keyboard.press('Control+v');
  assert(await paste.inputValue() === 'Mar 9, 2024\thttps://www.strava.com/activities/9007199254740993\t34:24\nMar 10, 2024\t35:05', 'canonical link extraction');
  await noOverflow();

  await page.evaluate(() => {
    document.addEventListener('submit', event => {
      const status = document.querySelector('#history-progress');
      if (event.target.matches('#history-import-form') && status.getBoundingClientRect().height > 0) {
        console.log(status.textContent);
      }
    }, {once: true});
  });
  const statusEvent = page.waitForEvent('console', {predicate: event => event.text() === 'Reading pasted results…'});
  await page.getByRole('button', {name: 'Preview paste'}).click();
  await statusEvent;
  await panel.getByText(/2 readable rows · 1 unique ride links · 0 unparsed/).waitFor();
  await panel.getByRole('button', {name: 'Save history'}).click();
  await panel.getByText(/Saved 2 pasted results/).waitFor();
  await saved.getByText('View 104 saved efforts').click();
  assert(await saved.getByRole('link', {name: 'Strava activity', exact: true}).count() === 1, 'one canonical pasted link saved');
  await saved.getByText('View 104 saved efforts').click();

  await page.setViewportSize({width: 390, height: 900});
  const bad = 'copied unrelated sentence';
  await page.evaluate(async value => navigator.clipboard.writeText(value), bad);
  await paste.focus();
  await page.keyboard.press('Control+v');
  await page.getByRole('button', {name: 'Preview paste'}).click();
  await panel.getByText('Nothing imported.').waitFor();
  assert(await paste.inputValue() === bad, 'failed paste retained');
  assert(await select.inputValue() === watched, 'selected watch retained');
  assert(await panel.getByRole('button', {name: 'Save history'}).count() === 0, 'zero results cannot be saved');
  await noOverflow();

  const plain = '1 Rider Apr 11, 2024 21.5 mph 146 bpm\n191 Wsvg\n34:42\n2 Rider Apr 12, 2024\n35:20\n3 Rider Apr 13, 2024\n—\n36:31';
  await page.evaluate(async value => navigator.clipboard.writeText(value), plain);
  const plainTypes = await page.evaluate(async () => (await navigator.clipboard.read()).flatMap(item => item.types));
  assert(plainTypes.length === 1 && plainTypes[0] === 'text/plain', 'text-only clipboard');
  await paste.focus();
  await page.keyboard.press('Control+a');
  await page.keyboard.press('Control+v');
  await page.getByRole('button', {name: 'Preview paste'}).click();
  await panel.getByText(/3 readable rows · 0 unique ride links · 0 unparsed/).waitFor();
  await panel.getByRole('button', {name: 'Save history'}).click();
  await panel.getByText(/Saved 3 pasted results/).waitFor();

  await page.getByRole('button', {name: 'From Strava'}).click();
  await panel.getByText(/2 validated efforts · 0 already saved · 2 to save/).waitFor();
  await panel.getByRole('button', {name: 'Save history'}).click();
  await panel.getByText('Saved 2 Strava efforts. 0 already saved.').waitFor();
  await saved.getByText('View 109 saved efforts').click();
  assert(await saved.getByRole('row').count() === 110, 'both sources and prior efforts preserved');
  assert(await saved.locator('tbody .segment-cell-label').first().isVisible(), 'narrow labels visible');
  await noOverflow();
  await saved.getByText('View 109 saved efforts').click();
  await page.getByRole('heading', {name: 'Synthetic Second Loop'}).waitFor();
  await source.close();
  return {richClipboardTypes: types, nativeCopyPaste: true, richRows: 2, linked: 1, textOnlyRows: 3,
    progress: true, zeroRetained: true, apiRows: 2, finalSaved: 109, viewports: [1440, 390]};
}
