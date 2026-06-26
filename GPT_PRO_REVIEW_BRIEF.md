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

Useful source files:

- `scripts/search_ultimate_monthly_20260626.py`
- `scripts/search_hgb_upper_bound_20260626.py`
- `scripts/search_online_expert_pool_20260627.py`
- `scripts/search_zscore_rsi_trend_20260627.py`
- `scripts/search_walkforward_hgb_strict_20260627.py`
- `scripts/analyze_expert_pool_bounds_20260627.py`
- `src/btc_ml_trader/backtest.py`

What advice is needed:

1. Suggest only methods that can be implemented as strict no-future backtests.
2. Prefer concrete algorithm changes over general trading risk advice.
3. If proposing ML, specify exact walk-forward training windows, label availability, threshold calibration, and leakage checks.
4. If the hard requirements look infeasible, suggest upper-bound tests that can prove where the bottleneck is.
