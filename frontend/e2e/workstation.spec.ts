import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const evidence = resolve('test-results/screenshots');
async function committee(request: APIRequestContext, label: string) {
  const list = await (await request.get('/api/backend/api/research/catalog?kind=committee')).json();
  const row = list.items.find((r: { label: string }) => r.label.includes(label));
  expect(row).toBeTruthy();
  return await (await request.get('/api/backend' + row.links.detail)).json();
}
async function loaded(page: Page, title: string) {
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  await expect(page.getByText('Backend connected', { exact: true })).toBeVisible();
}
test.beforeAll(async () => {
  await mkdir(evidence, { recursive: true });
});
test('genuine overview equals backend and renders actual chart', async ({ page, request }) => {
  const r = await committee(request, 'm8_baseline');
  await page.goto('/?run=' + r.id);
  await loaded(page, 'Research overview');
  await expect(
    page
      .getByText(
        new Intl.NumberFormat('en-US', {
          style: 'percent',
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(r.result.metrics.total_return),
        { exact: true },
      )
      .first(),
  ).toBeVisible();
  await expect(
    page.getByRole('img', { name: 'Historical simulated portfolio equity in USD' }),
  ).toBeVisible();
  await page.screenshot({ path: resolve(evidence, 'overview-desktop.png'), fullPage: true });
});
test('security and date controls fetch observations and exclude future information', async ({
  page,
}) => {
  await page.goto('/research');
  await loaded(page, 'IBM / security research');
  await page.getByLabel('Historical start date').fill('2026-09-09');
  await page.getByLabel('Historical end date').fill('2026-10-12');
  const response = page.waitForResponse(
    (r) => r.url().includes('/api/market/IBM') && r.url().includes('start=2026-09-09'),
  );
  await page.getByRole('button', { name: 'Apply context', exact: true }).click();
  expect((await response).ok()).toBe(true);
  await expect(page.getByRole('table', { name: 'Historical market observations' })).toBeVisible();
  await page.getByLabel('Research availability cutoff').fill('2020-01-01T00:00:00Z');
  await page.getByRole('button', { name: 'Apply availability cutoff' }).click();
  await expect(page.getByText('No eligible series to chart').first()).toBeVisible();
});
test('committee evidence and actual abstentions are inspectable', async ({ page, request }) => {
  const r = await committee(request, 'm8_baseline');
  await page.goto('/committee?run=' + r.id);
  await loaded(page, 'Investment committee');
  await expect(page.getByRole('heading', { name: /fundamental/i })).toBeVisible();
  await expect(page.getByText('Abstained', { exact: true }).first()).toBeVisible();
  await page.getByText('Evidence, clocks & dependencies', { exact: true }).first().click();
  await expect(page.locator('pre').filter({ hasText: 'market_prices:IBM' }).first()).toBeVisible();
  await page.screenshot({ path: resolve(evidence, 'committee-desktop.png'), fullPage: true });
});
test('risk veto, no approved allocation, insufficient-tail warning and no override', async ({
  page,
  request,
}) => {
  const r = await committee(request, 'combined');
  await page.goto('/risk?committee=' + r.id);
  await loaded(page, 'Risk center');
  await expect(page.getByText('REJECTED', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Risk-approved state', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No approved risk snapshot' })).toBeVisible();
  await expect(page.getByRole('button', { name: /override|execute rejected/i })).toHaveCount(0);
  await page.getByRole('button', { name: 'Actual current state' }).click();
  await expect(page.getByText('Insufficient tail history', { exact: true })).toBeVisible();
  await page.screenshot({ path: resolve(evidence, 'risk-desktop.png'), fullPage: true });
});
test('portfolio history slider uses actual ledger quantities', async ({ page, request }) => {
  const r = await committee(request, 'concentration');
  await page.goto('/portfolio?run=' + r.id);
  await loaded(page, 'Portfolio workstation');
  await expect(page.getByRole('table', { name: 'Actual ledger holdings' })).toBeVisible();
  await page.getByRole('slider', { name: 'Historical holdings snapshot' }).press('Home');
  await expect(
    page.getByRole('heading', { name: 'No records in this selection' }).first(),
  ).toBeVisible();
});
test('backtest benchmark comparison and real orders work', async ({ page, request }) => {
  const r = await committee(request, 'm8_baseline');
  await page.goto('/backtesting?run=' + r.backtest_id);
  await loaded(page, 'Backtesting analytics');
  await expect(page.getByRole('table', { name: 'Simulation trade records' })).toBeVisible();
  await expect(page.getByLabel('Benchmark experiment')).not.toHaveValue('');
  await expect(
    page.getByRole('img', { name: 'Portfolio and selected matched benchmark equity' }),
  ).toBeVisible();
  await page.getByLabel('Trade record type').selectOption('orders');
  await expect(page.getByRole('columnheader', { name: 'Order status' })).toBeVisible();
});
test('stored strategy rules and ML evaluation windows render', async ({ page }) => {
  await page.goto('/strategies');
  await loaded(page, 'Strategy lab');
  await expect(page.getByRole('table', { name: 'All strategy candidates' })).toBeVisible();
  await page.getByRole('button', { name: 'Inspect record 1' }).first().click();
  await page.getByText('Safe machine-readable definition and parameters', { exact: true }).click();
  await expect(page.locator('pre').filter({ hasText: '"entry"' }).first()).toBeVisible();
  await page.goto('/ml');
  await loaded(page, 'ML research');
  await expect(page.getByRole('table', { name: 'ML evaluation windows' })).toBeVisible();
  await expect(page.getByText('train_start', { exact: true })).toBeVisible();
});
test('missing sentiment and saved experiment switching are honest', async ({ page }) => {
  await page.goto('/sentiment');
  await loaded(page, 'Sentiment intelligence');
  await expect(page.getByRole('heading', { name: 'No eligible news observed' })).toBeVisible();
  await page.getByRole('link', { name: 'Experiment History', exact: true }).click();
  await loaded(page, 'Experiment history');
  await page.getByRole('button', { name: 'Backtests', exact: true }).click();
  await expect(page.getByRole('table', { name: 'Backtests registry' })).toBeVisible();
  await page.getByRole('button', { name: 'Inspect record 1' }).first().click();
  await expect(page.getByRole('heading', { name: 'Saved experiment inspector' })).toBeVisible();
});
test('hypothetical stress reaches FastAPI and returns calculated losses', async ({ page }) => {
  await page.goto('/risk');
  await loaded(page, 'Risk center');
  await page.getByText('Configure a linear equity shock', { exact: true }).click();
  await page.getByLabel('Assumed raw USD price', { exact: true }).fill('100');
  await page.getByLabel('Assumed shares', { exact: true }).fill('10');
  await page.getByLabel('Assumed cash USD', { exact: true }).fill('1000');
  await page.getByRole('button', { name: 'Review hypothetical scenario' }).click();
  await page.getByRole('button', { name: 'Calculate reviewed shock' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Run simulation research', exact: true }).click();
  await expect(page.getByText(/Scenario loss \$100.00/)).toBeVisible();
});
test('API errors and malformed responses do not fabricate values', async ({ page }) => {
  await page.route('**/api/backend/api/investment-committee/*', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":{"message":"Backend intentionally unavailable"}}',
    }),
  );
  await page.goto('/');
  await expect(page.getByText('Backend intentionally unavailable', { exact: true })).toBeVisible();
  await page.unrouteAll();
  await page.route('**/api/backend/api/research/catalog*', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"items":"invalid"}' }),
  );
  await page.goto('/experiments');
  await expect(page.getByText(/unexpected data contract/).first()).toBeVisible();
});
for (const width of [1440, 1280, 820, 390])
  test(`responsive layout and keyboard ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.goto('/');
    await loaded(page, 'Research overview');
    if (width < 760) {
      await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
      await expect(page.getByRole('navigation', { name: 'Research navigation' })).toBeVisible();
      await page.getByRole('link', { name: 'Risk Center', exact: true }).click();
      await loaded(page, 'Risk center');
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.keyboard.press('Tab');
    expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY');
    await page.screenshot({ path: resolve(evidence, `responsive-${width}.png`) });
  });
test('accessibility scan and runtime console on actual overview', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await loaded(page, 'Research overview');
  await expect(
    page.getByRole('img', { name: 'Historical simulated portfolio equity in USD' }),
  ).toBeVisible();
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze();
  await writeFile(resolve(evidence, '../accessibility.json'), JSON.stringify(results, null, 2));
  expect(results.violations).toEqual([]);
  expect(errors).toEqual([]);
});
