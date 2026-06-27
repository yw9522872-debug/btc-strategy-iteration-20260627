# GPT Pro 复核问题：15-21号以后是否该继续

本地路径：`C:\Users\WHR\Documents\策略迭代`

GitHub 仓库：`https://github.com/yw9522872-debug/btc-strategy-iteration-20260627`

本线程目标：复核 BTC 15m 策略研究中 15号到21号的负面结果，判断下一步是否还值得继续找新策略族，还是应先调整硬目标。

请先阅读：

1. `GPT_PRO_REVIEW_BRIEF.md`
2. `AGENTS.md`
3. `STRATEGY_15_UNIFIED_DATA_BASELINE.md`
4. `STRATEGY_16_NEW_FAMILY_PROBE.md`
5. `STRATEGY_17_SIMPLE_FAMILY_UPPER_BOUND.md`
6. `STRATEGY_18_UPPER_BOUND_FAILURE_REVIEW.md`
7. `STRATEGY_19_CALENDAR_SEASONALITY_PROBE.md`
8. `STRATEGY_20_OHLC_STRUCTURE_UPPER_BOUND.md`
9. `STRATEGY_21_VOLUME_UPPER_BOUND.md`
10. `artifacts/strategy_15_unified_data_baseline_20260627/summary.json`
11. `artifacts/strategy_16_new_family_probe_20260627/summary.json`
12. `artifacts/strategy_17_simple_family_upper_bound_20260627/summary.json`
13. `artifacts/strategy_18_upper_bound_failure_review_20260627/summary.json`
14. `artifacts/strategy_19_calendar_seasonality_probe_20260627/summary.json`
15. `artifacts/strategy_20_ohlc_structure_upper_bound_20260627/summary.json`
16. `artifacts/strategy_21_volume_upper_bound_20260627/summary.json`

关键背景：

- 0号策略已永久保存，只能当历史基准，不能覆盖。
- 14号已经把旧 `ret_state 64/100` 家族判为 `STOP_FAMILY`。
- 15号确认 USD-M futures 15m 数据底座可用。
- 16号简单价格规则失败。
- 17号对16号做“看答案”上限仍失败。
- 18号说明失败月里很多时候最好选择是空仓，一旦要求每月10单就亏。
- 19号日历/星期/小时季节性失败。
- 20号 OHLC K线实体/影线/振幅/波动结构上限失败。
- 21号成交量/taker 字段上限失败。

硬目标：

- 2025 年收益率大于 100%。
- 2026 年收益率大于 100%。
- 不能使用未来函数。
- 开平合计手续费按 0.2%。
- 历史回测每个月都盈利。
- 每个月交易次数最低 10 次。

请重点回答：

1. 按 15-21 的结果看，继续寻找“简单规则策略族”是否已经不值得？
2. 当前硬目标“每月盈利 + 每月最少10单 + 年收益100%”是否过严，是否应先调整研究目标？
3. 如果还要做 22号，最值得做的一个方向是什么？请只给一个方向，并说明为什么它和 16-21 不重复。
4. 如果建议停止，请说明停止理由，以及后续怎样保留 2C/0号作为历史基准。

要求：

- 只建议能做严格无未来函数回测的方法。
- 不要泛泛讲风险控制，请给具体可执行的下一步。
- 如果建议 ML，请写清楚训练窗口、标签可用时间、阈值选择和泄漏检查。
- 如果认为硬目标不可行，请建议一个能证明瓶颈的上限测试。
