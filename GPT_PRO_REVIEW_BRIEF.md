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

- `STRATEGY_5B_THREE_WAY_AUDIT.md`
  - Strategy 5B is an audit, not a new strategy.
  - Audit id: `strategy_5b_three_way_audit_20260627`.
  - Script: `scripts/audit_strategy_5b_three_way_20260627.py`.
  - Output: `artifacts/strategy_5b_three_way_audit_20260627/summary.json`.
  - Compared 2C, Strategy 3, and Strategy 4 under the same Strategy 5 audit grid.
  - Cost/delay result: 2C passed 13/16, Strategy 3 passed 13/16, Strategy 4 passed 14/16.
  - Order-miss result: 2C passed 7/9, Strategy 3 passed 7/9, Strategy 4 passed 8/9.
  - Order-miss profitability nuance: 2C and Strategy 3 had no losing months in all 9 order-miss scenarios; Strategy 4 had one losing-month scenario.
  - Interpretation: Strategy 3 did not beat 2C in robustness. It improves strong-trend coverage but does not justify promotion over 2C in this audit. Current practical ranking: 2C as main candidate, Strategy 4 as chart-quality/hard-pass comparator, Strategy 3 as intermediate experiment.

- `STRATEGY_6_MARKET_REGIME_AUDIT.md`
  - Strategy 6 is a market-regime audit, not a new strategy and not a live signal.
  - Audit id: `strategy_6_market_regime_audit_20260627`.
  - Script: `scripts/audit_strategy_6_market_regime_20260627.py`.
  - Output: `artifacts/strategy_6_market_regime_audit_20260627/summary.json`.
  - It reuses Strategy 5B monthly posthoc labels: monthly return >= +5% is up, <= -5% is down, otherwise sideways; max monthly drawdown/runup >= 15% marks a shock month.
  - These are posthoc month-end labels. They are historical attribution labels, not real-time market state signals.
  - Shared data end is 2026-06-19 23:45 UTC; 2026-06 is a partial month. Complete-month counts are down 5, sideways 6, up 6.
  - Base monthly results for 2C, Strategy 3, and Strategy 4 pass in each state, but the sample is only 17 complete months.
  - No confirmed regime weakness under the strict standard: complete months only, at least 2 distinct failure months, both cost/delay and order-miss stress families, and each family affecting at least 2 candidates.
  - Conservative observations only: cost/delay losses cluster in down months, especially 2026-01; order-miss issues cluster in sideways months, especially 2025-03.
  - GPT Pro review: keep Strategy 6 as a historical health check only; do not promote it into a router; avoid treating posthoc explanation as prediction; remember 2C/3/4 are one strategy family, not independent evidence.

- `STRATEGY_7_ORACLE_ROUTER_AUDIT.md`
  - Strategy 7 is an oracle router upper-bound audit, not a new strategy and not a live router.
  - Audit id: `strategy_7_oracle_router_audit_20260627`.
  - Script: `scripts/audit_strategy_7_oracle_router_20260627.py`.
  - Output: `artifacts/strategy_7_oracle_router_audit_20260627/summary.json`.
  - It excludes partial 2026-06 and uses 17 complete months only.
  - Static complete-month totals: 2C +1033.11%, Strategy 3 +1013.10%, Strategy 4 +829.14%.
  - `oracle_month_best` gets +1128.92%, but it picks the best candidate after seeing each month and is therefore a leaky upper bound.
  - `oracle_regime_best_fullsample` gets +1045.54%, only +12.42 percentage points above 2C.
  - `oracle_regime_past_only` gets +986.32%, underperforming 2C by 46.79 percentage points.
  - Interpretation: do not promote a router; complex real-time regime switching is not currently justified. Next useful work is execution-stress expansion, not more regime routing.

- `STRATEGY_8_EXECUTION_STRESS_AUDIT.md`
  - Strategy 8 is an execution-stress audit, not a new strategy.
  - Audit id: `strategy_8_execution_stress_20260627`.
  - Script: `scripts/audit_strategy_8_execution_stress_20260627.py`.
  - Output: `artifacts/strategy_8_execution_stress_20260627/summary.json`.
  - Stress set: volatility-scaled slippage, 1bp/3bp per 8h funding drag, missing the largest 5% rebalances, and short outages around the top 3 volatility bars.
  - Results: 2C passed 6/6 with worst year +218.06% and worst month +2.76%; Strategy 3 passed 6/6 with worst year +216.95% and worst month +2.44%; Strategy 4 passed 5/6.
  - Strategy 4 failure: `miss_top5pct_rebalance` in 2025-03, monthly return -0.56% with 11 orders.
  - Interpretation: execution stress further supports 2C as the main candidate. Strategy 4 remains a chart-quality/hard-pass comparator but is more fragile under critical missed rebalances.

- `STRATEGY_9_COLD_START_FEASIBILITY.md`
  - Strategy 9 is a cold-start feasibility audit, not a new strategy.
  - Audit id: `strategy_9_cold_start_feasibility_20260627`.
  - Script: `scripts/audit_strategy_9_cold_start_feasibility_20260627.py`.
  - Output: `artifacts/strategy_9_cold_start_feasibility_20260627/summary.json`.
  - Local feature data covers 2024-01 through 2026-06.
  - Saved monthly controls for 2C/3/4 start at 2025-01 and end at 2026-06.
  - Direct 2024 testing is not clean because 2024 is already training history for the saved candidates. Reusing 2025+ controls on 2024 would test the past with future-selected controls.
  - Clean options: fetch pre-2024 data and build a true 2024 walk-forward, or leave 2024 as training history and evaluate future newly arriving months without changing rules.

- `STRATEGY_10_PRE2024_DATA_PROBE.md`
  - Strategy 10 is a pre-2024 data probe, not a trading strategy and not a profitability backtest.
  - Probe id: `strategy_10_pre2024_data_probe_20260627`.
  - Script: `scripts/audit_strategy_10_pre2024_data_probe_20260627.py`.
  - Output: `artifacts/strategy_10_pre2024_data_probe_20260627/summary.json`.
  - It fetched 2023 BTCUSDT 15m public klines from Binance public monthly kline archives without API keys.
  - Official raw 2023 rows: 35035. Binance has a 5-bar 15m gap on 2023-03-24; public REST endpoints return the same gap.
  - The calendar-filled OHLC file inserts 5 flat bars using the previous close and marks them with `calendar_filled=True`.
  - Filled rows: 35040; duplicate rows 0; non-15m gap rows 0; required feature columns missing 0.
  - The feature probe is recomputed from public OHLC and is not an exact reproduction of the original `event_entry_fullscan` feature source.
  - Interpretation: use this as the data base for a new Strategy 11 true 2024 walk-forward. Do not reuse 2025+ saved controls on 2024.

- `STRATEGY_11_TRUE_2024_WALKFORWARD.md`
  - Strategy 11 is a true 2024 walk-forward audit, not a new trading strategy and not a freeze.
  - Audit id: `strategy_11_true_2024_walkforward_20260627`.
  - Script: `scripts/audit_strategy_11_true_2024_walkforward_20260627.py`.
  - Output: `artifacts/strategy_11_true_2024_walkforward_20260627/summary.json`.
  - It uses 2023 public data plus only prior months before each evaluated 2024 month to select controls, then evaluates 2024.
  - Tested variants: fixed `ret_state window=64 threshold=100 bps`; small rolling `ret_state` selector with windows 32/64/96 and thresholds 50/100/200.
  - Both variants selected back to `ret_state 64/100`.
  - 2024 result: +138.08%, minimum monthly orders 12, but one losing month: 2024-12 at -6.45%.
  - Hard-pass 2024 result: false, because the every-month-profitable condition fails.
  - Interpretation: this strengthens the overfit concern. Future work should study 2024-12 as an out-of-sample failure month instead of only adding rules on 2025/2026.

- `STRATEGY_12_202412_FAILURE_REVIEW.md`
  - Strategy 12 is a 2024-12 failure review, not a strategy and not a freeze.
  - Review id: `strategy_12_202412_failure_review_20260627`.
  - Script: `scripts/audit_strategy_12_202412_failure_review_20260627.py`.
  - Output: `artifacts/strategy_12_202412_failure_review_20260627/summary.json`.
  - Source result: Strategy 11 fixed `ret_state 64/100` true 2024 walk-forward.
  - 2024-12 net return: -6.45%; gross before turnover cost: +4.22%; turnover-cost drag: about 10.80% log; orders 18; turnover 108.0.
  - Main failure timing: around quota completion / early month, net -23.21%, gross before cost -17.97%, cost about 6.60% log. Later part recovered +21.83% net but did not fully repair the hole.
  - Small parameter sweep: 30 candidates, 8 train-hard-ok candidates, 2 train-hard-ok candidates were positive in 2024-12. Best 2024-12 candidate was +5.74%, but that is leaky hindsight and not tradeable.
  - Interpretation: do not immediately add a stop or switch rule from this single bad month. If continuing, build Strategy 13 as a low-turnover / low-reversal prevention rule selected from 2023 and evaluated on all 2024.

- `STRATEGY_13_LOW_TURNOVER_PREVENTION.md`
  - Strategy 13 is a low-turnover / low-reversal prevention experiment, not a candidate and not a freeze.
  - Experiment id: `strategy_13_low_turnover_prevention_20260627`.
  - Script: `scripts/search_strategy_13_low_turnover_prevention_20260627.py`.
  - Output: `artifacts/strategy_13_low_turnover_prevention_20260627/summary.json`.
  - Rule: base signal remains `ret_state window=64 threshold=100 bps`; switch side only after the new side persists for `confirm_bars` closed 15m bars.
  - Tested `confirm_bars`: 1, 2, 4, 8, 12. `confirm_bars=1` is the original immediate reversal.
  - Strict selection: use 2023 only to select `confirm_bars` and control params, then evaluate full 2024 from flat, without carrying 2023 positions into 2024.
  - 2023 selected `confirm_bars=1`, leverage 6, lock_log 0.04, quota_arm_log 0.08, quota_leverage 0.25.
  - Full 2024 result: +114.96%, one losing month, worst month -6.45%, min monthly orders 12, hard pass false.
  - Leaky diagnostics: if allowed to look at 2024, 24 candidates pass; best 2024 return is +183.61% with `confirm_bars=4`. This is hindsight only and must not be promoted.
  - Interpretation: confirmation has potential, but a strict 2023-only selector does not choose it. Do not freeze `confirm_bars=4` from this evidence.

