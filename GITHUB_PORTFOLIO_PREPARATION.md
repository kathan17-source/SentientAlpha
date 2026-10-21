# GitHub portfolio preparation — v0.12.0

Date: 2026-10-21. **READY FOR OWNER REVIEW BEFORE PUBLICATION.** This is a private candidate, not approval to make the repository public or deploy it.

## GitHub candidate

- Repository: https://github.com/kathan17-source/SentientAlpha — PRIVATE, verified through authenticated GitHub access.
- Branch: `release-candidate/v0.12.0`; target: `main`. No force push, merge, visibility change, release or deployment is authorized.
- Snapshot commit and private pull request: recorded after upload in the final local copy of this report and the PR. Use `git rev-parse HEAD` for the checkout's exact commit; a report cannot contain its own final commit hash.
- Full uploaded file-level hashes: `PUBLICATION_MANIFEST.json` (excludes itself to avoid a self-hash cycle). Git's tree includes the manifest itself.
- Exclusions: `PUBLICATION_SELECTION.md`, implementing the audit's exact seven recommended exclusions and seventeen held items, plus both environment examples. No source ZIP, private DB, model weights, caches, raw dataset, dependency installation or development Git history is uploaded.

## Rights and security

The existing destination LICENSE is byte-for-byte unchanged and scopes reserved rights to original controlled material. Copyright © 2026 Kathan Patel. All Rights Reserved. No open-source grant is applied. Node metadata is UNLICENSED; installation instructions are limited to owner/separately authorized evaluators.

`THIRD_PARTY_NOTICES.md` and exact upstream notices preserve Next/Vercel, Alembic, openapi-typescript and Lucide/Feather terms. The three retained historical dashboard screenshots show empty/error/synthetic states; five genuine-data screenshots are omitted. Attributed Federal Reserve Board headline examples remain under the documented Board policy. Model weights are external and retain independent restrictions; commercial model use and future binary/container redistribution are not cleared by this preparation.

The held/excluded payloads are absent; historical inventories retain only descriptive paths/hashes. Historical report links to omitted exports are labeled as omissions. No financial results were replaced with invented evidence. Owner review of original authorship and third-party/provider/model obligations remains necessary before public visibility.

The actual staged bytes and complete proposed ancestry are reviewed for configured credential signatures, private key headers, environment files, embedded credentials, private home paths, database/model/archive artifacts and excessive sizes. The existing three destination commits contain only README, LICENSE and ignore rules; their author/committer emails use GitHub noreply addresses. New commits also use the owner's GitHub noreply identity. Attribution contact addresses and explicitly invalid/test-only credential fixtures remain; no real credential was identified. This is a documented signature/manual review, not a guarantee against every possible secret.

The original project and verified ZIP are unchanged: 557 existing source-tree file hashes match the pre-work snapshot. The ZIP SHA-256 remains `95ffdfac9d5de691341a86e3dd2454f00ee0fdcce2b0339e4350b37596862900`. Runtime implementation, migrations and tests are byte-identical to the verified source; changes are documentation, selection, notices, ignore rules and npm rights metadata.

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

A fresh frontend `npm ci` passed. A fresh Python 3.12 virtual environment installed the runtime lock and editable candidate successfully; pip check passed and the imported module resolved to this isolated candidate. No environment example is required; server variables are documented in README.

Local native PostgreSQL remains blocked by macOS shared-memory restrictions; Docker runtime has no daemon. Current rendered browser/axe checks remain unverified under the available tool policy. CI includes disposable PostgreSQL and browser tests, but YAML is not a test pass. Actual remote status will be recorded after push; no blocked check is counted as passed. Container runtime, full accessibility and production security are not certified.

## Portfolio assessment and recommendation

The README provides a one-minute engineering overview, architecture diagram, authorized setup, offline demonstration, environment table and clear rights/limitations. Detailed architecture, methodology, migrations, generators, tests and milestone reports support deeper review. Genuine fundamental/macro/news coverage remains incomplete. The negative IBM finding remains −8.70% versus −4.69% buy-and-hold; robust alpha is not established. Synthetic demonstrations and modeled execution are explicitly labeled.

**READY FOR OWNER REVIEW BEFORE PUBLICATION:** the reviewed private source snapshot is suitable for owner inspection. Public visibility still requires the owner's explicit decision, review of remaining model/provider and redistribution obligations, and acceptance or resolution of documented infrastructure/rendering gaps. No merge, public release, visibility change, deployment or live trading is performed.
