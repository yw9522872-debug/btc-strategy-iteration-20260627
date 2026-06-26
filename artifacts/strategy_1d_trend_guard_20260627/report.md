# Strategy 1D Trend Guard

- strategy_id: `strategy_1d_trend_guard_20260627`
- strict_no_future_function: `True`
- hard_pass: `True`
- return_2025_pct: `350.17171925447406`
- return_2026_pct: `256.4432711297096`
- min_monthly_return_pct: `5.8786004289359095`
- min_monthly_orders: `11`
- max_drawdown_pct: `-32.66598420374073`
- strong_trend_reverse_big_active_bars: `2`
- weak_trend_big_order_events: `0`

## Change

- Cap selected leverage at 8x.
- If the base signal fights a strong trend, do not allow a large opposite trade.
- In weak trend zones, new or reverse trades are shrunk to 0.10x.
- After monthly lock, keep the small trend runner from 1C.
