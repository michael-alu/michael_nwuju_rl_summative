"""
Shows ThinBook Pension games to a person: a terminal view and a three.js browser game with an API.

1. Terminal: one line per trading day (format_day_line for main.py episode, format_live_line for the
   browser game) and a summary block at the end.
2. Plain words: what the agent did today and why a game was won or lost, for people with no finance
   background.
3. Server (FastAPI + uvicorn): the browser game at /, a WebSocket that streams a game day by day
   (/ws/game), and a REST API (/health, /models, /act, /episode) documented at /docs.
4. play_main: the command behind uv run main.py and uv run play.py.

The server only reads the env (to_json_state and the info dict); it never changes the game.

Run from the project root: uv run play.py --player ppo --seed 100000 --speed slow
"""

import argparse
import asyncio
import json
import threading
import webbrowser
from pathlib import Path

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from torch import nn

from classes.block_dealer_policy import BlockDealerPolicy
from classes.game_session import GameSession
from classes.perfect_foresight_planner import PerfectForesightPlanner
from classes.policy import Policy
from classes.random_policy import RandomPolicy
from classes.thin_book_pension_env import ThinBookPensionEnv
from classes.torch_policy import TorchPolicy
from custom_types.act_request import ActRequest
from custom_types.act_response import ActResponse
from custom_types.day_message import DayMessage
from custom_types.episode_log import EpisodeLog
from custom_types.episode_request import EpisodeRequest
from custom_types.game_meta import GameMeta
from custom_types.game_preview import GamePreview
from custom_types.health_response import HealthResponse
from custom_types.json_state import JsonState
from custom_types.market_config import MarketConfig
from custom_types.meta_message import MetaMessage
from custom_types.model_entry import ModelEntry
from custom_types.models_response import ModelsResponse
from custom_types.step_info import StepInfo
from environment.custom_env import ACTION_NAMES, OBSERVATION_NAMES, WARM_UP_DAYS, load_config, load_hard_config
from environment.model_registry import best_agent, list_players, load_network

DAY_HEADER = (
    f"{'day':>3} {'action':<32}{'cash':>7}{'tbills':>7}{'banks':>7}{'small':>7}{'sc %':>6}"
    f"{'vol/norm':>9}{'stale':>6}{'pts':>7}{'cost bps':>9}  notes"
)

WEB_DIR = Path(__file__).resolve().parent / "web"

DEFAULT_PORT = 8000

DEFAULT_SEED = 100_000

DEFAULT_SPEED = "slow"

SPEEDS = {"slow": 2.5, "1": 1.0, "5": 0.2, "20": 0.05, "instant": 0.0}

MARKETS = ["normal", "hard"]

BROWSER_DELAY_SECONDS = 1.5

PAST_TENSE = {
    "Wait": "Waited",
    "Sell T-bills": "Sold T-bills",
    "Sell bank shares": "Sold bank shares",
    "Sell small-cap shares": "Sold small-cap shares",
    "Call a big buyer": "Called a big buyer",
}

INVALID_REASONS = {
    "Sell T-bills": "Tried to sell T-bills, but none were left",
    "Sell bank shares": "Tried to sell bank shares, but none were left",
    "Sell small-cap shares": "Tried to sell small-cap shares, but none were left",
    "Call a big buyer": "Tried to call a big buyer, but none was offered",
}

FORCED_REASONS = {
    "forced: payout": "forced into a fire sale to pay a retiree",
    "forced: payout, beyond volume cap": "forced into a fire sale to pay a retiree",
    "forced: small caps over limit": "forced to sell small caps after the limit grace ran out",
    "forced: banks over limit": "forced to sell bank shares after the limit grace ran out",
    "forced: banks below lower limit": "forced to buy bank shares after the limit grace ran out",
    "forced: raise cash for limit buy": "forced to buy bank shares after the limit grace ran out",
}

PAYOUT_LABELS = {"scheduled_retirement": "Retirement", "early_withdrawal": "Early withdrawal", "death_benefit": "Death benefit"}

PLAYERS: dict[str, ModelEntry] = {}

NETWORKS: dict[str, nn.Sequential] = {}

