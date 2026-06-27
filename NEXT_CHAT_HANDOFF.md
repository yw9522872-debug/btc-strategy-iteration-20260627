# 下一窗口交接

本文件用于开启新的 Codex 对话时交接本项目。

## 项目身份

- 本地路径：`C:\Users\WHR\Documents\策略迭代`
- GitHub：`https://github.com/yw9522872-debug/btc-strategy-iteration-20260627`
- 15-19 保存提交：`ff67b92 Add strategy 15-19 research probes`
- 当前最新标签：`strategy-15-unified-data-baseline-20260627`、`strategy-16-new-family-probe-20260627`、`strategy-17-simple-family-upper-bound-20260627`、`strategy-18-upper-bound-failure-review-20260627`、`strategy-19-calendar-seasonality-probe-20260627`、`strategy-20-ohlc-structure-upper-bound-20260627`、`strategy-21-volume-upper-bound-20260627`
- 15号、16号、17号、18号、19号、20号、21号、22号及交接说明已提交并推送到 GitHub
- 1F/1G 策略结果提交：`e4232d3`
- 固化标签：`strategy-freeze-monthly-profit-lock-20260627`
- 固化标签对应提交：`910d99a`
- 当前固化策略源提交：`0c69585`
- 0号策略定位文件：`STRATEGY_0.md`
- 1号F保存标签：`strategy-1f-selective-runner-20260627`
- 1号G保存标签：`strategy-1g-cap7-selective-runner-20260627`
- 2号C保存标签：`strategy-2c-lock-cap-20260627`
- 4号候选保存标签：`strategy-4-entry-confirm-20260627`
- 5号审计保存标签：`strategy-5-robustness-audit-20260627`
- 5B审计保存标签：`strategy-5b-three-way-audit-20260627`
- 6号市场状态体检保存标签：`strategy-6-market-regime-audit-20260627`
- 7号 Oracle 路由上限审计保存标签：`strategy-7-oracle-router-audit-20260627`
- 8号执行压力审计保存标签：`strategy-8-execution-stress-20260627`
- 9号冷启动可行性审计保存标签：`strategy-9-cold-start-feasibility-20260627`
- 10号 pre-2024 数据探针保存标签：`strategy-10-pre2024-data-probe-20260627`
- 11号真正 2024 walk-forward 审计保存标签：`strategy-11-true-2024-walkforward-20260627`
- 12号 2024-12 失败复盘保存标签：`strategy-12-202412-failure-review-20260627`
- 13号低换手/低反手预防规则保存标签：`strategy-13-low-turnover-prevention-20260627`
- 14号 pre-2023 扩展滚动与拥挤压力审计保存标签：`strategy-14-pre2023-expanding-crowding-stress-audit-20260627`
- 15号统一数据底座体检保存标签：`strategy-15-unified-data-baseline-20260627`
- 16号新策略族可行性探针保存标签：`strategy-16-new-family-probe-20260627`
- 17号简单策略族上限测试保存标签：`strategy-17-simple-family-upper-bound-20260627`
- 18号上限失败月份复盘保存标签：`strategy-18-upper-bound-failure-review-20260627`
- 19号日历季节性探针保存标签：`strategy-19-calendar-seasonality-probe-20260627`
- 20号 OHLC结构上限测试保存标签：`strategy-20-ohlc-structure-upper-bound-20260627`
- 21号成交量上限测试保存标签：`strategy-21-volume-upper-bound-20260627`
- 22号硬目标瓶颈审计保存标签：`strategy-22-hard-target-bottleneck-audit-20260627`

不要和其他 Codex 线程、其他 Chrome/GPT Pro 页面、其他仓库混用。

## 必读文件

1. `AGENTS.md`
2. `STRATEGY_0.md`
3. `STRATEGY_1_CANDIDATE.md`
4. `STRATEGY_1B_CANDIDATE.md`
5. `STRATEGY_1C_CANDIDATE.md`
6. `STRATEGY_1F_CANDIDATE.md`
7. `STRATEGY_1G_CANDIDATE.md`
8. `STRATEGY_2C_CANDIDATE.md`
9. `STRATEGY_4_CANDIDATE.md`
10. `STRATEGY_5_ROBUSTNESS_AUDIT.md`
11. `STRATEGY_5B_THREE_WAY_AUDIT.md`
12. `STRATEGY_6_MARKET_REGIME_AUDIT.md`
13. `STRATEGY_7_ORACLE_ROUTER_AUDIT.md`
14. `STRATEGY_8_EXECUTION_STRESS_AUDIT.md`
15. `STRATEGY_9_COLD_START_FEASIBILITY.md`
16. `STRATEGY_10_PRE2024_DATA_PROBE.md`
17. `STRATEGY_11_TRUE_2024_WALKFORWARD.md`
18. `STRATEGY_12_202412_FAILURE_REVIEW.md`
19. `STRATEGY_13_LOW_TURNOVER_PREVENTION.md`
20. `STRATEGY_14_PRE2023_EXPANDING_CROWDING_STRESS_AUDIT.md`
21. `STRATEGY_15_UNIFIED_DATA_BASELINE.md`
22. `STRATEGY_16_NEW_FAMILY_PROBE.md`
23. `STRATEGY_17_SIMPLE_FAMILY_UPPER_BOUND.md`
24. `STRATEGY_18_UPPER_BOUND_FAILURE_REVIEW.md`
25. `STRATEGY_19_CALENDAR_SEASONALITY_PROBE.md`
26. `STRATEGY_20_OHLC_STRUCTURE_UPPER_BOUND.md`
27. `STRATEGY_21_VOLUME_UPPER_BOUND.md`
28. `STRATEGY_22_HARD_TARGET_BOTTLENECK_AUDIT.md`
29. `RESEARCH_DECISION_STOP_SIMPLE_RULES_AFTER_22.md`
30. `CURRENT_STRATEGY_FREEZE.md`
31. `GPT_PRO_REVIEW_BRIEF.md`
32. `artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json`
33. `artifacts/strategy_15_unified_data_baseline_20260627/summary.json`
34. `artifacts/strategy_16_new_family_probe_20260627/summary.json`
35. `artifacts/strategy_17_simple_family_upper_bound_20260627/summary.json`
36. `artifacts/strategy_18_upper_bound_failure_review_20260627/summary.json`
37. `artifacts/strategy_19_calendar_seasonality_probe_20260627/summary.json`
38. `artifacts/strategy_20_ohlc_structure_upper_bound_20260627/summary.json`
39. `artifacts/strategy_21_volume_upper_bound_20260627/summary.json`
40. `artifacts/strategy_22_hard_target_bottleneck_20260627/summary.json`

## 当前固化策略

- 策略编号：`0号策略`
- 固化编号：`monthly_profit_lock_research_freeze_20260627`
- 品种：`BTCUSDT`
- 周期：`15m`
- 信号：`ret_state`
- 回看窗口：`64` 根 15分钟K线
- 阈值：`100 bps`
- 杠杆：`8x`
- 手续费：开平合计 `0.2%`，代码里单边 `0.001`
- 月度锁利：当月至少 `10` 次交易且当月净对数收益达到 `0.04` 后，本月剩余时间空仓
- 月内补交易控制：当月净对数收益达到 `0.12` 但交易次数未满 `10` 次时，仓位降到 `0.1x` 直到交易次数补够

## 已知结果

按固化版历史结果：

| 年份 | 收益率 | 胜率 | 交易次数 | 最大回撤 |
|---|---:|---:|---:|---:|
| 2025 | `+326.26%` | `50.00%` | `148` | `-48.53%` |
| 2026 | `+106.93%` | `50.66%` | `72` | `-18.21%` |

胜率口径是“持仓中的 15分钟K线正收益占比”，不是严格单笔完整交易胜率。

## 1号策略候选

- 候选编号：`strategy_1_candidate_20260627`
- 定位文件：`STRATEGY_1_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1_candidate_20260627.py`
- 结果：`artifacts/strategy_1_candidate_20260627/summary.json`
- 2025：`+171.35%`，交易 `152` 次，最大回撤 `-24.01%`
- 2026：`+126.55%`，交易 `74` 次，最大回撤 `-19.42%`
- 每个评估月份都盈利，最低月交易次数 `12`
- 注意：它还不是固化版；固定信号 `ret_state 64/100` 仍来自前期历史研究。
- 另一个更自由的测试 `artifacts/strategy_1_walkforward_20260627/summary.json` 失败：2025 `-22.09%`，说明信号自由滚动选会追错参数。

