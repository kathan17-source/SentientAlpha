# Final implementation and verification inventory

Historical M12 snapshot; current post-release resolutions and remaining blockers are in [POST_RELEASE_VERIFICATION.md](../POST_RELEASE_VERIFICATION.md).
Implementation is distinct from execution evidence. All capabilities below existed before stabilization unless marked M12. Source ownership remains separated; no second accounting engine or order executor was introduced.

| Capability / owner | Implementation | Verification and limits |
|---|---|---|
| M1 ingestion, versioned market data, source quality / data, services, database | Implemented | VERIFIED SQLite/provider contract fixtures; genuine IBM results retained; remote provider availability not guaranteed |
| M2 indicators, as-of matrices, cell lineage / features | Implemented | VERIFIED numerical and future perturbation regressions; genuine PIT coverage remains limited |
| M3 news versions, sentiment lineage / sentiment | Implemented | VERIFIED persistence and time gates with fixtures; real cached FinBERT smoke passes; optional dependency security PARTIALLY VERIFIED |
| M4 execution, Decimal ledger, historical experiments / backtesting | Implemented | VERIFIED actual integration and golden references, approximate market execution |
| M5 allocation and constraints / optimization | Implemented | VERIFIED numerical tests, persisted optimization and frontier in combined demo |
| M6 preprocessing, matured labels, calibration, numeric model artifacts / ml | Implemented | VERIFIED tests and actual synthetic training, no predictive alpha claim |
| M7 bounded discovery, locked holdout / strategies | Implemented | VERIFIED tests and actual six-candidate demo, holdout already inspected is labeled |
| M8 specialized agents and committee / committee | Implemented | VERIFIED saved evidence/M5 execution integrations; missing news/fundamental/macro causes abstention |
| M9 independent target/fill risk / risk | Implemented | VERIFIED actual veto and post-fill holdings, insufficient tails fail closed |
| M10 API/BFF/dashboard / api, frontend | Implemented | VERIFIED 59 tests, build and 38 HTTP checks; current rendered browser/axe BLOCKED |
| M11 sessions, worker, durable events / paper | Implemented | VERIFIED local SQLite atomicity, OS process death, restart/replay, 1/5/20/50 assets |
| PostgreSQL dialect + migrations | Implemented | BLOCKED native runtime; shmget denied, not SQLite-equivalent certification |
| Backend + frontend containers (frontend added M12) | Implemented | PARTIALLY VERIFIED Compose config; Docker daemon BLOCKED |
| CI dual Python, frontend, PostgreSQL, security (extended M12) | Configured | PARTIALLY VERIFIED local equivalent checks; remote run BLOCKED, no repository/remote |
| Combined offline demo (M12) | Implemented | VERIFIED clean runtime install, fresh database, 5 actual synthetic fills, separate veto, replay |
| Local browser protections and bounded bodies (M12) | Implemented | VERIFIED adversarial direct API/BFF tests; not authentication |
| Public identity, tenancy, authorization | NOT IMPLEMENTED | Public hosting prohibited; local single-user scope |
| Broker, live-money routing, deposits | NOT IMPLEMENTED | Deliberately absent; only simulation/paper mode accepted |
| Genuine long-term forward alpha | NOT IMPLEMENTED as an established research result | Short IBM experiment negative; no profitable claim |

Repository audit: inspected milestone reports M1–M11, architecture/financial methodology, API routers and OpenAPI, configuration/locks, adapters, paper transactions/worker, migration chain and release tooling. Earlier specialized numerical code is retained and exercised rather than rewritten. Source file hashes and sizes are enumerated in RELEASE_MANIFEST.json. No production eval/exec, shell=True, arbitrary strategy interpreter or HTML injection sink was found in the reviewed source. Torch model.eval() is inference mode, not Python eval. ML artifacts use bounded numeric JSON rather than arbitrary pickle loading. Optional external model loading has separate known advisory restrictions.

No disconnected business engine or demonstrably dead production route justified removal. The frontend intentionally exposes a subset of API mutations; provider ingestion, training and model initialization remain explicit CLI/API operations. Generic error/empty states and twelve conceptual views map to eleven routes (Security Research is within security/overview explanations, not a nonexistent standalone product page). No paid feed is required for the demo. No placeholder metrics were introduced.
