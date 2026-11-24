"""
Estimate ThinBook Pension's market environment based on the real NGX data.

1. Load NGX daily prices (Kobo Terminal cache, pinned to the 2026-08-31 fetch) and the NGX All
Share Index (ASI), 2021-01-01 to 2026-08-28.
2. ASI: rate each month as calm or stormy by its volatility, then tabulate how long each lasts
and how much more volatile stormy months are.
3. Baskets: same-weight big-banks basket (5 banks) and small-caps basket (bottom third of NGX by
market cap): beta to the ASI and daily idiosyncratic volatility.
4. Small-cap liquidity: days with no trades, traded volume and spread, drought months
(normal vs drought), how long each lasts, and how volume differs in drought versus normal months.
5. ZENITHBANK: median daily traded value (a lower limit for the liquidity of the banks basket).

Only summary values are written (configs/calibration.yaml). Raw data is licensed and never
leaves the data folder. scripts/calibrate_volume_persistence.py then adds the volume
persistence section.

It only works with our capstone NGX data (specific licensed Kobo Terminal export files), which cannot be published online,
so the data folder is not in this repository.

Run from the project root:

uv run python scripts/calibrate.py --data-dir <path to the capstone NGX data>
"""

import argparse
import glob
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_types import BankLiquidity, BasketStatistics, Calibration, MarketStatistics, NgxStock, SmallCapsLiquidity  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "configs" / "calibration.yaml"

PINNED_FETCH_CUTOFF = "20260831T235959"

START_DATE = "2021-01-01"

END_DATE = "2026-08-28"

BANK_SYMBOL = "ZENITHBANK"

BANK_BASKET = ["ZENITHBANK", "GTCO", "ACCESSCORP", "UBA", "FIRSTHOLDCO"]

BOARD_MINIMUM_SHARES = 100_000

MINIMUM_SESSIONS = 500

SMALL_CAP_SHARE = 1 / 3

EXCLUDED_BOARDS = ["Real Estate Investment Trust & Close End Fund"]

CORPORATE_ACTION_RETURN = 0.25

DROUGHT_MONTH_THRESHOLD = 0.5

STORMY_MONTH_THRESHOLD = 1.5

SESSIONS_PER_MONTH = 21

BETA_HORIZON_SESSIONS = 20


def newest_pinned_file(files: list[str]) -> str | None:
    pinned_files: list[str] = []

    for file in files:
        fetch_date = file.split("_")[-1].replace(".json", "")

        if fetch_date <= PINNED_FETCH_CUTOFF:
            pinned_files.append(file)

    if not pinned_files:
        return None

    return sorted(pinned_files)[-1]


def load_prices(data_dir: Path, symbol: str, sessions: pd.DatetimeIndex) -> pd.DataFrame | None:
    files = glob.glob(str(data_dir / "prices" / f"{symbol}_*.json"))

    pinned_file = newest_pinned_file(files)

    if pinned_file is None:
        return None

    rows = json.load(open(pinned_file))["prices"]

    if not rows:
        return None

    prices = pd.DataFrame(rows)

    prices["trade_date"] = pd.to_datetime(prices["trade_date"])

    prices = prices.set_index("trade_date").sort_index()

    prices = prices[~prices.index.duplicated(keep="last")]

    first_session = max(prices.index[0], sessions[0])

    stock_sessions = sessions[(sessions >= first_session) & (sessions <= prices.index[-1])]

    prices = prices.reindex(stock_sessions)

    prices["volume"] = prices["volume"].fillna(0.0)

    prices["close_price"] = prices["close_price"].ffill()

    return prices[["close_price", "volume"]].dropna()


