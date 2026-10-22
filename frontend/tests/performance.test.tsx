import { afterAll, it, expect } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { DataTable } from '@/components/shared/table';
import { ledgerAnalytics } from '@/lib/series';
const samples: Record<string, number>[] = [];
for (const count of [20, 50, 500])
  it(`bounds rendered DOM for ${count} synthetic reference records`, () => {
    cleanup();
    const rows = Array.from({ length: count }, (_, i) => ({
      ticker: `FIXTURE${i}`,
      weight: i / count,
    }));
    const start = performance.now();
    render(
      <DataTable
        label={`Synthetic ${count} rows`}
        rows={rows}
        columns={[
          { key: 'ticker', label: 'Security' },
          { key: 'weight', label: 'Actual fixture weight' },
        ]}
      />,
    );
    samples.push({ records: count, jsdom_render_ms: performance.now() - start });
    expect(screen.getAllByRole('row').length).toBeLessThanOrEqual(11);
  });
it('processes a 2000-observation synthetic ledger without filling unknown data', () => {
  const rows = Array.from({ length: 2000 }, (_, i) => ({
    day: String(i),
    equity: 100000 * Math.exp(0.0001 * i + Math.sin(i) * 0.001),
  }));
  const start = performance.now();
  const series = ledgerAnalytics(rows);
  samples.push({ observations: 2000, transformation_ms: performance.now() - start });
  expect(series).toHaveLength(2000);
  expect(series[0].sharpe).toBeNull();
  expect(series[1999].volatility).not.toBeNull();
});
afterAll(() => {
  const p = resolve('test-results/performance');
  mkdirSync(p, { recursive: true });
  writeFileSync(
    resolve(p, 'component-benchmarks.json'),
    JSON.stringify(
      {
        scope:
          'Synthetic jsdom component rendering and Node transformations; not browser frame timing',
        samples,
      },
      null,
      2,
    ),
  );
});
