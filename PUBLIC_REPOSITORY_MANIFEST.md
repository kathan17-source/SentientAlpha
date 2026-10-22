> Historical audit/release record. The owner has now selected All Rights Reserved and authorized a private candidate upload. Current selection and verification supersede earlier pending-decision/upload statements: [publication selection](PUBLICATION_SELECTION.md), [current report](GITHUB_PORTFOLIO_PREPARATION.md). Historical results remain historical.

# Proposed public repository manifest

**Proposal only. No public package was built, no file was removed and no permission was inferred.** Existing verified archive:542 entries, SHA256 `95ffdfac9d5de691341a86e3dd2454f00ee0fdcce2b0339e4350b37596862900`. There is no Git tracked index; archived files plus two gate supplements were inventoried individually.

[Machine-readable selection and hashes](docs/ownership-audit/PROPOSED_PUBLIC_FILES.json) classifies 544 existing files into 512 conditional includes, 8 notice/source-attribution includes, 7 recommended exclusions and 17 held items. The audit's new Markdown/JSON documents are supplementary review artifacts, not silently added to that old archive; confirm their inclusion under D1/D2 when constructing a future release. This file does not grant redistribution rights.

## Include after D1/D2 confirmation

- backend source/tests; frontend app/components/lib/tests/e2e; scripts; config; migration chain; safe sample environments; project Docker/CI/build configuration.
- Dependency manifests/locks, API schemas/types, deterministic synthetic generators and small authored fixtures.
- README/architecture/methodology/research reports, security/deployment/demo instructions and selected sanitized verification summaries. Preserve all negative research conclusions and distinguish genuine from synthetic observations.
- Framework-derived scaffolds/generated declarations and permitted Board examples only with applicable attribution/notice treatment. Original-code licensing cannot remove upstream notices.

The exact 512-file conditional list and 8 notice/attribution paths are in the JSON. A KEEP recommendation always remains conditional on actual project rights; it is not a declaration that all code belongs exclusively to the user.

## Recommended exclusions from the future public selection

- `docs/M5_FROZEN_DEMO.json`
- `docs/M6_BENCHMARK_20.json`
- `docs/M6_BENCHMARK_5.json`
- `docs/M6_BENCHMARK_50.json`
- `docs/M6_FROZEN_DEMO.json`
- `docs/M6_SYNTHETIC_SENTIMENT.json`
- `docs/verification/public-provider.json`

The first is a genuine provider numeric example with no established redistribution permission. The other six are bulky explicitly synthetic generated artifacts, unnecessary when generators/tests are retained. Exclusion is a proposed packaging choice, not deletion or a change to working fixtures.

## Withhold pending D3 permission/material review

- `docs/M3_ALPHA_REAL_PIPELINE.json`
- `docs/M5_REAL_IBM.json`
- `docs/M6_REAL_IBM.json`
- `docs/M9_RESEARCH_EVIDENCE.json`
- `docs/REAL_IBM_FEATURE_CHECK.json`
- `docs/VERIFICATION_M4.json`
- `docs/VERIFICATION_M5.json`
- `docs/VERIFICATION_M6.json`
- `docs/VERIFICATION_M7.json`
- `docs/VERIFICATION_M8.json`
- `docs/VERIFICATION_M9.json`
- `docs/screenshots/milestone10/committee-desktop.png`
- `docs/screenshots/milestone10/overview-desktop.png`
- `docs/screenshots/milestone10/responsive-390.png`
- `docs/screenshots/milestone10/risk-desktop.png`
- `docs/screenshots/milestone10/sentiment-genuine.png`
- `docs/verification/milestone11/genuine-catchup.json`

These are optional genuine/mixed exports and genuine-derived/provider-metadata images. Withholding them is conservative handling of uncertain rights, not an assertion they are necessarily unlawful. Computed facts/metrics and source material can have different rights; no universal legal conclusion is made. Written negative findings remain included. Three other historical empty/synthetic PNGs are in the notice-qualified list; they are not current-release screenshots.

## Always keep outside the public source payload

Private .env/keys; local .db/.sqlite databases; downloaded raw data/news; model weights/tokenizer caches; virtual environments; node_modules; .next/build/binary bundles; test result dumps/traces and sensitive logs; model/provider caches; nested old ZIPs/DELIVERY paths. Optional installation instructions and hash metadata are different from shipping the corresponding bytes.

## .gitignore and packaging audit

Current .gitignore covers private .env (except .env.example), .venv, node_modules, .next, DB/WAL files, Python/type caches, build/dist, coverage and frontend browser results. It is **not a rights filter**, does not remove previously tracked files and does not address every possible model/raw-data extension or folder. No Git history/index exists to verify tracking. Existing release packaging successfully excluded installed dependencies/models/DB/env/cache outputs; its rights-based selection was not exhaustive: the genuine adjusted-close example and historical media are actually present.

No ignore rule or packaging behavior was changed. After D3, use an exact allowlist rather than broad add-all. Recommended supplemental patterns, tailored to actual future directories: data/raw/, model-cache/, .cache/, logs/, *.sqlite, *.sqlite3, *.safetensors, *.pt, *.pth and raw-provider response files. Do not broadly ignore every JSON/CSV or test fixture: schema/fixture inputs may be essential. Never infer file inclusion safety from filename extensions alone.

## Required staging checks after owner approval

1. Copy approved paths into a **new staging directory**, retaining local originals and the existing release ZIP.
2. Assemble accurate upstream notices from the versions actually represented; apply only the owner-approved code grant, scoped separately from data/models.
3. Reconcile documentation references to omitted files. Some historical reports link to excluded/held artifacts; annotate unbundled evidence and preserve conclusions instead of creating broken links or inventing replacement results. This proposal is **not link-closed** and must not be described as a final publication build.
4. Regenerate a separate public manifest, path hashes and candidate archive; do not overwrite historical manifests/archives or imply identical hashes.
5. Scan exact staged/archive contents for credentials, personal paths, private data, unintended binaries and unapproved material. Recheck links and documented offline demo as needed; existing engineering tests are unchanged by this audit.
6. Show the concrete staging set/license/notice text for review before a separately authorized upload. Do not publish or deploy from these recommendations alone.

## Two independent readiness assessments

**A. Public GitHub source: not yet approved.** D1 ownership/authority, D2 licensing intent, D3 actual material scope/notice compliance and D4 destination/upload authority remain. The application has strong local test evidence; PostgreSQL/Docker/CI/browser gaps must be disclosed, but are not automatic barriers to publishing honest source once rights/scope are resolved.

**B. Publicly hosted application: not ready.** Native PostgreSQL, actual Docker runtime, remote CI and current rendered/accessibility checks remain unverified. Authentication/authorization/isolation, operational controls and intended-environment recovery also remain uncertified. Public-source permission is never permission to expose the application as a service or enable real-money execution.