## 1号B策略候选

- 候选编号：`strategy_1b_expanded_controls_20260627`
- 定位文件：`STRATEGY_1B_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1b_expanded_controls_20260627.py`
- 结果：`artifacts/strategy_1b_expanded_controls_20260627/summary.json`
- 2025：`+419.18%`，交易 `150` 次，最大回撤 `-31.28%`
- 2026：`+199.48%`，交易 `74` 次，最大回撤 `-26.09%`
- 每个评估月份都盈利，最低月交易次数 `12`
- 相对 0号：2025/2026收益更高，2025回撤更小，但 2026 回撤更大。
- 风险：固定信号仍来自前期研究；会选到 `12x` 杠杆；开平合计手续费压到 `0.4%` 会失败。

## 1号C策略候选

- 候选编号：`strategy_1c_trend_runner_20260627`
- 定位文件：`STRATEGY_1C_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1c_trend_runner_20260627.py`
- 结果：`artifacts/strategy_1c_trend_runner_20260627/summary.json`
- 2025：`+503.36%`，交易 `180` 次，最大回撤 `-31.28%`
- 2026：`+199.61%`，交易 `82` 次，最大回撤 `-26.09%`
- 每个评估月份都盈利，最低月交易次数 `12`
- 改进点：针对图上“月度锁利后错过大趋势”的问题，锁利后只在强趋势条件下用 `0.25x` 小仓位继续跟随。
- 风险：固定信号仍来自前期研究；趋势跟随规则是本轮看图后追加的研究规则；开平合计手续费压到 `0.4%` 会失败。

## 1号F策略候选

- 候选编号：`strategy_1f_selective_runner_20260627`
- 定位文件：`STRATEGY_1F_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1f_selective_runner_20260627.py`
- 结果：`artifacts/strategy_1f_selective_runner_20260627/summary.json`
- 图片：
  - `artifacts/strategy_1f_selective_runner_20260627/strategy1f_trades_2025.png`
  - `artifacts/strategy_1f_selective_runner_20260627/strategy1f_trades_2026.png`
- 2025：`+433.74%`，交易 `158` 次，最大回撤 `-29.40%`
- 2026：`+260.59%`，交易 `72` 次，最大回撤 `-29.25%`
- 每个评估月份都盈利，最低月交易次数 `11`
- 诊断：强趋势反向大仓仅 `1` 根 15分钟K线；弱趋势区大仓开单 `0` 次。
- 压力测试：开平合计 `0.3%`、`0.4%`、信号晚 1 根K线、`0.3% + 晚1根` 都通过。
- 当前判断：比 1B/1C 图形更干净，是更稳的 1号候选。

## 1号G策略候选

- 候选编号：`strategy_1g_cap7_selective_runner_20260627`
- 定位文件：`STRATEGY_1G_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1g_cap7_selective_runner_20260627.py`
- 结果：`artifacts/strategy_1g_cap7_selective_runner_20260627/summary.json`
- 图片：
  - `artifacts/strategy_1g_cap7_selective_runner_20260627/strategy1g_trades_2025.png`
  - `artifacts/strategy_1g_cap7_selective_runner_20260627/strategy1g_trades_2026.png`
- 2025：`+471.14%`，交易 `160` 次，最大回撤 `-27.87%`
- 2026：`+246.16%`，交易 `72` 次，最大回撤 `-28.67%`
- 每个评估月份都盈利，最低月交易次数 `11`
- 诊断：强趋势反向大仓仅 `1` 根 15分钟K线；弱趋势区大仓开单 `0` 次。
- 压力测试：开平合计 `0.3%` 和信号晚 1 根K线通过；开平合计 `0.4%`、`0.3% + 晚1根` 失败。
- 当前判断：固定 `0.2%` 手续费下，1G 数字更漂亮；如果更重视压力测试，1F 更稳。

## 1F/1G 额外核查

- 核查脚本：`scripts/audit_strategy_1fg_extra_20260627.py`
- 结果目录：`artifacts/strategy_1fg_extra_audit_20260627/`
- 这不是新策略，只是额外压力测试和时序检查；没有覆盖 0号、1F、1G 原目录。
- 测试网格：开平合计手续费 `0.2%`、`0.3%`、`0.4%`；信号额外晚 `0`、`1`、`2` 根 15分钟K线。
- 时序检查通过：`active_position` 等于上一根K线的目标仓位；仓位没有超过各自杠杆上限。
- 1F：`9` 个场景通过 `7` 个；失败在 `0.4%手续费 + 晚1/2根K线`，主要打穿 `2025-02`。
- 1G：`9` 个场景通过 `4` 个；`0.3%手续费 + 晚1/2根K线` 失败，`0.4%手续费` 全部失败，也主要打穿 `2025-02`。
- 当前判断进一步加强：1F 比 1G 更抗手续费和信号延迟；1G 只适合看固定 `0.2%` 手续费下的进攻数字。

## 2025-02 失败复盘

- 复盘脚本：`scripts/analyze_strategy_1fg_202502_failure_20260627.py`
- 结果目录：`artifacts/strategy_1fg_202502_failure_review_20260627/`
- 结论：失败不是少了某个神奇指标，而是高成本/延迟下没能快速锁利停手，暴露K线、订单和换手急剧增加。
- 正常 1F/1G 在 `2025-02` 只暴露约 `640` 根 15分钟K线；失败压力场景暴露约 `2630` 根，几乎整月都在场内。
- 换手从正常的 `20.3` 到 `32.1`，暴涨到失败场景的 `536` 到 `660`。
- 最大伤口来自 `adverse_shock_cut`：大仓被急跌/急涨打中后切仓，行情亏损和手续费一起放大。

## 2号实验和2B实验

- `strategy_2_damage_stop_20260627`：失败。它用月内亏损阈值触发停手，太早杀掉很多原本赚钱的月份；2025 只有 `+22.36%`，2026 `+50.81%`，不达标。
- `strategy_2b_shock_stop_20260627`：失败但有价值。它正常结果完全等于 1F，但 `0.4%手续费 + 晚1/2根K线` 仍失败，说明等到第2次急变才停手太晚。
- 这两个不要当候选，只保留为负面实验。

## 2号C策略候选

- 候选编号：`strategy_2c_lock_cap_20260627`
- 定位文件：`STRATEGY_2C_CANDIDATE.md`
- 脚本：`scripts/search_strategy_2c_lock_cap_20260627.py`
- 结果目录：`artifacts/strategy_2c_lock_cap_20260627/`
- 核心改动：基于 1F，只把每月滚动选出来的 `lock_log` 最高封顶到 `0.04`，让策略满 10 次交易后更早收手。
- 2025：`+359.10%`，交易 `156` 次，最大回撤 `-29.40%`
- 2026：`+260.59%`，交易 `72` 次，最大回撤 `-29.25%`
- 每个评估月份都盈利，最差月份 `+5.58%`，每月最低交易次数 `11`。
- 压力测试：开平合计 `0.2%/0.3%/0.4%`，并且信号晚 `0/1/2` 根K线，`9/9` 全部通过。
- 最强压力 `0.4%手续费 + 晚2根K线`：2025 `+217.67%`，2026 `+181.75%`，最差月份 `+1.81%`。
- 当前判断：2C 比 1F 少赚一些，但比 1F 更抗手续费和延迟；它是当前更稳的新候选。

## 3号/4号视觉复盘优化

- 画图脚本：`scripts/plot_strategy_trade_charts_20260627.py`
- 2C 买卖点图：
  - `artifacts/strategy_2c_visual_review_20260627/strategy2c_trades_2025.png`
  - `artifacts/strategy_2c_visual_review_20260627/strategy2c_trades_2026.png`
- 复盘结论：2C 压力测试强，但图上仍有“锁利后大趋势空仓”的问题。

3号候选：

