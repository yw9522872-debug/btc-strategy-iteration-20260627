# 下一窗口交接

本文件用于开启新的 Codex 对话时交接本项目。

## 给下一个窗口直接发送的内容

```text
请接着这个项目继续工作：

本地路径：C:\Users\WHR\Documents\策略迭代
GitHub：https://github.com/yw9522872-debug/btc-strategy-iteration-20260627

请先阅读：
1. AGENTS.md
2. NEXT_CHAT_HANDOFF.md
3. GPT_PRO_REVIEW_BRIEF.md
4. STRATEGY_31_MULTISYMBOL_FREE_FUTURES_UPPER_BOUND.md
5. STRATEGY_32_BTC_3M_2025_TODAY_UPPER_BOUND.md
6. STRATEGY_33_MULTISYMBOL_FREE_FUTURES_STRICT_SELECTOR.md
7. STRATEGY_34_MULTISYMBOL_FAILURE_ROOT_CAUSE.md
8. STRATEGY_35_OLD_BTC_3M_INSPIRATION_REVIEW.md
9. STRATEGY_36_MULTISYMBOL_ENSEMBLE_SELECTOR.md
10. STRATEGY_37_BTC_3M_MULTITIMEFRAME_EVENT_POOL.md
11. STRATEGY_38_FORCED_OVERFIT_ALPHA_MINING.md
12. STRATEGY_39_ALPHA_PATTERN_DISCOVERY.md
13. STRATEGY_40_MULTISYMBOL_FUNDING_ALPHA_SELECTOR.md
14. STRATEGY_41_BTC_HYPE_RELAXED_DRAWDOWN.md
15. STRATEGY_42_BTC_HYPE_STATE_PREDICTABILITY.md
16. STRATEGY_43_BTC_HYPE_TAIL_EVENT_ATTRIBUTION.md
17. artifacts/strategy_31_multisymbol_free_futures_sample_upper_bound_20260628/summary.json
18. artifacts/strategy_32_btc_3m_2025_today_upper_bound_20260628/summary.json
19. artifacts/strategy_33_multisymbol_free_futures_strict_selector_20260629/summary.json
20. artifacts/strategy_34_multisymbol_failure_root_cause_20260629/summary.json
21. artifacts/strategy_35_old_btc_3m_inspiration_review_20260629/summary.json
22. artifacts/strategy_36_multisymbol_ensemble_selector_20260629/summary.json
23. artifacts/strategy_37_btc_3m_multitimeframe_event_pool_20260629/summary.json
24. artifacts/strategy_38_forced_overfit_alpha_mining_20260629/summary.json
25. artifacts/strategy_39_alpha_pattern_discovery_20260629/summary.json
26. artifacts/strategy_40_multisymbol_funding_alpha_selector_20260629/summary.json
27. artifacts/strategy_41_btc_hype_relaxed_drawdown_20260629/summary.json
28. artifacts/strategy_42_btc_hype_state_predictability_20260629/summary.json
29. artifacts/strategy_43_btc_hype_tail_event_attribution_20260629/summary.json

重要：不要和其他 Codex 线程、其他浏览器 GPT Pro 页面、其他仓库混淆。

当前最新策略结果提交：
330d787 Add strategy 33-40 research audits

当前最新标签：
strategy-32-btc-3m-2025-today-upper-bound-20260628

这里只做研究和回测：
不下实盘，不读取密钥，不启动 supervisor，不改真实仓位。

0号策略已经永久保存，不能覆盖。
1F、1G、2C、4号、10号到43号都不能覆盖，后续必须另起新编号、新目录。

当前关键结论：
2C 是当前旧候选里历史表现最好的一个：2025 +359.10%、2026 +260.59%，但仍是研究候选，不是实盘保证；0号是永久固化基准，不是收益最高者。
14号已经判定旧 ret_state 64/100 家族为 STOP_FAMILY。
22号说明简单免费K线小规则和严格选择器双重卡住。
23号资金费率看答案上限很好，但24号严格选择器失败，不能升级。
25号说明 Binance 免费持仓量/多空比历史不够多年回测。
30号 spot-perp aggTrades 样本上限失败，不要下载全量约90GB继续做。
31号多币种免费期货样本上限有信号，但只是四个月看答案样本，不能交易。
32号 BTC 单币 3m 从2025到2026-06-27上限失败，不要继续扩 BTC 3m 小规则。
33号多币种完整历史严格选择器失败：看答案 oracle 能过，但严格逐月选择器不能提前选中正确候选。
34号拆解33号失败根因：每个月都有看答案赚钱候选，但赢家换得太快，月初训练排序找不到；跟随上月赢家也大亏。
35号按用户要求复盘旧项目 `C:\Users\WHR\Documents\BTC多因子研究_20260626`：旧 BTC 3m 样本内线有收益，但2024压力和pre-2025锁参都失败；只能借框架，不能借旧参数。
36号先用33号已有候选测试“多规则组合”近路，180组严格组合配置通过数为0，最好2025也只有+0.06%、2026 YTD为-22.93%。
37号按35号建议另起 BTC 3m 多周期事件池审计，数据质量通过，但静态硬通过0；每月10单看答案 oracle 仍差 2024-04 和 2025-10 两个月；严格选择器最好 2025 -6.49%、2026 YTD -7.45%，不能升级。
38号按用户要求强行过拟合挖 Alpha 线索：合并33号和37号后，看答案结果月月正、2025 +17665719.09%、2026 YTD +4414.40%，但41/41个月赢家都来自33号，主要是多币种单币4倍动量/反转；月初训练排序找不到赢家，跟随上月赢家也大亏，所以只能当线索，不能升级策略。
39号按用户要求从38号里挖规律：规律明确，赢家集中在近期高波动/高涨跌幅山寨币、4倍、单币动量/反转，384根15m窗口最多；上月涨跌幅绝对值排前5占72.5%，上月波动率排前5占72.5%。但简单月初不看未来选择器不能让2025和2026同时盈利，说明只是找到历史赢家形状，还没找到可交易选择器。
40号按39号建议测试 funding 提前识别信号：下载 Binance 免费 fundingRate REST 历史，覆盖 ETH/SOL/DOGE/XRP/ADA/AVAX/LINK 从2022-12到2026-05，每币3834行。Funding 有弱解释力，赢家上月 funding 为正比例82.5%、绝对值排前3比例50.0%；最好不看未来选择器 2025 +203.32%、2026 YTD +18.01%，但2024 -90.19%，不能升级。
41号按用户要求缩到 BTC+HYPE 并放宽门槛：去掉月月盈利和每月交易次数，只要求2025/2026 YTD都超过100%、最大回撤不超过50%。静态固定参数通过数0；回撤限制版看答案 oracle 2025 +4176.22%、2026 YTD +100.67%、最大回撤 -49.98%，但这是看答案；严格不看未来选择器 2025 -16.27%、2026 YTD -35.55%，不能升级。
42号按 GPT Pro 建议做 BTC+HYPE 状态可预测性审计：只用 Binance 免费 REST 小数据 klines/fundingRate/premiumIndexKlines/markPriceKlines，不下载大 aggTrades。月初状态 top20 只包含41号安全oracle赢家 33.33%；top20回撤过滤看答案上限 2025 +191.46%、2026 YTD +36.17%、最大回撤 -47.88%；严格top1为2025 +29.45%、2026 YTD -32.95%、最大回撤 -99.999%。结论：月初状态打分近路失败，不能升级。
43号按 GPT Pro 第二轮建议做 BTC+HYPE 尾部事件归因：复用41号回撤限制版oracle逐K收益和42号BTC/HYPE 15m数据。极端事件原始K线占比6.20%，前后各48小时事件窗口占比79.05%；正收益log里90.44%落在事件窗口，窗口内净log +4.7580，窗口外净log -0.3059。结论：41号oracle利润确实和尾部事件相伴，但窗口很宽，只是线索，不能升级。

下一步建议：
不要继续手工扩多币种免费K线小规则，也不要照搬旧 BTC 3m 的7条规则，不要继续调33号组合参数，不要小修37号 BTC 3m 多周期事件池，不要把38号或41号看答案线当策略，也不要继续扩 funding-only 小规则。42号已经证明“月初状态打分缩小候选池”这条近路不够。43号说明剩余线索只在尾部事件附近。若继续，另起44号只做事件发生后的 action oracle 上限；如果事件后上限不够，就停止 BTC+HYPE 主线，改成影子跟踪/低年化验证。

环境状态：
刚执行过 `git gc --prune=now` 清理，`.git` loose objects 已从约 11.76GiB 降到几乎为0，pack约148.90MiB；没有 `.git/index.lock`。33-40号已提交到本地提交 `330d787`；41-43号是当前本地新结果，尚未提交、尚未推送、尚未打标签。

请用中文、通俗的话和我沟通。
```

