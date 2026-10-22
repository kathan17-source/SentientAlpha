import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Run against scripts/release_demo.py's combined, explicitly synthetic database.
const routes = [
  '/',
  '/portfolio',
  '/committee',
  '/strategies',
  '/backtesting',
  '/sentiment',
  '/risk',
  '/ml',
  '/research',
  '/experiments',
  '/paper',
];
for (const width of [1440, 1280, 820, 390]) {
  for (const route of routes) {
    test(`release ${route} at ${width}px: render, keyboard, overflow, axe`, async ({
      page,
    }, info) => {
      const errors: string[] = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
      await page.goto(route);
      await expect(page.locator('h1')).toBeVisible();
      await expect(page.getByText('Backend connected', { exact: true })).toBeVisible();
      await expect(page.getByText('Simulation only', { exact: true }).first()).toBeVisible();
      await page.keyboard.press('Tab');
      expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe('BODY');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      );
      const accessibility = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze();
      await info.attach('axe.json', {
        body: JSON.stringify(accessibility),
        contentType: 'application/json',
      });
      await page.screenshot({ path: info.outputPath('rendered.png'), fullPage: true });
      expect(accessibility.violations).toEqual([]);
      expect(errors).toEqual([]);
    });
  }
}

test('release paper view presents actual cash and the persisted veto warning', async ({
  page,
  request,
}) => {
  const response = await request.get('/api/backend/api/paper/sessions');
  expect(response.ok()).toBe(true);
  const sessions = (await response.json()).items;
  const normal = sessions.find((s: { status: string }) => s.status === 'RUNNING');
  const veto = sessions.find(
    (s: { status: string; warning: string | null }) => s.status === 'PAUSED' && s.warning,
  );
  expect(normal).toBeTruthy();
  expect(veto).toBeTruthy();
  await page.goto('/paper');
  await page.getByRole('combobox', { name: 'Saved paper session' }).selectOption(normal.id);
  const cash = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(Number(normal.portfolio.cash));
  await expect(page.getByText(cash, { exact: true }).first()).toBeVisible();
  await page.getByRole('combobox', { name: 'Saved paper session' }).selectOption(veto.id);
  await expect(page.getByText(veto.warning, { exact: true })).toBeVisible();
  const fills = await (
    await request.get(`/api/backend/api/paper/sessions/${veto.id}/fills`)
  ).json();
  expect(fills.items).toEqual([]);
});
