# 46号 BTC+HYPE 尾部事件严格走步验证

本文件用于定位 46号审计。它不是实盘策略，不能交易，也不是固化版。

46号接着 45号做严格检查：

每个月只用以前月份已经发生过的 44号 oracle 标签来训练决策树，然后测当前月份。当前月份的答案不能参与当前月份训练。

## 身份

- 审计编号：`strategy_46_btc_hype_tail_event_walkforward_policy_20260629`
- 来源脚本：`scripts/audit_strategy_46_btc_hype_tail_event_walkforward_policy_20260629.py`
- 结果目录：`artifacts/strategy_46_btc_hype_tail_event_walkforward_policy_20260629/`
- 主要结果：`artifacts/strategy_46_btc_hype_tail_event_walkforward_policy_20260629/summary.json`
- 报告：`artifacts/strategy_46_btc_hype_tail_event_walkforward_policy_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 事件识别只用过去已经收盘的K线。
- 当前月训练不使用当前月标签。
- 训练标签仍来自 44号 oracle，只是在标签月份过去以后才能用于以后月份。

## 测试方法

- 沿用 44/45号的 BTC+HYPE 尾部事件定义。
- 每个月滚动训练决策树。
- 测试 `market_only` 和 `market_plus_time` 两组特征。
- 扫描树深度 `2/3/4/5/6/8/12/unlimited`。
- 扫描最小叶子样本 `1/2/3/5`。

## 结果

最好严格走步结果：

- 特征集：`market_plus_time`
- 树深度：`5`
- 最小叶子样本：`3`
- 2025：`+230.13%`
- 2026 YTD：`+865.81%`
- 最大回撤：`-84.48%`
- 交易数：`130`
- 换手：`1052.0`
- 是否过放宽门槛：`false`

收益够，但最大回撤远远超过 `50%` 限制，所以不合格。

另外临时试过简单月内/总回撤刹车：回撤压到 50%以内时，收益明显掉下去；收益保住时，回撤仍然太大。因此没有把刹车另升为新策略。

## 判断

46号结论是：`TAIL_EVENT_WALKFORWARD_POLICY_FAILS_RELAXED_GATE`。

通俗说：

45号已经强行做出了历史上过线的策略，也给出了 HYPE 极端事件后的顺势/反转规律。但把这个规律拿去做严格未来验证，目前还过不了最大回撤门槛。

所以 45号可以当“寻找 alpha 的线索”，不能当成已经验证过的 alpha。
