# A repeatable 5–10 minute engineering demonstration

For the owner or separately authorized evaluators under [LICENSE](LICENSE): follow the [README setup](README.md#installation-and-offline-demonstration) and run `scripts/release_demo.py` against a **new** database/report path. The script executes the research, committee, risk and simulated accounting services and creates two paper sessions in the same database. It refuses existing files. No paid key, NLP download or GPU is needed. IDs/timestamps vary; the fixture and financial operations are deterministic within the documented platform tolerance, not bit-identical database bytes.

**Say first:** “This is a local research/simulation platform. These demonstration prices are synthetic. It has not established predictive alpha.” The genuine earlier IBM committee result was −8.70% against buy-and-hold −4.69%; preserve that result when discussing research quality.

| Time     | Actual operation and evidence                                                                                                                                                                                                                                                                                                                                                     |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0–1 min  | Open Overview. Show synthetic provenance, simulation mode and saved experiment catalog. Explain data → features → research → committee → independent risk → M4 ledger → persisted API/dashboard.                                                                                                                                                                                  |
| 1–3 min  | Open Security Research (/research) and inspect feature/dataset lineage. Open ML Research (/ml) and a saved model experiment; identify training/validation/calibration/test windows and limitations. Open Strategy Lab (/strategies), show actual candidate outcomes and already-inspected holdout labeling. Do not advertise a profitable winner.                                 |
| 3–5 min  | Open Investment Committee (/committee), inspect a saved decision and its evidence/abstentions. Open Portfolio (/portfolio), distinguish optimized proposal weights from actual holdings. Open Risk Center (/risk), inspect actual policy results and insufficient-tail warnings.                                                                                                  |
| 5–7 min  | Open Paper Trading (/paper). Use demo.json's `paper.session_id` if the veto session is selected first. The normal session has five persisted simulated fills after five events. Inspect orders, fills, cash, actual positions, event clocks and risk. The `risk_veto.session_id` is PAUSED with zero fills because required tail data is insufficient; do not override the gate.  |
| 7–8 min  | Reconcile the normal session. Pause it, then stop only the owned API/Next processes and restart with the same DATABASE_URL. Verify unchanged cash/positions/fill count before resuming. Stored state is authoritative; reloading the UI must not execute an order.                                                                                                                |
| 8–10 min | Inspect Backtesting and Experiment History; explain historical replay versus forward observations. Open Sentiment Intelligence: no eligible news is seeded, so absence is shown honestly. Distinguish passing hosted PostgreSQL/browser checks from unverified Docker application runtime, full manual accessibility and deployment. Optional NLP/model terms remain independent. |

Suggested curl inspection (use actual ID from demo.json):

```sh
curl -f http://127.0.0.1:8000/api/paper/sessions
curl -f 'http://127.0.0.1:8000/api/research/catalog?kind=committee'
```

In zsh, quote URLs containing query marks as shown above.

## Committee coverage

The baseline synthetic fixture has only the technical adapter participating per asset. Five other agent types honestly abstain:

| Agent               | Missing eligible evidence                                                                                      |
| ------------------- | -------------------------------------------------------------------------------------------------------------- |
| Sentiment           | No cached news feature; absence is not a neutral sentiment score                                               |
| Quant               | No unique original forecast for the decision session; a model ID alone does not supply matching-date forecasts |
| Strategy            | No existing selected M7 strategy configured into the committee request                                         |
| Fundamental / macro | No point-in-time statements or vintages configured; these replay adapters explicitly abstain                   |

The verified baseline generated 70 retained decisions: 60 committee replay decisions plus ten across the two five-event paper sessions. Across 140 asset-decisions, technical returned 69 positive, 65 negative and six neutral recommendations; each other agent type returned 140 insufficient-data recommendations. IDs and timestamps vary between runs.

Inspect each card's evidence, clocks and dependencies rather than presenting six cards as six independent investment opinions. Recognized technical/sentiment heuristic explanations display six significant digits; the evidence inspector retains exact stored prose and numerical records. Signal strength is a heuristic, not calibrated confidence or expected return.

A richer synthetic fixture would need eligible cached-news features, matching-date forecasts and a selected strategy, with temporal/dependency and independent risk tests. Fundamental/macro participation requires additional adapter work. That remains separate work; no agent conclusion, genuine research outcome or risk veto is overridden in this demo.

## Synthetic behavior and recovery

All demo prices and fills are generated; displayed returns do not establish market skill. The normal session has five persisted fills. The separate PAUSED session has zero fills because required tail evidence is insufficient. Select each session explicitly using the IDs in `demo.json` and compare cash, positions, fills and risk records.

Reconciliation/replay should preserve equivalent state. Pausing and restarting the owned API/Next processes with the same `DATABASE_URL` must retain cash, holdings and fills; a page reload must not place an order. Hosted paper browser checks verify pause persistence after reload. Full Docker runtime/restart remains unverified.

The [actual browser screenshots and reproduction steps](docs/PORTFOLIO_REVIEW.md#screenshot-provenance) use the same synthetic fixture. [Verification](docs/VERIFICATION.md) records executed checks and remaining operational limits.

For an alternate API port, use the chosen `--port` and set the matching loopback `API_BASE_URL` on Next; defaults use 8000. Keep `DASHBOARD_ORIGINS` and host allowlists consistent with your local ports. Stop only processes you started and never reseed existing output paths.

## Further manual accessibility review

Use Overview, Portfolio, Committee, Strategy Lab, Backtesting, Sentiment, Risk, ML, Security Research, History and Paper routes at 1440, 1280, 820 and 390 px widths. Inspect actual chart axes/legends, long IDs, horizontal table scrolling, financial units/undefined values and synthetic/simulation labels. Use keyboard-only navigation and visible focus; check field labels, modal opening/cancel/Escape/focus return, invalid inputs and reduced-motion behavior. Inspect empty sentiment, controlled backend error and incompatible-response messages without invented values. Verify the normal paper session's cash against the API; select the PAUSED veto session and inspect its warning/zero fills. Compare proposals with actual holdings and rejected orders with fills. Check screen-reader landmarks/table headers, contrast and console/hydration errors. Record axe violations and manual findings; automated success alone is not full accessibility certification.

[Host commands](DEPLOYMENT.md#minimal-remaining-host-verification-post-release) and [current verification](docs/VERIFICATION.md) distinguish what was run from these pending actions.
