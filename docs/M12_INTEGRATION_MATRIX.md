# Integration and failure verification matrix

Historical M12 snapshot; current post-release resolutions and remaining blockers are in [POST_RELEASE_VERIFICATION.md](../POST_RELEASE_VERIFICATION.md).
| Boundary / scenario | Actual evidence | Classification |
|---|---|---|
| Ingest → versioned SQLite → feature dataset | release_demo invokes existing M1/M2 services, saved dataset HTTP 200 | VERIFIED synthetic integration |
| News → availability/revisions → sentiment cells | test_sentiment_integration (actual SQLite, controlled news/model fixture); separate real cached FinBERT smoke | VERIFIED separately; combined genuine corpus path PARTIALLY VERIFIED |
| Features → M6 fit/calibration → model metadata | actual seed_dashboard_demo logistic training, saved experiment via proxy | VERIFIED synthetic integration |
| Features → M7 bounded discovery → saved failures | actual six-candidate discovery, saved experiment API | VERIFIED synthetic integration |
| Evidence → M8 → M5 → M9 → M4 → ledger | combined paper session generated five actual simulated fills, stored decisions/risk/artifacts and reconciliation | VERIFIED synthetic integration |
| Missing news/fundamentals/macro → agent abstention | no sentiment fixtures seeded; committee integration regressions | VERIFIED, genuine coverage incomplete |
| Insufficient VaR → veto → zero orders filled | independent risk_veto session PAUSED, zero fill artifacts, replay equivalent | VERIFIED synthetic integration |
| Persistent database → API → Next BFF | 38 actual HTTP checks, eleven HTML responses and persisted JSON fields | VERIFIED transport; rendered UI not certified |
| Artifact versions → deterministic historical replay | prior complete suites plus new paper replay and unchanged build check | VERIFIED local, no source reacquisition |
| Browser Origin/Host and body exhaustion | direct API adversaries, original BFF tests plus missing-length body test | VERIFIED automated |
| Pre-commit and post-commit process death | real child process terminated with os._exit(73), retry and portfolio/replay assertions | VERIFIED SQLite, no distributed exactly-once claim |
| Competing workers, duplicate fills/orders | existing actual SQLite concurrency and DB unique receipt tests | VERIFIED within tested local bounds |
| Provider timeout/rate-limit/malformed response | test_hardening_domain controlled transport failures and integration no-fallback audit | VERIFIED mocked external failures, not provider outage experiment |
| Database unavailable | unavailable PostgreSQL URL error sanitization regression | VERIFIED error behavior, native PostgreSQL operation BLOCKED |
| Backend unavailable → BFF | owned backend stopped; actual proxy 503 backend_unavailable then restarted | VERIFIED actual outage |
| Frontend unavailable | owned Next process stopped at teardown, connection refused checked | VERIFIED unavailability, no high availability |
| Backup → new DB → restart API → reconciliation | sqlite3 online backup + integrity_check; identical portfolio after new process + replay | VERIFIED local SQLite recovery |
| Corrupt ML artifact / missing history / unavailable strategy | existing ML, strategy and feature integration regressions | VERIFIED controlled failure tests |
| Undefined risk metric / empty sentiment | existing mathematical and temporal tests, veto demo and empty sentiment catalog | VERIFIED without fabricated neutral values |
| Invalid migration and legacy schema | migration consistency/downgrade/legacy preservation regression suite | VERIFIED SQLite; arbitrary broken user migrations not certified |
| Lost acknowledgement during submission | actual paper post-commit death + stable command retry | VERIFIED paper effects; do not blindly retry non-idempotent historical research requests |
| Unexpected API error / incompatible frontend envelope | backend sanitization and frontend schema rejection tests | VERIFIED controlled failures |
| Disk full or device loss | pre-commit crash/rollback tests only | PARTIALLY VERIFIED; actual OS disk-full/device loss NOT TESTED |
| PostgreSQL / Docker / remote CI | initdb error / missing daemon / absent authorized remote | BLOCKED |
| Browser layout, console, keyboard, screen reader, axe | CUA URL policy rejects access | BLOCKED current milestone, component tests are not visual/a11y certification |

No new genuine market fetch, paid provider integration or long forward performance experiment was attempted. Existing genuine IBM empirical evidence remains unchanged. Local HTTP timings do not measure browser rendering.
