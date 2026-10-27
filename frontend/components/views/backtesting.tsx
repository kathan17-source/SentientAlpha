'use client';
import { Fragment, useState } from 'react';
import Link from 'next/link';
import { useObject, usePage, useSelection } from '@/lib/hooks';
import { record, text, finite, money, percent, decimal, timestamp } from '@/lib/format';
import { alignedEquity, ledgerAnalytics, monthlyReturns, positions } from '@/lib/series';
import {
  Badge,
  Empty,
  Failure,
  JsonDetails,
  Loading,
  Metric,
  Note,
  PageHeader,
  Panel,
  Provenance,
  RunSelect,
} from '../shared/ui';
import { SeriesChart } from '../shared/charts';
import { DataTable } from '../shared/table';
import { ResearchForm, ReplayButton } from '../shared/research-form';
export default function Backtesting() {
  const s = useSelection('backtest');
  const [chosenBenchmark, setBenchmark] = useState<string | null>(null);
  const [tradeOffset, setTradeOffset] = useState(0);
  const [kind, setKind] = useState('fills');
  const run = useObject(s.id ? `/api/backtest/${s.id}` : undefined);
  const metrics = useObject(s.id ? `/api/backtest/${s.id}/metrics` : undefined);
  const equity = usePage(s.id ? `/api/backtest/${s.id}/equity?limit=2000` : undefined);
  const trades = usePage(
    s.id ? `/api/backtest/${s.id}/trades?kind=${kind}&limit=50&offset=${tradeOffset}` : undefined,
  );
  const cfg = record(record(run.data?.manifest).configuration);
  const m = record(metrics.data?.metrics);
  const candidates = s.items.filter(
    (c) =>
      c.id !== s.id &&
      c.configuration.start === cfg.start &&
      c.configuration.end === cfg.end &&
      JSON.stringify(c.configuration.tickers) === JSON.stringify(cfg.tickers),
  );
  const benchmark =
    chosenBenchmark ??
    candidates.find((c) => record(c.configuration.strategy).name === 'buy_hold')?.id ??
    '';
  const bench = usePage(benchmark ? `/api/backtest/${benchmark}/equity?limit=2000` : undefined);
  const benchRun = useObject(benchmark ? `/api/backtest/${benchmark}` : undefined);
  const benchConfig = record(record(benchRun.data?.manifest).configuration);
  const comparable =
    !!benchRun.data &&
    cfg.capital === benchConfig.capital &&
    JSON.stringify(cfg.costs) === JSON.stringify(benchConfig.costs);
  const data = alignedEquity(equity.data?.items ?? [], comparable ? (bench.data?.items ?? []) : []);
  const analytics = ledgerAnalytics(equity.data?.items ?? []);
  const months = monthlyReturns(equity.data?.items ?? []);
  const last = equity.data?.items.at(-1);
  return (
    <>
      <PageHeader
        title="Backtesting analytics"
        description="Inspect the authoritative simulated ledger, compare matched historical experiments, and separate results from assumptions."
        action={<Badge>Research approximation</Badge>}
      />
      <RunSelect
        items={s.items}
        value={s.id}
        onChange={(id) => {
          s.select(id);
          setBenchmark(null);
          setTradeOffset(0);
        }}
        next={s.catalog.data?.next_offset}
        onNext={s.next}
      />
      {s.catalog.isError ? (
        <Failure error={s.catalog.error} />
      ) : s.catalog.isPending ? (
        <Loading />
      ) : !s.id ? (
        <Empty title="No backtest saved" />
      ) : run.isError ? (
        <Failure error={run.error} />
      ) : (
        <>
          <div className="metrics">
            <Metric
              label="Total simulated return"
              value={percent(finite(m.total_return))}
              detail="After modeled costs"
              tone={(finite(m.total_return) ?? 0) < 0 ? 'bad' : 'good'}
            />
            <Metric
              label="Maximum drawdown"
              value={percent(finite(m.maximum_drawdown))}
              detail="Actual ledger path"
            />
            <Metric
              label="Annualized volatility"
              value={percent(finite(m.annualized_volatility))}
              detail="Short samples are unstable"
            />
            <Metric
              label="Total modeled costs"
              value={
                finite(m.commissions) !== null && finite(m.slippage) !== null
                  ? money(finite(m.commissions)! + finite(m.slippage)!)
                  : 'Unavailable'
              }
              detail="Commissions + slippage"
            />
          </div>
          <div className="run-select">
            <label>
              Matched benchmark experiment
              <select
                aria-label="Benchmark experiment"
                value={benchmark}
                onChange={(e) => setBenchmark(e.target.value)}
              >
                <option value="">No benchmark selected</option>
                {candidates.map((c) => (
                  <option key={c.id} value={c.id}>
                    {text(record(c.configuration.strategy).name, c.label)} · {c.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
            <ReplayButton path={`/api/backtest/${s.id}/replay`} />
          </div>
          <Panel
            title="Equity comparison"
            eyebrow="USD · exact date alignment"
            action={<Badge>Gaps remain missing</Badge>}
          >
            {equity.isError ? (
              <Failure error={equity.error} />
            ) : (
              <SeriesChart
                label="Portfolio and selected matched benchmark equity"
                data={data}
                series={[
                  { key: 'portfolio', label: 'Selected simulation' },
                  ...(benchmark ? [{ key: 'benchmark', label: 'Matched benchmark' }] : []),
                ]}
              />
            )}
            {bench.isError && <Failure error={bench.error} />}
            {benchmark && benchRun.isSuccess && !comparable && (
              <Note>
                Benchmark capital or cost assumptions differ. Its curve is withheld rather than
                implying a matched comparison.
              </Note>
            )}
            <div className="panel-body">
              <Note>
                Benchmarks must share the universe and evaluation range. The chart aligns actual
                session labels; no future observations or carried-forward values are added. Capital
                and cost assumptions remain available in each manifest.
              </Note>
              {equity.data?.next_offset != null && (
                <Note>
                  This chart is a bounded first2,000-observation window, not the complete run.
                  Retrieve further pages through the documented API before interpreting full-history
                  patterns.
                </Note>
              )}
            </div>
          </Panel>
          <div className="grid-two" style={{ marginTop: 20 }}>
            <Panel title="Drawdown" eyebrow="Derived from stored closing equity">
              <SeriesChart
                label="Realized drawdown below past equity peak"
                unit="percent"
                kind="area"
                data={analytics}
                series={[{ key: 'drawdown', label: 'Drawdown' }]}
              />
            </Panel>
            <Panel title="Exposure history" eyebrow="Actual filled positions / equity">
              <SeriesChart
                label="Actual ledger gross exposure"
                unit="percent"
                data={analytics}
                series={[{ key: 'exposure', label: 'Gross exposure' }]}
              />
            </Panel>
          </div>
          <div className="grid-two">
            <Panel title="Rolling Sharpe" eyebrow="20 returns · zero risk-free-rate assumption">
              <SeriesChart
                label="20-session rolling Sharpe ratio"
                unit="ratio"
                data={analytics}
                series={[{ key: 'sharpe', label: 'Rolling Sharpe' }]}
              />
            </Panel>
            <Panel
              title="Rolling volatility"
              eyebrow="20 returns · sample standard deviation × √252"
            >
              <SeriesChart
                label="20-session annualized volatility"
                unit="percent"
                data={analytics}
                series={[{ key: 'volatility', label: 'Annualized volatility' }]}
              />
            </Panel>
          </div>
          <div className="grid-two">
            <Panel title="Monthly returns" eyebrow="Compound observed ledger returns">
              {months.length ? (
                <div className="monthly-grid">
                  {months.map((r) => (
                    <div key={r.month} className="month">
                      <span>{r.month}</span>
                      <strong className={r.return < 0 ? 'bad' : 'good'}>{percent(r.return)}</strong>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty title="Insufficient return observations" />
              )}
              <div className="panel-body">
                <Note>
                  First and last months may be partial. Undefined ratios and warmup windows are left
                  unavailable.
                </Note>
              </div>
            </Panel>
            <Panel title="Performance summary" eyebrow="Backend-computed statistics">
              <dl className="detail-list panel-body">
                {[
                  'cagr',
                  'sharpe',
                  'sortino',
                  'calmar',
                  'alpha',
                  'beta',
                  'tracking_error',
                  'turnover',
                  'win_rate',
                  'profit_factor',
                ].map((k) => (
                  <Fragment key={k}>
                    <dt>{k.replaceAll('_', ' ')}</dt>
                    <dd>
                      {['cagr', 'alpha', 'tracking_error', 'win_rate'].includes(k)
                        ? percent(finite(m[k]))
                        : decimal(finite(m[k]), 3)}
                    </dd>
                  </Fragment>
                ))}
              </dl>
            </Panel>
          </div>
          <Panel
            title="Simulated orders & fills"
            eyebrow="Rejected orders are not executed trades"
            action={
              <select
                aria-label="Trade record type"
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setTradeOffset(0);
                }}
              >
                <option value="fills">Actual fills</option>
                <option value="orders">Submitted orders</option>
                <option value="actions">Recorded actions</option>
              </select>
            }
          >
            {trades.isError ? (
              <Failure error={trades.error} />
            ) : (
              <DataTable
                label="Simulation trade records"
                rows={trades.data?.items ?? []}
                columns={[
                  {
                    key: kind === 'orders' ? 'execution_at' : 'at',
                    label: 'Execution',
                    render: (v) => timestamp(v),
                  },
                  { key: 'ticker', label: 'Asset' },
                  { key: 'side', label: 'Side' },
                  {
                    key: kind === 'orders' ? 'filled_quantity' : 'quantity',
                    label: 'Filled quantity',
                    render: (v) => decimal(finite(v), 4),
                  },
                  {
                    key: kind === 'orders' ? 'execution_price' : 'price',
                    label: 'Price',
                    render: (v) => money(finite(v)),
                  },
                  { key: 'status', label: 'Order status' },
                  { key: 'reason', label: 'Reason' },
                ]}
              />
            )}
            <div className="panel-body button-row">
              {tradeOffset > 0 && (
                <button
                  className="button subtle"
                  onClick={() => setTradeOffset((o) => Math.max(0, o - 50))}
                >
                  Previous records
                </button>
              )}
              {trades.data?.next_offset != null && (
                <button
                  className="button subtle"
                  onClick={() => setTradeOffset(trades.data!.next_offset!)}
                >
                  More records
                </button>
              )}
            </div>
          </Panel>
          <div className="grid-two" style={{ marginTop: 20 }}>
            <Panel title="Final actual holdings" eyebrow={text(last?.day)}>
              <DataTable
                label="Final ledger positions"
                rows={positions(equity.data?.items ?? [])}
                columns={[
                  { key: 'ticker', label: 'Asset' },
                  { key: 'quantity', label: 'Shares', render: (v) => decimal(finite(v), 4) },
                  { key: 'market_value', label: 'Market value', render: (v) => money(finite(v)) },
                  { key: 'weight', label: 'Weight', render: (v) => percent(finite(v)) },
                ]}
              />
            </Panel>
            <Panel title="Execution configuration">
              <JsonDetails value={cfg} label="Capital, costs, calendar & strategy" />
              <JsonDetails value={run.data?.diagnostics} label="Warnings & diagnostics" />
              <div className="panel-body">
                <Link className="text-button" href="/experiments">
                  Explore related research →
                </Link>
              </div>
            </Panel>
          </div>
          <Provenance value={run.data?.manifest} />
        </>
      )}
      <ResearchForm kind="backtest" seed={cfg} />
    </>
  );
}
