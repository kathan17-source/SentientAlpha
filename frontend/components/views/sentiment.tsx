'use client';
import { useState } from 'react';
import { useResearch } from '../shell';
import { useArray, useCatalog, useObject } from '@/lib/hooks';
import { queryString } from '@/lib/api/client';
import { records, text, finite, percent, decimal, timestamp, type RecordData } from '@/lib/format';
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
import { DataTable } from '../shared/table';
import { SeriesChart } from '../shared/charts';
function safeUrl(value: unknown) {
  try {
    const u = new URL(String(value));
    return ['https:', 'http:'].includes(u.protocol) ? u.href : undefined;
  } catch {
    return undefined;
  }
}
export default function Sentiment() {
  const ctx = useResearch();
  const [cutoff, setCutoff] = useState<string | null>(null);
  const asOf = cutoff ?? ctx.asOf;
  const [ticker, setTicker] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<RecordData | null>(null);
  const symbol = ticker ?? ctx.ticker;
  const news = useArray(
    symbol && asOf
      ? `/api/news/${encodeURIComponent(symbol)}?${queryString({ as_of: asOf, limit: 50, offset })}`
      : undefined,
  );
  const inference = useArray(
    selected?.version_id ? `/api/sentiment/articles/${text(selected.version_id)}` : undefined,
  );
  const catalog = useCatalog('features');
  const [ds, setDataset] = useState('');
  const dataset = useObject(ds ? `/api/feature-datasets/${ds}` : undefined);
  const sentimentColumns = Array.isArray(dataset.data?.columns)
    ? (dataset.data.columns.filter(
        (c) => typeof c === 'string' && c.startsWith('sent_'),
      ) as string[])
    : [];
  const [chosenFeature, setChosenFeature] = useState<string | null>(null);
  const feature =
    chosenFeature && sentimentColumns.includes(chosenFeature)
      ? chosenFeature
      : (sentimentColumns.find((c) => c.startsWith('sent_mean__')) ?? sentimentColumns[0]);
  const volumeFeature =
    sentimentColumns.find((c) => c.startsWith('sent_news_volume__')) ??
    sentimentColumns.find((c) => c.startsWith('sent_article_count__'));
  const observations = useObject(
    ds && symbol && ctx.start && ctx.end
      ? `/api/features/${encodeURIComponent(symbol)}?${queryString({ dataset_id: ds, start: ctx.start, end: ctx.end, limit: 500 })}`
      : undefined,
  );
  const [observationDay, setObservationDay] = useState<string | null>(null);
  const contributors = useObject(
    ds && feature && observationDay
      ? `/api/sentiment/${ds}/contributors?${queryString({ ticker: symbol, session_date: observationDay, feature })}`
      : undefined,
  );
  const timeline = records(observations.data?.records).map((r) => {
    const cells = records(r.features);
    return {
      day: r.session_date,
      ...Object.fromEntries(
        sentimentColumns.map((name) => {
          const c = cells.find((c) => c.name === name);
          return [
            name,
            c?.online_ready_at && Date.parse(text(c.online_ready_at)) <= Date.parse(asOf)
              ? finite(c.value)
              : null,
          ];
        }),
      ),
    };
  });
  return (
    <>
      <PageHeader
        title="Sentiment intelligence"
        description="Inspect eligible news versions and actual financial NLP inference. Missing coverage is not neutral sentiment."
      />
      <form
        className="button-row"
        style={{ marginBottom: 18 }}
        onSubmit={(e) => {
          e.preventDefault();
          const input = String(new FormData(e.currentTarget).get('cutoff'));
          if (/(Z|[+-]\d{2}:\d{2})$/.test(input) && Number.isFinite(Date.parse(input)))
            setCutoff(input);
        }}
      >
        <label className="field">
          News / inference availability cutoff (UTC)
          <input name="cutoff" required defaultValue={asOf} placeholder="YYYY-MM-DDTHH:mm:ssZ" />
        </label>
        <button className="button subtle" type="submit">
          Apply news cutoff
        </button>
      </form>
      <div className="button-row" style={{ marginBottom: 18 }}>
        <Badge>Availability cutoff: {timestamp(asOf)}</Badge>
        <button
          className="button subtle"
          onClick={() => {
            setTicker(ctx.ticker);
            setOffset(0);
            setSelected(null);
          }}
        >
          Selected security: {ctx.ticker || 'Unavailable'}
        </button>
        <button
          className="button subtle"
          onClick={() => {
            setTicker('SENT.MKT');
            setOffset(0);
            setSelected(null);
          }}
        >
          Broad-market news
        </button>
      </div>
      <Panel
        title={`Retained news evidence / ${symbol || 'No security'}`}
        eyebrow="Provider records · rights-aware headline display"
      >
        {news.isError ? (
          <Failure error={news.error} retry={() => news.refetch()} />
        ) : !news.data?.length ? (
          <Empty title="No eligible news observed">
            This database does not establish complete historical news coverage for this selection.
            No sentiment score or neutral probability is inferred from an empty result.
          </Empty>
        ) : (
          <DataTable
            label="News evidence"
            rows={news.data}
            columns={[
              {
                key: 'headline',
                label: 'Headline',
                render: (v, r) => (
                  <span>
                    {text(v, 'Headline unavailable under source rights')}
                    {r.is_synthetic === true && <Badge tone="warn">Synthetic fixture</Badge>}
                  </span>
                ),
              },
              { key: 'publisher', label: 'Source' },
              { key: 'published_at', label: 'Published', render: (v) => timestamp(v) },
              { key: 'observed_at', label: 'First available version', render: (v) => timestamp(v) },
              { key: 'revision_no', label: 'Revision' },
              { key: 'relevance_status', label: 'Relevance' },
            ]}
            onSelect={setSelected}
          />
        )}
        <div className="panel-body button-row">
          {offset > 0 && (
            <button className="button subtle" onClick={() => setOffset((o) => Math.max(0, o - 50))}>
              Previous news
            </button>
          )}
          {news.data?.length === 50 && (
            <button className="button subtle" onClick={() => setOffset((o) => o + 50)}>
              More news
            </button>
          )}
        </div>
      </Panel>
      {selected && (
        <Panel
          title="Article version & financial sentiment"
          eyebrow={text(selected.version_id)}
          className="full"
        >
          <div className="panel-body">
            <h3>{text(selected.headline, 'Headline unavailable under source rights')}</h3>
            <Note>
              {selected.is_synthetic === true
                ? 'Explicitly synthetic article fixture.'
                : 'Retained provider observation; inspect publication and observation clocks separately.'}{' '}
              FinBERT sentiment does not establish a return forecast.
            </Note>
            {safeUrl(selected.url) && (
              <a
                className="text-button"
                href={safeUrl(selected.url)}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open original source ↗
              </a>
            )}
          </div>
          {inference.isError ? (
            <Failure error={inference.error} />
          ) : !inference.data?.length ? (
            <Empty title="No inference recorded for this article version">
              No fabricated neutral score is substituted. Explicit initialization and inference
              remain backend operations.
            </Empty>
          ) : (
            <DataTable
              label="Actual article inference probabilities"
              rows={inference.data.filter(
                (r) => Date.parse(text(r.inferred_at)) <= Date.parse(asOf),
              )}
              columns={[
                { key: 'status', label: 'Inference status' },
                {
                  key: 'positive',
                  label: 'Positive probability',
                  render: (v) => percent(finite(v)),
                },
                { key: 'neutral', label: 'Neutral probability', render: (v) => percent(finite(v)) },
                {
                  key: 'negative',
                  label: 'Negative probability',
                  render: (v) => percent(finite(v)),
                },
                { key: 'score', label: 'Signed score', render: (v) => decimal(finite(v), 4) },
                { key: 'inferred_at', label: 'Actually calculated', render: (v) => timestamp(v) },
              ]}
            />
          )}
          <Provenance
            value={{
              article: selected,
              inference: inference.data?.filter(
                (r) => Date.parse(text(r.inferred_at)) <= Date.parse(asOf),
              ),
            }}
          />
        </Panel>
      )}
      <Panel
        title="Historical sentiment features"
        eyebrow="Eligible cached M3 calculations only"
        className="full"
      >
        <div className="panel-body">
          <label className="field">
            Saved feature dataset
            <select
              aria-label="Sentiment feature dataset"
              value={ds}
              onChange={(e) => setDataset(e.target.value)}
            >
              <option value="">Select a dataset with actual M3 features</option>
              {catalog.data?.items.map((d) => (
                <option value={d.id} key={d.id}>
                  {d.id.slice(0, 8)} / {text(d.configuration.provider)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="panel-body">
          <label className="field">
            Sentiment metric (native definition)
            <select
              aria-label="Sentiment metric"
              value={feature ?? ''}
              onChange={(e) => setChosenFeature(e.target.value)}
            >
              {sentimentColumns.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>
        {observations.isError ? (
          <Failure error={observations.error} />
        ) : (
          <SeriesChart
            label="Eligible financial sentiment observations"
            unit={feature && /probability|fraction/.test(feature) ? 'percent' : 'ratio'}
            data={timeline}
            series={feature ? [{ key: feature, label: feature }] : []}
          />
        )}
        {volumeFeature && (
          <SeriesChart
            label="Eligible news volume"
            unit="ratio"
            kind="bar"
            data={timeline}
            series={[{ key: volumeFeature, label: volumeFeature + ' (observed count)' }]}
          />
        )}
        <DataTable
          label="Sentiment observation evidence"
          rows={timeline}
          columns={[
            { key: 'day', label: 'Observation session' },
            ...(feature
              ? [
                  {
                    key: feature,
                    label: 'Selected feature value',
                    render: (v: unknown) => decimal(finite(v), 5),
                  },
                ]
              : []),
          ]}
          onSelect={(r) => setObservationDay(text(r.day))}
        />
        {contributors.isError ? (
          <Failure error={contributors.error} />
        ) : (
          observationDay && (
            <>
              <JsonDetails
                label="Eligible cell contributors and model versions"
                value={contributors.data}
              />
              <DataTable
                label="Sentiment contributor inferences"
                rows={records(contributors.data?.inferences).filter(
                  (r) => Date.parse(text(r.inferred_at)) <= Date.parse(asOf),
                )}
                columns={[
                  { key: 'version_id', label: 'Article version' },
                  {
                    key: 'score',
                    label: 'Signed score',
                    render: (v: unknown) => decimal(finite(v), 4),
                  },
                  { key: 'inferred_at', label: 'Calculated', render: (v: unknown) => timestamp(v) },
                ]}
                onSelect={(r) =>
                  setSelected(
                    news.data?.find((n) => n.version_id === r.version_id) ?? {
                      version_id: r.version_id,
                    },
                  )
                }
              />
            </>
          )
        )}
        <div className="panel-body">
          <Note>
            No series is drawn for price-only datasets, missing inference, incomplete coverage, or
            calculations unavailable by the selected cutoff. News volume and sentiment probability
            have different units; inspect exact cell metadata.
          </Note>
        </div>
        <JsonDetails
          label="Selected sentiment definitions, coverage and versions"
          value={dataset.data}
        />
      </Panel>
    </>
  );
}
