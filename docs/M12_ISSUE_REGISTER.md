# Prioritized release issue register

Historical M12 snapshot; current post-release resolutions and remaining blockers are in [POST_RELEASE_VERIFICATION.md](../POST_RELEASE_VERIFICATION.md).
| Priority | Finding | Disposition / evidence |
|---|---|---|
| P1 | Direct unauthenticated API lacked browser Origin/Host checks | FIXED: TrustedHost and LocalBoundary; untrusted Origin/opaque origin/cross-site metadata denied before handler |
| P1 | BFF read entire chunked body before size check | FIXED: count streamed bytes before decode/forward; backend same 2 MiB bound |
| P1 | Process dies after durable fill, before acknowledgement | VERIFIED: new subprocess os._exit(73) before and after commit; retry yields exactly one fill, identical portfolio |
| P1 | Optional Transformers 4.57.6 advisories | OPEN: nine advisory records, six distinct IDs; blocks untrusted model artifacts/public NLP deployment. Default runtime/demo omits NLP. No ignore-list or silent major upgrade |
| P1 | No authentication/tenant isolation | OUT OF SCOPE, blocks public/multi-user exposure. Bind loopback; browser protections do not authenticate local processes |
| P2 | Certifi 2026.7.22 in dev/NLP locks | FIXED: 2026.10.19, installed and optional inference retested; runtime did not include it |
| P2 | Healthy old session paused using start time | FIXED: last successful processing time used, start time only before first event; clock-controlled freshness/staleness regression |
| P2 | Compose missing frontend | FIXED configuration: minimal Node standalone image, internal API destination and loopback host mapping; runtime BLOCKED by daemon |
| P2 | CI only Python 3.12 and no advisory/credential guard | FIXED configuration: 3.12/3.14 matrix, pip-audit/npm audit/source guard; remote unexecuted |
| P2 | PostgreSQL never actually executed | BLOCKED: native initdb shared memory Operation not permitted; disposable PostgreSQL CI commands supplied |
| P2 | Current visual/axe evidence missing | BLOCKED: permitted CUA access rejected URL policy; no alternate browser bypass or fabricated screenshot |
| P2 | No authorized remote CI | BLOCKED: source delivery has no Git repository/remote; no publication authorized |
| P3 | Runtime TestClient httpx deprecation | OPEN: existing warning, tests pass; migrate test client in a later compatibility change |
| P3 | OS-level disk-full, sustained service availability, load/SLA | NOT VERIFIED: transaction fault tests are not actual disk exhaustion or operational certification |
| P3 | Pinned locks lack artifact hashes; container tags not digest pinned | OPEN: version reproducibility only, not bit-for-bit or supply-chain certification |

Advisory snapshot in verification/milestone12/pip-audit-all-final.json. The scanner emits duplicate advisory IDs from its upstream database; counts must not be read as nine unique defects. Root cause/reproduction and deployment impact also appear in MILESTONE12_REPORT.md and DEPLOYMENT.md.
