# Relational model and migration plan

UUID primary keys unless noted; monetary/price fields use fixed-precision numerics;
return/feature values use finite float64 calculations with documented units, persisted as JSON numbers/nulls. UTC timestamp fields include
creation and availability. Cross-module references are foreign keys, not free-form labels.

## M1 — implemented, with explicit verification boundaries

Three revisions: `0001_market_data` (unchanged original), `0002_data_contract`,
`0003_exact_sqlite_prices`. SQLite schema drift, fresh migrations and legacy preservation are
verified. PostgreSQL SQL dialect has partial fallback verification; native execution is blocked.

| Table | Columns and integrity |
|---|---|
| assets | id PK; ticker unique; name; sector; currency (USD); created_at. Never infers sector from price data. |
| ingestion_runs | id PK; provider; ticker; requested_start/end; status; started_at; completed_at; inserted/deduplicated counts; sanitized error_code; parameters (seed or endpoint settings, never secrets); quality_report (calendar/version, missing sessions, discontinuities, conflicts and transformations). Failed attempts remain auditable. |
| market_prices | id PK; asset_id FK; ingestion_run_id FK; session_date; open/high/low/close PostgreSQL Numeric(20,8) / SQLite decimal text(21); adjusted_close nullable; volume bigint; session_close_at nullable; observed_at nullable; available_at; ingested_at; availability_kind; calendar; adjustment_status; currency; revision_no; quality_flags; provider; is_synthetic; checksum. Unique (asset_id, provider, session_date, ingestion_run_id); range index (asset_id, provider, session_date, ingested_at). OHLC/volume, finite bounds, UTC ordering and provenance CHECK constraints; unique asset/provider/date/revision_no. |

Prices are content revisions. A checksum covers normalized economic content and provenance
kind, excluding observed acquisition timestamps so reruns are idempotent. Compare with the
latest revision, so a provider reverting a prior correction is preserved as another revision. Reads select one latest visible
revision per session/provider. Revision numbers determine order, including tied timestamps. Providers are never silently blended.
Legacy close/acquisition metadata is not backfilled. SQLite encoding migration flags old rows
`legacy_numeric_precision_unknown` and records its transformation without inventing lost digits.
Downgrade refuses prices that would lose exact precision. This service applies append-only
price updates; a database administrator retains mutation privileges. Freeze as-of plus exact
row IDs/checksums for research snapshots; ingestion timestamps are not transaction-commit timestamps.

The run counts only its newly inserted and deduplicated rows. Per-ticker PostgreSQL advisory locks and SQLite writer reservations serialize application
writes. Remaining uniqueness conflicts cause an atomic failed run with a retryable conflict code; partial writes never survive.

## M2 — implemented feature snapshot tables

Migration `0004_feature_engine` adds `feature_datasets`, `feature_source_assets`, `feature_inputs`
and `feature_rows`; seven application tables now share SQLAlchemy metadata. Datasets retain
normalized configuration, definitions, engine/library-dependent hashes, source cutoff, calculation
time and current/stale state. Inputs reference exact retained price revisions. Wide JSON rows store
values, null reasons and availability/ingestion/dependency clocks with dataset/asset/date primary keys.
Foreign keys restrict deletion of source evidence. A complete snapshot persists atomically in bulk
batches; matching source/configuration/definition hashes reuse it. Ingestion marks affected snapshots
stale in its price transaction. Definition compatibility is rechecked on reads.

The original three migrations remain unchanged. M2 is verified using actual SQLite migrations,
schema drift checks, atomic persistence, stale/revision/cache tests and API retrieval. PostgreSQL
migration SQL emission is a structural check only; native execution remains unverified. Historical
universe membership tables are deferred; current feature cohorts are fixed requested symbols, not
survivorship-free index membership. See [feature details](FEATURE_ENGINEERING.md).

## M3 — implemented news and sentiment evidence

Migration `0005_sentiment` adds eight tables: `news_stories`, `news_articles`, `news_versions`,
`article_associations`, `sentiment_inferences`, `sentiment_runs`, `news_coverage`, `sentiment_inputs`.
Article identities link exact revisions and story dedup reasons; inference attempts retain failed and
successful probability evidence without overwrite. Contexts reference existing assets. Distribution/
clock/unique constraints are checked using actual SQLite persistence. Sentiment values reuse M2
feature datasets/rows, with model/configuration/source hashes, clocks, coverage and interned contributor
sets. Large evidence maps stay internal; bounded API contributor queries expose model evidence.