## 项目身份

- 本地路径：`C:\Users\WHR\Documents\策略迭代`
- GitHub：`https://github.com/yw9522872-debug/btc-strategy-iteration-20260627`
- 当前最新策略结果提交：`0500e23 Add strategy 32 BTC 3m upper bound audit`
- 当前最新标签：`strategy-32-btc-3m-2025-today-upper-bound-20260628`
- 33号、34号、35号、36号、37号、38号、39号、40号已提交到本地提交 `330d787 Add strategy 33-40 research audits`。41号、42号、43号本地结果已生成：`strategy_41_btc_hype_relaxed_drawdown_20260629`、`strategy_42_btc_hype_state_predictability_20260629`、`strategy_43_btc_hype_tail_event_attribution_20260629`。41-43号当前尚未提交、尚未推送、尚未打标签。
- Git 清理状态：已执行 `git gc --prune=now`；`.git` loose objects 几乎为0，pack约 `148.90 MiB`，当前没有 `.git/index.lock`。
- 15-19 保存提交：`ff67b92 Add strategy 15-19 research probes`
- 15号、16号、17号、18号、19号、20号、21号、22号、23号、24号、25号、26号、27号、28号、29号、30号、31号、32号及交接说明已提交并推送到 GitHub
- 持仓量/多空比历史数据源审查文件：`DATA_SOURCE_OPEN_INTEREST_LONG_SHORT_REVIEW_20260627.md`。它不是策略，无策略标签。
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
- 23号资金费率上限测试保存标签：`strategy-23-funding-rate-upper-bound-20260627`
- 24号资金费率严格选择器保存标签：`strategy-24-funding-rate-strict-selector-20260627`
- 25号持仓量上限可行性审计保存标签：`strategy-25-open-interest-upper-bound-feasibility-20260627`
- 26号1分钟内部结构上限测试保存标签：`strategy-26-intrabar-1m-upper-bound-20260627`
- 27号目标可行性审计保存标签：`strategy-27-target-feasibility-audit-20260627`
- 28号不要求月月盈利审计保存标签：`strategy-28-relaxed-no-monthly-profit-audit-20260628`
- 29号免费 raw trade 数据覆盖审计保存标签：`strategy-29-free-raw-trade-coverage-audit-20260628`
- 30号 spot-perp aggTrades 样本上限测试保存标签：`strategy-30-spot-perp-aggtrade-sample-upper-bound-20260628`
- 31号多币种免费期货样本上限测试保存标签：`strategy-31-multisymbol-free-futures-sample-upper-bound-20260628`
- 32号 BTC 3m 2025到最新公开数据上限测试保存标签：`strategy-32-btc-3m-2025-today-upper-bound-20260628`

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
29. `STRATEGY_23_FUNDING_RATE_UPPER_BOUND.md`
30. `STRATEGY_24_FUNDING_RATE_STRICT_SELECTOR.md`
31. `STRATEGY_25_OPEN_INTEREST_UPPER_BOUND_FEASIBILITY.md`
32. `STRATEGY_26_INTRABAR_1M_UPPER_BOUND.md`
33. `STRATEGY_27_TARGET_FEASIBILITY_AUDIT.md`
34. `STRATEGY_28_RELAXED_NO_MONTHLY_PROFIT_AUDIT.md`
35. `STRATEGY_29_FREE_RAW_TRADE_COVERAGE_AUDIT.md`
36. `STRATEGY_30_SPOT_PERP_AGGTRADE_SAMPLE_UPPER_BOUND.md`
37. `STRATEGY_31_MULTISYMBOL_FREE_FUTURES_UPPER_BOUND.md`
38. `STRATEGY_32_BTC_3M_2025_TODAY_UPPER_BOUND.md`
39. `STRATEGY_33_MULTISYMBOL_FREE_FUTURES_STRICT_SELECTOR.md`
40. `STRATEGY_34_MULTISYMBOL_FAILURE_ROOT_CAUSE.md`
41. `STRATEGY_35_OLD_BTC_3M_INSPIRATION_REVIEW.md`
42. `STRATEGY_36_MULTISYMBOL_ENSEMBLE_SELECTOR.md`
43. `STRATEGY_37_BTC_3M_MULTITIMEFRAME_EVENT_POOL.md`
44. `STRATEGY_38_FORCED_OVERFIT_ALPHA_MINING.md`
45. `STRATEGY_39_ALPHA_PATTERN_DISCOVERY.md`
46. `STRATEGY_40_MULTISYMBOL_FUNDING_ALPHA_SELECTOR.md`
47. `DATA_SOURCE_OPEN_INTEREST_LONG_SHORT_REVIEW_20260627.md`
48. `RESEARCH_DECISION_STOP_SIMPLE_RULES_AFTER_22.md`
49. `CURRENT_STRATEGY_FREEZE.md`
50. `GPT_PRO_REVIEW_BRIEF.md`
51. `artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json`
52. `artifacts/strategy_15_unified_data_baseline_20260627/summary.json`
53. `artifacts/strategy_16_new_family_probe_20260627/summary.json`
54. `artifacts/strategy_17_simple_family_upper_bound_20260627/summary.json`
55. `artifacts/strategy_18_upper_bound_failure_review_20260627/summary.json`
56. `artifacts/strategy_19_calendar_seasonality_probe_20260627/summary.json`
57. `artifacts/strategy_20_ohlc_structure_upper_bound_20260627/summary.json`
58. `artifacts/strategy_21_volume_upper_bound_20260627/summary.json`
59. `artifacts/strategy_22_hard_target_bottleneck_20260627/summary.json`
60. `artifacts/strategy_23_funding_rate_upper_bound_20260627/summary.json`
61. `artifacts/strategy_24_funding_rate_strict_selector_20260627/summary.json`
62. `artifacts/strategy_25_open_interest_upper_bound_feasibility_20260627/summary.json`
63. `artifacts/strategy_26_intrabar_1m_upper_bound_20260627/summary.json`
64. `artifacts/strategy_27_target_feasibility_audit_20260627/summary.json`
65. `artifacts/strategy_28_relaxed_no_monthly_profit_audit_20260628/summary.json`
66. `artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/summary.json`
67. `artifacts/strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628/summary.json`
68. `artifacts/strategy_31_multisymbol_free_futures_sample_upper_bound_20260628/summary.json`
69. `artifacts/strategy_32_btc_3m_2025_today_upper_bound_20260628/summary.json`
70. `artifacts/strategy_33_multisymbol_free_futures_strict_selector_20260629/summary.json`
71. `artifacts/strategy_34_multisymbol_failure_root_cause_20260629/summary.json`
72. `artifacts/strategy_35_old_btc_3m_inspiration_review_20260629/summary.json`
73. `artifacts/strategy_36_multisymbol_ensemble_selector_20260629/summary.json`
74. `artifacts/strategy_37_btc_3m_multitimeframe_event_pool_20260629/summary.json`
75. `artifacts/strategy_38_forced_overfit_alpha_mining_20260629/summary.json`
76. `artifacts/strategy_39_alpha_pattern_discovery_20260629/summary.json`
77. `artifacts/strategy_40_multisymbol_funding_alpha_selector_20260629/summary.json`

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

## 23号资金费率上限测试

