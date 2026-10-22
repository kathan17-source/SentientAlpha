'use client';
import { createContext, useContext, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  BrainCircuit,
  ChevronRight,
  FlaskConical,
  History,
  LayoutDashboard,
  Menu,
  Network,
  Newspaper,
  Search,
  ShieldCheck,
  Wallet,
  X,
} from 'lucide-react';
import { api, pageSchema, objectSchema } from '@/lib/api/client';
import { text, timestamp, type RecordData } from '@/lib/format';
import { Badge } from './shared/ui';
const nav = [
  ['/', 'Overview', LayoutDashboard],
  ['/portfolio', 'Portfolio', Wallet],
  ['/paper', 'Paper Trading', Activity],
  ['/committee', 'Investment Committee', Network],
  ['/strategies', 'Strategy Lab', FlaskConical],
  ['/backtesting', 'Backtesting', BarChart3],
  ['/sentiment', 'Sentiment Intelligence', Newspaper],
  ['/risk', 'Risk Center', ShieldCheck],
  ['/ml', 'ML Research', BrainCircuit],
  ['/research', 'Security Research', Search],
  ['/experiments', 'Experiment History', History],
] as const;
export type ResearchContext = {
  ticker: string;
  provider: string;
  start: string;
  end: string;
  asOf: string;
  coverage: RecordData[];
};
const Research = createContext<ResearchContext>({
  ticker: '',
  provider: '',
  start: '',
  end: '',
  asOf: '',
  coverage: [],
});
export const useResearch = () => useContext(Research);
function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const coverage = useQuery({
    queryKey: ['coverage'],
    queryFn: ({ signal }) => api('/api/research/coverage?limit=200', pageSchema, { signal }),
    staleTime: 60000,
  });
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => api('/ready', objectSchema, { signal }),
    staleTime: 60000,
  });
  const [filters, setFilters] = useState<{
    key: string;
    start: string;
    end: string;
    asOf: string;
  } | null>(null);
  const choices = coverage.data?.items ?? [];
  const first = choices.find((c) => c.provider !== 'synthetic') ?? choices[0];
  const selected = choices.find((c) => `${c.ticker}:${c.provider}` === filters?.key) ?? first;
  const context: ResearchContext = {
    ticker: text(selected?.ticker, ''),
    provider: text(selected?.provider, ''),
    start: filters?.start || text(selected?.start, ''),
    end: filters?.end || text(selected?.end, ''),
    asOf: filters?.asOf || text(selected?.latest_ingested_at, ''),
    coverage: choices,
  };
  const title = nav.find(([href]) => href === pathname)?.[1] ?? 'Research';
  return (
    <Research.Provider value={context}>
      <div className="workstation">
        <a className="skip-link" href="#main-content">
          Skip to research content
        </a>
        <aside id="research-sidebar" className={`sidebar ${open ? 'is-open' : ''}`}>
          <Link href="/" className="brand" onClick={() => setOpen(false)}>
            <span className="brand-mark">
              <Activity size={23} />
            </span>
            <span>
              sentient<span className="brand-alpha">alpha</span>
              <small>QUANTITATIVE RESEARCH</small>
            </span>
          </Link>
          <div className="sidebar-caption">
            WORKSTATION
            <button
              className="mobile-close"
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
            >
              <X size={18} />
            </button>
          </div>
          <nav aria-label="Research navigation">
            {nav.map(([href, label, Icon]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={pathname === href ? 'nav-item active' : 'nav-item'}
                aria-current={pathname === href ? 'page' : undefined}
              >
                <Icon size={17} />
                <span>{label}</span>
                {pathname === href && <span className="nav-dot" />}
              </Link>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="workspace-label">
              <span className="workspace-avatar">SA</span>
              <div>
                Local research workspace<small>Single-user · v0.11.0</small>
              </div>
            </div>
            <div className="simulation-lock">
              <ShieldCheck size={14} />
              Simulation only<span>LOCKED</span>
            </div>
            <p>
              No brokerage connection.
              <br />
              Historical results are not live positions.
            </p>
          </div>
        </aside>
        {open && (
          <button
            className="nav-backdrop"
            aria-label="Close navigation overlay"
            onClick={() => setOpen(false)}
          />
        )}
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumbs">
              <button
                className="mobile-menu"
                aria-label="Open navigation"
                aria-expanded={open}
                aria-controls="research-sidebar"
                onClick={() => setOpen(true)}
              >
                <Menu size={20} />
              </button>
              <span>Research workspace</span>
              <ChevronRight size={13} />
              <strong>{title}</strong>
            </div>
            <div className="top-status">
              <span
                aria-hidden="true"
                className={`status-dot ${health.isError ? 'offline' : health.isSuccess ? '' : 'pending'}`}
              />
              <span role="status" aria-live="polite">
                {health.isSuccess
                  ? 'Backend connected'
                  : health.isError
                    ? 'Backend unavailable'
                    : 'Connecting'}
              </span>
              <span className="top-separator" />
              <Badge>Simulation only</Badge>
              <span className="simulation-locked">LOCKED</span>
            </div>
          </header>
          <div className="contextbar">
            <form
              key={`${context.ticker}:${context.provider}`}
              className="context-form"
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                setFilters({
                  key: String(form.get('dataset')),
                  start: String(form.get('start')),
                  end: String(form.get('end')),
                  asOf: String(form.get('asOf')),
                });
              }}
            >
              <label className="context-security">
                <Search size={14} />
                <span className="sr-only">Security and source</span>
                <select
                  name="dataset"
                  defaultValue={`${context.ticker}:${context.provider}`}
                  aria-label="Security and source"
                  onChange={(e) => {
                    const c = choices.find((c) => `${c.ticker}:${c.provider}` === e.target.value);
                    if (c)
                      setFilters({
                        key: e.target.value,
                        start: text(c.start, ''),
                        end: text(c.end, ''),
                        asOf: text(c.latest_ingested_at, ''),
                      });
                  }}
                >
                  <option value=":" disabled>
                    No market dataset
                  </option>
                  {choices.map((c) => (
                    <option key={`${c.ticker}:${c.provider}`} value={`${c.ticker}:${c.provider}`}>
                      {text(c.ticker)} · {text(c.provider)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>From</span>
                <input
                  aria-label="Historical start date"
                  type="date"
                  name="start"
                  defaultValue={context.start}
                  required
                />
              </label>
              <label>
                <span>To</span>
                <input
                  aria-label="Historical end date"
                  type="date"
                  name="end"
                  defaultValue={context.end}
                  min={context.start}
                  required
                />
              </label>
              <input type="hidden" name="asOf" value={context.asOf} />
              <button className="button subtle" type="submit" disabled={!context.ticker}>
                Apply context
              </button>
            </form>
            <div className="context-meta">
              <span>Retained observations</span>
              <strong>{context.end || 'No dataset'}</strong>
            </div>
          </div>
          <main id="main-content" tabIndex={-1}>
            {context.provider === 'synthetic' && (
              <div className="synthetic-banner" role="status">
                Synthetic dataset context — generated observations verify software behavior, not
                market performance. Saved experiments retain their own source provenance.
              </div>
            )}
            {children}
          </main>
          <footer className="app-footer">
            <span>SentientAlpha / Research infrastructure</span>
            <span>
              Data availability: {timestamp(context.asOf)} <ArrowUpRight size={11} />
            </span>
          </footer>
        </div>
      </div>
    </Research.Provider>
  );
}
export default function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false, refetchOnReconnect: false },
          mutations: { retry: false },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <Shell>{children}</Shell>
    </QueryClientProvider>
  );
}
