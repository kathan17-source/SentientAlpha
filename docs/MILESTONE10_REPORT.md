# SentientAlpha — Milestone 10 delivery report

Date:2026-10-20 America/Chicago. Version0.10.0; schema0011. UTC evidence may be dated2026-10-21.

## 1. Milestone status

**COMPLETE for local full-stack engineering, with recorded verification limitations.** Core pages, actual API integration, bounded submissions, numerical displays, production build, preserved regressions and actual browser workflows are VERIFIED. Native Playwright/axe and deployment gates remain BLOCKED or unverified. This is simulation-only research, not a production-certified hedge fund. Milestone11 has not started.

## 2. Architecture decisions

VERIFIED. Ten Next App Router routes use a fixed server-only same-origin proxy to existing FastAPI engines. Generated OpenAPI types, runtime validation, cancellation-aware TanStack queries, URL-selected saved runs, bounded read catalogs and reusable components keep quantitative authority in M1–M9. The only application backend addition is public metadata catalog/coverage; schema remains0011. No engine was rewritten. [Architecture](FRONTEND_ARCHITECTURE.md).

## 3. Frontend stack and versions

VERIFIED. Resolved lockfile versions:

- @playwright/test: 1.64.1
- @radix-ui/react-dialog: 1.3.1
- @tanstack/react-query: 5.104.5
- @tanstack/react-table: 8.21.3
- eslint: 10.13.0
- next: 16.4.2
- prettier: 3.9.10
- react: 19.3.1
- react-dom: 19.3.1
- recharts: 3.10.1
- tailwindcss: 4.3.3
- typescript: 5.9.3
- vitest: 4.1.12
- zod: 4.6.7

Node24.16.0/npm11.13.0. Webpack is used because native Turbopack filesystem watching failed in this sandbox. ESLint flat configuration with TypeScript/React Hooks is used; the Next ESLint preset was removed to eliminate an unpatched vulnerable development dependency rather than downgrade the application.

## 4. Files added and modified

VERIFIED. New `frontend/` contains routes, design system, query/client/format/series helpers, generated contracts, lockfile, unit/integration/browser tests and local environment example. New backend `api/research.py` and `tests/test_research_catalog.py`; app router registration and package version updated. New offline pipeline `scripts/seed_dashboard_demo.py`; CI frontend job added; documentation/OpenAPI updated. [Exact changes](CHANGESET_M10.json) and [source hashes](SOURCE_SHA256_M10.json) enumerate delivery files. All original M9 tests and migrations are byte-identical to the M9 archive; no historical reports or archives were replaced.

## 5. Implemented pages

VERIFIED. `/` overview; `/portfolio` actual snapshots and numerical targets; `/committee` evidence and disagreements; `/strategies` candidates and locked splits; `/backtesting` ledger/metrics/comparison; `/sentiment` article versions and inference; `/risk` interventions/history; `/ml` experiments/models/forecasts; `/research` security and strict as-of inspection; `/experiments` saved manifests/replay. Each has loading/error/empty states and real records when available.

## 6. Reusable design components

VERIFIED. Charcoal terminal shell, compact responsive navigation, source/date context, simulation lock, provenance drawers, metrics/badges, paginated sortable/filterable tables, Recharts plots with accessible data disclosures, exact JSON downloads and Radix confirmation dialogs. Closed phone navigation is hidden from focus. Pending computations are labeled without invented progress percentages.

## 7. API endpoints integrated

VERIFIED. Health/readiness; bounded catalog/coverage; market/features/datasets; versioned news/FinBERT/contributors; backtest metrics/equity/orders/fills/replay; optimizer results/frontier points/replay; ML experiment metrics/importance/models/predictions/replay; strategy discovery/leaderboard/definitions/history/robustness/trades/replay; committee details/decisions/replay; risk decisions/policies/history/portfolio/alerts/stress/replay. See [exact OpenAPI](openapi.json) and the architecture document. OpenAPI type regeneration was byte-identical.

## 8. Actual user workflows tested

