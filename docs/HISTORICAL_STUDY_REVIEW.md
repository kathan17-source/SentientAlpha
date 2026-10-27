# Earlier Mac study: evidence review

## Conclusion

A separate local **v0.6.0** code line contains the reported 40-stock study. Its original inputs and written protocol were located; the reported performance has **not been independently reproduced in this review** and is not a v0.12 result. It stays out of the README performance headline. The unsuccessful [IBM committee evaluation](RESEARCH_RESULTS.md) is unchanged.

## Located and checked

The local study is titled `2026-10-14-real-data-validation`. Reviewed materials include `PLAN.md`, `RESULTS.md`, four YAML configurations, `analysis/results_summary.json`, `analysis/verification.json`, independent-analysis scripts, v0.6 ML/selection/execution code and the original database/feature file. No provider rows, model weights or restricted exports are added to this repository.

| Claim | Evidence checked | Assessment |
|---|---|---|
| 40 stocks / about 12.8 years | `core40` config has 40 traded large caps plus eight benchmark/context ETFs. Original SQLite contains 154,272 Yahoo bars, 48 assets, 2014-01-02–2026-10-13 | Input scope confirmed; **12.8 years is data coverage, not the test duration** |
| Original inputs | Database SHA-256 `817d3584f52642d4c011c7f7bc3f3a0c8e77021c291749d6779be21165ae2250`; feature parquet `cb198e40a2d304614103bb56e46a6ffbf9bc330a709b99a544b41e92335d1a39` | Both match the plan; all four configuration hash prefixes also match |
| 18 strategies | Summary contains 18 non-baseline entries in the Holm-adjusted comparison family, with other baselines/control portfolios reported separately | Consistent written comparison count; not 18 independent fresh holdouts |
| EW Sharpe ≈1.54 / SPY ≈1.28 | Stored summary reports 1.53927 / 1.27586 | **Historical reported numbers only**; no underlying evaluated ledger found for recomputation |
| Frozen before evaluation | Plan says frozen; code truncates selection data at validation end and hashes selection before allowing one test-data access | Supports intended software protocol, not independent proof of pre-registration. Plan/results first appear in the same local commit `048cfe5` |
| Genuine OOS | Chronological split and purging are implemented; old verification JSON reports corruption/reproduction checks | Not independently re-executed. Local guard is per experiment, not a global barrier to repeated studies; historical test window is now inspected |
| Reproducible under v0.12 | Old package metadata and failed ingestion experiment identify v0.6.0; different package layout/schema/contracts | No equivalence or v0.12 reproduction established |

The available original database contains only one **failed** ML experiment and **zero backtest runs/daily-ledger rows**. The report explicitly says successful experiments ran on another copy. A filename search including ignored files in the local coding, Downloads and Codex work areas located the original database but not the evaluated copy, model artifacts, prediction parquets or comparator return-series parquets. The summary's exact numbers are inspectable, but fresh ledger, model and leakage reproduction remains unavailable. This does not prove that the copy never existed.

An independent input-only recalculation in this review reconstructed close-to-close total-return indices from prices plus ex-date dividends for all 48 assets and compared them with normalized Yahoo adjusted closes. The maximum relative index difference over all dates/assets was **0.20853%**; SPY's maximum was **0.09185%**. Thus the earlier “±0.2%” description is approximate, not an exact bound. This checks raw-input adjustment consistency, not the missing portfolio ledgers, exact simulated SPY Sharpe or model performance.

## Reconstructed protocol and remaining risks

- Train: **2016-01-04–2021-12-31**. Validation: **2022-02-02–2023-06-30**. Test: **2023-08-02–2026-06-30**, reported 730 sessions, approximately 2.9 years. Configured gaps: 21 sessions. Labels span 1/5/21 sessions; training purging and validation-only calibration/selection are visible in code.
- Configurations specify monthly decisions/next-open fills, long-only portfolios, 0% risk-free convention, 0.5 bp commission, 2 bp half-spread and square-root impact (η=0.1, cap 100 bp). SPY is buy-and-hold, EW rebalances monthly: the common execution engine and aligned dates do **not** make their turnover/construction identical.
- The code uses split-adjusted prices with explicit dividends; old verification reports adjusted-SPY alignment and dividend-sensitive label differences. Without evaluated ledgers/predictions, these reported checks were inspected, not rerun. Ex-date dividend reinvestment and uncalibrated market impact are approximations.
- **Survivorship and hindsight remain:** today's surviving large caps and current sector classifications are projected backward. This can inflate EW and its comparison with SPY; it is not a historical investable-universe test.
- All market inputs were acquired after the evaluated periods. Filing/feature availability logic and old corruption checks help assess temporal ordering, but do not establish contemporaneous capture of historical data revisions. No fresh live/forward evidence is inferred.
- Four truncated SEC registrant histories were fixed **after** the reported experiment. Macro, VIX, risk-free and news coverage were absent. Re-running corrected data would be a new experiment on an already-inspected window.
- Config selection uses validation, and historical analysis reports paired 21-day block bootstrap intervals and Holm correction over 18 comparisons. The report found **no reliable ML skill or statistically distinguishable strategy advantage over EW**. Post-test regime exploration, multiple study attempts and horizon/monthly-holding mismatch constrain interpretation further.

The reported EW–SPY gap is a baseline comparison, not evidence that the multi-agent system generated alpha. A defensible future reproduction requires the exact evaluated copy and artifacts, ledger/adjustment/cost checks, and a separately frozen fresh evaluation. Do not obtain or publish restricted data to fill this gap.
