"""
ThinBook Pension, the gymnasium environment. The game is described in environment/custom_env.py
and every setting is in configs/market.yaml.
"""

import math
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from custom_types.asset_weights import AssetWeights
from custom_types.json_state import JsonState
from custom_types.limit_breaches import LimitBreaches
from custom_types.market_config import MarketConfig
from custom_types.market_day import MarketDay
from custom_types.payout import Payout
from custom_types.step_info import StepInfo
from custom_types.trade import Trade
from environment.custom_env import (
    ACTION_NAMES,
    CALL_BIG_BUYER,
    DUE_LATER_DAYS,
    DUE_SOON_DAYS,
    MAX_PAYMENT_ATTEMPTS,
    MINIMUM_TRADE_NAIRA,
    OBSERVATION_HIGH,
    OBSERVATION_LOW,
    OBSERVATION_NAMES,
    PAYMENT_MARGIN,
    PAYOUT_SCALE,
    SELL_BANK_SHARES,
    SELL_SMALL_CAP_SHARES,
    SELL_TBILLS,
    SUDDEN_KINDS,
    VOLATILITY_SCALE,
    WAIT,
    WARM_UP_DAYS,
    load_config,
)


class ThinBookPensionEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config: MarketConfig | None = None) -> None:
        if config is None:
            config = load_config()

        self.config = config

        self.action_names = ACTION_NAMES

        self.action_space = spaces.Discrete(len(self.action_names))

        self.observation_space = spaces.Box(low=OBSERVATION_LOW, high=OBSERVATION_HIGH, dtype=np.float32)

        self.impact_decay = 0.5 ** (1 / config["small_caps_impact_half_life_days"])

    def _draw_market(self) -> None:
        config = self.config

        total_days = WARM_UP_DAYS + config["horizon_days"]

        stormy_share = config["calm_to_stormy_daily"] / (config["calm_to_stormy_daily"] + config["stormy_to_calm_daily"])

        drought_share = config["normal_to_drought_daily"] / (config["normal_to_drought_daily"] + config["drought_to_normal_daily"])

        stormy = bool(self.np_random.random() < stormy_share)

        drought = bool(self.np_random.random() < drought_share)

        volume_deviation = 0.0

        rho = config["small_caps_volume_autocorrelation"]

        sigma = config["small_caps_volume_log_sigma"]

        self.market: list[MarketDay] = []

        for _ in range(total_days):
            multiplier = config["stormy_volatility_multiplier"] if stormy else 1.0

            banks_volatility = config["banks_daily_volatility"] * multiplier

            small_caps_volatility = config["small_caps_daily_volatility"] * multiplier

            zero_probability = config["small_caps_zero_volume_drought"] if drought else config["small_caps_zero_volume_normal"]

            volume_median = config["small_caps_median_volume"] * (config["small_caps_drought_volume_multiplier"] if drought else 1.0)

            nobody_trades = self.np_random.random() < zero_probability

            volume_shock = self.np_random.standard_normal()

            volume = 0.0

            if not nobody_trades:
                volume_deviation = rho * volume_deviation + math.sqrt(1 - rho**2) * sigma * volume_shock

                volume = volume_median * math.exp(volume_deviation)

            offer_probability = config["big_buyer_probability_drought"] if drought else config["big_buyer_probability_normal"]

            self.market.append({
                "stormy": stormy,
                "drought": drought,
                "banks_move": banks_volatility * self.np_random.standard_normal() - 0.5 * banks_volatility**2,
                "small_caps_move": small_caps_volatility * self.np_random.standard_normal() - 0.5 * small_caps_volatility**2,
                "small_caps_volume": volume,
                "banks_daily_value": config["banks_daily_value_naira"] * math.exp(config["banks_value_log_sigma"] * self.np_random.standard_normal()),
                "big_buyer_offered": bool(self.np_random.random() < offer_probability),
            })

            if stormy and self.np_random.random() < config["stormy_to_calm_daily"]:
                stormy = False

            elif not stormy and self.np_random.random() < config["calm_to_stormy_daily"]:
                stormy = True

            if drought and self.np_random.random() < config["drought_to_normal_daily"]:
                drought = False

            elif not drought and self.np_random.random() < config["normal_to_drought_daily"]:
                drought = True

    def _draw_payouts(self) -> None:
        config = self.config

        horizon = config["horizon_days"]

        count = int(self.np_random.integers(config["payouts_min"], config["payouts_max"] + 1))

        total_share = self.np_random.uniform(config["payouts_total_min"], config["payouts_total_max"])

        split = self.np_random.dirichlet(np.full(count, 2.0))

        stormy_day_weights: list[float] = []

        for day in range(horizon):
            stormy = self.market[WARM_UP_DAYS + day]["stormy"]

            stormy_day_weights.append(config["sudden_stormy_weight"] if stormy else 1.0)

        day_weights = np.array(stormy_day_weights)

        self.payouts: list[Payout] = []

        for index in range(count):
            amount = float(total_share * split[index] * config["starting_fund_naira"])

            announced = bool(self.np_random.random() < config["announced_share"])

            if announced:
                notice = int(self.np_random.integers(config["announced_notice_min"], config["announced_notice_max"] + 1))

                due_day = int(self.np_random.integers(notice + 1, horizon + 1))

            else:
                notice = int(self.np_random.integers(config["sudden_notice_min"], config["sudden_notice_max"] + 1))

                latest_arrival = horizon - notice

                weights = day_weights[:latest_arrival] / day_weights[:latest_arrival].sum()

                arrival = int(self.np_random.choice(latest_arrival, p=weights)) + 1

                due_day = arrival + notice

            kind = "scheduled_retirement"

            if not announced:
                sudden_so_far = 0

                for payout in self.payouts:
                    if not payout["announced"]:
                        sudden_so_far = sudden_so_far + 1

                kind = SUDDEN_KINDS[sudden_so_far % len(SUDDEN_KINDS)]

            self.payouts.append({"arrival_day": due_day - notice, "due_day": due_day, "amount": amount, "announced": announced, "kind": kind, "paid": False})

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)

        config = self.config

        self._draw_market()

        self._draw_payouts()

        fund = config["starting_fund_naira"]

        self.day = 0

        self.banks_price = config["banks_start_price"]

        small_caps_shares = config["small_caps_position_days"] * config["small_caps_median_volume"]

        self.small_caps_fair = config["start_small_caps"] * fund / small_caps_shares

        self.small_caps_impact = 0.0

        self.small_caps_board = self.small_caps_fair

        self.days_since_board_move = 0

        self.banks_history = [self.banks_price]

        self.volume_history: list[float] = []

        for warm_day in range(WARM_UP_DAYS):
            self._move_market(self.market[warm_day])

            self._update_board(self.market[warm_day]["small_caps_volume"])

        self.cash = 0.0

        self.settling_cash = 0.0

        self.tbills = config["start_tbills"] * fund

        self.banks_shares = config["start_banks"] * fund / self.banks_price

        self.small_caps_shares = small_caps_shares

        price_scale = config["start_small_caps"] * fund / (small_caps_shares * self.small_caps_fair)

        self.small_caps_fair = self.small_caps_fair * price_scale

        self.small_caps_board = self.small_caps_board * price_scale

        self.reference_banks_price = self.banks_price

        self.reference_small_caps_price = self.small_caps_fair

        self.small_caps_sold_today = 0.0

        self.breach_started_day = 0

        self.forced_events: list[str] = []

        self.trades_today: list[Trade] = []

        self.cost_naira = 0.0

        self.fees_naira = 0.0

        self.total_points = 0.0

        self.points_today = 0.0

        self.invalid_actions = 0

        self.last_action = WAIT

        self.last_invalid = False

        self.paid_out = 0.0

        self.outcome = ""

        self.outcome_reason = ""

        self.end_score = 0.0

        return self._observation(), dict(self._info())

    @property
    def small_caps_real(self) -> float:
        return self.small_caps_fair * math.exp(self.small_caps_impact)

    def _today(self) -> MarketDay:
        return self.market[WARM_UP_DAYS + max(self.day, 1) - 1]

    def _move_market(self, today: MarketDay) -> None:
        self.banks_price = self.banks_price * math.exp(today["banks_move"])

        self.small_caps_fair = self.small_caps_fair * math.exp(today["small_caps_move"])

        self.small_caps_impact = self.small_caps_impact * self.impact_decay

        self.banks_history.append(self.banks_price)

    def _update_board(self, day_volume: float) -> None:
        self.volume_history.append(day_volume)

        if day_volume >= self.config["board_minimum_shares"]:
            self.small_caps_board = self.small_caps_real

            self.days_since_board_move = 0

        else:
            self.days_since_board_move = self.days_since_board_move + 1

    def observed_value(self) -> float:
        stocks = self.banks_shares * self.banks_price + self.small_caps_shares * self.small_caps_board

        return self.cash + self.settling_cash + self.tbills + stocks

    def book_value(self) -> float:
        stocks = self.banks_shares * self.reference_banks_price + self.small_caps_shares * self.reference_small_caps_price

        return self.cash + self.settling_cash + self.tbills + stocks

    def weights(self) -> AssetWeights:
        value = self.book_value()

        weights: AssetWeights = {
            "cash": (self.cash + self.settling_cash) / value,
            "tbills": self.tbills / value,
            "banks": self.banks_shares * self.reference_banks_price / value,
            "small_caps": self.small_caps_shares * self.reference_small_caps_price / value,
        }

        return weights

    def _score_sale(self, asset: str, shares: float, proceeds: float, fair_value: float, fee: float, reason: str) -> None:
        cost = fair_value - proceeds + fee

        self.cost_naira = self.cost_naira + cost

        self.fees_naira = self.fees_naira + fee

        self.points_today = self.points_today - cost * self.config["points_per_naira"]

        self.trades_today.append({"asset": asset, "shares": shares, "proceeds": proceeds, "fee": fee, "cost": cost, "reason": reason})

        if reason.startswith("forced"):
            self.forced_events.append(f"day {self.day}: {reason} ({asset})")

    def _receive(self, naira: float, settle_now: bool) -> None:
        if settle_now:
            self.cash = self.cash + naira

        else:
            self.settling_cash = self.settling_cash + naira

    def _sell_tbills(self, naira: float, reason: str) -> None:
        amount = min(naira, self.tbills)

        if amount <= 0:
            return

        fee = amount * self.config["tbill_fee"]

        self.tbills = self.tbills - amount

        self.cash = self.cash + amount - fee

        self._score_sale("tbills", amount, amount, amount, fee, reason)

    def _sell_banks(self, naira: float, reason: str, discount: float, settle_now: bool) -> None:
        shares = min(self.banks_shares, naira / self.banks_price)

        if shares <= 0:
            return

        fair_value = shares * self.banks_price

        impact = self.config["banks_impact_coefficient"] * math.sqrt(fair_value / self._today()["banks_daily_value"])

        proceeds = fair_value * (1 - impact) * (1 - discount)

        fee = proceeds * self.config["stock_sell_fee"]

        self.banks_shares = self.banks_shares - shares

        self._receive(proceeds - fee, settle_now)

        self._score_sale("banks", shares, proceeds, fair_value, fee, reason)

    def small_caps_room_today(self) -> float:
        return max(self.config["participation_limit"] * self._today()["small_caps_volume"] - self.small_caps_sold_today, 0.0)

    def _sell_small_caps(self, naira: float, reason: str, discount: float, settle_now: bool, on_exchange: bool, capped: bool) -> None:
        config = self.config

        shares = min(self.small_caps_shares, naira / self.small_caps_fair)

        if capped:
            shares = min(shares, self.small_caps_room_today())

        if shares <= 0:
            return

        market_volume = max(self._today()["small_caps_volume"], 1.0)

        participation = min(shares / market_volume, 1.0) if on_exchange else 0.0

        temporary_impact = config["small_caps_temporary_impact"] * math.sqrt(participation)

        fair_value = shares * self.small_caps_fair

        proceeds = shares * self.small_caps_real * (1 - temporary_impact) * (1 - discount)

        fee = proceeds * config["stock_sell_fee"]

        self.small_caps_shares = self.small_caps_shares - shares

        if on_exchange:
            self.small_caps_sold_today = self.small_caps_sold_today + shares

            self.small_caps_impact = self.small_caps_impact - config["small_caps_permanent_impact"] * participation

        self._receive(proceeds - fee, settle_now)

        self._score_sale("small_caps", shares, proceeds, fair_value, fee, reason)

    def _buy_banks_forced(self, naira: float) -> None:
        self._sell_tbills(max(naira - self.cash, 0.0), "forced: raise cash for limit buy")

        naira = min(naira, self.cash)

        if naira <= 0:
            return

        price = self.banks_price * (1 + self.config["forced_buy_premium"])

        shares = naira / price

        self.cash = self.cash - naira

        self.banks_shares = self.banks_shares + shares

        cost = naira - shares * self.banks_price

        self.cost_naira = self.cost_naira + cost

        self.points_today = self.points_today - cost * self.config["points_per_naira"]

        self.forced_events.append(f"day {self.day}: forced: banks below lower limit (banks)")

        self.trades_today.append({"asset": "banks", "shares": -shares, "proceeds": -naira, "fee": 0.0, "cost": cost, "reason": "forced: banks below lower limit"})

    def _sale_order(self, action: int) -> tuple[str, float]:
        config = self.config

        orders = {
            WAIT: ("wait", 0.0),
            SELL_TBILLS: ("tbills", config["tbill_slice"]),
            SELL_BANK_SHARES: ("banks", config["banks_slice"]),
            SELL_SMALL_CAP_SHARES: ("small_caps", config["small_caps_slice"]),
            CALL_BIG_BUYER: ("big_buyer", config["big_buyer_slice"]),
        }

        return orders[action]

    def _invalid(self, action: int) -> bool:
        asset, _ = self._sale_order(action)

        if asset == "tbills":
            return self.tbills < MINIMUM_TRADE_NAIRA

        if asset == "banks":
            return self.banks_shares * self.banks_price < MINIMUM_TRADE_NAIRA

        if asset == "small_caps":
            return self.small_caps_shares * self.small_caps_board < MINIMUM_TRADE_NAIRA

        if asset == "big_buyer":
            return not self._today()["big_buyer_offered"] or self.small_caps_shares * self.small_caps_board < MINIMUM_TRADE_NAIRA

        return False

    def _act(self, action: int) -> None:
        config = self.config

        asset, slice_share = self._sale_order(action)

        naira = slice_share * config["starting_fund_naira"]

        if asset == "tbills":
            self._sell_tbills(naira, "agent")

        elif asset == "banks":
            self._sell_banks(naira, "agent", discount=0.0, settle_now=False)

        elif asset == "big_buyer":
            self._sell_small_caps(naira, "big buyer", discount=config["big_buyer_discount"], settle_now=False, on_exchange=False, capped=False)

        elif asset == "small_caps":
            self._sell_small_caps(naira, "agent", discount=0.0, settle_now=False, on_exchange=True, capped=True)

    def due_today(self) -> float:
        total = 0.0

        for payout in self.payouts:
            if payout["due_day"] == self.day and not payout["paid"]:
                total = total + payout["amount"]

        return total

    def _pay_payouts(self) -> None:
        config = self.config

        amount = self.due_today()

        if amount <= 0:
            return

        if self.cash < amount:
            self._sell_tbills((amount - self.cash) / (1 - config["tbill_fee"]), "forced: payout")

        if self.cash < amount:
            gross = (amount - self.cash) / ((1 - config["banks_fire_sale_discount"]) * (1 - config["stock_sell_fee"])) * PAYMENT_MARGIN

            self._sell_banks(gross, "forced: payout", discount=config["banks_fire_sale_discount"], settle_now=True)

        if self.cash < amount:
            gross = (amount - self.cash) / ((1 - config["small_caps_fire_sale_discount"]) * (1 - config["stock_sell_fee"]))

            self._sell_small_caps(gross, "forced: payout", discount=config["small_caps_fire_sale_discount"], settle_now=True, on_exchange=True, capped=True)

        attempts = 0

        while self.cash < amount - 0.01 and self.small_caps_shares > 0 and attempts < MAX_PAYMENT_ATTEMPTS:
            gross = (amount - self.cash) / ((1 - config["small_caps_fire_sale_discount"]) * (1 - config["stock_sell_fee"])) * PAYMENT_MARGIN

            self._sell_small_caps(gross, "forced: payout, beyond volume cap", discount=config["small_caps_fire_sale_discount"], settle_now=True, on_exchange=False, capped=False)

            attempts = attempts + 1

        paid = min(amount, self.cash)

        self.cash = self.cash - paid

        self.paid_out = self.paid_out + paid

        for payout in self.payouts:
            if payout["due_day"] == self.day:
                payout["paid"] = True

    def breaches(self) -> LimitBreaches:
        config = self.config

        weights = self.weights()

        value = self.book_value()

        breaches: LimitBreaches = {
            "small_caps_over": max(weights["small_caps"] - config["small_caps_max_share"], 0.0) * value,
            "banks_over": max(weights["banks"] - config["banks_max_share"], 0.0) * value,
            "banks_under": max(config["banks_min_share"] - weights["banks"], 0.0) * value,
        }

        return breaches

    def grace_days_left(self) -> int:
        if self.breach_started_day == 0:
            return self.config["breach_grace_days"]

        return max(self.config["breach_grace_days"] - (self.day - self.breach_started_day), 0)

    def _enforce_limits(self, final_day: bool) -> None:
        config = self.config

        breaches = self.breaches()

        in_breach = breaches["small_caps_over"] > 1.0 or breaches["banks_over"] > 1.0 or breaches["banks_under"] > 1.0

        if not in_breach:
            self.breach_started_day = 0

            return

        if self.breach_started_day == 0:
            self.breach_started_day = self.day

        grace_over = self.day - self.breach_started_day >= config["breach_grace_days"]

        if not grace_over and not final_day:
            return

        small_caps_excess_book = breaches["small_caps_over"] / (1 - config["small_caps_max_share"])

        if small_caps_excess_book > 1.0:
            naira_at_fair = small_caps_excess_book / self.reference_small_caps_price * self.small_caps_fair

            self._sell_small_caps(naira_at_fair, "forced: small caps over limit", discount=config["small_caps_fire_sale_discount"], settle_now=True, on_exchange=not final_day, capped=not final_day)

        banks_excess_book = self.breaches()["banks_over"] / (1 - config["banks_max_share"])

        if banks_excess_book > 1.0:
            self._sell_banks(banks_excess_book / self.reference_banks_price * self.banks_price, "forced: banks over limit", discount=config["banks_fire_sale_discount"], settle_now=True)

        banks_shortfall_book = self.breaches()["banks_under"] / (1 - config["banks_min_share"])

        if banks_shortfall_book > 1.0:
            self._buy_banks_forced(banks_shortfall_book / self.reference_banks_price * self.banks_price)

    def step(self, action: int | np.integer | np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        action = int(action)

        config = self.config

        self.day = self.day + 1

        today = self._today()

        self.trades_today = []

        self.points_today = 0.0

        self.small_caps_sold_today = 0.0

        self._move_market(today)

        self.cash = self.cash + self.settling_cash

        self.settling_cash = 0.0

        self.last_invalid = self._invalid(action)

        if self.last_invalid:
            self.invalid_actions = self.invalid_actions + 1

        else:
            self._act(action)

        self._pay_payouts()

        self._update_board(today["small_caps_volume"] + self.small_caps_sold_today)

        game_over = self.day >= config["horizon_days"]

        self._enforce_limits(final_day=game_over)

        reward = self.points_today - (config["invalid_action_penalty"] if self.last_invalid else 0.0)

        if game_over:
            self._finish()

            reward = reward + self.end_score

        self.total_points = self.total_points + reward

        self.last_action = action

        return self._observation(), float(reward), game_over, False, dict(self._info())

    def cost_bps(self) -> float:
        return 10000 * self.cost_naira / self.config["starting_fund_naira"]

    def _finish(self) -> None:
        config = self.config

        if self.forced_events:
            self.outcome = "lost"

            self.outcome_reason = "forced sale"

        elif self.cost_bps() >= config["won_cost_bps"]:
            self.outcome = "lost"

            self.outcome_reason = "too costly"

        else:
            self.outcome = "won"

            self.outcome_reason = ""

        self.end_score = config["end_score_won"] if self.outcome == "won" else config["end_score_lost"]

    def known_payouts(self) -> list[Payout]:
        upcoming_day = self.day + 1

        known: list[Payout] = []

        for payout in self.payouts:
            if payout["arrival_day"] <= upcoming_day and not payout["paid"]:
                known.append(payout)

        return known

    def _due_within(self, days: int) -> float:
        upcoming_day = self.day + 1

        total = 0.0

        for payout in self.known_payouts():
            if payout["due_day"] < upcoming_day + days:
                total = total + payout["amount"]

        return total

    def _observation(self) -> np.ndarray:
        config = self.config

        fund = config["starting_fund_naira"]

        weights = self.weights()

        value = self.book_value()

        upcoming_day = self.day + 1

        days_until_each_due: list[int] = []

        for payout in self.known_payouts():
            days_until_each_due.append(payout["due_day"] - upcoming_day)

        days_to_next_due = min(days_until_each_due) if days_until_each_due else DUE_LATER_DAYS

        in_breach = self.breach_started_day > 0

        grace_left = self.grace_days_left() / config["breach_grace_days"] if in_breach else 1.0

        prices = np.array(self.banks_history[-(config["volatility_window_days"] + 1):])

        recent_volatility = float(np.std(np.diff(np.log(prices))))

        volume_scale = math.log1p(config["volume_ratio_cap"])

        yesterday_ratio = self.volume_history[-1] / config["small_caps_median_volume"]

        five_day_ratio = float(np.mean(self.volume_history[-config["volume_window_days"]:])) / config["small_caps_median_volume"]

        offered_today = self.day < config["horizon_days"] and self.market[WARM_UP_DAYS + self.day]["big_buyer_offered"]

        banks_band = config["banks_max_share"] - config["banks_min_share"]

        observation = np.array(
            [
                (config["horizon_days"] - self.day) / config["horizon_days"],

                weights["tbills"],

                (weights["banks"] - config["banks_min_share"] + banks_band) / (3 * banks_band),

                weights["small_caps"] / (2 * config["small_caps_max_share"]),

                (self.cash) / value,

                self.settling_cash / value,

                self._due_within(DUE_SOON_DAYS) / (PAYOUT_SCALE * fund),

                self._due_within(DUE_LATER_DAYS) / (PAYOUT_SCALE * fund),

                min(days_to_next_due, DUE_LATER_DAYS) / DUE_LATER_DAYS,

                grace_left,

                min(self.days_since_board_move, config["staleness_cap_days"]) / config["staleness_cap_days"],

                math.log1p(yesterday_ratio) / volume_scale,

                math.log1p(five_day_ratio) / volume_scale,

                recent_volatility / VOLATILITY_SCALE,

                float(offered_today),
            ],
            dtype=np.float32,
        )

        return np.clip(observation, OBSERVATION_LOW, OBSERVATION_HIGH)

    def _known_payouts_copy(self) -> list[Payout]:
        payouts_copy: list[Payout] = []

        for payout in self.known_payouts():
            payouts_copy.append(payout.copy())

        return payouts_copy

    def _info(self) -> StepInfo:
        upcoming_day = self.day + 1

        due_tomorrow = 0.0

        for payout in self.known_payouts():
            if payout["due_day"] == upcoming_day:
                due_tomorrow = due_tomorrow + payout["amount"]

        info: StepInfo = {
            "day": self.day,
            "action_name": self.action_names[self.last_action],
            "invalid_action": self.last_invalid,
            "invalid_actions": self.invalid_actions,
            "trades": list(self.trades_today),
            "weights": self.weights(),
            "cash_naira": self.cash,
            "settling_naira": self.settling_cash,
            "tbills_naira": self.tbills,
            "banks_naira": self.banks_shares * self.banks_price,
            "small_caps_naira_board": self.small_caps_shares * self.small_caps_board,
            "small_caps_shares": self.small_caps_shares,
            "observed_value_naira": self.observed_value(),
            "book_value_naira": self.book_value(),
            "small_caps_naira_book": self.small_caps_shares * self.reference_small_caps_price,
            "banks_naira_book": self.banks_shares * self.reference_banks_price,
            "known_payouts": self._known_payouts_copy(),
            "due_within_5_naira": self._due_within(DUE_SOON_DAYS),
            "due_within_15_naira": self._due_within(DUE_LATER_DAYS),
            "due_tomorrow_naira": due_tomorrow,
            "in_breach": self.breach_started_day > 0,
            "grace_days_left": self.grace_days_left(),
            "small_caps_board_price": self.small_caps_board,
            "small_caps_fair_price": self.small_caps_fair,
            "small_caps_real_price": self.small_caps_real,
            "small_caps_days_since_board_move": self.days_since_board_move,
            "small_caps_volume_yesterday": self.volume_history[-1],
            "banks_price": self.banks_price,
            "big_buyer_offered_today": bool(self.day < self.config["horizon_days"] and self.market[WARM_UP_DAYS + self.day]["big_buyer_offered"]),
            "stormy": self.market[WARM_UP_DAYS + min(self.day, self.config["horizon_days"] - 1)]["stormy"],
            "drought": self.market[WARM_UP_DAYS + min(self.day, self.config["horizon_days"] - 1)]["drought"],
            "points_today": self.points_today,
            "total_points": self.total_points,
            "cost_bps": self.cost_bps(),
            "fees_naira": self.fees_naira,
            "paid_out_naira": self.paid_out,
            "forced_events": list(self.forced_events),
            "forced_event_count": len(self.forced_events),
            "won_flag": 1.0 if self.outcome == "won" else 0.0,
            "outcome": self.outcome,
            "outcome_reason": self.outcome_reason,
        }

        return info

    def to_json_state(self) -> JsonState:
        named_observation: dict[str, float] = {}

        for name, value in zip(OBSERVATION_NAMES, self._observation()):
            named_observation[name] = float(value)

        state: JsonState = {**self._info(), "observation": named_observation}

        return state
