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
- `scripts/plot_strategy_trade_charts_20260627.py`
- `src/btc_ml_trader/backtest.py`

What advice is needed:

1. Suggest only methods that can be implemented as strict no-future backtests.
2. Prefer concrete algorithm changes over general trading risk advice.
3. If proposing ML, specify exact walk-forward training windows, label availability, threshold calibration, and leakage checks.
4. If the hard requirements look infeasible, suggest upper-bound tests that can prove where the bottleneck is.
