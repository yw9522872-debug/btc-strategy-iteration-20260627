# Strategy 1E Shock Guard

- strategy_id: `strategy_1e_shock_guard_20260627`
- strict_no_future_function: `True`
- hard_pass: `True`
- return_2025_pct: `412.05570181711283`
- return_2026_pct: `257.43541356723665`
- min_monthly_return_pct: `4.488453572042084`
- min_monthly_orders: `11`
- max_drawdown_pct: `-29.403117070591435`
- strong_trend_reverse_big_active_bars: `1`
- weak_trend_big_order_events: `0`
- adverse_shock_cut_events: `1`

## Change

- Cap selected leverage at 8x.
- If the base signal fights a strong trend, do not allow a large opposite trade.
- In weak trend zones, new or reverse trades are shrunk to 0.10x.
- If the current closed bar badly hurts the active position, cut or shrink the next-bar target.
