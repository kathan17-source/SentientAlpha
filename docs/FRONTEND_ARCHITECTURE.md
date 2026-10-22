# Frontend architecture — Milestones 10–11

## Boundary and local operation

SentientAlpha 0.10.0 is a single-user, local, simulation-only research workstation. Next.js renders eleven research/paper routes; FastAPI remains the authority for M1–M9 calculations, records, replay and validation. No brokerage, account, live order, authentication or hosted deployment was added. Bind both services to loopback. Publishing requires separate authentication, authorization, transport, quotas, operational and licensing work.

The generated `types/openapi.ts` comes from `docs/openapi.json`. `lib/api/client.ts` pairs generated contracts with Zod runtime envelopes and sanitized errors. Server-only `API_BASE_URL` selects a fixed backend. `/api/backend/[...path]` exposes a bounded same-origin proxy: allowed route/method pairs, explicit POST origins, traversal rejection, 2 MiB body limit, 120-second timeout, cancellation and no forwarded cookies or authorization. It is a local integration boundary, not a public authentication layer.

## Stack and organization

App Router and strict TypeScript; React; Tailwind with authored terminal-style CSS; Recharts; TanStack Query and Table; Zod; Radix Dialog; Lucide. Exact resolved versions are in `package-lock.json` and `VERIFICATION_M10.json`. Node 24.16.0/npm 11.13.0 were used; Node >=22 is required. Webpack is explicit because this sandbox's native Turbopack file watcher failed. See [Next installation](https://nextjs.org/docs/app/getting-started/installation), [Next 16 migration](https://nextjs.org/docs/app/guides/upgrading/version-16) and [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview).

- `app/`: ten thin route entries, shared providers/layout, proxy and styles.
- `components/views/`: overview, portfolio, committee, strategies, backtesting, sentiment, risk, ML, research and experiments.
- `components/shared/`: metrics, status states, provenance, confirmation dialogs, bounded submission forms, paginated tables and accessible chart data.
- `lib/hooks.ts`: cancellation-aware queries, catalogs and URL-selected immutable runs. Research context is separate from a saved experiment's source universe and period.
- `lib/format.ts` and `lib/series.ts`: finite-value formatting and explicitly labeled presentation calculations. Backend Decimal strings remain available in exact JSON disclosures.
- `tests/`, `e2e/`: meaningful numerical, UI, API, proxy and browser checks.

## APIs and data flow

Health and research coverage supply connection/source context. New read-only `/api/research/catalog` lists seven kinds with bounded pagination and public metadata only; `/api/research/coverage` lists retained ranges, not certified complete/live coverage. Catalog queries select only public ORM fields and never load serialized model artifacts or raw source blobs. No schema migration was required.

Existing endpoint families remain authoritative: `/api/market/{ticker}`, `/api/features/{ticker}`, `/api/feature-datasets/{id}`, `/api/news/{ticker}`, `/api/sentiment/articles/{version}`, sentiment contributors; `/api/backtest/{id}` metrics/equity/trades/replay; `/api/portfolio/optimization/{id}` result/points/replay; `/api/ml/experiments`, models and predictions; strategy discovery/leaderboard/definitions/history/robustness/trades/replay; committee detail/decisions/replay; risk history/decisions/policies/portfolio/alerts/stress/replay. See exported OpenAPI for exact schemas and bounds.

Forms submit actual baseline backtests, static optimization/frontiers, bounded discovery, analysis-only committees and hypothetical stress. Every operation shows its exact request before a Radix confirmation; responses contain real saved IDs or explicit errors. Computation is synchronous with pending state; there is no invented job percentage. Discovery does not automatically unlock holdout evaluation. The committee form does not create execution orders. Stress inputs are user assumptions, not historical scenario calibration.

## Numerical and research rules

Prices/equity/P&L are labeled USD; weights/returns/volatility are fractions formatted as percentages; slippage is basis points; ratios are dimensionless. Null/non-finite values render Unavailable, never zero. UTC timestamps require an offset. Plot gaps stay gaps. Benchmarks must match dates, provider/universe, capital and costs; observations align by session, never forward fill. Rolling metrics use 20 observed returns, annualization252 and explicit zero risk-free assumption; monthly returns compound observed returns and disclose partial months. Holdings use actual ledger snapshots: value=weight×equity, average cost=cost_basis/quantity and unrealized P&L=value−cost_basis. Exact original snapshots remain inspectable.

Proposal, risk-approved target and executed holdings are separate states with dates. Vetoed approval remains null. Historical portfolio selection retrieves risk as of the selected snapshot, excluding later assessments. Research source/ingestion/calculation/decision clocks remain distinct; strict security inspection excludes future market/features/forecast evidence. Retrospective reconstruction is explicitly labeled and does not establish historical online availability. Missing fundamentals, macro, sentiment or model evidence produces abstention, not neutral evidence or invented panels.

## Interaction, accessibility and scale

Native labels/buttons/links, skip link, semantic tables, visible keyboard focus, Radix focus trap/Escape/restore, reduced-motion styling and chart data disclosures support keyboard and screen-reader use. The closed phone sidebar is hidden from focus. Actual tested widths:1440,1280,820,390 without document overflow; data tables scroll within panels. Tables render10 rows per page. API lists are bounded; equity charts cap2000 observations with truncation disclosure. This is not an unbounded market terminal or distributed job system.

A sample of178 rendered text nodes met4.5:1 with minimum6.78:1. Full automated axe/WCAG certification is not claimed: the native Chromium launcher is sandbox-blocked. Actual in-app-browser checks are documented separately from provided Playwright suites. Node/jsdom timings are component benchmarks, not browser frame/memory measurements.

## Repeatable local demonstration

Follow the root README. `scripts/seed_dashboard_demo.py` refuses an existing target and creates explicitly synthetic research through the existing ingestion, feature, ML, discovery, optimizer, backtest, committee and risk engines. It needs no credentials or network. Genuine retained IBM and M3 news were verified separately; their private working databases and model caches are deliberately absent from the source ZIP. The offline seed leaves unavailable sentiment/fundamental/macro evidence unavailable. Changing the seed is not proof of alpha.

## Verification and operating limitations

Read `MILESTONE10_REPORT.md` and `VERIFICATION_M10.json` for exact results. Native PostgreSQL/Docker, remote CI, public auth/deployment, browser heap/frame profiling and automated axe remain open. Existing historical corporate-action, membership, PIT news and statistical limitations remain unchanged. Milestone11 has not started.


## Milestone 11 — Paper Trading workstation

`/paper` is the eleventh route, added to the existing shell. It uses current mutable-session queries with explicit refresh/invalidation, while earlier immutable research queries keep their prior semantics. Local commands are reviewed as exact JSON before Radix confirmation; a pending request retains its retry key. Lifecycle choices follow returned status; stopped/historical sessions cannot advance. The view exposes actual ledger metrics/positions/equity, M5/M9/filled-weight distinctions, agent participation, provider updates, paged order/fill/risk/event records, cancellation and immutable reconciliation. It never labels paper data LIVE or brokerage performance. The proxy adds only named paper session actions, not arbitrary order submission. Strict types, unit tests and production build pass; actual proxy/API integration passes. Browser visual verification for this route is BLOCKED by browser tool URL policy; no M11 screenshot/axe pass is claimed.