- `STRATEGY_14_PRE2023_EXPANDING_CROWDING_STRESS_AUDIT.md`
  - Strategy 14 is a pre-2023 expanding walk-forward and crowding/execution stress audit, not a candidate and not a freeze.
  - Audit id: `strategy_14_pre2023_expanding_crowding_stress_audit_20260627`.
  - Script: `scripts/audit_strategy_14_pre2023_expanding_crowding_stress_20260627.py`.
  - Output: `artifacts/strategy_14_pre2023_expanding_crowding_stress_audit_20260627/summary.json`.
  - Important data correction: `event_entry_fullscan` matches Binance USD-M futures public klines, not spot klines. Strategy 14 therefore uses USD-M futures public klines for 2020-2024 and local event tail for 2025 through complete 2026-05.
  - 2024 parity check: 35136 public futures rows, 35136 event rows, 35136 matched rows, 0 close mismatches.
  - This means 10/11/13, which used the 2023 spot probe with the old event data, should be treated as exploratory/diagnostic rather than the final clean pre-2024 audit.
  - Candidate family: fixed `ret_state 64/100`; `confirm_bars` in 1/2/4/8/12; 30 small control-grid rows; 150 candidates total.
  - Nested expanding result, 2023-01 through 2026-05: 2023 -21.96%, 2024 +140.23%, 2025 -5.28%, 2026 YTD -0.35%; losing eval months 6; worst month -39.60%; max drawdown -58.39%.
  - All 41 evaluated months selected `confirm_bars=8`, but the family still failed.
  - Stress: 11 fixed scenarios covering 0.2/0.3/0.4/0.6% round-trip cost, 1/2/4-bar signal delay, 1/3/5bp per 8h funding drag, and dynamic volatility slippage. Hard-pass scenarios: 0/11.
  - Decision: `STOP_FAMILY`. Do not keep hand-tuning this `ret_state 64/100` family to repair known bad months.

- `STRATEGY_15_UNIFIED_DATA_BASELINE.md`
  - Strategy 15 is a unified data-baseline audit, not a strategy, not a profitability backtest, and not a freeze.
  - Audit id: `strategy_15_unified_data_baseline_20260627`.
  - Script: `scripts/audit_strategy_15_unified_data_baseline_20260627.py`.
  - Output: `artifacts/strategy_15_unified_data_baseline_20260627/summary.json`.
  - It audits the Strategy 14 combined OHLC file rather than downloading new data.
  - Accepted baseline: BTCUSDT 15m Binance USD-M futures public archive for 2020-2024 plus local `event_entry_fullscan` tail for 2025 through complete 2026-05.
  - Coverage: 2020-01-01 00:00 UTC through 2026-05-31 23:45 UTC, 224,928 rows, 77 complete months.
  - Quality checks: duplicate timestamps 0, non-15m gaps 0, invalid OHLC rows 0, calendar-filled rows 0, incomplete months 0, missing months 0.
  - Inherits Strategy 14's 2024 parity check: 35,136 public futures rows vs 35,136 event rows, 0 close mismatches.
  - Decision: `DATA_BASELINE_READY`. Next new strategy family should use this futures baseline and avoid mixing the earlier 2023 spot probe with the event source.

- `STRATEGY_16_NEW_FAMILY_PROBE.md`
  - Strategy 16 is a new-family feasibility probe, not a candidate, not a freeze, and not live trading.
  - Probe id: `strategy_16_new_family_probe_20260627`.
  - Script: `scripts/audit_strategy_16_new_family_probe_20260627.py`.
  - Output: `artifacts/strategy_16_new_family_probe_20260627/summary.json`.
  - Data: Strategy 15 USD-M futures baseline, 2020-01 through complete 2026-05.
  - Evaluation: strict monthly expanding selection, evaluating 2023-01 through 2026-05. Complete-year hard gate applies to 2023/2024/2025; 2026 is YTD only.
  - Cost: round-trip open+close 0.2%, modeled as `cost_per_side = 0.001`.
  - Candidate grid: 144 simple non-`ret_state` candidates: MA trend, Donchian trend, RSI reversion, Bollinger reversion, and ATR breakout; leverage only 1x/2x/4x.
  - Best strict selector: `all_families`, with 2023 +23.04%, 2024 +33.45%, 2025 -54.66%, 2026 YTD +1.90%; 22 losing months, worst month -25.35%, minimum monthly orders 3, max drawdown -72.40%.
  - Family selectors also failed: trend matches all_families; volatility_breakout lost money in 2023/2024/2025/YTD; mean_reversion lost money in every listed year.
  - Static hindsight scan hard-pass count: 0 out of 144.
  - Decision: `NO_HARD_PASS_IN_SIMPLE_NEW_FAMILY_PROBE`. Do not promote Strategy 16; next useful step is an upper-bound/oracle test before adding complexity to these simple rules.

- `STRATEGY_17_SIMPLE_FAMILY_UPPER_BOUND.md`
  - Strategy 17 is a leaky monthly oracle upper-bound test, not a strategy, not tradeable, and not a freeze.
  - Test id: `strategy_17_simple_family_upper_bound_20260627`.
  - Script: `scripts/audit_strategy_17_simple_family_upper_bound_20260627.py`.
  - Output: `artifacts/strategy_17_simple_family_upper_bound_20260627/summary.json`.
  - Source: the 144 simple Strategy 16 candidates on the Strategy 15 USD-M futures baseline.
  - Warning: the monthly oracle chooses the best candidate after seeing each evaluated month, so `strict_no_future = false`; month-boundary switching cost is not included, making this optimistic.
  - Most permissive oracle, `monthly_oracle_best_return`, ignores the 10-order monthly floor. It has huge annual returns, but still fails hard gates: non-positive months are 2023-07, 2024-12, 2025-06, 2025-09, 2026-04, and 2026-05; minimum monthly orders is 0.
  - Order-floor oracle, `monthly_oracle_best_return_order10`, only chooses candidates with at least 10 monthly orders. It still has 10 non-positive months: 2023-07, 2023-09, 2024-04, 2024-06, 2024-12, 2025-06, 2025-07, 2025-09, 2026-04, and 2026-05.
  - Decision: `SIMPLE_FAMILY_UPPER_BOUND_FAILS`. Do not keep expanding this simple MA/Donchian/RSI/Bollinger/ATR-breakout menu; the problem is not just selector quality.

- `STRATEGY_18_UPPER_BOUND_FAILURE_REVIEW.md`
  - Strategy 18 is a failure-month review for Strategy 17, not a strategy, not a candidate, and not a freeze.
  - Review id: `strategy_18_upper_bound_failure_review_20260627`.
  - Script: `scripts/audit_strategy_18_upper_bound_failure_review_20260627.py`.
  - Output: `artifacts/strategy_18_upper_bound_failure_review_20260627/summary.json`.
  - Reviewed months: 2023-07, 2023-09, 2024-04, 2024-06, 2024-12, 2025-06, 2025-07, 2025-09, 2026-04, and 2026-05.
  - Failure types: `no_positive_candidate` in 6 months, meaning none of the 144 simple candidates had positive return that month; `positive_only_with_too_few_orders` in 4 months, meaning positive candidates existed but had fewer than 10 monthly orders.
  - `no_positive_candidate` months: 2023-07, 2024-12, 2025-06, 2025-09, 2026-04, 2026-05.
  - `positive_only_with_too_few_orders` months: 2023-09, 2024-04, 2024-06, 2025-07.
  - Decision: `FAILURE_MONTHS_EXPLAIN_SIMPLE_FAMILY_STOP`. This supports stopping expansion of the simple MA/Donchian/RSI/Bollinger/ATR-breakout menu.

- `STRATEGY_19_CALENDAR_SEASONALITY_PROBE.md`
  - Strategy 19 is a calendar/time-of-week seasonality probe, not a candidate, not a freeze, and not live trading.
  - Probe id: `strategy_19_calendar_seasonality_probe_20260627`.
  - Script: `scripts/audit_strategy_19_calendar_seasonality_probe_20260627.py`.
  - Output: `artifacts/strategy_19_calendar_seasonality_probe_20260627/summary.json`.
  - Data: Strategy 15 USD-M futures baseline. Model months start at 2021-01; evaluation is 2023-01 through 2026-05.
  - Candidate grid: 216 candidates using session, weekday, hour, and hour-of-week buckets; lookback 12 months, 24 months, or expanding; minimum average bucket threshold 0/0.5/1.0 bps; minimum samples 20/50; leverage 1x/2x/4x.
  - Signals use only calendar buckets and prior-month training history; positions participate from the next bar.
  - Best strict selector: `all_calendar`, with 2023 -1.32%, 2024 +71.64%, 2025 -26.91%, 2026 YTD +43.60%; 22 losing months, worst month -25.36%, minimum monthly orders 0, max drawdown -46.37%.
  - Best single dynamic candidate: `calendar_weekday_lbexpanding_thr0p0_min20_lev1p0`, with 2023 +31.81%, 2024 +71.57%, 2025 -10.55%, 2026 YTD +43.60%; 17 losing months, minimum monthly orders 10.
  - Decision: `CALENDAR_SEASONALITY_FAILS`. Do not promote Strategy 19.

