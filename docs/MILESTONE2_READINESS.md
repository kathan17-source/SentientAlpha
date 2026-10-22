> Historical M1 handoff document. Milestone 2 is now implemented; see [M2 report](MILESTONE2_REPORT.md) and [feature contracts](FEATURE_ENGINEERING.md).

# Milestone 2 readiness — no feature engine implemented

Assessment: **ready for feature-engine development on controlled local data; research-valid
historical experiments and production PostgreSQL deployment remain gated.**

## Available foundation

- Raw OHLCV and optional adjusted close are separate. Prices round-trip exactly in new SQLite
  records and PostgreSQL NUMERIC; legacy SQLite precision is explicitly unknown.
- Provider/ticker/session/revision IDs, content hashes, ingestion-run IDs and seeded demo
  configurations support reproducible input manifests. Never blend sources implicitly.
- Session close (scheduled), acquisition, asserted availability and ingestion are distinct UTC
  fields. Legacy session/acquisition timestamps stay null. As-of retrieval preserves revisions.
- XNYS sessions cover holidays, early closes and DST; the demo's weekday calendar is explicitly
  a model. Calendar implementation/version is recorded in each quality report.
- Missing sessions, source conflicts and discontinuities are preserved as diagnostics, without
  filling prices or adjusting corporate actions. A downstream module must inspect the run report
  as well as per-row flags; deduplicated rows retain their original row metadata.
- Date windows and bounded pagination already allow requesting lookback history. Freeze the
  returned `as_of` during pagination, then save exact row IDs/checksums in the future manifest.
- Request/database/API regressions, schema drift checks and simulation-only modes are exercised.

## Required M2 design decisions (deferred to M2, not implemented here)

| Concern | Gate |
|---|---|
| SMA/EMA/RSI/MACD/ATR/volatility/momentum | Implement pure deterministic calculations using aligned raw/total-return inputs as appropriate; version formulas and units |
| Multiple lookbacks / warmup | Fetch sufficient preceding **sessions**, not calendar-day guesses; identify warmup nulls and forbid future fill |
| Gaps and suspicious rows | Define stop/exclude policy; no implicit forward fill, return across unexplained splits or unrecorded repair |
| Corporate actions | Current raw adapter has no split/dividend ledger. Total-return research requires action-aware data or an explicit restricted experiment |
| PIT policy | Strict mode filters both availability and ingestion. Downloads acquired today cannot establish a past PIT universe or price publication history |
| Reconstruction | A separate explicitly labeled historical reconstruction policy may be needed. It must never be the default or called verified PIT |
| Historical universe | Only a current 24-symbol sample exists. Effective-dated membership and delistings remain unimplemented; never call the sample historical S&P 100 |
| ML chronology | Freeze train/validation/test ranges, label horizons and purging/embargo rules before deriving targets; fit preprocessing only on train |
| Multi-asset matrices | Use explicit calendar intersection/union policy, nulls/masks, units and identical as-of cutoffs; document cross-asset missingness |
| Reproducibility | Hash dataset manifest, row revisions, calendar version, code/formula version, settings and seed |

The original 1,560-bar demo has only 65 weekdays per asset, includes exchange holidays, and does
not support a 200-session indicator, robust ML splits or investment-performance claims.
The verified public IBM sample covers seven requested real sessions and a limited compact
response. It proves transport and persistence, not sufficient data for strategy discovery.

Native PostgreSQL 16 error rollback/concurrency and container execution still require an
unrestricted local/CI environment. The WebAssembly fallback failed negative transaction tests;
do not use it as the production database. No feature, strategy, ML or trading implementation
was added in this hardening task.
