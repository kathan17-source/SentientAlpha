> Historical M1 evidence. Current M1–2 verification is in [MILESTONE2_REPORT.md](MILESTONE2_REPORT.md).

# Milestone 1 hardening validation

Validated October 13, 2026 (America/Chicago). See [full engineering report](HARDENING_REPORT.md)
for original status, changes, exact files, evidence categories, blockers and M2 readiness.

| Executed check | Actual result |
|---|---|
| Original baseline, Python 3.14.5 | 40 passed; 11 subtests; one dependency warning |
| Hardened full suite, Python 3.12.15 | **82 passed; 11 subtests; zero skipped** |
| Hardened full suite, Python 3.14.5 | **82 passed; 11 subtests; zero skipped** |
| Ruff lint / formatting | Passed |
| Mypy | Passed for all 19 application modules; untyped definitions prohibited; external calendar boundary is typed as Any |
| Dependency consistency | `pip check` passed in both interpreters |
| Source compilation | Passed for backend, migrations and scripts |
| SQLite migrations / schema drift / preservation | Passed; three revisions, fresh databases and legacy upgrade round trip |
| SQLite concurrency / actual rollback / idempotency | Passed; four parallel first ingestions -> one asset, four prices, 12 deduplicated rows |
| Real public provider, request -> database -> API | **7 real IBM bars**, Oct 1–9; repeat inserted 0/deduplicated 7; app restart preserved prices; synthetic source isolated |
| Compose v2.39.4 `config --quiet` | Passed with disposable placeholder database password |
| Docker runtime dry-run | **BLOCKED**: cannot connect to Docker daemon at `/var/run/docker.sock` |
| Native PostgreSQL 16.2 initdb | **BLOCKED**: sandbox denied `shmget`, including explicit mmap attempt |
| PGlite PostgreSQL 18.6 fallback suite, Python 3.12 | **23 passed, 3 failed, 2 setup errors**; not an all-passing PostgreSQL suite |
| Fallback isolated exact/max-price probes after restart | 2 passed; these do not erase the full-suite failures |
| Frontend | Absent by roadmap; no frontend/build/UI verification claimed |

The fallback suite is 28 tests: most use the PostgreSQL dialect fixture; four test local SQLite,
unavailability or configuration independently. It disables client prepared statements to avoid
shared prepared-name collisions in the fallback multiplexer. Failed negative tests concern
post-error rollback protocol; later setup errors concern authentication protocol state. Native
PostgreSQL must pass the normal suite in CI without fallback-specific client changes.

One Starlette test-client warning remains: its httpx compatibility adapter is deprecated.
Tests still execute and pass on both Python versions. Provider timeout, HTTP 429, malformed
payloads, source conflicts and internal failures use explicitly controlled inputs/fault
injection; the public IBM success path uses actual network data. Real exhaustion of a private
subscription quota was not attempted. Adjusted prices and corporate actions are unsupported.

Raw provider responses, original database backup, environments, downloaded binaries and full
execution logs remain outside the source deliverable in workspace scratch storage. Deliverable
JSON summaries contain no private credentials or licensed bulk price dataset. No real brokerage
adapter or order endpoint exists. Milestone 2 was not started.