VERIFIED in the connected in-app browser against actual FastAPI/SQLite, not mocked responses. 30 recorded checks cover every workspace, evidence, vetoes, dates/provider switching, strict earlier cutoffs, historical holdings, benchmarks/orders/fills, failed strategy candidates, ML, genuine news, empty database, actually stopped backend, keyboard focus and responsive widths. All five submission kinds reached real engines: baseline, optimization, analysis-only committee, bounded discovery and hypothetical stress. New IDs include baseline `94726f43-232d-4573-85bd-7471a30efd66`, optimization `64f6210e-0cbc-4d01-87a3-4578720cd759`, committee `d8e71028-6892-40cb-be7e-92a45e1faf65` and discovery `9566f55c-62c1-46cf-9578-c994cbc142cd`. Follow-up HTTP reads confirmed committee `status=analyzed, backtest_id=null`; discovery candidates=2 and `no_eligible_strategy`. That failure is retained, not hidden or relabeled success. No automatic holdout run occurred. [Browser checks](verification/milestone10/browser-checks.json).

## 9. Financial charts implemented

VERIFIED for available data. Actual equity, drawdown,20-return rolling volatility/Sharpe, observed monthly compounded returns, allocation, sector exposure, correlation, component volatility, numerical frontier, source prices, ML importance/reliability/forecasts and sentiment probability/feature displays. Every plot labels units and has data disclosure. Missing series remain empty; absent statistical inputs do not become zero. Dense histories are bounded at2000 observations with disclosure. Sentiment-history breadth remains data-dependent and is only PARTIALLY VERIFIED on retained news coverage.

## 10. Investment Committee visualization

VERIFIED. Six specialized agent cards show participating/abstaining status, heuristic signal, reason, model/rule version, evidence clocks and source dependencies. Aggregation exposes independent groups/disagreement rather than presenting correlated votes as independent evidence. Proposal, risk-approved target and actual pre-decision holdings are separate, with links to actual execution and M9 decisions. Missing fundamental/macro/news agents abstain.

## 11. Risk Center implementation

VERIFIED. Original, approved and actual states stay separate; rejected approval is null. Policy/version, violations, exposure/covariance, tail confidence/sample/horizon, USD/fraction loss, realized drawdown latch, liquidity proxy and stress evidence are inspectable. Insufficient historical tails visibly remain INSUFFICIENT_DATA; no0VaR is invented. Hypothetical stress is explicitly a user-assumption sandbox; a100USD loss/5% example was computed by the backend while aggregate risk remained insufficient. No override or rejected-order retry bypass exists.

## 12. Strategy Lab implementation

VERIFIED. Backend validation ranking, all candidates including failed/no-trade rules, readable canonical grammar, costs/complexity, training/validation/test separation, search history, robustness and retained trades. Fold filtering follows actual backend records. Bounded grid/random discovery is reviewable and durable. Test periods remain locked and previously inspected samples remain labeled; neither best-case selection nor automatic holdout evaluation is added.

## 13. Backtesting visualization

VERIFIED. Stored ledger equity/metrics/trades and order-versus-fill switching; compatible benchmarks match provider/universe/date/capital/cost configuration. Sessions align without fabricated observations. Rolling/monthly presentation transformations have independent numerical tests. The genuine IBM baseline remains −8.70% versus buy-hold−4.69%; front-end polish does not change this negative research finding. Raw prices, approximate capacity/cost assumptions and missing action/membership history remain limitations.

## 14. Sentiment and ML workspaces

VERIFIED on actual retained records. Genuine M3 article versions and FinBERT probabilities/model provenance were inspected in a separate database: one actual example shows3.90% positive,93.92% neutral,2.17% negative (rounded). Rights-restricted headlines remain withheld. That database has synthetic context prices, visibly labeled, and is never joined to IBM investment performance. Missing IBM news is unavailable rather than neutral. ML displays saved experiments, split windows, held-out baselines, importance, calibration and forecasts with actual field names/clocks. No model training controls or alpha claims were invented. Broad genuine sentiment/forecast coverage is PARTIALLY VERIFIED.

## 15. Data provenance and missing-data handling

