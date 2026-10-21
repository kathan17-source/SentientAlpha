> Historical audit/release record. The owner has now selected All Rights Reserved and authorized a private candidate upload. Current selection and verification supersede earlier pending-decision/upload statements: [publication selection](PUBLICATION_SELECTION.md), [current report](GITHUB_PORTFOLIO_PREPARATION.md). Historical results remain historical.

# Final publication gate — SentientAlpha

**Decision: NOT YET READY FOR PUBLIC REPOSITORY REVIEW**

Verification date:2026-10-21. The implementation passes local checks; the remaining source-publication hold is owner confirmation of ownership, licensing intent and third-party material selection. No new critical code defect was found. Infrastructure/browser gaps remain explicitly unverified. They are important source-review limitations and block deployment certification; public source review and operating a public web service have separate requirements.

## Ownership audit update — current publication assessment

**NOT YET READY FOR PUBLIC REPOSITORY REVIEW.** The remaining human decisions are now explicit in [PUBLICATION_DECISIONS.md](PUBLICATION_DECISIONS.md): D1 authority over original/AI-assisted contributions and any borrowed portions; D2 original-code license or deliberate no-grant intent; D3 actual material selection/permissions; D4 later publication destination/authority. No license or publication action was applied.

The [material audit](THIRD_PARTY_MATERIALS.md) and [proposed public manifest](PUBLIC_REPOSITORY_MANIFEST.md) refine the prior blanket material hold:512 existing files are conditionally retainable,8 need notices/source attribution,7 are recommended for exclusion and 17 remain held. Three historical empty/synthetic screenshots can be proposed with UI/icon rights/notices; five genuine-derived/provider-metadata screenshots remain for D3. A genuine adjusted-close example is actually present in docs/verification/public-provider.json; its public redistribution permission is not established. Three Board headline examples have specific public-domain/source-credit support, subject to item exceptions. No claim that the entire existing ZIP is free of unauthorized content is possible from signature scans alone.

Source ZIP checksum/CRC and all541 archived payload hashes matched; no working source, tests, migrations, calculations, fixtures, negative outcomes or original local material was removed or altered. Only audit documents/inventories and this supplementary gate assessment changed. No tests were rerun for this documentation-only pass; the existing606/605 backend counts,59 frontend tests and38 HTTP checks remain the last executed evidence, not new results.

Public source review can proceed after rights/scope/notice decisions and truthful staging; native PostgreSQL, Docker, remote CI and current browser/accessibility remain unverified and must be disclosed, not passed by implication. A public web service remains separately not ready. Original-code license options do not grant rights in external data/models/dependencies. Routine notice assembly, selected-file staging and link/manifest reconciliation follow your decisions; no new engineering milestone is needed.

The earlier host verification below remains historical evidence; the ownership audit is the current statement of material-selection recommendations.

## Exact baseline and changes

Version **0.12.0**, revision **post-release-verification-2026-10-21**. Source manifest SHA256: `4376b107659d13162f454d990525ca945c2b8f7e3dbf191578075d56947db5a5`. Existing542-file ZIP SHA256: `95ffdfac9d5de691341a86e3dd2454f00ee0fdcce2b0339e4350b37596862900`.

Every manifest file and archive checksum/CRC matched before this pass and again after verification. **No code, dependency, test, migration or existing release document changed.** This report and its [evidence summary](docs/FINAL_PUBLICATION_GATE_EVIDENCE.json) are supplementary additions; the verified source ZIP/manifest remain unchanged. No license, remote, commit, push, publication, deployment or real-money capability was added.

## Executed final checks

| Check | Result |
|---|---|
| Python3.12, full suite with real cached FinBERT enabled/offline | **606 passed +11 subtests**, zero skips,88.87s |
| Python3.14, full core suite with skip reasons | **605 passed +11 subtests,1 skip**,86.18s |
| Frontend | **59 passed**; strict TypeScript, ESLint, formatting and production build passed |
| Backend static checks | Ruff lint/format and mypy126 modules passed |
| Dependency scan | Current developer+optional NLP pins: **0 known advisories**; npm: **0**; no suppressions |
| Demo | New synthetic database; **38 actual Next/FastAPI HTTP checks**; five persisted simulated fills; separate zero-fill risk veto; equivalent replay |
| Restart | New API process on the same DB returned identical portfolio and five fills; reconciliation passed |
| Hygiene | Source signature scan passed; archived paths/bytes rechecked for private env, DB/cache/model/dependency directories, user paths and credential signatures |

The full suites include rollback, unique fills, competing paper commands, risk persistence and real pre/post-commit process-death recovery tests on SQLite. They are not PostgreSQL certification. Both owned services were stopped; ports3000/8100 confirmed closed. Exact evidence hashes are in the summary; executed local logs remain under work/final-gate outside the source release.

**Exact count discrepancy:** `backend/tests/test_finbert_optional.py::test_real_finbert_probabilities_batch_consistency_and_truncation`. Its decorator skips unless `RUN_FINBERT=1`. The3.12 invocation enables it and supplies the trusted model cache;3.14 has RUN_FINBERT/cache unset and no torch/Transformers installed. The3.14 `-rs` output names that test and reason. This is intentional optional-environment coverage, not a failure, missing core test or evidence of Python3.14 incompatibility. No assertion was changed to equalize totals.

## Host verification and severity