- 候选编号：`strategy_3_trend_coverage_20260627`
- 脚本：`scripts/search_strategy_3_trend_coverage_20260627.py`
- 结果目录：`artifacts/strategy_3_trend_coverage_20260627/`
- 图：`artifacts/strategy_3_visual_review_20260627/strategy3_trades_2025.png`、`artifacts/strategy_3_visual_review_20260627/strategy3_trades_2026.png`
- 改动：保留 2C 锁利封顶，把锁利后小趋势仓触发从 `700 bps` 放宽到 `350 bps`，仍只用 `0.10x`。
- 2025：`+352.49%`；2026：`+259.39%`；最差月份 `+5.11%`；压力测试 `9/9` 通过。
- 强趋势空仓K线从 2C 的 `1208` 降到 `152`。
- 问题：主仓位仍有一些“刚反手就被打脸”的点，不利进场事件 `21/217`。

4号候选：

- 候选编号：`strategy_4_entry_confirm_20260627`
- 定位文件：`STRATEGY_4_CANDIDATE.md`
- 脚本：`scripts/search_strategy_4_entry_confirm_20260627.py`
- 结果目录：`artifacts/strategy_4_entry_confirm_20260627/`
- 图：`artifacts/strategy_4_visual_review_20260627/strategy4_trades_2025.png`、`artifacts/strategy_4_visual_review_20260627/strategy4_trades_2026.png`
- 改动：基于 3号，主方向刚切换时，要求新方向连续出现 `4` 根 15分钟K线；没站稳前先空仓等待。
- 2025：`+290.69%`；2026：`+263.17%`；最差月份 `+4.56%`；最低月交易次数 `10`；压力测试 `9/9` 通过。
- 最强压力 `0.4%手续费 + 晚2根K线`：2025 `+201.77%`，2026 `+183.84%`，最差月份 `+1.46%`。
- 不利进场事件从 3号的 `21/217` 降到 `16/203`；最大回撤约 `-28.79%`。
- 当前判断：2C 数字和压力余量更漂亮；4号图形更安静，更少假反手。4号是候选，不是固化版。

已否掉的方向：

- 仓位爬坡：压力测试从 `9/9` 掉到 `8/9`，不采用。
- 弱趋势一直小仓位：压力测试 `0/9`，不采用。
- RSI/Donchian 极端追高追低过滤：没有稳定改善，不采用。

## 5号鲁棒性审计

- 审计编号：`strategy_5_robustness_audit_20260627`
- 定位文件：`STRATEGY_5_ROBUSTNESS_AUDIT.md`
- 脚本：`scripts/audit_strategy_5_robustness_20260627.py`
- 结果目录：`artifacts/strategy_5_robustness_audit_20260627/`
- 这不是新策略，只比较 2C 和 4号。
- 手续费/延迟网格：开平合计 `0.2%/0.3%/0.4%/0.5%`，信号额外晚 `0/1/2/3` 根K线。
- 漏成交测试：基础手续费下，随机漏掉 `2%/5%/10%` 调仓指令，各跑 3 个固定种子。
- 手续费/延迟共 `16` 个场景：2C 通过 `13` 个，4号通过 `14` 个。
- 漏成交共 `9` 个场景：2C 通过 `7` 个，4号通过 `8` 个。
- 关键细节：2C 的漏成交失败是交易次数降到 `9` 次，不是亏钱；4号有 1 个漏成交场景出现亏损月。
- 当前判断：严格按硬条件通过数量看，4号略好；如果更在意漏成交后不要亏月，2C 更干净。

## 5B 三方鲁棒性审计

- 审计编号：`strategy_5b_three_way_audit_20260627`
- 定位文件：`STRATEGY_5B_THREE_WAY_AUDIT.md`
- 脚本：`scripts/audit_strategy_5b_three_way_20260627.py`
- 结果目录：`artifacts/strategy_5b_three_way_audit_20260627/`
- 这不是新策略，只把 3号拉进 2C/4号同一套审计。
- 手续费/延迟共 `16` 个场景：2C 通过 `13` 个，3号通过 `13` 个，4号通过 `14` 个。
- 漏成交共 `9` 个场景：2C 通过 `7` 个，3号通过 `7` 个，4号通过 `8` 个。
- 漏成交后不亏月：2C 和 3号都是 `9/9`，4号是 `8/9`。
- 3号没有明显超过 2C：它改善强趋势空仓，但在这套审计里没有换来更强鲁棒性。
- 当前判断：主候选仍倾向 2C；4号做图形质量/硬压力对照；3号暂时只保留为中间实验。

## 6号市场状态体检

- 审计编号：`strategy_6_market_regime_audit_20260627`
- 定位文件：`STRATEGY_6_MARKET_REGIME_AUDIT.md`
- 脚本：`scripts/audit_strategy_6_market_regime_20260627.py`
- 结果目录：`artifacts/strategy_6_market_regime_audit_20260627/`
- 这不是新策略，也不是实时状态识别器，只是历史体检表。
- 复用 5B 的月度事后标签：月涨幅 `>= +5%` 是上涨月，月跌幅 `<= -5%` 是下跌月，中间是震荡月；月内最大回撤或最大上涨 `>= 15%` 标成冲击月。
- 数据共同截止到 `2026-06-19 23:45 UTC`，`2026-06` 是未完整月份。
- 完整月统计：下跌月 `5` 个，震荡月 `6` 个，上涨月 `6` 个。
- 基础月度表现：2C、3号、4号在各状态下都满足收益为正且交易次数不少于 `10`。
- 压力失败没有达到“确认弱点”的严格标准；只保守观察到下跌月的手续费/延迟风险、震荡月的漏成交风险。
- GPT Pro 复核意见：6号可保留为历史体检表，但绝不能升级成策略依据；最大坑是把事后解释当成事前预测。
- 当前判断：不升级策略，不做路由，2C/4号/3号排序不变。

## 7号 Oracle 路由上限审计

- 审计编号：`strategy_7_oracle_router_audit_20260627`
- 定位文件：`STRATEGY_7_ORACLE_ROUTER_AUDIT.md`
- 脚本：`scripts/audit_strategy_7_oracle_router_20260627.py`
- 结果目录：`artifacts/strategy_7_oracle_router_audit_20260627/`
- 这不是新策略，只测试“如果事后完美知道市场状态，状态路由最多能不能明显超过 2C”。
- 只看完整月份，排除未完整的 `2026-06`。
- 静态 2C 完整月总收益 `+1033.11%`；3号 `+1013.10%`；4号 `+829.14%`。
- 每月事后最佳 `+1128.92%`，但这是看答案，不能交易。
- 按市场状态全样本最佳 `+1045.54%`，只比 2C 多 `+12.42` 个百分点。
- 只用过去同状态选择 `+986.32%`，反而比 2C 少 `46.79` 个百分点。
- 当前判断：不升级路由；复杂实时状态切换暂时不值得做。下一步更值得做执行压力升级，而不是继续调状态路由。

## 8号执行压力审计

- 审计编号：`strategy_8_execution_stress_20260627`
- 定位文件：`STRATEGY_8_EXECUTION_STRESS_AUDIT.md`
- 脚本：`scripts/audit_strategy_8_execution_stress_20260627.py`
- 结果目录：`artifacts/strategy_8_execution_stress_20260627/`
- 这不是新策略，只检查 2C、3号、4号在更坏执行条件下是否容易坏。
- 压力项：波动放大滑点、每8小时资金费 `1bp/3bp`、专门漏掉换手最大的 `5%` 调仓、最大波动附近交易所短时停摆。
- 2C：`6/6` 通过，最差年度 `+218.06%`，最差月 `+2.76%`。
- 3号：`6/6` 通过，最差年度 `+216.95%`，最差月 `+2.44%`。
- 4号：`5/6` 通过，失败在 `miss_top5pct_rebalance` 的 `2025-03`，月收益 `-0.56%`。
- 当前判断：2C 执行压力下暂时最稳；4号图形更安静，但关键调仓漏掉时更脆。

## 9号冷启动可行性审计

