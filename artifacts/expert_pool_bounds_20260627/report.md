# Expert Pool Bounds 20260627

- status: `expert_pool_bounds_ready`
- expert_count: `730`
- unit_count: `2920`
- cost: `0.1% per side, 0.2% open+close; real turnover orders counted`
- theoretical_upper_bound_pass: `True`
- strict_tradeable_pass: `False`

## Static Single Expert Best

- hard_pass: `False`
- selector: `static_single_expert_best`
- unit: `expert_0098_gap_adx_state_lev1`
- 2025 return: `53.95106225741573`
- 2026 return: `37.93829885723461`
- min monthly return: `-17.65984858326401`
- min monthly orders: `0`

## Monthly Posthoc Oracle

- strict_no_future: `false`
- hard_pass: `True`
- 2025 return: `370900113695.3203`
- 2026 return: `2737161.0965417833`
- min monthly return: `112.29415706860877`
- min monthly orders: `10`

## Best Strict Tradeable Selector

- strict_no_future: `True`
- selector: `strict_first_14d_calibrate_trade_rest`
- hard_pass: `False`
- 2025 return: `77.76033602831977`
- 2026 return: `153.75278888662137`
- min monthly return: `-63.623025082080034`
- losing eval months: `5`
- min monthly orders: `2`
