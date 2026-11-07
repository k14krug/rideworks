/* Playwright check against preview_race_results.py --seam-case. */
async page => {
  const base = new URL(page.url()).origin;
  let checks = 0;
  const check = (condition, message) => { checks++; if (!condition) throw Error(message); };
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto(base + '/race-results/import');
  await page.evaluate(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 768; canvas.height = 939;
    const context = canvas.getContext('2d');
    context.fillStyle = 'white'; context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = 'blue'; context.font = '20px sans-serif';
    context.fillText('Stage 4 Loop de', 250, 338);
    context.fillText('Loop', 250, 358);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    const files = new DataTransfer();
    files.items.add(new File([blob], 'synthetic-seam.png', {type: 'image/png'}));
    document.querySelector('input[name=image]').files = files.files;
  });
  await page.locator('input[name=timezone]').fill('UTC');
  await page.getByRole('button', {name: 'Extract screenshot'}).click();
  const cards = page.locator('.race-review-row');
  check(await cards.count() === 3, 'all source observations retained');
  check((await cards.nth(2).innerText()).includes('Possible section-boundary fragment'), 'fragment warning shown');
  check((await cards.nth(2).innerText()).includes('"event": "Loop"'), 'original fragment available');
  check(await page.getByRole('button', {name: 'Confirm Batch'}).isDisabled(), 'unresolved batch blocked');
  await page.locator('input[name=visible_count]').fill('2');
  await page.locator('input[name=visible_confirmed]').check();
  await page.locator('select[name="0.group"]').selectOption('different');
  await page.locator('select[name="1.group"]').selectOption('different');
  await page.getByRole('button', {name: 'Review changes'}).click();
  check(await page.getByRole('button', {name: 'Confirm Batch'}).isDisabled(), 'unresolved fragment still blocks');
  await page.locator('select[name="2.group"]').selectOption('1');
  await page.locator('.race-review-row').nth(2).getByText('Compare overlapping observations and both crop contexts').click();
  check(await page.locator('.race-crop-comparison img').count() >= 2, 'both source crops available');
  await page.getByRole('button', {name: 'Review changes'}).click();
  check((await cards.nth(1).innerText()).includes('"date": null'), 'unreadable complete row retained');
  check(await page.getByRole('button', {name: 'Confirm Batch'}).isDisabled(), 'missing date blocks whole batch');
  await page.locator('input[name="1.date"]').fill('2024-11-08');
  await page.getByRole('button', {name: 'Review changes'}).click();
  await page.locator('input[name="0.corrected"]').check();
  check(await page.getByRole('button', {name: 'Confirm Batch'}).isEnabled(), 'explicit correction allows matched batch');
  await page.setViewportSize({width: 390, height: 900});
  check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'no mobile overflow');
  await page.getByRole('button', {name: 'Confirm Batch'}).click();
  check((await page.locator('main').innerText()).includes('Added 2'), 'only the two reconciled races saved');
  return `${checks} synthetic seam browser checks passed; no OpenAI request was made.`;
}
