"""
Checks that the browser game's server works and shows the real game.

Starts the real FastAPI app with uvicorn on a free port (no browser, no training) and calls it the
way the browser and other apps do: REST with urllib, the game stream with a WebSocket.

Run from the project root: uv run pytest tests/test_server.py
"""

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import cast

import pytest
import torch
import uvicorn
from websockets.sync.client import connect

from classes import BlockDealerPolicy, ThinBookPensionEnv
from custom_types import DayMessage, EpisodeLog, MetaMessage
from custom_types.act_response import ActResponse
from custom_types.error_response import ErrorResponse
from custom_types.health_response import HealthResponse
from custom_types.models_response import ModelsResponse
from environment import rendering
from environment.baselines import play
from environment.custom_env import load_config

TEST_SEED = 100_000

START_TIMEOUT_SECONDS = 30

GOOD_OBSERVATION = [0.5, 0.15, 0.6, 0.43, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.3, 0.3, 0.2, 0.0]


def free_port() -> int:
    probe = socket.socket()

    probe.bind(("127.0.0.1", 0))

    port = probe.getsockname()[1]

    probe.close()

    return int(port)


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    torch.set_num_threads(1)

    port = free_port()

    server = uvicorn.Server(uvicorn.Config(rendering.app, host="127.0.0.1", port=port, log_level="warning"))

    thread = threading.Thread(target=server.run, daemon=True)

    thread.start()

    waited = 0.0

    while not server.started and waited < START_TIMEOUT_SECONDS:
        time.sleep(0.1)

        waited = waited + 0.1

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True

    thread.join(timeout=5)


def get_json(url: str) -> object:
    with urllib.request.urlopen(url) as response:
        body: object = json.loads(response.read())

    return body


def post_json(url: str, body: dict[str, object]) -> tuple[int, object]:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json"})

    try:
        with urllib.request.urlopen(request) as response:
            answer: object = json.loads(response.read())

            return response.status, answer

    except urllib.error.HTTPError as error:
        problem: object = json.loads(error.read())

        return error.code, problem


def test_health_and_models_respond(base_url: str) -> None:
    health = cast(HealthResponse, get_json(f"{base_url}/health"))

    models = cast(ModelsResponse, get_json(f"{base_url}/models"))

    players = []

    for entry in models["players"]:
        players.append(entry["player"])

    assert health["status"] == "ok"

    assert players == ["ppo", "dqn", "a2c", "reinforce", "block_dealer", "perfect_foresight", "random"]

    assert len(models["observation_names"]) == len(GOOD_OBSERVATION)


def test_act_returns_an_action_and_rejects_bad_observations(base_url: str) -> None:
    status, body = post_json(f"{base_url}/act", {"observation": GOOD_OBSERVATION, "player": "ppo"})

    short_status, _ = post_json(f"{base_url}/act", {"observation": GOOD_OBSERVATION[:3], "player": "ppo"})

    out_of_range = GOOD_OBSERVATION[:-1] + [3.0]

    range_status, range_body = post_json(f"{base_url}/act", {"observation": out_of_range, "player": "ppo"})

    answer = ActResponse.model_validate(body)

    problem = cast(ErrorResponse, range_body)

    assert status == 200

    assert 0 <= answer.action_id < 5

    assert answer.probabilities is not None

    assert abs(sum(answer.probabilities) - 1.0) < 1e-5

    assert short_status == 422

    assert range_status == 422

    assert "between 0 and 1" in problem["detail"]


def test_episode_shows_the_real_game(base_url: str) -> None:
    config = load_config()

    direct = play(ThinBookPensionEnv(config), BlockDealerPolicy(config), TEST_SEED)

    status, body = post_json(f"{base_url}/episode", {"player": "block_dealer", "seed": TEST_SEED, "market": "normal"})

    log = cast(EpisodeLog, body)

    assert status == 200

    assert len(log["days"]) == config["horizon_days"] + 1

    assert log["total_points"] == direct["total_points"]

    assert log["cost_bps"] == direct["cost_bps"]

    assert log["forced_sales"] == direct["forced_events"]

    rewards_added_up = 0.0

    for day in log["days"]:
        rewards_added_up = rewards_added_up + day["reward"]

    assert abs(rewards_added_up - direct["total_points"]) < 1e-9


def test_streamed_game_reaches_day_60_with_an_outcome(base_url: str) -> None:
    websocket_url = base_url.replace("http", "ws") + "/ws/game"

    with connect(websocket_url) as game:
        game.send(json.dumps({"player": "random", "seed": TEST_SEED, "market": "normal", "speed": "instant"}))

        first = cast(MetaMessage, json.loads(game.recv(timeout=10)))

        message = cast(DayMessage, json.loads(game.recv(timeout=10)))

        while not message["finished"]:
            message = cast(DayMessage, json.loads(game.recv(timeout=10)))

    assert first["type"] == "meta"

    assert message["state"]["day"] == 60

    assert message["state"]["outcome"] in ("won", "lost")

    assert message["outcome_text"].startswith(("Won", "Lost"))
