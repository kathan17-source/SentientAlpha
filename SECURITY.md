# Security scope and restrictions

**Local single-user research/simulation only. No public deployment approval or production certification.** No brokerage, execution credentials, arbitrary executable strategy language or user model upload is supported. `simulation` and `paper` are the only operating modes. A local process can call the API; Origin/Host checks are not authentication.

## Verified controls

- FastAPI validates typed requests, bounded universes/budgets and literal strategy/model choices. ORM queries use parameters. Reviewed production source has no Python eval/exec, shell=True, dynamic strategy interpreter or unsafe frontend HTML sink.
- The direct API rejects untrusted Host and browser Origin, opaque origins and cross-site fetch metadata. Legitimate local CLI calls without browser Origin remain supported. CORS is not opened broadly.
- The Next proxy selects a fixed server-only upstream; path/mutation allowlists and trusted dashboard origins gate browser mutations. Browser cookies/credentials are not forwarded. Actual streamed request bytes are bounded to 2 MiB before handler/forwarding, including requests without Content-Length. These limits do not cap all CPU/job time across all research routes or authenticate a local user.
- Errors are sanitized; keys/database passwords are hidden from Settings representations. Frontend escapes news/evidence as text. Untrusted news is financial evidence, never instructions to execute tools. No agent is granted a general-purpose shell or brokerage action.
- ML artifacts use validated numerical JSON, not uploaded Python/pickle execution. FinBERT has a fixed repository/revision, trust_remote_code=False and local-only API initialization. These restrictions do not remove library advisories or make an untrusted local cache safe.
- Risk gates, session lifecycle, frozen inputs, database uniqueness and atomic transactions prevent unapproved/duplicate economic effects within the tested SQLite concurrency scope. Pre/post-commit actual process death is tested. No distributed exactly-once or durable internet job service is claimed.
- API/BFF no-store, nosniff, no-referrer; frontend frame denial and disabled camera/microphone/location permissions. Full public CSP, TLS, auth, per-user rate limits and tenancy are not implemented.

## Current dependency findings — post-release 2026-10-21

**VERIFIED:** optional Transformers was updated from4.57.6 to5.20.2 after an isolated real FinBERT test, seven-text old/new probability comparison (maximum difference0.0), full regression run and clean final advisory scan. The associated hub/tokenizer and required dependencies are pinned. Current combined developer/NLP and npm scans report zero known advisories, with no suppressions. See [assessment](docs/TRANSFORMERS_SECURITY_ASSESSMENT.md) and [current verification](POST_RELEASE_VERIFICATION.md).

The M12 report's nine records/six distinct IDs are preserved as a historical finding, resolved in this source revision's version scan. This does not certify arbitrary model loading: fixed repository/revision, trusted offline cache and no user checkpoints remain required. Optional inference was verified on Python3.12 CPU; Python3.14 core still skips the optional model test. The default runtime and container omit NLP.

Source credential checks are signature-based, not exhaustive. Twenty-seven historical diagnostics had machine-specific usernames/paths redacted without changing financial or test outcomes; docs/PATH_REDACTIONS.json records before/after hashes. Original release archives remain separately preserved. No private environments, databases, model weights, node_modules or downloaded raw corpus is included. Dependency locks lack full wheel hashes and container tags lack digest pins; no bit-for-bit or supply-chain certification.

## Operational boundary

Bind host servers to loopback. Do not share the local port through tunnels, reverse proxies, public host bindings or cloud hosting. Keep raw keys in private environment variables and licensed raw research content outside the release. Optional provider failure never silently falls back to synthetic observations. Prompt-like news text cannot override independent risk gates. Do not blindly retry non-idempotent historical research submissions after connection loss; inspect saved runs first. Paper commands use stable idempotency keys.

Report a suspected defect privately to the project owner; no public issue tracker, remote reporting address or security response SLA is configured. Never paste credentials into reports. Review/rotate any exposed key independently if one is discovered later.


## Repository hygiene guard

The source guard scans Git-tracked and visible untracked paths when run in a checkout, including tracked files that ignore rules would hide. It rejects environment examples as well as private environment files, common private configuration/certificates, database sidecars, model/data/archive artifacts, generated dependency/build folders and configured token signatures. Separately downloaded dependencies and caches stay ignored and untracked. Extracted non-Git source uses a filesystem fallback. The guard reports paths rather than matched credential values; it is a preventive signature check, not exhaustive secret detection or a substitute for rights review.

The merged v0.12.0 browser failures remain open. Repository hygiene does not establish browser/accessibility readiness, resolve the publication gate, or authorize public visibility, deployment or live trading.
