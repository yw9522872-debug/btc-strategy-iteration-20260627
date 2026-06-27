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
  - Strategy 0 / current frozen research candidate.
  - Human-readable Strategy 0 pointer: `STRATEGY_0.md`.
  - Machine-readable freeze file: `artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json`.
  - Freeze id: `monthly_profit_lock_research_freeze_20260627`.
  - Do not edit Strategy 0 in place; create a new strategy number, artifact directory, and freeze id for parameter, rule, cost, or data changes.

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

- `artifacts/profit_lock_walkforward_20260627/summary.json`
  - New strict expanding walk-forward check for the fixed `ret_state` expert only (`window=64`, `threshold_bps=100`).
  - For each evaluated month, lock/quota/leverage parameters are selected using only `2024-01` through the month before the evaluated month.
  - Local feature-frame result: 2025 return 171.35%; 2026 return 126.55%; no losing evaluated months; minimum monthly orders 12.
  - Important caveat: the fixed expert/window/threshold still comes from earlier historical research, so this is a stronger validation artifact, not a fully independent live-ready strategy.

- `STRATEGY_1_CANDIDATE.md`
  - Current Strategy 1 candidate pointer.
  - Candidate id: `strategy_1_candidate_20260627`.
  - Results: 2025 return 171.35%; 2026 return 126.55%; no losing evaluated months; minimum monthly orders 12.
  - Script: `scripts/search_strategy_1_candidate_20260627.py`.
  - Output: `artifacts/strategy_1_candidate_20260627/summary.json`.

- `STRATEGY_1B_CANDIDATE.md`
  - Stronger Strategy 1B candidate pointer.
  - Candidate id: `strategy_1b_expanded_controls_20260627`.
  - Script: `scripts/search_strategy_1b_expanded_controls_20260627.py`.
  - Output: `artifacts/strategy_1b_expanded_controls_20260627/summary.json`.
  - Result: 2025 return 419.18%; 2026 return 199.48%; no losing evaluated months; minimum monthly orders 12.
  - Versus Strategy 0: higher 2025 and 2026 return, lower 2025 max drawdown (-31.28% vs -48.53%), but worse 2026 max drawdown (-26.09% vs -18.21%).
  - Stress: base cost and extra 1-bar delay pass; round-trip cost 0.4% fails. It is cost-sensitive and can select 12x leverage.

- `STRATEGY_1C_CANDIDATE.md`
  - Strategy 1C candidate addressing the chart critique that Strategy 1B misses large post-lock trends.
  - Candidate id: `strategy_1c_trend_runner_20260627`.
  - Script: `scripts/search_strategy_1c_trend_runner_20260627.py`.
  - Output: `artifacts/strategy_1c_trend_runner_20260627/summary.json`.
  - Change: after monthly lock, keep only a small 0.25x trend-runner position when `trend_close_ema_gap_bps_60 >= 350` and `trend_adx_30 >= 30` for long, or the symmetric short condition.
  - Result: 2025 return 503.36%; 2026 return 199.61%; no losing evaluated months; minimum monthly orders 12; max drawdown -31.28%.
  - Stress: base cost, 0.3% round-trip cost, and extra 1-bar delay pass; 0.4% round-trip cost fails. It remains cost-sensitive.

- `STRATEGY_1F_CANDIDATE.md`
  - Strategy 1F candidate addressing the chart critique that Strategy 1B/1C still take large opposite trades in strong trends and open large trades in weak trend zones.
  - Candidate id: `strategy_1f_selective_runner_20260627`.
  - Script: `scripts/search_strategy_1f_selective_runner_20260627.py`.
  - Output: `artifacts/strategy_1f_selective_runner_20260627/summary.json`.
  - Result: 2025 return 433.74%; 2026 return 260.59%; no losing evaluated months; minimum monthly orders 11; max drawdown -29.40%.
  - Diagnostics: strong-trend reverse big active bars = 1; weak-trend big order events = 0.
  - Stress: base cost, 0.3% round-trip cost, 0.4% round-trip cost, extra 1-bar delay, and 0.3% + 1-bar delay all pass.
  - Interpretation: currently the more robust Strategy 1 candidate, but still posthoc research and not a live guarantee.

