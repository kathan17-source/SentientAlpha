'use client';
import Link from 'next/link';
import { ArrowRight, ArrowUpRight, ShieldCheck } from 'lucide-react';
import { useObject, usePage, useSelection } from '@/lib/hooks';
import {
  record,
  records,
  finite,
  text,
  money,
  percent,
  decimal,
  timestamp,
  shortId,
} from '@/lib/format';
import { alignedEquity } from '@/lib/series';
import {
  Badge,
  Empty,
  Failure,
  Loading,
  Metric,
  Note,
  PageHeader,
  Panel,
  Provenance,
  RunSelect,
  statusTone,
} from '../shared/ui';
import { SeriesChart } from '../shared/charts';
import { DataTable } from '../shared/table';
export default function Overview() {
  const selection = useSelection('committee', 'm8_baseline');
  const run = useObject(selection.id ? `/api/investment-committee/${selection.id}` : undefined);
  const result = record(run.data?.result),
    metrics = record(result.metrics),
    manifest = record(run.data?.manifest),
    config = record(manifest.configuration);
  const backtest = text(run.data?.backtest_id, '');
  const equity = usePage(backtest ? `/api/backtest/${backtest}/equity?limit=500` : undefined);
  const trades = usePage(backtest ? `/api/backtest/${backtest}/trades?limit=10` : undefined);
  const decisions = usePage(
    selection.id ? `/api/investment-committee/${selection.id}/decisions?limit=1` : undefined,
  );
  const alerts = usePage('/api/risk/alerts?limit=4');
  const latest = equity.data?.items.at(-1);
  const eq = finite(latest?.equity);
  const starting = finite(equity.data?.items[0]?.equity);
  const proposals = record(decisions.data?.items[0]);
  const recommendations = records(proposals.recommendations);
  return (
    <>
      <PageHeader
        title="Research overview"
        description="A clear view of the evidence, simulated outcomes, and decisions behind your research."
        action={
          <Link className="button" href="/experiments">
            Explore experiments <ArrowUpRight size={14} />
          </Link>
        }
      />
      <RunSelect
        items={selection.items}
        value={selection.id}
        onChange={selection.select}
        next={selection.catalog.data?.next_offset}
        onNext={selection.next}
        label="Historical committee experiment"
      />
      {selection.catalog.isError ? (
        <Failure error={selection.catalog.error} retry={() => selection.catalog.refetch()} />
      ) : selection.catalog.isPending ? (
        <Loading />
      ) : !selection.id ? (
        <Empty title="Your research workspace is ready">
          No committee experiment is saved in this database. Explore available datasets or start a
          bounded committee analysis.
        </Empty>
      ) : run.isPending ? (
        <Loading />
      ) : run.isError ? (
        <Failure error={run.error} retry={() => run.refetch()} />
      ) : (
        <>
          <div className="metrics">
            <Metric
              label="Simulated portfolio equity"
              value={money(eq)}
              detail={`Ledger valuation · ${text(latest?.day)}`}
              href={`/portfolio?run=${selection.id}`}
            />
            <Metric
              label="Cumulative return"
              value={percent(finite(metrics.total_return))}
              detail="Historical simulation · after modeled costs"
              tone={(finite(metrics.total_return) ?? 0) < 0 ? 'bad' : 'good'}
              href={`/backtesting?run=${backtest}`}
            />
            <Metric
              label="Maximum drawdown"
              value={percent(finite(metrics.maximum_drawdown))}
              detail="Realized path · not a forecast"
              href={`/risk?committee=${selection.id}`}
            />
            <Metric
              label="Sharpe ratio"
              value={decimal(finite(metrics.sharpe))}
              detail="Annualized · short samples are unreliable"
              href={`/backtesting?run=${backtest}`}
            />
          </div>
          <div className="grid-main">
            <Panel
              title="Portfolio equity"
              eyebrow="Authoritative simulated ledger"
              action={<Badge>USD · historical</Badge>}
            >
              {equity.isError ? (
                <Failure error={equity.error} />
              ) : equity.isPending && backtest ? (
                <Loading />
              ) : (
                <SeriesChart
                  label="Historical simulated portfolio equity in USD"
                  data={alignedEquity(equity.data?.items ?? [], [])}
                  series={[{ key: 'portfolio', label: 'Selected experiment' }]}
                  kind="area"
                />
              )}
              <div className="panel-body" style={{ paddingTop: 0 }}>
                <Link className="text-button" href={`/backtesting?run=${backtest}`}>
                  Open benchmark comparison →
                </Link>
              </div>
            </Panel>
            <Panel
              title="Research snapshot"
              eyebrow="Selected experiment"
              action={<Badge tone={statusTone(run.data?.status)}>{text(run.data?.status)}</Badge>}
            >
              <div className="panel-body">
                <dl className="detail-list">
                  <dt>Universe</dt>
                  <dd>
                    {Array.isArray(config.tickers) ? config.tickers.join(', ') : 'Unavailable'}
                  </dd>
                  <dt>Evaluation period</dt>
                  <dd>
                    {text(config.start)} — {text(config.end)}
                  </dd>
                  <dt>Portfolio P&amp;L</dt>
                  <dd className={eq !== null && starting !== null && eq < starting ? 'bad' : ''}>
                    {eq !== null && starting !== null ? money(eq - starting) : 'Unavailable'}
                  </dd>
                  <dt>Actual cash</dt>
                  <dd>{money(finite(latest?.cash))}</dd>
                  <dt>Gross exposure</dt>
                  <dd>{percent(finite(latest?.gross_exposure))}</dd>
                  <dt>Simulated fills</dt>
                  <dd>{decimal(finite(result.fills), 0)}</dd>
                  <dt>Run ID</dt>
                  <dd>{shortId(selection.id)}</dd>
                </dl>
                <Note>
                  Past results describe a research approximation. Genuine predictive alpha has not
                  been established.
                </Note>
                <Link className="button subtle" href={`/committee?run=${selection.id}`}>
                  Inspect committee evidence <ArrowRight size={13} />
                </Link>
              </div>
            </Panel>
          </div>
          <div className="grid-two">
            <Panel
              title="Committee participation"
              eyebrow="First retained decision"
              action={
                <Link className="text-button" href={`/committee?run=${selection.id}`}>
                  Open workstation ↗
                </Link>
              }
            >
              {decisions.isError ? (
                <Failure error={decisions.error} />
              ) : (
                <DataTable
                  label="Agent participation"
                  pageSize={6}
                  filterable={false}
                  rows={recommendations}
                  columns={[
                    { key: 'agent_id', label: 'Agent' },
                    {
                      key: 'status',
                      label: 'Evidence status',
                      render: (v) => <Badge tone={statusTone(v)}>{text(v)}</Badge>,
                    },
                    { key: 'signal', label: 'Signal', render: (v) => decimal(finite(v), 3) },
                  ]}
                />
              )}
            </Panel>
            <Panel
              title="Risk audit"
              eyebrow="Recent saved alerts · all portfolios"
              action={<ShieldCheck size={16} color="#64c9c3" />}
            >
              {alerts.isError ? (
                <Failure error={alerts.error} />
              ) : !alerts.data?.items.length ? (
                <Empty title="No risk alerts recorded">
                  An empty alert history does not imply that all portfolios have been assessed.
                </Empty>
              ) : (
                alerts.data.items.map((a, i) => (
                  <Link
                    className="alert-row"
                    key={text(a.id, String(i))}
                    href={`/risk?assessment=${text(a.assessment_id, '')}`}
                  >
                    <Badge tone="warn">Review</Badge>
                    <div>
                      <strong>{text(a.metric).replaceAll('_', ' ')}</strong>
                      <p>
                        {text(
                          a.explanation,
                          'Inspect the retained risk measurement and applicable policy.',
                        )}
                      </p>
                    </div>
                  </Link>
                ))
              )}
            </Panel>
          </div>
          <Panel
            title="Recent simulated fills"
            eyebrow="Executed ledger records · selected experiment"
            action={
              <Link className="text-button" href={`/backtesting?run=${backtest}`}>
                All trades ↗
              </Link>
            }
          >
            {trades.isError ? (
              <Failure error={trades.error} />
            ) : (
              <DataTable
                label="Recent fills"
                filterable={false}
                pageSize={5}
                rows={trades.data?.items ?? []}
                columns={[
                  { key: 'at', label: 'Execution time', render: (v) => timestamp(v) },
                  { key: 'ticker', label: 'Security' },
                  {
                    key: 'side',
                    label: 'Side',
                    render: (v) => <Badge tone={v === 'buy' ? 'cyan' : 'neutral'}>{text(v)}</Badge>,
                  },
                  { key: 'quantity', label: 'Filled shares', render: (v) => decimal(finite(v), 4) },
                  { key: 'price', label: 'Fill price', render: (v) => money(finite(v)) },
                  { key: 'commission', label: 'Commission', render: (v) => money(finite(v)) },
                ]}
              />
            )}
          </Panel>
          <Provenance
            value={{
              ...config,
              run_id: selection.id,
              build_id: manifest.build_id,
              valuation: latest,
              information_policy: config.information_policy,
              limitations: manifest.limitations,
            }}
          />
          <Note>
            Displayed metrics come from this saved run. The toolbar filters market/security
            research; saved experiments retain their own immutable universe and evaluation dates.
          </Note>
        </>
      )}
    </>
  );
}
