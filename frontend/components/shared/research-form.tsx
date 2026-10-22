'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { z } from 'zod';
import { api, objectSchema } from '@/lib/api/client';
import { useCatalog, useObject } from '@/lib/hooks';
import { finite, record, records, text, money, percent, type RecordData } from '@/lib/format';
import { useResearch } from '../shell';
import { Badge, ConfirmDialog, Failure, JsonDetails, Note, Panel } from './ui';

export function ReplayButton({ path }: { path: string }) {
  const job = useMutation({ mutationFn: () => api(path, objectSchema, { body: {} }) });
  return (
    <div>
      <ConfirmDialog
        title="Replay saved research"
        description="Recalculate from retained immutable inputs. A changed code build or source may correctly produce a replay-mismatch error. No orders or live trades are submitted."
        onConfirm={() => job.mutate()}
        disabled={job.isPending}
      >
        {job.isPending ? 'Replaying…' : 'Verify historical replay'}
      </ConfirmDialog>
      {job.isError && <Failure error={job.error} />}{' '}
      {job.isSuccess && <JsonDetails label="Actual replay response" value={job.data} />}
    </div>
  );
}
const controls = z
  .object({
    tickers: z.string().min(1),
    start: z.iso.date(),
    end: z.iso.date(),
    capital: z.coerce.number().positive().max(10000000),
    concentration: z.coerce.number().gt(0).lte(1),
    candidates: z.coerce.number().int().min(1).max(100),
  })
  .refine((v) => v.start <= v.end, { message: 'Start must precede end', path: ['end'] });
const before = (date: string) =>
  new Date(new Date(date + 'T00:00:00Z').getTime() - 86400000).toISOString();
