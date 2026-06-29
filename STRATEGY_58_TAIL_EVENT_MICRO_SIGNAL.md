# Strategy 58：尾部事件微观提前信息审计

本文件记录 58 号研究结果。

这不是实盘策略，不能交易。它只回答一个问题：

> 比 57 号更贴近事件本身的信息，能不能提前判断尾部事件后该顺势还是反转？

## 背景

57号已经确认：

- 事件后看答案 oracle 很强。
- 但只用简单状态特征，严格走步预测动作失败。

58号继续往事件本身靠近，测试这些信息：

- funding 当前水平和变化；
- premium 当前水平和变化；
- BTC/HYPE 谁先动；
- 事件后第 `1/2/4` 根15分钟K线确认；
- 成交量放大；
- taker 主动买卖压力。

事件后确认K线只在收盘后使用，入场也延后，所以不算偷看。

## 数据

数据来源：

- `artifacts/strategy_42_btc_hype_state_predictability_20260629/btc_hype_15m_klines_rest_2025_05_2026_05.csv.gz`
- `artifacts/strategy_42_btc_hype_state_predictability_20260629/btc_hype_funding_rate_2025_05_2026_05.csv`
- `artifacts/strategy_42_btc_hype_state_predictability_20260629/btc_hype_premiumIndexKlines_15m_2025_05_2026_05.csv.gz`

主审计范围：

- `2025-06` 到 `2026-05`
- 15分钟K线行数：`35168`
- 重复时间戳：`0`
- 非15分钟断档：`0`

注意：

49号最新 2026-06 K线只有 close，没有成交量/taker 列。  
所以58号主审计停在 `2026-05`，避免把不完整数据硬混进去。

手续费：

- 单边 `0.1%`
- 开平合计 `0.2%`

## 事件定义

仍沿用 57 号事件：

- HYPE 4小时绝对涨跌不低于 `4%`
- 或 HYPE 24小时绝对涨跌不低于 `10%`
- 或 HYPE 相对 BTC 的4小时残差 z 值绝对值不低于 `2.0`

确认延迟测试：

- `0` 根15分钟K线
- `1` 根15分钟K线
- `2` 根15分钟K线
- `4` 根15分钟K线

## 看答案 oracle

最好确认延迟 oracle：

| 项目 | 结果 |
|---|---:|
| confirm_bars | `0` |
| 2025收益 | `+72596889.40%` |
| 2026收益 | `+2176924.83%` |
| 最大回撤 | `-31.21%` |
| 亏损月份 | `0` |
| 交易数 | `247` |
| 是否过放宽门槛 | `True` |

这说明：

> 尾部事件后仍然有很强的历史动作空间。

但这个 oracle 是看未来选动作，不能交易。

## 严格走步结果

共扫描 `1620` 个严格配置。

通过放宽门槛的配置数：

| 项目 | 数量 |
|---|---:|
| 严格配置总数 | `1620` |
| 通过数 | `0` |

最好严格走步动作策略：

| 项目 | 结果 |
|---|---:|
| confirm_bars | `2` |
| feature_set | `market_only` |
| max_depth | `4` |
| min_samples_leaf | `3` |
| hold_bars | `96` |
| leverage | `2.0` |
| 2025收益 | `+144.16%` |
| 2026收益 | `+151.71%` |
| 最大回撤 | `-65.31%` |
| 亏损月份 | `4` |
| 交易数 | `173` |
| 是否过放宽门槛 | `False` |

这个配置收益够，但回撤太大。

## 最接近通过的低回撤配置

如果先要求最大回撤不超过 `50%`，最好的配置是：

| 项目 | 结果 |
|---|---:|
| confirm_bars | `1` |
| feature_set | `event_micro_plus_time` |
| max_depth | `3` |
| min_samples_leaf | `3` |
| hold_bars | `96` |
| leverage | `2.0` |
| 2025收益 | `+88.56%` |
| 2026收益 | `+368.95%` |
| 最大回撤 | `-47.83%` |
| 亏损月份 | `4` |

这个配置回撤合格，但 2025 没到 `100%`。

这很重要：

> 微观信息确实有一点帮助，能把回撤压下来。  
> 但它还不能同时满足“2025/2026都超过100%”和“最大回撤不超过50%”。

## 核心结论

`EVENT_MICRO_ORACLE_PASSES_BUT_WALKFORWARD_FAILS`

通俗说：

> 事件后仍然有钱可以赚。  
> 事件后等1到2根K线、看 funding/premium、看谁先动、看成交量/taker，确实比纯状态更接近答案。  
> 但严格不看未来时，仍然没有做出合格策略。

58号不能升级为策略。

## 后续判断

不要继续只调这些东西：

- 决策树深度；
- 叶子样本数；
- 持仓 `32/64/96`；
- 杠杆 `0.5/1/2`；
- 确认 `0/1/2/4` 根K线。

这些已经扫过，结果是 `0/1620` 通过。

如果继续，下一步更适合做 59 号：

> 用58号最接近的低回撤配置做失败月份归因，看看 2025 收益差在哪里、回撤来自哪几次事件。

如果失败集中在少数事件，再考虑极简的因果风控；如果失败分散，就说明这条尾部事件动作选择路线也接近停线。

## 文件

- 脚本：`scripts/audit_strategy_58_tail_event_micro_signal_20260630.py`
- 摘要：`artifacts/strategy_58_tail_event_micro_signal_20260630/summary.json`
- 报告：`artifacts/strategy_58_tail_event_micro_signal_20260630/report.md`
- oracle标签：`artifacts/strategy_58_tail_event_micro_signal_20260630/oracle_event_labels.csv`
- 确认延迟oracle：`artifacts/strategy_58_tail_event_micro_signal_20260630/oracle_by_confirm.csv`
- 严格动作扫描：`artifacts/strategy_58_tail_event_micro_signal_20260630/action_policy_scan.csv`
- 最好严格月度：`artifacts/strategy_58_tail_event_micro_signal_20260630/best_action_policy_monthly.csv`
- 最好严格交易：`artifacts/strategy_58_tail_event_micro_signal_20260630/best_action_policy_trades.csv`