def load_asi(data_dir: Path) -> pd.Series:
    asi_file = newest_pinned_file(glob.glob(str(data_dir / "indices" / "ASI_*.json")))

    if asi_file is None:
        raise SystemExit(f"No pinned ASI file in {data_dir / 'indices'}")

    history = json.load(open(asi_file))["history"]

    asi = pd.DataFrame(history)

    asi["date"] = pd.to_datetime(asi["date"])

    asi_series = asi.set_index("date")["value"].sort_index()

    return asi_series.loc[START_DATE:END_DATE]


def spell_lengths(flags: np.ndarray) -> list[int]:
    lengths: list[int] = []

    current_length = 0

    for flag in flags:
        if flag:
            current_length = current_length + 1

        elif current_length > 0:
            lengths.append(current_length)

            current_length = 0

    if current_length > 0:
        lengths.append(current_length)

    return lengths


def market_cap_of(stock: NgxStock) -> float:
    if stock["market_cap"] is None:
        return 0.0

    return stock["market_cap"]


def pick_small_caps(data_dir: Path, sessions: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    universe_file = newest_pinned_file(glob.glob(str(data_dir / "stocks" / "ngx_universe_*.json")))

    if universe_file is None:
        raise SystemExit(f"No pinned NGX universe file in {data_dir / 'stocks'}")

    universe: list[NgxStock] = json.load(open(universe_file))["stocks"]

    candidates: list[NgxStock] = []

    for stock in universe:
        if stock["market_cap"] and stock["market"] not in EXCLUDED_BOARDS:
            candidates.append(stock)

    candidates = sorted(candidates, key=market_cap_of)

    small_cap_count = int(len(candidates) * SMALL_CAP_SHARE)

    small_caps: dict[str, pd.DataFrame] = {}

    for stock in candidates[:small_cap_count]:
        prices = load_prices(data_dir, stock["symbol"], sessions)

        if prices is None:
            continue

        long_enough = len(prices) >= MINIMUM_SESSIONS

        ever_traded = bool((prices["volume"] > 0).any())

        if long_enough and ever_traded:
            small_caps[stock["symbol"]] = prices

    return small_caps


def monthly_drought_flags(prices: pd.DataFrame) -> pd.Series:
    clears_board_rule = prices["volume"] >= BOARD_MINIMUM_SHARES

    overall_rate = clears_board_rule.mean()

    monthly_rate = clears_board_rule.resample("ME").mean()

    return monthly_rate < DROUGHT_MONTH_THRESHOLD * overall_rate


def daily_switch_probability(mean_spell_months: float) -> float:
    return 1 / (mean_spell_months * SESSIONS_PER_MONTH)


def small_cap_liquidity(small_caps: dict[str, pd.DataFrame]) -> SmallCapsLiquidity:
    zero_volume_rates: list[float] = []

    log_volume_medians: list[float] = []

    log_volume_spreads: list[float] = []

    drought_spells: list[int] = []

    normal_spells: list[int] = []

    zero_rate_normal: list[float] = []

    zero_rate_drought: list[float] = []

    volume_ratio_drought: list[float] = []

    for prices in small_caps.values():
        volume = prices["volume"]

        traded_volume = volume[volume > 0]

        zero_volume_rates.append(float((volume == 0).mean()))

        log_volume = np.log(traded_volume)

        log_volume_medians.append(float(np.median(log_volume)))

        log_volume_spreads.append(float(np.std(log_volume)))

        drought_flags = monthly_drought_flags(prices)

        drought_spells.extend(spell_lengths(drought_flags.to_numpy()))

        normal_spells.extend(spell_lengths(~drought_flags.to_numpy()))

        month_of_day = pd.DatetimeIndex(volume.index).to_period("M").to_timestamp("M")

        day_in_drought = drought_flags.reindex(month_of_day).to_numpy()

        normal_days = volume[~day_in_drought]

        drought_days = volume[day_in_drought]

        if len(normal_days) > 0 and len(drought_days) > 0:
            zero_rate_normal.append(float((normal_days == 0).mean()))

            zero_rate_drought.append(float((drought_days == 0).mean()))

            volume_ratio_drought.append(float(drought_days.mean() / normal_days.mean()))

    statistics: SmallCapsLiquidity = {
        "stocks_used": len(small_caps),
        "symbols": sorted(small_caps),
        "mean_normal_spell_months": float(np.mean(normal_spells)),
        "mean_drought_spell_months": float(np.mean(drought_spells)),
        "zero_volume_rate_median": float(np.median(zero_volume_rates)),
        "log_volume_sigma_median": float(np.median(log_volume_spreads)),
        "drought_volume_vs_normal_median": float(np.median(volume_ratio_drought)),
        "median_traded_volume_shares": float(np.exp(np.median(log_volume_medians))),
        "zero_volume_rate_normal_months_median": float(np.median(zero_rate_normal)),
        "zero_volume_rate_drought_months_median": float(np.median(zero_rate_drought)),
        "normal_to_drought_daily": daily_switch_probability(float(np.mean(normal_spells))),
        "drought_to_normal_daily": daily_switch_probability(float(np.mean(drought_spells))),
        "drought_month_share": float(sum(drought_spells) / (sum(drought_spells) + sum(normal_spells))),
    }

    return statistics


def basket_index(prices_by_symbol: dict[str, pd.DataFrame], sessions: pd.DatetimeIndex) -> pd.Series:
    daily_returns = []

    for prices in prices_by_symbol.values():
        log_returns = np.log(prices["close_price"]).diff()

        log_returns[log_returns.abs() > CORPORATE_ACTION_RETURN] = 0.0

        daily_returns.append(log_returns.rename(None))

    return_table = pd.concat(daily_returns, axis=1).reindex(sessions)

    basket_returns = return_table.mean(axis=1, skipna=True).fillna(0.0)

    return np.exp(basket_returns.cumsum())


def beta_and_noise(stock_close: pd.Series, asi: pd.Series, horizon: int) -> tuple[float, float]:
    joined = pd.concat([stock_close, asi], axis=1, join="inner").dropna()

    stock_returns = np.log(joined.iloc[::horizon, 0]).diff().dropna()

    market_returns = np.log(joined.iloc[::horizon, 1]).diff().dropna()

    keep = stock_returns.abs() < CORPORATE_ACTION_RETURN * np.sqrt(horizon)

    stock_returns = stock_returns[keep]

    market_returns = market_returns[keep]

    beta = float(np.cov(stock_returns, market_returns)[0, 1] / np.var(market_returns, ddof=1))

    residuals = stock_returns - beta * market_returns

    daily_noise = float(np.std(residuals) / np.sqrt(horizon))

    return beta, daily_noise


def market_statistics(asi: pd.Series) -> MarketStatistics:
    log_returns = np.log(asi).diff().dropna()

    monthly_volatility = log_returns.resample("ME").std()

    stormy_months = monthly_volatility > STORMY_MONTH_THRESHOLD * monthly_volatility.median()

    stormy_spells = spell_lengths(stormy_months.to_numpy())

    calm_spells = spell_lengths(~stormy_months.to_numpy())

    month_of_day = pd.DatetimeIndex(log_returns.index).to_period("M").to_timestamp("M")

    day_is_stormy = stormy_months.reindex(month_of_day).to_numpy()

    calm_volatility = float(log_returns[~day_is_stormy].std())

    stormy_volatility = float(log_returns[day_is_stormy].std())

    statistics: MarketStatistics = {
        "asi_daily_volatility_calm": calm_volatility,
        "asi_daily_volatility_stormy": stormy_volatility,
        "stormy_month_share": float(stormy_months.mean()),
        "mean_calm_spell_months": float(np.mean(calm_spells)),
        "mean_stormy_spell_months": float(np.mean(stormy_spells)),
        "stormy_volatility_multiplier": stormy_volatility / calm_volatility,
        "calm_to_stormy_daily": daily_switch_probability(float(np.mean(calm_spells))),
        "stormy_to_calm_daily": daily_switch_probability(float(np.mean(stormy_spells))),
    }

    return statistics


def basket_statistics(prices_by_symbol: dict[str, pd.DataFrame], sessions: pd.DatetimeIndex, asi: pd.Series, horizon: int) -> BasketStatistics:
    index = basket_index(prices_by_symbol, sessions)

    beta, daily_noise = beta_and_noise(index, asi, horizon=horizon)

    statistics: BasketStatistics = {
        "beta_to_asi": beta,
        "members": len(prices_by_symbol),
        "symbols": sorted(prices_by_symbol),
        "daily_idiosyncratic_volatility": daily_noise,
        "measured_on": f"non-overlapping {horizon}-session returns",
        "weighting": "equal weight, daily rebalanced, corporate-action jumps over 25% set to zero",
    }

    return statistics


def bank_daily_value(data_dir: Path, sessions: pd.DatetimeIndex) -> BankLiquidity:
    prices = load_prices(data_dir, BANK_SYMBOL, sessions)

    if prices is None:
        raise SystemExit(f"No pinned price file for {BANK_SYMBOL}")

    traded_value = prices["close_price"] * prices["volume"]

    liquidity: BankLiquidity = {"symbol": BANK_SYMBOL, "median_daily_value_naira": float(traded_value.median())}

    return liquidity


def rounded(value: object) -> object:
    if isinstance(value, float):
        return float(f"{value:.6g}")

    if isinstance(value, dict):
        rounded_values: dict[str, object] = {}

        for key, item in value.items():
            rounded_values[key] = rounded(item)

        return rounded_values

    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate ThinBook Pension from NGX data.")

    parser.add_argument("--data-dir", type=Path, required=True)

    arguments = parser.parse_args()

    data_dir = arguments.data_dir.expanduser()

    asi = load_asi(data_dir)

    sessions = pd.DatetimeIndex(asi.index)

    small_caps = pick_small_caps(data_dir, sessions)

    banks: dict[str, pd.DataFrame] = {}

    for symbol in BANK_BASKET:
        prices = load_prices(data_dir, symbol, sessions)

        if prices is not None:
            banks[symbol] = prices

    small_caps_basket = basket_statistics(small_caps, sessions, asi, horizon=BETA_HORIZON_SESSIONS)

    small_caps_basket.pop("symbols")

    calibration: Calibration = {
        "sessions": len(sessions),
        "generated_on": str(date.today()),
        "market_asi": market_statistics(asi),
        "small_caps_basket": small_caps_basket,
        "bank_liquidity": bank_daily_value(data_dir, sessions),
        "small_caps_liquidity": small_cap_liquidity(small_caps),
        "date_range": f"{asi.index[0].date()} to {asi.index[-1].date()}",
        "big_banks_basket": basket_statistics(banks, sessions, asi, horizon=1),
        "source": "NGX daily prices and ASI from the Kobo Terminal cache (fetch pinned to 2026-08-31); licensed, raw data not included",
        "rules": {
            "board_minimum_shares": BOARD_MINIMUM_SHARES,
            "small_caps": f"bottom third of NGX by market cap (REIT/closed-end board excluded), at least {MINIMUM_SESSIONS} sessions, at least one traded session (drops dormant or suspended names)",
            "drought_month": f"a month where the stock clears the 100,000-share rule on fewer than {DROUGHT_MONTH_THRESHOLD:.0%} of its usual share of days",
            "stormy_month": f"a month where ASI daily volatility is above {STORMY_MONTH_THRESHOLD}x the median month",
            "switch_probability": "1 / mean spell length in sessions (21 sessions per month)",
        },
    }

    OUTPUT_PATH.write_text(yaml.safe_dump(rounded(calibration), sort_keys=False, width=200), encoding="utf-8")

    print(yaml.safe_dump(rounded(calibration), sort_keys=False, width=200))


if __name__ == "__main__":
    main()
