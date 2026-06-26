# Strategy 1F Selective Runner

- strategy_id: `strategy_1f_selective_runner_20260627`
- strict_no_future_function: `True`
- hard_pass: `True`
- return_2025_pct: `433.737120815807`
- return_2026_pct: `260.5918213916581`
- min_monthly_return_pct: `4.488453572042084`
- min_monthly_orders: `11`
- max_drawdown_pct: `-29.40311707059142`
- strong_trend_reverse_big_active_bars: `1`
- weak_trend_big_order_events: `0`
- adverse_shock_cut_events: `1`

## Change

- Cap selected leverage at 8x.
- If the base signal fights a strong trend, do not allow a large opposite trade.
- In weak trend zones, new or reverse trades are shrunk to 0.10x.
- If the current closed bar badly hurts the active position, cut or shrink the next-bar target.
- After monthly lock, run only a stricter tiny trend follower.