- 测试编号：`strategy_23_funding_rate_upper_bound_20260627`
- 定位文件：`STRATEGY_23_FUNDING_RATE_UPPER_BOUND.md`
- 脚本：`scripts/audit_strategy_23_funding_rate_upper_bound_20260627.py`
- 结果目录：`artifacts/strategy_23_funding_rate_upper_bound_20260627/`
- 这不是策略，不能交易，只是测试资金费率这个新数据源的“看答案”月度上限。
- 数据源：Binance public USD-M futures fundingRate archive，`2020-01` 到 `2026-05`，共 `7029` 条资金费率记录，无重复、无8小时断档。
- 候选：`246` 个，只用资金费率水平、变化、均值、z-score。
- 静态候选硬通过数量：`0`。
- 带每月10单门槛的月度oracle能过：2023 `+17263.32%`，2024 `+45467.21%`，2025 `+6801.02%`，2026 YTD `+648.74%`，亏损月 `0`，最差月 `+5.43%`，最少月交易 `10`。
- 当前判断：`FUNDING_RATE_UPPER_BOUND_HAS_MONTHLY_PIECES`。资金费率有事后好月份，但不能交易，必须做严格选择器。

## 24号资金费率严格选择器

- 测试编号：`strategy_24_funding_rate_strict_selector_20260627`
- 定位文件：`STRATEGY_24_FUNDING_RATE_STRICT_SELECTOR.md`
- 脚本：`scripts/audit_strategy_24_funding_rate_strict_selector_20260627.py`
- 结果目录：`artifacts/strategy_24_funding_rate_strict_selector_20260627/`
- 这不是策略，不能交易，只复用23号资金费率候选，没有新增规则。
- 严格口径：每个月只能用过去月份选择候选。
- 最好严格选择器 `funding_mean_only`：2023 `-22.82%`，2024 `-42.05%`，2025 `+9.70%`，2026 YTD `+10.95%`，亏损月 `20`，最差月 `-29.05%`，最少月交易 `0`。
- 当前判断：`FUNDING_RATE_STRICT_SELECTOR_FAILS`。资金费率看答案很好，但当前规则无法提前选中好月份，不要升级资金费率候选。

## 25号持仓量上限可行性审计

- 审计编号：`strategy_25_open_interest_upper_bound_feasibility_20260627`
- 定位文件：`STRATEGY_25_OPEN_INTEREST_UPPER_BOUND_FEASIBILITY.md`
- 脚本：`scripts/audit_strategy_25_open_interest_upper_bound_feasibility_20260627.py`
- 结果目录：`artifacts/strategy_25_open_interest_upper_bound_feasibility_20260627/`
- 这不是策略，也不是收益回测，只检查 Binance 公开持仓量历史够不够做 2020-2026 上限测试。
- 官方接口：`openInterestHist`，官方说明只提供最近 `1` 个月。
- 实测：2020-01 和 2023-01 请求失败，错误为 `startTime invalid`；2026-05-31 到 2026-06-01 成功返回 `97` 行；最近数据成功返回 `500` 行。
- 当前判断：`OPEN_INTEREST_HISTORY_NOT_AVAILABLE_FOR_2020_2026`。公开持仓量接口不够覆盖 2023-2026 硬目标，不能硬做历史上限。

## 持仓量/多空比历史数据源审查

- 审查文件：`DATA_SOURCE_OPEN_INTEREST_LONG_SHORT_REVIEW_20260627.md`
- 这不是策略，没有收益回测，也没有策略标签。
- 结论：Binance 官方 REST 不能做多年历史回测，因为持仓量只给最近 `1` 个月，多空比只给最近 `30` 天。
- 首选数据源：`Tardis.dev`。原因是它有 Binance USDS-M futures 历史覆盖说明、CSV/API、交易所时间和本地接收时间；持仓量从 2020-05 起，多空比从 `2020-10-28` 起。
- 备选：`CoinGlass` 和 `Amberdata`。但必须先确认能导出 BTCUSDT Binance futures 从 `2020-10-28` 到 `2026-05-31` 的完整历史。
- 拿到完整 CSV 前，不要硬做持仓量/多空比多年回测。拿到后，先做数据质量审计和 15m 底座对齐，再做上限测试。

## 26号 1分钟内部结构上限测试

- 测试编号：`strategy_26_intrabar_1m_upper_bound_20260627`
- 定位文件：`STRATEGY_26_INTRABAR_1M_UPPER_BOUND.md`
- 脚本：`scripts/audit_strategy_26_intrabar_1m_upper_bound_20260627.py`
- 结果目录：`artifacts/strategy_26_intrabar_1m_upper_bound_20260627/`
- 这不是策略，不能交易，只是用 Binance 免费公开 1分钟K线测试15分钟内部结构的“看答案”上限。
- 数据：BTCUSDT USD-M futures 1m 月包，`2020-01` 到 `2026-05`；缺失1分钟K线 `0`，重复 `0`，非1分钟断档 `0`，不完整15分钟组 `0`。
- 数据注意：1分钟聚合OHLC有 `8` 根15分钟K线和15号底座不一致，26号已禁用这些K线信号。
- 候选：`186` 个，包括前10/后5分钟走势、后5分钟成交量占比、late taker买入比例、路径效率、高低点出现位置、震荡反转。
- 静态硬通过数量：`0`。
- 最好看答案上限 `monthly_oracle_best_return`：2023 `+47.27%`、2024 `+16.29%`、2025 `-3.27%`、2026 YTD `-7.68%`，亏损月 `28`，最少月交易 `0`。
- 要求每月10单后的看答案上限：2023 `+34.37%`、2024 `+15.88%`、2025 `-8.43%`、2026 YTD `-9.54%`，不盈利月份 `30`。
- 当前判断：`INTRABAR_1M_UPPER_BOUND_FAILS`。不要继续扩这批1分钟内部结构小规则。

## 27号目标可行性审计

- 审计编号：`strategy_27_target_feasibility_audit_20260627`
- 定位文件：`STRATEGY_27_TARGET_FEASIBILITY_AUDIT.md`
- 脚本：`scripts/audit_strategy_27_target_feasibility_20260627.py`
- 结果目录：`artifacts/strategy_27_target_feasibility_audit_20260627/`
- 这不是策略，不能交易，只检查继续加小规则前，原目标是不是太硬。
- 未新增候选规则；复用22号里16/19/20/21的 `927` 个候选月度基础表，并参考23/24资金费率、26号1分钟内部结构结果。
- 目标网格：年收益 `30/50/80/100%`，月度不限/不低于`-2%`/不低于`-1%`/>`0`，每月交易 `0/5/10`，主手续费仍为开平合计 `0.2%`。
- 原目标下：看答案 oracle 仍失败，差 `2023-07` 和 `2024-06` 两个月；严格逐月选择器 2025 `-95.78%`、2026 YTD `+7.81%`，不合格月份 `41`。
- 放宽后：严格逐月选择器 `0/49` 通过；看答案 oracle `37/49` 通过。
- 原手续费 `0.2%` 下，看答案 oracle 最接近原目标的通过口径是：年门槛 `100%`、每月交易不少于 `10`、月收益不低于 `-1%`。
- 当前判断：`TARGET_RELAXATION_HELPS_ORACLE_NOT_SELECTOR`。目标放宽能让看答案上限通过，但不能让严格选择器通过；真正卡点是不能提前选中正确月份/候选。

## 28号不要求月月盈利审计

- 审计编号：`strategy_28_relaxed_no_monthly_profit_audit_20260628`
- 定位文件：`STRATEGY_28_RELAXED_NO_MONTHLY_PROFIT_AUDIT.md`
- 脚本：`scripts/audit_strategy_28_relaxed_no_monthly_profit_20260628.py`
- 结果目录：`artifacts/strategy_28_relaxed_no_monthly_profit_audit_20260628/`
- 这不是策略，不能交易，只检查“如果不要求每个月都盈利，ret_state 64/100 家族能不能重新优化”。
- 未新增交易规则，未新增市场数据；复用14号 `ret_state 64/100` 家族和统一 futures K线底座。
- 主手续费仍为开平合计 `0.2%`；严格选择器仍然每个月只能用过去月份选参数。
- 最好的严格不看未来结果：2023 `-21.96%`、2024 `+140.23%`、2025 `-5.28%`、2026 YTD `-0.35%`，亏损月份 `6`，最差月份 `-39.60%`，最大回撤 `-58.39%`，最低月交易 `10`。
- 看答案月度 oracle 很强：2025 `+1692.64%`、2026 YTD `+171.90%`，但它事后挑当月最好候选，是未来函数，不能交易。
- 当前判断：`NO_STRICT_RELAXED_UPGRADE`。去掉月月盈利要求也救不回严格选择器；问题不是月月盈利条件单独太严，而是当月之前选不出正确候选。