VERIFIED. Provider, synthetic flag, retained date range, source acquisition, availability/ingestion, calculation, decision and execution clocks remain distinct. Saved-run context is immutable and separately labeled from navigation context. Strict research filters hide not-yet-online features and future-generated forecasts. Null/NaN/infinite values render Unavailable; unknown sector remains UNKNOWN; source gaps are not filled. Genuine retrospective acquisition does not prove historical PIT availability. Missing covariance/tails/benchmark/news/fundamentals/macros retain explicit reasons.

## 16. Responsive design verification

VERIFIED by actual browser captures at1440×1000,1280×900,820×1180 and390×844. Document widths matched each viewport; tables scroll inside panels. Phone navigation opens/routes and closed navigation is not focusable. Actual390px screenshot was visually inspected for text/readability. Temporary viewport override was reset after QA. This is a representative width/device sample, not all devices.

## 17. Accessibility verification

PARTIALLY VERIFIED. Actual keyboard traversal showed visible solid focus; modal confirmation, Escape/focus behavior and semantic labels are covered by UI tests. Native controls/skip link/chart data tables/reduced motion are implemented. A rendered178-text-node sample had minimum contrast6.78:1 and no sample below4.5:1. Automated axe is provided but BLOCKED by native Chromium launch; no full WCAG certification or exhaustive assistive-technology audit is claimed.

## 18. TypeScript test results

VERIFIED. `npm run typecheck` runs Next type generation and strict `tsc --noEmit`, including fresh install without preexisting `.next` types. No type errors. Generated OpenAPI types reproduce byte-for-byte. ESLint and Prettier checks pass. [Logs](verification/milestone10/typecheck-final.txt).

## 19. Frontend unit and integration test results

VERIFIED. **51 tests in5 files pass**; final run958ms. Tests cover finite/UTC/financial formatting, drawdown/rolling/monthly and ledger-derived values, benchmark alignment, bounded pagination/accessible controls/dialog, XSS-safe text, actual client error/cancellation behavior, proxy route/origin/traversal/body limits, sanitized503 and no forwarded session credentials. Performance fixtures exercise20/50/500 synthetic records with at most10 rendered table rows and2000-point transformations. [Log](verification/milestone10/frontend-tests-final.txt).

## 20. Browser end-to-end test results

Actual connected-browser integration is VERIFIED: 30 checks passed against real services, including all submission flows. Native CLI Playwright is BLOCKED: Chromium installation succeeded, but macOS `bootstrap_check_in ... MachPortRendezvousServer` returned permission denied1100 and SIGTRAP before test actions. Fifteen native tests were attempted and could not launch; they are not counted as passes or application assertion failures. Four self-contained offline CI tests are additionally provided, not executed by remote CI here. Axe did not execute. Captured browser console contained four development Fast Refresh reload warnings during edits and no runtime/hydration error; this is observed-session evidence, not a universal guarantee.

## 21. Backend regression test results

VERIFIED. Python3.12:556 passed,1 optional skipped,11 subtests,68.14s; Python3.14:556 passed,1 optional skipped,11 subtests,70.47s. Optional real cached FinBERT passed separately (1 test,3.64s). Original554 tests and all migrations are byte-identical;2 new catalog/coverage tests were added. Ruff211 files, mypy119 modules, compileall and pip dependency checks on both environments pass. One existing Starlette/httpx deprecation warning remains. Original test/migration hashes are checked against M9. [3.12](verification/milestone10/backend312-final.txt), [3.14](verification/milestone10/backend314-final.txt).

## 22. Production build result

VERIFIED. `next build --webpack` succeeds for ten static research routes plus the dynamic proxy. Final compiler phase1382ms; TypeScript1069ms; static generation133ms. A production server started in86ms reported by Next and served actual backend integration. Separate fresh `npm ci`, type generation and clean production build succeed; final source was recopied and clean-built after the last form fixes. Development server also started and served actual data. No hosted deployment was attempted. [Build log](verification/milestone10/build-final.txt).

## 23. Actual performance measurements

