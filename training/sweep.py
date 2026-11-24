"""
Run the hyperparameter sweep: every config in configs/sweeps/*.yaml, several at a time.

1. Read the configs for the chosen algorithms (and an optional slice such as --configs 0-4).
2. Skip every run whose summary already exists, so the sweep can be stopped and restarted
   (and slices run on Colab can be merged back by copying their files in).
3. Run the rest as separate processes, --workers at a time, 1,000,000 frames each by default.
   Every run uses the same frozen game, the same validation seeds for checkpoint choice and
   the same held-out seeds for its final score.
4. --status prints what is done, running and pending, with a rough time left.

Outputs per run: logs/sweep/<algorithm>/<name>_{training,episodes,summary,console}.*
and models/<pg|dqn>/<name>_{best,final}.pt.

Run from the project root:
uv run python -m training.sweep --algo all --workers 6
uv run python -m training.sweep --status
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import yaml

from custom_types import RunPaths, RunSummary, SweepRow
from training.common import PROJECT_ROOT

SWEEP_DIR = PROJECT_ROOT / "configs" / "sweeps"

LOGS_ROOT = PROJECT_ROOT / "logs" / "sweep"

ALGORITHMS = ["ppo", "a2c", "reinforce", "dqn"]

DEFAULT_FRAMES = 1_000_000

DEFAULT_WORKERS = 6

RUNNING_WINDOW_SECONDS = 600


def load_configs(algorithm: str) -> list[SweepRow]:
    rows: list[SweepRow] = yaml.safe_load((SWEEP_DIR / f"{algorithm}.yaml").read_text(encoding="utf-8"))

    return rows


def pick_slice(rows: list[SweepRow], configs: str) -> list[SweepRow]:
    if configs == "all":
        return rows

    if "-" in configs:
        first, last = configs.split("-")

        return rows[int(first):int(last) + 1]

    return [rows[int(configs)]]


def run_name(row: SweepRow, seed: int) -> str:
    if seed == 0:
        return str(row["name"])

    return f"{row['name']}_seed{seed}"


def run_paths(algorithm: str, name: str) -> RunPaths:
    log_dir = LOGS_ROOT / algorithm

    paths: RunPaths = {
        "log_dir": log_dir,
        "summary": log_dir / f"{name}_summary.json",
        "training": log_dir / f"{name}_training.csv",
        "console": log_dir / f"{name}_console.log",
        "model_dir": PROJECT_ROOT / "models" / ("dqn" if algorithm == "dqn" else "pg"),
    }

    return paths


def flag_value(value: str | int | float | bool) -> str:
    if value is True:
        return "on"

    if value is False:
        return "off"

    return str(value)


def build_command(algorithm: str, row: SweepRow, name: str, frames: int, seed: int) -> list[str]:
    paths = run_paths(algorithm, name)

    module = "training.dqn_training" if algorithm == "dqn" else "training.pg_training"

    command = [sys.executable, "-m", module, "--name", name, "--frames", str(frames), "--seed", str(seed)]

    command = command + ["--log-dir", str(paths["log_dir"]), "--model-dir", str(paths["model_dir"])]

    if algorithm != "dqn":
        command = command + ["--algorithm", algorithm]

    for key, value in row.items():
        if key == "name":
            continue

        command = command + [f"--{key.replace('_', '-')}", flag_value(value)]

    return command


def run_one(algorithm: str, row: SweepRow, frames: int, seed: int) -> None:
    name = run_name(row, seed)

    paths = run_paths(algorithm, name)

    paths["log_dir"].mkdir(parents=True, exist_ok=True)

    command = build_command(algorithm, row, name, frames, seed)

    started = time.time()

    print(f"{time.strftime('%H:%M:%S')} start  {algorithm}/{name}", flush=True)

    console = open(paths["console"], "w", encoding="utf-8")

    environment = dict(os.environ)

    environment["RL_WARNINGS"] = "False"

    finished = subprocess.run(command, stdout=console, stderr=subprocess.STDOUT, cwd=PROJECT_ROOT, env=environment)

    console.close()

    minutes = (time.time() - started) / 60

    if finished.returncode != 0 or not paths["summary"].exists():
        print(f"{time.strftime('%H:%M:%S')} FAILED {algorithm}/{name} after {minutes:.0f} min, see {paths['console']}", flush=True)

        return

    summary: RunSummary = json.loads(paths["summary"].read_text(encoding="utf-8"))

    card = summary["held_out"]

    print(
        f"{time.strftime('%H:%M:%S')} done   {algorithm}/{name} in {minutes:.0f} min: won {card['win_rate']:.1%}, points {card['mean_points']:.1f}, "
        f"cost {card['mean_cost_bps']:.1f} bps, forced {card['forced_sale_rate']:.1%}, invalid/game {card['invalid_actions_per_game']:.1f}",
        flush=True,
    )


def planned_runs(algorithms: list[str], configs: str, seed: int) -> list[tuple[str, SweepRow]]:
    runs: list[tuple[str, SweepRow]] = []

    for algorithm in algorithms:
        for row in pick_slice(load_configs(algorithm), configs):
            runs.append((algorithm, row))

    return runs


def print_status(algorithms: list[str], configs: str, seed: int, workers: int) -> None:
    done_seconds: list[float] = []

    pending = 0

    print(f"{'run':<28}{'state':<10}{'progress':>22}")

    for algorithm, row in planned_runs(algorithms, configs, seed):
        name = run_name(row, seed)

        paths = run_paths(algorithm, name)

        if paths["summary"].exists():
            summary: RunSummary = json.loads(paths["summary"].read_text(encoding="utf-8"))

            done_seconds.append(summary["seconds"])

            card = summary["held_out"]

            print(f"{algorithm + '/' + name:<28}{'done':<10}{'won ' + format(card['win_rate'], '.1%') + ', ' + format(card['mean_points'], '.1f') + ' pts':>22}")

            continue

        recently_active = paths["training"].exists() and time.time() - paths["training"].stat().st_mtime < RUNNING_WINDOW_SECONDS

        if recently_active:
            lines = paths["training"].read_text(encoding="utf-8").strip().splitlines()

            frames = lines[-1].split(",")[1] if len(lines) > 1 else "0"

            print(f"{algorithm + '/' + name:<28}{'running':<10}{frames + ' frames':>22}")

            pending = pending + 1

            continue

        print(f"{algorithm + '/' + name:<28}{'pending':<10}{'':>22}")

        pending = pending + 1

    if done_seconds:
        average_minutes = sum(done_seconds) / len(done_seconds) / 60

        hours_left = pending * average_minutes / workers / 60

        print(f"\n{len(done_seconds)} done (average {average_minutes:.0f} min per run), {pending} left: about {hours_left:.1f} h with {workers} workers")

    else:
        print(f"\n0 done, {pending} left")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ThinBook Pension hyperparameter sweep.")

    parser.add_argument("--algo", default="all", choices=ALGORITHMS + ["all"])

    parser.add_argument("--configs", default="all", help="all, one index (3) or a range (0-4) within each algorithm's list")

    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)

    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)

    parser.add_argument("--seed", type=int, default=0, help="training seed; runs with a non-zero seed get a _seedN suffix")

    parser.add_argument("--status", action="store_true", help="print progress and exit")

    parser.add_argument("--dry-run", action="store_true", help="print the commands and exit")

    arguments = parser.parse_args()

    algorithms = ALGORITHMS if arguments.algo == "all" else [arguments.algo]

    if arguments.status:
        print_status(algorithms, arguments.configs, arguments.seed, arguments.workers)

        return

    to_run: list[tuple[str, SweepRow]] = []

    for algorithm, row in planned_runs(algorithms, arguments.configs, arguments.seed):
        name = run_name(row, arguments.seed)

        if run_paths(algorithm, name)["summary"].exists():
            print(f"skip   {algorithm}/{name} (summary exists)")

            continue

        to_run.append((algorithm, row))

    if arguments.dry_run:
        for algorithm, row in to_run:
            print(" ".join(build_command(algorithm, row, run_name(row, arguments.seed), arguments.frames, arguments.seed)))

        return

    print(f"{len(to_run)} runs to do, {arguments.workers} at a time, {arguments.frames:,} frames each", flush=True)

    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        for algorithm, row in to_run:
            pool.submit(run_one, algorithm, row, arguments.frames, arguments.seed)

    print(f"{time.strftime('%H:%M:%S')} sweep finished. Report tables: uv run python -m training.sweep_report", flush=True)


if __name__ == "__main__":
    main()
