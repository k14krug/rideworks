async page => {
  const base = 'http://127.0.0.1:18774';
  const context = page.context();
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], {origin: base});
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto(base + '/segments');
  const watched = '9007199254740995';
  const name = 'Synthetic Watched Loop';
  const card = page.locator('.segment-card').filter({has: page.getByRole('heading', {name})});
  const table = card.getByRole('table');
  const displayed = () => table.locator('tbody tr').count();
  const first = index => table.locator(`tbody tr:first-child td:nth-child(${index}) > div`);
  const last = index => table.locator(`tbody tr:last-child td:nth-child(${index}) > div`);
  const panel = card.getByRole('region', {name: 'Import history'});
  const paste = panel.getByLabel('Paste My Results');
  const previewButton = panel.getByRole('button', {name: 'Preview paste'});
  const save = panel.getByRole('button', {name: 'Save history'});
  const api = panel.getByRole('button', {name: 'From Strava'});
  const assert = (condition, label) => { if (!condition) throw Error(label); };
  const checkNoOverflow = async () => assert(await page.evaluate(() => {
    if (document.documentElement.scrollWidth > innerWidth) return false;
    return Array.from(document.querySelectorAll('.segments-page textarea, .segments-page input[type=url], .segments-page select'))
      .filter(field => field.offsetWidth).every(field => {
        const bounds = field.closest('.panel').getBoundingClientRect();
        const rect = field.getBoundingClientRect();
        return rect.left >= bounds.left && rect.right <= bounds.right;
      });
  }), 'page or form overflow');

  const sort = (label, keyboard = false) => {
    const header = table.getByRole('link', {name: label, exact: true});
    return keyboard ? header.press('Enter') : header.click();
  };
  const direction = label => table.getByRole('columnheader', {name: label, exact: true}).getAttribute('aria-sort');
  const openImporter = () => card.getByRole('link', {name: 'Import history for ' + name}).click();
  const openHistory = () => card.locator('.segment-saved-list > summary').click();
  const screenshot = async path => {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: `/tmp/${path}`, fullPage: true, animations: 'disabled'});
  };

  assert(await page.locator('#history-import-form, #segment-link').count() === 0, 'forms initially closed');
  await page.getByRole('link', {name: 'Add segment', exact: true}).click();
  await page.getByLabel('Strava activity-effort link').waitFor();
  await checkNoOverflow();
  await page.getByRole('link', {name: 'Cancel add'}).click();
  assert(!(await card.locator('.segment-saved-list').evaluate(el => el.open)), 'history initially closed');
  await openHistory();
  assert(await displayed() === 10 && await direction('Date') === 'descending', 'newest first, ten rows');
  assert(!(await first(4).innerText()).includes('510.5'), 'oldest high power starts offscreen');
  assert(await table.getByRole('columnheader').count() === 6, 'six columns');
  assert(await table.getByRole('columnheader', {name: 'Ride'}).getByRole('link').count() === 0, 'Ride does not sort');
  assert(await table.getByText('#1 · Best', {exact: true}).count() === 0, 'tied best efforts start outside the short view');
  await sort('Rank / Behind best', true);
  assert(await direction('Rank / Behind best') === 'descending' && await first(3).innerText() === '#102 · +4:15', 'rank sorts numerically descending');
  await sort('Rank / Behind best', true);
  assert(await direction('Rank / Behind best') === 'ascending', 'rank sort direction after keyboard toggle');
  assert(await table.locator('tbody .segment-rank').allTextContents().then(ranks =>
    ranks.slice(0, 3).join('|') === '#1 · Best|#1 · Best|#3 · +0:02'), 'tied best and exact gap to third');
  await card.getByRole('link', {name: 'View all 102 efforts'}).click();
  assert(await displayed() === 102 && await last(3).innerText() === '#102 · +4:15', 'full history keeps rank and gap');
  await card.getByRole('link', {name: 'Show short history'}).click();
  await screenshot('seg02-history-desktop.png');
  await sort('Avg Power', true);
  assert(await direction('Avg Power') === 'descending' && (await first(4).innerText()).includes('510.5 W'), 'keyboard sort across all 102 rows');

  await sort('Avg Power');
  assert(await direction('Avg Power') === 'ascending' && (await first(4).innerText()).includes('92 W'), 'numeric ascending');
  await sort('Time');
  await sort('Time');
  assert(await direction('Time') === 'ascending' && (await first(2).innerText()) === '2:00', 'numeric durations');
  await table.getByRole('columnheader', {name: 'Avg HR', exact: true}).getByRole('link').click();
  assert(await direction('Avg HR') === 'descending' && (await first(5).innerText()) === '191 bpm', 'whole-history HR sort');
  await card.getByRole('link', {name: 'View all 102 efforts'}).click();
  assert(await displayed() === 102 && (await last(5).innerText()) === '—', 'full view, missing last on descending');
  await sort('Avg HR');
  assert(await direction('Avg HR') === 'ascending' && (await last(5).innerText()) === '—', 'missing last on ascending');
  await card.getByRole('link', {name: 'Show short history'}).click();
  assert(await displayed() === 10, 'return to short history');

  await openImporter();
  assert(await panel.locator('input[name=segment]').inputValue() === watched, 'per-card segment preselected');
  const source = await context.newPage();
  await source.goto(base + '/segments');
  await source.setContent('<table><tr><th>Rank</th><th>Name</th><th>Date</th><th>Speed</th><th>HR</th><th>Power</th><th>Time</th></tr>'
    + '<tr><td>1</td><td>Rider</td><td><a href="https://www.strava.com/activities/9007199254740993">Mar 9, 2024</a></td><td>21.5 mph</td><td>146 bpm</td><td>191 W</td><td>34:24</td></tr>'
    + '<tr><td>2</td><td>Rider</td><td><a href="https://example.invalid/activities/12">Mar 10, 2024</a></td><td></td><td>—</td><td>invalid W</td><td>35:05</td></tr></table>');
  await source.bringToFront();
  await source.evaluate(() => {
    const range = document.createRange();
    range.selectNode(document.querySelector('table'));
    getSelection().removeAllRanges();
    getSelection().addRange(range);
  });
  await source.keyboard.press('Control+c');
  await page.bringToFront();
  const clipboardTypes = async () => page.evaluate(async () => (await navigator.clipboard.read()).flatMap(item => item.types));
  const types = await clipboardTypes();
  assert(types.includes('text/html') && types.includes('text/plain'), 'native rich clipboard types');
  const nativePaste = async () => {
    await paste.focus();
    await page.keyboard.press('Control+a');
    await page.keyboard.press('Control+v');
  };
  await nativePaste();
  assert(await paste.inputValue() === 'Mar 9, 2024\thttps://www.strava.com/activities/9007199254740993\t146 bpm\t191 W\t34:24\nMar 10, 2024\t35:05',
    'HTML extraction retains canonical link and valid metrics');
  await checkNoOverflow();
  await page.evaluate(() => {
    document.addEventListener('submit', event => {
      const status = document.querySelector('#history-progress');
      if (event.target.matches('#history-import-form') && status.getBoundingClientRect().height > 0) {
        console.log(status.textContent);
      }
    }, {once: true});
  });
  const progress = page.waitForEvent('console', {predicate: event => event.text() === 'Reading pasted results…'});
  await previewButton.click();
  await progress;
  await panel.getByText(/2 readable rows · 1 unique ride links · 0 unparsed/).waitFor();
  await save.click();
  await panel.getByText(/Saved 2 pasted results/).waitFor();

  await page.setViewportSize({width: 390, height: 900});
  const bad = 'copied unrelated sentence';
  await page.evaluate(value => navigator.clipboard.writeText(value), bad);
  await nativePaste();
  await previewButton.click();
  await panel.getByText('Nothing imported.').waitFor();
  assert(await paste.inputValue() === bad, 'failed paste retained');
  assert(await panel.locator('input[name=segment]').inputValue() === watched, 'segment retained after error');
  assert(await save.count() === 0, 'zero results cannot be saved');
  await checkNoOverflow();

  const plain = '1 Rider Apr 11, 2024 21.5 mph 143 bpm\n193 Wsvg\n34:42\n2 Rider Apr 12, 2024\n35:20\n3 Rider Apr 13, 2024\n—\n36:31';
  await page.evaluate(value => navigator.clipboard.writeText(value), plain);
  assert((await clipboardTypes()).join() === 'text/plain', 'text-only clipboard');
  await nativePaste();
  await previewButton.click();
  await panel.getByText(/3 readable rows · 0 unique ride links · 0 unparsed/).waitFor();
  await save.click();
  await panel.getByText(/Saved 3 pasted results/).waitFor();

  await api.click();
  await panel.getByText(/2 validated efforts · 0 already saved · 2 to save/).waitFor();
  await save.click();
  await panel.getByText('Saved 2 Strava efforts. 0 already saved.').waitFor();
  await api.click();
  await panel.getByText(/2 validated efforts · 2 already saved · 0 to save/).waitFor();
  assert(await save.count() === 0, 'API replay adds no effort');
  await card.getByRole('link', {name: 'Close import'}).click();
  assert(await displayed() === 10, 'history opens without expanded import');
  assert(await table.locator('tbody .segment-cell-label').first().isVisible(), 'narrow row labels');
  assert((await first(4).innerText()).includes('—'), 'malformed API power is unavailable');
  await table.getByRole('link', {name: 'Avg Power', exact: true}).click();
  assert((await first(4).innerText()).includes('510.5 W'), 'sorting available at 390 px');
  await checkNoOverflow();
  await screenshot('seg02-history-390.png');

  await card.getByRole('link', {name: 'View all 109 efforts'}).click();
  assert(await displayed() === 109, 'all prior, clipboard, and API efforts preserved');
  const rich = table.getByRole('row').filter({has: page.getByText('34:24', {exact: true})});
  await rich.getByText('Effort details', {exact: true}).click();
  await rich.getByRole('link', {name: 'Strava activity', exact: true}).waitFor();
  await rich.getByRole('link', {name: 'RideWorks ride', exact: true}).waitFor();
  await rich.getByText('Avg Power · My Results paste · Power status unknown', {exact: true}).waitFor();
  await rich.getByText('191 W', {exact: true}).waitFor();
  await table.getByText('193 W', {exact: true}).waitFor();
  await table.getByText('251.5 W', {exact: true}).waitFor();
  await checkNoOverflow();
  for (const path of ['/', '/activities']) {
    await page.goto(base + path);
    await page.getByRole('link', {name: '2 tracked segments', exact: true}).click();
    await page.getByRole('link', {name: 'All watched segments'}).waitFor();
    await page.getByRole('heading', {name: 'Synthetic West Loop'}).waitFor();
    await sort('Rank / Behind best', true);
    await sort('Rank / Behind best', true);
    assert(await first(3).innerText() === '#3 · +0:02', 'filtered ride keeps rank from all saved efforts');
    assert(await table.getByText('#1 · Best', {exact: true}).count() === 0, 'fastest efforts belong to another ride');
    await checkNoOverflow();
  }
  await source.close();
  return {richClipboard: types, richRows: 2, localLink: 1, plainRows: 3, apiRows: 2,
    replay: true, fullHistory: 109, shortView: 10, numericSort: true, missingLast: true, rankTiesAndRideFilter: true,
    progressAndRecovery: true, viewports: [1440, 390], screenshots: 2};
}
