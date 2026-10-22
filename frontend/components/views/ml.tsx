'use client';
import { useState } from 'react';
import { useObject, usePage, useSelection } from '@/lib/hooks';
import { useResearch } from '../shell';
import { record, records, text, finite, decimal, timestamp } from '@/lib/format';
import { entries } from '@/lib/series';
import {
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
import { DataTable } from '../shared/table';
import { SeriesChart } from '../shared/charts';
import { ReplayButton } from '../shared/research-form';
export default function ML() {
  const s = useSelection('ml');
  const context = useResearch();
  const [fold, setFold] = useState(0);
  const run = useObject(s.id ? `/api/ml/experiments/${s.id}` : undefined);
  const metrics = usePage(s.id ? `/api/ml/experiments/${s.id}/metrics` : undefined);
  const importance = usePage(s.id ? `/api/ml/experiments/${s.id}/feature-importance` : undefined);
  const models = usePage('/api/ml/models?limit=100');
  const [picked, setPicked] = useState<string | null>(null);
  const modelId = picked ?? text(models.data?.items.find((m) => m.experiment_id === s.id)?.id, '');
  const model = usePage(modelId ? `/api/ml/models/${modelId}` : undefined);
  const forecasts = usePage(
    context.ticker ? `/api/ml/predictions/${context.ticker}?limit=500` : undefined,
  );
  const f = metrics.data?.items[fold] ?? metrics.data?.items[0] ?? {};
  const test = record(f.metrics);
  const calibration = record(f.calibration);
  const reliability = records(test.reliability);
  const explained = importance.data?.items.find((i) => i.fold === f.fold);
  const chosenForecasts = (forecasts.data?.items ?? []).filter((p) => p.model_id === modelId);
  return (
    <>
      <PageHeader
        title="ML research"
        description="Inspect fitted models, chronological evaluation windows, calibration evidence, and historical forecasts without conflating probability with performance."
      />
      <RunSelect
        items={s.items}
        value={s.id}
        onChange={(id) => {
          s.select(id);
          setFold(0);
          setPicked(null);
        }}
        next={s.catalog.data?.next_offset}
        onNext={s.next}
      />
      {s.catalog.isError ? (
        <Failure error={s.catalog.error} />
      ) : !s.id ? (
        <Empty title="No fitted research experiment saved" />
      ) : run.isError ? (
        <Failure error={run.error} />
      ) : (
        <>
          <div className="run-select">
            <label>
              Evaluation fold
              <select value={fold} onChange={(e) => setFold(Number(e.target.value))}>
                {metrics.data?.items.map((f, i) => (
                  <option key={i} value={i}>
                    Fold {String(f.fold)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Registered model
              <select
                aria-label="Registered model"
                value={modelId}
                onChange={(e) => setPicked(e.target.value)}
              >
                {models.data?.items
                  .filter((m) => m.experiment_id === s.id)
                  .map((m) => (
                    <option key={text(m.id)} value={text(m.id)}>
                      {text(m.id).slice(0, 8)} / {text(m.version).slice(0, 12)}
                    </option>
                  ))}
              </select>
            </label>
            <ReplayButton path={`/api/ml/experiments/${s.id}/replay`} />
          </div>
          <div className="metrics">
            <Metric
              label="Held-out observations"
              value={decimal(finite(test.n), 0)}
              detail="Selected fold only"
            />
            <Metric
              label="Held-out correlation"
              value={decimal(finite(test.correlation), 3)}
              detail="Undefined if variance is absent"
            />
            <Metric
              label="Held-out loss / error"
              value={decimal(finite(test.log_loss ?? test.rmse), 4)}
              detail={test.log_loss != null ? 'Log loss' : 'RMSE in target units'}
            />
            <Metric
              label="Calibration status"
              value={text(calibration.status)}
              detail={`${text(calibration.method)} / n=${decimal(finite(calibration.n), 0)}`}
            />
          </div>
          <Panel
            title="Chronological research windows"
            eyebrow="Training → validation → calibration → untouched-at-selection test"
          >
            <DataTable
              label="ML evaluation windows"
              filterable={false}
              rows={entries(f.window).map((r) => ({ window: r.asset, date: r.value }))}
              columns={[
                { key: 'window', label: 'Window boundary' },
                { key: 'date', label: 'Date' },
              ]}
            />
            <Note>
              These are the experiment’s saved windows. Toolbar dates do not retroactively change
              its fitted model or held-out results.
            </Note>
          </Panel>
          <div className="grid-two" style={{ marginTop: 20 }}>
            <Panel
              title="Validation selection"
              eyebrow="Training-selected candidates · no test-based ranking"
            >
              <DataTable
                label="ML validation candidates"
                rows={records(f.candidates).map((c) => ({
                  ...c,
                  model: record(c.candidate).model,
                }))}
                columns={[
                  { key: 'model', label: 'Model family' },
                  {
                    key: 'validation_loss',
                    label: 'Validation loss',
                    render: (v) => decimal(finite(v), 6),
                  },
                  { key: 'status', label: 'Fit status' },
                ]}
              />
              <JsonDetails value={f.selection_rule} label="Selection rule and eligibility" />
            </Panel>
            <Panel
              title="Held-out baseline comparison"
              eyebrow="Test evidence, not training performance"
            >
              <DataTable
                label="Held-out model and baselines"
                rows={[
                  { model: 'Selected model', ...test },
                  ...entries(f.baselines).map((r) => ({ model: r.asset, ...record(r.value) })),
                ]}
                columns={[
                  { key: 'model', label: 'Estimator' },
                  { key: 'n', label: 'Samples' },
                  { key: 'log_loss', label: 'Log loss', render: (v) => decimal(finite(v), 4) },
                  { key: 'accuracy', label: 'Accuracy', render: (v) => decimal(finite(v), 4) },
                  { key: 'rmse', label: 'RMSE', render: (v) => decimal(finite(v), 5) },
                  { key: 'r2', label: 'R²', render: (v) => decimal(finite(v), 4) },
                ]}
              />
              <div className="panel-body">
                <Note>
                  A returned probability does not establish useful prediction. The small retained
                  IBM experiment did not establish an advantage over simple baselines.
                </Note>
              </div>
            </Panel>
          </div>
          <div className="grid-two">
            <Panel title="Reliability diagram" eyebrow="Stored held-out probability bins only">
              <SeriesChart
                label="Forecast probability versus observed event frequency"
                x="probability"
                unit="percent"
                data={reliability}
                series={[{ key: 'frequency', label: 'Observed event frequency' }]}
              />
              <JsonDetails
                label="Exact calibration and reliability values"
                value={{ calibration, reliability }}
              />
            </Panel>
            <Panel title="Feature importance" eyebrow="Model-specific stored explanations">
              <DataTable
                label="Model feature importance"
                rows={records(explained?.native)}
                columns={[
                  { key: 'feature', label: 'Feature' },
                  {
                    key: 'value',
                    label: 'Native importance',
                    render: (v) => decimal(finite(v), 5),
                  },
                ]}
              />
              <JsonDetails label="Native and held-out permutation evidence" value={explained} />
            </Panel>
          </div>
          <Panel
            title="Historical forecasts"
            eyebrow={`${context.ticker || 'No security'} · selected model only`}
          >
            {forecasts.isError ? (
              <Failure error={forecasts.error} />
            ) : (
              <DataTable
                label="Historical model forecasts"
                rows={chosenForecasts}
                columns={[
                  {
                    key: 'decision_at',
                    label: 'Research decision time',
                    render: (v) => timestamp(v),
                  },
                  { key: 'generated_at', label: 'Actually generated', render: (v) => timestamp(v) },
                  { key: 'value', label: 'Forecast', render: (v) => decimal(finite(v), 5) },
                  { key: 'horizon', label: 'Horizon' },
                  { key: 'units', label: 'Units' },
                  { key: 'origin', label: 'Provenance' },
                ]}
              />
            )}
            <div className="panel-body">
              <Note>
                Forecast generation and historical decision times are separate. Retrospectively
                generated values are research reconstructions, not contemporaneous live forecasts.
                Missing curves and calibration remain unavailable.
              </Note>
            </div>
          </Panel>
          <JsonDetails
            label="Registered model configuration and limitations"
            value={model.data?.items}
          />
          <JsonDetails
            label="Complete fold metrics, periods, calibration and uncertainty"
            value={f}
          />
          <Provenance value={run.data?.manifest} />
        </>
      )}
    </>
  );
}
