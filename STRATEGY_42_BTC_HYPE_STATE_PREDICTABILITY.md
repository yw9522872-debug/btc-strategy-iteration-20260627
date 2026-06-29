# 42号 BTC+HYPE 状态可预测性审计

本文件用于定位 42号审计。它不是实盘策略，不能交易，也不是固化版。

42号按 GPT Pro 建议做第一步：检查 41号里“看答案才能选中”的 BTC+HYPE 赢家，能不能被提前可见的状态特征缩小范围。

## 身份

- 审计编号：`strategy_42_btc_hype_state_predictability_20260629`
- 来源脚本：`scripts/audit_strategy_42_btc_hype_state_predictability_20260629.py`
- 结果目录：`artifacts/strategy_42_btc_hype_state_predictability_20260629/`
- 主要结果：`artifacts/strategy_42_btc_hype_state_predictability_20260629/summary.json`
- 报告：`artifacts/strategy_42_btc_hype_state_predictability_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 使用 Binance 免费公开 REST 小数据。
- 数据范围：`2025-05-01` 到 `2026-05-31`。
- 交易月份只评估 `2025-06` 到 `2026-05`，因为 HYPE 免费15m历史从 2025-06 开始完整。

## 使用的数据

- `/fapi/v1/klines`
- `/fapi/v1/fundingRate`
- `/fapi/v1/premiumIndexKlines`
- `/fapi/v1/markPriceKlines`

没有下载全量 `aggTrades`，也没有使用官方只保留近30天的多空比/持仓量接口。

## 测试方法

42号没有直接再赌月初 top1，而是先做一个“前置信号保留能力”审计：

- 对每个月开始前可见的数据，计算 BTC/HYPE 的涨跌幅、波动、成交额、taker 失衡、funding、premium、mark price 状态。
- 用这些状态给 41号的 1008 个 BTC+HYPE 候选打分。
- 检查 41号“安全看答案赢家”能不能落进 top10/top20/top50。
- 再检查 top20 内看答案上限是否还能满足 2025/2026 和最大回撤要求。

## 结果

- top10 包含 41号安全 oracle 赢家比例：`16.67%`
- top20 包含 41号安全 oracle 赢家比例：`33.33%`
- top50 包含 41号安全 oracle 赢家比例：`33.33%`

普通 top20 看答案上限：

- 2025：`+254.72%`
- 2026 YTD：`+129.73%`
- 最大回撤：`-99.999%`
- 判断：收益够，但回撤爆掉，不合格。

回撤过滤 top20 看答案上限：

- 2025：`+191.46%`
- 2026 YTD：`+36.17%`
- 最大回撤：`-47.88%`
- 判断：回撤合格，但 2026 不够，不合格。

严格 top1 状态打分：

- 2025：`+29.45%`
- 2026 YTD：`-32.95%`
- 最大回撤：`-99.999%`
- 判断：失败。

## 判断

42号结论是：`BTC_HYPE_STATE_FEATURES_FAIL_FIRST_PASS`。

通俗说：

这批最容易拿到的提前状态特征，包括 funding、premium、mark、15m 成交和 taker 信息，暂时不能把 41号看答案赢家稳定提前找出来。

这不是证明 BTC+HYPE 永远没机会，而是说明“月初用这些状态给 1008 个候选打分”的近路失败了。下一步如果继续，只能测试更细的严格动态门控；如果动态门控也失败，就应该停止 BTC+HYPE 这条主线，改成更现实的影子跟踪/低年化验证。