- 审计编号：`strategy_9_cold_start_feasibility_20260627`
- 定位文件：`STRATEGY_9_COLD_START_FEASIBILITY.md`
- 脚本：`scripts/audit_strategy_9_cold_start_feasibility_20260627.py`
- 结果目录：`artifacts/strategy_9_cold_start_feasibility_20260627/`
- 这不是新策略，只判断能不能干净地把 2C、3号、4号直接拿去测 2024。
- 本地特征数据覆盖 `2024-01` 到 `2026-06`。
- 2C、3号、4号使用的已保存月度控制参数覆盖 `2025-01` 到 `2026-06`。
- 结论：不能干净直接测 2024。因为 2024 已经是这些保存候选的训练历史；拿 2025 以后保存下来的参数倒回去测 2024，是未来参数测过去。
- 干净做法：补 2023 或更早数据，为 2024 做真正 walk-forward；或者不改规则，等待未来新月份做影子记录。

## 10号 pre-2024 数据探针

- 探针编号：`strategy_10_pre2024_data_probe_20260627`
- 定位文件：`STRATEGY_10_PRE2024_DATA_PROBE.md`
- 脚本：`scripts/audit_strategy_10_pre2024_data_probe_20260627.py`
- 结果目录：`artifacts/strategy_10_pre2024_data_probe_20260627/`
- 这不是新策略，不回测收益，只补 2023 年 BTCUSDT 15m 公开K线和探针版特征。
- 数据来源：Binance public monthly kline archive，不使用 API key。
- 官方原始 2023 K线有 `35035` 根，`2023-03-24` 有 5 根15分钟K线缺口；REST 接口也同样缺这 5 根。
- 补齐日历版用上一根收盘价补平这 5 根，并用 `calendar_filled=True` 标记；补齐后 `35040` 根，重复 `0`，非15分钟缺口 `0`，必要特征列缺失 `0`。
- 当前判断：10号可作为 11号真正 2024 walk-forward 的数据底座；下一步不要倒用 2025+ 保存参数测 2024。

## 11号真正 2024 Walk-Forward 审计

- 审计编号：`strategy_11_true_2024_walkforward_20260627`
- 定位文件：`STRATEGY_11_TRUE_2024_WALKFORWARD.md`
- 脚本：`scripts/audit_strategy_11_true_2024_walkforward_20260627.py`
- 结果目录：`artifacts/strategy_11_true_2024_walkforward_20260627/`
- 这不是新策略，只检查：用 2023 和每个评估月以前的数据提前选参数，再测 2024。
- 测了两个版本：固定 `ret_state 64/100`；小范围 `ret_state` 滚动选择器。
- 两个版本最终都选回 `ret_state window=64 threshold=100 bps`。
- 2024 收益 `+138.08%`，最少月交易 `12`，但 `2024-12` 亏 `-6.45%`，所以硬条件不通过。
- 当前判断：11号不能升级候选；它说明当前策略族仍有样本外坏月，下一步应优先研究 `2024-12`，不要只在 2025/2026 上继续加规则。

## 12号 2024-12 失败复盘

- 复盘编号：`strategy_12_202412_failure_review_20260627`
- 定位文件：`STRATEGY_12_202412_FAILURE_REVIEW.md`
- 脚本：`scripts/audit_strategy_12_202412_failure_review_20260627.py`
- 结果目录：`artifacts/strategy_12_202412_failure_review_20260627/`
- 这不是新策略，只复盘 11号真正样本外测试里的 `2024-12` 亏损月。
- `2024-12` 全月净收益 `-6.45%`；不算手续费/换手前 `+4.22%`；换手成本约 `10.80%` log；订单 `18`，换手 `108.0`。
- 真正的问题在月初：达到月交易配额前后那段净收益 `-23.21%`，不算成本也亏 `-17.97%`，成本约 `6.60%` log；后半月追回 `+21.83%`，但没完全补回。
- 参数复查：小网格候选 `30` 个，训练期达标 `8` 个，其中 `2` 个在 `2024-12` 为正；事后最佳 `+5.74%`，但这是看答案，不能交易。
- 当前判断：12号不升级策略，也不立刻加规则。下一步如果继续，应另起 13号，用 `2023` 训练期设计低换手/低反手预防规则，再测完整 `2024`。

## 13号低换手/低反手预防规则

- 实验编号：`strategy_13_low_turnover_prevention_20260627`
- 定位文件：`STRATEGY_13_LOW_TURNOVER_PREVENTION.md`
- 脚本：`scripts/search_strategy_13_low_turnover_prevention_20260627.py`
- 结果目录：`artifacts/strategy_13_low_turnover_prevention_20260627/`
- 这不是候选策略，是负面实验。
- 规则：基础信号仍是 `ret_state 64/100`；新方向连续出现 `confirm_bars` 根 15分钟K线后才允许切换方向；测试 `1/2/4/8/12`。
- 严格选择口径：只用 `2023` 训练期选择 `confirm_bars` 和控制参数，然后完整测试 `2024`，2024 从空仓开始，不带 2023 仓位。
- 2023 选中的仍是 `confirm_bars=1`，也就是不确认、直接反手。
- 完整 2024：收益 `+114.96%`，亏损月 `1`，最差月 `-6.45%`，最少月交易 `12`，硬条件不通过。
- 事后看 2024，有 `24` 个候选能通过，事后最佳 `confirm_bars=4`、收益 `+183.61%`，但这是看答案，不能交易。
- 当前判断：13号不能升级。它只说明“确认后反手”有潜力，但不能直接拿 `confirm_bars=4` 固化。

## 14号 pre-2023 扩展滚动与拥挤压力审计

- 审计编号：`strategy_14_pre2023_expanding_crowding_stress_audit_20260627`
- 定位文件：`STRATEGY_14_PRE2023_EXPANDING_CROWDING_STRESS_AUDIT.md`
- 脚本：`scripts/audit_strategy_14_pre2023_expanding_crowding_stress_20260627.py`
- 结果目录：`artifacts/strategy_14_pre2023_expanding_crowding_stress_audit_20260627/`
- 这不是新策略，不是候选，也不是固化版。
- 先问过 GPT Pro。GPT Pro 建议不要继续堆参数修 2024-12，而要做更早历史、更严格 walk-forward 和拥挤执行压力审计。
- 重要数据修正：旧 `event_entry_fullscan` 对齐的是 Binance USD-M futures 公共K线，不是 spot K线。14号改用 USD-M futures 公共K线补 `2020-2024`，并接本地 `2025` 到完整 `2026-05` 数据。
- 2024 对齐检查：公共 futures `35136` 行，本地 event `35136` 行，匹配 `35136` 行，close 差异 `0`。
- 这说明 10/11/13 用 2023 spot 探针接旧 event 数据的结果，只能当探索或诊断，不能当最终严审依据。
- 14号候选族固定为 `ret_state 64/100`；`confirm_bars` 只允许 `1/2/4/8/12`；控制参数用 11号小网格，共 `150` 个候选。
- 评估范围：`2023-01` 到 `2026-05`，每个月只用评估月之前的数据选参数。
- 基础滚动结果：2023 `-21.96%`，2024 `+140.23%`，2025 `-5.28%`，2026 YTD `-0.35%`。
- 评估期亏损月 `6`，最差月 `-39.60%`，最大回撤 `-58.39%`。
- 所有 `41` 个评估月都选中 `confirm_bars=8`，但仍然不稳。
- 压力测试 `11` 个场景全部失败，包括 0.2/0.3/0.4/0.6% 开平合计手续费、1/2/4 根K线延迟、资金费和波动滑点。
- 当前判断：`STOP_FAMILY`。不要继续给这个 `ret_state 64/100` 家族手工堆补丁，也不要为了已知坏月继续加规则。

## 15号统一数据底座体检

