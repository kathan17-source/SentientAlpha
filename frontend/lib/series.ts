import { finite, record, text, type RecordData } from './format';
export function alignedEquity(portfolio: RecordData[], benchmark: RecordData[]) {
  const benchmarkMap = new Map(
    benchmark.map((r) => [text(r.day, text(r.at).slice(0, 10)), finite(r.equity)]),
  );
  return portfolio.map((r) => {
    const day = text(r.day, text(r.at).slice(0, 10));
    return {
      day,
      portfolio: finite(r.equity),
      benchmark: benchmarkMap.get(day) ?? null,
      cash: finite(r.cash),
      exposure: finite(r.gross_exposure),
    };
  });
}
export function ledgerAnalytics(rows: RecordData[]) {
  let peak: number | null = null;
  const returns: number[] = [];
  let previous: number | null = null;
  return rows.map((r) => {
    const eq = finite(r.equity);
    const day = text(r.day, text(r.at).slice(0, 10));
    if (eq !== null) peak = Math.max(peak ?? eq, eq);
    const ret = eq !== null && previous !== null && previous > 0 ? eq / previous - 1 : null;
    if (ret !== null) returns.push(ret);
    if (eq !== null) previous = eq;
    const window = returns.slice(-20);
    const mean = window.reduce((a, b) => a + b, 0) / window.length;
    const sd =
      window.length >= 20
        ? Math.sqrt(window.reduce((s, n) => s + (n - mean) ** 2, 0) / (window.length - 1))
        : null;
    return {
      day,
      drawdown: eq !== null && peak ? eq / peak - 1 : null,
      volatility: sd === null ? null : sd * Math.sqrt(252),
      sharpe: sd && sd > 0 ? (mean / sd) * Math.sqrt(252) : null,
      return: ret,
      exposure: finite(r.gross_exposure),
    };
  });
}
export function monthlyReturns(rows: RecordData[]) {
  const months = new Map<string, number>();
  for (const r of ledgerAnalytics(rows)) {
    if (r.return !== null)
      months.set(r.day.slice(0, 7), (months.get(r.day.slice(0, 7)) ?? 1) * (1 + r.return));
  }
  return Array.from(months, ([month, growth]) => ({ month, return: growth - 1 }));
}
export function positions(rows: RecordData[], index = rows.length - 1): RecordData[] {
  const equity = finite(rows[index]?.equity);
  return Object.entries(record(rows[index]?.positions)).map(([ticker, p]) => {
    const item = record(p),
      q = finite(item.quantity),
      basis = finite(item.cost_basis),
      weight = finite(item.weight);
    const marketValue =
      finite(item.market_value) ?? (equity !== null && weight !== null ? equity * weight : null);
    return {
      ticker,
      ...item,
      market_value: marketValue,
      average_cost: q && basis !== null ? basis / q : null,
      unrealized_pnl: marketValue !== null && basis !== null ? marketValue - basis : null,
    };
  });
}
export function entries(value: unknown): RecordData[] {
  return Object.entries(record(value)).map(([asset, value]) => ({ asset, value }));
}