- `STRATEGY_20_OHLC_STRUCTURE_UPPER_BOUND.md`
  - Strategy 20 is a leaky monthly oracle upper-bound test, not a strategy, not tradeable, and not a freeze.
  - Test id: `strategy_20_ohlc_structure_upper_bound_20260627`.
  - Script: `scripts/audit_strategy_20_ohlc_structure_upper_bound_20260627.py`.
  - Output: `artifacts/strategy_20_ohlc_structure_upper_bound_20260627/summary.json`.
  - Data: Strategy 15 USD-M futures baseline. The baseline has only OHLC, no volume, so Strategy 20 does not test volume.
  - Candidate grid: 189 OHLC-only candidates using candle body momentum/reversal, wick reversal, range momentum/reversal, high-volatility body momentum/reversal, and low-volatility wick reversal.
  - Warning: the monthly oracle chooses the best candidate after seeing each evaluated month, so `strict_no_future = false`; month-boundary switching cost is not included.
  - Static hindsight scan hard-pass count: 0 out of 189.
  - Most permissive oracle, `monthly_oracle_best_return`, ignores the 10-order monthly floor. It still fails: 2023 +51.61%, 2024 +18.35%, 2025 +12.99%, 2026 YTD +0.18%; 30 non-positive months; minimum monthly orders 0.
  - Order-floor oracle, `monthly_oracle_best_return_order10`, also fails: 2023 +22.80%, 2024 -2.56%, 2025 -6.90%, 2026 YTD -2.98%; 33 non-positive months; minimum monthly orders 10.
  - Decision: `OHLC_STRUCTURE_UPPER_BOUND_FAILS`. Do not promote Strategy 20 or keep expanding these OHLC-only candle/range/volatility micro-rules.

- `STRATEGY_21_VOLUME_UPPER_BOUND.md`
  - Strategy 21 is a leaky monthly oracle upper-bound test, not a strategy, not tradeable, and not a freeze.
  - Test id: `strategy_21_volume_upper_bound_20260627`.
  - Script: `scripts/audit_strategy_21_volume_upper_bound_20260627.py`.
  - Output: `artifacts/strategy_21_volume_upper_bound_20260627/summary.json`.
  - Data: Binance public USD-M futures monthly klines with volume/taker fields, 2020-01 through 2026-05. 224,928 rows; duplicate timestamps 0; non-15m gaps 0; calendar fills 0; invalid volume rows 0. Close parity with Strategy 15 baseline is 224,928/224,928 rows, close mismatches 0.
  - Candidate grid: 378 candidates using volume spike body momentum/reversal, taker buy/sell imbalance momentum/reversal, and volume-confirmed price move momentum/reversal.
  - Static hindsight scan hard-pass count: 0 out of 378.
  - Most permissive oracle, `monthly_oracle_best_return`, ignores the 10-order monthly floor. It still fails: 2023 +45.98%, 2024 +54.74%, 2025 -12.01%, 2026 YTD -9.17%; 25 non-positive months; minimum monthly orders 2.
  - Order-floor oracle, `monthly_oracle_best_return_order10`, also fails: 2023 +39.04%, 2024 +50.98%, 2025 -12.73%, 2026 YTD -9.17%; 29 non-positive months; minimum monthly orders 10.
  - Decision: `VOLUME_UPPER_BOUND_FAILS`. Do not promote Strategy 21 or keep expanding these simple volume/taker-flow micro-rules.

- `STRATEGY_22_HARD_TARGET_BOTTLENECK_AUDIT.md`
  - Strategy 22 is a hard-target bottleneck audit, not a strategy, not tradeable, and not a freeze.
  - Audit id: `strategy_22_hard_target_bottleneck_20260627`.
  - Script: `scripts/audit_strategy_22_hard_target_bottleneck_20260627.py`.
  - Output: `artifacts/strategy_22_hard_target_bottleneck_20260627/summary.json`.
  - It reuses only Strategy 16/19/20/21 candidates, 927 candidates total, and adds no new rules.
  - Grid: monthly order floor 0/2/5/10; round-trip cost 0.0/0.1/0.2/0.3/0.4%; monthly requirement allow-any / return >= -1% / return > 0; annual threshold 50/100%.
  - Strict expanding monthly selector pass count: 0/120.
  - Monthly oracle pass count: 80/120, but it is leaky and not tradeable.
  - Original hard target row, with 0.2% round-trip cost, monthly return > 0, monthly orders >= 10, annual threshold 100%: monthly oracle still fails due to 2023-07 and 2024-06; strict selector fails badly with 2025 -95.78% and 2026 YTD +7.81%.
  - Decision: `ORIGINAL_TARGET_AND_SELECTION_BOTTLENECK`. Do not keep expanding Strategy 16/19/20/21 micro-rules. If continuing research, use a genuinely different data source with an upper-bound test first, or lower the target to something more realistic.

- `RESEARCH_DECISION_STOP_SIMPLE_RULES_AFTER_22.md`
  - Project-level research decision after Strategy 22.
  - Stop patching `ret_state 64/100`, simple price indicators, calendar seasonality, OHLC candle/range/volatility micro-rules, and volume/taker micro-rules.
  - Do not jump straight to ML unless a new feature set first shows useful upper-bound evidence under no-future constraints.

- `STRATEGY_23_FUNDING_RATE_UPPER_BOUND.md`
  - Strategy 23 is a funding-rate upper-bound test, not a strategy, not tradeable, and not a freeze.
  - Test id: `strategy_23_funding_rate_upper_bound_20260627`.
  - Script: `scripts/audit_strategy_23_funding_rate_upper_bound_20260627.py`.
  - Output: `artifacts/strategy_23_funding_rate_upper_bound_20260627/summary.json`.
  - Data: Binance public USD-M futures monthly fundingRate archive, 2020-01 through 2026-05, 7,029 funding rows, no duplicate timestamps and no 8h gaps after second-flooring.
  - Candidate grid: 246 candidates using funding level, change, rolling mean, and z-score, with 1x/2x/4x leverage.
  - Static hindsight scan hard-pass count: 0.
  - Monthly oracle with monthly orders >= 10 passes: 2023 +17,263.32%, 2024 +45,467.21%, 2025 +6,801.02%, 2026 YTD +648.74%, zero losing months, minimum monthly return +5.43%, minimum monthly orders 10.
  - Decision: `FUNDING_RATE_UPPER_BOUND_HAS_MONTHLY_PIECES`. It is leaky and not tradeable; it only justifies a strict selector test.

- `STRATEGY_24_FUNDING_RATE_STRICT_SELECTOR.md`
  - Strategy 24 reuses Strategy 23 funding candidates with strict expanding monthly selection, not a new strategy and not a freeze.
  - Test id: `strategy_24_funding_rate_strict_selector_20260627`.
  - Script: `scripts/audit_strategy_24_funding_rate_strict_selector_20260627.py`.
  - Output: `artifacts/strategy_24_funding_rate_strict_selector_20260627/summary.json`.
  - No new rules were added. Each evaluated month uses only months before it for selection.
  - Best strict selector is `funding_mean_only`: 2023 -22.82%, 2024 -42.05%, 2025 +9.70%, 2026 YTD +10.95%, 20 losing months, minimum monthly orders 0.
  - Decision: `FUNDING_RATE_STRICT_SELECTOR_FAILS`. Funding-rate oracle pieces cannot currently be selected without future information, so do not promote this family.

- `STRATEGY_25_OPEN_INTEREST_UPPER_BOUND_FEASIBILITY.md`
  - Strategy 25 is an open-interest data availability audit, not a strategy and not a freeze.
  - Audit id: `strategy_25_open_interest_upper_bound_feasibility_20260627`.
  - Script: `scripts/audit_strategy_25_open_interest_upper_bound_feasibility_20260627.py`.
  - Output: `artifacts/strategy_25_open_interest_upper_bound_feasibility_20260627/summary.json`.
  - Source checked: Binance USD-M futures `openInterestHist` REST endpoint.
  - Official Binance documentation says only the latest 1 month is available.
  - Actual checks: 2020-01 and 2023-01 requests failed with `startTime` invalid; recent data and 2026-05-31 succeeded.
  - Decision: `OPEN_INTEREST_HISTORY_NOT_AVAILABLE_FOR_2020_2026`. Do not run a 2023-2026 hard-target upper bound from incomplete public open-interest data.

- `DATA_SOURCE_OPEN_INTEREST_LONG_SHORT_REVIEW_20260627.md`
  - Data-source review for historical open interest and long/short ratios.
  - Binance official REST is not enough for multi-year backtests: open interest history is latest 1 month only; long/short ratio endpoints are latest 30 days only.
  - Best next source is Tardis.dev because it documents Binance USDS-M futures coverage, timestamps, generated channels, CSV/API access, open interest from 2020-05, and long/short ratio channels from 2020-10-28.
  - CoinGlass and Amberdata are backups if they can provide complete BTCUSDT Binance futures exports for at least 2020-10-28 through 2026-05-31.
  - Do not start any open-interest/long-short-ratio backtest until complete local CSV exports are available; first step after CSV is a data-quality audit and 15m baseline alignment check.

- `STRATEGY_26_INTRABAR_1M_UPPER_BOUND.md`
  - Strategy 26 is a leaky monthly oracle upper-bound test using free Binance USD-M futures 1m klines, not a strategy and not tradeable.
  - Test id: `strategy_26_intrabar_1m_upper_bound_20260627`.
  - Script: `scripts/audit_strategy_26_intrabar_1m_upper_bound_20260627.py`.
  - Output: `artifacts/strategy_26_intrabar_1m_upper_bound_20260627/summary.json`.
  - Data: BTCUSDT 1m public monthly klines from 2020-01 through 2026-05, aggregated to the Strategy 15 15m baseline. Missing 1m rows 0, duplicates 0, non-1m gaps 0, incomplete 15m groups 0.
  - Caveat: 8 aggregated 15m bars disagree with the Strategy 15 OHLC baseline; Strategy 26 disables signals on those bars instead of repairing them.
  - Candidate grid: 186 intrabar candidates using early/late 1m movement, late volume share, late taker ratio, path efficiency, high/low minute position, and chop reversal.
  - Static hard-pass count: 0.
  - Best oracle, `monthly_oracle_best_return`: 2023 +47.27%, 2024 +16.29%, 2025 -3.27%, 2026 YTD -7.68%, 28 losing months, minimum monthly orders 0.
  - Order-floor oracle, `monthly_oracle_best_return_order10`: 2023 +34.37%, 2024 +15.88%, 2025 -8.43%, 2026 YTD -9.54%, 30 non-positive months, minimum monthly orders 10.
  - Decision: `INTRABAR_1M_UPPER_BOUND_FAILS`. Do not keep expanding this 1m intrabar micro-rule family.

