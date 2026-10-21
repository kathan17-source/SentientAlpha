# M9 adversarial verification map

All references below are executable tests in `backend/tests/test_risk_math.py` (M) or `test_risk_integration.py` (I), not mocked production evidence. Math fixtures are explicitly synthetic. I tests use actual SQLite, M8, M4 and FastAPI with generated synthetic sources; injected failures/forwarding are deliberate adversarial interventions. Genuine market experiments are reported separately.

| Requested case | Test/evidence |
|---|---|
| 1 Security cap | M `test_hard_limits_never_fail_open` concentration parameter; I actual committee reduction |
| 2 Combined sector cap | M hard-limits sector parameter sums multiple assets |
| 3 Volatility cap | M hard-limits volatility parameter |
| 4 VaR cap | M hard-limits VaR parameter |
| 5 CVaR cap | M hard-limits CVaR parameter |
| 6 Thin tails | M `test_missing_tail_history_rejects_required_risk`; genuine IBM remains unreliable |
| 7 Cash overcommitment | M `test_explicit_orders_check_cash_and_negative_holdings`; pending-buy test |
| 8 Missing/stale quote | M parametrized `test_missing_stale_or_incompatible_quotes_reject` |
| 9 Participation | M hard-limits participation parameter |
| 10 Realized drawdown breach | M `test_drawdown_is_past_realized_path_and_latches_until_explicit_recovery`; actual genuine drawdown-policy/M4 run |
| 11 Reduction creates another cap breach | M `test_reduction_or_fees_cannot_create_another_concentration_breach` |
| 12 Singular covariance | M `test_singular_covariance_and_perfect_correlation_are_not_hidden_by_regularization` |
| 13 Nearly perfect correlation | M `test_nearly_correlated_and_zero_volatility_inputs_have_explicit_outcomes` |
| 14 Cash only | M `test_cash_only_is_exact_zero_risk_without_fabricated_covariance` |
| 15 Zero variance | M nearly-correlated/zero-volatility test |
| 16 NaN/infinity | M `test_policy_code_nan_future_versions_and_unsupported_units_rejected`; frozen contracts forbid nonfinite values |
| 17 Committee override | I `test_target_consensus_and_accidental_forwarding_cannot_bypass_fill_veto` |
| 18 Rejected target forwarded | I same test bypasses target check deliberately; M4 fills remain empty |
| 19 New rejected request identifier | I `test_real_api_policies_idempotency_historical_cutoffs_and_replay`; same mathematical decision reused |
| 20 Later policy | M `test_later_policy_effective_time_cannot_govern_earlier_state`; I frozen-policy version/tamper test |
| 21 Future returns | M `test_future_returns_never_change_prior_var` |
| 22 Later revision | I `test_frozen_risk_survives_later_policy_and_data_revision_and_detects_tampering`; frozen original replay unchanged, mutation rejected |
| 23 Nonfinite stress | M `test_stress_uses_declared_shocks_and_contributions_not_predictions` rejects infinite shock; scenario output has finite guard |
| 24 Adjustment basis mismatch | M quote-adversary adjusted price and `test_adjusted_returns_and_missing_sector_classifications_fail_closed` |
| 25 Combined constraints after adjustment | M `test_scaled_allocation_passes_complete_policy_not_individual_clipping` |
| 26 Required unavailable measure | M missing-tail, adjusted/missing-sector, singular configured-volatility cases |
| 27 Partial fills | I `test_partial_fills_post_monitor_uses_actual_not_theoretical_weights`; actual closing weights reconciled to M4 |
| 28 Future peak/trough | M drawdown latch test rejects future equity and uses prior peak only |
| 29 Alert duplication | I real API/idempotency test verifies unchanged alert count after repeated requests and new identifier |
| 30 Unsafe/malformed policy | M strict configuration test plus API extra-field rejection and immutable version409 |

Additional checks cover exact fractional tail mass/ties/signed gains, hand covariance/risk contributions, actual benchmark beta/TE, historical scenario exact eligible coverage, chronological exception diagnostics, pending buys versus unfilled sale proceeds, transactional rollback and linked parent/standalone replay. Existing M1–M8 tests remain byte-identical; no prior migration or regression test was weakened.
