import { test, expect } from '@playwright/test';
test('paper seed displays actual persisted ledger and unmistakable mode', async ({
  page,
  request,
}) => {
  const list = await (await request.get('/api/backend/api/paper/sessions')).json();
  const selected = list.items.find((r: { mode: string }) => r.mode === 'synthetic_demo');
  expect(selected).toBeTruthy();
  await page.goto('/paper');
  await expect(page.getByRole('heading', { name: 'Paper trading', exact: true })).toBeVisible();
  await expect(page.getByText(/PAPER TRADING — SIMULATED EXECUTION — NO REAL MONEY/)).toBeVisible();
  await expect(page.getByRole('table', { name: 'Paper ledger holdings' })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Paper agent participation' })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Paper session equity in USD' })).toBeVisible();
});
test('actual pending review cannot mutate lifecycle until confirmed', async ({ page, request }) => {
  await page.goto('/paper');
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  const before = await (await request.get('/api/backend/api/paper/sessions')).json();
  await page.getByRole('button', { name: 'Confirm reviewed paper command' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  const after = await (await request.get('/api/backend/api/paper/sessions')).json();
  expect(after.items[0].status).toBe(before.items[0].status);
});
test('reconciles real frozen paper event history through the API', async ({ request }) => {
  const list = await (await request.get('/api/backend/api/paper/sessions')).json();
  const id = list.items[0].id;
  const response = await request.post(`/api/backend/api/paper/sessions/${id}/reconcile`, {
    headers: { Origin: process.env.DASHBOARD_URL || 'http://127.0.0.1:3000' },
    data: { key: 'browser-reconcile-command' },
  });
  expect(response.ok()).toBe(true);
  expect((await response.json()).data.equivalent).toBe(true);
});

test('confirmed pause persists without changing actual holdings or fills', async ({
  page,
  request,
}) => {
  const sessions = await (await request.get('/api/backend/api/paper/sessions')).json();
  const normal = sessions.items.find(
    (row: { mode: string; status: string }) =>
      row.mode === 'synthetic_demo' && row.status === 'RUNNING',
  );
  expect(normal).toBeTruthy();
  const path = `/api/backend/api/paper/sessions/${normal.id}`;
  const before = await (await request.get(path)).json();
  const fills = await (await request.get(`${path}/fills`)).json();
  expect(fills.items.length).toBeGreaterThan(0);
  await page.goto('/paper');
  await page.getByRole('combobox', { name: 'Saved paper session' }).selectOption(normal.id);
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm reviewed paper command' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Run simulation research' }).click();
  await expect.poll(async () => (await (await request.get(path)).json()).status).toBe('PAUSED');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Resume', exact: true })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Paper ledger holdings' })).toBeVisible();
  const after = await (await request.get(path)).json();
  expect(after.portfolio).toEqual(before.portfolio);
  expect((await (await request.get(`${path}/fills`)).json()).items).toEqual(fills.items);
});