- `STRATEGY_27_TARGET_FEASIBILITY_AUDIT.md`
  - Strategy 27 is a target-feasibility audit, not a strategy and not tradeable.
  - Audit id: `strategy_27_target_feasibility_audit_20260627`.
  - Script: `scripts/audit_strategy_27_target_feasibility_20260627.py`.
  - Output: `artifacts/strategy_27_target_feasibility_audit_20260627/summary.json`.
  - No new candidate rules were added. It reuses Strategy 22's 927-candidate monthly base from Strategies 16/19/20/21 and references Strategy 23/24/26 results.
  - Grid at the main 0.2% round-trip cost: annual thresholds 30/50/80/100%, monthly gates allow-any / >= -2% / >= -1% / > 0, and monthly order floors 0/5/10. It also adds one no-fee original-gate diagnostic row.
  - Original target still fails: monthly oracle fails due to 2 non-passing months; strict selector fails with 2025 -95.78%, 2026 YTD +7.81%, and 41 non-passing months.
  - Relaxed grid: strict expanding selector passes 0/49 scenarios; monthly oracle passes 37/49 scenarios.
  - Closest oracle pass at the real 0.2% cost is annual 100%, monthly orders >= 10, and monthly return >= -1%; this is leaky and not tradeable.
  - Decision: `TARGET_RELAXATION_HELPS_ORACLE_NOT_SELECTOR`. Target relaxation helps the oracle but not the strict selector; the bottleneck is selecting the right month/candidate without future information.

- `STRATEGY_28_RELAXED_NO_MONTHLY_PROFIT_AUDIT.md`
  - Strategy 28 is a relaxed-target audit, not a strategy and not tradeable.
  - Audit id: `strategy_28_relaxed_no_monthly_profit_audit_20260628`.
  - Script: `scripts/audit_strategy_28_relaxed_no_monthly_profit_20260628.py`.
  - Output: `artifacts/strategy_28_relaxed_no_monthly_profit_audit_20260628/summary.json`.
  - It reuses the Strategy 14 `ret_state 64/100` family and the unified futures OHLC baseline; no new trading rule or market data was added.
  - Monthly profitable-month requirement is removed, while the 0.2% round-trip cost and no-future expanding monthly selection rule remain.
  - Four strict selectors were tested: loss-control first, return first, return first with monthly order-floor preference, and worst-full-year balance.
  - Best strict exact result is still weak: 2023 -21.96%, 2024 +140.23%, 2025 -5.28%, 2026 YTD -0.35%, 6 losing eval months, max drawdown -58.39%, min monthly orders 10.
  - The monthly oracle is strong, with 2025 +1692.64% and 2026 YTD +171.90%, but it chooses the best candidate after seeing each month and is therefore leaky.
  - Decision: `NO_STRICT_RELAXED_UPGRADE`. Removing the monthly-profit requirement does not fix the non-leaky selector problem.

- `STRATEGY_29_FREE_RAW_TRADE_COVERAGE_AUDIT.md`
  - Strategy 29 is a free-data coverage audit, not a strategy and not tradeable.
  - Audit id: `strategy_29_free_raw_trade_coverage_audit_20260628`.
  - Script: `scripts/audit_strategy_29_free_raw_trade_coverage_20260628.py`.
  - Output: `artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/summary.json`.
  - It follows the GPT Pro recommendation to check the last plausible free route: spot-perp raw-trade lead/lag plus funding/mark/index/premium filters.
  - The audit uses HEAD checks only and does not download or parse the large trade zip files.
  - Coverage from 2020-01 through 2026-05 is complete, 77/77 months, for futures/spot aggTrades, futures/spot trades, futures/spot 1m klines, fundingRate, markPriceKlines, indexPriceKlines, and premiumIndexKlines.
  - Optional bookTicker archive probes return 404 for 2020-01, so do not build a second-level order-book strategy from monthly bookTicker archives.
  - Decision: `FREE_SPOT_PERP_RAW_TRADE_DATA_AVAILABLE`. Next step, if any, should be a separate spot-perp aggTrades lead/lag upper-bound test with funding/mark/index/premium as filters.

- `STRATEGY_30_SPOT_PERP_AGGTRADE_SAMPLE_UPPER_BOUND.md`
  - Strategy 30 is a small-sample leaky upper-bound test, not a strategy and not tradeable.
  - Audit id: `strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628`.
  - Script: `scripts/audit_strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628.py`.
  - Output: `artifacts/strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628/summary.json`.
  - It downloaded only four sample months, `2023-07`, `2024-06`, `2025-08`, and `2026-05`, for spot/futures BTCUSDT `aggTrades`; raw zip files were deleted after 15m aggregation.
  - Data quality passed: 11808 15m feature rows, no missing spot/futures 15m rows, about 2.586 GB compressed downloaded, 208.8M raw rows parsed.
  - Candidate grid: 204 spot-perp return/flow lead-lag candidates, leverage 1x/2x/4x, using Strategy 15 futures 15m returns and 0.2% round-trip cost.
  - Best no-order-floor oracle is no trading, 0.00% sample return; order>=10 oracle loses all four sample months, total -25.33%, worst month -12.67%, minimum monthly orders 39.
  - Decision: `SPOT_PERP_AGGTRADE_SAMPLE_UPPER_BOUND_FAILS`. Do not download the full ~90 GB aggTrades set for this lead-lag route.

- `STRATEGY_31_MULTISYMBOL_FREE_FUTURES_UPPER_BOUND.md`
  - Strategy 31 is a small-sample multi-symbol free-data upper-bound test, not a strategy and not tradeable.
  - Audit id: `strategy_31_multisymbol_free_futures_sample_upper_bound_20260628`.
  - Script: `scripts/audit_strategy_31_multisymbol_free_futures_upper_bound_20260628.py`.
  - Output: `artifacts/strategy_31_multisymbol_free_futures_sample_upper_bound_20260628/summary.json`.
  - Symbols: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, HYPEUSDT, DOGEUSDT, XRPUSDT, ADAUSDT, AVAXUSDT, LINKUSDT on Binance USD-M futures 15m public klines.
  - Sample months: 2023-07, 2024-06, 2025-08, 2026-05. HYPE covers only 2 sample months; DOGE covers 3; the other major symbols cover all 4.
  - Candidate grid: 816 candidates, cross-sectional strong/weak rotation and single-symbol momentum/reversal, leverage 1x/2x/4x, 0.2% round-trip cost.
  - Result: 18 static candidates are positive in all four sample months. The order>=10 monthly oracle is positive in all four months, worst month +244.10%, minimum monthly orders 18, but it is leaky and the return numbers are extreme.
  - Decision: `MULTISYMBOL_FREE_FUTURES_SAMPLE_UPPER_BOUND_HAS_SIGNAL`. Next step should be Strategy 32 full-history coverage plus strict monthly selector. Do not promote Strategy 31 directly.

- `STRATEGY_32_BTC_3M_2025_TODAY_UPPER_BOUND.md`
  - Strategy 32 is a user-requested BTC 3m upper-bound test from 2025 through the latest available public archive, not a strategy and not tradeable.
  - Audit id: `strategy_32_btc_3m_2025_today_upper_bound_20260628`.
  - Script: `scripts/audit_strategy_32_btc_3m_2025_today_upper_bound_20260628.py`.
  - Output: `artifacts/strategy_32_btc_3m_2025_today_upper_bound_20260628/summary.json`.
  - Data: Binance USD-M futures BTCUSDT 3m public klines from 2025-01-01 00:00 UTC through 2026-06-27 23:57 UTC. The 2026-06-28 daily archive was not available at run time.
  - Data quality passed: 260640 rows, no duplicate timestamps, no non-3m gaps, no calendar-filled bars.
  - Candidate grid: 348 single-BTC 3m momentum/reversal, EMA/Donchian trend, RSI/Bollinger mean-reversion, ATR breakout, and volume-body candidates, leverage 1x/2x/4x, 0.2% round-trip cost.
  - Result: 0 static candidates are positive in every month. The order>=10 monthly oracle has 2025 +51.33%, 2026 YTD +227.11%, but 11 non-positive months and worst month -3.67%.
  - Decision: `BTC_3M_2025_TODAY_UPPER_BOUND_FAILS`. Do not continue single-BTC 3m micro-rule expansion; if continuing, return to the Strategy 31 multi-symbol full-history strict-selector route.

- `STRATEGY_33_MULTISYMBOL_FREE_FUTURES_STRICT_SELECTOR.md`
  - Strategy 33 is the full-history multi-symbol strict monthly selector after Strategy 31's sample upper-bound signal, not a strategy and not tradeable.
  - Audit id: `strategy_33_multisymbol_free_futures_strict_selector_20260629`.
  - Script: `scripts/audit_strategy_33_multisymbol_free_futures_strict_selector_20260629.py`.
  - Output: `artifacts/strategy_33_multisymbol_free_futures_strict_selector_20260629/summary.json`.
  - Data: Binance USD-M futures 15m monthly klines for BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, DOGEUSDT, XRPUSDT, ADAUSDT, AVAXUSDT, and LINKUSDT from 2020-01-01 00:00 UTC through 2026-05-31 23:45 UTC. Main timestamp rows 224,928; duplicate timestamps 0; non-15m gaps 0. HYPEUSDT is excluded from candidate selection because its history is too short.
  - Candidate grid: 744 cross-sectional and single-symbol momentum/reversal candidates, leverage 1x/2x/4x, 0.2% round-trip cost.
  - Static hindsight hard-pass count: 0.
  - Monthly oracle with monthly orders >= 10 passes the original 2025/2026 YTD, every-month-positive, order-floor target, but it is leaky and not tradeable.
  - Best strict selector is `all_multisymbol`: 2023 +17.72%, 2024 -21.17%, 2025 -46.85%, 2026 YTD -5.64%, 21 non-positive months, minimum monthly orders 1.
  - Decision: `MULTISYMBOL_ORACLE_HAS_PIECES_BUT_STRICT_SELECTOR_FAILS`. Strategy 31's sample signal remains a hindsight-selection problem on full history; do not promote it or keep hand-expanding the same free multi-symbol kline micro-rules.

