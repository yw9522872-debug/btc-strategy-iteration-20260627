# Strategy 53：2C 每月只做前N笔

- strategy_id: `strategy_53_2c_first_n_orders_only_20260630`
- 这是研究审计，不是固化版。
- 规则：每个月只做2C逻辑产生的前N笔订单，然后无条件空仓到月底。
- 手续费：开平合计 `0.002`

| 版本 | 2025 | 2026 | 最差月 | 亏损月 | 最大回撤 | hard_pass |
|---|---:|---:|---:|---:|---:|---|
| `first_5_orders_then_flat` | 115.94% | 182.69% | -15.66% | 4 | -24.36% | `False` |
| `first_10_orders_then_flat` | 202.08% | 261.07% | -7.91% | 2 | -29.25% | `False` |
| `first_15_orders_then_flat` | 197.10% | 41.46% | -19.22% | 6 | -49.70% | `False` |
| `first_20_orders_then_flat` | 124.56% | 180.40% | -37.01% | 7 | -68.88% | `False` |

## 结论

- `FIRST_N_ONLY_HAS_RELAXED_SIGNAL_NOT_ORIGINAL_PASS`
- hard_pass_variants: `[]`
- relaxed_annual_100_dd50_variants: `['first_5_orders_then_flat', 'first_10_orders_then_flat']`
- best_variant_id: `first_10_orders_then_flat`
- 每月只做前N笔不能满足月月盈利原目标，但前5笔和前10笔能满足年收益都超100%、最大回撤小于50%的放宽门槛；这说明前段窗口有历史信号，但仍是事后发现，不能直接实盘。
