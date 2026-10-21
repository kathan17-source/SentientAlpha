'use client';
import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ShieldCheck } from 'lucide-react';
import { useObject, usePage, useSelection } from '@/lib/hooks';
import { record, records, text, finite, money, percent, decimal, timestamp } from '@/lib/format';
import { entries } from '@/lib/series';
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
  statusTone,
} from '../shared/ui';
import { Correlation, SeriesChart } from '../shared/charts';
import { DataTable } from '../shared/table';
import { ReplayButton, StressForm } from '../shared/research-form';
export default function Risk() {
  const params = useSearchParams();
  const s = useSelection('committee', 'combined');
  const [chosenCommittee, setChosenCommittee] = useState<string | null>(null);
  const committee = chosenCommittee ?? params.get('committee') ?? s.id;
  const run = useObject(committee ? `/api/investment-committee/${committee}` : undefined);
  const config = record(record(run.data?.manifest).configuration);
  const portfolio = text(config.idempotency_key, '');
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState('current');
  const history = usePage(
    portfolio
      ? `/api/risk/history?portfolio_id=${encodeURIComponent(portfolio)}&limit=100&offset=${offset}`
      : undefined,
  );
  const rows = history.data?.items ?? [];
  const id =
    selected ??
    params.get('assessment') ??
    text(
      rows.find((r) => r.status === 'REJECTED')?.id,
      text(rows.find((r) => r.status === 'APPROVED_WITH_REDUCTION')?.id, text(rows.at(-1)?.id, '')),
    );
  const assessment = useObject(id ? `/api/risk/decisions/${id}` : undefined);
  const payload = record(assessment.data?.payload);
  let selectedData = record(payload[snapshot]);
  if (selectedData.same_as) selectedData = record(payload[text(selectedData.same_as)]);
  const exposure = record(selectedData.exposure),
    volatility = record(selectedData.volatility),
    tail = record(selectedData.tail),
    drawdown = record(selectedData.drawdown),
    control = record(payload.control);
  const policies = usePage(
    payload.policy_id
      ? `/api/risk/policies/${text(payload.policy_id)}?version=${encodeURIComponent(text(payload.policy_version))}`
      : undefined,
  );
  const violations = records(payload.violations);
  const timeline = rows.map((r) => {
    const p = record(r.payload),
      current = record(p.current);
    return {
      day: timestamp(r.at),
      volatility: finite(record(current.volatility).estimated_annual),
      var: finite(record(current.tail).var_loss_fraction),
      drawdown: finite(record(current.drawdown).current),
    };
  });
  return (
    <>
      <PageHeader
        title="Risk center"
        description="Independent numerical authority. Inspect what was proposed, what was permitted, and what actually reached the simulated ledger."
        action={
          <Badge tone="cyan">
            <ShieldCheck size={12} />
            Vetoes cannot be overridden
          </Badge>
        }
      />
      <RunSelect
        items={s.items}
        value={committee}
        onChange={(id) => {
          s.select(id);
          setChosenCommittee(id);
          setSelected(null);
          setOffset(0);
        }}
        next={s.catalog.data?.next_offset}
        onNext={s.next}
        label="Committee portfolio for risk history"
      />
      {history.isError ? (
        <Failure error={history.error} />
      ) : history.isPending && portfolio ? (
        <Loading />
      ) : !id ? (
        <Empty title="No M9 risk assessments in this selection">
          A prior M8 run may contain only the original M5 safeguards. Select an M9-enabled
          experiment; absence of a record is not an approval.
        </Empty>
      ) : assessment.isError ? (
        <Failure error={assessment.error} />
      ) : assessment.isPending ? (
        <Loading />
      ) : (
        <>
          <div className="run-select">
            <label>
              Risk assessment
              <select
                aria-label="Risk assessment"
                value={id}
                onChange={(e) => setSelected(e.target.value)}
              >
                {!rows.some((r) => r.id === id) && (
                  <option value={id}>{id.slice(0, 12)} · linked assessment</option>
                )}
                {rows.map((r) => (
                  <option key={text(r.id)} value={text(r.id)}>
                    {timestamp(r.at)} · {text(r.phase)} · {text(r.status)}
                  </option>
                ))}
              </select>
            </label>
            <ReplayButton path={`/api/risk/decisions/${id}/replay`} />
          </div>
          <div className="button-row" style={{ marginBottom: 18 }}>
            <Badge tone={statusTone(assessment.data.status)}>{text(assessment.data.status)}</Badge>
            <Badge>{text(assessment.data.phase)}</Badge>
            <Badge tone={control.state === 'HALTED' ? 'bad' : 'neutral'}>
              Risk state: {text(control.state)}
            </Badge>
            <Badge>
              Policy {text(payload.policy_id)} / {text(payload.policy_version)}
            </Badge>
          </div>
          <div className="tabs" aria-label="Risk snapshot">
            {['current', 'proposed', 'approved'].map((v) => (
              <button key={v} aria-pressed={snapshot === v} onClick={() => setSnapshot(v)}>
                {v === 'current'
                  ? 'Actual current state'
                  : v === 'proposed'
                    ? 'Original proposed state'
                    : 'Risk-approved state'}
              </button>
            ))}
          </div>
          {!Object.keys(selectedData).length ? (
            <Empty title="No approved risk snapshot">
              A rejected proposal has no approved allocation. The UI does not substitute the
              original target.
            </Empty>
          ) : (
            <>
              <div className="metrics">
                <Metric
                  label="Estimated annual volatility"
                  value={percent(finite(volatility.estimated_annual))}
                  detail={text(volatility.status)}
                />
                <Metric
                  label={`${percent(finite(tail.confidence), 0)} one-session VaR`}
                  value={percent(finite(tail.var_loss_fraction))}
                  detail={`${money(finite(tail.var_currency))} · positive means loss`}
                />
                <Metric
                  label="Expected shortfall / CVaR"
                  value={percent(finite(tail.cvar_loss_fraction))}
                  detail={`${money(finite(tail.cvar_currency))} · upper tail mean`}
                />
                <Metric
                  label="Current realized drawdown"
                  value={percent(finite(drawdown.current))}
                  detail={`Observed maximum ${percent(finite(drawdown.maximum_observed))}`}
                />
              </div>
              {tail.status === 'INSUFFICIENT_TAIL_DATA' && (
                <div className="failure" role="status">
                  <ShieldCheck size={18} />
                  <div>
                    <strong>Insufficient tail history</strong>
                    <p>
                      {decimal(finite(tail.samples), 0)} eligible returns;{' '}
                      {decimal(finite(tail.effective_tail_observations), 2)} effective tail
                      observations. Numerical estimates are not reliable coverage validation.
                      Required controls must fail closed.
                    </p>
                  </div>
                </div>
              )}
              <div className="grid-two">
                <Panel title="Exposure & concentration" eyebrow={`${snapshot} snapshot`}>
                  <dl className="detail-list panel-body">
                    {['gross', 'net', 'cash_weight', 'maximum_weight', 'top_five'].map((k) => (
                      <span key={k} style={{ display: 'contents' }}>
                        <dt>{k.replaceAll('_', ' ')}</dt>
                        <dd>{percent(finite(exposure[k]))}</dd>
                      </span>
                    ))}
                    <dt>HHI, equity weights</dt>
                    <dd>{decimal(finite(exposure.hhi_equity_weights), 4)}</dd>
                    <dt>Effective invested holdings</dt>
                    <dd>{decimal(finite(exposure.effective_holdings_invested))}</dd>
                    <dt>Benchmark beta</dt>
                    <dd>{decimal(finite(volatility.benchmark_beta), 3)}</dd>
                  </dl>
                </Panel>
                <Panel title="Security risk contribution" eyebrow="Annual component volatility">
                  <SeriesChart
                    label="Risk contributions by security"
                    unit="percent"
                    kind="bar"
                    x="asset"
                    data={entries(volatility.component_volatility)}
                    series={[{ key: 'value', label: 'Component volatility' }]}
                  />
                </Panel>
              </div>
              <div className="grid-two">
                <Panel title="Sector exposure">
                  <SeriesChart
                    label="Risk snapshot sector exposure"
                    unit="percent"
                    kind="bar"
                    x="asset"
                    data={entries(exposure.sectors)}
                    series={[{ key: 'value', label: 'Sector weight' }]}
                  />
                </Panel>
                <Panel title="Correlation & conditioning">
                  <Correlation matrix={volatility.correlation} names={volatility.asset_order} />
                  <div className="panel-body">
                    <Badge tone={volatility.raw_covariance_reliable ? 'neutral' : 'warn'}>
                      {volatility.raw_covariance_reliable
                        ? 'Raw support passes configured condition check'
                        : 'Raw covariance reliability unverified'}
                    </Badge>
                    <Note>
                      Regularization does not prove that a singular or nearly singular risk model is
                      reliable.
                    </Note>
                  </div>
                </Panel>
              </div>
              <Panel
                title="Historical risk metric chronology"
                eyebrow="Actual current state at each saved event"
              >
                <SeriesChart
                  label="Stored volatility, VaR and drawdown history"
                  data={timeline}
                  unit="percent"
                  series={[
                    { key: 'volatility', label: 'Annual volatility' },
                    { key: 'var', label: 'One-session VaR' },
                    { key: 'drawdown', label: 'Realized drawdown' },
                  ]}
                />
                <div className="panel-body">
                  <Note>
                    These horizons differ; the legend preserves their definitions. Events include
                    intraday valuations, not only independent daily observations.
                  </Note>
                </div>
              </Panel>
              <div className="grid-two" style={{ marginTop: 20 }}>
                <Panel title="Daily-volume liquidity proxies">
                  <DataTable
                    label="Liquidity evidence"
                    rows={entries(selectedData.liquidity).map((r) => ({
                      ticker: r.asset,
                      ...record(r.value),
                    }))}
                    columns={[
                      { key: 'ticker', label: 'Asset' },
                      { key: 'status', label: 'Coverage' },
                      {
                        key: 'average_volume',
                        label: 'ADV shares',
                        render: (v) => decimal(finite(v), 0),
                      },
                      {
                        key: 'average_dollar_volume',
                        label: 'Dollar volume',
                        render: (v) => money(finite(v), 0),
                      },
                      { key: 'observations', label: 'Observations' },
                    ]}
                  />
                  <div className="panel-body">
                    <Note>
                      Daily-volume proxies do not measure order-book depth, intraday impact, or a
                      guaranteed liquidation time.
                    </Note>
                  </div>
                </Panel>
                <Panel
                  title="Stress scenarios"
                  eyebrow="Linear equity revaluation · not predictions"
                >
                  {records(selectedData.stress).length ? (
                    records(selectedData.stress).map((r, i) => (
                      <div key={i}>
                        <div className="panel-body">
                          <Badge tone={r.kind === 'hypothetical' ? 'warn' : 'neutral'}>
                            {text(r.kind)}
                          </Badge>
                          <h3 style={{ marginTop: 10 }}>{text(r.id)}</h3>
                          <p>
                            Scenario loss: {money(finite(r.loss_currency))} /{' '}
                            {percent(finite(r.loss_fraction))}
                          </p>
                        </div>
                        <SeriesChart
                          label={`Scenario ${text(r.id)} asset loss attribution`}
                          kind="bar"
                          x="asset"
                          data={entries(r.asset_loss_contributions)}
                          series={[
                            { key: 'value', label: 'Hypothetical or historical-window loss USD' },
                          ]}
                        />
                      </div>
                    ))
                  ) : (
                    <Empty title="No scenarios configured for this policy" />
                  )}
                </Panel>
              </div>
            </>
          )}
          <Panel
            title="Risk decision inspector"
            eyebrow="Proposal → policy → authority → actual execution"
          >
            <div className="panel-body">
              <Note>
                {payload.executable === true
                  ? 'Only this assessed plan is executable, subject to a fresh fill-time check. Approval is not permission to bypass future policy checks.'
                  : 'No executable plan was approved by this assessment. No override or order-forwarding control exists in the interface.'}
              </Note>
            </div>
            <DataTable
              label="Risk limit violations"
              rows={violations}
              columns={[
                { key: 'metric', label: 'Risk metric' },
                {
                  key: 'observed',
                  label: 'Observed',
                  render: (v) => (typeof v === 'number' ? decimal(v, 6) : text(v)),
                },
                {
                  key: 'limit',
                  label: 'Limit',
                  render: (v) => (typeof v === 'number' ? decimal(v, 6) : text(v)),
                },
                { key: 'kind', label: 'Violation type' },
                { key: 'explanation', label: 'Explanation' },
              ]}
            />
            <JsonDetails label="Original quantities / target proposal" value={payload.proposal} />
            <JsonDetails label="Applicable immutable policy" value={policies.data?.items} />
            <JsonDetails label="Risk-approved plan (null on veto)" value={payload.approved_plan} />
            <JsonDetails
              label="State transitions, reductions & numerical methodology"
              value={{
                control: payload.control,
                adjustment_attempts: payload.adjustment_attempts,
                tail: selectedData.tail,
                methodology: payload.methodology,
              }}
            />
            <div className="panel-body button-row">
              {!!assessment.data.backtest_id && (
                <Link
                  className="button subtle"
                  href={`/backtesting?run=${text(assessment.data.backtest_id)}`}
                >
                  Inspect actual M4 fills & holdings →
                </Link>
              )}
              {!!assessment.data.committee_id && (
                <Link
                  className="button subtle"
                  href={`/committee?run=${text(assessment.data.committee_id)}`}
                >
                  Original committee evidence →
                </Link>
              )}
            </div>
          </Panel>
          <Panel title="Risk event history" className="full">
            <DataTable
              label="Risk event chronology"
              rows={rows}
              columns={[
                { key: 'at', label: 'Assessment time', render: (v) => timestamp(v) },
                { key: 'phase', label: 'Phase' },
                {
                  key: 'status',
                  label: 'Decision',
                  render: (v) => <Badge tone={statusTone(v)}>{text(v)}</Badge>,
                },
                { key: 'id', label: 'Assessment', render: (v) => text(v).slice(0, 12) },
              ]}
              onSelect={(r) => setSelected(text(r.id))}
            />
            <div className="panel-body button-row">
              {offset > 0 && (
                <button
                  className="button subtle"
                  onClick={() => setOffset((o) => Math.max(0, o - 100))}
                >
                  Previous events
                </button>
              )}
              {history.data?.next_offset != null && (
                <button
                  className="button subtle"
                  onClick={() => setOffset(history.data!.next_offset!)}
                >
                  Later events
                </button>
              )}
            </div>
          </Panel>
          <Provenance
            value={{
              assessment_id: id,
              policy_key: assessment.data.policy_key,
              at: assessment.data.at,
              phase: assessment.data.phase,
              portfolio_id: assessment.data.portfolio_id,
            }}
          />
        </>
      )}
      <StressForm />
    </>
  );
}