## 29号免费 raw trade 数据覆盖审计

- 审计编号：`strategy_29_free_raw_trade_coverage_audit_20260628`
- 定位文件：`STRATEGY_29_FREE_RAW_TRADE_COVERAGE_AUDIT.md`
- 脚本：`scripts/audit_strategy_29_free_raw_trade_coverage_20260628.py`
- 结果目录：`artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/`
- 这不是策略，不能交易，只检查 GPT Pro 建议的免费路线：现货-永续 raw trade 成交流错位。
- 审计只做 HTTP HEAD 检查，不下载大 trade 压缩包。
- `2020-01` 到 `2026-05` 共 `77` 个月全部覆盖：futures/spot `aggTrades`、futures/spot `trades`、futures/spot 1m K线、fundingRate、markPriceKlines、indexPriceKlines、premiumIndexKlines 都是 `77/77`。
- 可选 `bookTicker` 月包探针 2020-01 返回 `404`，不要做秒级盘口主策略。
- 数据量很大：futures `aggTrades` 约 `39.56GB`，spot `aggTrades` 约 `50.70GB`；所以下一步优先用 `aggTrades`，不要先下更重的 `trades`。
- 当前判断：`FREE_SPOT_PERP_RAW_TRADE_DATA_AVAILABLE`。如果继续，另起30号，只做 spot-perp `aggTrades` 成交流错位上限测试，funding/mark/index/premium 只做过滤器。

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

- 当前最新研究链：14号判定 `ret_state 64/100` 家族 `STOP_FAMILY`；15号确认 futures 统一K线底座可用；16-22号说明免费K线小规则和严格选择器卡住；23-24号说明资金费率看答案强但严格选择失败；25号说明 Binance 免费持仓量历史不够；26-28号继续确认 BTC 单币旧路线救不回；29号确认免费 raw trade 数据覆盖完整；30号 spot-perp `aggTrades` 样本上限失败；31号多币种样本上限有信号；32号 BTC 单币 3m 上限失败；33号多币种完整历史严格选择器失败；34号确认33号根因是赢家不稳定、过去表现选不中；35号复盘旧 BTC 3m 项目，结论是可借框架但不能借旧参数；36号测试33号候选多规则组合近路，仍失败。
- 下一轮不要继续修 `ret_state 64/100`，不要继续扩均线/Donchian/RSI/布林带/ATR突破，不要升级日历季节性，不要继续扩 OHLC/成交量/taker/1分钟内部结构小规则，不要继续 spot-perp `aggTrades`，也不要继续单币 BTC 3m。
- 如果继续研究，不要继续手工扩多币种免费K线小规则；若测试新选择方法，必须另起新编号并先做上限/泄漏审计，否则应换真正不同的新数据源，或先把目标改成更现实的影子跟踪/低年化验证。
- 当前历史硬目标很可能过严，但不是唯一问题：22号显示原始硬目标下连看答案 oracle 都差 `2` 个月；27号显示放宽后看答案能过，但严格逐月选择器仍 `0/49`；28号显示拿掉“月月盈利”后，旧 ret_state 家族严格选择器仍在 2025/2026 亏损。
- 每次新结果都写清楚手续费、未来函数检查、月度收益、交易次数、最大回撤。

## 发到下一个窗口的内容

最新可复制内容已经放在本文顶部“给下一个窗口直接发送的内容”。下面长版保留作历史参考，避免遗漏旧资料。

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
30. STRATEGY_23_FUNDING_RATE_UPPER_BOUND.md
31. STRATEGY_24_FUNDING_RATE_STRICT_SELECTOR.md
32. STRATEGY_25_OPEN_INTEREST_UPPER_BOUND_FEASIBILITY.md
33. STRATEGY_26_INTRABAR_1M_UPPER_BOUND.md
34. STRATEGY_27_TARGET_FEASIBILITY_AUDIT.md
35. STRATEGY_28_RELAXED_NO_MONTHLY_PROFIT_AUDIT.md
36. STRATEGY_29_FREE_RAW_TRADE_COVERAGE_AUDIT.md
37. DATA_SOURCE_OPEN_INTEREST_LONG_SHORT_REVIEW_20260627.md
38. RESEARCH_DECISION_STOP_SIMPLE_RULES_AFTER_22.md
39. CURRENT_STRATEGY_FREEZE.md
40. GPT_PRO_REVIEW_BRIEF.md
41. artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json
42. artifacts/strategy_15_unified_data_baseline_20260627/summary.json
43. artifacts/strategy_16_new_family_probe_20260627/summary.json
44. artifacts/strategy_17_simple_family_upper_bound_20260627/summary.json
45. artifacts/strategy_18_upper_bound_failure_review_20260627/summary.json
46. artifacts/strategy_19_calendar_seasonality_probe_20260627/summary.json
47. artifacts/strategy_20_ohlc_structure_upper_bound_20260627/summary.json
48. artifacts/strategy_21_volume_upper_bound_20260627/summary.json
49. artifacts/strategy_22_hard_target_bottleneck_20260627/summary.json
50. artifacts/strategy_23_funding_rate_upper_bound_20260627/summary.json
51. artifacts/strategy_24_funding_rate_strict_selector_20260627/summary.json
52. artifacts/strategy_25_open_interest_upper_bound_feasibility_20260627/summary.json
53. artifacts/strategy_26_intrabar_1m_upper_bound_20260627/summary.json
54. artifacts/strategy_27_target_feasibility_audit_20260627/summary.json
55. artifacts/strategy_28_relaxed_no_monthly_profit_audit_20260628/summary.json
56. artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/summary.json
57. artifacts/strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628/summary.json
58. artifacts/strategy_31_multisymbol_free_futures_sample_upper_bound_20260628/summary.json

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

当前新增 23号资金费率上限测试：
23号：strategy_23_funding_rate_upper_bound_20260627，不是策略，不能交易，只测试资金费率这个新数据源的看答案月度上限。Binance public USD-M futures fundingRate archive，2020-01到2026-05，共7029条，无重复、无8小时断档。246个资金费率候选静态硬通过0个，但带每月10单门槛的月度oracle能过：2023 +17263.32%，2024 +45467.21%，2025 +6801.02%，2026 YTD +648.74%，亏损月0，最差月 +5.43%，最少月交易10。当前判断：FUNDING_RATE_UPPER_BOUND_HAS_MONTHLY_PIECES，但它看答案不能交易。

当前新增 24号资金费率严格选择器：
24号：strategy_24_funding_rate_strict_selector_20260627，不是策略，不能交易，只复用23号候选，每个月只用过去月份选候选。最好严格选择器 funding_mean_only：2023 -22.82%，2024 -42.05%，2025 +9.70%，2026 YTD +10.95%，亏损月20，最差月 -29.05%，最少月交易0。当前判断：FUNDING_RATE_STRICT_SELECTOR_FAILS。资金费率看答案很好，但当前规则无法提前选中好月份，不要升级资金费率候选。

当前新增 25号持仓量上限可行性审计：
25号：strategy_25_open_interest_upper_bound_feasibility_20260627，不是策略，也不是收益回测，只检查 Binance 公开持仓量历史够不够做2020-2026上限测试。官方 openInterestHist 只提供最近1个月。实测 2020-01 和 2023-01 请求失败，错误 startTime invalid；2026-05-31 到 2026-06-01 成功返回97行；最近数据成功返回500行。当前判断：OPEN_INTEREST_HISTORY_NOT_AVAILABLE_FOR_2020_2026。公开持仓量接口不够覆盖2023-2026硬目标，不能硬做历史上限。

