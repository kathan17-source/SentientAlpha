'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useCatalog, useObject, usePage } from '@/lib/hooks';
import type { CatalogKind } from '@/lib/api/client';
import { record, text, timestamp } from '@/lib/format';
import {
  Badge,
  Empty,
  Failure,
  JsonDetails,
  Note,
  PageHeader,
  Panel,
  Provenance,
  statusTone,
} from '../shared/ui';
import { DataTable } from '../shared/table';
import { ReplayButton } from '../shared/research-form';
const labels: Record<CatalogKind, string> = {
  backtest: 'Backtests',
  optimization: 'Optimizations',
  ml: 'ML experiments',
  strategy: 'Strategy discovery',
  committee: 'Committee decisions',
  features: 'Feature datasets',
  sentiment: 'Sentiment runs',
};
const routes: Partial<Record<CatalogKind, string>> = {
  backtest: '/backtesting',
  optimization: '/portfolio',
  ml: '/ml',
  strategy: '/strategies',
  committee: '/committee',
};
export default function Experiments() {
  const [kind, setKind] = useState<CatalogKind>('committee');
  const [offset, setOffset] = useState(0);
  const [id, setId] = useState<string | null>(null);
  const catalog = useCatalog(kind, offset);
  const selected = catalog.data?.items.find((r) => r.id === id);
  const detail = useObject(selected?.links.detail);
  const [riskOffset, setRiskOffset] = useState(0);
  const risk = usePage(`/api/risk/history?limit=20&offset=${riskOffset}`);
  const replayPath =
    selected && ['backtest', 'optimization', 'ml', 'strategy', 'committee'].includes(kind)
      ? selected.links.detail + '/replay'
      : undefined;
  return (
    <>
      <PageHeader
        title="Experiment history"
        description="Trace each result to a saved configuration, data version, and reproducible research manifest. Failed and insufficient-data runs remain visible."
      />
      <div className="tabs" aria-label="Research registry">
        {Object.entries(labels).map(([key, label]) => (
          <button
            key={key}
            aria-pressed={kind === key}
            onClick={() => {
              setKind(key as CatalogKind);
              setId(null);
              setOffset(0);
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <Panel title={labels[kind]} eyebrow="Read-only registry · actual persisted IDs">
        {catalog.isError ? (
          <Failure error={catalog.error} retry={() => catalog.refetch()} />
        ) : (
          <DataTable
            label={`${labels[kind]} registry`}
            rows={catalog.data?.items ?? []}
            columns={[
              {
                key: 'id',
                label: 'Run ID',
                render: (v) => <span className="mono">{text(v).slice(0, 12)}</span>,
              },
              { key: 'label', label: 'Research configuration' },
              {
                key: 'status',
                label: 'Status',
                render: (v) => <Badge tone={statusTone(v)}>{text(v)}</Badge>,
              },
              { key: 'created_at', label: 'Actually recorded', render: (v) => timestamp(v) },
            ]}
            onSelect={(r) => setId(text(r.id))}
          />
        )}
        <div className="button-row panel-body">
          {offset > 0 && (
            <button className="button subtle" onClick={() => setOffset((o) => Math.max(0, o - 30))}>
              Previous runs
            </button>
          )}
          {catalog.data?.next_offset != null && (
            <button className="button subtle" onClick={() => setOffset(catalog.data!.next_offset!)}>
              More runs
            </button>
          )}
        </div>
      </Panel>
      {selected && (
        <Panel
          title="Saved experiment inspector"
          eyebrow={`${selected.kind} / ${selected.id}`}
          className="full"
        >
          <div className="button-row panel-body">
            {routes[kind] && (
              <Link
                className="button"
                href={`${routes[kind]}?${kind === 'optimization' ? 'optimization' : 'run'}=${selected.id}`}
              >
                Open analytical workspace →
              </Link>
            )}
            {replayPath && <ReplayButton path={replayPath} />}
          </div>
          {detail.isError ? (
            <Failure error={detail.error} />
          ) : (
            <>
              <JsonDetails
                value={detail.data}
                label="Exact saved manifest and public research response"
              />
              <Provenance
                value={{ ...selected, limitations: record(detail.data?.manifest).limitations }}
              />
            </>
          )}
          <Note>
            A saved manifest is not a successful replay. The replay control reports the actual
            response and preserves build/source mismatch failures.
          </Note>
        </Panel>
      )}
      <Panel
        title="Independent risk assessments"
        eyebrow="Linked decisions and standalone numerical evaluations"
        className="full"
      >
        {risk.isError ? (
          <Failure error={risk.error} />
        ) : risk.data?.items.length ? (
          <DataTable
            label="Risk assessment registry"
            rows={risk.data.items}
            columns={[
              {
                key: 'id',
                label: 'Assessment ID',
                render: (v) => (
                  <Link className="text-button" href={`/risk?assessment=${text(v)}`}>
                    {text(v).slice(0, 12)} ↗
                  </Link>
                ),
              },
              { key: 'portfolio_id', label: 'Portfolio' },
              { key: 'at', label: 'Valuation time', render: (v) => timestamp(v) },
              { key: 'phase', label: 'Phase' },
              {
                key: 'status',
                label: 'Risk decision',
                render: (v) => <Badge tone={statusTone(v)}>{text(v)}</Badge>,
              },
            ]}
          />
        ) : (
          <Empty title="No retained risk assessments" />
        )}
        <div className="panel-body button-row">
          {riskOffset > 0 && (
            <button
              className="button subtle"
              onClick={() => setRiskOffset((o) => Math.max(0, o - 20))}
            >
              Previous assessments
            </button>
          )}
          {risk.data?.next_offset != null && (
            <button
              className="button subtle"
              onClick={() => setRiskOffset(risk.data!.next_offset!)}
            >
              More assessments
            </button>
          )}
        </div>
      </Panel>
    </>
  );
}