VERIFIED within stated scope. Actual production browser route gesture→visible ML heading165ms including automation transport; browser Performance/memory globals were unavailable, so frame-rate/heap measurements are BLOCKED. Node/jsdom synthetic table renders20/50/500 records:22.123/2.881/4.282ms; cold first sample is not comparable to warm samples. At most10 rows render. A2000-observation transformation took2.318ms. Local production proxy→FastAPI→SQLite readiness11.688ms; backtest catalog3.515ms/1668bytes; ML catalog2.587ms/425bytes; coverage3.719ms/613bytes. These single-machine sequential samples are not p95, load capacity or50-asset research engine benchmarks. Existing M2–M9 multi-asset engine benchmarks remain in historical reports. No new browser-memory claim. [Measurements](verification/milestone10/component-benchmarks.json).

## 24. Security review results

VERIFIED for the local review/test scope. Fixed upstream, method/path allowlist, explicit browser POST origins, no credentials forwarded, bounded body/timeout, sanitized upstream errors, escaped provider text, no arbitrary rule execution, no broker/live endpoints, no public deployment. npm audit reports0 vulnerabilities in the final dependency tree. Exact public JSON remains user-downloadable without private artifacts. The services remain unauthenticated single-user loopback software: do not expose them publicly. Authentication/authorization, network-level quotas, operational audit, supply-chain monitoring and licensing review are future deployment gates;0 audit findings is not a complete security certification.

## 25. Genuine versus synthetic demo coverage

VERIFIED and kept separate. Fresh retained raw IBM M8 inputs were copied/migrated and recomputed through fixed M9 profiles at the final backend build; existing negative baseline, risk interventions and replay evidence remain unchanged. It is a short already-inspected retrospective sample, not held-out alpha. Separate genuine M3 articles/inferences demonstrate NLP provenance with explicitly synthetic context bars. New offline script independently generates synthetic two-asset prices, features, actual logistic ML, discovery, optimization/frontier, baseline comparisons, committee and M9 records through existing engines. It refuses existing databases. It does not manufacture news/fundamentals/macros. Source ZIP includes the reproducible generator, not private databases, licensed content or model caches.

## 26. PostgreSQL/Docker/CI limitations

BLOCKED/UNVERIFIED. Native PostgreSQL shared-memory/runtime and Docker daemon limitations documented in M9 persist; this milestone verifies SQLite. Existing PostgreSQL CI job is preserved and includes new catalog tests; a Node24/Python3.12 frontend job now installs/types/lints/tests/builds/seeds and runs offline browser tests on Linux. No Git remote exists and CI was not executed remotely. Configuration is not proof of CI success. No container build or complete production deployment is certified.

## 27. Screenshots captured from the actual rendered application

VERIFIED. These are direct application captures, not mockups. Additional captures include empty and actually unavailable backend states, genuine sentiment, phone layout and a submitted discovery. Hashes are in verification JSON.

Actual overview (`screenshots/milestone10/overview-desktop.png`, intentionally omitted; see PUBLICATION_SELECTION.md)

Committee evidence (`screenshots/milestone10/committee-desktop.png`, intentionally omitted; see PUBLICATION_SELECTION.md)

Independent risk (`screenshots/milestone10/risk-desktop.png`, intentionally omitted; see PUBLICATION_SELECTION.md)

Phone layout (`screenshots/milestone10/responsive-390.png`, intentionally omitted; see PUBLICATION_SELECTION.md)

## 28. Remaining issues

No critical disconnected page or dead submission flow remains in tested local contexts. Open limits: native Playwright/axe; broader assistive-technology/browser/device coverage; browser heap/frame/load profiling; native PostgreSQL/Docker/remote CI; public authentication/operations; comprehensive genuine PIT prices/actions/membership/news/macros/fundamentals; longer tail samples and calibrated inference. Dense views intentionally cap API records and disclose truncation. Computation remains synchronous with timeout rather than a durable distributed worker. Research results may legitimately fail, abstain, reject risk or have insufficient data. These states are preserved.

## 29. Readiness for Milestone 11 — Simulated Paper Trading

The local research workstation provides real evidence, ledger inspection, risk authority and reviewable research submissions for a later paper-execution design. Milestone11 is **NOT STARTED**. Before implementation, define paper-order idempotency, eligible clocks, fresh risk revalidation, conservation and stale-input behavior; resolve deployment gates when deploying. No broker connection or real-money path was introduced. This delivery stops at Milestone10.
