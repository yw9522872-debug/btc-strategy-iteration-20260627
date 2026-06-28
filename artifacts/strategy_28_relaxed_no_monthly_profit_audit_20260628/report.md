# 28 Relaxed No-Monthly-Profit Audit

This is research only. It is not a live-trading strategy.

## Question

What happens if the monthly-profitable-month requirement is removed?

## Best strict exact result

- Selector: `loss_control_no_positive_gate`
- 2025 return: `-5.28%`
- 2026 YTD return: `-0.35%`
- Losing eval months: `6`
- Worst month: `-39.60%`
- Max drawdown: `-58.39%`

## Decision

- Verdict: `NO_STRICT_RELAXED_UPGRADE`
- Reason: 去掉每月盈利要求后，严格不看未来的选择器仍没有做出2025和2026 YTD同时够强的结果。
- Next step: 不要继续在这批免费K线规则里硬挤；若继续研究，应降低目标或等新数据源。