The original four migrations remain unchanged. The working M2 DB was backed up and upgraded to 0005;
existing price/feature evidence was preserved. Native PostgreSQL runtime remains unverified. See
[SENTIMENT_ENGINEERING.md](SENTIMENT_ENGINEERING.md) and [M3 report](MILESTONE3_REPORT.md).

## Later migrations — design, not installed tables

| Milestone | Tables / relationships / principal fields |
|---|---|
| Later historical-universe extension | universes(id,name); universe_memberships(universe_id FK,asset_id FK,valid_from,to,known_at), unique effective interval; reconcile historical membership before survivorship-sensitive research |
| Later sentiment extension | Entitled full-text source references, historical entity/sector vintages and validated relation extraction; do not duplicate implemented M3 version/inference/feature tables |
| M4 | corporate_actions(asset_id FK,effective_date,available_at,type,ratio,cash,source_version); fundamentals(asset_id FK,period_end,published_at,available_at,vintage,metrics); macro_data(series_id,observation_date,released_at,vintage_date,value); effective and publication times indexed |
| M4–6 | experiments(id,seed,config_hash,dataset_id FK,train/validation/test bounds,code_version,status,metrics,created_at); strategy_backtests(id,strategy_id FK,experiment_id FK,cost_model,metrics,ledger_ref); model_versions(id,experiment_id FK,model_name,hyperparameters,features,artifact_hash,artifact_ref,trained_until) |
| M7 | strategies(id,genome_json,genome_hash,search_experiment_id FK,complexity,status,rejection_reason); jobs(id,kind,config,status,lease_until,attempts,error_code,result_ref), unique idempotency key; no arbitrary executable genome |
| M8 | agent_signals(id,agent_version,asset_id FK,experiment_id FK,as_of,horizon,signal,confidence,expected_return,risk_score,features,reason_codes); agent_performance(agent_version,regime,window_end,matured_count,accuracy,IC,Brier,PnL,Sharpe); committee_decisions(id,asset_id FK,experiment_id FK,as_of,signal_ids,disagreement,confidence,proposal,risk_adjustments,final_decision) |
| M9 | portfolios(id,name,mode,base_currency); portfolio_positions(portfolio_id FK,asset_id FK,as_of,quantity,weight,cost_basis), unique portfolio/asset/as_of; risk_metrics(portfolio_id FK,experiment_id FK,as_of,metric_values,limit_config,violations); decision_signals(decision_id FK,signal_id FK) normalizes committee evidence links |
| M11 | orders(id,portfolio_id FK,asset_id FK,decision_id FK,strategy_id FK,created_at,eligible_at,side,quantity,expected_price,status,idempotency_key UNIQUE); trades(id,order_id FK,filled_at,quantity,execution_price,commission,slippage,reason,before_snapshot,after_snapshot); portfolio_snapshots(id,portfolio_id FK,as_of,cash,equity,positions_hash) |
| M12 / remote gate | users(id,external_subject UNIQUE,created_at); portfolio_owners(user_id FK,portfolio_id FK); audit_events(actor_id FK,action,entity_id,at). Identity handled by an established OIDC provider. |

Large immutable artifacts (trained models, dense feature matrices, equity series) live in
versioned artifact storage and are referenced by checksum. PostgreSQL stores searchable
metadata and audit relationships. Foreign-key deletion defaults to RESTRICT for evidence.
Retention/redaction of licensed text follows provider terms; avoid publishing raw licensed data.


## M9 schema0011

Adds immutable `risk_policy_versions`, source-linked `risk_assessments` and deduplicated `risk_alerts`. Committee-linked rows reference M8 frozen sources and M4 events, not duplicated positions/orders. Standalone rows freeze supplied state and returns. Policy IDs/versions and committee event sequences are unique; alerts are unique per assessment/metric. All26 pre-existing tables retained identical row hashes through the M8→M9 upgrade. SQLite migration/model checks passed; PostgreSQL SQL generation passed but native runtime remains blocked. See RISK_MANAGEMENT.md for transaction/replay contracts.
