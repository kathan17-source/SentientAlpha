> Historical audit/release record. The owner has now selected All Rights Reserved and authorized a private candidate upload. Current selection and verification supersede earlier pending-decision/upload statements: [publication selection](PUBLICATION_SELECTION.md), [current report](GITHUB_PORTFOLIO_PREPARATION.md). Historical results remain historical.

# SentientAlpha — post-release verification

Date: 2026-10-21. Version **v0.12.0**, source revision `post-release-verification-2026-10-21`. No Milestone13 or new financial functionality. This revision changes optional dependencies and verification/presentation material; it is a new source archive, not the original M12 archive under the same hash.

**Ready for owner technical review: VERIFIED. Public publication readiness: PARTIALLY VERIFIED**, pending the owner's license/material review and transparent acceptance of remaining verification gaps. Local core research/simulation remains verified. Deployment/production claims remain BLOCKED. Nothing was published, pushed, uploaded or deployed externally.

## 1. Baseline and preservation

The original499-file M12 ZIP matched SHA256 `ffaacf09fa0d25ee3483f393ad61c55619a449984063a15554790b2c0a7390bd`; every source-manifest file hash matched before edits. Its reported605+11 subtests per Python,59 frontend tests,38 HTTP checks, clean install, crash/backup recovery and archive evidence were inspected. The original ZIP/sidecar remain unchanged outside the new source archive.

All **55 prior backend/frontend test, e2e and migration files** are byte-identical. **Every backend production source file is byte-identical**. No mathematical convention, model weight, strategy, agent, ledger/executor or API behavior was rewritten. The optional dependency metadata and provenance change intentionally. Source remains0.12.0 with this explicitly named verification revision; compare manifests, not just the display version.

## 2. Final gap status and cause

| Area | Final classification | Cause, attempt and next step |
|---|---|---|
| Native PostgreSQL | **BLOCKED** | Actual installed initdb rerun once in fresh disposable directory; bootstrap fails `could not create shared memory segment: Operation not permitted`, shmget size56. Software exists; the OS sandbox denies a shared-memory primitive, not a demonstrated application defect. No native integration test passed. Use the loopback disposable host/CI procedure below. |
| Docker | **PARTIALLY VERIFIED** configuration; runtime **BLOCKED** | No Docker CLI on PATH and no standard daemon sockets. Official standalone Compose config --quiet passes; Compose ps fails Cannot connect to Docker daemon. Host-script preflight also reports CLI absent. No privileged installation or host setting change was attempted. Run supplied host script only after enabling a host daemon. |
| Remote CI | **BLOCKED** execution; configuration **PARTIALLY VERIFIED** | Source directory is not a Git repository, no authorized remote exists. YAML parsed; actual remote run unavailable and no push/create attempted. Dual-Python/PG/security/browser jobs are configured, not certified passed remotely. |
| Rendered browser/axe | **BLOCKED** | Permitted inventory still shows the same in-app data: error page. Prior explicit URL-policy rejection prohibited indirect/native/alternate-browser workarounds. The known prohibited action was not repeatedly retried. No current screenshot or axe run exists.45 release browser tests collect successfully; collection is not execution. |
| Optional Transformers advisories | **VERIFIED targeted fix and compatibility** | Old4.57.6 had9 scanner records/6 unique IDs. New5.20.2 plus resolver-required hub/tokenizer dependencies passes real FinBERT and complete3.12 regression tests; current combined scan returns0 known advisories with no suppression. This is not arbitrary-artifact or unknown-vulnerability certification. |

Exact diagnostics and current command logs: [evidence directory](docs/verification/post-release), [machine-readable verification](docs/POST_RELEASE_VERIFICATION.json). No external production database was accessed. SQLite results are not substituted for PostgreSQL results.

## 3. Dependency investigation and change

See [full advisory/reachability assessment](docs/TRANSFORMERS_SECURITY_ASSESSMENT.md). Transformer conversion/Trainer/LightGlue/generative save/load utilities are not intentionally invoked by the supported fixed BERT classifier; the shared from_pretrained/config path still requires a trusted cache. No exploit was reproduced and no categorical unreachable-code guarantee is asserted.

Version5.10.0 was considered from advisory fix metadata but rejected after its actual PyPI yanked warning. Candidate5.20.2 was installed in isolation, tested offline against the same cached pinned FinBERT revision and scanned before adoption. Seven inputs including positive/negative/neutral and truncation produced **maximum absolute probability difference0.0** (tolerance1e-5). New pins include hub2.2.0/tokenizers0.23.3 and required HTTP/CLI packages. Default runtime/Docker/demo omit NLP. Python3.12 optional CPU inference is verified; Python3.14 optional inference was not installed/tested.