- `STRATEGY_34_MULTISYMBOL_FAILURE_ROOT_CAUSE.md`
  - Strategy 34 is a root-cause audit for Strategy 33, not a strategy and not tradeable.
  - Audit id: `strategy_34_multisymbol_failure_root_cause_20260629`.
  - Script: `scripts/audit_strategy_34_multisymbol_failure_root_cause_20260629.py`.
  - Output: `artifacts/strategy_34_multisymbol_failure_root_cause_20260629/summary.json`.
  - No new trading rules and no new downloads. It reuses Strategy 33's candidate monthly table, strict selector output, selected params, and leaky oracle output.
  - Key finding: all 41 evaluated months have at least one order>=10 positive-return candidate in hindsight, but the strict selector has 33 hard-nonpassing months.
  - Training hard-pass candidates are absent in every evaluated month: `months_with_no_train_hard_ok_candidates = 41`.
  - The hindsight monthly oracle winner is not findable by the past-performance selector: median hard-guard rank before the month is 222, top-10 months 0, top-50 months 1.
  - Following the previous month's oracle winner also fails badly: 2025 -99.9983%, 2026 YTD -96.7508%.
  - Loss split for the strict selector: 21 net losing months; only 3 are gross-win fee-killed months, while 18 are market-direction losses; 13 months have fewer than 10 trades.
  - Decision: `ROOT_CAUSE_UNSTABLE_HINDSIGHT_SELECTION`. The failure is not a small fee/turnover patch problem; the winning candidate changes too fast to select from prior performance. Do not add more trade-rule patches to this same family.

- `STRATEGY_35_OLD_BTC_3M_INSPIRATION_REVIEW.md`
  - Strategy 35 is a review of the separate local project `C:\Users\WHR\Documents\BTC多因子研究_20260626`, not a strategy and not tradeable.
  - Audit id: `strategy_35_old_btc_3m_inspiration_review_20260629`.
  - Script: `scripts/audit_strategy_35_old_btc_3m_inspiration_review_20260629.py`.
  - Output: `artifacts/strategy_35_old_btc_3m_inspiration_review_20260629/summary.json`.
  - The old project has a saved BTC 3m sample-in line: 2025 +145.67%, 2026 YTD +104.09%, 18/18 positive months, minimum monthly trades 340, and 0 bps label-vs-independent-price replay mismatch.
  - The same 7-rule line fails 2024 stress badly: -211.74%, only 2/12 positive months. Pre-2025 locked rules have 0 pass rows, and the pre-2025 ML router also has 0 pass rows.
  - Decision: `OLD_BTC_3M_GIVES_FRAMEWORK_NOT_DEPLOYABLE_RULES`. Borrow only the research framework: multi-timeframe features, funding/premium availability checks, event pools, capital-aware replay, and MTM validation. Do not copy the old rules, thresholds, 10x gross exposure, or sample-in selection.

- `STRATEGY_36_MULTISYMBOL_ENSEMBLE_SELECTOR.md`
  - Strategy 36 is a cheap strict ensemble-selector audit over Strategy 33's existing monthly candidate table, not a strategy and not tradeable.
  - Audit id: `strategy_36_multisymbol_ensemble_selector_20260629`.
  - Script: `scripts/audit_strategy_36_multisymbol_ensemble_selector_20260629.py`.
  - Output: `artifacts/strategy_36_multisymbol_ensemble_selector_20260629/summary.json`.
  - No new market data and no new trade rules. For each month, it selects top-k candidates using only prior-month candidate returns, then equal-weights the selected candidates at the monthly return level.
  - Config grid: 180 strict configs. Strict pass count: 0.
  - Best config: top_k 50, lookback 24, min_pos_rate 0.45, score pos_mean. Returns: 2023 -14.30%, 2024 -26.26%, 2025 +0.06%, 2026 YTD -22.93%, with 24 non-positive months and minimum monthly orders 546.
  - Decision: `ENSEMBLE_SELECTOR_ON_33_CANDIDATES_FAILS`. The simple ensemble shortcut does not rescue Strategy 33's candidate pool. Do not keep tuning Strategy 33 combinations; if pursuing the old BTC 3m inspiration, build a genuinely new 3m/multi-timeframe event-pool audit with strict walk-forward selection.

- `STRATEGY_37_BTC_3M_MULTITIMEFRAME_EVENT_POOL.md`
  - Strategy 37 is a BTCUSDT 3m multi-timeframe event-pool audit, not a strategy and not tradeable.
  - Audit id: `strategy_37_btc_3m_multitimeframe_event_pool_20260629`.
  - Script: `scripts/audit_strategy_37_btc_3m_multitimeframe_event_pool_20260629.py`.
  - Output: `artifacts/strategy_37_btc_3m_multitimeframe_event_pool_20260629/summary.json`.
  - Data: Binance USD-M futures BTCUSDT 3m monthly klines from 2020-01-01 00:00 UTC through 2026-05-31 23:57 UTC; 1,124,640 rows, duplicate timestamps 0, non-3m gaps 0, missing months 0.
  - Candidate grid: 496 event candidates using 3m trigger windows, longer 3m windows as 15m/1h/4h-style context, event holds, trend/range/volume families, leverage 1x/2x/4x, 0.2% round-trip cost.
  - Static hard-pass count: 0.
  - Best order>=10 monthly oracle: 2025 +503.35%, 2026 YTD +157.89%, but it still has 2 non-positive months: 2024-04 and 2025-10. This means the leaky upper bound itself misses the original every-month-positive target.
  - Best strict selector is `range_events`: 2023 -2.17%, 2024 -8.69%, 2025 -6.49%, 2026 YTD -7.45%, 27 non-positive months, minimum monthly orders 2.
  - The cheap monthly combo approximation also fails: best 2025 -9.44%, 2026 YTD 0.00%, 34 non-positive months.
  - Decision: `BTC_3M_MULTITIMEFRAME_EVENT_POOL_FAILS`. Do not keep patching this BTC 3m event pool; without genuinely different data, a more realistic shadow-tracking / lower-return validation target is more appropriate.

- `STRATEGY_38_FORCED_OVERFIT_ALPHA_MINING.md`
  - Strategy 38 is a deliberately leaky forced-overfit alpha-mining audit, not a strategy and not tradeable.
  - Audit id: `strategy_38_forced_overfit_alpha_mining_20260629`.
  - Script: `scripts/audit_strategy_38_forced_overfit_alpha_mining_20260629.py`.
  - Output: `artifacts/strategy_38_forced_overfit_alpha_mining_20260629/summary.json`.
  - No new market data and no new trade rules. It reuses Strategy 33 and Strategy 37 candidate monthly tables.
  - Method: for each evaluated month, choose the same-month best candidate among candidates with at least 10 orders. This sees the answer and is only for clue mining.
  - Combined leaky oracle hard-passes the original 2025/2026 YTD, every-month-positive, order-floor target: 2025 +17,665,719.09%, 2026 YTD +4,414.40%, 0 non-positive months, worst month +25.64%, minimum monthly orders 14.
  - Source split: Strategy 33 alone hard-passes with the same result; Strategy 37 alone fails because 2024-04 and 2025-10 are non-positive.
  - Winner pattern: 41/41 combined winners come from Strategy 33, mostly `single_symbol` 4x momentum/reversal structures. Frequent symbols include AVAX, SOL, LINK, XRP, DOGE, and ADA.
  - Non-leaky selection diagnostics are poor: the same-month oracle winner has median prior-training hard-guard rank 231, top-10 months 0, top-50 months 1, and following the previous month's winner loses badly in 2025 and 2026 YTD.
  - Decision: `FORCED_OVERFIT_ALPHA_CLUES_NOT_YET_TRADEABLE`. Keep the winner structures as research clues only; do not promote the leaky line. A next audit should test an independent no-future selector for these multi-symbol structures.

- `STRATEGY_39_ALPHA_PATTERN_DISCOVERY.md`
  - Strategy 39 is an alpha-pattern discovery audit, not a strategy and not tradeable.
  - Audit id: `strategy_39_alpha_pattern_discovery_20260629`.
  - Script: `scripts/audit_strategy_39_alpha_pattern_discovery_20260629.py`.
  - Output: `artifacts/strategy_39_alpha_pattern_discovery_20260629/summary.json`.
  - No new market data and no new trade rules. It explains Strategy 38 winners using Strategy 33 winners, candidate monthly rows, and the multi-symbol close panel.
  - Discovered pattern: hindsight winners are concentrated in multi-symbol altcoins, 4x, `single_symbol`, momentum/reversal. The 384-bar 15m lookback is most common. Frequent symbols are AVAX, SOL, LINK, XRP, DOGE, ADA, and ETH.
  - Predictive clue: winner symbols are usually recently active. Prior-month absolute-return top-5 hit rate is 72.5%; prior-month volatility top-5 hit rate is 72.5%.
  - Simple no-future transfer tests fail: month-start rules using previous high-volatility/high-absolute-return symbols cannot make 2025 and 2026 YTD both profitable. Best simple test `prev_abs_top2_reversal` has 2023 +100.22%, 2024 -40.50%, 2025 0.00%, 2026 YTD +18.01%.
  - Decision: `ALPHA_PATTERN_FOUND_BUT_SIMPLE_SELECTOR_STILL_FAILS`. The alpha shape is identified, but free-kline simple selectors do not trade it. If continuing, seek earlier identification signals such as funding, premium, order-flow, open interest, or long/short ratios.