type FormKind = 'backtest' | 'optimization' | 'committee' | 'strategy';
export function ResearchForm({ kind, seed = {} }: { kind: FormKind; seed?: RecordData }) {
  const context = useResearch();
  const datasets = useCatalog('features');
  const [datasetId, setDataset] = useState<string | null>(null);
  const ds =
    datasetId ??
    datasets.data?.items.find(
      (d) =>
        d.configuration.provider === context.provider &&
        Array.isArray(d.configuration.tickers) &&
        d.configuration.tickers.includes(context.ticker),
    )?.id ??
    datasets.data?.items[0]?.id ??
    '';
  const dataset = useObject(ds ? `/api/feature-datasets/${ds}` : undefined);
  const [pending, setPending] = useState<{ path: string; body: RecordData } | null>(null);
  const [error, setError] = useState('');
  const cache = useQueryClient();
  const job = useMutation({
    mutationFn: (input: { path: string; body: RecordData }) =>
      api(input.path, objectSchema, { body: input.body }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['catalog'] }),
  });
  const title = {
    backtest: 'New baseline simulation',
    optimization: 'New portfolio optimization',
    committee: 'New committee analysis',
    strategy: 'New bounded strategy discovery',
  }[kind];
  const defaultStart = text(seed.start, kind === 'committee' ? context.end : context.start),
    defaultEnd = text(seed.end, context.end);
  const split = record(Array.isArray(seed.windows) ? seed.windows[0] : undefined);
  return (
    <Panel title={title} eyebrow="Explicit research submission" className="full">
      <details className="panel-body">
        <summary>Configure a bounded research request</summary>
        <Note>
          Runs are synchronous. A pending response means computation is in progress; no percentage
          or queue status is invented. This form never forwards a rejected order.
        </Note>
        <form
          key={`${context.ticker}-${ds}-${kind}-${text(dataset.data?.calculated_at, '')}-${text(seed.source_as_of, '')}`}
          onSubmit={(event) => {
            event.preventDefault();
            setError('');
            setPending(null);
            const form = new FormData(event.currentTarget);
            const raw = Object.fromEntries(form.entries());
            const parsed = controls.safeParse(raw);
            if (!parsed.success) {
              setError(parsed.error.issues.map((e) => e.message).join('; '));
              return;
            }
            try {
              const f = parsed.data;
              const tickers = f.tickers
                .split(',')
                .map((t) => t.trim().toUpperCase())
                .filter(Boolean);
              if (
                tickers.length > 10 ||
                new Set(tickers).size !== tickers.length ||
                tickers.some((t) => !/^([A-Z][A-Z0-9.]{0,11})$/.test(t))
              )
                throw new Error('Use 1–10 distinct supported ticker symbols.');
              const sourceAsOf = String(form.get('sourceAsOf'));
              if (
                !sourceAsOf ||
                !/(Z|[+-]\d{2}:\d{2})$/.test(sourceAsOf) ||
                !Number.isFinite(Date.parse(sourceAsOf))
              )
                throw new Error('Supply an aware source acquisition timestamp.');
              const effective = before(f.start);
              const costs = {
                fixed: '1',
                slippage_bps: String(form.get('slippage')),
                participation: '0.01',
                unknown_volume: 'reject',
              };
              const constraint = { cash_maximum: 1, concentration: f.concentration };
              let path = '',
                body: RecordData = {};
              if (kind === 'backtest') {
                path = '/api/backtest';
                body = {
                  tickers,
                  provider: context.provider,
                  start: f.start,
                  end: f.end,
                  source_as_of: sourceAsOf,
                  calendar: context.provider === 'synthetic' ? 'weekday' : 'XNYS',
                  information_policy: 'research_replay',
                  capital: String(f.capital),
                  strategy: { name: String(form.get('method')), rebalance: 'monthly' },
                  costs,
                  benchmarks: ['buy_hold', 'equal_weight'],
                  seconds: 30,
                };
              }
              if (kind === 'optimization') {
                path =
                  String(form.get('method')) === 'frontier'
                    ? '/api/portfolio/efficient-frontier'
                    : '/api/portfolio/optimize';
                const optimization = {
                  price_dataset_id: ds,
                  tickers,
                  history_start: f.start,
                  estimation_end: f.end,
                  decision_at: f.end + 'T23:59:59Z',
                  source_as_of: sourceAsOf,
                  information_policy: 'research_replay',
                  objective: {
                    method:
                      String(form.get('method')) === 'frontier'
                        ? 'mean_variance'
                        : String(form.get('method')),
                  },
                  constraints: constraint,
                  estimator: { minimum_observations: 20 },
                };
                body = path.endsWith('frontier')
                  ? { optimization, risk_aversions: [1, 3, 10, 30] }
                  : optimization;
              }
              if (kind === 'committee') {
                path = '/api/investment-committee/analyze';
                body = {
                  dataset_id: ds,
                  tickers,
                  history_start: text(dataset.data?.start_date, f.start),
                  start: f.start,
                  end: f.end,
                  source_as_of: sourceAsOf,
                  information_policy: 'retrospective',
                  policy: { effective_at: effective, minimum_independent_groups: 1 },
                  estimator: { minimum_observations: 20 },
                  constraints: { cash_maximum: 1 },
                  risk_policy: {
                    id: 'ui-fixed-' + f.start + '-' + Math.round(f.concentration * 10000),
                    version: '1',
                    effective_at: effective,
                    constraints: constraint,
                    estimator: { minimum_observations: 20 },
                    adjustment: 'scale_to_cash',
                  },
                  idempotency_key: 'ui-analysis-' + crypto.randomUUID(),
                  capital: f.capital,
                  costs,
                  seconds: 30,
                };
              }
              if (kind === 'strategy') {
                const dates = [
                  'train_start',
                  'train_end',
                  'validation_start',
                  'validation_end',
                  'test_start',
                  'test_end',
                ].map((k) => String(form.get(k)));
                if (
                  dates.some((d) => !/^\d{4}-\d{2}-\d{2}$/.test(d)) ||
                  !(
                    dates[0] <= dates[1] &&
                    dates[1] < dates[2] &&
                    dates[2] <= dates[3] &&
                    dates[3] < dates[4] &&
                    dates[4] <= dates[5]
                  )
                )
                  throw new Error(
                    'Train, validation and locked test windows must be chronological and disjoint.',
                  );
                const feature = String(form.get('feature'));
                if (
                  !Array.isArray(dataset.data?.columns) ||
                  !dataset.data.columns.includes(feature)
                )
                  throw new Error('Choose an actual feature column from the selected dataset.');
                path = '/api/strategies/discover';
                body = {
                  dataset_id: ds,
                  tickers,
                  source_as_of: sourceAsOf,
                  information_policy: 'retrospective',
                  windows: [
                    Object.fromEntries(
                      [
                        'train_start',
                        'train_end',
                        'validation_start',
                        'validation_end',
                        'test_start',
                        'test_end',
                      ].map((k, i) => [k, dates[i]]),
                    ),
                  ],
                  space: {
                    axes: [{ feature, operator: 'gt', thresholds: [0] }],
                    maximum_conditions: 1,
                    holdings: [5, 10],
                    exposure: f.concentration,
                  },
                  algorithm: String(form.get('algorithm')),
                  candidates: f.candidates,
                  capital: f.capital,
                  costs,
                  seconds: 30,
                  maximum_simulations: 500,
                  robustness: false,
                  holdout_history: 'previously_inspected',
                  idempotency_key: 'ui-discovery-' + crypto.randomUUID(),
                };
              }
              setPending({ path, body });
            } catch (e) {
              setError(e instanceof Error ? e.message : 'Invalid research request.');
            }
          }}
        >
          <div className="form-grid">
            <label>
              Universe (comma-separated tickers)
              <input name="tickers" required defaultValue={context.ticker} maxLength={130} />
            </label>
            {kind !== 'backtest' && (
              <label>
                Eligible feature dataset
                <select
                  aria-label={`${kind} feature dataset`}
                  value={ds}
                  onChange={(e) => setDataset(e.target.value)}
                >
                  {datasets.data?.items.map((d) => (
                    <option value={d.id} key={d.id}>
                      {text(d.configuration.provider)} · {d.id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {kind !== 'strategy' ? (
              <label>
                Evaluation start
                <input name="start" type="date" required defaultValue={defaultStart} />
              </label>
            ) : (
              <input type="hidden" name="start" value={defaultStart} />
            )}
            {kind !== 'strategy' ? (
              <label>
                Evaluation end
                <input name="end" type="date" required defaultValue={defaultEnd} />
              </label>
            ) : (
              <input type="hidden" name="end" value={defaultEnd} />
            )}
            <label>
              Source acquisition cutoff (UTC)
              <input
                name="sourceAsOf"
                required
                defaultValue={text(
                  seed.source_as_of,
                  Date.parse(text(dataset.data?.calculated_at, '')) > Date.parse(context.asOf)
                    ? text(dataset.data?.calculated_at)
                    : context.asOf,
                )}
                placeholder="2026-10-20T12:00:00Z"
              />
            </label>
            {kind !== 'optimization' ? (
              <label>
                Simulated capital (USD)
                <input name="capital" type="number" min={1} max={10000000} defaultValue={100000} />
              </label>
            ) : (
              <input type="hidden" name="capital" value="100000" />
            )}
            {kind !== 'backtest' ? (
              <label>
                Single-asset / discovery exposure cap (fraction)
                <input
                  name="concentration"
                  type="number"
                  min={0.01}
                  max={1}
                  step={0.01}
                  defaultValue={0.5}
                />
              </label>
            ) : (
              <input type="hidden" name="concentration" value="1" />
            )}
            {kind !== 'optimization' ? (
              <label>
                Slippage assumption (basis points)
                <input name="slippage" type="number" min={0} max={1000} step={1} defaultValue={5} />
              </label>
            ) : (
              <input type="hidden" name="slippage" value="5" />
            )}
            {kind !== 'strategy' && <input type="hidden" name="candidates" value="10" />}
            {(kind === 'backtest' || kind === 'optimization') && (
              <label>
                Supported method
                <select name="method" aria-label="Research method">
                  {(kind === 'backtest'
                    ? ['buy_hold', 'equal_weight', 'moving_average']
                    : [
                        'equal_weight',
                        'minimum_variance',
                        'mean_variance',
                        'maximum_sharpe',
                        'risk_parity',
                        'frontier',
                      ]
                  ).map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
            )}
            {kind === 'strategy' && (
              <>
                <label>
                  Search budget (maximum100 candidates)
                  <input type="number" name="candidates" min={1} max={100} defaultValue={10} />
                </label>
                <label>
                  Algorithm
                  <select name="algorithm">
                    <option value="random">Seeded random</option>
                    <option value="grid">Bounded grid</option>
                  </select>
                </label>
                <label>
                  Feature family / threshold rule
                  <select name="feature">
                    {Array.isArray(dataset.data?.columns) &&
                      dataset.data.columns.map((c) => <option key={String(c)}>{String(c)}</option>)}
                  </select>
                </label>
                {[
                  'train_start',
                  'train_end',
                  'validation_start',
                  'validation_end',
                  'test_start',
                  'test_end',
                ].map((k) => (
                  <label key={k}>
                    {k.replaceAll('_', ' ')}
                    <input type="date" name={k} required defaultValue={text(split[k], '')} />
                  </label>
                ))}
                <Note>
                  The test window stays locked; this operation searches training/validation only.
                  The period is marked previously inspected. No holdout evaluation is triggered
                  automatically.
                </Note>
              </>
            )}
          </div>
          {kind === 'backtest' && (
            <Note>
              This is an independent M4 baseline simulation, not an M9-approved order submission. It
              cannot execute a rejected committee allocation.
            </Note>
          )}
          {kind === 'committee' && (
            <Note>
              Analysis only: no M4 orders are generated. The fixed risk policy is opt-in here;
              unavailable agent evidence must abstain. Retrospective research timing is not proof of
              genuine historical publication.
            </Note>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <div className="button-row" style={{ marginTop: 18 }}>
            <button
              className="button"
              type="submit"
              disabled={
                job.isPending ||
                !context.ticker ||
                (kind !== 'backtest' && (!ds || dataset.isPending))
              }
            >
              Review request
            </button>
            {job.isPending && <span role="status">Research computation pending…</span>}
          </div>
        </form>
        {pending && (
          <>
            <JsonDetails value={pending} label="Exact bounded request — review before submission" />
            <ConfirmDialog
              title={title}
              description="Submit this reviewed configuration to the existing local quantitative service. This may create a saved experiment and consume local computation. It cannot enable real-money trading."
              onConfirm={() => job.mutate(pending)}
              disabled={job.isPending}
            >
              Submit reviewed research
            </ConfirmDialog>
          </>
        )}
        {job.isError && <Failure error={job.error} />}{' '}
        {job.isSuccess && (
          <div className="panel-body">
            <Badge tone="good">Backend response received</Badge>
            <JsonDetails value={job.data} label="Saved experiment response" />
            <Link
              className="text-button"
              href={`/${kind === 'backtest' ? 'backtesting' : kind === 'optimization' ? 'portfolio' : kind === 'strategy' ? 'strategies' : 'committee'}?${kind === 'optimization' ? 'optimization' : 'run'}=${text(job.data.id, '')}`}
            >
              Open saved result →
            </Link>
          </div>
        )}
      </details>
    </Panel>
  );
}
export function StressForm() {
  const [request, setRequest] = useState<RecordData | null>(null);
  const [error, setError] = useState('');
  const ctx = useResearch();
  const job = useMutation({
    mutationFn: (body: RecordData) => api('/api/risk/stress-test', objectSchema, { body }),
  });
  return (
    <Panel
      title="Hypothetical stress sandbox"
      eyebrow="Bounded user-supplied state · no orders"
      className="full"
    >
      <details className="panel-body">
        <summary>Configure a linear equity shock</summary>
        <Note>
          Provide an explicit standalone portfolio state. These inputs are user-supplied
          assumptions, not authenticated ledger prices. The scenario evaluates a shock; it cannot
          change holdings or override any risk decision. No covariance history is fabricated.
        </Note>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setError('');
            setRequest(null);
            const f = new FormData(e.currentTarget);
            const schema = z.object({
              ticker: z.string().regex(/^[A-Z][A-Z0-9.]{0,11}$/),
              price: z.coerce.number().positive().max(1000000),
              quantity: z.coerce.number().nonnegative().max(10000000),
              cash: z.coerce.number().nonnegative().max(100000000),
              shock: z.coerce.number().min(-1).max(3),
            });
            const parsed = schema.safeParse(Object.fromEntries(f.entries()));
            if (!parsed.success) {
              setError(parsed.error.issues.map((i) => i.message).join('; '));
              return;
            }
            const v = parsed.data,
              at = new Date().toISOString();
            setRequest({
              state: {
                portfolio_id: 'ui-standalone-stress',
                at,
                valuation_at: at,
                cash: String(v.cash),
                equity: String(v.cash + v.quantity * v.price),
                quantities: { [v.ticker]: String(v.quantity) },
                prices: [
                  {
                    ticker: v.ticker,
                    asset_id: v.ticker,
                    value: String(v.price),
                    observed_at: at,
                    available_at: at,
                    source: 'User-supplied stress assumption',
                    basis: 'raw',
                  },
                ],
                provenance: 'synthetic_fixture',
                calendar: 'weekday',
              },
              policy: {
                id: 'ui-shock-' + crypto.randomUUID(),
                version: '1',
                effective_at: at,
                scenarios: [
                  { id: 'user-hypothetical', version: '1', effective_at: at, broad_shock: v.shock },
                ],
              },
              idempotency_key: 'ui-stress-' + crypto.randomUUID(),
            });
          }}
        >
          <div className="form-grid">
            <label>
              Ticker
              <input name="ticker" required defaultValue={ctx.ticker} />
            </label>
            <label>
              Assumed raw USD price
              <input name="price" type="number" required min={0.01} step={0.01} />
            </label>
            <label>
              Assumed shares
              <input name="quantity" type="number" required min={0} step={1} />
            </label>
            <label>
              Assumed cash USD
              <input name="cash" type="number" required min={0} step={0.01} />
            </label>
            <label>
              Hypothetical return shock (fraction)
              <input name="shock" type="number" min={-1} max={3} step={0.01} defaultValue={-0.1} />
            </label>
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button className="button" style={{ marginTop: 16 }} type="submit">
            Review hypothetical scenario
          </button>
        </form>
        {request && (
          <>
            <JsonDetails value={request} label="Explicit assumptions and scenario" />
            <ConfirmDialog
              title="Calculate hypothetical shock"
              description="Save a standalone synthetic-assumption assessment. No trades are submitted. Other risk measures may correctly remain unavailable without return history."
              onConfirm={() => job.mutate(request)}
              disabled={job.isPending}
            >
              Calculate reviewed shock
            </ConfirmDialog>
          </>
        )}
        {job.isError && <Failure error={job.error} />}{' '}
        {job.isSuccess && (
          <div className="panel-body">
            <Badge tone="warn">Hypothetical, not a prediction</Badge>
            {records(record(record(job.data.payload).current).stress).map((s, i) => (
              <p key={i}>
                Scenario loss {money(finite(s.loss_currency))} ({percent(finite(s.loss_fraction))});
                equity after shock {money(finite(s.equity_after))}.
              </p>
            ))}
            <Note>
              Overall assessment status: {text(job.data.status)}. A calculated scenario is not
              approval to trade; absent covariance history remains unavailable.
            </Note>
            <JsonDetails value={job.data} label="Complete backend stress result" />
          </div>
        )}
      </details>
    </Panel>
  );
}
