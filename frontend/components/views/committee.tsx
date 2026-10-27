'use client';
import { useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Network, ShieldCheck } from 'lucide-react';
import { useSelection, useObject, usePage } from '@/lib/hooks';
import { record, records, text, finite, percent, decimal, timestamp } from '@/lib/format';
import { entries } from '@/lib/series';
import { heuristicReasoning } from '@/lib/committee-format';
import {
  Badge,
  Empty,
  Failure,
  JsonDetails,
  Loading,
  Note,
  PageHeader,
  Panel,
  Provenance,
  RunSelect,
  statusTone,
} from '../shared/ui';
import { DataTable } from '../shared/table';
import { ResearchForm } from '../shared/research-form';
export default function Committee() {
  const s = useSelection('committee', 'm8_baseline');
  const [offset, setOffset] = useState(0);
  const [index, setIndex] = useState(0);
  const run = useObject(s.id ? `/api/investment-committee/${s.id}` : undefined);
  const decisions = usePage(
    s.id ? `/api/investment-committee/${s.id}/decisions?limit=10&offset=${offset}` : undefined,
  );
  const d = decisions.data?.items[index] ?? decisions.data?.items[0];
  const recommendations = records(d?.recommendations);
  const allocation = record(d?.allocation);
  const proposal = record(allocation.proposal);
  const m9 = record(d?.m9_risk);
  const config = record(record(run.data?.manifest).configuration);
  const weightRows = Array.from(
    new Set([
      ...Object.keys(record(proposal.weights)),
      ...Object.keys(record(allocation.final_allocation)),
    ]),
  ).map((t) => ({
    ticker: t,
    proposed: record(proposal.weights)[t],
    approved: record(allocation.final_allocation)[t],
    actual: record(d?.actual_weights_before)[t],
  }));
  return (
    <>
      <PageHeader
        title="Investment committee"
        description="Inspect the evidence behind each recommendation. Follow the proposal through independent risk review and simulated execution."
        action={
          <Badge tone="cyan">
            <Network size={12} />
            Evidence, not role-play
          </Badge>
        }
      />
      <RunSelect
        items={s.items}
        value={s.id}
        onChange={(id) => {
          s.select(id);
          setOffset(0);
          setIndex(0);
        }}
        next={s.catalog.data?.next_offset}
        onNext={s.next}
      />
      {s.catalog.isError ? (
        <Failure error={s.catalog.error} />
      ) : s.catalog.isPending ? (
        <Loading />
      ) : !s.id ? (
        <Empty title="No saved committee run" />
      ) : run.isError ? (
        <Failure error={run.error} />
      ) : (
        <>
          <div className="decision-flow">
            {[
              'Research evidence',
              'Agent recommendations',
              'Evidence aggregation',
              'M5 proposal',
              'Independent risk review',
              'M4 simulation',
            ].map((step, i) => (
              <span key={step} style={{ display: 'contents' }}>
                <span className="flow-step">{step}</span>
                {i < 5 && <ArrowRight size={12} color="#8ca5b7" />}
              </span>
            ))}
          </div>
          <div className="run-select">
            <label>
              Retained decision
              <select
                aria-label="Retained decision"
                value={index}
                onChange={(e) => setIndex(Number(e.target.value))}
              >
                {decisions.data?.items.map((r, i) => (
                  <option key={i} value={i}>
                    {text(r.day)} · {text(r.final_action)}
                  </option>
                ))}
              </select>
            </label>
            {offset > 0 && (
              <button
                className="button subtle"
                onClick={() => {
                  setOffset((o) => Math.max(0, o - 10));
                  setIndex(0);
                }}
              >
                Previous decisions
              </button>
            )}
            {decisions.data?.next_offset != null && (
              <button
                className="button subtle"
                onClick={() => {
                  setOffset(decisions.data!.next_offset!);
                  setIndex(0);
                }}
              >
                Later decisions
              </button>
            )}
          </div>
          {decisions.isPending ? (
            <Loading />
          ) : decisions.isError ? (
            <Failure error={decisions.error} />
          ) : !d ? (
            <Empty title="No eligible committee decisions" />
          ) : (
            <>
              <Panel
                title="Specialized research agents"
                eyebrow={`Decision cutoff · ${timestamp(d.decision_at)}`}
                action={<Badge tone={statusTone(d.final_action)}>{text(d.final_action)}</Badge>}
              >
                <div className="agent-grid">
                  {recommendations.map((a, i) => (
                    <article className="agent-card" key={`${a.agent_id}-${a.ticker}-${i}`}>
                      <header>
                        <h3 className="agent-name">
                          {text(a.agent_id)}{' '}
                          <span className="subtle-label">/ {text(a.ticker)}</span>
                        </h3>
                        <Badge tone={statusTone(a.status)}>{text(a.status)}</Badge>
                      </header>
                      <div className="agent-signal">
                        {finite(a.signal) === null ? 'Abstained' : decimal(finite(a.signal), 3)}
                      </div>
                      <p>{heuristicReasoning(a)}</p>
                      <dl>
                        <dt>Interpretation</dt>
                        <dd>{text(a.interpretation)}</dd>
                        <dt>Heuristic strength</dt>
                        <dd>{decimal(finite(a.strength), 3)}</dd>
                        <dt>Evidence coverage</dt>
                        <dd>{percent(finite(a.coverage))}</dd>
                        <dt>Version</dt>
                        <dd>{text(a.agent_version)}</dd>
                      </dl>
                      <JsonDetails
                        label="Evidence, clocks & dependencies"
                        value={{
                          reasoning: a.reasoning,
                          evidence: a.evidence,
                          diagnostics: a.diagnostics,
                          limitations: a.limitations,
                          data_cutoff: a.data_cutoff,
                          prediction: a.prediction,
                          prediction_units: a.prediction_units,
                        }}
                      />
                    </article>
                  ))}
                </div>
              </Panel>
              <Note>
                Signal strength is a bounded heuristic, not calibrated confidence or expected
                return. Missing fundamental, macro, or sentiment history produces explicit
                abstention.
              </Note>
              <div className="grid-two">
                <Panel
                  title="Portfolio proposal & approval"
                  eyebrow="Weights · fractions of equity"
                >
                  <DataTable
                    label="Proposed versus approved weights"
                    filterable={false}
                    rows={weightRows}
                    columns={[
                      { key: 'ticker', label: 'Asset' },
                      { key: 'proposed', label: 'M5 proposal', render: (v) => percent(finite(v)) },
                      {
                        key: 'approved',
                        label: 'Risk-approved target',
                        render: (v) => percent(finite(v)),
                      },
                      {
                        key: 'actual',
                        label: 'Actual before decision',
                        render: (v) => percent(finite(v)),
                      },
                    ]}
                  />
                  <div className="panel-body">
                    <Link className="text-button" href={`/portfolio?run=${s.id}`}>
                      Inspect actual post-execution holdings →
                    </Link>
                  </div>
                  <JsonDetails label="Optimization & risk review" value={allocation} />
                </Panel>
                <Panel
                  title="Independent risk authority"
                  eyebrow="No override permitted"
                  action={<ShieldCheck size={16} color="#64c9c3" />}
                >
                  <div className="panel-body">
                    <Badge tone={statusTone(m9.status ?? record(allocation.risk_review).status)}>
                      {text(m9.status ?? record(allocation.risk_review).status)}
                    </Badge>
                    <Note>
                      {Object.keys(m9).length
                        ? 'M9 assessed this proposal. Only an approved plan can proceed, subject to a fresh fill-time check.'
                        : 'This run contains the original M8/M5 risk checks. Advanced M9 coverage is not implied.'}
                    </Note>
                    <Link className="button subtle" href={`/risk?committee=${s.id}`}>
                      Open risk decision inspector →
                    </Link>
                  </div>
                  <JsonDetails
                    label="Risk decision record"
                    value={Object.keys(m9).length ? m9 : allocation.risk_review}
                  />
                </Panel>
              </div>
              <Panel title="Aggregation & disagreement" eyebrow="Dependency-aware evidence groups">
                <DataTable
                  label="Committee aggregation"
                  rows={entries(d.aggregation).map((r) => ({
                    ticker: r.asset,
                    ...record(r.value),
                  }))}
                  columns={[
                    { key: 'ticker', label: 'Security' },
                    { key: 'participating', label: 'Participating' },
                    { key: 'abstaining', label: 'Abstaining' },
                    { key: 'independent_groups', label: 'Independent groups' },
                    {
                      key: 'disagreement',
                      label: 'Disagreement',
                      render: (v) => (v === true ? 'Yes' : 'No'),
                    },
                    {
                      key: 'aggregate_heuristic',
                      label: 'Aggregate signal',
                      render: (v) => decimal(finite(v), 3),
                    },
                  ]}
                />
                <JsonDetails
                  label="Group dependencies and exact aggregation"
                  value={d.aggregation}
                />
              </Panel>
            </>
          )}
          <Provenance value={run.data?.manifest} />
        </>
      )}
      <ResearchForm kind="committee" seed={config} />
    </>
  );
}
