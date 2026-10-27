/* Run with Playwright CLI against the disposable Store from seed_ftp02_browser.py only. */
async page => {
  const base = new URL(page.url()).origin;
  let checks = 0;
  const check = (condition, label) => {
    checks++;
    if (!condition) throw new Error(label);
  };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base + '/performance/ftp');
  await page.waitForSelector('.ftp-entry');
  const original = JSON.parse(await page.locator('#ftp-data').textContent());
  check(original.rows.length === 2 &&
    original.rows[0].effective_from_date === '2024-01-01' && original.rows[0].ftp_watts === 180 &&
    original.rows[1].effective_from_date === '2024-11-01' && original.rows[1].ftp_watts === 200,
    'expected synthetic FTP entries');
  check(original.points.length === 1, 'synthetic ride on chart');
  check(original.points[0].watts === 190 && original.points[0].proposed === 190, '95% ride comparison');
  await page.locator('#ftp-rides button').first().click();
  check(await page.locator('#ftp-date').inputValue() === original.points[0].date, 'ride selects date');
  check(await page.locator('#ftp-watts').inputValue() === '190', 'ride suggests watts');
  await page.locator('#ftp-cancel').click();
  const stale = await page.context().newPage();
  await stale.goto(base + '/performance/ftp');
  await page.locator('#ftp-date').fill('2025-01-02');
  await page.locator('#ftp-watts').fill('160');
  check(!(await page.locator('#ftp-save').isDisabled()), 'latest manual entry enabled without a selected ride');
  const preview = await page.locator('#ftp-preview').textContent();
  check(preview.includes('200 W') && preview.includes('until another entry'), 'latest interval explained');
  const [response] = await Promise.all([
    page.waitForNavigation(), page.locator('#ftp-save').click()
  ]);
  check(response.status() === 200, 'secure form submission and redirect');
  const after = JSON.parse(await page.locator('#ftp-data').textContent());
  check(after.revision === original.revision + 1, 'revision advanced');
  check(after.rows.length === 3 && after.rows[2].effective_from_date === '2025-01-02' &&
    after.rows[2].ftp_watts === 160 && after.rows[2].effective_until_date_exclusive === null,
    'latest lower FTP stored indefinitely');
  check(after.rows[0].ftp_watts === 180 && after.rows[1].ftp_watts === 200 &&
    after.rows[1].effective_until_date_exclusive === '2025-01-02', 'old settings preserved');
  check(after.points[0].watts === original.points[0].watts, 'ride measurement preserved');
  await page.locator('#ftp-date').fill('2025-01-02');
  await page.locator('#ftp-watts').fill('175');
  check(await page.locator('#ftp-save').isDisabled(), 'duplicate date disabled');
  await stale.locator('#ftp-date').fill('2025-02-01');
  await stale.locator('#ftp-watts').fill('170');
  const [staleResponse] = await Promise.all([
    stale.waitForNavigation(), stale.locator('#ftp-save').click()
  ]);
  check(staleResponse.status() === 400, 'stale revision rejected');
  check((await stale.locator('#ftp-message').textContent()).includes('changed'), 'stale error shown');
  check(JSON.parse(await stale.locator('#ftp-data').textContent()).rows.length === 3, 'stale submission did not insert');
  await stale.close();
  check(errors.length === 0, 'no JavaScript errors');
  return {checks, result: 'PASS'};
}
