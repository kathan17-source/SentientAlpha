'use client';
import { useState } from 'react';
import { useObject, usePage, useSelection } from '@/lib/hooks';
import { record, text, finite, percent, decimal } from '@/lib/format';
import {
  Badge,
  Empty,
  Failure,
  JsonDetails,
  Note,
  PageHeader,
  Panel,
  Provenance,
  RunSelect,
  statusTone,
} from '../shared/ui';
import { DataTable } from '../shared/table';
import { ResearchForm, ReplayButton } from '../shared/research-form';
export default function Strategies() {
  const s = useSelection('strategy');
  const [fold, setFold] = useState(0);
  const [offset, setOffset] = useState(0);
  const [candidateId, setCandidate] = useState<string | null>(null);
  const run = useObject(s.id ? `/api/strategies/discovery/${s.id}` : undefined);
  const ranked = usePage(s.id ? `/api/strategies/leaderboard?run_id=${s.id}&limit=100` : undefined);
  const history = useObject(
    s.id
      ? `/api/strategies/discovery/${s.id}/history?fold=${fold}&limit=100&offset=${offset}`
      : undefined,
  );
  const candidates = usePage(
    s.id ? `/api/strategies?run_id=${s.id}&limit=100&offset=${offset}` : undefined,
  );
  const id =
    candidateId ?? text(ranked.data?.items[0]?.id, text(candidates.data?.items[0]?.id, ''));
  const candidate = useObject(id ? `/api/strategies/${id}` : undefined);
  const robust = useObject(id ? `/api/strategies/${id}/robustness` : undefined);
  const trades = useObject(id ? `/api/strategies/${id}/trades` : undefined);
  const performance = record(candidate.data?.performance);
  const rows =
    ranked.data?.items
      .filter((r) => r.fold === fold)
      .map((r, i) => ({
        ...r,
        rank: i + 1,
        validation_return: record(record(record(r.performance).validation).metrics).total_return,
        validation_score: record(record(record(r.performance).validation).fitness).score,
        complexity: record(record(r.performance).complexity).normalized,
        turnover: record(record(record(r.performance).validation).metrics).turnover,
      })) ?? [];
  return (
    <>
      <PageHeader
        title="Strategy lab"
        description="Explore validation-ranked rules, rejected candidates, and locked out-of-sample results. Search is numerical, bounded, and reproducible."
      />
      <RunSelect
        items={s.items}
        value={s.id}
        onChange={(id) => {
          s.select(id);
          setCandidate(null);
          setOffset(0);
          setFold(0);
        }}
        next={s.catalog.data?.next_offset}
        onNext={s.next}
      />
      {s.catalog.isError ? (
        <Failure error={s.catalog.error} />
      ) : !s.id ? (
        <Empty title="No discovery experiment saved" />
      ) : run.isError ? (
        <Failure error={run.error} />
      ) : (
        <>
          <div className="button-row" style={{ marginBottom: 18 }}>
            <label className="field">
              Fold
              <input
                type="number"
                aria-label="Discovery fold"
                min={0}
                max={7}
                value={fold}
                onChange={(e) => setFold(Number(e.target.value))}
              />
            </label>
            <ReplayButton path={`/api/strategies/discovery/${s.id}/replay`} />
            <Badge tone={statusTone(run.data?.status)}>{text(run.data?.status)}</Badge>
          </div>
          <Panel
            title="Validation-ranked leaderboard"
            eyebrow="Backend ranking · final test returns never determine order"
          >
            {ranked.isError ? (
              <Failure error={ranked.error} />
            ) : rows.length ? (
              <DataTable
                label="Validation-ranked strategy leaderboard"
                rows={rows}
                columns={[
                  { key: 'rank', label: 'Validation rank' },
                  { key: 'rule', label: 'Readable rule' },
                  {
                    key: 'validation_score',
                    label: 'Validation fitness',
                    render: (v) => decimal(finite(v), 4),
                  },
                  {
                    key: 'validation_return',
                    label: 'Validation return',
                    render: (v) => percent(finite(v)),
                  },
                  { key: 'complexity', label: 'Complexity', render: (v) => decimal(finite(v), 3) },
                  { key: 'turnover', label: 'Turnover', render: (v) => decimal(finite(v), 3) },
                  {
                    key: 'selected',
                    label: 'Locked selection',
                    render: (v) => (
                      <Badge tone={v ? 'cyan' : 'neutral'}>{v ? 'Selected' : 'Candidate'}</Badge>
                    ),
                  },
                ]}
                onSelect={(r) => setCandidate(text(r.id))}
              />
            ) : (
              <Empty title="No robust eligible candidates">
                This is a valid research outcome. Inspect rejected rules and their actual validation
                failures rather than inventing a winning strategy.
              </Empty>
            )}
          </Panel>
          <Panel
            title="All retained candidates"
            eyebrow="Including rejected and unsuccessful rules"
            className="full"
          >
            {candidates.isError ? (
              <Failure error={candidates.error} />
            ) : (
              <DataTable
                label="All strategy candidates"
                rows={candidates.data?.items ?? []}
                columns={[
                  { key: 'id', label: 'Candidate', render: (v) => text(v).slice(0, 8) },
                  {
                    key: 'status',
                    label: 'Status',
                    render: (v) => <Badge tone={statusTone(v)}>{text(v)}</Badge>,
                  },
                  { key: 'rule', label: 'Entry conditions' },
                  { key: 'fold', label: 'Fold' },
                ]}
                onSelect={(r) => setCandidate(text(r.id))}
              />
            )}
            <div className="panel-body button-row">
              {offset > 0 && (
                <button
                  className="button subtle"
                  onClick={() => setOffset((o) => Math.max(0, o - 100))}
                >
                  Previous candidates
                </button>
              )}
              {(candidates.data?.items.length ?? 0) === 100 && (
                <button className="button subtle" onClick={() => setOffset((o) => o + 100)}>
                  More candidates
                </button>
              )}
            </div>
          </Panel>
          {id && (
            <Panel title="Strategy detail" eyebrow={id} className="full">
              {candidate.isError ? (
                <Failure error={candidate.error} />
              ) : (
                <>
                  <div className="panel-body">
                    <h3>{text(candidate.data?.rule)}</h3>
                    <Note>
                      Feature dependencies:{' '}
                      {Array.isArray(candidate.data?.requirements)
                        ? candidate.data.requirements.join(', ')
                        : 'Unavailable'}
                      . Conditions are displayed as passive text, never executed in the browser.
                    </Note>
                    <Badge tone={statusTone(candidate.data?.status)}>
                      {text(candidate.data?.status)}
                    </Badge>
                  </div>
                  <DataTable
                    label="Separated strategy evaluation windows"
                    rows={['train', 'validation', 'test'].map((window) => ({
                      window,
                      ...record(record(performance[window]).metrics),
                      eligible: record(record(performance[window]).fitness).eligible,
                    }))}
                    columns={[
                      { key: 'window', label: 'Research split' },
                      { key: 'total_return', label: 'Return', render: (v) => percent(finite(v)) },
                      {
                        key: 'maximum_drawdown',
                        label: 'Maximum drawdown',
                        render: (v) => percent(finite(v)),
                      },
                      { key: 'turnover', label: 'Turnover', render: (v) => decimal(finite(v), 3) },
                      { key: 'trade_count', label: 'Trades', render: (v) => decimal(finite(v), 0) },
                      {
                        key: 'eligible',
                        label: 'Fitness eligibility',
                        render: (v) => (v == null ? 'Not evaluated' : v ? 'Eligible' : 'Rejected'),
                      },
                    ]}
                  />
                  <JsonDetails
                    label="Safe machine-readable definition and parameters"
                    value={candidate.data?.definition}
                  />
                  <JsonDetails label="Research failures, costs & complexity" value={performance} />
                  {robust.isError ? (
                    <Failure error={robust.error} />
                  ) : (
                    <JsonDetails label="Stored robustness evidence" value={robust.data} />
                  )}{' '}
                  {trades.isError ? (
                    <Failure error={trades.error} />
                  ) : (
                    <JsonDetails
                      label="Actual retained strategy trade records"
                      value={trades.data}
                    />
                  )}
                </>
              )}
            </Panel>
          )}
          <JsonDetails label="Bounded search history" value={history.data} />
          <Provenance value={run.data?.manifest} />
          <Note>
            Train and validation are separate from locked test outcomes. This interface does not
            trigger final holdout evaluation, tune on holdout returns, or claim historical alpha.
          </Note>
        </>
      )}
      <ResearchForm kind="strategy" seed={record(record(run.data?.manifest).configuration)} />
    </>
  );
}
