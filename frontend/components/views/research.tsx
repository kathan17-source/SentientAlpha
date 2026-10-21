'use client';
import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useResearch } from '../shell';
import { useCatalog, useObject, useArray, usePage } from '@/lib/hooks';
import { queryString } from '@/lib/api/client';
import { records, text, finite, money, decimal, timestamp, type RecordData } from '@/lib/format';
import {
  Badge,
  Empty,
  Failure,
  JsonDetails,
  Note,
  PageHeader,
  Panel,
  Provenance,
} from '../shared/ui';
import { SeriesChart } from '../shared/charts';
import { DataTable } from '../shared/table';
export default function Research() {
  const ctx = useResearch(),
    params = useSearchParams();
  const ticker = params.get('ticker') ?? ctx.ticker;
  const [cutoff, setCutoff] = useState<string | null>(null);
  const asOf = cutoff ?? ctx.asOf;
  const [selectedCell, setCell] = useState<RecordData | null>(null);
  const [ds, setDataset] = useState<string | null>(null);
  const catalog = useCatalog('features');
  const datasetId =
    ds ??
    catalog.data?.items.find(
      (d) =>
        Array.isArray(d.configuration.tickers) &&
        d.configuration.tickers.includes(ticker) &&
        d.configuration.provider === ctx.provider,
    )?.id ??
    '';
  const dataset = useObject(datasetId ? `/api/feature-datasets/${datasetId}` : undefined);
  const market = useObject(
    ticker && ctx.start && ctx.end && asOf
      ? `/api/market/${encodeURIComponent(ticker)}?${queryString({ start: ctx.start, end: ctx.end, provider: ctx.provider, as_of: asOf, limit: 500 })}`
      : undefined,
  );
  const feature = useObject(
    datasetId && ticker && ctx.start && ctx.end
      ? `/api/features/${ticker}?${queryString({ dataset_id: datasetId, start: ctx.start, end: ctx.end, limit: 500 })}`
      : undefined,
  );
  const predictions = usePage(ticker ? `/api/ml/predictions/${ticker}?limit=500` : undefined);
  const news = useArray(
    ticker && asOf ? `/api/news/${ticker}?${queryString({ as_of: asOf, limit: 20 })}` : undefined,
  );
  const rows = records(feature.data?.records).flatMap((r) =>
    records(r.features).map((c) => {
      const eligible =
        typeof c.online_ready_at === 'string' && Date.parse(c.online_ready_at) <= Date.parse(asOf);
      return {
        ...c,
        day: r.session_date,
        known_by_cutoff: eligible,
        value: eligible ? c.value : null,
        display_status: eligible ? text(c.missing_reason, 'Calculated') : 'Unavailable by cutoff',
      };
    }),
  );
  const forecasts = (predictions.data?.items ?? []).filter(
    (p) =>
      Date.parse(text(p.generated_at)) <= Date.parse(asOf) &&
      Date.parse(text(p.decision_at)) <= Date.parse(asOf),
  );
  return (
    <>
      <PageHeader
        title={ticker ? `${ticker} / security research` : 'Security research'}
        description="A shared historical context for market observations, calculated features, eligible forecasts, and source evidence."
      />
      <div className="panel panel-body" style={{ marginBottom: 20 }}>
        <form
          className="button-row"
          onSubmit={(e) => {
            e.preventDefault();
            const v = String(new FormData(e.currentTarget).get('asOf'));
            if (Number.isFinite(Date.parse(v))) setCutoff(v);
          }}
        >
          <label className="field">
            Availability cutoff (aware UTC timestamp)
            <input
              name="asOf"
              aria-label="Research availability cutoff"
              defaultValue={asOf}
              placeholder="YYYY-MM-DDTHH:mm:ssZ"
              required
            />
          </label>
          <button className="button" type="submit">
            Apply availability cutoff
          </button>
          <Badge>Strict known-by-cutoff display</Badge>
        </form>
        <Note>
          Changing the historical date never substitutes later information as known then. Market
          APIs require both availability and ingestion; features also require online readiness.
          Retrospective research artifacts remain labeled separately.
        </Note>
      </div>
      <Panel
        title="Raw market observations"
        eyebrow={`${ctx.provider || 'No provider'} · retained source revisions`}
      >
        {market.isError ? (
          <Failure error={market.error} retry={() => market.refetch()} />
        ) : (
          <SeriesChart
            label={`${ticker} eligible raw closing prices`}
            data={records(market.data?.prices).map((p) => ({
              day: p.session_date,
              close: finite(p.close),
            }))}
            series={[{ key: 'close', label: 'Raw close USD' }]}
          />
        )}
        <DataTable
          label="Historical market observations"
          rows={records(market.data?.prices)}
          columns={[
            { key: 'session_date', label: 'Session' },
            { key: 'close', label: 'Raw close USD', render: (v) => money(finite(v)) },
            { key: 'volume', label: 'Daily volume', render: (v) => decimal(finite(v), 0) },
            { key: 'available_at', label: 'Availability', render: (v) => timestamp(v) },
            { key: 'ingested_at', label: 'Ingested', render: (v) => timestamp(v) },
            { key: 'revision_no', label: 'Revision' },
            {
              key: 'is_synthetic',
              label: 'Source type',
              render: (v) => (
                <Badge tone={v ? 'warn' : 'neutral'}>
                  {v ? 'Synthetic fixture' : 'Provider observation'}
                </Badge>
              ),
            },
          ]}
        />
        <JsonDetails
          label="Price basis, calendar and source contract"
          value={{
            price_basis: market.data?.price_basis,
            availability_policy: market.data?.availability_policy,
            provider: market.data?.provider,
            as_of: market.data?.as_of,
          }}
        />
      </Panel>
      <Panel
        title="Point-in-time financial features"
        eyebrow="Actual M2/M3 cells and eligibility clocks"
        className="full"
      >
        <div className="panel-body">
          <label className="field">
            Cached feature dataset
            <select
              aria-label="Security feature dataset"
              value={datasetId}
              onChange={(e) => setDataset(e.target.value)}
            >
              {catalog.data?.items.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.id.slice(0, 8)} · {text(d.configuration.provider)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {feature.isError ? (
          <Failure error={feature.error} />
        ) : (
          <DataTable
            label="Eligible feature cells"
            rows={rows}
            columns={[
              { key: 'day', label: 'Observation' },
              { key: 'name', label: 'Feature' },
              { key: 'value', label: 'Value (native units)', render: (v) => decimal(finite(v), 6) },
              { key: 'display_status', label: 'Eligibility / missing reason' },
              { key: 'online_ready_at', label: 'Online-ready time', render: (v) => timestamp(v) },
            ]}
            onSelect={setCell}
          />
        )}{' '}
        {selectedCell && (
          <JsonDetails
            value={selectedCell}
            label="Selected numerical feature and exact dependency clocks"
          />
        )}
        <Provenance value={dataset.data} />
      </Panel>
      <div className="grid-two" style={{ marginTop: 20 }}>
        <Panel
          title="Eligible saved model forecasts"
          eyebrow="Generated and decision timestamps both ≤ cutoff"
        >
          <DataTable
            label="Known-by-cutoff forecasts"
            rows={forecasts}
            columns={[
              { key: 'decision_at', label: 'Decision', render: (v) => timestamp(v) },
              { key: 'generated_at', label: 'Generated', render: (v) => timestamp(v) },
              { key: 'value', label: 'Prediction', render: (v) => decimal(finite(v), 5) },
              { key: 'units', label: 'Units' },
            ]}
          />
        </Panel>
        <Panel title="News evidence coverage" eyebrow="Retained eligible article versions">
          {news.isError ? (
            <Failure error={news.error} />
          ) : news.data?.length ? (
            <DataTable
              label="Eligible security headlines"
              rows={news.data}
              columns={[
                {
                  key: 'headline',
                  label: 'Headline',
                  render: (v) => text(v, 'Restricted headline'),
                },
                { key: 'published_at', label: 'Published', render: (v) => timestamp(v) },
              ]}
            />
          ) : (
            <Empty title="Historical news unavailable">
              No observed coverage is not neutral sentiment.
            </Empty>
          )}
        </Panel>
      </div>
      <div className="grid-two">
        <Panel title="Fundamental information">
          <Empty title="No verified historical statements">
            No point-in-time financial statements are supplied by the current backend. No financial
            ratios or Fundamental Agent opinion is invented.
          </Empty>
        </Panel>
        <Panel title="Macro context">
          <Empty title="No verified historical macro vintages">
            The platform cannot reconstruct this historical category from the retained inputs. The
            Macro Agent must abstain.
          </Empty>
        </Panel>
      </div>
      <Note>
        To inspect agent recommendations, strategy signals, and portfolio risk, open the linked
        saved committee/portfolio experiment. Their immutable dates may differ from this market
        context.
      </Note>
    </>
  );
}