- `STRATEGY_40_MULTISYMBOL_FUNDING_ALPHA_SELECTOR.md`
  - Strategy 40 is a multi-symbol funding-rate early-identification audit, not a strategy and not tradeable.
  - Audit id: `strategy_40_multisymbol_funding_alpha_selector_20260629`.
  - Script: `scripts/audit_strategy_40_multisymbol_funding_alpha_selector_20260629.py`.
  - Output: `artifacts/strategy_40_multisymbol_funding_alpha_selector_20260629/summary.json`.
  - It downloads only Binance public USD-M futures fundingRate REST history for Strategy 39's frequent winner symbols: ETH, SOL, DOGE, XRP, ADA, AVAX, and LINK.
  - Data range: 2022-12 through 2026-05. Each symbol has 3,834 rows over 42 months, duplicate timestamps 0, invalid 8h interval rows 0.
  - Winner funding clue: 40 Strategy 38 winner months have prior-month funding data; prior-month funding absolute-rank median is 3.5, top-3 hit rate is 50.0%, and prior-month funding is positive in 82.5% of winner months.
  - Best no-future selector test is `hot_abs_funding_abs_both`: 2023 +6,662.64%, 2024 -90.19%, 2025 +203.32%, 2026 YTD +18.01%, 17 traded months, 6 losing traded months, worst traded month -76.35%.
  - Decision: `FUNDING_SIGNAL_WEAK_NOT_TRADEABLE`. Funding adds a weak crowding clue and improves the Strategy 39 pattern, but it still does not meet the original target. Do not keep expanding funding-only micro-rules; test premium or order-flow as the next independent early signal.

- `STRATEGY_41_BTC_HYPE_RELAXED_DRAWDOWN.md`
  - Strategy 41 is a BTC+HYPE relaxed-gate audit, not a strategy and not tradeable.
  - Audit id: `strategy_41_btc_hype_relaxed_drawdown_20260629`.
  - Script: `scripts/audit_strategy_41_btc_hype_relaxed_drawdown_20260629.py`.
  - Output: `artifacts/strategy_41_btc_hype_relaxed_drawdown_20260629/summary.json`.
  - Relaxed gate: only BTCUSDT and HYPEUSDT; remove monthly-profit and monthly-order gates; require 2025 and 2026 YTD each >100%; require max drawdown no worse than -50%.
  - Data: BTC 15m has 224,928 rows from 2020-01-01 through 2026-05-31; HYPE 15m has 35,040 rows from 2025-06-01 through 2026-05-31. Duplicate timestamps 0, non-15m gaps 0.
  - Candidate grid: 1,008 BTC/HYPE pair and single-symbol momentum/reversal candidates with 0.2% round-trip cost. Static fixed-parameter relaxed pass count: 0.
  - Plain monthly oracle has huge returns but max drawdown -100%, so it fails the drawdown gate.
  - Drawdown-capped monthly oracle passes the 2025/2026 relaxed gate: 2025 +4,176.22%, 2026 YTD +100.67%, max drawdown -49.98%. This is leaky because it chooses the same-month winner after seeing the month.
  - Strict no-future selector fails: 2025 -16.27%, 2026 YTD -35.55%, max drawdown -40.04%.
  - Decision: `BTC_HYPE_DRAWDOWN_CAPPED_ORACLE_ONLY_PASSES`. Historical BTC+HYPE pieces can be overfit into the relaxed target, but there is still no tradeable no-future selector.

- `STRATEGY_42_BTC_HYPE_STATE_PREDICTABILITY.md`
  - Strategy 42 is a BTC+HYPE state-predictability audit after GPT Pro review, not a strategy and not tradeable.
  - Audit id: `strategy_42_btc_hype_state_predictability_20260629`.
  - Script: `scripts/audit_strategy_42_btc_hype_state_predictability_20260629.py`.
  - Output: `artifacts/strategy_42_btc_hype_state_predictability_20260629/summary.json`.
  - It uses small Binance public REST data only: `klines`, `fundingRate`, `premiumIndexKlines`, `markPriceKlines`. No full `aggTrades` download.
  - Months: 2025-06 through 2026-05.
  - Purpose: check whether month-start visible state can rank Strategy 41's BTC+HYPE candidates well enough to keep the drawdown-capped oracle winner in a small shortlist.
  - K20 contains the Strategy 41 safe oracle winner in only 33.33% of months. K10 retention is 16.67%; K50 retention is also 33.33%.
  - K20 ordinary oracle upper bound: 2025 +254.72%, 2026 YTD +129.73%, but max drawdown -99.999%, so it fails the relaxed drawdown gate.
  - K20 drawdown-capped oracle upper bound: 2025 +191.46%, 2026 YTD +36.17%, max drawdown -47.88%, so 2026 still fails.
  - Strict top1 state score: 2025 +29.45%, 2026 YTD -32.95%, max drawdown -99.999%.
  - Decision: `BTC_HYPE_STATE_FEATURES_FAIL_FIRST_PASS`. The cheap month-start state-ranking shortcut fails. If continuing, test dynamic intramonth state gating; do not promote this audit.

- `STRATEGY_43_BTC_HYPE_TAIL_EVENT_ATTRIBUTION.md`
  - Strategy 43 is a BTC+HYPE tail-event attribution audit, not a strategy and not tradeable.
  - Audit id: `strategy_43_btc_hype_tail_event_attribution_20260629`.
  - Script: `scripts/audit_strategy_43_btc_hype_tail_event_attribution_20260629.py`.
  - Output: `artifacts/strategy_43_btc_hype_tail_event_attribution_20260629/summary.json`.
  - It replays Strategy 41's drawdown-capped oracle bar PnL and checks whether profits concentrate around predefined BTC/HYPE tail-event windows using Strategy 42's BTC/HYPE 15m data.
  - Tail event definition: HYPE 4h absolute return >=5%, or HYPE 24h absolute return >=12%, or abs(HYPE-minus-BTC 4h residual z) >=2.5. Event window is +/-48h.
  - Results: raw tail-event bars are 6.20% of bars; +/-48h event windows cover 79.05% of bars; 90.44% of positive log PnL falls inside event windows; net log PnL inside windows is +4.7580 and outside windows is -0.3059.
  - Decision: `TAIL_EVENTS_DOMINATE_ORACLE_PNL`. Strategy 41's oracle profits are tied to tail-event regimes, but the event window is broad, so this is only an attribution clue. If continuing, run a separate event-after-action oracle before any strict policy.

- `STRATEGY_44_BTC_HYPE_TAIL_EVENT_ACTION_ORACLE.md`
  - Strategy 44 is a BTC+HYPE tail-event-after-action oracle, not a strategy and not tradeable.
  - Audit id: `strategy_44_btc_hype_tail_event_action_oracle_20260629`.
  - Script: `scripts/audit_strategy_44_btc_hype_tail_event_action_oracle_20260629.py`.
  - Output: `artifacts/strategy_44_btc_hype_tail_event_action_oracle_20260629/summary.json`.
  - Event detection uses only closed past bars; action selection uses future returns after the event.
  - Best event thresholds: abs(HYPE 4h return) >=4%, or abs(HYPE 24h return) >=10%, or abs(HYPE-minus-BTC 4h residual z) >=2.0; min_gap 16; max per-trade drawdown filter -30%.
  - Best action oracle passes the relaxed BTC/HYPE gate: 2025 +2,349,453,758,140.50%, 2026 YTD +3,774,017,741.59%, max drawdown -31.94%, 161 trades, turnover 1,330.0.
  - Action mix: HYPE reversal 63, HYPE momentum 62, BTC momentum 14, pair relative-value reversal 12, BTC reversal 10.
  - Decision: `TAIL_EVENT_ACTION_ORACLE_PASSES_RELAXED_GATE`. Historical tail events have enough after-event action opportunity, but this is still a future oracle.

- `STRATEGY_45_BTC_HYPE_TAIL_EVENT_FITTED_POLICY.md`
  - Strategy 45 is a forced-overfit fitted tail-event policy, not a live strategy and not tradeable.
  - Audit id: `strategy_45_btc_hype_tail_event_fitted_policy_20260629`.
  - Script: `scripts/audit_strategy_45_btc_hype_tail_event_fitted_policy_20260629.py`.
  - Output: `artifacts/strategy_45_btc_hype_tail_event_fitted_policy_20260629/summary.json`.
  - It fits decision trees on Strategy 44 oracle labels and evaluates on the same 2025-06 through 2026-05 period.
  - Best policy is a `market_only` decision tree, depth 16, 100 leaves, train accuracy 100%; it exactly matches the 161 Strategy 44 oracle event trades.
  - In-sample result: 2025 +2,349,453,758,140.50%, 2026 YTD +3,774,017,741.59%, max drawdown -31.94%, 161 trades, turnover 1,330.0.
  - Most important market-only features include HYPE/BTC residual z, HYPE/BTC 4-day trend, HYPE/BTC 24h returns, HYPE 4h shock, premium, and funding.
  - Decision: `TAIL_EVENT_FITTED_POLICY_PASSES_IN_SAMPLE_RELAXED_GATE`. This proves a historical overfit can pass, but the labels come from same-period future oracle. Next useful audit is Strategy 46: strict walk-forward tree training using only prior tail events, then testing the next month.

- `STRATEGY_46_BTC_HYPE_TAIL_EVENT_WALKFORWARD_POLICY.md`
  - Strategy 46 is a strict walk-forward validation of Strategy 45, not a live strategy and not tradeable.
  - Audit id: `strategy_46_btc_hype_tail_event_walkforward_policy_20260629`.
  - Script: `scripts/audit_strategy_46_btc_hype_tail_event_walkforward_policy_20260629.py`.
  - Output: `artifacts/strategy_46_btc_hype_tail_event_walkforward_policy_20260629/summary.json`.
  - Each month trains only on earlier Strategy 44 oracle-labeled tail events, then tests the current month. Current-month labels are not used for current-month training.
  - Best strict walk-forward policy is `market_plus_time`, depth 5, min_samples_leaf 3: 2025 +230.13%, 2026 YTD +865.81%, but max drawdown -84.48%, 130 trades, turnover 1,052.0.
  - Simple temporary monthly/global drawdown stops were also probed after the formal run; none passed the relaxed gate because drawdown-safe variants lost too much return while high-return variants still exceeded the drawdown limit.
  - Decision: `TAIL_EVENT_WALKFORWARD_POLICY_FAILS_RELAXED_GATE`. Strategy 45 found a strong in-sample overfit pattern, but it is not yet a validated alpha.