- `STRATEGY_1G_CANDIDATE.md`
  - Strategy 1G candidate keeps the 1F logic but lowers main leverage cap from 8x to 7x.
  - Candidate id: `strategy_1g_cap7_selective_runner_20260627`.
  - Script: `scripts/search_strategy_1g_cap7_selective_runner_20260627.py`.
  - Output: `artifacts/strategy_1g_cap7_selective_runner_20260627/summary.json`.
  - Result: 2025 return 471.14%; 2026 return 246.16%; no losing evaluated months; minimum monthly orders 11; max drawdown -28.67%.
  - Diagnostics: strong-trend reverse big active bars = 1; weak-trend big order events = 0.
  - Stress: base cost, 0.3% round-trip cost, and extra 1-bar delay pass; 0.4% round-trip cost and 0.3% + 1-bar delay fail.
  - Interpretation: stronger under the fixed 0.2% fee backtest, but less robust than 1F under stress.

- `artifacts/strategy_1fg_extra_audit_20260627/summary.json`
  - Extra audit only; not a new strategy and does not overwrite Strategy 0, 1F, or 1G.
  - Script: `scripts/audit_strategy_1fg_extra_20260627.py`.
  - Grid: round-trip cost 0.2%, 0.3%, 0.4%; extra signal delay 0, 1, and 2 bars.
  - Checks passed: active position equals previous target position, and position does not exceed each candidate leverage cap.
  - 1F passed 7/9 scenarios. It failed only under 0.4% round-trip cost plus 1-bar or 2-bar extra delay, mainly because 2025-02 turned sharply negative.
  - 1G passed 4/9 scenarios. It failed under 0.3% round-trip cost plus delay and all 0.4% round-trip cost scenarios, also mainly due to 2025-02.
  - Interpretation: this strengthens the current judgment that 1F is the more robust candidate, while 1G is mainly attractive under the fixed 0.2% cost assumption.

- `artifacts/strategy_1fg_202502_failure_review_20260627/summary.json`
  - Failure review for 2025-02.
  - Script: `scripts/analyze_strategy_1fg_202502_failure_20260627.py`.
  - Main finding: the stress failure was not caused by a missing indicator. Under higher cost/delay, the strategy did not lock early enough, stayed exposed for almost the whole month, and turnover exploded.
  - Normal 2025-02 active bars were about 640; failed stress scenarios had about 2630 active bars.
  - Normal turnover was about 20-32; failed stress turnover was about 536-660.
  - Largest loss contribution came from `adverse_shock_cut`, where large active positions were hit by abrupt moves and then paid large switching cost.

- `artifacts/strategy_2_damage_stop_20260627/summary.json`
  - Negative experiment, not a candidate.
  - It added a month-level drawdown damage stop. This was too aggressive and killed many profitable months.
  - Result: 2025 return 22.36%, 2026 return 50.81%, 10 losing evaluated months. Do not promote this.

- `artifacts/strategy_2b_shock_stop_20260627/summary.json`
  - Negative experiment, not a candidate.
  - It only stopped after two adverse shocks in a month.
  - Base result matched 1F, but 0.4% round-trip cost plus delay still failed. Interpretation: waiting until the second adverse shock is too late.

- `STRATEGY_2C_CANDIDATE.md`
  - Strategy 2C candidate.
  - Candidate id: `strategy_2c_lock_cap_20260627`.
  - Script: `scripts/search_strategy_2c_lock_cap_20260627.py`.
  - Output: `artifacts/strategy_2c_lock_cap_20260627/summary.json`.
  - Change: keep 1F logic, but cap the monthly selected `lock_log` at 0.04, so the strategy locks earlier after the 10-order monthly quota is met.
  - Base result at 0.2% round-trip cost: 2025 return 359.10%; 2026 return 260.59%; no losing evaluated months; minimum monthly orders 11; max drawdown -29.40%.
  - Stress grid passed 9/9: round-trip cost 0.2%, 0.3%, 0.4% crossed with extra signal delay 0, 1, 2 bars.
  - Worst stress case, 0.4% round-trip plus 2-bar delay: 2025 return 217.67%; 2026 return 181.75%; worst evaluated month +1.81%.
  - Interpretation: 2C gives up some base return versus 1F but is currently more robust to execution cost and delay. It is still posthoc research and not a live guarantee.

