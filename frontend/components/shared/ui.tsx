'use client';
import Link from 'next/link';
import { AlertCircle, ArrowUpRight, ChevronDown, Download, RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { pretty, text, record } from '@/lib/format';
import type { CatalogItem } from '@/lib/api/client';
import * as Dialog from '@radix-ui/react-dialog';

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'good' | 'bad' | 'warn' | 'cyan';
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Panel({
  title,
  eyebrow,
  children,
  action,
  className = '',
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-head">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2>{title}</h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}
export function PageHeader({
  title,
  description,
  tag = 'Historical research',
  action,
}: {
  title: string;
  description: string;
  tag?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">
          <span className="tiny-line" />
          {tag}
        </div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Metric({
  label,
  value,
  detail,
  href,
  tone,
}: {
  label: string;
  value: string;
  detail?: string;
  href?: string;
  tone?: 'bad' | 'good';
}) {
  const content = (
    <>
      <div className="metric-label">
        {label}
        {href && <ArrowUpRight size={14} />}
      </div>
      <div className={`metric-number ${tone || ''}`}>{value}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </>
  );
  return href ? (
    <Link className="metric" href={href}>
      {content}
    </Link>
  ) : (
    <div className="metric">{content}</div>
  );
}
export function Empty({
  title = 'No saved observations',
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-symbol">∅</div>
      <h3>{title}</h3>
      <p>
        {children ||
          'Choose another historical context or create a bounded research run. Missing data is never replaced with invented results.'}
      </p>
    </div>
  );
}
export function Failure({ error, retry }: { error: Error | null; retry?: () => void }) {
  return (
    <div className="failure" role="alert">
      <AlertCircle size={18} />
      <div>
        <strong>Research data unavailable</strong>
        <p>{error?.message || 'The request could not be completed.'}</p>
        {retry && (
          <button className="button subtle" onClick={retry}>
            <RefreshCw size={13} />
            Retry request
          </button>
        )}
      </div>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="skeleton" />
      <span className="skeleton" />
      <p>Retrieving saved research…</p>
    </div>
  );
}
export function JsonDetails({
  value,
  label = 'Research manifest',
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <details className="json-details">
      <summary>
        {label}
        <ChevronDown size={14} />
      </summary>
      <pre>{pretty(value)}</pre>
      <button
        className="button subtle"
        onClick={() => {
          const url = URL.createObjectURL(new Blob([pretty(value)], { type: 'application/json' }));
          const a = document.createElement('a');
          a.href = url;
          a.download = 'sentientalpha-research.json';
          a.click();
          URL.revokeObjectURL(url);
        }}
      >
        <Download size={14} />
        Download JSON
      </button>
    </details>
  );
}
export function Provenance({
  value,
  label = 'Source & methodology',
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <div className="provenance">
      <Badge tone="cyan">Provenance</Badge>
      <JsonDetails label={label} value={value} />
    </div>
  );
}
export function RunSelect({
  items,
  value,
  onChange,
  label = 'Saved research run',
  next,
  onNext,
  onPrevious,
}: {
  items: CatalogItem[];
  value: string;
  onChange: (id: string) => void;
  label?: string;
  next?: number | null;
  onNext?: () => void;
  onPrevious?: () => void;
}) {
  return (
    <div className="run-select">
      <label>
        {label}
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select a saved run</option>
          {items.map((r) => (
            <option key={r.id} value={r.id}>
              {text(record(r.configuration.strategy).name, r.label).replaceAll('_', ' ')} ·{' '}
              {r.id.slice(0, 8)} · {r.status}
            </option>
          ))}
        </select>
      </label>
      {onPrevious && (
        <button className="button subtle" onClick={onPrevious}>
          Previous runs
        </button>
      )}
      {next != null && (
        <button className="button subtle" onClick={onNext}>
          More runs
        </button>
      )}
    </div>
  );
}
export function ConfirmDialog({
  title,
  description,
  children,
  onConfirm,
  disabled = false,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onConfirm: () => void;
  disabled?: boolean;
}) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="button" disabled={disabled}>
          {children}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content">
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <div className="button-row">
            <Dialog.Close className="button subtle">Cancel</Dialog.Close>
            <Dialog.Close className="button primary" onClick={onConfirm}>
              Run simulation research
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Note({ children }: { children: ReactNode }) {
  return (
    <p className="research-note">
      <AlertCircle size={15} />
      <span>{children}</span>
    </p>
  );
}
export const statusTone = (status: unknown): 'bad' | 'good' | 'warn' | 'neutral' =>
  /REJECT|HALT|VETO|failed/i.test(text(status, ''))
    ? 'bad'
    : /INSUFFICIENT|ABSTAIN|REDUCTION|UNAVAILABLE/i.test(text(status, ''))
      ? 'warn'
      : /APPROVED|completed|participated/i.test(text(status, ''))
        ? 'good'
        : 'neutral';