- 体检编号：`strategy_15_unified_data_baseline_20260627`
- 定位文件：`STRATEGY_15_UNIFIED_DATA_BASELINE.md`
- 脚本：`scripts/audit_strategy_15_unified_data_baseline_20260627.py`
- 结果目录：`artifacts/strategy_15_unified_data_baseline_20260627/`
- 这不是新策略，也不是收益回测，只确认以后换新策略族时先用哪份K线。
- 输入数据沿用 14号合并K线：`artifacts/strategy_14_pre2023_expanding_crowding_stress_audit_20260627/btc_15m_2020_2026_05_combined_ohlc.csv`
- 时间范围：`2020-01-01 00:00 UTC` 到 `2026-05-31 23:45 UTC`，共 `224928` 根 15分钟K线、`77` 个月。
- 来源拆分：`2020-2024` 为 Binance public USD-M futures archive，`2025-2026-05` 为本地 `event_entry_fullscan`。
- 质量检查：重复时间戳 `0`，非15分钟断档 `0`，OHLC异常 `0`，补齐K线 `0`，不完整月份 `0`，缺失月份 `0`。
- 继承 14号 2024 对齐结论：public futures 与本地 event 都是 `35136` 行，close 差异 `0`。
- 当前判断：`DATA_BASELINE_READY`。后续新策略族应先用这份 futures 统一K线底座，不要再混用 spot 探针和旧 event 口径。

## 16号新策略族可行性探针

- 探针编号：`strategy_16_new_family_probe_20260627`
- 定位文件：`STRATEGY_16_NEW_FAMILY_PROBE.md`
- 脚本：`scripts/audit_strategy_16_new_family_probe_20260627.py`
- 结果目录：`artifacts/strategy_16_new_family_probe_20260627/`
- 这不是候选策略，也不是固化版，只是在 15号 futures 底座上检查简单新策略族有没有继续研究价值。
- 评估范围：`2023-01` 到 `2026-05`；完整年度硬门槛看 `2023/2024/2025`，`2026` 只记录 YTD。
- 手续费：开平合计 `0.2%`，代码里单边 `0.001`。
- 候选：共 `144` 个，包含均线趋势、Donchian 突破、RSI 回归、布林带回归、ATR 突破；杠杆只测 `1x/2x/4x`。
- 严格逐月选择：每个月只用评估月以前的数据选参数；信号只用已收盘K线，下一根K线吃收益。
- 最好严格选择器：`all_families`，2023 `+23.04%`，2024 `+33.45%`，2025 `-54.66%`，2026 YTD `+1.90%`；亏损月 `22`，最差月 `-25.35%`，最少月交易 `3`，最大回撤 `-72.40%`。
- 单类结果也失败：trend 同上；volatility_breakout 为 2023 `-15.38%`、2024 `-35.94%`、2025 `-6.78%`；mean_reversion 为 2023 `-36.13%`、2024 `-22.65%`、2025 `-32.68%`。
- 144个静态候选事后硬通过数量也是 `0`；事后最好是 `trend_donchian_trend_lev1p0_lookback192`，但 2025 仍 `-54.66%`，亏损月 `22`。
- 当前判断：`NO_HARD_PASS_IN_SIMPLE_NEW_FAMILY_PROBE`。不要升级16号；下一步更适合做17号上限测试，先看这批简单候选的理论月度上限够不够。

## 17号简单策略族上限测试

- 测试编号：`strategy_17_simple_family_upper_bound_20260627`
- 定位文件：`STRATEGY_17_SIMPLE_FAMILY_UPPER_BOUND.md`
- 脚本：`scripts/audit_strategy_17_simple_family_upper_bound_20260627.py`
- 结果目录：`artifacts/strategy_17_simple_family_upper_bound_20260627/`
- 这不是策略，不能交易，也不是固化版；它是“看答案”的月度上限测试。
- 来源：16号的 `144` 个简单候选；评估范围仍是 `2023-01` 到 `2026-05`；手续费开平合计 `0.2%`。
- 最宽松上限 `monthly_oracle_best_return`：每个月直接挑收益最高候选，不要求交易次数够 `10`。2023 `+10048.37%`，2024 `+5634.19%`，2025 `+1912.71%`，2026 YTD `+564.01%`，但仍有 `6` 个不盈利月份：`2023-07`、`2024-12`、`2025-06`、`2025-09`、`2026-04`、`2026-05`；最少月交易 `0`。
- 带交易次数门槛上限 `monthly_oracle_best_return_order10`：每个月只在交易次数不少于 `10` 的候选里事后挑最好。2023 `+3299.38%`，2024 `+1721.70%`，2025 `+385.93%`，2026 YTD `+274.52%`，但仍有 `10` 个不盈利月份：`2023-07`、`2023-09`、`2024-04`、`2024-06`、`2024-12`、`2025-06`、`2025-07`、`2025-09`、`2026-04`、`2026-05`。
- 当前判断：`SIMPLE_FAMILY_UPPER_BOUND_FAILS`。不是严格选择器太笨，而是这批简单规则本身不够；不要继续扩这批均线/Donchian/RSI/布林带/ATR突破简单变体。

## 18号上限失败月份复盘

- 复盘编号：`strategy_18_upper_bound_failure_review_20260627`
- 定位文件：`STRATEGY_18_UPPER_BOUND_FAILURE_REVIEW.md`
- 脚本：`scripts/audit_strategy_18_upper_bound_failure_review_20260627.py`
- 结果目录：`artifacts/strategy_18_upper_bound_failure_review_20260627/`
- 这不是策略，也不是候选，只复盘 17号为什么连看答案上限都没过。
- 复盘月份：`2023-07`、`2023-09`、`2024-04`、`2024-06`、`2024-12`、`2025-06`、`2025-07`、`2025-09`、`2026-04`、`2026-05`。
- 失败类型：`no_positive_candidate` 有 `6` 个月，意思是 144个简单候选里没有任何一个当月正收益；`positive_only_with_too_few_orders` 有 `4` 个月，意思是有正收益候选但交易次数不到 `10`。
- `no_positive_candidate` 月份：`2023-07`、`2024-12`、`2025-06`、`2025-09`、`2026-04`、`2026-05`。
- `positive_only_with_too_few_orders` 月份：`2023-09`、`2024-04`、`2024-06`、`2025-07`。
- 当前判断：`FAILURE_MONTHS_EXPLAIN_SIMPLE_FAMILY_STOP`。这批简单规则在很多失败月份里，最好的选择其实是空仓；一旦要求每月10次交易，就变成亏钱。不要继续微调这批规则。

## 19号日历季节性探针

- 探针编号：`strategy_19_calendar_seasonality_probe_20260627`
- 定位文件：`STRATEGY_19_CALENDAR_SEASONALITY_PROBE.md`
- 脚本：`scripts/audit_strategy_19_calendar_seasonality_probe_20260627.py`
- 结果目录：`artifacts/strategy_19_calendar_seasonality_probe_20260627/`
- 这不是候选策略，也不是固化版，只检查星期几、小时、交易时段这类日历规律有没有用。
- 数据底座：15号确认过的 USD-M futures 合并K线；模型起点 `2021-01`；评估范围 `2023-01` 到 `2026-05`。
- 候选：`216` 个，分桶包括 `session`、`weekday`、`hour`、`hour_week`；回看训练期 `12/24/扩展`；阈值 `0/0.5/1.0 bps`；最小样本数 `20/50`；杠杆 `1x/2x/4x`。
- 最好严格选择器：`all_calendar`，2023 `-1.32%`，2024 `+71.64%`，2025 `-26.91%`，2026 YTD `+43.60%`；亏损月 `22`，最差月 `-25.36%`，最少月交易 `0`，最大回撤 `-46.37%`。
- 单个动态候选事后最好：`calendar_weekday_lbexpanding_thr0p0_min20_lev1p0`，2023 `+31.81%`，2024 `+71.57%`，2025 `-10.55%`，2026 YTD `+43.60%`，亏损月 `17`，最少月交易 `10`。
- 当前判断：`CALENDAR_SEASONALITY_FAILS`。单靠星期几、小时、交易时段这种规律不够，不要升级19号。

## 20号 OHLC结构上限测试

