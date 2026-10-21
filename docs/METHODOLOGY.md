# Quantitative specification (planned M2–9; not implemented at M1)

Daily returns are decimal, time in trading sessions; 252 is a configurable annualization
convention. Prices used for fills are raw. Total returns separately account for splits and
cash distributions. Never mix adjusted closes with raw OHLC for fills.

- Simple return: r_t = P_t/P_(t-1) − 1 (corporate-action-safe total-return series for analytics).
- Portfolio equity: E_t = cash_t + sum_i q_(i,t) P_(i,t). Return E_t/E_(t-1) − 1,
  adjusted for any external flows. Trading costs reduce cash, not reported separately from NAV.
- Covariance: sample covariance of synchronous training returns, with train-fitted shrinkage.
  Annual covariance is 252 Σ_daily; vol = sqrt(wᵀΣ_annual w).
- Excess daily return x_t = r_t − r_f,t. Sharpe = sqrt(252) mean(x)/std(x, ddof=1).
  Undefined denominators are null with reason, never infinity or silently zero.
- Sortino = sqrt(252) mean(r−MAR) / sqrt(mean(min(r−MAR,0)^2)); MAR in daily units.
- CAGR = (E_end/E_start)^(252/N) − 1 for N observed return intervals and positive equity.
- Drawdown D_t = E_t / max_(s≤t) E_s − 1; maximum drawdown = −min(D_t).
- Calmar = CAGR / maximum drawdown if drawdown is positive.
- Daily loss L = −r; historical VaR_α = quantile_α(L); CVaR_α = mean(L | L ≥ VaR_α).
  Record quantile convention/sample count; report signed loss quantiles consistently.
- Beta = cov(r_p,r_b)/var(r_b). Alpha is the intercept of excess-return regression;
  report daily intercept and annualized approximation 252α. Align calendars explicitly.
- Information ratio = sqrt(252) mean(r_p−r_b)/std(r_p−r_b).
- Turnover = 0.5 sum_i |w_after,i−w_before,i| including cash; costs instead use actual
  gross traded dollars, avoiding a factor-of-two error.
- Win rate and profit factor use completed round-trip trades net of allocated costs, not
  positive days; profit factor = gross winning P&L / |gross losing P&L|. Define open trades
  and no-loss/no-trade cases explicitly.

## Portfolio construction

Mean-variance: minimize wᵀΣw − λ μᵀw, with Σ and μ on the same horizon.
Include cash: sum_i w_i + w_cash = 1; 0 ≤ w_i ≤ cap_i; w_cash ≥ 0;
sector sums ≤ sector caps; turnover ≤ budget; no leverage. λ is selected on train/validation.
Minimum variance drops the expected-return term. Maximum Sharpe maximizes
(μᵀw−r_f)/sqrt(wᵀΣw). Risk parity targets equal risky-asset contributions
w_i(Σw)_i / sqrt(wᵀΣw), with cash handled separately. Solver success is insufficient:
recheck all constraints and finite outputs. Report infeasibility; never silently relax limits.

Sentiment: μ_adjusted,i,t = μ_base,i,t + βᵀ z_i,t, where z includes train-scaled level,
momentum, surprise, dispersion and log coverage intensity. Fit β with regularized regression
on training pairs (z_t, future return over the specified horizon), purge boundary labels,
choose penalty on validation, freeze for test. This estimates the requested sentiment strength
rather than choosing an attractive constant. Report incremental performance after costs.

## Backtest and discovery protocol

Signal uses only inputs available at decision time; execute no earlier than next eligible
session open. Missing next open means deferred/canceled fill according to fixed policy, never
last-price fill. Cost = commission + abs(quantity)*execution_price*slippage_bps/10000.
Record cash, positions, limits, eligibility time and reason for every fill/rejection.

Chronological train → validation → locked test. Purge all labels crossing split boundaries;
embargo at least the label horizon. Walk-forward refits use only data preceding each fold.
Validation fitness (train generates candidates) is a configurable weighted combination of
Sharpe, Sortino and CAGR, minus drawdown, turnover and AST-node complexity penalties. Freeze
weights before search. Reject low-trade, excessive-turnover and unstable-window strategies
before ranking. Save every attempted candidate, rejection and search budget. Do not optimize
against test or keep rerunning holdout until a favorable result appears.

Agent performance updates only after targets mature; risk constraints override expected
returns. Report all folds, failed candidates and all baselines using identical dates/costs.
Synthetic demos cannot establish predictive skill. Free contemporary datasets usually cannot
remove survivorship, revision and coverage bias; attach these limitations to each experiment.
