'use client';
import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useCatalog, useObject, usePage, useSelection } from '@/lib/hooks';
import { record, records, text, finite, money, percent, decimal } from '@/lib/format';
import { entries, positions } from '@/lib/series';
import {
  Badge,
  Empty,
  Failure,
  JsonDetails,
  Metric,
  Note,
  PageHeader,
  Panel,
  Provenance,
  RunSelect,
} from '../shared/ui';
import { Correlation, SeriesChart } from '../shared/charts';
import { DataTable } from '../shared/table';
import { ResearchForm, ReplayButton } from '../shared/research-form';
export default function Portfolio() {
  const params = useSearchParams();
  const s = useSelection('committee', 'concentration');
  const run = useObject(s.id ? `/api/investment-committee/${s.id}` : undefined);
  const backtest = text(run.data?.backtest_id, '');
  const eq = usePage(backtest ? `/api/backtest/${backtest}/equity?limit=2000` : undefined);
  const [historyIndex, setHistoryIndex] = useState<number | null>(null);
  const history = eq.data?.items ?? [];
  const index = Math.min(historyIndex ?? history.length - 1, history.length - 1);
  const current = history[index];
  const config = record(record(run.data?.manifest).configuration);
  const pid = text(config.idempotency_key, '');
  const risk = useObject(
    pid && config.risk_policy && current?.at
      ? `/api/risk/portfolio/${encodeURIComponent(pid)}?as_of=${encodeURIComponent(text(current?.at))}`
      : undefined,
  );
  const currentRisk = record(record(risk.data?.payload).current);
  const volatility = record(currentRisk.volatility);
  const decision = usePage(
    s.id
      ? `/api/investment-committee/${s.id}/decisions?limit=1&offset=${Math.max(0, (finite(record(run.data?.result).decision_count) ?? 1) - 1)}`
      : undefined,
  );
  const last = decision.data?.items.at(-1);
  const allocation = record(last?.allocation);
  const proposed = record(record(allocation.proposal).weights);
  const approved = record(allocation.final_allocation);
  const optCatalog = useCatalog('optimization');
  const [selectedOpt, setOpt] = useState<string | null>(null);
  const opt = selectedOpt ?? params.get('optimization') ?? optCatalog.data?.items[0]?.id ?? '';
  const optRun = useObject(opt ? `/api/portfolio/optimization/${opt}` : undefined);
  const optResult = useObject(opt ? `/api/portfolio/optimization/${opt}/result` : undefined);
  const summary = record(record(optResult.data?.result).data);
  const points = useObject(
    opt && optRun.data?.kind === 'frontier'
      ? `/api/portfolio/optimization/${opt}/result?section=points&limit=100`
      : undefined,
  );
  const [pointIndex, setPointIndex] = useState(0);
  const rawPoints = records(record(points.data?.result).data);
  const result =
    optRun.data?.kind === 'frontier'
      ? (rawPoints[Math.min(pointIndex, rawPoints.length - 1)] ?? {})
      : summary;
  const expected = record(result.risk);
  const frontier = records(record(points.data?.result).data).map((r) => ({
    ...r,
    volatility: record(r.risk).volatility,
    expected_return: record(r.risk).expected_return,
  }));
  const weightRows = Array.from(
    new Set([
      ...Object.keys(proposed),
      ...Object.keys(approved),
      ...positions(history, index).map((p) => text(p.ticker)),
    ]),
  ).map((t) => ({
    ticker: t,
    actual: positions(history, index).find((p) => p.ticker === t)?.weight ?? (current ? 0 : null),
    proposed: proposed[t],
    approved: approved[t],
  }));
  return (
    <>
      <PageHeader
        title="Portfolio workstation"
        description="Separate actual filled holdings from theoretical targets. Explore allocations, risk sources, and numerical optimization."
      />
      <RunSelect
        items={s.items}
        value={s.id}
        onChange={(id) => {
          s.select(id);
          setHistoryIndex(null);
        }}
        next={s.catalog.data?.next_offset}
        onNext={s.next}
        label="Committee-linked simulated portfolio"
      />
      {s.catalog.isError ? (
        <Failure error={s.catalog.error} />
      ) : !s.id ? (
        <Empty title="No simulated portfolio saved" />
      ) : run.isError ? (
        <Failure error={run.error} />
      ) : (
        <>
          <div className="metrics">
            <Metric
              label="Actual ledger equity"
              value={money(finite(current?.equity))}
              detail={text(current?.day)}
            />
            <Metric
              label="Actual cash"
              value={money(finite(current?.cash))}
              detail="Available simulated cash"
            />
            <Metric
              label="Gross exposure"
              value={percent(finite(current?.gross_exposure))}
              detail="Actual filled market values / equity"
            />
            <Metric
              label="Unrealized P&L"
              value={money(finite(current?.unrealized_pnl))}
              detail="From the authoritative M4 ledger"
            />
          </div>
          <Panel title="Historical holdings" eyebrow="Actual closing ledger snapshots">
            <div className="panel-body">
              <label className="field">
                Valuation snapshot · {text(current?.day)}
                <input
                  aria-label="Historical holdings snapshot"
                  type="range"
                  min={0}
                  max={Math.max(0, history.length - 1)}
                  value={Math.max(0, index)}
                  onChange={(e) => setHistoryIndex(Number(e.target.value))}
                  disabled={!history.length}
                />
              </label>
            </div>
            {eq.isError ? (
              <Failure error={eq.error} />
            ) : (
              <DataTable
                label="Actual ledger holdings"
                rows={positions(history, index)}
                columns={[
                  {
                    key: 'ticker',
                    label: 'Security',
                    render: (v) => (
                      <Link className="text-button" href={`/research?ticker=${text(v)}`}>
                        {text(v)}
                      </Link>
                    ),
                  },
                  { key: 'quantity', label: 'Quantity', render: (v) => decimal(finite(v), 4) },
                  { key: 'market_value', label: 'Market value', render: (v) => money(finite(v)) },
                  { key: 'weight', label: 'Actual weight', render: (v) => percent(finite(v)) },
                  { key: 'average_cost', label: 'Average cost', render: (v) => money(finite(v)) },
                  {
                    key: 'unrealized_pnl',
                    label: 'Unrealized P&L',
                    render: (v) => money(finite(v)),
                  },
                ]}
              />
            )}
            <JsonDetails label="Exact ledger snapshot and cost basis fields" value={current} />
          </Panel>
          <div className="grid-two" style={{ marginTop: 20 }}>
            <Panel
              title="Allocation composition"
              eyebrow={`Actual snapshot · ${text(current?.day)}`}
            >
              <SeriesChart
                label="Actual security allocation"
                kind="bar"
                unit="percent"
                x="asset"
                data={positions(history, index).map((r) => ({
                  asset: r.ticker,
                  value: finite(r.weight),
                }))}
                series={[{ key: 'value', label: 'Actual weight' }]}
              />
            </Panel>
            <Panel
              title="Proposed versus actual"
              eyebrow={`Proposal at ${text(last?.day)} · actual at ${text(current?.day)}`}
            >
              <DataTable
                label="Allocation distinctions"
                filterable={false}
                rows={weightRows}
                columns={[
                  { key: 'ticker', label: 'Asset' },
                  { key: 'proposed', label: 'M5 proposed', render: (v) => percent(finite(v)) },
                  {
                    key: 'approved',
                    label: 'Risk-approved target',
                    render: (v) => percent(finite(v)),
                  },
                  {
                    key: 'actual',
                    label: 'Selected actual snapshot',
                    render: (v) => percent(finite(v)),
                  },
                ]}
              />
              <div className="panel-body">
                <Note>
                  Targets are proposals, not executed holdings. Dates are shown separately; partial
                  fills and market movement can produce differences.
                </Note>
              </div>
            </Panel>
          </div>
          <div className="grid-two">
            <Panel
              title="Estimated risk contribution"
              eyebrow={`Latest M9 assessment · ${text(risk.data?.at)}`}
            >
              <SeriesChart
                label="Component contribution to annual volatility"
                kind="bar"
                unit="percent"
                x="asset"
                data={entries(volatility.component_volatility)}
                series={[{ key: 'value', label: 'Component volatility' }]}
              />
            </Panel>
            <Panel title="Sector exposure" eyebrow="Latest M9 assessment · unknown stays unknown">
              <SeriesChart
                label="Sector concentration"
                kind="bar"
                unit="percent"
                x="asset"
                data={entries(record(currentRisk.exposure).sectors)}
                series={[{ key: 'value', label: 'Sector weight' }]}
              />
            </Panel>
          </div>
          <Panel title="Correlation matrix" eyebrow="Eligible historical return estimate">
            <Correlation matrix={volatility.correlation} names={volatility.asset_order} />
            {!config.risk_policy && (
              <div className="panel-body">
                <Note>
                  This experiment has no advanced M9 policy. Select an M9-enabled run for linked
                  risk analytics.
                </Note>
              </div>
            )}
          </Panel>
          <Provenance value={run.data?.manifest} />
        </>
      )}
      <div style={{ marginTop: 28 }}>
        <PageHeader
          title="Numerical allocation research"
          description="Existing M5 optimizer results. These are estimated target portfolios and do not alter any simulated ledger."
          tag="Portfolio optimization"
        />
        <RunSelect
          items={optCatalog.data?.items ?? []}
          value={opt}
          onChange={setOpt}
          label="Saved optimization / frontier"
        />
        {optRun.data?.kind === 'frontier' && rawPoints.length > 0 && (
          <div className="run-select">
            <label>
              Frontier point / risk-aversion configuration
              <select
                aria-label="Frontier point"
                value={pointIndex}
                onChange={(e) => setPointIndex(Number(e.target.value))}
              >
                {rawPoints.map((r, i) => (
                  <option key={i} value={i}>
                    Risk aversion {String(r.risk_aversion)} · {text(r.status)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        {optRun.isError ? (
          <Failure error={optRun.error} />
        ) : opt ? (
          <>
            <div className="metrics">
              <Metric
                label="Solver status"
                value={text(optRun.data?.status)}
                detail={text(optRun.data?.kind)}
              />
              <Metric
                label="Expected annual return"
                value={percent(finite(expected.expected_return))}
                detail="Historical estimator · not a forecast guarantee"
              />
              <Metric
                label="Estimated annual volatility"
                value={percent(finite(expected.volatility))}
              />
              <Metric label="Estimated turnover" value={percent(finite(expected.turnover))} />
            </div>
            <div className="grid-two">
              <Panel title="Optimizer target weights" action={<Badge>Not holdings</Badge>}>
                <DataTable
                  label="Optimizer proposed weights"
                  rows={entries(result.weights)}
                  columns={[
                    { key: 'asset', label: 'Security' },
                    { key: 'value', label: 'Proposed weight', render: (v) => percent(finite(v)) },
                  ]}
                />
                <JsonDetails value={result} label="Solver warnings, constraints & attribution" />
              </Panel>
              <Panel title="Efficient frontier" eyebrow="Solved numerical points only">
                <SeriesChart
                  label="Expected-return versus volatility frontier"
                  kind="scatter"
                  unit="percent"
                  x="volatility"
                  data={frontier}
                  series={[{ key: 'expected_return', label: 'Estimated return' }]}
                />
                <div className="panel-body">
                  <Note>
                    Frontier points appear only for an actual saved frontier run. Other optimizer
                    runs are not interpolated into fictional points.
                  </Note>
                </div>
              </Panel>
            </div>
            <ReplayButton path={`/api/portfolio/optimization/${opt}/replay`} />
            <Provenance value={optRun.data?.manifest} />
          </>
        ) : (
          <Empty title="No saved optimization" />
        )}
        <ResearchForm
          kind="optimization"
          seed={record(record(optRun.data?.manifest).configuration)}
        />
      </div>
    </>
  );
}
