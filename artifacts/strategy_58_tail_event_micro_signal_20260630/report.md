# Strategy 58：尾部事件微观提前信息审计

- 这是研究审计，不是实盘策略。
- 主数据到 2026-05，因为 2026-06 最新K线缺成交量/taker列。
- 事件后确认K线只在收盘后使用，入场也延后，不算偷看。

## 最好确认延迟oracle

- confirm_bars: `0`
- 2025: `72596889.40%`
- 2026: `2176924.83%`
- 最大回撤: `-31.21%`
- 交易数: `247`
- hard_pass_relaxed: `True`

## 最好严格走步动作策略

- confirm_bars: `2`
- feature_set: `market_only`
- max_depth: `4`
- min_samples_leaf: `3`
- hold_bars: `96`
- leverage: `2.0`
- 2025: `144.16%`
- 2026: `151.71%`
- 最大回撤: `-65.31%`
- 亏损月: `4`
- 交易数: `173`
- hard_pass_relaxed: `False`

## 结论

- `EVENT_MICRO_ORACLE_PASSES_BUT_WALKFORWARD_FAILS`
- 确认K、funding、premium、lead-lag、成交量/taker 的看答案空间存在，但严格走步动作选择仍失败。
