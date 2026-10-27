import { it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  Badge,
  PageHeader,
  Metric,
  Failure,
  Empty,
  Loading,
  ConfirmDialog,
  RunSelect,
} from '@/components/shared/ui';
import { DataTable } from '@/components/shared/table';
it('renders unavailable metric honestly and navigates from an actual metric card', () => {
  render(
    <Metric label="VaR" value="Unavailable" href="/risk" detail="Insufficient tail history" />,
  );
  expect(screen.getByRole('link')).toHaveAttribute('href', '/risk');
  expect(screen.getByText('Unavailable')).toBeVisible();
});
it('labels rejected orders as rejected without an override', () => {
  render(<Badge tone="bad">REJECTED</Badge>);
  expect(screen.getByText('REJECTED')).toBeVisible();
  expect(screen.queryByRole('button')).toBeNull();
});
it('separates missing news from a neutral score', () => {
  render(
    <Empty title="No eligible news observed">Missing coverage is not neutral sentiment.</Empty>,
  );
  expect(screen.getByText('Missing coverage is not neutral sentiment.')).toBeVisible();
  expect(screen.queryByText('0.00%')).toBeNull();
});
it('announces loading and offers a working retry', async () => {
  const retry = vi.fn();
  render(
    <>
      <Loading />
      <Failure error={new Error('Backend unavailable')} retry={retry} />
    </>,
  );
  expect(screen.getByRole('status')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Retry request' }));
  expect(retry).toHaveBeenCalledOnce();
});
it('filters, sorts and paginates real table records', async () => {
  render(
    <DataTable
      rows={Array.from({ length: 21 }, (_, i) => ({ ticker: `ASSET${i}`, weight: i / 100 }))}
      columns={[
        { key: 'ticker', label: 'Security' },
        { key: 'weight', label: 'Actual weight' },
      ]}
      pageSize={10}
    />,
  );
  await userEvent.click(screen.getByRole('button', { name: 'Next table page' }));
  expect(screen.getByText('Page 2 of 3')).toBeVisible();
  await userEvent.type(screen.getByRole('textbox', { name: 'Filter Research records' }), 'ASSET20');
  expect(screen.getByText('ASSET20')).toBeVisible();
  expect(screen.getByText('Page 1 of 1')).toBeVisible();
});
it('selects a saved run without silently creating a replacement', async () => {
  const fn = vi.fn();
  render(
    <RunSelect
      value=""
      onChange={fn}
      items={[
        {
          id: 'abc',
          kind: 'committee',
          status: 'completed',
          created_at: '2026-10-20T00:00:00Z',
          label: 'Stored run',
          configuration: {},
          links: { detail: '/api/x' },
        },
      ]}
    />,
  );
  await userEvent.selectOptions(screen.getByRole('combobox'), 'abc');
  expect(fn).toHaveBeenCalledWith('abc');
});
it('requires explicit review confirmation and supports keyboard cancel', async () => {
  const confirm = vi.fn();
  render(
    <ConfirmDialog title="Run bounded research" description="Simulation only" onConfirm={confirm}>
      Review research
    </ConfirmDialog>,
  );
  await userEvent.click(screen.getByRole('button', { name: 'Review research' }));
  expect(screen.getByRole('dialog')).toBeVisible();
  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(confirm).not.toHaveBeenCalled();
});
it('renders untrusted news as text, never active markup', () => {
  render(<Empty title={'<img src=x onerror=alert(1)>'}>Unknown provider</Empty>);
  expect(screen.getByRole('heading')).toHaveTextContent('<img');
  expect(document.querySelector('img')).toBeNull();
});

it('keeps a single primary heading when a research subsection uses PageHeader', () => {
  render(
    <>
      <PageHeader title="Portfolio workstation" description="Actual simulated ledger" />
      <PageHeader
        title="Numerical allocation research"
        description="Estimated targets, not holdings"
        headingLevel={2}
      />
    </>,
  );
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
    'Numerical allocation research',
  );
});
