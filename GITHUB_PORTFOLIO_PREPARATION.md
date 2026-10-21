# GitHub portfolio preparation — v0.12.0

Date: 2026-10-21. **NOT READY FOR OWNER REVIEW BEFORE PUBLICATION.** This is a private candidate, not approval to make the repository public or deploy it.

## GitHub candidate

- Repository: https://github.com/kathan17-source/SentientAlpha — PRIVATE, verified through authenticated GitHub access.
- Branch: `release-candidate/v0.12.0`; target: `main`. No force push, merge, visibility change, release or deployment is authorized.
- Initial source snapshot commit: `c790de7c77c0d0d26a72c166c9749544d08f82fe`. Private pull request: https://github.com/kathan17-source/SentientAlpha/pull/1 (OPEN into main). Follow-up release-engineering/report commits are part of the same candidate; use `git rev-parse HEAD` for the exact checkout revision. The final local report records the final branch head, avoiding a self-referential commit hash.
- Full uploaded file-level hashes: `PUBLICATION_MANIFEST.json` (excludes itself to avoid a self-hash cycle). Git's tree includes the manifest itself.
- Exclusions: `PUBLICATION_SELECTION.md`, implementing the audit's exact seven recommended exclusions and seventeen held items, plus both environment examples. No source ZIP, private DB, model weights, caches, raw dataset, dependency installation or development Git history is uploaded.

## Rights and security

The existing destination LICENSE is byte-for-byte unchanged and scopes reserved rights to original controlled material. Copyright © 2026 Kathan Patel. All Rights Reserved. No open-source grant is applied. Node metadata is UNLICENSED; installation instructions are limited to owner/separately authorized evaluators.

`THIRD_PARTY_NOTICES.md` and exact upstream notices preserve Next/Vercel, Alembic, openapi-typescript and Lucide/Feather terms. The three retained historical dashboard screenshots show empty/error/synthetic states; five genuine-data screenshots are omitted. Attributed Federal Reserve Board headline examples remain under the documented Board policy. Model weights are external and retain independent restrictions; commercial model use and future binary/container redistribution are not cleared by this preparation.

The held/excluded payloads are absent; historical inventories retain only descriptive paths/hashes. Historical report links to omitted exports are labeled as omissions. No financial results were replaced with invented evidence. Owner review of original authorship and third-party/provider/model obligations remains necessary before public visibility.

The actual staged bytes and complete proposed ancestry are reviewed for configured credential signatures, private key headers, environment files, embedded credentials, private home paths, database/model/archive artifacts and excessive sizes. The existing three destination commits contain only README, LICENSE and ignore rules; their author/committer emails use GitHub noreply addresses. New commits also use the owner's GitHub noreply identity. Attribution contact addresses and explicitly invalid/test-only credential fixtures remain; no real credential was identified. This is a documented signature/manual review, not a guarantee against every possible secret.

The original project and verified ZIP are unchanged: 557 existing source-tree file hashes match the pre-work snapshot. The ZIP SHA-256 remains `95ffdfac9d5de691341a86e3dd2454f00ee0fdcce2b0339e4350b37596862900`. Runtime implementation, migrations and tests are byte-identical to the verified source; changes are documentation, selection, notices, ignore rules, npm rights metadata and optional-dependency type-check configuration.

## Independent candidate verification

| Check | Prior verified release | Cleaned candidate, rerun |
|---|---|---|
| Python 3.12, real optional FinBERT | 606 passed + 11 subtests | 606 passed + 11 subtests; 89.52 s |
| Python 3.14 core | 605 passed + 11 subtests, 1 optional skip | 605 passed + 11 subtests, 1 optional skip; 88.28 s |
| Frontend | 59 tests | 59 tests in 8 files passed |
| Backend static checks | Passed | Ruff lint/format and mypy passed; 126 typed source files |
| Frontend static/build | Passed | Type generation/TypeScript, ESLint, Prettier and production build passed |
| OpenAPI generation | Matched | Regenerated output matches source |
| Migrations | SQLite full chain | Demo applied through 0012; alembic check reports no new upgrade operations |
| Offline demo | Five fills; zero-fill veto | Five fills, separate PAUSED zero-fill veto, both replay equivalent |
| Actual HTTP | 38 checks | 38 checks through production Next proxy/API passed |
| Restart persistence | Passed | New API process: exact portfolio equality, five fills, equivalent replay |
| Python advisory scans | No known advisories | Core/developer and optional NLP lock scans: no known vulnerabilities |
| npm advisory scan | Zero | Zero vulnerabilities in installed lockfile audit |
| Credential/private artifact guard | Passed | Passed after keeping generated test DBs outside candidate |

Backend tests ran with candidate `PYTHONPATH=backend`, including actual process-death/idempotency regression tests. Python 3.12 used the separately cached pinned FinBERT; weights were not copied. Python 3.14 intentionally skips `test_real_finbert_probabilities_batch_consistency_and_truncation` without the optional stack. Its single Starlette/httpx deprecation warning is retained. Tests and financial assertions were not modified.

A fresh frontend `npm ci` passed. A second offline demo also passed in the newly installed minimal Python runtime: five fills, separate PAUSED zero-fill risk veto and equivalent replay, without optional NLP packages. A fresh Python 3.12 virtual environment installed the runtime lock and editable candidate successfully; pip check passed and the imported module resolved to this isolated candidate. No environment example is required; server variables are documented in README.