- 测试编号：`strategy_20_ohlc_structure_upper_bound_20260627`
- 定位文件：`STRATEGY_20_OHLC_STRUCTURE_UPPER_BOUND.md`
- 脚本：`scripts/audit_strategy_20_ohlc_structure_upper_bound_20260627.py`
- 结果目录：`artifacts/strategy_20_ohlc_structure_upper_bound_20260627/`
- 这不是策略，不能交易，只是“看答案”的月度上限测试。
- 数据底座：15号确认过的 USD-M futures 合并K线；这份底座没有成交量，所以 20号只测 OHLC，不测 volume。
- 候选：`189` 个，包含 K线实体动量/反转、上下影线反转、大振幅K线动量/反转、高波动实体动量/反转、低波动影线反转。
- 静态候选硬通过数量：`0`。
- 最宽松上限 `monthly_oracle_best_return`：2023 `+51.61%`、2024 `+18.35%`、2025 `+12.99%`、2026 YTD `+0.18%`，仍有 `30` 个不盈利月份，最少月交易 `0`。
- 带交易次数门槛上限 `monthly_oracle_best_return_order10`：2023 `+22.80%`、2024 `-2.56%`、2025 `-6.90%`、2026 YTD `-2.98%`，不盈利月份 `33`，最少月交易 `10`。
- 当前判断：`OHLC_STRUCTURE_UPPER_BOUND_FAILS`。只看K线实体、影线、振幅和波动结构，连看答案上限都不够，不要升级20号，也不要继续扩这批 OHLC 结构小规则。

## 21号成交量上限测试

- 测试编号：`strategy_21_volume_upper_bound_20260627`
- 定位文件：`STRATEGY_21_VOLUME_UPPER_BOUND.md`
- 脚本：`scripts/audit_strategy_21_volume_upper_bound_20260627.py`
- 结果目录：`artifacts/strategy_21_volume_upper_bound_20260627/`
- 这不是策略，不能交易，只是“看答案”的月度上限测试。
- 数据源：Binance public USD-M futures monthly klines，`2020-01` 到 `2026-05`，带 `volume`、`quote_volume`、`taker_base`、`taker_quote`。
- 数据质量：`224928` 行，重复时间戳 `0`，非15分钟断档 `0`，补齐K线 `0`，volume异常 `0`；与15号 OHLC 底座 close 对齐 `224928/224928`，close 差异 `0`。
- 候选：`378` 个，包含 volume 放大后的实体动量/反转、taker买卖比例动量/反转、价格涨跌叠加放量确认后的动量/反转。
- 静态候选硬通过数量：`0`。
- 最宽松上限 `monthly_oracle_best_return`：2023 `+45.98%`、2024 `+54.74%`、2025 `-12.01%`、2026 YTD `-9.17%`，仍有 `25` 个不盈利月份，最少月交易 `2`。
- 带交易次数门槛上限 `monthly_oracle_best_return_order10`：2023 `+39.04%`、2024 `+50.98%`、2025 `-12.73%`、2026 YTD `-9.17%`，不盈利月份 `29`，最少月交易 `10`。
- 当前判断：`VOLUME_UPPER_BOUND_FAILS`。只看成交量放大、taker买卖比例、放量动量/反转，连看答案上限都不够，不要升级21号，也不要继续扩这批成交量小规则。

## 22号硬目标瓶颈审计

- 审计编号：`strategy_22_hard_target_bottleneck_20260627`
- 定位文件：`STRATEGY_22_HARD_TARGET_BOTTLENECK_AUDIT.md`
- 脚本：`scripts/audit_strategy_22_hard_target_bottleneck_20260627.py`
- 结果目录：`artifacts/strategy_22_hard_target_bottleneck_20260627/`
- 这不是策略，不能交易，只是把 16/19/20/21 的候选放进同一张硬目标压力表。
- 候选：`927` 个，只复用 16号简单价格、19号日历、20号 OHLC结构、21号成交量/taker，没有新增规则。
- 压力网格：月交易次数 `0/2/5/10`，开平合计手续费 `0.0%/0.1%/0.2%/0.3%/0.4%`，月收益要求不限/`>=-1%`/`>0`，年收益门槛 `50%/100%`。
- 严格逐月选择器：`0/120` 通过。
- 月度oracle：`80/120` 通过，但它是看答案，不能交易。
- 原始硬目标口径下，月度oracle仍失败，差 `2023-07` 和 `2024-06` 两个月；严格选择器也失败，2025 `-95.78%`，2026 YTD `+7.81%`。
- 当前判断：`ORIGINAL_TARGET_AND_SELECTION_BOTTLENECK`。原始硬目标太紧，而且严格选择器选不出看答案月份。不要继续扩 16/19/20/21 小规则。
- 停止结论文件：`RESEARCH_DECISION_STOP_SIMPLE_RULES_AFTER_22.md`

## 重要风险

- 当前执行逻辑没有发现明显未来函数：信号只用已收盘K线，下一根K线才吃收益。
- 参数是事后从历史中挑出来的，过拟合风险高。
- 已做过更严格检查：用 2024 年选参数，再测 2025/2026，没有达到每年 100%。
- 本轮新增 `artifacts/profit_lock_walkforward_20260627/summary.json`：固定老信号 `ret_state window=64 threshold=100`，但每个月只用前面月份选择锁利/补交易/杠杆参数。这个检查在本地特征数据上通过：2025 `+171.35%`，2026 `+126.55%`，无亏损评估月份，最低月交易次数 `12`。注意：固定信号本身仍来自历史研究，所以还不能说完全不过拟合。
- 2026 主结果用本地数据到 `2026-06-19 23:45 UTC`。
- 另有 Binance 补测到 `2026-06-26 18:30 UTC`，补测后 6 月已锁利空仓。
- 本项目只做研究和回测，不下实盘，不读取密钥，不启动 supervisor。

## 下一轮建议

0号策略不要覆盖。下一轮如果继续做，只能另起新编号、新目录，例如：

- 当前最新研究链：14号判定 `ret_state 64/100` 家族 `STOP_FAMILY`；15号确认 futures 统一K线底座可用；16号简单价格规则失败；17号看答案上限失败；18号解释失败月份；19号日历季节性失败；20号 OHLC 结构上限失败；21号成交量/taker 上限失败；22号确认原始硬目标和严格选择器双重卡住。
- 下一轮不要继续修 `ret_state 64/100`，不要继续扩均线/Donchian/RSI/布林带/ATR突破，不要升级日历季节性，不要继续扩 OHLC 结构小规则，也不要继续扩成交量/taker小规则。
- 如果继续研究，应另起 23号，只做真正不同的数据源上限测试，或先把目标改得更现实。不要直接写可交易策略，也不要直接上机器学习。
- 当前历史硬目标很可能过严：22号显示原始硬目标下连看答案 oracle 都差 `2` 个月；放宽后看答案能过，但严格逐月选择器 `0/120` 通过。
- 每次新结果都写清楚手续费、未来函数检查、月度收益、交易次数、最大回撤。

## 发到下一个窗口的内容