Current final Python developer+optional lock audit: **zero known advisories**. npm audit: **zero**. Locks are version pinned, not fully wheel-hashed; these results are database snapshots. Old findings remain historical, marked superseded in current docs rather than concealed. Dependency versions participate in model keys; never relabel previous predictions with the new version.

## 4. Exact executed tests and local checks

| Executed check | Actual final result |
|---|---|
| Python3.12 full suite with RUN_FINBERT=1, trusted cached weights, hub offline | **606 passed +11 subtests, zero skips**,89.23s. Includes the formerly optional skipped case; no new backend test was counted. |
| Python3.14 core suite | **605 passed +11 subtests,1 optional skip**,88.84s. Existing TestClient/httpx deprecation warning remains in this environment. |
| FinBERT isolated candidate smoke | **1 passed**,4.38s; seven-input old/new comparison separately passed. |
| Frontend Vitest | **59 passed,8 files**,2.39s. |
| Ruff lint / formatting / mypy | Passed;247 formatted Python files,126 backend source modules checked. |
| Dependency consistency | pip check passed for updated3.12, existing3.14 and clean core environment. |
| Compile/import syntax | compileall passed for backend and scripts. |
| Frontend contracts / lint / format / build | Strict type generation/TypeScript, ESLint, Prettier and production build passed. No application UI code was changed. |
| New browser suite | **45 collected**, not executed:44 route/viewport axe/keyboard/overflow checks plus actual cash/veto presentation check. |
| Infrastructure configuration | Compose configuration and CI YAML parsed/passed applicable static checks. CLI help/missing-Docker preflight checked; runtime commands unexecuted. |

Full commands/logs are archived rather than inferring execution from configuration. Original paper process-death, duplicate fill, risk veto, transaction rollback and replay tests run inside both full suites. No assertions were weakened or removed. New frontend browser checks use no genuine paid fixture; existing genuine-data tests remain preserved and separate.

## 5. Recruiter demo and recovery

**VERIFIED within transport/persistence scope.** Created a new Python3.12 environment, installed runtime lock and editable package, applied migrations through0012, and ran release_demo.py to new paths. A separate fresh frontend copy completed npm ci and production build. The actual clean backend and local production Next service passed **38 HTTP checks** across11 HTML routes and saved feature/model/discovery/optimization/committee/backtest/risk/paper objects.

The new combined synthetic database has **five actual simulated fills**, a separate PAUSED insufficient-tail veto with **zero fills**, and equivalent replay for both. A new API process using the same DB returned identical portfolio values and five fills, then reconciled successfully. The previously verified real pre/post-commit process-death tests were rerun with both suites. M12 backup-restore evidence remains preserved; this pass specifically repeated same-database process restart. Owned API/Next services were stopped and their ports verified closed.

README/DEMO setup commands use normal build isolation, explicit DATABASE_URL, quoted query URLs and correct server-only API_BASE_URL when using alternate8100. No key, GPU or model download is required for the offline demo. Visual charts, keyboard/forms, responsive layouts and screen-reader behavior remain pending rendered checks, not proven by HTTP200 or component tests.

## 6. Infrastructure procedures requiring host participation