Local native PostgreSQL remains blocked by macOS shared-memory restrictions; Docker runtime has no daemon. Current rendered browser/axe checks remain unverified under the available tool policy. CI includes disposable PostgreSQL and browser tests, but YAML is not a test pass. The initial remote run 39689937470 passed its security job but both backend jobs stopped at mypy because the optional torch/transformers packages are absent in core-only CI. A narrow ignore-missing-imports override for those two optional libraries corrects the release-check configuration; no runtime code or test assertion changed. Final rerun status is recorded in the final local report; no blocked check is counted as passed. Container runtime, full accessibility and production security are not certified.

## Portfolio assessment and recommendation

The README provides a one-minute engineering overview, architecture diagram, authorized setup, offline demonstration, environment table and clear rights/limitations. Detailed architecture, methodology, migrations, generators, tests and milestone reports support deeper review. Genuine fundamental/macro/news coverage remains incomplete. The negative IBM finding remains −8.70% versus −4.69% buy-and-hold; robust alpha is not established. Synthetic demonstrations and modeled execution are explicitly labeled.

**NOT READY FOR OWNER REVIEW BEFORE PUBLICATION:** the private source upload and rights/security preparation are complete, but actual browser CI has failed. Resolve and rerun the failing rendered checks before advancing the publication gate. The source and open PR remain available for private owner inspection. Public visibility still requires the owner's explicit decision, review of remaining model/provider and redistribution obligations, and acceptance or resolution of documented infrastructure/rendering gaps. No merge, public release, visibility change, deployment or live trading is performed.


## Actual remote CI — application/configuration revision 4a2bfeb8e482c0cc003ca48e0bdd9d54a1a2454b

Push run: https://github.com/kathan17-source/SentientAlpha/actions/runs/39690184592 . PR run: https://github.com/kathan17-source/SentientAlpha/actions/runs/39690191315 . The two obsolete initial runs were cancelled after their missing-optional-import type failures; those failures remain recorded. The correction is limited to mypy's absent optional torch/transformers imports and passed locally with and without the NLP stack.

- **Python 3.12 CI passed:** 605 core tests + 11 subtests, one optional-model skip; actual PostgreSQL 16 integration: 198 passed, 2 skipped. Core runtime has no NLP weights.
- **Python 3.14 CI passed:** 605 core tests + 11 subtests, one optional-model skip; actual PostgreSQL 16 integration: 198 passed, 2 skipped.
- The two PostgreSQL skips are SQLite-specific process-death tests; they passed in the full SQLite suites. PostgreSQL process-kill recovery is not thereby certified.
- Both Python jobs also passed dependency consistency, lint, format, mypy and Docker Compose static configuration. Docker application-image runtime/restart remains unverified.
- **Remote security passed:** runtime/developer lock, optional NLP lock, npm audit and source credential guard.
- Frontend installation, generated API match, type checking, lint, format, 59 component tests and production build passed remotely. **Rendered browser checks failed**; 49 combined offline/release browser tests completed: 4 passed, 45 failed. Full details follow below. The standalone paper-browser step is downstream and is not claimed as executed.

These actual failures supersede earlier 'browser unverified' wording for the hosted environment. Local browser policy restrictions and manual accessibility/review gaps still apply. Existing tests, UI implementation and financial assertions are preserved rather than altered to improve a pass count. Publication is blocked on reviewing the browser failures and obtaining a meaningful green rerun. The final report-only commit uses [skip ci] to avoid rerunning unchanged application tests; it does not clear or conceal the recorded failed application revision.


### Completed browser failure inventory

Both current push and PR workflows concluded **FAILURE** because of the frontend browser job. The 49-test combined suite completed with **4 passed, 45 failed** (11.8 minutes in the push run):

- 40 release-route checks (10 routes at four widths) timed out matching exact text `Backend connected`. The shared status container also contains the Simulation badge, so the locator/markup contract needs review. HTTP success is separately established; this error alone does not prove backend unavailability.
- Four portfolio-route checks failed because `locator('h1')` matched two headings: the top-level portfolio page and its numerical allocation subsection. Heading hierarchy and test intent need review.
- One offline sentiment/locked-mode check could not match exact text `Simulation only`; the label shares a container with `LOCKED`. The no-news assertion preceding it passed.
- The three initial offline data/research checks and the release paper cash/veto display check passed.

All 44 route checks stop before their keyboard/overflow/axe assertions. **No axe or responsive-layout pass is claimed**, and no count of accessibility violations is inferred from these early failures. The later standalone three-test paper suite was not run because its preceding workflow step failed. CI screenshots/traces were created on ephemeral runners but the existing workflow does not upload them; this preparation does not invent or republish those images. Detailed failed-call logs remain in the linked private workflow.

Next publication-gate action: resolve the label/locator contracts and portfolio heading hierarchy, then rerun the complete existing browser coverage, including actual axe/layout checks and standalone paper interactions. Do not delete assertions or count unexecuted cases as passes. This release-engineering snapshot deliberately preserves the original UI/tests and negative results rather than expanding into a new implementation milestone.