当前新增持仓量/多空比历史数据源审查：
DATA_SOURCE_OPEN_INTEREST_LONG_SHORT_REVIEW_20260627.md 不是策略，只审查后续能不能找到完整、可审计的数据源。结论：Binance 官方 REST 不能做多年历史回测，因为持仓量只给最近1个月，多空比只给最近30天。首选 Tardis.dev，因其有 Binance USDS-M futures 历史覆盖、CSV/API、交易所时间和本地接收时间；持仓量从2020-05起，多空比从2020-10-28起。CoinGlass 和 Amberdata 可作备选，但必须先确认能导出 BTCUSDT Binance futures 从2020-10-28到2026-05-31的完整历史。拿到完整 CSV 前，不要硬做持仓量/多空比多年回测；拿到后先做数据质量审计和15m底座对齐，再做上限测试。

当前新增 26号 1分钟内部结构上限测试：
26号：strategy_26_intrabar_1m_upper_bound_20260627，不是策略，不能交易，只用 Binance 免费公开 1分钟 USD-M futures K线测试15分钟内部结构的看答案上限。2020-01到2026-05 的1分钟月包完整，缺失/重复/断档均为0；有8根15分钟K线和15号底座OHLC不一致，已禁用这些K线信号。186个候选静态硬通过为0；最好看答案上限 monthly_oracle_best_return 为 2023 +47.27%、2024 +16.29%、2025 -3.27%、2026 YTD -7.68%，亏损月28，最少月交易0；要求每月10单后 2025 -8.43%、2026 YTD -9.54%，不盈利月份30。当前判断：INTRABAR_1M_UPPER_BOUND_FAILS。不要继续扩这批1分钟内部结构小规则。

当前新增 27号目标可行性审计：
27号：strategy_27_target_feasibility_audit_20260627，不是策略，不能交易，只检查继续加小规则前，原目标是不是太硬。它未新增候选规则，复用22号里16/19/20/21的927个候选月度基础表，并参考23/24资金费率和26号1分钟内部结构结果。目标网格：年收益30/50/80/100%，月度不限/不低于-2%/不低于-1%/>0，每月交易0/5/10，主手续费仍为开平合计0.2%。原目标下，看答案oracle仍失败，差2023-07和2024-06两个月；严格逐月选择器2025 -95.78%、2026 YTD +7.81%，不合格月份41。放宽后，严格逐月选择器0/49通过；看答案oracle37/49通过。原手续费0.2%下，看答案oracle最接近原目标的通过口径是年门槛100%、每月交易不少于10、月收益不低于-1%。当前判断：TARGET_RELAXATION_HELPS_ORACLE_NOT_SELECTOR。目标放宽能让看答案上限通过，但不能让严格选择器通过；真正卡点是不能提前选中正确月份/候选。

当前新增 28号不要求月月盈利审计：
28号：strategy_28_relaxed_no_monthly_profit_audit_20260628，不是策略，不能交易，只检查如果不要求每个月都盈利，旧 ret_state 64/100 家族能不能重新优化。它不新增交易规则，不新增市场数据，复用14号统一 futures K线底座；主手续费仍为开平合计0.2%，严格选择器仍每个月只能用过去数据选参数。最好的严格不看未来结果：2023 -21.96%、2024 +140.23%、2025 -5.28%、2026 YTD -0.35%，亏损月份6，最差月份 -39.60%，最大回撤 -58.39%，最低月交易10。看答案月度oracle很强：2025 +1692.64%、2026 YTD +171.90%，但它事后挑当月最好候选，是未来函数，不能交易。当前判断：NO_STRICT_RELAXED_UPGRADE。去掉月月盈利要求也救不回严格选择器；问题不是月月盈利条件单独太严，而是当月之前选不出正确候选。

当前新增 29号免费 raw trade 数据覆盖审计：
29号：strategy_29_free_raw_trade_coverage_audit_20260628，不是策略，不能交易，只检查 GPT Pro 建议的免费路线：现货-永续 raw trade 成交流错位。它只做 HTTP HEAD 检查，不下载大 trade 压缩包。2020-01 到 2026-05 共77个月全部覆盖：futures/spot aggTrades、futures/spot trades、futures/spot 1m K线、fundingRate、markPriceKlines、indexPriceKlines、premiumIndexKlines 都是77/77。可选 bookTicker 月包探针 2020-01 返回404，不做秒级盘口主策略。当前判断：FREE_SPOT_PERP_RAW_TRADE_DATA_AVAILABLE。如果继续，另起30号，只做 spot-perp aggTrades 成交流错位上限测试，funding/mark/index/premium 只做过滤器。

当前新增 30号 spot-perp aggTrades 样本上限测试：
30号：strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628，不是策略，不能交易，只拿四个关键样本月测试免费 spot/futures aggTrades 成交流错位有没有希望。样本月是 2023-07、2024-06、2025-08、2026-05。实际下载压缩包约2.586GB，处理成15分钟特征后删除原始zip；数据质量通过，11808根15分钟特征，spot/futures缺失15分钟行均为0。204个候选里，不要求交易次数时最好只是0%不交易；要求每月至少10单时，看答案oracle四个样本月全部亏，样本总收益 -25.33%，最差月 -12.67%，最少月交易39。当前判断：SPOT_PERP_AGGTRADE_SAMPLE_UPPER_BOUND_FAILS。不要下载全量约90GB继续做这条免费aggTrades lead-lag路线。

当前新增 31号多币种免费期货样本上限测试：
31号：strategy_31_multisymbol_free_futures_sample_upper_bound_20260628，不是策略，不能交易，只拿四个关键样本月测试多币种免费 USD-M futures 15m K线有没有比 BTC 单币更多机会。样本月是 2023-07、2024-06、2025-08、2026-05；币种为 BTC、ETH、SOL、BNB、HYPE、DOGE、XRP、ADA、AVAX、LINK。HYPE只覆盖2个样本月，DOGE覆盖3个，其余主要币覆盖4个。816个候选包括跨币种强弱轮动、单币动量/反转；18个静态候选四个样本月都为正。每月10单 oracle 四个样本月全正，最差月 +244.10%，最少月交易18，但这是看答案且收益极端，不能交易。当前判断：MULTISYMBOL_FREE_FUTURES_SAMPLE_UPPER_BOUND_HAS_SIGNAL。下一步如果继续，应另起32号做完整历史覆盖和严格逐月选择器，不要直接升级31号。

当前新增 32号 BTC 3m 2025到最新公开数据上限测试：
32号：strategy_32_btc_3m_2025_today_upper_bound_20260628，不是策略，不能交易，只测用户要求的 BTCUSDT 3m，从 2025-01 到当前公开可取数据。Binance USD-M futures 3m K线实际拿到 2025-01-01 00:00 UTC 到 2026-06-27 23:57 UTC，共260640根；重复、断档、补齐均为0；2026-06-28日包运行时未公开。348个 BTC 单币3m候选里，静态每月全正数量0。要求每月10单的月度看答案 oracle：2025 +51.33%，2026 YTD +227.11%，但仍有11个不盈利月份，最差月 -3.67%。当前判断：BTC_3M_2025_TODAY_UPPER_BOUND_FAILS。不要继续单币 BTC 3m 小规则；31号方向后来已由33号完整历史严格选择器检查，仍然失败。

当前新增 33号多币种完整历史严格选择器：
33号：strategy_33_multisymbol_free_futures_strict_selector_20260629，不是策略，不能交易，只把31号多币种样本上限扩到完整历史并做严格逐月选择器。Binance USD-M futures 15m 月包覆盖 BTC/ETH/SOL/BNB/DOGE/XRP/ADA/AVAX/LINK，2020-01-01 00:00 UTC 到 2026-05-31 23:45 UTC，共224928根主时间轴，重复/断档均为0；HYPE历史太短，不参与主选择。744个候选静态硬通过数量0。每月10单看答案 oracle 能过，2025 +17665719.09%、2026 YTD +4414.40%、不盈利月0、最少月交易14，但这是未来函数，不能交易。最好严格选择器 all_multisymbol：2023 +17.72%、2024 -21.17%、2025 -46.85%、2026 YTD -5.64%，不盈利月份21，最少月交易1。当前判断：MULTISYMBOL_ORACLE_HAS_PIECES_BUT_STRICT_SELECTOR_FAILS。31号样本信号扩到完整历史后仍然只能看答案选中，不能升级候选；不要继续手工扩这批多币种免费K线小规则。