Detailed bounded procedures: [DEPLOYMENT.md](DEPLOYMENT.md#minimal-remaining-host-verification-post-release). They are prepared and statically checked, not a runtime pass.

**Docker already enabled on the host; ports8000/3000 free:**

```sh
source .venv/bin/activate
python scripts/verify_infrastructure.py docker
```

Uses a unique disposable Compose project/password, builds/starts/migrates, checks both services, ingests explicitly synthetic data, runs actual paper committee/risk/execution, restarts DB/API/frontend, compares holdings/fills and retries/reconciles. Shuts down only that project and retains any created named volume. No volume deletion/software installation is automatic. The process exits nonzero on failure; do not change assertions to manufacture success.

**Native loopback PostgreSQL already running, authorized local test role, matching Python environment:**

```sh
python -m pip install -r requirements.lock
createdb sentientalpha_verify_test
export TEST_DATABASE_URL='postgresql+psycopg://localhost/sentientalpha_verify_test'
python scripts/verify_infrastructure.py postgres
```

Use fresh empty DBs on3.12 and3.14. The script executes the exact maintained CI PostgreSQL suite, refuses non-loopback/wrong DB names, and existing fixtures refuse any tables. Supply required credentials privately. Tests cover migrations/model compatibility, rollback/constraints, concurrent writes, paper state, risk/committee and replay where implemented. Actual native server restart/operational behavior must additionally be executed; the Docker procedure exercises database restart. Do not point tests at production/user databases.

**Permitted host browser, running combined offline demo and services:**

```sh
cd frontend
npx playwright install chromium
DASHBOARD_URL=http://127.0.0.1:3000 npm run test:e2e -- offline.spec.ts release.spec.ts
```

This is user execution in a permitted environment, not permission to bypass current tool policy. Inspect every axe violation and genuine screenshot, then complete the human checklist in DEMO.md (contrast, screen reader, focus return, modal/invalid/empty/error states, charts/tables and units). Automated success is not full manual accessibility certification. Existing single-session paper.spec.ts uses its separately seeded CI fixture.

**Remote CI:** choose source licensing/materials, then explicitly authorize an intended GitHub repository/remote and any push/publication. This pass does not create one. Once authorized, run the configured push/PR/manual workflow and inspect actual results before changing status. No remote URL or run ID is invented.

## 7. CI preparation

Preserved Python3.12/3.14 matrix and actual PostgreSQL16 service test list (migrations, all subsystem storage, risk, paper rollback/unique/concurrency/replay and release crash tests). Frontend builds/types/lint/tests remain required. CI now seeds the combined offline demo for original offline tests plus45 release render/axe checks, retains the original separate paper fixture/tests, and cleans owned background service processes. Security checks include optional NLP lock scanning without installing heavy model dependencies. Manual workflow dispatch was added. Syntax/collection/local equivalents were checked; **remote CI has not run**.

## 8. Repository hygiene and licensing

**VERIFIED source-path/signature/artifact hygiene within stated checks; licensing PARTIALLY VERIFIED.** Found and redacted machine usernames/absolute paths in27 historical diagnostics. No financial numbers/test outcomes changed. Before/after hashes are in docs/PATH_REDACTIONS.json, and original M12 ZIP remains preserved separately. New evidence is sanitized. No private env, credentials, local DB, venv/node_modules, model cache/weights, compiled object or nested archive is included. Small synthetic generators and curated historical outcome evidence remain. Genuine historical screenshots are identified as historical and require owner content review before publication; no new screenshot was generated.

Dependency license metadata inventories are provided. [LICENSE_REVIEW.md](LICENSE_REVIEW.md) distinguishes original source, dependency notices, model weights/training data, provider data/news and historical media. MIT is a conditional recommendation for original source after ownership review, **not an applied license**. No LICENSE file, blanket model/data redistribution claim or commercial clearance was added. Owner license/material decisions remain before publication. Source signature scans are not exhaustive secret detection or legal clearance.

## 9. Research limitations and truthful presentation

No research result was improved or rewritten. Genuine historical IBM committee **−8.70%** versus buy-and-hold **−4.69%** remains visible. Risk controls reduced reported exposure/losses without establishing alpha. Genuine all-agent historical coverage and reliable tail samples are incomplete, universe survivorship and execution approximation remain, and no long-term forward track record exists.

[PORTFOLIO_PRESENTATION.md](PORTFOLIO_PRESENTATION.md) provides three accurate résumé bullets, a concise project description,60-second interview explanation and5-minute walkthrough. Emphasize reproducible architecture, time-safe ML, optimization, independent governance, transaction recovery and full-stack tests. Do not call it a production-ready AI hedge fund or a profitable prediction system.

## 10. Changes and remaining issues

Changed optional NLP pins/extra metadata; added host verification script,45-case browser suite and CI improvements; updated current README/security/demo/deployment/checklist; created security assessment, license recommendation/inventories and portfolio presentation; redacted27 diagnostic path strings and updated affected evidence hashes. No backend production code or previous tests/migrations changed. Full path/hash/size delta is in the new RELEASE_MANIFEST.json.

Remaining: native PostgreSQL execution/operational checks; actual Linux Docker stack; authorized remote CI; current rendered visual/axe/manual accessibility; source-license/material decision; complete dependency artifact hashes/container digest pins; intended-public-environment auth/isolation/rate controls/monitoring/backup operational certification. No sustained availability/SLA, distributed exactly-once or investment-alpha claim is made. Blocking causes/next actions are specific above; known prohibited approaches were not repeatedly retried.

## 11. Updated source and final classification

New source archive: **SentientAlpha-Post-Release-Verified.zip**, with external DELIVERY sidecar SHA256/size/file count and per-file manifest verification. Original M12 archive is unchanged. ZIP CRC, every archived source hash, prohibited path/signature checks and protected baseline comparisons are verified during packaging. The manifest excludes its own recursive hash and the sidecar records that hash separately. No upload/publication/deployment occurred.

**VERIFIED for owner technical review as a local research/simulation portfolio project. PARTIALLY VERIFIED for eventual public GitHub presentation. BLOCKED for deployment/production certification.** Owner participation is limited to permitted-host infrastructure/browser execution, license/material decisions and any later explicit repository/publication authorization. This targeted pass stops after delivering these artifacts.
