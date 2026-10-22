# A repeatable 5–10 minute engineering demonstration

Run the README's tested clean setup and `scripts/release_demo.py` against a **new** database/report path. The script executes the existing M1/M2/M4–M9 services and creates two M11 sessions in the same database. It refuses existing files. No paid key, NLP download or GPU is needed. IDs/timestamps vary; the fixture and financial operations are deterministic within the documented platform tolerance, not bit-identical database bytes.

**Say first:** “This is a local research/simulation platform. These demonstration prices are synthetic. It has not established predictive alpha.” The genuine earlier IBM committee result was −8.70% against buy-and-hold −4.69%; preserve that result when discussing research quality.

| Time | Actual operation and evidence |
|---|---|
| 0–1 min | Open Overview. Show synthetic provenance, simulation mode and saved experiment catalog. Explain data → features → research → committee → independent risk → M4 ledger → persisted API/dashboard. |
| 1–3 min | Open Security Research (/research) and inspect feature/dataset lineage. Open ML Research (/ml) and a saved model experiment; identify training/validation/calibration/test windows and limitations. Open Strategy Lab (/strategies), show actual candidate outcomes and already-inspected holdout labeling. Do not advertise a profitable winner. |
| 3–5 min | Open Investment Committee (/committee), inspect a saved decision and its evidence/abstentions. Open Portfolio (/portfolio), distinguish optimized proposal weights from actual holdings. Open Risk Center (/risk), inspect actual policy results and insufficient-tail warnings. |
| 5–7 min | Open Paper Trading (/paper). Use demo.json's `paper.session_id` if the veto session is selected first. The normal session has five persisted simulated fills after five events. Inspect orders, fills, cash, actual positions, event clocks and risk. The `risk_veto.session_id` is PAUSED with zero fills because required tail data is insufficient; do not override the gate. |
| 7–8 min | Reconcile the normal session. Pause it, then stop only the owned API/Next processes and restart with the same DATABASE_URL. Verify unchanged cash/positions/fill count before resuming. Stored state is authoritative; reloading the UI must not execute an order. |
| 8–10 min | Inspect Backtesting and Experiment History; explain historical replay versus forward observations. Open Sentiment Intelligence: no eligible news is seeded, so absence is shown honestly. State that native PostgreSQL, Docker runtime, remote CI and current rendered accessibility remain unverified; the optional NLP upgrade passed its advisory/compatibility checks, while arbitrary artifacts remain prohibited. |

Suggested curl inspection (use actual ID from demo.json):

```sh
curl -f http://127.0.0.1:8000/api/paper/sessions
curl -f 'http://127.0.0.1:8000/api/research/catalog?kind=committee'
```

In zsh, quote URLs containing query marks if invoking them directly: `curl -f 'http://127.0.0.1:8000/api/research/catalog?kind=committee'`.

No screenshot is included for M12: permitted browser access was rejected by tool policy. Actual HTTP and component checks do not prove chart layout, keyboard behavior, contrast or screen-reader support. Browser tests/axe configurations are provided for a permitted environment. The presentation should emphasize time safety, evidence, negative findings, independent governance and durable recovery rather than simulated returns.


## Post-release independent execution

A new Python3.12 environment installed the runtime lock and editable source, applied the full migration chain, and generated a new combined database. A separately copied frontend completed clean npm installation/build; the local production frontend and clean backend passed38 real HTTP checks. A new backend process then returned identical portfolio values, five fills and equivalent replay. This is transport/persistence evidence; browser rendering remained unavailable. Core demo remains independent of NLP weights and paid feeds. Do not rerun the seed against the same paths: it intentionally refuses replacement.

For the documented alternate API port8100, start the API with `--port 8100` and set `API_BASE_URL=http://127.0.0.1:8100` on the Next process. Default README commands use8000. All query-string curl URLs in this guide are quoted for zsh.

## Human rendered-review checklist (still pending)

Use Overview, Portfolio, Committee, Strategy Lab, Backtesting, Sentiment, Risk, ML, Security Research, History and Paper routes at1440,1280,820 and390px widths. Inspect actual chart axes/legends, long IDs, horizontal table scrolling, financial units/undefined values and synthetic/simulation labels. Use keyboard-only navigation and visible focus; check field labels, modal opening/cancel/Escape/focus return, invalid inputs and reduced-motion behavior. Inspect empty sentiment, controlled backend error and incompatible-response messages without invented values. Verify the normal paper session's cash against the API; select the PAUSED veto session and inspect its warning/zero fills. Compare proposals with actual holdings and rejected orders with fills. Check screen-reader landmarks/table headers, contrast and console/hydration errors. Record axe violations and manual findings; automated success alone is not full accessibility certification.

[Host commands](DEPLOYMENT.md#minimal-remaining-host-verification-post-release) and [current verification](POST_RELEASE_VERIFICATION.md) distinguish what was run from these pending actions.