当前新增 34号多币种失败根因审计：
34号：strategy_34_multisymbol_failure_root_cause_20260629，不是策略，不能交易，只复用33号结果拆失败根因，不新增交易规则、不重新下载数据。41个评估月里，每个月都有“每月10单且正收益”的看答案候选，但严格选择器有33个不达标月份；训练期没有硬通过候选的月份为41；当月oracle赢家在月初训练排序里的中位名次为222，排进前10的月份为0；跟随上月oracle赢家在2025为-99.9983%、2026 YTD为-96.7508%。失败拆分：严格选择器净亏损月份21，其中手续费把毛盈利打成净亏3个月，行情方向本身亏18个月，交易次数不足10次13个月。当前判断：ROOT_CAUSE_UNSTABLE_HINDSIGHT_SELECTION。拆根因能看清问题，但不能直接把这批规则修成可靠盈利策略；不要先加交易规则，若继续只能另起新编号测试真正不同的选择方法，并先做上限/泄漏审计。

当前新增 35号旧 BTC 3m 项目灵感复盘：
35号：strategy_35_old_btc_3m_inspiration_review_20260629，不是策略，不能交易，只按用户要求查看 `C:\Users\WHR\Documents\BTC多因子研究_20260626` 寻找灵感。旧项目保存的 BTC 3m 样本内组合为2025 +145.67%、2026 YTD +104.09%、18个月全正、最少月交易340，标签收益和独立3m价格重放差异0 bps；但同一组规则压到2024为-211.74%、正收益月份2/12，pre-2025锁参通过行数0，pre-2025 ML路由通过行数0。当前判断：OLD_BTC_3M_GIVES_FRAMEWORK_NOT_DEPLOYABLE_RULES。可以借多周期特征、funding/premium可用时间、事件池、资金约束和逐K盯市框架；不能照搬旧7条规则、阈值、10x毛暴露或样本内选择结果。

当前新增 36号多币种候选组合选择器审计：
36号：strategy_36_multisymbol_ensemble_selector_20260629，不是策略，不能交易，只借旧项目“多规则组合”思路做便宜检查；不下载新数据、不新增交易规则，只复用33号候选月度结果。每个月只用该月以前的数据选 top-k 候选等权组合，测试180组配置。严格通过配置数0；最好配置 top_k=50、lookback=24、min_pos_rate=0.45、score=pos_mean，2023 -14.30%、2024 -26.26%、2025 +0.06%、2026 YTD -22.93%，仍有24个不盈利月份，最小月交易546。当前判断：ENSEMBLE_SELECTOR_ON_33_CANDIDATES_FAILS。组合33号已有候选不能直接解决问题；不要继续调33号组合参数。

当前新增 37号 BTC 3m 多周期事件池审计：
37号：strategy_37_btc_3m_multitimeframe_event_pool_20260629，不是策略，不能交易，只借旧项目“多周期事件池”框架，不照搬旧7条规则、旧阈值或10x毛暴露。Binance USD-M futures BTCUSDT 3m月包覆盖2020-01到2026-05，共1124640根3分钟K线，重复/断档/缺失月份均为0。496个事件候选静态硬通过0；每月10单看答案oracle为2025 +503.35%、2026 YTD +157.89%，但仍有2024-04和2025-10两个不盈利月份；严格选择器最好range_events为2023 -2.17%、2024 -8.69%、2025 -6.49%、2026 YTD -7.45%，不盈利月份27，最少月交易2。当前判断：BTC_3M_MULTITIMEFRAME_EVENT_POOL_FAILS。不要继续小修这批BTC 3m多周期事件。

当前新增 38号强行过拟合 Alpha 挖掘审计：
38号：strategy_38_forced_overfit_alpha_mining_20260629，不是策略，不能交易，是按用户要求故意“看答案”挖线索。它不下载新数据、不新增交易规则，只复用33号和37号候选月度结果；每个月强行挑当月收益最高且至少10单的候选。合并看答案结果硬通过：2023 +5474067.32%、2024 +148266201.79%、2025 +17665719.09%、2026 YTD +4414.40%，不盈利月份0，最差月+25.64%，最少月交易14。但41/41个月赢家都来自33号，主要是多币种single_symbol的4倍动量/反转，常见 AVAX/SOL/LINK/XRP/DOGE/ADA。当月赢家在月初训练排序中位名次231，进前10月份0，跟随上月赢家在2025和2026都接近归零。当前判断：FORCED_OVERFIT_ALPHA_CLUES_NOT_YET_TRADEABLE。38号只说明历史赢家画像，不是可交易策略；若继续，另起39号研究无未来数据提前识别这些多币种赢家结构。

当前新增 39号 Alpha 规律挖掘：
39号：strategy_39_alpha_pattern_discovery_20260629，不是策略，不能交易，只把38号答案拆成规律并做简单不看未来搬运测试。发现的规律很清楚：赢家集中在近期活跃的山寨币，全部有符号赢家都是4倍，主要是single_symbol单币动量/反转，384根15m窗口最多；常见 AVAX、SOL、LINK、XRP、DOGE、ADA、ETH。上月涨跌幅绝对值排前5占72.5%，上月波动率排前5占72.5%。但把这个规律做成月初简单选择器后失败，最好 prev_abs_top2_reversal 为2023 +100.22%、2024 -40.50%、2025 0.00%、2026 YTD +18.01%，不能同时让2025和2026盈利。当前判断：ALPHA_PATTERN_FOUND_BUT_SIMPLE_SELECTOR_STILL_FAILS。下一步若继续，不要继续扩普通K线规则，应围绕这个规律找能提前识别“热币会延续还是反转”的新信号。

当前新增 40号多币种 Funding 提前识别审计：
40号：strategy_40_multisymbol_funding_alpha_selector_20260629，不是策略，不能交易，只按39号规律测试 funding 能不能提前识别。它下载 Binance 免费 USD-M futures fundingRate REST 历史，币种为 ETH/SOL/DOGE/XRP/ADA/AVAX/LINK，范围2022-12到2026-05；每币3834行、42个月、重复时间戳0、非8小时间隔0。赢家 funding 画像：40个有funding数据的赢家月里，上月funding绝对值排名中位数3.5，排前3比例50.0%，上月funding为正比例82.5%；动量赢家上月funding为正79.17%，反转赢家为正87.50%。最好不看未来测试 hot_abs_funding_abs_both：2023 +6662.64%、2024 -90.19%、2025 +203.32%、2026 YTD +18.01%，交易月份17，亏损交易月份6，最差交易月-76.35%。当前判断：FUNDING_SIGNAL_WEAK_NOT_TRADEABLE。Funding有一点拥挤度信息，但还不能达标；不要继续扩funding-only小规则。

当前新增 41号 BTC+HYPE 放宽门槛审计：
41号：strategy_41_btc_hype_relaxed_drawdown_20260629，不是策略，不能交易，只按用户要求把多币种缩到 BTCUSDT/HYPEUSDT，并去掉月月盈利、每月交易次数要求，只保留2025/2026 YTD都超过100%、最大回撤不超过50%。BTC 15m 覆盖2020-01-01到2026-05-31，共224928行；HYPE 15m 只从2025-06-01到2026-05-31，共35040行；主时间轴重复/断档为0。1008个候选静态固定参数通过数0；普通看答案 oracle 收益很高但最大回撤 -100%，不合格；回撤限制版看答案 oracle 2025 +4176.22%、2026 YTD +100.67%、最大回撤 -49.98%，能过放宽门槛但这是未来函数；严格不看未来选择器 2025 -16.27%、2026 YTD -35.55%、最大回撤 -40.04%。当前判断：BTC_HYPE_DRAWDOWN_CAPPED_ORACLE_ONLY_PASSES。41号说明历史上能用 BTC+HYPE 拼出放宽目标，但还没有能提前选择的可交易策略。

