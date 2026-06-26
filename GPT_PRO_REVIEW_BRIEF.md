# GPT Pro Review Brief

Project identity:

- Local path: `C:\Users\WHR\Documents\策略迭代`
- GitHub repository: `https://github.com/yw9522872-debug/btc-strategy-iteration-20260627`
- GitHub purpose: BTC strategy iteration research only.
- Do not mix this repository with other Codex/Chrome/GPT Pro threads.
- If discussing this repo in ChatGPT, start the prompt with this local path and the GitHub repository URL.

Hard requirements:

- BTC 15m strategy research.
- 2025 historical return must be greater than 100%.
- 2026 available-data return must be greater than 100%.
- No future function: signal at bar `t` can use only bar `t` closed data and earlier, and participates from bar `t+1`.
- Market open+close total fee is 0.2%, modeled here as `COST_PER_SIDE = 0.001`.
- Every evaluated 2025/2026 month must be profitable.
- Every evaluated month must have at least 10 real orders/side changes.
- Research only. No live orders, no API keys, no supervisor.

Important current results:

- `CURRENT_STRATEGY_FREEZE.md`
  - Current frozen research candidate.
  - Machine-readable freeze file: `artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json`.
  - Freeze id: `monthly_profit_lock_research_freeze_20260627`.
  - Do not edit this frozen strategy in place; create a new freeze id for parameter, rule, cost, or data changes.

- `artifacts/event_entry_v2_alpha_source_robustness_review_20260625/summary.json`
  - Existing robust static candidate has 2025 and 2026 returns above 100%.
  - It fails the new task because it has losing months and too few trades.

- `artifacts/ultimate_monthly_search_20260626/summary.json`
  - Closed-bar rule scan with 0.2% round-trip fee.
  - `hard_pass_rows = 0`.

- `artifacts/hgb_in_sample_upper_bound_20260626/summary.json`
  - This is a leaky upper bound, not a valid strategy.
  - It trains on full-sample future labels and evaluates on the same sample.
  - Do not treat this result as success.

- `artifacts/online_expert_pool_20260627/summary.json`
  - Strict online current-month expert following.
  - No future function by construction.
  - `hard_pass_rows = 0`; best result is negative for 2025 and 2026.

- `artifacts/zscore_rsi_trend_20260627/summary.json`
  - Z-score / RSI / trend rule scan from a worker.
  - Review this file before suggesting extensions.

- `artifacts/walkforward_hgb_strict_20260627/summary.json`
  - Strict monthly expanding walk-forward HGB.
  - Training rows require label availability before the prediction month starts.
  - `hard_pass_rows = 0`.

- `artifacts/expert_pool_bounds_20260627/summary.json`
  - Expert-pool upper-bound and strict selector tests.
  - Monthly posthoc oracle can pass, but `strict_no_future = false`.
  - Best strict tradeable selector still fails; `strict_pass_rows = 0`.

- `artifacts/monthly_profit_lock_20260627/summary.json`
  - First historical hard-pass candidate found.
  - `hard_pass_rows = 24`.
  - Best candidate: fixed `ret_state` expert, window 64, threshold 100 bps, leverage 8.
  - Causal monthly lock: after at least 10 real orders and current month net return reaches lock, go flat for the rest of the month.
  - Causal quota-completion mode: after current month log return reaches 0.12 but before 10 orders are complete, reduce notional exposure to 0.1x until the 10-order quota is met.
  - 2025 return: 326.26%; 2026 return: 106.93%; worst evaluated month: +7.38%; minimum monthly orders: 12.
  - Important caveat: parameter selection is posthoc research selection over the historical file. This is not a live guarantee.

- `artifacts/profit_lock_overfit_validation_20260627/summary.json`
  - Fixed historical hard-pass parameters still reproduce the historical hard pass.
  - Fixed-parameter full-history result: 2025 return 326.26%; 2026 return 106.93%; worst evaluated month +7.38%; minimum monthly orders 12.
  - A stricter within-expert check selected lock/quota parameters using only 2024, then evaluated 2025/2026.
  - The 2024-selected parameters did not meet the target: 2025 return 88.38%; 2026 return 41.66%; no losing evaluated months; minimum monthly orders 12.
  - Latest Binance 15m fetch extended June 2026 from local end 2026-06-19 23:45 UTC to 2026-06-26 18:30 UTC.
  - Fixed hard-pass candidate June combined result after the fetch: +18.10%, 12 orders. New post-local segment had 0 orders and 0.00% return because the monthly lock was already flat.
  - Interpretation: no obvious execution-time future function was found, but overfit risk remains high. Treat the historical hard pass as a research artifact, not a robust strategy.

Useful source files:

- `scripts/search_ultimate_monthly_20260626.py`
- `scripts/search_hgb_upper_bound_20260626.py`
- `scripts/search_online_expert_pool_20260627.py`
- `scripts/search_zscore_rsi_trend_20260627.py`
- `scripts/search_walkforward_hgb_strict_20260627.py`
- `scripts/analyze_expert_pool_bounds_20260627.py`
- `scripts/search_monthly_profit_lock_20260627.py`
- `scripts/validate_profit_lock_overfit_20260627.py`
- `src/btc_ml_trader/backtest.py`

What advice is needed:

1. Suggest only methods that can be implemented as strict no-future backtests.
2. Prefer concrete algorithm changes over general trading risk advice.
3. If proposing ML, specify exact walk-forward training windows, label availability, threshold calibration, and leakage checks.
4. If the hard requirements look infeasible, suggest upper-bound tests that can prove where the bottleneck is.
