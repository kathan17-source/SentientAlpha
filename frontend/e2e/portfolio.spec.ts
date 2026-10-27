import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import packageInfo from '../package.json' with { type: 'json' };

// Real rendered views of release_demo.py. No mocked responses or injected page content.
test('capture four synthetic portfolio views', async ({ page, request }, info) => {
  const coverage = await (await request.get('/api/backend/api/research/coverage?limit=200')).json();
  expect(coverage.items.length).toBeGreaterThan(0);
  expect(coverage.items.every((r: { provider: string }) => r.provider === 'synthetic')).toBe(true);
  const sessions = await (await request.get('/api/backend/api/paper/sessions')).json();
  const normal = sessions.items.find((r: { status: string }) => r.status === 'RUNNING');
  expect(normal).toBeTruthy();
  const fills = await (
    await request.get(`/api/backend/api/paper/sessions/${normal.id}/fills`)
  ).json();
  expect(fills.items.length).toBeGreaterThan(0);
  const output = process.env.PORTFOLIO_SCREENSHOTS || info.outputPath('portfolio');
  await mkdir(output, { recursive: true });
  await page.setViewportSize({ width: 1600, height: 1100 });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  for (const [name, route] of [
    ['overview', '/'],
    ['committee', '/committee'],
    ['risk', '/risk'],
    ['paper', '/paper'],
  ]) {
    await page.goto(route);
    if (name === 'paper')
      await page.getByRole('combobox', { name: 'Saved paper session' }).selectOption(normal.id);
    await expect(page.locator('h1')).toHaveCount(1);
    await expect(page.getByText('Backend connected', { exact: true })).toBeVisible();
    await expect(page.getByText('Simulation only', { exact: true }).first()).toBeVisible();
    await expect(
      page.getByText(`Single-user · v${packageInfo.version}`, { exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/Synthetic dataset context/)).toBeVisible();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.loading')).toHaveCount(0);
    await page.evaluate(() => document.fonts.ready);
    if (name === 'committee') {
      await expect(page.locator('.agent-card')).toHaveCount(12);
      const technical = page
        .locator('.agent-card')
        .filter({ has: page.getByRole('heading', { name: /technical/ }) })
        .first();
      await expect(technical.locator('p')).toContainText('Existing feature=0.0096395;');
      await expect(technical.locator('p')).not.toContainText('0.009639496694523464');
    }
    await page.screenshot({ path: join(output, `${name}.png`), animations: 'disabled' });
  }
  expect(errors).toEqual([]);
});