```text
请接着这个项目继续工作：

本地路径：C:\Users\WHR\Documents\策略迭代
GitHub：https://github.com/yw9522872-debug/btc-strategy-iteration-20260627

请先阅读：
1. AGENTS.md
2. NEXT_CHAT_HANDOFF.md
3. STRATEGY_0.md
4. STRATEGY_1_CANDIDATE.md
5. STRATEGY_1B_CANDIDATE.md
6. STRATEGY_1C_CANDIDATE.md
7. STRATEGY_1F_CANDIDATE.md
8. STRATEGY_1G_CANDIDATE.md
9. STRATEGY_2C_CANDIDATE.md
10. STRATEGY_4_CANDIDATE.md
11. STRATEGY_5_ROBUSTNESS_AUDIT.md
12. STRATEGY_5B_THREE_WAY_AUDIT.md
13. STRATEGY_6_MARKET_REGIME_AUDIT.md
14. STRATEGY_7_ORACLE_ROUTER_AUDIT.md
15. STRATEGY_8_EXECUTION_STRESS_AUDIT.md
16. STRATEGY_9_COLD_START_FEASIBILITY.md
17. STRATEGY_10_PRE2024_DATA_PROBE.md
18. STRATEGY_11_TRUE_2024_WALKFORWARD.md
19. STRATEGY_12_202412_FAILURE_REVIEW.md
20. STRATEGY_13_LOW_TURNOVER_PREVENTION.md
21. STRATEGY_14_PRE2023_EXPANDING_CROWDING_STRESS_AUDIT.md
22. STRATEGY_15_UNIFIED_DATA_BASELINE.md
23. STRATEGY_16_NEW_FAMILY_PROBE.md
24. STRATEGY_17_SIMPLE_FAMILY_UPPER_BOUND.md
25. STRATEGY_18_UPPER_BOUND_FAILURE_REVIEW.md
26. STRATEGY_19_CALENDAR_SEASONALITY_PROBE.md
27. STRATEGY_20_OHLC_STRUCTURE_UPPER_BOUND.md
28. STRATEGY_21_VOLUME_UPPER_BOUND.md
29. STRATEGY_22_HARD_TARGET_BOTTLENECK_AUDIT.md
30. RESEARCH_DECISION_STOP_SIMPLE_RULES_AFTER_22.md
31. CURRENT_STRATEGY_FREEZE.md
32. GPT_PRO_REVIEW_BRIEF.md
33. artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json
34. artifacts/strategy_15_unified_data_baseline_20260627/summary.json
35. artifacts/strategy_16_new_family_probe_20260627/summary.json
36. artifacts/strategy_17_simple_family_upper_bound_20260627/summary.json
37. artifacts/strategy_18_upper_bound_failure_review_20260627/summary.json
38. artifacts/strategy_19_calendar_seasonality_probe_20260627/summary.json
39. artifacts/strategy_20_ohlc_structure_upper_bound_20260627/summary.json
40. artifacts/strategy_21_volume_upper_bound_20260627/summary.json
41. artifacts/strategy_22_hard_target_bottleneck_20260627/summary.json

重要：不要和其他 Codex 线程、其他浏览器 GPT Pro 页面、其他仓库混淆。

当前已有固化研究版：
monthly_profit_lock_research_freeze_20260627

这一版已经定位为 0号策略，必须永久保留。后续优化必须另起新编号、新文件夹，不能覆盖 0号策略。

它的历史结果：
2025 收益 +326.26%，胜率 50.00%，交易次数 148，最大回撤 -48.53%。
2026 收益 +106.93%，胜率 50.66%，交易次数 72，最大回撤 -18.21%。

手续费按开平合计 0.2%。
当前执行逻辑没发现明显未来函数。
但参数是历史事后挑出来的，过拟合风险高。
2024 选参再测 2025/2026 没达到每年 100%。

当前保存的 1号候选：
1F：标签 strategy-1f-selective-runner-20260627，2025 +433.74%，2026 +260.59%，更稳，0.4% 开平合计手续费压力测试通过。
1G：标签 strategy-1g-cap7-selective-runner-20260627，2025 +471.14%，2026 +246.16%，当前 0.2% 手续费下数字更漂亮，但 0.4% 手续费压力测试失败。

当前新增 2号C候选：
2C：strategy_2c_lock_cap_20260627，基于 1F，只把每月 lock_log 封顶为 0.04。2025 +359.10%，2026 +260.59%，开平合计 0.2%/0.3%/0.4% 乘以信号晚 0/1/2 根K线的 9 个压力场景全部通过。当前判断：比 1F 少赚一点，但更抗手续费和延迟。

当前新增 4号候选：
4号：strategy_4_entry_confirm_20260627，基于 3号视觉复盘优化。它保留 2C 锁利封顶，降低锁利后强趋势空仓，并要求主方向刚切换时连续确认 4 根 15分钟K线。2025 +290.69%，2026 +263.17%，9 个压力场景全部通过。当前判断：2C 数字和压力余量更漂亮；4号图形更安静，更少假反手。

当前新增 5号审计：
5号：strategy_5_robustness_audit_20260627，不是新策略，只比较 2C 和 4号。手续费/延迟 16 个场景里，2C 通过 13 个，4号通过 14 个；漏成交 9 个场景里，2C 通过 7 个，4号通过 8 个。但 2C 漏成交失败是交易次数不足，不是亏钱；4号有 1 个漏成交场景亏损。当前判断：4号硬条件略胜，2C 漏成交盈利稳定性更干净。

当前新增 5B审计：
5B：strategy_5b_three_way_audit_20260627，不是新策略，只把 3号也拉进来和 2C/4号同台比较。手续费/延迟 16 个场景里，2C 13/16，3号 13/16，4号 14/16；漏成交 9 个场景里，2C 7/9，3号 7/9，4号 8/9。2C 和 3号漏成交后都没有亏损月，4号有 1 个亏损月。当前判断：主候选仍倾向 2C；4号做对照；3号暂不升主候选。

当前新增 6号市场状态体检：
6号：strategy_6_market_regime_audit_20260627，不是新策略，也不是实时状态识别器。它复用 5B 的月度事后市场标签，只检查历史弱点是否集中。数据到 2026-06-19 23:45 UTC，2026-06 是未完整月份；完整月只有 17 个。压力失败没有达到确认弱点标准，只保守观察到下跌月手续费/延迟风险、震荡月漏成交风险。GPT Pro 复核后也建议：6号只能当体检表，不能当策略依据，不能做路由。

当前新增 7号 Oracle 路由上限审计：
7号：strategy_7_oracle_router_audit_20260627，不是新策略，只测试“完美知道状态时，路由最多能不能明显超过 2C”。完整月里，2C 总收益 +1033.11%；每月事后最佳 +1128.92%，但这是看答案；按状态全样本最佳 +1045.54%，只比 2C 多 12.42 个百分点；只用过去同状态选择 +986.32%，反而跑输 2C。当前判断：不升级路由，复杂实时状态切换暂时不值得做。

当前新增 8号执行压力审计：
8号：strategy_8_execution_stress_20260627，不是新策略，只检查更坏执行条件。压力包括波动放大滑点、资金费、关键调仓漏单、最大波动附近短时停摆。2C 6/6 通过，最差月 +2.76%；3号 6/6 通过，最差月 +2.44%；4号 5/6 通过，在 2025-03 关键调仓漏单场景亏 -0.56%。当前判断：执行压力下 2C 暂时最稳。

当前新增 9号冷启动可行性审计：
9号：strategy_9_cold_start_feasibility_20260627，不是新策略，只判断能否干净直接测 2024。结论：不能。因为当前保存候选的月度控制参数从 2025-01 开始，2024 已经是训练历史；拿这些参数倒回去测 2024 是未来参数测过去。干净做法是补 2023 或更早数据，或等待未来新月份做影子记录。

当前新增 10号 pre-2024 数据探针：
10号：strategy_10_pre2024_data_probe_20260627，不是新策略，只补 2023 BTCUSDT 15m 公开K线和探针版特征。Binance 官方原始数据有 35035 根，2023-03-24 有 5 根15分钟K线缺口；REST 接口也同样缺。补齐日历版用上一根收盘价补平，并用 calendar_filled=True 标记；补齐后 35040 根，重复 0，非15分钟缺口 0，必要特征列缺失 0。下一步应另起 11号做真正 2024 walk-forward。

当前新增 11号真正 2024 walk-forward 审计：
11号：strategy_11_true_2024_walkforward_20260627，不是新策略，只检查用 2023 和每个评估月以前的数据提前选参数，再测 2024。固定 ret_state 64/100 与小范围 ret_state 滚动选择器最终都选回 ret_state 64/100；2024 收益 +138.08%，最少月交易 12，但 2024-12 亏 -6.45%，所以不满足每月盈利硬条件。当前判断：不能升级候选；下一步更应该复盘 2024-12 样本外坏月。

当前新增 12号 2024-12 失败复盘：
12号：strategy_12_202412_failure_review_20260627，不是新策略，只复盘 11号真正样本外坏月。2024-12 全月净收益 -6.45%；不算手续费/换手前 +4.22%；换手成本约 10.80% log；订单 18，换手 108.0。真正问题在月初：达到月交易配额前后那段净收益 -23.21%，不算成本也亏 -17.97%，成本约 6.60% log；后半月追回 +21.83%，但没完全补回。小网格里训练期达标候选 8 个，其中 2 个 2024-12 为正，事后最佳 +5.74%，但这是看答案。当前判断：不升级策略，不立刻加规则；下一步若继续，应做 13号低换手/低反手预防规则，并测完整 2024。

当前新增 13号低换手/低反手预防规则：
13号：strategy_13_low_turnover_prevention_20260627，不是候选策略，是负面实验。规则是基础信号 ret_state 64/100 新方向连续出现 confirm_bars 根 15分钟K线后才切换，测试 1/2/4/8/12。严格口径只用 2023 训练期选择 confirm_bars 和控制参数，完整测试 2024，并且 2024 从空仓开始。2023 选中的仍是 confirm_bars=1；完整 2024 收益 +114.96%，亏损月 1，最差月 -6.45%，最少月交易 12，硬条件不通过。事后看 2024 有 24 个候选能通过，事后最佳 confirm_bars=4、收益 +183.61%，但这是看答案，不能交易。当前判断：13号不能升级。

当前新增 14号 pre-2023 扩展滚动与拥挤压力审计：
14号：strategy_14_pre2023_expanding_crowding_stress_audit_20260627，不是新策略，不是候选，也不是固化版。它按 GPT Pro 建议做更早历史、更严格 walk-forward 和执行拥挤压力审计。重要发现：旧 event_entry_fullscan 对齐 Binance USD-M futures，不是 spot；14号用 futures 公共K线补 2020-2024，并接本地 2025 到完整 2026-05 数据。2024 futures 对齐检查 35136/35136 行完全匹配，close 差异 0。基础滚动结果：2023 -21.96%，2024 +140.23%，2025 -5.28%，2026 YTD -0.35%；亏损月 6，最差月 -39.60%，最大回撤 -58.39%。11 个压力场景全部失败。当前判断：STOP_FAMILY，不要继续给 ret_state 64/100 家族手工堆补丁。

当前新增 15号统一数据底座体检：
15号：strategy_15_unified_data_baseline_20260627，不是新策略，也不是收益回测，只确认以后换新策略族时先用哪份K线。它沿用 14号合并K线：2020-01-01 到 2026-05-31，共 224928 根15分钟K线、77个月；2020-2024 来自 Binance public USD-M futures archive，2025-2026-05 来自本地 event_entry_fullscan。质量检查：重复时间戳 0，非15分钟断档 0，OHLC异常 0，补齐K线 0，不完整月份 0，缺失月份 0。继承14号结论：2024 public futures 与本地 event 都是 35136 行，close 差异 0。当前判断：DATA_BASELINE_READY。后续新策略族应先用这份 futures 统一K线底座，不要再混用 spot 探针和旧 event 口径。

当前新增 16号新策略族可行性探针：
16号：strategy_16_new_family_probe_20260627，不是候选策略，也不是固化版。它在15号 futures 底座上扫了 144 个简单候选：均线趋势、Donchian突破、RSI回归、布林带回归、ATR突破，杠杆只测 1x/2x/4x。严格逐月选择每个月只用过去数据选参数。最好严格选择器 all_families：2023 +23.04%，2024 +33.45%，2025 -54.66%，2026 YTD +1.90%；亏损月 22，最差月 -25.35%，最少月交易 3，最大回撤 -72.40%。144个静态候选事后硬通过数量也是 0。当前判断：NO_HARD_PASS_IN_SIMPLE_NEW_FAMILY_PROBE。不要升级16号；下一步更适合做17号上限测试，先看这批简单候选的理论月度上限够不够。

当前新增 17号简单策略族上限测试：
17号：strategy_17_simple_family_upper_bound_20260627，不是策略，不能交易，只是“看答案”的月度上限测试。来源是16号的144个简单候选。最宽松上限 monthly_oracle_best_return 每个月直接挑收益最高候选：2023 +10048.37%，2024 +5634.19%，2025 +1912.71%，2026 YTD +564.01%，但仍有6个不盈利月份：2023-07、2024-12、2025-06、2025-09、2026-04、2026-05，且最少月交易为0。带交易次数门槛 monthly_oracle_best_return_order10：2023 +3299.38%，2024 +1721.70%，2025 +385.93%，2026 YTD +274.52%，但仍有10个不盈利月份。当前判断：SIMPLE_FAMILY_UPPER_BOUND_FAILS。不要继续扩这批均线/Donchian/RSI/布林带/ATR突破简单变体。

当前新增 18号上限失败月份复盘：
18号：strategy_18_upper_bound_failure_review_20260627，不是策略，也不是候选，只复盘17号为什么连看答案上限都没过。复盘10个失败月份：2023-07、2023-09、2024-04、2024-06、2024-12、2025-06、2025-07、2025-09、2026-04、2026-05。失败类型：no_positive_candidate 有6个月，意思是144个简单候选里没有任何一个当月正收益；positive_only_with_too_few_orders 有4个月，意思是有正收益候选但交易次数不到10。当前判断：FAILURE_MONTHS_EXPLAIN_SIMPLE_FAMILY_STOP。不要继续微调这批简单规则。

当前新增 19号日历季节性探针：
19号：strategy_19_calendar_seasonality_probe_20260627，不是候选策略，也不是固化版，只检查星期几、小时、交易时段这类日历规律有没有用。候选216个，分桶包括 session/weekday/hour/hour_week。最好严格选择器 all_calendar：2023 -1.32%，2024 +71.64%，2025 -26.91%，2026 YTD +43.60%；亏损月22，最差月 -25.36%，最少月交易0，最大回撤 -46.37%。单个动态候选事后最好 calendar_weekday_lbexpanding_thr0p0_min20_lev1p0：2023 +31.81%，2024 +71.57%，2025 -10.55%，2026 YTD +43.60%，亏损月17，最少月交易10。当前判断：CALENDAR_SEASONALITY_FAILS。不要升级19号。

当前新增 20号 OHLC结构上限测试：
20号：strategy_20_ohlc_structure_upper_bound_20260627，不是策略，不能交易，只是“看答案”的月度上限测试。15号 futures 底座没有成交量，所以只测 K线实体、影线、振幅和波动结构，共189个候选。静态硬通过数量 0。最宽松上限 monthly_oracle_best_return：2023 +51.61%，2024 +18.35%，2025 +12.99%，2026 YTD +0.18%，但仍有30个不盈利月份，最少月交易0。要求每月交易不少于10次后：2023 +22.80%，2024 -2.56%，2025 -6.90%，2026 YTD -2.98%，不盈利月份33个。当前判断：OHLC_STRUCTURE_UPPER_BOUND_FAILS。不要继续扩这批 OHLC 结构小规则。

当前新增 21号成交量上限测试：
21号：strategy_21_volume_upper_bound_20260627，不是策略，不能交易，只是“看答案”的月度上限测试。它下载 Binance public USD-M futures 15m K线的 volume/taker 字段，2020-01 到 2026-05 共224928行；与15号 OHLC 底座 close 完全对齐。候选378个，包括成交量放大、taker买卖比例、放量确认涨跌。静态硬通过数量 0。最宽松上限 monthly_oracle_best_return：2023 +45.98%，2024 +54.74%，2025 -12.01%，2026 YTD -9.17%，仍有25个不盈利月份。要求每月交易不少于10次后：2023 +39.04%，2024 +50.98%，2025 -12.73%，2026 YTD -9.17%，不盈利月份29个。当前判断：VOLUME_UPPER_BOUND_FAILS。不要继续扩这批成交量小规则。

当前新增 22号硬目标瓶颈审计：
22号：strategy_22_hard_target_bottleneck_20260627，不是策略，不能交易，只把16/19/20/21的927个候选放进同一张压力表。压力网格包括月交易次数0/2/5/10、手续费0.0%到0.4%、月收益要求不限/>=-1%/>0、年收益门槛50%/100%。严格逐月选择器0/120通过；月度oracle80/120通过但它看答案不能交易。原始硬目标下，月度oracle也失败，差2023-07和2024-06两个月；严格选择器2025 -95.78%，2026 YTD +7.81%。当前判断：ORIGINAL_TARGET_AND_SELECTION_BOTTLENECK。不要继续扩16/19/20/21小规则，见 RESEARCH_DECISION_STOP_SIMPLE_RULES_AFTER_22.md。

后续如果继续开发，不能覆盖 0号策略，必须另起新编号、新文件夹。
这里只做研究和回测，不下实盘，不读取密钥，不启动 supervisor。下一步如果继续，只能另起23号，换真正不同的数据源先做上限测试，或把目标改得更现实；不要直接上机器学习。

请用中文、通俗的话和我沟通。
```
