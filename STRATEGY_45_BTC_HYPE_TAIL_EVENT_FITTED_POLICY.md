# 45号 BTC+HYPE 尾部事件强过拟合策略

本文件用于定位 45号审计。它不是实盘策略，不能交易，也不是固化版。

45号按用户要求强行过拟合：用 44号未来 oracle 的赚钱动作当老师，把它拟合成一个固定决策树策略，看看历史上能不能过放宽门槛，并从中找规律。

## 身份

- 审计编号：`strategy_45_btc_hype_tail_event_fitted_policy_20260629`
- 来源脚本：`scripts/audit_strategy_45_btc_hype_tail_event_fitted_policy_20260629.py`
- 结果目录：`artifacts/strategy_45_btc_hype_tail_event_fitted_policy_20260629/`
- 主要结果：`artifacts/strategy_45_btc_hype_tail_event_fitted_policy_20260629/summary.json`
- 报告：`artifacts/strategy_45_btc_hype_tail_event_fitted_policy_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 交易成本仍按开平合计 `0.2%`，代码里单边 `0.001`。
- 事件识别只用过去已经收盘的K线。
- 决策树训练标签来自 44号未来 oracle，同一段历史训练、同一段历史评估，所以是强过拟合。

## 使用的特征

决策树只用事件发生时已经可见的市场状态：

- HYPE/BTC 的 4小时、24小时、4天收益。
- HYPE 相对 BTC 的 4小时残差 z 值。
- HYPE 溢价 `premium96`。
- HYPE 7天 funding 汇总 `fund672`。
- 极端冲击方向、长期趋势是否同向、拥挤状态是否同向。

最好结果使用 `market_only` 特征，没有加入日历时间字段；但树深度很深，仍然是在同段样本内记忆。

## 结果

最好拟合策略：

- 策略类型：`decision_tree`
- 特征集：`market_only`
- 树深度：`16`
- 叶子数：`100`
- 训练准确率：`100%`
- 2025：`+2349453758140.50%`
- 2026 YTD：`+3774017741.59%`
- 最大回撤：`-31.94%`
- 交易数：`161`
- 换手：`1330.0`
- 是否过放宽门槛：`true`

45号最好策略和 44号 oracle 的 `161` 笔事件完全对齐，所以收益曲线相同。

## 找到的规律

最重要的特征大致是：

- HYPE 相对 BTC 的短期残差。
- HYPE/BTC 的 4天趋势。
- HYPE/BTC 的 24小时涨跌。
- HYPE 的 4小时冲击。
- 溢价和 funding。

动作上主要集中在：

- HYPE 反转：`63` 笔
- HYPE 顺势：`62` 笔
- BTC 顺势：`14` 笔
- HYPE/BTC 相对价值反转：`12` 笔
- BTC 反转：`10` 笔

通俗说：历史利润主要来自 HYPE 极端波动后的顺势和反转切换，持仓经常接近 `192` 根15分钟K线，也就是约2天。不是“永远追涨”或“永远抄底”。

## 判断

45号结论是：`TAIL_EVENT_FITTED_POLICY_PASSES_IN_SAMPLE_RELAXED_GATE`。

通俗说：

我们已经强行做出了一个历史上满足放宽门槛的 BTC+HYPE 策略。但它是同段历史强过拟合出来的，不能说未来也能赚钱。

下一步如果继续，不能直接上实盘，也不能把45号升级。应该另起46号做严格走步：每个月只用以前发生过的 44号风格事件训练树，再测下个月。只有 46号也能接近过线，45号挖到的 alpha 才算有一点真实希望。
