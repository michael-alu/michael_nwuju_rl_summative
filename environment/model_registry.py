"""
Finds and loads the players the game and the API can use.

1. Trained agents: for each algorithm, read the sweep summaries (logs/sweep/<algorithm>/*_summary.json)
   and pick the run with the best held-out win rate (mean points break ties). Its weights are
   models/<pg|dqn>/<run>_best.pt. Until the sweep has a PPO run, PPO falls back to
   models/pg/pension5_seed0_best.pt. Algorithms with no finished run are listed as "not trained yet".
2. Baselines: block_dealer, the perfect-foresight planner (it cheats: it sees the future) and random play.

Serialization path: a model is saved as torch.save(network.state_dict()). To rebuild it you need the
network shape: 15 observation numbers in, two hidden layers of settings["hidden_size"] (from the run's
summary), 5 action scores out (training/common.py make_network). Load with
network.load_state_dict(torch.load(path)) and feed it the observation described in docs/ENVIRONMENT.md.
"""

import csv
import json
from pathlib import Path

import torch
from torch import nn

from custom_types.model_entry import ModelEntry
from custom_types.run_summary import RunSummary
from custom_types.scorecard import Scorecard
from environment.custom_env import ACTION_NAMES
from training.common import PROJECT_ROOT, is_better, make_network

SWEEP_LOGS = PROJECT_ROOT / "logs" / "sweep"

FALLBACK_PPO_MODEL = PROJECT_ROOT / "models" / "pg" / "pension5_seed0_best.pt"

FALLBACK_PPO_SUMMARY = PROJECT_ROOT / "logs" / "ppo" / "pension5_seed0_summary.json"

FALLBACK_PPO_TABLE = PROJECT_ROOT / "report_tables" / "agents_vs_baselines_normal.csv"

FALLBACK_PPO_ROW = "pension5_seed0_best"

DEFAULT_HIDDEN_SIZE = 128

AGENT_PLAYERS = ["ppo", "dqn", "a2c", "reinforce"]

AGENT_NAMES = {"ppo": "PPO", "dqn": "DQN", "a2c": "A2C", "reinforce": "REINFORCE"}

BASELINE_ENTRIES: list[ModelEntry] = [
    {"player": "block_dealer", "label": "Block dealer (simple rule)", "kind": "baseline", "run_name": "", "source": "classes/block_dealer_policy.py", "held_out_win_rate": None, "held_out_mean_points": None, "hidden_size": 0, "available": True, "note": "the best simple rule"},
    {"player": "perfect_foresight", "label": "Perfect foresight (cheats: sees the future)", "kind": "planner", "run_name": "", "source": "classes/perfect_foresight_planner.py", "held_out_win_rate": None, "held_out_mean_points": None, "hidden_size": 0, "available": True, "note": "an analysis tool, never trained"},
    {"player": "random", "label": "Random (any action, uniformly)", "kind": "random", "run_name": "", "source": "classes/random_policy.py", "held_out_win_rate": None, "held_out_mean_points": None, "hidden_size": 0, "available": True, "note": "random play"},
]


def model_path(algorithm: str, run_name: str) -> Path:
    folder = "dqn" if algorithm == "dqn" else "pg"

    return PROJECT_ROOT / "models" / folder / f"{run_name}_best.pt"


def read_summary(path: Path) -> RunSummary:
    summary: RunSummary = json.loads(path.read_text(encoding="utf-8"))

    return summary


def best_sweep_run(algorithm: str) -> RunSummary | None:
    best: RunSummary | None = None

    best_card: Scorecard | None = None

    for summary_path in sorted((SWEEP_LOGS / algorithm).glob("*_summary.json")):
        summary = read_summary(summary_path)

        if not model_path(algorithm, summary["name"]).exists():
            continue

        if is_better(summary["held_out"], best_card):
            best = summary

            best_card = summary["held_out"]

    return best


def fallback_ppo_entry() -> ModelEntry:
    win_rate = 0.0

    mean_points = 0.0

    table_file = open(FALLBACK_PPO_TABLE, encoding="utf-8")

    for row in csv.DictReader(table_file):
        if row["Policy"] == FALLBACK_PPO_ROW:
            win_rate = float(row["Win rate"].rstrip("%")) / 100

            mean_points = float(row["Mean points"])

    table_file.close()

    settings = json.loads(FALLBACK_PPO_SUMMARY.read_text(encoding="utf-8"))["settings"]

    entry: ModelEntry = {
        "player": "ppo",
        "label": f"Best PPO (pension5_seed0, wins {win_rate:.1%})",
        "kind": "agent",
        "run_name": "pension5_seed0",
        "source": str(FALLBACK_PPO_MODEL.relative_to(PROJECT_ROOT)),
        "held_out_win_rate": win_rate,
        "held_out_mean_points": mean_points,
        "hidden_size": settings["hidden_size"],
        "available": True,
        "note": "fallback until the sweep has a PPO run",
    }

    return entry


def agent_entry(algorithm: str) -> ModelEntry:
    name = AGENT_NAMES[algorithm]

    summary = best_sweep_run(algorithm)

    if summary is None and algorithm == "ppo" and FALLBACK_PPO_MODEL.exists():
        return fallback_ppo_entry()

    if summary is None:
        missing: ModelEntry = {"player": algorithm, "label": f"Best {name} (not trained yet)", "kind": "agent", "run_name": "", "source": "", "held_out_win_rate": None, "held_out_mean_points": None, "hidden_size": DEFAULT_HIDDEN_SIZE, "available": False, "note": "not trained yet"}

        return missing

    card = summary["held_out"]

    path = model_path(algorithm, summary["name"])

    entry: ModelEntry = {
        "player": algorithm,
        "label": f"Best {name} ({summary['name']}, wins {card['win_rate']:.1%})",
        "kind": "agent",
        "run_name": summary["name"],
        "source": str(path.relative_to(PROJECT_ROOT)),
        "held_out_win_rate": card["win_rate"],
        "held_out_mean_points": card["mean_points"],
        "hidden_size": summary["settings"]["hidden_size"],
        "available": True,
        "note": "best sweep run",
    }

    return entry


def list_players() -> list[ModelEntry]:
    entries: list[ModelEntry] = []

    for algorithm in AGENT_PLAYERS:
        entries.append(agent_entry(algorithm))

    for baseline in BASELINE_ENTRIES:
        entries.append(baseline)

    return entries


def load_network(entry: ModelEntry) -> nn.Sequential:
    network = make_network(len(ACTION_NAMES), entry["hidden_size"])

    network.load_state_dict(torch.load(PROJECT_ROOT / entry["source"]))

    network.eval()

    return network


def best_agent(entries: list[ModelEntry]) -> str:
    best_player = ""

    best_win_rate = -1.0

    for entry in entries:
        win_rate = entry["held_out_win_rate"]

        if entry["kind"] == "agent" and entry["available"] and win_rate is not None and win_rate > best_win_rate:
            best_player = entry["player"]

            best_win_rate = win_rate

    if best_player == "":
        return "block_dealer"

    return best_player