当前新增 42号 BTC+HYPE 状态可预测性审计：
42号：strategy_42_btc_hype_state_predictability_20260629，不是策略，不能交易，是按 GPT Pro 建议做的轻量前置信号审计。它只用 Binance 免费 REST 小数据：klines、fundingRate、premiumIndexKlines、markPriceKlines，范围2025-05到2026-05，评估月份2025-06到2026-05，不下载全量 aggTrades。它用月初已知状态给41号1008个BTC+HYPE候选打分，检查能不能把41号安全oracle赢家放进top10/top20/top50。结果：top10包含赢家16.67%，top20包含赢家33.33%，top50也只有33.33%。普通top20看答案上限 2025 +254.72%、2026 YTD +129.73%，但最大回撤 -99.999%，不合格；回撤过滤top20看答案上限 2025 +191.46%、2026 YTD +36.17%、最大回撤 -47.88%，2026不够；严格top1状态打分 2025 +29.45%、2026 YTD -32.95%、最大回撤 -99.999%。当前判断：BTC_HYPE_STATE_FEATURES_FAIL_FIRST_PASS。月初状态打分缩小候选池这条近路失败，不能升级。

当前新增 43号 BTC+HYPE 尾部事件归因审计：
43号：strategy_43_btc_hype_tail_event_attribution_20260629，不是策略，不能交易，是按 GPT Pro 第二轮建议做的尾部事件归因。它复用41号回撤限制版oracle逐K收益和42号BTC/HYPE 15m数据。极端事件定义：HYPE 4小时绝对涨跌幅不低于5%，或24小时绝对涨跌幅不低于12%，或HYPE相对BTC的4小时残差z值绝对值不低于2.5；事件窗口为前后各48小时。结果：原始事件K线占比6.20%，事件窗口占比79.05%；正收益log里90.44%落在事件窗口；事件窗口内净log +4.7580，窗口外净log -0.3059。当前判断：TAIL_EVENTS_DOMINATE_ORACLE_PNL。43号说明41号oracle利润确实和尾部事件相伴，但48小时窗口很宽，只是线索；下一步若继续，另起44号做事件后 action oracle 上限。

当前新增 44号 BTC+HYPE 尾部事件后动作 oracle：
44号：strategy_44_btc_hype_tail_event_action_oracle_20260629，不是策略，不能交易，只测试“事件发生后如果看答案选动作，理论上够不够”。事件检测只用过去已收盘K线，但动作选择看未来。最好配置：HYPE 4小时绝对涨跌4%、24小时绝对涨跌10%、HYPE/BTC 4小时残差z绝对值2.0、min_gap 16、单笔最大回撤过滤 -30%。结果硬通过放宽门槛：2025 +2349453758140.50%、2026 YTD +3774017741.59%、最大回撤 -31.94%、交易161笔、换手1330.0。动作分布：HYPE反转63笔、HYPE顺势62笔、BTC顺势14笔、HYPE/BTC相对价值反转12笔、BTC反转10笔。当前判断：TAIL_EVENT_ACTION_ORACLE_PASSES_RELAXED_GATE。44号证明历史上 HYPE 极端事件后确实有足够动作空间，但仍是未来函数，不能升级。

当前新增 45号 BTC+HYPE 尾部事件强过拟合策略：
45号：strategy_45_btc_hype_tail_event_fitted_policy_20260629，不是实盘策略，不能交易，是按用户要求强行过拟合。它用44号未来oracle动作当标签，拟合决策树，再在同一段历史评估。最好策略为 market_only 决策树，深度16、叶子100、训练准确率100%；结果和44号oracle完全对齐：2025 +2349453758140.50%、2026 YTD +3774017741.59%、最大回撤 -31.94%、交易161笔，过放宽门槛。当前判断：TAIL_EVENT_FITTED_POLICY_PASSES_IN_SAMPLE_RELAXED_GATE。45号说明“历史上能做出过线策略”，但这是同段强过拟合，不能实盘；可借的规律是 HYPE/BTC 极端事件后，HYPE顺势/反转切换最重要，HYPE/BTC残差、4天趋势、24小时涨跌、premium/funding 都有解释力。

当前新增 46号 BTC+HYPE 尾部事件严格走步验证：
46号：strategy_46_btc_hype_tail_event_walkforward_policy_20260629，不是实盘策略，不能交易，只检查45号规律能不能用过去事件训练后预测未来月份。每个月只用以前月份的44号oracle标签训练决策树，再测当前月；当前月标签不进当前月训练。最好严格走步为 market_plus_time、树深度5、最小叶子样本3：2025 +230.13%、2026 YTD +865.81%，但最大回撤 -84.48%、交易130笔，所以未过“最大回撤不超过50%”的放宽门槛。临时试过简单月内/总回撤刹车，0个通过：回撤压住时收益掉太多，收益够时回撤仍过大。当前判断：TAIL_EVENT_WALKFORWARD_POLICY_FAILS_RELAXED_GATE。46号说明45号是很强的历史过拟合线索，但还没变成稳定可交易 alpha。

当前新增 47号 BTC+HYPE 尾部事件因果风控覆盖审计：
47号：strategy_47_btc_hype_tail_event_causal_risk_overlay_20260629，不是实盘策略，不能交易，只在46号严格走步动作上加逐笔因果风控。事件识别只用已收盘K线；每个月只用以前月份训练树；逐笔风控只用交易已经发生的盈亏。扫描7560个配置，其中99个过放宽门槛。最好配置 market_plus_time、树深度5、最小叶子3、仓位缩放0.8、跟踪止损-10%、止盈20%：2025 +281.55%、2026 YTD +226.41%、最大回撤 -45.23%、交易130笔。更保守的 market_only 配置也过线：树深度6、最小叶子3、仓位缩放0.65、跟踪止损-8%、止盈50%，2025 +180.30%、2026 YTD +222.40%、最大回撤 -42.22%、交易124笔。当前判断：TAIL_EVENT_CAUSAL_RISK_OVERLAY_PASSES_RELAXED_GATE_IN_SAMPLE。47号比45/46更接近可执行逻辑，但风控参数仍在同一段历史里挑出来，不能直接实盘。

当前新增 49号 BTC+HYPE 冻结47号参数最新公开数据验证：
49号：strategy_49_btc_hype_frozen_47_latest_public_20260629，不是实盘策略，不能交易。48号编号本地已有“公开 Jesse 策略代理回测”未提交文件，所以 BTC+HYPE 冻结验证顺延到49号，避免混号。49号冻结47号最好配置和47号 market_only 配置，不在最新数据上重新扫描参数，只用 Binance USD-M futures 公共 REST 拉取 2026-05-01 到 2026-06-29 15:00 UTC 已收盘15分钟K线；BTC/HYPE 行数各5726、重复0、缺失0。结果：47号最好配置 2026-06 当前 -14.09%、最大回撤 -36.31%、交易13；47号 market_only 配置 -23.44%、最大回撤 -46.38%、交易13。当前判断：FROZEN_47_LATEST_PARTIAL_MONTH_FAILS。49号说明47号冻结后最新未调参数据失败，不能进入实盘或testnet。

当前新增 50号 2C 去掉月度锁利审计：
50号：strategy_50_2c_without_monthly_lock_20260629，不是实盘策略，不能交易，只按用户要求检查2C如果去掉月度锁利会不会更强。复用2C和1F逻辑，不改信号、不改手续费；测试两个版本：no_lock_keep_quota 去掉月度盈利后停手但保留未满10单前临时降仓，no_lock_no_quota 连临时降仓也去掉。结果都失败：no_lock_keep_quota 为2025 -99.97%、2026 -11.19%、最差月 -91.98%、亏损月13、最大回撤 -99.99%；no_lock_no_quota 为2025 -99.98%、2026 +131.38%、最差月 -89.48%、亏损月13、最大回撤接近 -100%。当前判断：MONTHLY_LOCK_IS_CRITICAL_FOR_2C。2C的月度锁利是核心保护，不要把“直接去掉2C月度锁利”作为升级方向。

