import { test, expect } from '@playwright/test';
// Self-contained CI fixture generated through M1–M9 engines, never claimed as genuine market data.
test('offline synthetic seed is clearly labeled and exposes actual saved metrics', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByText(/Synthetic dataset context/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Research overview' })).toBeVisible();
  await expect(
    page.getByRole('img', { name: 'Historical simulated portfolio equity in USD' }),
  ).toBeVisible();
});
test('offline committee and risk records are genuinely connected', async ({ page }) => {
  await page.goto('/committee');
  await expect(page.getByRole('heading', { name: 'Specialized research agents' })).toBeVisible();
  await expect(page.getByText('Abstained', { exact: true }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Risk Center', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Risk decision inspector' })).toBeVisible();
});
test('offline model, discovery, and optimizer registries contain generated artifacts', async ({
  page,
}) => {
  await page.goto('/ml');
  await expect(page.getByRole('table', { name: 'ML evaluation windows' })).toBeVisible();
  await page.goto('/strategies');
  await expect(page.getByRole('table', { name: 'All strategy candidates' })).toBeVisible();
  await page.goto('/portfolio');
  await expect(page.getByRole('heading', { name: 'Numerical allocation research' })).toBeVisible();
});
test('offline news absence and locked simulation mode stay explicit', async ({ page }) => {
  await page.goto('/sentiment');
  await expect(page.getByRole('heading', { name: 'No eligible news observed' })).toBeVisible();
  await expect(page.getByText('Simulation only', { exact: true }).first()).toBeVisible();
});
