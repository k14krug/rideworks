/* Playwright check against preview_race_results.py --identity-case. */
async page => {
  const base = new URL(page.url()).origin;
  let checks = 0;
  const check = (condition, message) => { checks++; if (!condition) throw Error(message); };
  await page.setViewportSize({width: 390, height: 900});
  await page.goto(base + '/race-results/import');
  await page.evaluate(async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 768; canvas.height = 939;
    const context = canvas.getContext('2d');
    context.fillStyle = 'white'; context.fillRect(0, 0, canvas.width, canvas.height);
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    const files = new DataTransfer();
    files.items.add(new File([blob], 'synthetic.png', {type: 'image/png'}));
    document.querySelector('input[name=image]').files = files.files;
  });
  await page.locator('input[name=timezone]').fill('UTC');
  await page.getByRole('button', {name: 'Extract screenshot'}).click();
  const reviewUrl = page.url();
  const reconcile = async () => {
    await page.locator('input[name="overlap.1.2"][value=same]').check();
    await page.getByRole('button', {name: 'Review changes'}).click();
  };
  await reconcile();
  check(await page.locator('.race-identity-card').count() === 1, 'possible prior association shown');
  check(await page.locator('button[value=confirm]').isDisabled(), 'unresolved identity blocks batch');
  await page.getByText('Compare original screenshots').click();
  check(await page.locator('.race-identity-card img').count() === 2, 'both screenshots available');
  check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), 'no mobile overflow');
  const choice = page.locator('.race-identity-card select');
  await choice.selectOption({label: 'Different races — retain both'});
  await page.locator('input[name="0.replace"]').check();
  await page.getByRole('button', {name: 'Review changes'}).click();
  await page.locator('input[name=list_acknowledged]').check();
  check(await page.locator('button[value=confirm]').isDisabled(), 'a retained prior result cannot be replaced by another batch row');
  check((await page.locator('main').innerText()).includes('would be replaced'), 'retained-result conflict is explained');
  await page.locator('.race-identity-card select').selectOption({label: 'Same race — correct old attachment'});
  await page.getByRole('button', {name: 'Review changes'}).click();
  check(await page.locator('button[value=confirm]').isDisabled(), 'same race blocks batch');
  const removalUrl = await page.locator('.race-identity-card a').getAttribute('href');
  await page.goto(base + removalUrl);
  check((await page.locator('main').innerText()).includes('source screenshot and result history will be retained'), 'separate removal confirmation');
  await page.getByRole('button', {name: 'Remove race result'}).click();
  await page.goto(reviewUrl);
  await reconcile();
  check(await page.locator('.race-identity-card').count() === 0, 'removed prior link no longer blocks');
  await page.locator('input[name="0.replace"]').check();
  await page.locator('input[name=list_acknowledged]').check();
  await page.locator('button[value=confirm]').click();
  check((await page.locator('main').innerText()).includes('Added 2'), 'freshly revalidated full batch saved');
  return `${checks} synthetic identity browser checks passed; no OpenAI request was made.`;
}
