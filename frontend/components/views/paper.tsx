'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, objectSchema, pageSchema } from '@/lib/api/client';
import {
  finite,
  money,
  percent,
  record,
  records,
  text,
  timestamp,
  type RecordData,
} from '@/lib/format';
import { modeLabel, paperActions } from '@/lib/paper';
import {
  Badge,
  ConfirmDialog,
  Empty,
  Failure,
  JsonDetails,
  Loading,
  Metric,
  Note,
  PageHeader,
  Panel,
} from '../shared/ui';
import { DataTable } from '../shared/table';
import { SeriesChart } from '../shared/charts';

type Request = { path: string; body: RecordData; title: string };
export default function Paper() {
  const cache = useQueryClient();
  const [selected, setSelected] = useState('');
  const [offset, setOffset] = useState(0);
  const [kind, setKind] = useState('orders');
  const [recordOffset, setRecordOffset] = useState(0);
  const [pending, setPending] = useState<Request | null>(null);
  const [inspected, setInspected] = useState<RecordData | null>(null);
  const [validation, setValidation] = useState('');
  const sessions = useQuery({
    queryKey: ['paper', 'sessions', offset],
    queryFn: ({ signal }) =>
      api(`/api/paper/sessions?limit=20&offset=${offset}`, pageSchema, { signal }),
    staleTime: 0,
  });
  const id = selected || text(sessions.data?.items[0]?.id, '');
  const session = useQuery({
    queryKey: ['paper', id],
    queryFn: ({ signal }) => api(`/api/paper/sessions/${id}`, objectSchema, { signal }),
    enabled: !!id,
    staleTime: 0,
  });
  const history = useQuery({
    queryKey: ['paper', id, kind, recordOffset],
    queryFn: ({ signal }) =>
      api(`/api/paper/sessions/${id}/${kind}?limit=20&offset=${recordOffset}`, pageSchema, {
        signal,
      }),
    enabled: !!id,
    staleTime: 0,
  });
  const performance = useQuery({
    queryKey: ['paper', id, 'performance'],
    queryFn: ({ signal }) => api(`/api/paper/sessions/${id}/performance`, objectSchema, { signal }),
    enabled: !!id,
    staleTime: 0,
  });
  const job = useMutation({
    mutationFn: (q: Request) => api(q.path, objectSchema, { body: q.body }),
    onSuccess: (data) => {
      if (pending?.path === '/api/paper/sessions') setSelected(text(data.id, ''));
      setPending(null);
      void cache.invalidateQueries({ queryKey: ['paper'] });
    },
  });
  const row = session.data ?? {};
  const portfolio = record(row.portfolio),
    metrics = record(record(performance.data?.data).metrics);
  const mode = text(row.mode),
    status = text(row.status);
  const request = (action: string, extra: RecordData = {}) => {
    job.reset();
    setPending({
      path: `/api/paper/sessions/${id}/${action}`,
      body: { key: 'ui-' + crypto.randomUUID(), ...extra },
      title: action === 'advance' ? 'Advance one eligible observation' : `${action} paper session`,
    });
  };
  const positions = Object.entries(record(portfolio.positions)).map(([ticker, value]) => ({
    ticker,
    ...record(value),
  }));
  const equity = records(record(performance.data?.data).equity).map((v) => ({
    ...v,
    equity: Number(v.equity),
  }));
  return (
    <>
      <PageHeader
        title="Paper trading"
        tag="Persistent local operations"
        description="Forward observations, durable decisions and authoritative simulated holdings. Daily execution is an explicitly labeled approximation."
        action={
          <button
            className="button"
            onClick={() => void cache.invalidateQueries({ queryKey: ['paper'] })}
          >
            Refresh persisted state
          </button>
        }
      />
      <Note>
        PAPER TRADING — SIMULATED EXECUTION — NO REAL MONEY. The local service or optional worker
        must remain running. No brokerage connection or always-on guarantee.
      </Note>
      <Panel title="Create a paper session" eyebrow="Immutable configuration">
        <details className="panel-body">
          <summary>Configure a new session</summary>
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              setValidation('');
              job.reset();
              const f = new FormData(event.currentTarget);
              const mode = String(f.get('mode'));
              const tickers = String(f.get('tickers'))
                .split(',')
                .map((t) => t.trim().toUpperCase())
                .filter(Boolean);
              const capital = Number(f.get('capital')),
                cap = Number(f.get('cap'));
              if (
                !tickers.length ||
                tickers.length > 50 ||
                new Set(tickers).size !== tickers.length ||
                tickers.some((t) => !/^[A-Z][A-Z0-9.-]{0,11}$/.test(t)) ||
                !Number.isFinite(capital) ||
                capital <= 0 ||
                capital > 1e9 ||
                !(cap > 0 && cap <= 1)
              ) {
                setValidation(
                  'Use 1–50 distinct tickers, positive capital up to one billion USD and an exposure cap in (0,1].',
                );
                return;
              }
              const effective = String(f.get('effective'));
              if (
                !/(Z|[+-]\d{2}:\d{2})$/.test(effective) ||
                !Number.isFinite(Date.parse(effective))
              ) {
                setValidation('Policy timestamp must include a timezone.');
                return;
              }
              setPending({
                path: '/api/paper/sessions',
                title: 'Create immutable simulated session',
                body: {
                  key: 'ui-create-' + crypto.randomUUID(),
                  mode,
                  provider: mode === 'synthetic_demo' ? 'synthetic' : 'alphavantage',
                  tickers,
                  capital: String(capital),
                  history_start: String(f.get('history')),
                  simulation_start: mode === 'synthetic_demo' ? String(f.get('start')) : null,
                  committee_policy: { effective_at: effective, minimum_independent_groups: 1 },
                  risk_policy: {
                    id: 'ui-paper-' + crypto.randomUUID(),
                    version: '1',
                    effective_at: effective,
                    constraints: { concentration: cap, cash_maximum: 1 },
                    estimator: { minimum_observations: 20 },
                    adjustment: 'reject',
                  },
                  costs: {
                    fixed: String(f.get('fee')),
                    slippage_bps: String(f.get('slippage')),
                    participation: '0.01',
                    position_limit: '1',
                  },
                },
              });
            }}
          >
            <label>
              Operating mode
              <select name="mode" defaultValue="synthetic_demo">
                <option value="synthetic_demo">Synthetic demonstration · virtual clock</option>
                <option value="forward_paper">Forward paper · actual processing times</option>
              </select>
            </label>
            <label>
              Universe
              <input name="tickers" defaultValue="AAPL" required />
            </label>
            <label>
              Starting simulated capital (USD)
              <input
                name="capital"
                type="number"
                defaultValue="100000"
                min="1"
                max="1000000000"
                required
              />
            </label>
            <label>
              History start
              <input name="history" type="date" defaultValue="2024-01-02" required />
            </label>
            <label>
              Synthetic start (ignored in forward mode)
              <input name="start" type="date" defaultValue="2024-04-01" required />
            </label>
            <label>
              Policy effective timestamp (UTC)
              <input name="effective" defaultValue="2023-12-31T00:00:00Z" required />
            </label>
            <label>
              Single-security cap (fraction)
              <input
                name="cap"
                type="number"
                defaultValue="0.4"
                min="0.01"
                max="1"
                step="0.01"
                required
              />
            </label>
            <label>
              Commission per fill (USD)
              <input
                name="fee"
                type="number"
                defaultValue="1"
                min="0"
                max="1000"
                step="0.01"
                required
              />
            </label>
            <label>
              Slippage (basis points)
              <input name="slippage" type="number" defaultValue="5" min="0" max="1000" required />
            </label>
            <div className="wide">
              <Note>
                Creation does not start processing. Ready → Start is explicit. Synthetic bars
                require the offline demo seed or a separate explicit provider update. Forward mode
                uses actual receipt/processing clocks; historical backfill cannot become past paper
                trades. Historical replay remains in <Link href="/backtesting">Backtesting</Link>.
                Optional model/news versions are supported by the typed API; no automatic training
                or discovery runs here.
              </Note>
              {validation && <p role="alert">{validation}</p>}
              <button className="button primary" type="submit">
                Review new session
              </button>
            </div>
          </form>
        </details>
      </Panel>
      {sessions.isPending && <Loading />}
      {sessions.isError && <Failure error={sessions.error} />}
      <label className="field">
        Saved paper session
        <select
          aria-label="Saved paper session"
          value={id}
          onChange={(e) => {
            setSelected(e.target.value);
            setPending(null);
            setRecordOffset(0);
            setInspected(null);
          }}
        >
          <option value="">Select a session</option>
          {sessions.data?.items.map((v) => (
            <option key={text(v.id)} value={text(v.id)}>
              {modeLabel(text(v.mode))} · {text(v.status)} · {text(v.id).slice(0, 8)}
            </option>
          ))}
        </select>
      </label>
      <div className="run-select">
        <button
          className="button"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Earlier session page
        </button>
        <button
          className="button"
          disabled={sessions.data?.next_offset == null}
          onClick={() => setOffset(sessions.data?.next_offset ?? offset)}
        >
          Next session page
        </button>
      </div>
      {!id && !sessions.isPending && (
        <Empty title="No paper sessions saved">
          Create a session, inspect its configuration, then explicitly ready and start it. No
          positions or returns are invented.
        </Empty>
      )}
      {session.isError && <Failure error={session.error} />}
      {session.data && (
        <>
          <Panel
            title="Session control"
            eyebrow={modeLabel(mode)}
            action={
              <Badge tone={status === 'RUNNING' ? 'good' : status === 'FAILED' ? 'bad' : 'warn'}>
                {status}
              </Badge>
            }
          >
            <div className="panel-body">
              <Note>
                {modeLabel(mode)}. Execution convention: next eligible observed close, IOC; an
                earlier daily open is never reused. Queued targets do not change holdings.
              </Note>
              {!!row.warning && <Note>{text(row.warning)}</Note>}
              <div className="run-select">
                {paperActions(status, mode).map((action) => (
                  <button
                    key={action}
                    className="button"
                    disabled={job.isPending}
                    onClick={() =>
                      request(action, action === 'advance' ? { maximum_events: 1 } : {})
                    }
                  >
                    {action === 'advance'
                      ? 'Advance next observation'
                      : action[0].toUpperCase() + action.slice(1)}
                  </button>
                ))}
                <button className="button" onClick={() => request('reconcile')}>
                  Reconcile immutable events
                </button>
                {['READY', 'RUNNING', 'PAUSED'].includes(status) && (
                  <button
                    className="button"
                    onClick={() => {
                      const end = new Date(Date.now() - 86400000),
                        start = new Date(Date.now() - 8 * 86400000);
                      request('update', {
                        start: start.toISOString().slice(0, 10),
                        end: end.toISOString().slice(0, 10),
                      });
                    }}
                  >
                    Update last seven completed dates
                  </button>
                )}
              </div>
              <JsonDetails
                label="Immutable session configuration and operational state"
                value={row}
              />
            </div>
          </Panel>
          <div className="metrics">
            <Metric
              label="Realized equity drawdown"
              value={percent(finite(metrics.maximum_drawdown))}
              detail="Actual session equity peaks"
            />
            <Metric
              label="Simulated equity"
              value={money(finite(portfolio.equity))}
              detail={modeLabel(mode)}
            />
            <Metric label="Cash · actual ledger" value={money(finite(portfolio.cash))} />
            <Metric label="Realized P&L" value={money(finite(portfolio.realized_pnl))} />
            <Metric label="Unrealized P&L" value={money(finite(portfolio.unrealized_pnl))} />
            <Metric label="Gross exposure" value={percent(finite(portfolio.gross_exposure))} />
            <Metric
              label="Cumulative simulated return"
              value={percent(finite(metrics.total_return))}
              detail="Stored session only · no historical curve splicing"
            />
          </div>
          <div className="grid-two">
            <Panel
              title="Authoritative positions"
              eyebrow={
                row.valuation_stale
                  ? 'Valuation stale / no eligible snapshot'
                  : 'Latest available valuation'
              }
            >
              <div className="panel-body">
                <p>
                  Observation: {text(portfolio.day)} · processed {timestamp(portfolio.processed_at)}
                </p>
                <p>
                  Pending orders: {text(row.pending_orders, String(row.pending_orders ?? 0))} · Fees{' '}
                  {money(finite(portfolio.fees))} · Slippage {money(finite(portfolio.slippage))}
                </p>
                <DataTable
                  label="Paper ledger holdings"
                  rows={positions}
                  columns={[
                    { key: 'ticker', label: 'Security' },
                    { key: 'quantity', label: 'Filled shares' },
                    {
                      key: 'cost_basis',
                      label: 'Cost basis (USD)',
                      render: (v) => money(finite(v)),
                    },
                    { key: 'weight', label: 'Actual weight', render: (v) => percent(finite(v)) },
                  ]}
                />
                <Note>{text(row.reservation_policy)}</Note>
              </div>
            </Panel>
            <Panel title="Session equity" eyebrow={modeLabel(mode)}>
              <SeriesChart
                label="Paper session equity in USD"
                data={equity}
                x="day"
                series={[{ key: 'equity', label: 'Actual ledger equity' }]}
                unit="currency"
              />
              <div className="panel-body">
                <Note>
                  Short sessions withhold annualized ratios and tail statistics. No independently
                  received aligned forward benchmark is configured. No benchmark is fabricated.
                </Note>
                <JsonDetails
                  label="Actual simulated performance and history limits"
                  value={performance.data}
                />
              </div>
            </Panel>
          </div>
          <Panel
            title="Latest committee decision"
            eyebrow="Evidence-backed research · M9 remains authoritative"
          >
            <div className="panel-body">
              {!row.latest_decision ? (
                <Empty title="No forward decision recorded">
                  No historical decision is substituted for a paper decision.
                </Empty>
              ) : (
                <>
                  <p>
                    Decision: {timestamp(record(row.latest_decision).at)} · M9{' '}
                    {text(record(record(row.latest_decision).m9).status)}
                  </p>
                  <DataTable
                    label="Paper agent participation"
                    rows={records(record(record(row.latest_decision).payload).recommendations)}
                    columns={[
                      { key: 'agent_id', label: 'Agent' },
                      { key: 'ticker', label: 'Security' },
                      { key: 'status', label: 'Participation' },
                      { key: 'signal', label: 'Heuristic signal' },
                      { key: 'reasoning', label: 'Evidence / abstention reason' },
                    ]}
                  />
                  <DataTable
                    label="Paper proposal versus approved versus filled"
                    rows={Object.keys(
                      record(record(record(row.latest_decision).payload).aggregation),
                    ).map((ticker) => ({
                      ticker,
                      proposed: record(
                        record(record(record(row.latest_decision).payload).allocation)
                          .final_allocation,
                      )[ticker],
                      approved: record(record(record(row.latest_decision).m9).approved_targets)[
                        ticker
                      ],
                      actual: record(record(portfolio.positions)[ticker]).weight,
                    }))}
                    columns={[
                      { key: 'ticker', label: 'Security' },
                      { key: 'proposed', label: 'M5 proposal', render: (v) => percent(finite(v)) },
                      {
                        key: 'approved',
                        label: 'M9 approved target',
                        render: (v) => percent(finite(v)),
                      },
                      {
                        key: 'actual',
                        label: 'Actually filled weight',
                        render: (v) => percent(finite(v)),
                      },
                    ]}
                  />
                  <JsonDetails
                    label="Latest decision, evidence clocks, policy and independent veto"
                    value={row.latest_decision}
                  />
                </>
              )}
              <JsonDetails
                label="Latest provider update (unavailable until explicitly requested)"
                value={row.last_provider_update}
              />
            </div>
          </Panel>
          <Panel title="Orders, decisions and operational audit" eyebrow="Durable records">
            <div className="panel-body">
              <label>
                Record type
                <select
                  aria-label="Paper record type"
                  value={kind}
                  onChange={(e) => {
                    setKind(e.target.value);
                    setRecordOffset(0);
                    setInspected(null);
                  }}
                >
                  {['orders', 'fills', 'decisions', 'risk', 'events'].map((k) => (
                    <option key={k}>{k}</option>
                  ))}
                </select>
              </label>
              {history.isError && <Failure error={history.error} />}
              {history.isPending && <Loading />}
              <DataTable
                label={`Paper ${kind}`}
                rows={history.data?.items ?? []}
                columns={
                  kind === 'orders'
                    ? [
                        { key: 'ticker', label: 'Security' },
                        { key: 'side', label: 'Side' },
                        { key: 'status', label: 'State' },
                        { key: 'requested_quantity', label: 'Requested' },
                        { key: 'filled_quantity', label: 'Filled' },
                        { key: 'remaining_quantity', label: 'Unfilled' },
                        { key: 'reason', label: 'Risk / execution reason' },
                      ]
                    : kind === 'fills'
                      ? [
                          { key: 'ticker', label: 'Security' },
                          { key: 'quantity', label: 'Filled shares' },
                          { key: 'price', label: 'Execution USD', render: (v) => money(finite(v)) },
                          { key: 'commission', label: 'Fee USD', render: (v) => money(finite(v)) },
                          { key: 'at', label: 'Simulation timestamp', render: (v) => timestamp(v) },
                        ]
                      : [
                          { key: 'id', label: 'Record ID' },
                          {
                            key: kind === 'events' ? 'kind' : kind === 'risk' ? 'phase' : 'at',
                            label: 'Phase / decision time',
                          },
                          { key: 'status', label: 'Status' },
                        ]
                }
                onSelect={setInspected}
              />
              <div className="run-select">
                <button
                  className="button"
                  disabled={recordOffset === 0}
                  onClick={() => setRecordOffset(Math.max(0, recordOffset - 20))}
                >
                  Previous audit page
                </button>
                <button
                  className="button"
                  disabled={history.data?.next_offset == null}
                  onClick={() => setRecordOffset(history.data?.next_offset ?? recordOffset)}
                >
                  Next audit page
                </button>
              </div>
              {inspected && (
                <>
                  <JsonDetails
                    label="Exact selected operational record and evidence"
                    value={inspected}
                  />
                  {kind === 'orders' &&
                    ['QUEUED', 'APPROVED', 'PENDING_RISK', 'CREATED'].includes(
                      text(inspected.status),
                    ) && (
                      <button
                        className="button"
                        onClick={() => request(`orders/${text(inspected.id)}/cancel`)}
                      >
                        Review cancellation
                      </button>
                    )}
                  {!!inspected.committee_id && (
                    <Link href={`/committee?run=${text(inspected.committee_id)}`}>
                      Open source committee record →
                    </Link>
                  )}
                </>
              )}
            </div>
          </Panel>
        </>
      )}
      {pending && (
        <Panel title="Review local simulation command" eyebrow={pending.title}>
          <div className="panel-body">
            <JsonDetails label="Exact paper command" value={pending} />
            <ConfirmDialog
              title={pending.title}
              description="This changes only durable local simulated records. No brokerage or real-money action exists. Retrying a failed request uses this same command key."
              onConfirm={() => job.mutate(pending)}
              disabled={job.isPending}
            >
              {job.isPending ? 'Processing…' : 'Confirm reviewed paper command'}
            </ConfirmDialog>
            <button className="button" onClick={() => setPending(null)} disabled={job.isPending}>
              Discard review
            </button>
          </div>
        </Panel>
      )}
      {job.isError && <Failure error={job.error} />}
      {job.isSuccess && <JsonDetails label="Actual paper operation response" value={job.data} />}
    </>
  );
}