- `STRATEGY_47_BTC_HYPE_TAIL_EVENT_CAUSAL_RISK_OVERLAY.md`
  - Strategy 47 adds causal per-trade risk controls to Strategy 46's strict walk-forward tail-event policy. It is still not a live strategy and not tradeable.
  - Audit id: `strategy_47_btc_hype_tail_event_causal_risk_overlay_20260629`.
  - Script: `scripts/audit_strategy_47_btc_hype_tail_event_causal_risk_overlay_20260629.py`.
  - Output: `artifacts/strategy_47_btc_hype_tail_event_causal_risk_overlay_20260629/summary.json`.
  - Event detection uses closed past bars; each month trains only on earlier oracle-labeled events; risk exits use only trade-to-date PnL/drawdown. The risk grid itself is still selected on the same 2025-06 through 2026-05 sample.
  - Scan size: 7,560 configs; relaxed-gate pass count: 99.
  - Best config: `market_plus_time`, depth 5, min_samples_leaf 3, position_scale 0.8, trailing_stop -10%, take_profit 20%: 2025 +281.55%, 2026 YTD +226.41%, max drawdown -45.23%, 130 trades, turnover 844.8.
  - More conservative no-time-feature pass: `market_only`, depth 6, min_samples_leaf 3, position_scale 0.65, trailing_stop -8%, take_profit 50%: 2025 +180.30%, 2026 YTD +222.40%, max drawdown -42.22%, 124 trades, turnover 650.0.
  - Decision: `TAIL_EVENT_CAUSAL_RISK_OVERLAY_PASSES_RELAXED_GATE_IN_SAMPLE`. This is the first BTC+HYPE result after 41 that is strict walk-forward on action labels and passes the relaxed return/drawdown gate with causal risk management, but it remains in-sample parameter selection. Recommended next audit: Strategy 48 freezes Strategy 47 parameters and tests latest/unseen data or shadow-tracking protocol.

- `STRATEGY_49_BTC_HYPE_FROZEN_47_LATEST_PUBLIC.md`
  - Strategy 49 freezes Strategy 47 parameters and tests them on latest public 2026-06 BTC/HYPE data. It is not a live strategy and not tradeable.
  - Audit id: `strategy_49_btc_hype_frozen_47_latest_public_20260629`.
  - Script: `scripts/audit_strategy_49_btc_hype_frozen_47_latest_public_20260629.py`.
  - Output: `artifacts/strategy_49_btc_hype_frozen_47_latest_public_20260629/summary.json`.
  - Numbering note: local uncommitted Strategy 48 public Jesse proxy-backtest files already exist, so this BTC/HYPE frozen validation uses 49 to avoid overwriting or mixing work.
  - It freezes Strategy 47 best and market-only configs, does not rescan parameters on latest data, and fetches Binance USD-M futures public REST data through the last closed 15m bar at 2026-06-29 15:00 UTC. BTC/HYPE rows are 5,726 each; duplicates 0; missing 15m rows 0.
  - Frozen Strategy 47 best config on 2026-06: return -14.09%, max drawdown -36.31%, 13 trades.
  - Frozen Strategy 47 market-only config on 2026-06: return -23.44%, max drawdown -46.38%, 13 trades.
  - Decision: `FROZEN_47_LATEST_PARTIAL_MONTH_FAILS`. Strategy 47 should not go to live/testnet. Recommended next audit, if continuing, is failure attribution: determine whether June had no after-event opportunity or whether Strategy 47 picked the wrong action/risk exits; do not tune parameters on June.

- `STRATEGY_50_2C_WITHOUT_MONTHLY_LOCK.md`
  - Strategy 50 tests the user's request to remove Strategy 2C's monthly profit lock. It is not a live strategy and not tradeable.
  - Audit id: `strategy_50_2c_without_monthly_lock_20260629`.
  - Script: `scripts/audit_strategy_50_2c_without_monthly_lock_20260629.py`.
  - Output: `artifacts/strategy_50_2c_without_monthly_lock_20260629/summary.json`.
  - It reuses Strategy 2C/1F signal and guard logic, keeps the same 0.2% round-trip cost, and tests two variants: removing the monthly halt while keeping the pre-10-trade quota throttle, and removing both.
  - `no_lock_keep_quota`: 2025 -99.97%, 2026 -11.19%, worst month -91.98%, 13 losing months, max drawdown -99.99%.
  - `no_lock_no_quota`: 2025 -99.98%, 2026 +131.38%, worst month -89.48%, 13 losing months, max drawdown about -100%.
  - Decision: `MONTHLY_LOCK_IS_CRITICAL_FOR_2C`. Removing the monthly lock turns 2C into near-always-in-market exposure with far higher turnover and catastrophic drawdown. Do not use direct lock removal as an upgrade path.

- `STRATEGY_51_2C_LOCK_MIN_ORDERS_SENSITIVITY.md`
  - Strategy 51 tests the user's concern that Strategy 2C only works because it locks monthly profit after roughly 10 trades. It is not a live strategy and not tradeable.
  - Audit id: `strategy_51_2c_lock_min_orders_sensitivity_20260629`.
  - Script: `scripts/audit_strategy_51_2c_lock_min_orders_sensitivity_20260629.py`.
  - Output: `artifacts/strategy_51_2c_lock_min_orders_sensitivity_20260629/summary.json`.
  - It keeps most Strategy 2C logic unchanged, keeps the 0.2% round-trip cost, keeps the pre-10-trade quota throttle, and varies only the minimum number of monthly trades required before profit lock can halt trading: 10, 20, 30, 50, 100, and no lock.
  - Only `lock_after_10_orders` passes: 2025 +359.10%, 2026 +260.59%, worst month +5.58%, max drawdown -29.40%.
  - `lock_after_20_orders` already fails: 2025 -84.39%, 2026 +460.62%, worst month -87.98%, 3 losing months, max drawdown -95.46%.
  - 30/50/100 trade thresholds and no-lock variants are near-collapses, with max drawdowns near -100%.
  - Decision: `TEN_TRADE_MONTHLY_LOCK_IS_A_FRAGILE_PART_OF_2C`. The user's criticism is valid: 2C is not a robust raw signal; it is a historical candidate highly dependent on early monthly profit locking. Do not continue small ret_state/2C tweaks as a serious upgrade path.

- `STRATEGY_52_2C_FIRST10_VS_AFTER10_ATTRIBUTION.md`
  - Strategy 52 is an attribution audit, not a strategy and not tradeable.
  - Audit id: `strategy_52_2c_first10_vs_after10_20260629`.
  - Script: `scripts/audit_strategy_52_2c_first10_vs_after10_20260629.py`.
  - Output: `artifacts/strategy_52_2c_first10_vs_after10_20260629/summary.json`.
  - It reuses Strategy 50's no-lock/keep-quota 2C replay and splits each month into the area before 10 monthly orders and the area after 10 monthly orders.
  - First-10-order area: 2025 +183.19%, 2026 +216.76%, 2 losing months.
  - After-10-order area: 2025 -99.99%, 2026 -71.96%, 14 losing months, high turnover and high exposure.
  - Decision: `POST_10_TRADES_EXPOSES_WEAK_RAW_SIGNAL`. The user's interpretation is correct: 10-trade monthly locking is not a robust edge; it hides the poor quality of the later trading area. If researching this family further, only test whether the early-month/first-10-trades concentration can be identified strictly without future data.

- `STRATEGY_53_2C_FIRST_N_ORDERS_ONLY.md`
  - Strategy 53 tests whether the first-10-trades clue can stand without the monthly profit-threshold lock. It is not a live strategy and not tradeable.
  - Audit id: `strategy_53_2c_first_n_orders_only_20260630`.
  - Script: `scripts/audit_strategy_53_2c_first_n_orders_only_20260630.py`.
  - Output: `artifacts/strategy_53_2c_first_n_orders_only_20260630/summary.json`.
  - It reuses Strategy 2C logic, ignores the monthly profit threshold, and simply trades only the first N monthly orders before forcing flat for the rest of the month. N tested: 5, 10, 15, 20.
  - No variant passes the original monthly-profit hard target.
  - Under the relaxed gate of 2025/2026 each above +100% and max drawdown no worse than -50%, `first_5_orders_then_flat` and `first_10_orders_then_flat` pass.
  - `first_10_orders_then_flat`: 2025 +202.08%, 2026 +261.07%, worst month -7.91%, 2 losing months, max drawdown -29.25%.
  - Decision: `FIRST_N_ONLY_HAS_RELAXED_SIGNAL_NOT_ORIGINAL_PASS`. The early-window clue is not just a profit-threshold artifact, but it is still post-hoc and should not be promoted. If continuing, freeze first5/first10 and validate on earlier history plus latest public data without retuning N.

- `STRATEGY_54_2C_CORE_SIGNAL_FAILURE.md`
  - Strategy 54 is a core-signal failure attribution requested after the user clarified that the problem is the strategy itself, not order count. It is not a live strategy and not tradeable.
  - Audit id: `strategy_54_2c_core_signal_failure_20260630`.
  - Script: `scripts/audit_strategy_54_2c_core_signal_failure_20260630.py`.
  - Output: `artifacts/strategy_54_2c_core_signal_failure_20260630/summary.json`.
  - It directly tests the old Strategy 2C / `ret_state 64/100` direction signal without monthly early stop, under 1x/8x, zero/normal cost, and compares the Strategy 2C guards without lock.
  - Core signal 1x zero cost no lock: 2025 -4.90%, 2026 +100.48%, max drawdown -37.12%.
  - Core signal 1x normal cost no lock: 2025 -48.95%, 2026 +50.61%, max drawdown -76.58%.
  - Core signal 8x normal cost no lock: 2025 -99.54%, max drawdown about -100%.
  - Strategy 2C guards without early lock also nearly collapse: keep-quota version 2025 -99.97%, 2026 -11.19%, max drawdown -99.99%.
  - One-bar direction edge at 1x zero cost: 2024 +14.26%, 2025 -4.90%, 2026 +100.48%; 2025 win rate 49.53%, average edge -0.0143 bps.
  - Decision: `CORE_RET_STATE_SIGNAL_NOT_GOOD_ENOUGH`. The user's correction is valid: the old 2C/ret_state family should not be repaired by changing lock/order-count/risk patches. Future work should switch the core signal source.