| Remaining issue | Severity | Evidence and minimum human action |
|---|---|---|
| Ownership/license intent and publication materials | **Critical publication gate** | No source license or owner material clearance is recorded. Confirm ownership and choose the intended code license **or explicitly choose source-available publication without an open-source grant**. Approve or omit historical images/genuine research exports whose redistribution rights remain unconfirmed. Missing a license file alone is not a finding that publication is unlawful. |
| PostgreSQL runtime | **Important** | Packaged PostgreSQL16.2 binary executes --version. Previous actual disposable initdb fails shmget(size56): Operation not permitted. Same sandbox; initialization was not repeated. Use a permitted host with an already-running local PostgreSQL server and a fresh empty `_test` database, then run the command below on both Python versions. Native restart/operational checks remain unexecuted. No existing/production DB was contacted. |
| Docker runtime | **Important** | No Docker Desktop, CLI in standard paths or daemon sockets. Compose config passed; Compose ps returned Cannot connect to Docker daemon. Enable an approved host Docker installation, then run the bounded host verifier below. No privileged software or settings were changed here. |
| Current rendered browser/axe/manual accessibility | **Important** | Permitted inventory still shows the in-app error-page tab; earlier explicit URL-policy prohibition remains. No repeated forbidden navigation, alternate browser/native workaround, current screenshot or axe execution. Use a permitted host and the command/checklist below. |
| Remote CI | **Important** | Directory is not a Git repository; no authorized remote/runs exist. YAML parses,3.12/3.14 matrix, PG16 service and referenced integration files are valid; frontend/security/browser definitions inspected. After publication approval, establish only the approved repository/visibility/remote, push and inspect actual workflow results. None was triggered here. |
| Full wheel hashes/container digest pins; broader platform/performance evidence | **Optional for source review** | Retain explicit version/platform limits. Before a real deployment, design/validate operational controls separately. |
| Genuine alpha/long forward track record | **Optional for software-source review** | Not established; do not make profitability, production trading or market-prediction claims. Genuine IBM committee −8.70% vs buy-and-hold −4.69% remains unchanged. |

## Security and rights review

Transformers remains pinned at **5.20.2**, with the existing real FinBERT regression passing and a freshly clean version scan. A scanner snapshot does not certify untrusted artifacts. Fixed revision, trusted cache and local-only initialization remain required; core/demo/container omit NLP. No secret or prohibited private artifact was found by the stated checks, which are not exhaustive security certification.

Code rights and data/model rights are separate. The current [official FinBERT card](https://huggingface.co/ProsusAI/finbert) labels weights CC-BY-NC-SA-4.0 and states separate training-corpus terms; weights are not shipped. [Alpha Vantage terms](https://www.alphavantage.co/terms_of_service/) do not grant blanket public redistribution rights for everything obtained through its API. News rights vary. Raw databases/corpora/caches are excluded, but archived genuine outcome evidence and eight historical M10 screenshots still require the owner's publication-material decision. One historical sentiment image was inspected: headlines are withheld under source rights; that is not blanket clearance for all assets or current visual verification.

Frontend source uses declared component/chart/icon dependencies; installed/lock license inventories and [LICENSE_REVIEW.md](LICENSE_REVIEW.md) remain available. No external image/font fetch was found in reviewed frontend app/component code. Metadata is not complete notice/ownership clearance. [MIT](https://opensource.org/license/mit) remains a recommendation for original code after ownership confirmation, not an applied license or permission to relicense model/data material.

## Minimum remaining host commands

From an activated developer environment, with PostgreSQL already running on loopback and an authorized local test role:

```sh
createdb sentientalpha_verify_test
export TEST_DATABASE_URL='postgresql+psycopg://localhost/sentientalpha_verify_test'
python scripts/verify_infrastructure.py postgres
```

Use a fresh empty database for each Python3.12/3.14 run; never a user/production DB. With Docker already enabled and ports8000/3000 free:

```sh
python scripts/verify_infrastructure.py docker
```

This unique-project procedure builds/starts/migrates and exercises simulated fills and DB/service restart, retaining any created volume. Actual host execution remains pending; see [deployment details](DEPLOYMENT.md#minimal-remaining-host-verification-post-release).

With the combined demo and API/Next running in a permitted browser environment:

```sh
cd frontend
npx playwright install chromium
npm run test:e2e -- offline.spec.ts release.spec.ts
```

**Shortest manual checklist:** inspect all11 routes at1440px and390px; tab through navigation/forms/modals and verify visible focus/Escape/focus return; check chart labels, table scrolling, financial units, simulation/synthetic labels; inspect empty sentiment, loading/backend-error states and zero-fill risk veto; inspect console/hydration and axe findings. Current desktop/mobile rendering and accessibility are **unexecuted**, not passed.

## Demo and final disposition

Saved feature, ML, strategy, committee evidence/abstentions, optimization, risk, backtest and paper objects were retrieved through the actual proxy/API. Synthetic mode is explicit; no missing sentiment was fabricated and no negative finding replaced. Transport/persistence verification does not prove current rendered chart/form behavior.

The release remains credible for private technical review and local research/simulation. The critical next step for **public source** is a single owner decision on ownership/licensing and the materials to include; then approve an intended GitHub destination/visibility before any upload. Infrastructure/browser gaps may be disclosed for source review but cannot be described as passed. A publicly accessible service additionally needs authentication/authorization, isolation, operational security, monitoring and tested deployment/recovery; it is **not ready** on this evidence. No further speculative fixes or prohibited retries are scheduled by this report.