当前新增 51号 2C 锁利前交易次数敏感性审计：
51号：strategy_51_2c_lock_min_orders_sensitivity_20260629，不是实盘策略，不能交易，只按用户质疑检查2C是否过度依赖“每月10笔后锁利”。保持2C大部分逻辑不变，只把允许月度锁利前的最低交易次数从10提到20、30、50、100，并加完全不锁利对照。只有10笔版本通过：2025 +359.10%、2026 +260.59%、最大回撤 -29.40%。20笔版本已失败：2025 -84.39%、2026 +460.62%、最差月 -87.98%、亏损月3、最大回撤 -95.46%。30/50/100笔和不锁利基本都是接近打穿。当前判断：TEN_TRADE_MONTHLY_LOCK_IS_A_FRAGILE_PART_OF_2C。用户判断成立，2C不是可以放心放开的强策略，而是高度依赖早锁利的历史候选。

当前新增 52号 2C 前10笔与10笔后归因：
52号：strategy_52_2c_first10_vs_after10_20260629，不是策略，不能交易，只复用50号 no_lock_keep_quota 的逐K回放，把每个月按订单数拆成前10笔交易区域和10笔之后区域。结果：前10笔区域2025 +183.19%、2026 +216.76%、亏损月份2；10笔之后区域2025 -99.99%、2026 -71.96%、亏损月份14、换手和暴露都很高。当前判断：POST_10_TRADES_EXPOSES_WEAK_RAW_SIGNAL。用户判断成立，10笔锁利不是策略优势，而是因为后续交易区间整体质量很差；2C原始信号不能长时间暴露。

当前新增 53号 2C 每月只做前N笔审计：
53号：strategy_53_2c_first_n_orders_only_20260630，不是实盘策略，不能交易，只检查52号“前10笔附近收益集中”是否完全依赖月度利润阈值。它复用2C逻辑，不看利润是否达到锁利阈值，只规定每个月最多做前5/10/15/20笔订单，到达后无条件空仓。原始月月盈利硬目标没有任何版本通过；但放宽到2025/2026收益都超100%、最大回撤不超过50%时，first_5_orders_then_flat 和 first_10_orders_then_flat 通过。first_10 为2025 +202.08%、2026 +261.07%、最差月 -7.91%、亏损月2、最大回撤 -29.25%。当前判断：FIRST_N_ONLY_HAS_RELAXED_SIGNAL_NOT_ORIGINAL_PASS。前段窗口不是纯利润阈值幻觉，但仍是事后发现的历史线索；不能直接升级。

当前新增 54号 2C 核心信号失败归因：
54号：strategy_54_2c_core_signal_failure_20260630，不是策略，不能交易，是按用户纠正“不只是开仓笔数，策略本身有问题”做的核心信号归因。它不再研究前N笔，而是直接检查旧2C/ret_state 64/100 核心方向信号。结果：核心信号1倍无手续费不锁利为2025 -4.90%、2026 +100.48%、最大回撤 -37.12%；1倍正常手续费为2025 -48.95%、2026 +50.61%、最大回撤 -76.58%；8倍正常手续费为2025 -99.54%、最大回撤接近 -100%；2C保护逻辑不锁利也接近打穿。单根K线方向预测1倍无手续费为2024 +14.26%、2025 -4.90%、2026 +100.48%，2025胜率49.53%、平均边际 -0.0143 bps。当前判断：CORE_RET_STATE_SIGNAL_NOT_GOOD_ENOUGH。用户判断成立，问题不是笔数，而是旧2C/ret_state核心信号不够好。

当前新增 55号 BTC/HYPE 尾部事件核心信号审计：
55号：strategy_55_btc_hype_tail_event_core_signal_20260630，不是实盘策略，不能交易，是按用户要求换核心信号后做的第一轮。它不再使用旧2C/ret_state，而是用 BTC/HYPE 尾部事件触发：HYPE 4小时/24小时大波动，或 HYPE 相对 BTC 4小时残差z极端；动作包括 HYPE/BTC 顺势、反转、配对顺势/反转，持仓16/32/64/96根15分钟K线，杠杆0.5/1/2，共144个候选。数据覆盖2025-06到2026-06-29 15:15 UTC。静态固定候选0个过放宽门槛，最好静态 loose_hype_reversal_hold64_lev2p0 为2025 +34.83%、2026 +104.15%、最大回撤 -71.97%；严格选择器2025 -11.64%、2026 -0.41%；普通看答案oracle收益很高但回撤 -91.10%；回撤限制版看答案oracle为2025 +1689.67%、2026 +1047.55%、最大回撤 -40.66%、亏损月份0，能过放宽门槛但看答案。当前判断：TAIL_EVENT_CORE_DRAWDOWN_CAPPED_ORACLE_ONLY_PASSES。尾部事件后有空间，但还不能提前选对动作，不能升级策略。

当前新增 56号 尾部事件亏损根因审计：
56号：strategy_56_tail_event_loss_root_cause_20260630，不是策略，不能交易，只复用55号结果深挖亏损根因，不新增候选、不调参数。结论：LOSS_ROOT_CAUSE_UNSTABLE_ACTION_SELECTION。根因不是没有事件机会，而是事件后正确动作每月切换太快；13个oracle月份用了10个不同候选，动作切换10次；oracle动作分布为HYPE顺势6、HYPE反转4、BTC顺势2、BTC反转1。严格选择器0个月选中同一候选，只2个月选中同一种动作，10个月错过正收益oracle；oracle赢家在训练期排序中位名次为98，12个月里0次排进前10；跟随上月oracle赢家只有5/12个月为正，简单收益求和+22.81%，而当月oracle简单收益求和+652.46%。当前判断：不能靠过去月度收益排名选动作；若继续，应研究事件当下状态特征是否能提前判断顺势/反转。

当前新增 57号 尾部事件状态动作可预测性审计：
57号：strategy_57_tail_event_state_action_predictability_20260630，不是策略，不能交易，只按56号建议检查“事件发生当下状态”能否提前判断尾部事件后该顺势还是反转。数据来自41号BTC/HYPE面板加49号最新公开K线，覆盖2025-06-01到2026-06-29 15:15 UTC，共37790根15分钟K线，重复/断档均为0。事件标签oracle看未来但能过放宽门槛：2025 +1528.72%、2026 +659.73%、最大回撤 -38.23%、交易268、亏损月0。严格走步完整标签预测失败：最好 market_only 树深6、叶子5，2025 -24.71%、2026 +73.97%、最大回撤 -41.65%。严格走步粗动作预测也失败：最好 market_only 树深6、叶子8、hold64、2倍，2025 +27.13%、2026 +9.63%、最大回撤 -35.36%。当前判断：EVENT_STATE_LABEL_ORACLE_PASSES_BUT_WALKFORWARD_FAILS。尾部事件后有历史空间，但当前简单状态特征/决策树不能提前稳定选动作；不要把57号升级策略，也不要继续只调树深、叶子、持仓时间。

后续如果继续开发，不能覆盖 0号策略，必须另起新编号、新文件夹。
这里只做研究和回测，不下实盘，不读取密钥，不启动 supervisor。下一步如果继续，不要继续免费K线小规则、单币 BTC 3m 小规则、旧 ret_state 64/100 家族、资金费率严格选择器、多币种免费K线小规则、免费 aggTrades lead-lag 路线，也不要照搬旧 BTC 3m 样本内规则、继续调33号组合参数、小修37号事件池、把38号、41号、44号、45号看答案/强过拟合线或47号同段挑参数线当实盘策略，也不要围绕旧2C/ret_state家族继续调锁利、调笔数、调小保护。57号后如果继续，应另起58号，看更贴近事件的提前信息：funding/premium 变化、BTC/HYPE 谁先动、事件后最初几根15分钟确认、成交量/taker 压力；不要继续只调57号决策树参数。

请用中文、通俗的话和我沟通。
```
