"""Every setting in configs/market.yaml, with its type."""

from typing import TypedDict


class MarketConfig(TypedDict):
    starting_fund_naira: float

    horizon_days: int

    points_per_naira: float

    invalid_action_penalty: float

    end_score_won: float

    end_score_lost: float

    won_cost_bps: float

    start_tbills: float

    start_banks: float

    start_small_caps: float

    small_caps_position_days: int

    small_caps_max_share: float

    banks_min_share: float

    banks_max_share: float

    breach_grace_days: int

    payouts_min: int

    payouts_max: int

    payouts_total_min: float

    payouts_total_max: float

    announced_share: float

    announced_notice_min: int

    announced_notice_max: int

    sudden_notice_min: int

    sudden_notice_max: int

    sudden_stormy_weight: float

    tbill_slice: float

    banks_slice: float

    small_caps_slice: float

    big_buyer_slice: float

    stock_sell_fee: float

    tbill_fee: float

    stock_settlement_days: int

    small_caps_fire_sale_discount: float

    banks_fire_sale_discount: float

    forced_buy_premium: float

    calm_to_stormy_daily: float

    stormy_to_calm_daily: float

    stormy_volatility_multiplier: float

    banks_daily_volatility: float

    small_caps_daily_volatility: float

    banks_start_price: float

    banks_daily_value_naira: float

    banks_value_log_sigma: float

    banks_impact_coefficient: float

    normal_to_drought_daily: float

    drought_to_normal_daily: float

    small_caps_median_volume: float

    small_caps_volume_log_sigma: float

    small_caps_volume_autocorrelation: float

    small_caps_zero_volume_normal: float

    small_caps_zero_volume_drought: float

    small_caps_drought_volume_multiplier: float

    board_minimum_shares: float

    participation_limit: float

    small_caps_temporary_impact: float

    small_caps_permanent_impact: float

    small_caps_impact_half_life_days: float

    big_buyer_probability_normal: float

    big_buyer_probability_drought: float

    big_buyer_discount: float

    volatility_window_days: int

    volume_window_days: int

    staleness_cap_days: int

    volume_ratio_cap: float
