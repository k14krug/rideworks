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
    context.fillText('Stage 4 Loop de', 250, 404);
    context.fillText('Loop', 250, 428);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    const files = new DataTransfer();
    files.items.add(new File([blob], 'synthetic-seam.png', {type: 'image/png'}));
    document.querySelector('input[name=image]').files = files.files;
  });
  await page.locator('select[name=mode]').selectOption('sectioned');
  await page.locator('input[name=timezone]').fill('UTC');
  await page.getByRole('button', {name: 'Extract screenshot'}).click();
  const cards = page.locator('.race-candidate-row');
  check(await cards.count() === 3, 'all source observations retained');
  check((await page.locator('.race-overlap').innerText()).includes('Loop'), 'fragment appears in a possible-duplicate question');
  check(await page.locator('button[value=confirm]').isDisabled(), 'unresolved batch blocked');
  await page.locator('input[name="overlap.0.2"][value=same]').check();
  await page.getByText('Compare screenshot crops').click();
  check(await page.locator('.race-crop-comparison img').count() >= 2, 'both source crops available');
  await page.getByRole('button', {name: 'Review changes'}).click();
  check((await cards.nth(1).innerText()).includes('Unknown'), 'unreadable complete row retained');
  check(await page.locator('button[value=confirm]').isDisabled(), 'missing date blocks whole batch');
  await cards.nth(1).getByText('Edit', {exact: true}).click();
  await page.locator('input[name="1.date"]').fill('2024-11-08');
  await page.getByRole('button', {name: 'Review changes'}).click();
  check((await page.locator('.race-conflict').innerText()).includes('Event:'), 'fragment title disagreement is visible');
  await page.locator('input[name="verify.0.2"]').check();
  await page.locator('input[name=list_acknowledged]').check();
  check(await page.locator('button[value=confirm]').isEnabled(), 'explicit acknowledgment allows matched batch');
  await page.setViewportSize({width: 390, height: 900});
  check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'no mobile overflow');
  await page.locator('button[value=confirm]').click();
  check((await page.locator('main').innerText()).includes('Added 2'), 'only the two reconciled races saved');
  return `${checks} synthetic seam browser checks passed; no OpenAI request was made.`;
}