- `STRATEGY_55_BTC_HYPE_TAIL_EVENT_CORE_SIGNAL.md`
  - Strategy 55 is the first audit after switching away from old 2C/ret_state. It is not a live strategy and not tradeable.
  - Audit id: `strategy_55_btc_hype_tail_event_core_signal_20260630`.
  - Script: `scripts/audit_strategy_55_btc_hype_tail_event_core_signal_20260630.py`.
  - Output: `artifacts/strategy_55_btc_hype_tail_event_core_signal_20260630/summary.json`.
  - It uses BTC/HYPE tail-event triggers: HYPE 4h/24h large moves or HYPE-vs-BTC 4h residual z extremes. Fixed actions include HYPE/BTC momentum, reversal, and pair trades. Holds are 16/32/64/96 15m bars; leverage is 0.5/1/2. Candidate count: 144.
  - Data covers 2025-06 through 2026-06-29 15:15 UTC using Strategy 41 BTC/HYPE panel plus Strategy 49 latest public REST klines.
  - Static fixed-candidate pass count: 0. Best static candidate `loose_hype_reversal_hold64_lev2p0`: 2025 +34.83%, 2026 +104.15%, max drawdown -71.97%, 7 losing months.
  - Strict prior-month selector: 2025 -11.64%, 2026 -0.41%, max drawdown -10.83%, 10 losing months.
  - Normal monthly oracle has high returns but max drawdown -91.10%, so it fails the relaxed drawdown gate.
  - Drawdown-capped monthly oracle passes: 2025 +1689.67%, 2026 +1047.55%, max drawdown -40.66%, 0 losing months. This is leaky and cannot be traded.
  - Decision: `TAIL_EVENT_CORE_DRAWDOWN_CAPPED_ORACLE_ONLY_PASSES`. The new core source has event-after-action space, but the current fixed/strict selector cannot pick actions ahead of time. If continuing, Strategy 56 should focus on causal action selection after tail events, not on old 2C repairs.

- `STRATEGY_56_TAIL_EVENT_LOSS_ROOT_CAUSE.md`
  - Strategy 56 is a loss root-cause audit for Strategy 55, not a strategy and not tradeable.
  - Audit id: `strategy_56_tail_event_loss_root_cause_20260630`.
  - Script: `scripts/audit_strategy_56_tail_event_loss_root_cause_20260630.py`.
  - Output: `artifacts/strategy_56_tail_event_loss_root_cause_20260630/summary.json`.
  - It reuses Strategy 55 outputs only: no new candidates and no parameter tuning.
  - Decision: `LOSS_ROOT_CAUSE_UNSTABLE_ACTION_SELECTION`.
  - Root cause: event opportunities exist, but the correct post-event action switches too quickly by month. The drawdown-capped oracle uses 10 different candidates across 13 months and switches action 10 times.
  - Oracle action distribution: HYPE momentum 6 months, HYPE reversal 4, BTC momentum 2, BTC reversal 1.
  - Strict selector action distribution: BTC momentum 9 months, pair reversal 2, BTC reversal 1. It controls drawdown by choosing conservative BTC actions but misses HYPE event profits.
  - Strict selector matches the exact oracle candidate in 0 months, matches oracle action in only 2 months, and misses positive oracle months 10 times.
  - Oracle winner prior-training rank median is 98 out of 144; it is in the top 10 in 0/12 rankable months.
  - Following the previous month's oracle winner is positive only 5/12 months; simple return sum is +22.81% versus +652.46% for current-month oracle over those same months.
  - Next useful audit: Strategy 57 should test whether features known at event time can predict momentum vs reversal/action choice. Do not use past monthly return ranking as selector.

- `STRATEGY_57_TAIL_EVENT_STATE_ACTION_PREDICTABILITY.md`
  - Strategy 57 tests whether event-time state features can predict post-tail-event action choice without using current-month labels. It is not a strategy and not tradeable.
  - Audit id: `strategy_57_tail_event_state_action_predictability_20260630`.
  - Script: `scripts/audit_strategy_57_tail_event_state_action_predictability_20260630.py`.
  - Output: `artifacts/strategy_57_tail_event_state_action_predictability_20260630/summary.json`.
  - Data uses Strategy 41 BTC/HYPE close panel plus Strategy 49 latest public klines, covering 2025-06-01 through 2026-06-29 15:15 UTC, 37,790 15m bars, no duplicate timestamps and no non-15m gaps.
  - Event labels are oracle labels based on future post-event returns, but walk-forward training only uses labels from months before the tested month.
  - Event-label oracle passes the relaxed gate: 2025 +1528.72%, 2026 +659.73%, max drawdown -38.23%, 268 trades, 0 losing months. This is leaky and cannot be traded.
  - Best full-label walk-forward policy fails: `market_only`, depth 6, min leaf 5, 2025 -24.71%, 2026 +73.97%, max drawdown -41.65%, 5 losing months.
  - Best action-only walk-forward policy also fails: `market_only`, depth 6, min leaf 8, hold 64 bars, leverage 2.0, 2025 +27.13%, 2026 +9.63%, max drawdown -35.36%, 8 losing months.
  - Decision: `EVENT_STATE_LABEL_ORACLE_PASSES_BUT_WALKFORWARD_FAILS`. Tail events still have post-event opportunity, but the current simple state features / decision tree cannot reliably predict future-month action choice. Do not keep tuning tree depth, leaf size, hold bars, or leverage as the next step.

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
- `scripts/audit_strategy_5b_three_way_20260627.py`
- `scripts/audit_strategy_6_market_regime_20260627.py`
- `scripts/audit_strategy_7_oracle_router_20260627.py`
- `scripts/audit_strategy_8_execution_stress_20260627.py`
- `scripts/audit_strategy_9_cold_start_feasibility_20260627.py`
- `scripts/audit_strategy_10_pre2024_data_probe_20260627.py`
- `scripts/audit_strategy_11_true_2024_walkforward_20260627.py`
- `scripts/audit_strategy_12_202412_failure_review_20260627.py`
- `scripts/search_strategy_13_low_turnover_prevention_20260627.py`
- `scripts/audit_strategy_14_pre2023_expanding_crowding_stress_20260627.py`
- `scripts/audit_strategy_15_unified_data_baseline_20260627.py`
- `scripts/audit_strategy_16_new_family_probe_20260627.py`
- `scripts/audit_strategy_17_simple_family_upper_bound_20260627.py`
- `scripts/audit_strategy_18_upper_bound_failure_review_20260627.py`
- `scripts/audit_strategy_19_calendar_seasonality_probe_20260627.py`
- `scripts/audit_strategy_20_ohlc_structure_upper_bound_20260627.py`
- `scripts/audit_strategy_21_volume_upper_bound_20260627.py`
- `scripts/audit_strategy_22_hard_target_bottleneck_20260627.py`
- `scripts/audit_strategy_23_funding_rate_upper_bound_20260627.py`
- `scripts/audit_strategy_24_funding_rate_strict_selector_20260627.py`
- `scripts/audit_strategy_25_open_interest_upper_bound_feasibility_20260627.py`
- `scripts/audit_strategy_26_intrabar_1m_upper_bound_20260627.py`
- `scripts/audit_strategy_27_target_feasibility_20260627.py`
- `scripts/audit_strategy_28_relaxed_no_monthly_profit_20260628.py`
- `scripts/audit_strategy_29_free_raw_trade_coverage_20260628.py`
- `scripts/audit_strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628.py`
- `scripts/audit_strategy_31_multisymbol_free_futures_upper_bound_20260628.py`
- `scripts/audit_strategy_32_btc_3m_2025_today_upper_bound_20260628.py`
- `scripts/audit_strategy_33_multisymbol_free_futures_strict_selector_20260629.py`
- `scripts/audit_strategy_34_multisymbol_failure_root_cause_20260629.py`
- `scripts/audit_strategy_35_old_btc_3m_inspiration_review_20260629.py`
- `scripts/audit_strategy_36_multisymbol_ensemble_selector_20260629.py`
- `scripts/audit_strategy_37_btc_3m_multitimeframe_event_pool_20260629.py`
- `scripts/audit_strategy_38_forced_overfit_alpha_mining_20260629.py`
- `scripts/audit_strategy_39_alpha_pattern_discovery_20260629.py`
- `scripts/audit_strategy_40_multisymbol_funding_alpha_selector_20260629.py`
- `scripts/audit_strategy_41_btc_hype_relaxed_drawdown_20260629.py`
- `scripts/audit_strategy_42_btc_hype_state_predictability_20260629.py`
- `scripts/audit_strategy_43_btc_hype_tail_event_attribution_20260629.py`
- `scripts/audit_strategy_44_btc_hype_tail_event_action_oracle_20260629.py`
- `scripts/audit_strategy_45_btc_hype_tail_event_fitted_policy_20260629.py`
- `scripts/audit_strategy_46_btc_hype_tail_event_walkforward_policy_20260629.py`
- `scripts/audit_strategy_47_btc_hype_tail_event_causal_risk_overlay_20260629.py`
- `scripts/audit_strategy_49_btc_hype_frozen_47_latest_public_20260629.py`
- `scripts/audit_strategy_50_2c_without_monthly_lock_20260629.py`
- `scripts/audit_strategy_51_2c_lock_min_orders_sensitivity_20260629.py`
- `scripts/audit_strategy_52_2c_first10_vs_after10_20260629.py`
- `scripts/audit_strategy_53_2c_first_n_orders_only_20260630.py`
- `scripts/audit_strategy_54_2c_core_signal_failure_20260630.py`
- `scripts/audit_strategy_55_btc_hype_tail_event_core_signal_20260630.py`
- `scripts/audit_strategy_56_tail_event_loss_root_cause_20260630.py`
- `scripts/audit_strategy_57_tail_event_state_action_predictability_20260630.py`
- `scripts/plot_strategy_trade_charts_20260627.py`
- `src/btc_ml_trader/backtest.py`

What advice is needed:

1. Suggest only methods that can be implemented as strict no-future backtests.
2. Prefer concrete algorithm changes over general trading risk advice.
3. If proposing ML, specify exact walk-forward training windows, label availability, threshold calibration, and leakage checks.
4. If the hard requirements look infeasible, suggest upper-bound tests that can prove where the bottleneck is.
