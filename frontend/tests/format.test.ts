import { describe, it, expect } from 'vitest';
import { finite, money, percent, decimal, bps, timestamp } from '@/lib/format';
import { alignedEquity, ledgerAnalytics, monthlyReturns, positions } from '@/lib/series';
describe('financial formatting and missing values', () => {
  it.each([null, undefined, NaN, Infinity, -Infinity, '', 'not-a-number', true, {}])(
    'does not fabricate a finite value for %s',
    (v) => expect(finite(v)).toBeNull(),
  );
  it('preserves backend fraction units, signed losses and bps', () => {
    expect(percent(0.05)).toBe('5.00%');
    expect(percent(-0.03)).toBe('-3.00%');
    expect(bps(0.0005)).toBe('5 bps');
  });
  it('formats exact USD strings for display without changing stored values', () => {
    expect(money('100000.25')).toBe('$100,000.25');
    expect(decimal('1.25', 4)).toBe('1.25');
  });
  it('never turns undefined ratios into zero', () => {
    expect(percent(null)).toBe('Unavailable');
    expect(money(Infinity)).toBe('Unavailable');
    expect(decimal(undefined)).toBe('Unavailable');
  });
  it('normalizes aware timestamps and rejects invalid dates', () => {
    expect(timestamp('2026-10-20T10:00:00-05:00')).toContain('15:00:00');
    expect(timestamp('bad date')).toBe('Unavailable');
  });
});
describe('documented ledger transformations', () => {
  it('aligns benchmarks on actual session dates and never fills gaps', () => {
    const d = alignedEquity(
      [
        { day: '2026-01-01', equity: '100' },
        { day: '2026-01-02', equity: '90' },
      ],
      [{ day: '2026-01-02', equity: '110' }],
    );
    expect(d[0].benchmark).toBeNull();
    expect(d[1].benchmark).toBe(110);
  });
  it('computes realized drawdown from past peaks only', () => {
    const r = ledgerAnalytics([
      { day: 'a', equity: 100 },
      { day: 'b', equity: 80 },
      { day: 'c', equity: 120 },
    ]);
    expect(r[1].drawdown).toBeCloseTo(-0.2);
    expect(r[2].drawdown).toBe(0);
  });
  it('keeps rolling metrics undefined until 20 returns exist', () => {
    expect(ledgerAnalytics([{ equity: 100 }, { equity: 110 }])[1].sharpe).toBeNull();
    expect(
      ledgerAnalytics(Array.from({ length: 21 }, (_, i) => ({ equity: 100 + i }))).at(-1)
        ?.volatility,
    ).not.toBeNull();
  });
  it('does not return an infinite Sharpe for constant return history', () => {
    expect(
      ledgerAnalytics(Array.from({ length: 21 }, () => ({ equity: 100 }))).at(-1)?.sharpe,
    ).toBeNull();
  });
  it('compounds monthly ledger returns across the month boundary', () => {
    const r = monthlyReturns([
      { day: '2026-01-01', equity: 100 },
      { day: '2026-01-02', equity: 110 },
      { day: '2026-02-02', equity: 99 },
    ]);
    expect(r[0].return).toBeCloseTo(0.1);
    expect(r[1].return).toBeCloseTo(-0.1);
  });
  it('derives actual value and cost per share from actual ledger identities', () => {
    const r = positions([
      { equity: 1000, positions: { AAA: { quantity: '5', cost_basis: '250', weight: 0.3 } } },
    ]);
    expect(r[0]).toMatchObject({ market_value: 300, average_cost: 50, unrealized_pnl: 50 });
  });
  it('does not substitute target weights for actual holdings', () => {
    expect(positions([{ equity: 1000, positions: {} }])).toEqual([]);
  });
});