- `STRATEGY_4_CANDIDATE.md`
  - Strategy 4 candidate from visual review of 2C/3.
  - Candidate id: `strategy_4_entry_confirm_20260627`.
  - Script: `scripts/search_strategy_4_entry_confirm_20260627.py`.
  - Output: `artifacts/strategy_4_entry_confirm_20260627/summary.json`.
  - Charts: `artifacts/strategy_4_visual_review_20260627/strategy4_trades_2025.png` and `artifacts/strategy_4_visual_review_20260627/strategy4_trades_2026.png`.
  - Change: keep the 2C lock cap; use the Strategy 3 post-lock 0.10x trend runner with 350 bps gap, ADX >= 30, and 8-bar confirmation; add a 4-bar confirmation wait before allowing a newly switched main base direction to enter.
  - Base result at 0.2% round-trip cost: 2025 return 290.69%; 2026 return 263.17%; no losing evaluated months; minimum monthly orders 10; max drawdown about -28.79%.
  - Stress grid passed 9/9: round-trip cost 0.2%, 0.3%, 0.4% crossed with extra signal delay 0, 1, 2 bars.
  - Worst stress case, 0.4% round-trip plus 2-bar delay: 2025 return 201.77%; 2026 return 183.84%; worst evaluated month +1.46%.
  - Visual diagnostics: strong-trend flat bars fell from 2C's 1208 to 152 after the Strategy 3 runner change; adverse entry events fell from Strategy 3's 21/217 to Strategy 4's 16/203 after the 4-bar entry confirmation.
  - Rejected experiments: leverage ramp failed stress 8/9; continuous weak-trend cap failed stress 0/9; RSI/Donchian extreme filters did not improve robustly.
  - Interpretation: 2C has better headline return and stress margin; Strategy 4 has cleaner charts and fewer fast false reversals. Both remain posthoc research, not live guarantees.

- `STRATEGY_5_ROBUSTNESS_AUDIT.md`
  - Strategy 5 is an audit, not a new strategy.
  - Audit id: `strategy_5_robustness_audit_20260627`.
  - Script: `scripts/audit_strategy_5_robustness_20260627.py`.
  - Output: `artifacts/strategy_5_robustness_audit_20260627/summary.json`.
  - Compared only 2C and Strategy 4; did not edit either strategy.
  - Cost/delay grid: round-trip cost 0.2%, 0.3%, 0.4%, 0.5% crossed with extra signal delay 0, 1, 2, 3 bars.
  - Cost/delay result: 2C passed 13/16, Strategy 4 passed 14/16. Worst min monthly return: 2C -2.78%, Strategy 4 -1.49%.
  - Order-miss test: base cost, deterministic random missed rebalance instructions at 2%, 5%, 10%, three seeds each.
  - Order-miss result: 2C passed 7/9, Strategy 4 passed 8/9. Important nuance: 2C failures were due to monthly order count falling to 9, not losing months; Strategy 4 had one order-miss scenario with a losing month.
  - Interpretation: Strategy 4 wins strict hard-pass count; 2C is cleaner if order-miss profitability is weighted above the monthly order-count rule.

- `artifacts/strategy_1_walkforward_20260627/summary.json`
  - Experimental attempt to select `ret_state` window/threshold plus lock/quota/leverage using only prior months.
  - This failed: 2025 return -22.09%, 2026 return 126.55%, two losing evaluated months.
  - Interpretation: freely selecting the signal from a larger pool made the walk-forward selector chase a poor 64/200 setting in 2025, so it is useful as a negative result.

Useful source files:

- `scripts/search_ultimate_monthly_20260626.py`
- `scripts/search_hgb_upper_bound_20260626.py`
- `scripts/search_online_expert_pool_20260627.py`
- `scripts/search_zscore_rsi_trend_20260627.py`
- `scripts/search_walkforward_hgb_strict_20260627.py`
- `scripts/analyze_expert_pool_bounds_20260627.py`
- `scripts/search_monthly_profit_lock_20260627.py`
- `scripts/validate_profit_lock_overfit_20260627.py`
- `scripts/validate_profit_lock_walkforward_20260627.py`
- `scripts/search_strategy_1_candidate_20260627.py`
- `scripts/search_strategy_1_walkforward_20260627.py`
- `scripts/search_strategy_1b_expanded_controls_20260627.py`
- `scripts/search_strategy_1c_trend_runner_20260627.py`
- `scripts/search_strategy_3_trend_coverage_20260627.py`
- `scripts/search_strategy_4_entry_confirm_20260627.py`
- `scripts/audit_strategy_5_robustness_20260627.py`
- `scripts/plot_strategy_trade_charts_20260627.py`
- `src/btc_ml_trader/backtest.py`

What advice is needed:

1. Suggest only methods that can be implemented as strict no-future backtests.
2. Prefer concrete algorithm changes over general trading risk advice.
3. If proposing ML, specify exact walk-forward training windows, label availability, threshold calibration, and leakage checks.
4. If the hard requirements look infeasible, suggest upper-bound tests that can prove where the bottleneck is.
