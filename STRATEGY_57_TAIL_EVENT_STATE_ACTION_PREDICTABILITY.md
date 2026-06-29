# Strategy 57：尾部事件状态动作可预测性审计

本文件记录 57 号研究结果。

这不是实盘策略，不能交易。它只回答一个问题：

> HYPE/BTC 尾部事件发生时，能不能只用当时已经知道的状态，提前判断应该顺势还是反转？

## 背景

55号说明：BTC/HYPE 尾部事件后有利润空间，但固定规则和严格选择器都失败。

56号继续拆原因，发现真正的问题不是没有事件，而是事件后正确动作切换太快：

- 有时 HYPE 顺势。
- 有时 HYPE 反转。
- 有时 BTC 顺势。
- 有时 BTC 反转。

所以57号不再用“过去哪个候选赚钱就选哪个”，而是检查事件发生当下的状态特征有没有预测力。

## 数据

数据来源：

- `artifacts/strategy_41_btc_hype_relaxed_drawdown_20260629/btc_hype_close_panel_15m_2020_2026_05.csv.gz`
- `artifacts/strategy_49_btc_hype_frozen_47_latest_public_20260629/latest_klines.csv.gz`

评估范围：

- `2025-06-01 00:00 UTC` 到 `2026-06-29 15:15 UTC`
- 共 `37790` 根15分钟K线
- 重复时间戳：`0`
- 非15分钟断档：`0`

手续费：

- 单边 `0.1%`
- 开平合计 `0.2%`

## 事件定义

事件只用过去已收盘K线识别：

- HYPE 4小时绝对涨跌不低于 `4%`
- 或 HYPE 24小时绝对涨跌不低于 `10%`
- 或 HYPE 相对 BTC 的4小时残差 z 值绝对值不低于 `2.0`

事件最小间隔：

- `16` 根15分钟K线

## 标签说明

57号先用未来收益给每个事件打一个 oracle 标签，找出事后最好的动作。

这一步标签本身看了未来，所以不能交易。

但后面的严格走步训练遵守规则：

> 测某个月时，只能用这个月以前的事件标签训练，当前月标签不能进入当前月训练。

## 标签oracle结果

这个结果代表“如果事件后动作能看答案，理论空间有多大”。

| 项目 | 结果 |
|---|---:|
| 事件标签数 | `268` |
| 不同完整标签数 | `25` |
| 2025收益 | `+1528.72%` |
| 2026收益 | `+659.73%` |
| 最大回撤 | `-38.23%` |
| 亏损月份 | `0` |
| 交易数 | `268` |
| 是否过放宽门槛 | `True` |

动作分布：

| 动作 | 次数 |
|---|---:|
| BTC 反转 | `119` |
| BTC 顺势 | `117` |
| HYPE 顺势 | `16` |
| HYPE 反转 | `16` |

这说明尾部事件后确实有历史空间。

## 最好完整标签严格走步

完整标签的意思是同时预测：

- 做哪个币
- 顺势还是反转
- 持仓多久
- 杠杆多少

最好结果：

| 项目 | 结果 |
|---|---:|
| feature_set | `market_only` |
| max_depth | `6` |
| min_samples_leaf | `5` |
| 2025收益 | `-24.71%` |
| 2026收益 | `+73.97%` |
| 最大回撤 | `-41.65%` |
| 亏损月份 | `5` |
| 交易数 | `248` |
| 是否过放宽门槛 | `False` |

完整标签太难预测，没有通过。

## 最好粗动作严格走步

粗动作的意思是只预测：

- BTC 顺势
- BTC 反转
- HYPE 顺势
- HYPE 反转

持仓和杠杆另外固定扫描。

最好结果：

| 项目 | 结果 |
|---|---:|
| feature_set | `market_only` |
| max_depth | `6` |
| min_samples_leaf | `8` |
| hold_bars | `64` |
| leverage | `2.0` |
| 2025收益 | `+27.13%` |
| 2026收益 | `+9.63%` |
| 最大回撤 | `-35.36%` |
| 亏损月份 | `8` |
| 交易数 | `267` |
| 是否过放宽门槛 | `False` |

即使只预测粗动作，也没有通过。

## 核心结论

`EVENT_STATE_LABEL_ORACLE_PASSES_BUT_WALKFORWARD_FAILS`

通俗说：

> 尾部事件后确实有钱可以赚。  
> 但我们现在这些简单状态特征，还不能提前判断“下一次事件后该顺势还是反转”。  
> 所以57号不能升级为策略。

## 该学到什么

57号没有白做。它把问题缩得更小了：

1. 机会集中在尾部事件后。
2. 靠月度历史收益排名选动作不行。
3. 靠当前这些K线状态特征和简单决策树也不行。
4. 后续如果继续找 alpha，需要更贴近事件本身的提前信息。

可能的下一步不是继续调树深、调叶子、调持仓时间，而是另起58号检查更细的事件前后信息：

- funding/premium 在事件前后的变化；
- 事件前 HYPE 和 BTC 谁先动；
- 事件后最初几根15分钟K线是否能作为二次确认；
- 或者用可获得的成交量/taker 成交方向检查事件后的真实买卖压力。

仍然必须严格不看未来。

## 文件

- 脚本：`scripts/audit_strategy_57_tail_event_state_action_predictability_20260630.py`
- 摘要：`artifacts/strategy_57_tail_event_state_action_predictability_20260630/summary.json`
- 报告：`artifacts/strategy_57_tail_event_state_action_predictability_20260630/report.md`
- 事件标签：`artifacts/strategy_57_tail_event_state_action_predictability_20260630/oracle_event_labels.csv`
- 完整标签走步扫描：`artifacts/strategy_57_tail_event_state_action_predictability_20260630/walkforward_policy_scan.csv`
- 粗动作走步扫描：`artifacts/strategy_57_tail_event_state_action_predictability_20260630/walkforward_action_only_scan.csv`
