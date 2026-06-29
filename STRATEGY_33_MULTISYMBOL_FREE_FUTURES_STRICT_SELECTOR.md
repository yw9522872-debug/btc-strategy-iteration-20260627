# 33号多币种完整历史严格选择器

本文件用于定位 33号审计。它不是策略，不能交易，也不是固化版。

33号只做一件事：

把 31号“四个月多币种看答案样本”扩到完整历史，并检查严格不看未来的逐月选择器能不能提前选中候选。

## 身份

- 审计编号：`strategy_33_multisymbol_free_futures_strict_selector_20260629`
- 来源脚本：`scripts/audit_strategy_33_multisymbol_free_futures_strict_selector_20260629.py`
- 结果目录：`artifacts/strategy_33_multisymbol_free_futures_strict_selector_20260629/`
- 主要结果：`artifacts/strategy_33_multisymbol_free_futures_strict_selector_20260629/summary.json`
- 报告：`artifacts/strategy_33_multisymbol_free_futures_strict_selector_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 数据使用 Binance 免费 USD-M futures 15m 月包。
- 主币种：`BTCUSDT`、`ETHUSDT`、`SOLUSDT`、`BNBUSDT`、`DOGEUSDT`、`XRPUSDT`、`ADAUSDT`、`AVAXUSDT`、`LINKUSDT`。
- `HYPEUSDT` 历史太短，只作说明，不参与候选选择。
- 数据范围：`2020-01-01 00:00 UTC` 到 `2026-05-31 23:45 UTC`。
- 手续费沿用旧口径：开平合计 `0.2%`。
- 信号只用已收盘15分钟K线，下一根15分钟K线才吃收益。
- 严格选择器每个月只用该月之前的数据选候选。

## 数据质量

- 15分钟行数：`224928`
- 覆盖月份：`77`
- 重复时间戳：`0`
- 15分钟断档：`0`
- 主币种从各自上市月到 `2026-05` 没有中间缺月。

## 结果

33号结论是：`MULTISYMBOL_ORACLE_HAS_PIECES_BUT_STRICT_SELECTOR_FAILS`。

通俗说：

多币种完整历史里，“看答案”仍然有很多赚钱片段；但只用过去数据提前选择时，选不准。

关键结果：

- 候选数量：`744`
- 静态事后硬通过数量：`0`
- 每月10单看答案 oracle：通过硬目标，但它看答案，不能交易。
- 最好严格选择器：`all_multisymbol`
- 最好严格选择器 2023：`+17.72%`
- 最好严格选择器 2024：`-21.17%`
- 最好严格选择器 2025：`-46.85%`
- 最好严格选择器 2026 YTD：`-5.64%`
- 不盈利月份：`21`
- 最差月：`-21.89%`
- 最少月交易：`1`
- 最大回撤：`-69.49%`

## 判断

33号不能升级为候选策略。

31号样本里看到的强信号，扩到完整历史后证明仍然是“看答案才能选中”。真正卡点还是：当月开始前，不能稳定选中正确币种和正确规则。

后续不要继续手工扩这批多币种免费K线小规则。除非换真正不同的新数据，或者先把目标改成更现实的影子跟踪/低年化验证。
