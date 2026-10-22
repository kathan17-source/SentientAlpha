# M11 adversarial coverage

The42 new paper tests supplement unchanged M1–M10 regressions and actual HTTP/worker demonstrations. Controlled-clock/provider fixtures are not genuine market evidence. Inherited or partial verification is distinguished explicitly.

| Case | Status | Evidence / boundary |
|---|---|---|
| 1. Duplicate market event | VERIFIED | Unique session/day plus competing worker test; no duplicate economic event. |
| 2. Duplicate advance request | VERIFIED | Same-key API/engine retry returns frozen command result. |
| 3. Duplicate order submission | VERIFIED | No arbitrary submission API; stable IDs and database uniqueness tested. |
| 4. Duplicate fill attempt | VERIFIED | Unique one-IOC-fill receipt constraint and frozen replay. |
| 5. Restart after decision | VERIFIED | Injected after_decision rollback and fresh engine recovery. |
| 6. Restart after risk approval | VERIFIED | Injected after_risk rollback and recovery. |
| 7. Restart after fill persistence | VERIFIED | Injected after_fill flush rolls back; separate process recovers committed fills. |
| 8. Restart before checkpoint | VERIFIED | Injected before_checkpoint; partial batch resumes only its planned dates. |
| 9. Concurrency race | VERIFIED | Two actual worker threads, SQLite writer reservation and same command/day. |
| 10. Invalid transitions | VERIFIED | Created cannot start/pause/resume; stopped cannot restart. |
| 11. Paused receiving data | VERIFIED | Actual M1 update while paused preserves portfolio/checkpoint. |
| 12. Stopped trading attempt | VERIFIED | API advance/resume rejected; separate worker preserves STOPPED. |
| 13. Market holiday | VERIFIED inherited calendar boundary | XNYS fixture filters actual sessions; preserved M1/M4 calendar tests. No invented holiday event. |
| 14. Missing execution price/security | VERIFIED | Missing-universe safety pause, M4 missing-price regressions; no fabricated valuation. |
| 15. Delayed provider data | VERIFIED clock fixture | Forward reception-delay and eligibility guards; fixture is modeled, not genuine evidence. |
| 16. Historical backfill as contemporary | VERIFIED | Controlled pre-start catch-up and actual retained IBM zero-order demonstration. |
| 17. Stale observation | VERIFIED | Forward stale fixture; no fill; explicit pause policy. |
| 18. Revised news after decision | PARTIALLY VERIFIED inherited boundary | Preserved M3/M8 future-news/ingestion/frozen-source tests; no genuine paper-news track record. |
| 19. Future-trained forecast | PARTIALLY VERIFIED inherited boundary | Preserved M6/M8 training/effective/generated clocks; paper uses same adapters; no genuine forward forecast demo. |
| 20. Future holdout-selected rule | PARTIALLY VERIFIED inherited boundary | Preserved M7/M8 selection-lock tests; optional return/close paper adapter not exercised on a genuine eligible rule. |
| 21. Risk bypass | VERIFIED | No bypass endpoint; actual foreign/arbitrary mutations rejected; M9 gate mandatory. |
| 22. Pending becomes risk-ineligible | VERIFIED actual demonstration | Fresh fill vetoes retained; rejected orders have no fill receipt. |
| 23. Partial-fill accounting | VERIFIED | Independent M4 numerical case plus actual paper IOC partial/cancel/replay demo. |
| 24. Cash with pending orders | VERIFIED bounded model | Single outstanding batch, M9 pending commitments, M4 cash invariants and multi-asset demonstrations; no extra reservation ledger. |
| 25. Corporate action limitation | VERIFIED refusal; incomplete coverage | Pause on quality/revision flags; no inferred real actions; original M4 supported-action tests retained. |
| 26. Transaction rollback | VERIFIED | All injected stages, unique constraints and unchanged artifact/checkpoint counts. |
| 27. Provider connectivity failure | VERIFIED fault injection | Sanitized failure audit, same-key result, explicit new-key retry; no fabricated prices. |
| 28. Nonfinite valuation | VERIFIED validation boundary | Original M1/M4 finite Decimal guards and risk Frozen finite schemas; paper rejects quality-invalid sources. Not a silently accepted NaN DB record. |
| 29. Missing risk sample | VERIFIED actual demonstration | Required VaR limit yields insufficient-risk safety pause and no fill. |
| 30. Target versus holdings mismatch | VERIFIED | Actual IOC partial fill, separate M5/M9/filled columns and exact ledger reconciliation. |
| 31. Untrusted expression | VERIFIED | Extra strategy expression rejected; closed typed grammar and preserved M7 tests. |
| 32. Malformed API input | VERIFIED | Mode/provider/clock/budget/capital/ticker/extra-field rejection. |
| 33. Unsupported cancellation | VERIFIED | Filled/terminal or absent order cancellation rejected; pending cancellation idempotent. |
| 34. Replay mismatch | VERIFIED | Event/config/order/checkpoint/durable projection integrity; original build required. |
| 35. Historical UI labeled live | VERIFIED component/proxy; browser BLOCKED | Mode helper tests never emit live/brokerage labels. Actual visual browser QA rejected by URL policy. |