app = FastAPI(
    title="ThinBook Pension",
    description="Watch an agent run a Nigerian pension fund for 60 trading days, or call the agents from another app.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def short_naira(amount: float) -> str:
    return f"{amount / 1_000_000:.2f}m"


def naira(amount: float) -> str:
    if abs(amount) >= 999_500:
        return f"₦{amount / 1_000_000:.2f}M"

    if abs(amount) < 500:
        return "₦0"

    return f"₦{amount / 1_000:.0f}K"


def format_day_line(info: StepInfo, median_volume: float) -> str:
    notes: list[str] = []

    if info["invalid_action"]:
        notes.append("INVALID")

    for trade in info["trades"]:
        notes.append(f"{trade['reason']}: {trade['asset']} N{trade['proceeds']:,.0f} (cost N{trade['cost']:,.0f})")

    upcoming: list[str] = []

    for payout in info["known_payouts"]:
        kind = payout["kind"].replace("_", " ")

        upcoming.append(f"{kind} N{payout['amount'] / 1e6:.2f}m due d{payout['due_day']}")

    if upcoming:
        notes.append("known: " + ", ".join(upcoming))

    if info["in_breach"]:
        notes.append(f"OVER INVESTMENT LIMIT, grace {info['grace_days_left']}d")

    if info["big_buyer_offered_today"]:
        notes.append("big buyer offered")

    notes.append("[stormy]" if info["stormy"] else "[calm]")

    if info["drought"]:
        notes.append("[drought]")

    weights = info["weights"]

    line = (
        f"{info['day']:>3} {info['action_name']:<32}{short_naira(info['cash_naira'] + info['settling_naira']):>7}"
        f"{short_naira(info['tbills_naira']):>7}{short_naira(info['banks_naira']):>7}{short_naira(info['small_caps_naira_board']):>7}"
        f"{weights['small_caps']:>6.0%}{info['small_caps_volume_yesterday'] / median_volume:>9.2f}{info['small_caps_days_since_board_move']:>6}"
        f"{info['points_today']:>7.2f}{info['cost_bps']:>9.1f}  {'; '.join(notes)}"
    )

    return line


def format_game_summary(info: StepInfo) -> str:
    reason = f" ({info['outcome_reason']})" if info["outcome_reason"] else ""

    summary = (
        f"Outcome: {info['outcome'].upper()}{reason}. Selling cost {info['cost_bps']:.1f} bps of the starting fund, "
        f"paid to retirees and families N{info['paid_out_naira']:,.0f}, total points {info['total_points']:.1f}, forced events {len(info['forced_events'])}, invalid actions {info['invalid_actions']}."
    )

    return summary


def agent_filled_naira(state: JsonState) -> float:
    filled = 0.0

    for trade in state["trades"]:
        if trade["reason"] in ("agent", "big buyer"):
            filled = filled + trade["proceeds"]

    return filled


def had_forced_sale(state: JsonState) -> bool:
    for trade in state["trades"]:
        if trade["reason"].startswith("forced"):
            return True

    return False


def action_text(state: JsonState, config: MarketConfig) -> str:
    name = state["action_name"]

    if state["day"] == 0:
        return "Game starts: nothing sold yet"

    if state["invalid_action"]:
        reason = INVALID_REASONS.get(name, f"Tried to {name.lower()}, but could not")

        if name == "Call a big buyer" and state["big_buyer_offered_today"]:
            reason = "Tried to call a big buyer, but no small caps were left"

        return f"{reason}: counted as Wait, -{config['invalid_action_penalty']:.0f} point"

    text = PAST_TENSE[name]

    if name in ("Sell small-cap shares", "Call a big buyer") and agent_filled_naira(state) <= 0:
        text = text + " (nothing filled: nobody traded today)"

    return text


def first_forced_event(state: JsonState) -> tuple[int, str]:
    event = state["forced_events"][0]

    day_part, rest = event.split(": ", 1)

    reason = rest.rsplit(" (", 1)[0]

    return int(day_part.replace("day ", "")), reason


def outcome_text(state: JsonState, config: MarketConfig) -> str:
    line = config["won_cost_bps"]

    cost = state["cost_bps"]

    if state["outcome"] == "won":
        return f"Won: every retiree paid, no fire sales, selling cost {cost:.0f} bps, under the {line:.0f} bps line"

    if state["forced_events"]:
        day, reason = first_forced_event(state)

        what_happened = FORCED_REASONS.get(reason, "forced into a fire sale")

        return f"Lost: {what_happened} on day {day}"

    return f"Lost: selling cost {cost:.0f} bps, over the {line:.0f} bps line"


def next_payout_text(state: JsonState) -> str:
    if not state["known_payouts"]:
        return "no payout known"

    nearest = state["known_payouts"][0]

    for payout in state["known_payouts"]:
        if payout["due_day"] < nearest["due_day"]:
            nearest = payout

    days = nearest["due_day"] - state["day"]

    return f"{naira(nearest['amount'])} in {days} day{'s' if days != 1 else ''}"


def format_live_line(state: JsonState, config: MarketConfig) -> str:
    parts = [
        f"Day {state['day']:>2}",
        action_text(state, config),
        f"filled {naira(agent_filled_naira(state))}",
        f"cash {naira(state['cash_naira'])} (+{naira(state['settling_naira'])} tomorrow)",
        f"small caps {state['weights']['small_caps']:.1%} (limit {config['small_caps_max_share']:.0%})",
        f"payout due: {next_payout_text(state)}",
        f"points {state['points_today']:.2f}",
        f"total {state['total_points']:.2f}",
    ]

    if state["in_breach"]:
        parts.append(f"OVER THE LIMIT: {state['grace_days_left']} days to fix")

    if had_forced_sale(state):
        parts.append("FORCED SALE")

    return " | ".join(parts)


def format_live_summary(state: JsonState, config: MarketConfig) -> str:
    lines = [
        "",
        "=" * 72,
        outcome_text(state, config),
        f"Total points: {state['total_points']:.2f}",
        f"Selling cost: {state['cost_bps']:.1f} bps (win line {config['won_cost_bps']:.0f} bps)",
        f"Forced sales: {state['forced_event_count']}",
        f"Invalid actions: {state['invalid_actions']}",
        "=" * 72,
        "",
    ]

    return "\n".join(lines)


def numpy_value(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()

    raise TypeError(f"Cannot turn {type(value).__name__} into JSON")


def to_json_text(value: object) -> str:
    return json.dumps(value, default=numpy_value)


def load_players() -> None:
    if PLAYERS:
        return

    torch.set_num_threads(1)

    for entry in list_players():
        PLAYERS[entry["player"]] = entry

        if entry["kind"] == "agent" and entry["available"]:
            NETWORKS[entry["player"]] = load_network(entry)


def market_config(market: str) -> MarketConfig:
    if market == "hard":
        return load_hard_config()

    return load_config()


def check_game_request(player: str, market: str) -> str:
    load_players()

    if player not in PLAYERS:
        return f"Unknown player '{player}'. Choose one of: {', '.join(PLAYERS)}."

    if not PLAYERS[player]["available"]:
        return f"Player '{player}' is not trained yet."

    if market not in MARKETS:
        return f"Unknown market '{market}'. Choose normal or hard."

    return ""


def make_policy(player: str, config: MarketConfig) -> Policy:
    if player in NETWORKS:
        return TorchPolicy(NETWORKS[player])

    if player == "block_dealer":
        return BlockDealerPolicy(config)

    if player == "perfect_foresight":
        return PerfectForesightPlanner(config)

    return RandomPolicy()


def game_preview(env: ThinBookPensionEnv, config: MarketConfig) -> GamePreview:
    """
    What to expect from the game the env has just drawn: its payouts and the character of its market,
    counted over the trading days. For the viewer only; it reads the drawn game and changes nothing.
    """

    days = env.market[WARM_UP_DAYS:WARM_UP_DAYS + config["horizon_days"]]

    no_trade_days = 0

    dry_spell_days = 0

    stormy_days = 0

    big_buyer_days = 0

    for day in days:
        if day["small_caps_volume"] <= 0:
            no_trade_days = no_trade_days + 1

        if day["drought"]:
            dry_spell_days = dry_spell_days + 1

        if day["stormy"]:
            stormy_days = stormy_days + 1

        if day["big_buyer_offered"]:
            big_buyer_days = big_buyer_days + 1

    surprises = 0

    total = 0.0

    for payout in env.payouts:
        total = total + payout["amount"]

        if payout["kind"] != "scheduled_retirement":
            surprises = surprises + 1

    preview: GamePreview = {
        "payouts": len(env.payouts),
        "surprise_payouts": surprises,
        "payout_total_naira": total,
        "no_trade_days": no_trade_days,
        "dry_spell_days": dry_spell_days,
        "stormy_days": stormy_days,
        "big_buyer_days": big_buyer_days,
    }

    return preview


def game_meta(player: str, seed: int, market: str, config: MarketConfig, preview: GamePreview) -> GameMeta:
    meta: GameMeta = {
        "player": player,
        "player_label": PLAYERS[player]["label"],
        "seed": seed,
        "market": market,
        "horizon_days": config["horizon_days"],
        "fund_naira": config["starting_fund_naira"],
        "won_cost_bps": config["won_cost_bps"],
        "small_caps_max_share": config["small_caps_max_share"],
        "banks_min_share": config["banks_min_share"],
        "banks_max_share": config["banks_max_share"],
        "breach_grace_days": config["breach_grace_days"],
        "small_caps_median_volume": config["small_caps_median_volume"],
        "board_minimum_shares": config["board_minimum_shares"],
        "preview": preview,
    }

    return meta


def day_message(state: JsonState, config: MarketConfig, reward: float, finished: bool) -> DayMessage:
    message: DayMessage = {
        "type": "day",
        "state": state,
        "action_text": action_text(state, config),
        "reward": reward,
        "finished": finished,
        "outcome_text": outcome_text(state, config) if finished else "",
    }

    return message


def play_episode(player: str, seed: int, market: str) -> EpisodeLog:
    config = market_config(market)

    session = GameSession(make_policy(player, config), config, seed)

    final = session.start()

    preview = game_preview(session.env, config)

    days = [day_message(final, config, 0.0, False)]

    while not session.finished:
        final = session.step()

        days.append(day_message(final, config, session.last_reward, session.finished))

    log: EpisodeLog = {
        "meta": game_meta(player, seed, market, config, preview),
        "days": days,
        "outcome": final["outcome"],
        "outcome_text": outcome_text(final, config),
        "total_points": final["total_points"],
        "cost_bps": final["cost_bps"],
        "forced_sales": final["forced_event_count"],
        "invalid_actions": final["invalid_actions"],
    }

    return log


def softmax(scores: torch.Tensor) -> list[float]:
    probabilities = torch.softmax(scores, dim=-1)

    values: list[float] = []

    for value in probabilities:
        values.append(float(value))

    return values


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> HealthResponse:
    load_players()

    loaded: dict[str, str] = {}

    for player, entry in PLAYERS.items():
        if entry["kind"] == "agent" and entry["available"]:
            loaded[player] = entry["label"]

    answer: HealthResponse = {"status": "ok", "models": loaded}

    return answer


@app.get("/models")
def models() -> ModelsResponse:
    load_players()

    players: list[ModelEntry] = []

    for entry in PLAYERS.values():
        players.append(entry)

    answer: ModelsResponse = {"players": players, "observation_names": OBSERVATION_NAMES, "action_names": ACTION_NAMES}

    return answer


@app.post("/act", response_model=ActResponse)
def act(request: ActRequest) -> ActResponse:
    load_players()

    if len(request.observation) != len(OBSERVATION_NAMES):
        raise HTTPException(status_code=422, detail=f"observation must have {len(OBSERVATION_NAMES)} numbers (got {len(request.observation)}); see GET /models for the order.")

    for index_in_list, value in enumerate(request.observation):
        if not 0.0 <= value <= 1.0:
            raise HTTPException(status_code=422, detail=f"observation[{index_in_list}] ({OBSERVATION_NAMES[index_in_list]}) is {value}; every number must be between 0 and 1.")

    if request.player == "random":
        action_id = int(np.random.default_rng().integers(len(ACTION_NAMES)))

        uniform = [1.0 / len(ACTION_NAMES)] * len(ACTION_NAMES)

        return ActResponse(action_id=action_id, action_name=ACTION_NAMES[action_id], probabilities=uniform)

    if request.player not in NETWORKS:
        raise HTTPException(status_code=422, detail=f"player must be a trained agent ({', '.join(NETWORKS)}) or random; baselines need the full game state, use POST /episode.")

    with torch.no_grad():
        scores = NETWORKS[request.player](torch.tensor(request.observation, dtype=torch.float32))

    action_id = int(torch.argmax(scores).item())

    probabilities = None if request.player == "dqn" else softmax(scores)

    return ActResponse(action_id=action_id, action_name=ACTION_NAMES[action_id], probabilities=probabilities)


@app.post("/episode")
def episode(request: EpisodeRequest) -> JSONResponse:
    problem = check_game_request(request.player, request.market)

    if problem:
        raise HTTPException(status_code=422, detail=problem)

    log = play_episode(request.player, request.seed, request.market)

    return JSONResponse(content=json.loads(to_json_text(log)))


async def read_controls(websocket: WebSocket, controls: asyncio.Queue[dict[str, object]]) -> None:
    try:
        while True:
            message = await websocket.receive_json()

            await controls.put(message)

    except WebSocketDisconnect:
        await controls.put({"type": "closed"})


@app.websocket("/ws/game")
async def game_socket(websocket: WebSocket) -> None:
    await websocket.accept()

    request = await websocket.receive_json()

    player = str(request.get("player", "ppo"))

    market = str(request.get("market", "normal"))

    seed = int(request.get("seed", DEFAULT_SEED))

    speed = str(request.get("speed", DEFAULT_SPEED))

    pause_at = int(request.get("pause_at", 0))

    paused = bool(request.get("paused", False))

    problem = check_game_request(player, market)

    if problem:
        await websocket.send_text(to_json_text({"type": "error", "message": problem}))

        await websocket.close()

        return

    config = market_config(market)

    session = GameSession(make_policy(player, config), config, seed)

    state = session.start()

    meta: MetaMessage = {"type": "meta", "meta": game_meta(player, seed, market, config, game_preview(session.env, config))}

    await websocket.send_text(to_json_text(meta))

    await websocket.send_text(to_json_text(day_message(state, config, 0.0, False)))

    print(f"\nNew game: {PLAYERS[player]['label']}, seed {seed}, {market} market", flush=True)

    controls: asyncio.Queue[dict[str, object]] = asyncio.Queue()

    reader = asyncio.create_task(read_controls(websocket, controls))

    closed = False

    while not session.finished and not closed:
        step_once = False

        while not controls.empty() or (paused and not step_once):
            control = await controls.get()

            kind = control.get("type")

            if kind == "closed":
                closed = True

                break

            if kind == "pause":
                paused = True

            if kind == "play":
                paused = False

            if kind == "step":
                step_once = True

            if kind == "speed":
                speed = str(control.get("speed", speed))

        if closed:
            break

        state = session.step()

        await websocket.send_text(to_json_text(day_message(state, config, session.last_reward, session.finished)))

        print(format_live_line(state, config), flush=True)

        if pause_at and state["day"] == pause_at:
            paused = True

        if not paused:
            await asyncio.sleep(SPEEDS.get(speed, SPEEDS[DEFAULT_SPEED]))

    if session.finished:
        print(format_live_summary(state, config), flush=True)

    reader.cancel()

    if not closed:
        await websocket.close()


def build_play_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Watch an agent run the ThinBook Pension fund in the browser.")

    parser.add_argument("--player", default="", help="ppo, dqn, a2c, reinforce, block_dealer, perfect_foresight or random (default: the best trained agent)")

    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="which game; the same seed always draws the same game")

    parser.add_argument("--market", default="normal", choices=MARKETS)

    parser.add_argument("--speed", default=DEFAULT_SPEED, choices=list(SPEEDS))

    parser.add_argument("--no-browser", action="store_true", help="start the server without opening a browser")

    parser.add_argument("--port", type=int, default=DEFAULT_PORT)

    return parser


def print_startup(url: str, player: str) -> None:
    print("ThinBook Pension: watch the agent", flush=True)

    for entry in PLAYERS.values():
        if entry["kind"] != "agent":
            continue

        if entry["available"]:
            print(f"  loaded {entry['label']} from {entry['source']} ({entry['note']})", flush=True)

        else:
            print(f"  {entry['label']}", flush=True)

    print(f"Starting player: {PLAYERS[player]['label']}", flush=True)

    print(f"Open {url}", flush=True)

    print(f"API docs: {url.split('?')[0]}docs", flush=True)

    print("Press Ctrl+C to stop the server.", flush=True)


def play_main(argv: list[str]) -> None:
    arguments = build_play_parser().parse_args(argv)

    load_players()

    player = arguments.player if arguments.player else best_agent(list(PLAYERS.values()))

    problem = check_game_request(player, arguments.market)

    if problem:
        raise SystemExit(problem)

    url = f"http://127.0.0.1:{arguments.port}/?player={player}&seed={arguments.seed}&market={arguments.market}&speed={arguments.speed}&autoplay=1"

    print_startup(url, player)

    if not arguments.no_browser:
        threading.Timer(BROWSER_DELAY_SECONDS, webbrowser.open, args=[url]).start()

    uvicorn.run(app, host="127.0.0.1", port=arguments.port, log_level="warning")
