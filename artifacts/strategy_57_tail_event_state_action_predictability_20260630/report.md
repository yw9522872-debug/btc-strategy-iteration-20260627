# Strategy 57：尾部事件状态动作可预测性审计

- 这是研究审计，不是实盘策略。
- 目标：用事件发生当时已经知道的状态，预测该顺势还是反转。

## 标签oracle

- 2025: `1528.72%`
- 2026: `659.73%`
- 最大回撤: `-38.23%`
- 交易数: `268`
- hard_pass_relaxed: `True`

## 最好严格走步策略

- feature_set: `market_only`
- max_depth: `6`
- min_samples_leaf: `5`
- 2025: `-24.71%`
- 2026: `73.97%`
- 最大回撤: `-41.65%`
- 亏损月: `5`
- 交易数: `248`
- hard_pass_relaxed: `False`

## 最好粗动作走步策略

- feature_set: `market_only`
- max_depth: `6`
- min_samples_leaf: `8`
- hold_bars: `64`
- leverage: `2.0`
- 2025: `27.13%`
- 2026: `9.63%`
- 最大回撤: `-35.36%`
- 亏损月: `8`
- 交易数: `267`
- hard_pass_relaxed: `False`

## 结论

- `EVENT_STATE_LABEL_ORACLE_PASSES_BUT_WALKFORWARD_FAILS`
- 事件标签oracle有空间，但当前简单状态特征/决策树无论预测完整标签还是粗动作，都不能稳定预测未来月份动作。
