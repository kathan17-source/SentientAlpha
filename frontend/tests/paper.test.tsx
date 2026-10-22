import { it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { modeLabel, paperActions } from '@/lib/paper';
import Paper from '@/components/views/paper';
vi.mock('@/components/shared/charts', () => ({
  SeriesChart: () => <div>Accessible chart data</div>,
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it.each(['historical_replay', 'synthetic_demo', 'forward_paper'])(
  'never calls %s live brokerage performance',
  (mode) => {
    expect(modeLabel(mode)).not.toMatch(/live|brokerage/i);
  },
);
it('offers only supported lifecycle operations', () => {
  expect(paperActions('CREATED', 'forward_paper')).toEqual(['ready', 'stop']);
  expect(paperActions('PAUSED', 'forward_paper')).toEqual(['resume', 'stop']);
  expect(paperActions('STOPPED', 'forward_paper')).toEqual([]);
  expect(paperActions('FAILED', 'forward_paper')).toEqual(['stop']);
  expect(paperActions('RUNNING', 'historical_replay')).toEqual(['stop']);
});
function mount(fetcher: ReturnType<typeof vi.fn>) {
  vi.stubGlobal('fetch', fetcher);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Paper />
    </QueryClientProvider>,
  );
}
it('empty API state does not invent positions or equity', async () => {
  mount(vi.fn().mockResolvedValue(Response.json({ items: [], next_offset: null })));
  expect(await screen.findByText('No paper sessions saved')).toBeInTheDocument();
  expect(
    screen.getByText(/PAPER TRADING — SIMULATED EXECUTION — NO REAL MONEY/),
  ).toBeInTheDocument();
  expect(screen.queryByText('Simulated equity')).not.toBeInTheDocument();
});
it('reviewing a new session cannot submit it before confirmation', async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json({ items: [], next_offset: null }));
  mount(fetcher);
  const user = userEvent.setup();
  await user.click(screen.getByText('Configure a new session'));
  await user.click(screen.getByRole('button', { name: 'Review new session' }));
  expect(screen.getByText('Review local simulation command')).toBeInTheDocument();
  expect(
    fetcher.mock.calls.every(([, options]) => !options?.method || options.method === 'GET'),
  ).toBe(true);
  await user.click(screen.getByRole('button', { name: 'Confirm reviewed paper command' }));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  await user.keyboard('{Escape}');
  expect(
    fetcher.mock.calls.every(([, options]) => !options?.method || options.method === 'GET'),
  ).toBe(true);
});
