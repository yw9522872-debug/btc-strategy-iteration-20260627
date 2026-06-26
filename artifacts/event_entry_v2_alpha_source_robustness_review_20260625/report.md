# Event Entry V2 Alpha Source Robustness Review

- Status: `event_entry_v2_alpha_source_robustness_review_ready`
- Review rows: `109`
- Yearly-gate pass variants: `23`
- Lower-drawdown yearly-gate pass variants: `5`
- Candidate ready: `False`
- Entry capable: `False`
- Live promotion: `LIVE_PROMOTION_NO_GO`

## Best Variant

- Variant: `alpha_robust_static_a742e1d0c3_lev2.2`
- Kind: `static`
- Leverage: `2.2`
- Total return: `1993.4034292614904`
- 2025 return: `149.65324085613253`
- 2026 return: `106.40825380994343`
- Yearly gate pass: `True`
- Max drawdown: `-57.92983869640362`
- Drawdown improvement: `11.363152441552401`
- Exposure: `95.24486681465038`
- Segments: `2`

## Cost Stress

- Rows: `4`
- Passing rows: `4`
- Worst 2025 return: `147.03077362966553`
- Worst 2026 return: `106.40825380994343`

## Guard

- `research_review_only_not_live_source`
- `entry_capable_false`
- `downstream_rebuild_not_allowed`
- `monthly_meta_late_era_rebuild_not_run`
- `observe_paper_mock_acceptance_not_run`
- `explicit_user_live_confirmation_missing`
- `LIVE_PROMOTION_NO_GO`
- `lower_drawdown_variant_is_research_only`
- `walk_forward_and_no_lookahead_audit_not_sufficient_for_promotion`
