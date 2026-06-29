# 43号 BTC+HYPE 尾部事件归因审计

本文件用于定位 43号审计。它不是策略，不能交易，也不是固化版。

43号按 GPT Pro 第二轮建议，只做一个更窄的问题：

41号回撤限制版看答案 oracle 的利润，是不是主要集中在 BTC/HYPE 极端事件附近？

## 身份

- 审计编号：`strategy_43_btc_hype_tail_event_attribution_20260629`
- 来源脚本：`scripts/audit_strategy_43_btc_hype_tail_event_attribution_20260629.py`
- 结果目录：`artifacts/strategy_43_btc_hype_tail_event_attribution_20260629/`
- 主要结果：`artifacts/strategy_43_btc_hype_tail_event_attribution_20260629/summary.json`
- 报告：`artifacts/strategy_43_btc_hype_tail_event_attribution_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 复用 41号回撤限制版看答案 oracle 的逐K收益。
- 使用 42号下载的 BTC/HYPE 15m 小数据定义事件。

## 事件定义

只看 2025-06 到 2026-05。

极端事件满足任一条件：

- HYPE 4小时涨跌幅绝对值不低于 `5%`。
- HYPE 24小时涨跌幅绝对值不低于 `12%`。
- HYPE 相对 BTC 的 4小时残差 z 值绝对值不低于 `2.5`。

事件窗口为事件前后各 `48小时`。

## 结果

- 41号回撤限制版 oracle：2025 `+4176.22%`，2026 YTD `+100.67%`。
- 极端事件原始K线占比：`6.20%`。
- 事件窗口占全部15分钟K线比例：`79.05%`。
- 正收益 log 中落在事件窗口的比例：`90.44%`。
- 事件窗口内净 log 收益：`+4.7580`。
- 事件窗口外净 log 收益：`-0.3059`。

## 判断

43号结论是：`TAIL_EVENTS_DOMINATE_ORACLE_PNL`。

通俗说：

41号看答案曲线的利润，确实主要发生在 HYPE/BTC 极端波动附近；窗口外整体反而是亏的。

但要注意：这里用的是事件前后各48小时，窗口覆盖了约79%的K线，不是一个很窄的精准信号。因此 43号只能证明“尾部事件方向值得继续证伪”，不能证明已经有可交易策略。

下一步如果继续，只能另起44号：固定事件集，在事件发生后才选择 continuation / reversal / pair / cash，先做事件后 action oracle 上限；如果事件后上限都不够，就停止 BTC+HYPE 主线。
