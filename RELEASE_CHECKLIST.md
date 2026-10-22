# v0.12.0 local research/simulation release checklist

Post-release current status: [verification report](POST_RELEASE_VERIFICATION.md). Original M12 counts below remain historical; current3.12 includes real optional inference (606 tests).

- [x] Scope frozen; no new strategy/model/agent/broker.
- [x] Prior 53 test/migration files retained byte-for-byte.
- [x] Python 3.12 and 3.14: 605 passed +11 subtests each, one optional skip each.
- [x] Optional actual cached FinBERT smoke: one passed separately after certifi update.
- [x] Ruff, formatting, mypy (126 modules), pip dependency consistency.
- [x] Frontend: 59 tests, strict types, ESLint, formatting, regular and standalone builds.
- [x] Clean Python runtime/Node install, fresh migrations and combined synthetic demo.
- [x] 38 real HTTP checks; backend outage/error recovery; restored SQLite portfolio/replay.
- [x] Actual child-process death pre/post-commit; exactly one local economic fill on retry.
- [x] Runtime/developer dependency scans and npm scan: zero known advisories.
- [x] Original optional NLP advisories disclosed; post-release patched stack verified without ignore lists.
- [x] Native PostgreSQL attempt, Compose configuration and daemon error recorded honestly.
- [x] CI 3.12/3.14/security configuration parsed; no remote run claimed.
- [x] Current browser policy blocker preserved; no fake screenshots/a11y claims.
- [x] Genuine IBM negative findings and incomplete coverage remain visible.
- [x] Source archive contents/checksums verified; private artifacts excluded.
- [ ] Native PostgreSQL runtime, restart and concurrency certification.
- [ ] Docker image build/start/networking/volume recovery.
- [ ] Authorized remote GitHub Actions execution.
- [ ] Current desktop/laptop/tablet/mobile rendered and axe/manual accessibility review.
- [x] Optional NLP targeted migration, real FinBERT compatibility and zero-known-advisory scan. Arbitrary artifact trust is not certified.
- [ ] Public auth/isolation/rate controls/monitoring/backups/operational validation.
- [ ] Production readiness or established genuine predictive alpha.

Classifications: **Local Research Ready, Local Simulation Ready, Reproducible Demo Ready** within the verified SQLite/core scope. **Deployment Verified: NO. Production Ready: NO.** Checklist archive status refers to the final manifest/sidecar checksum verification, not third-party audit certification. No publication or deployment occurred.


## Post-release owner-review checkpoint

- [x] Original M12 archive/source hash baseline independently matched.
- [x]55 prior test/migration files and all backend production source unchanged.
- [x] Optional NLP patched, isolated compatibility tested,606 total3.12 passes and clean advisory scan.
- [x]27 historical path diagnostics redacted, original archives preserved.
- [x] Host scripts,45 collected browser checks, current report and portfolio/licensing recommendations prepared.
- [ ] Owner executes permitted-host PostgreSQL/container/browser procedures and inspects actual results.
- [ ] Owner confirms material rights/ownership and chooses/applies source license.
- [ ] Owner separately authorizes any GitHub remote, push, release or public deployment.

Current report: [POST_RELEASE_VERIFICATION.md](POST_RELEASE_VERIFICATION.md). No public action is implied by these prepared files.
