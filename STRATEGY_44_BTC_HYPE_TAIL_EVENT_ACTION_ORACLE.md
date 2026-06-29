# 44号 BTC+HYPE 尾部事件后动作 oracle

本文件用于定位 44号审计。它不是策略，不能交易，也不是固化版。

44号接着 43号做一个更窄的问题：

极端事件已经发生以后，如果仍然“看答案”选择顺势、反转、配对或空仓，理论上还够不够通过用户放宽后的目标？

## 身份

- 审计编号：`strategy_44_btc_hype_tail_event_action_oracle_20260629`
- 来源脚本：`scripts/audit_strategy_44_btc_hype_tail_event_action_oracle_20260629.py`
- 结果目录：`artifacts/strategy_44_btc_hype_tail_event_action_oracle_20260629/`
- 主要结果：`artifacts/strategy_44_btc_hype_tail_event_action_oracle_20260629/summary.json`
- 报告：`artifacts/strategy_44_btc_hype_tail_event_action_oracle_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 使用 42号 BTC/HYPE 15m、funding、premium 小数据。
- 事件识别只用已经收盘的过去K线。
- 动作选择看了事件后的未来收益，所以是未来函数。

## 事件和动作

事件只看 `2025-06` 到 `2026-05`。

最好配置的事件条件：

- HYPE 4小时涨跌幅绝对值不低于 `4%`；或
- HYPE 24小时涨跌幅绝对值不低于 `10%`；或
- HYPE 相对 BTC 的 4小时残差 z 值绝对值不低于 `2.0`。

事件后可选动作：

- HYPE 顺势。
- HYPE 反转。
- BTC 顺势。
- BTC 反转。
- HYPE/BTC 相对价值反转。
- 空仓。

持仓长度测试 `16/32/64/96/192` 根15分钟K线，杠杆测试 `1/2/3/4`。

## 结果

最好 action oracle：

- 2025：`+2349453758140.50%`
- 2026 YTD：`+3774017741.59%`
- 最大回撤：`-31.94%`
- 事件数：`4187`
- 交易数：`161`
- 换手：`1330.0`
- 是否过放宽门槛：`true`

动作分布：

- HYPE 反转：`63` 笔
- HYPE 顺势：`62` 笔
- BTC 顺势：`14` 笔
- HYPE/BTC 相对价值反转：`12` 笔
- BTC 反转：`10` 笔

## 判断

44号结论是：`TAIL_EVENT_ACTION_ORACLE_PASSES_RELAXED_GATE`。

通俗说：

BTC+HYPE 在 HYPE 极端事件之后，历史上确实有足够大的“可赚钱动作”。但 44号是在事件发生以后看未来，挑了最赚钱的动作，所以不能交易。

它给出的线索是：真正该研究的不是月初选一个固定候选，而是“事件发生后，判断顺势还是反转、拿多久、用几倍”。
