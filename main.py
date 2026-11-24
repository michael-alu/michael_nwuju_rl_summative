"""
ThinBook Pension entry point.

Commands available so far:
1. episode: play one game with a baseline (or the perfect-foresight planner) and print every trading day.
2. baselines: evaluate every baseline and the perfect-foresight planner on held-out seeds.
3. design-checks: run the structural design checks.
4. sweep: run the hyperparameter sweep (options are passed to training/sweep.py).
5. sweep-report: build the report tables from the finished sweep runs.

Run from the project root: uv run main.py episode --policy block_dealer --seed 100000
"""

import argparse
import runpy
import sys

from classes import PerfectForesightPlanner, Policy
from environment import baselines
from environment.custom_env import load_config
from classes import ThinBookPensionEnv
from environment.policy_helpers import read_step_info
from environment.rendering import DAY_HEADER, format_day_line, format_game_summary

DEFAULT_SEED = 100_000


def run_episode(policy_name: str, seed: int) -> None:
    config = load_config()

    policies: dict[str, Policy] = {}

    for policy in baselines.simple_baselines(config) + [PerfectForesightPlanner(config)]:
        policies[policy.name] = policy

    policy = policies[policy_name]

    env = ThinBookPensionEnv(config)

    observation, raw_info = env.reset(seed=seed)

    info = read_step_info(raw_info)

    policy.reset(env)

    print(f"ThinBook Pension, policy {policy_name}, seed {seed}. Pension fund N{info['observed_value_naira']:,.0f}, {config['horizon_days']} trading days.")

    print(f"PenCom-style limits (not the exact PenCom figures): small caps at most {config['small_caps_max_share']:.0%}, banks {config['banks_min_share']:.0%}-{config['banks_max_share']:.0%}. Money in naira millions at board prices.\n")

    print(DAY_HEADER)

    finished = False

    while not finished:
        observation, _, finished, _, raw_info = env.step(policy.act(observation, info))

        info = read_step_info(raw_info)

        print(format_day_line(info, config["small_caps_median_volume"]))

    print(f"\n{format_game_summary(info)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ThinBook Pension.")

    commands = parser.add_subparsers(dest="command")

    episode_parser = commands.add_parser("episode", help="Play one game with a baseline policy.")

    episode_parser.add_argument("--policy", default="block_dealer")

    episode_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)

    commands.add_parser("baselines", help="Evaluate the baselines and the perfect-foresight planner.")

    commands.add_parser("design-checks", help="Run the structural design checks.")

    commands.add_parser("sweep", help="Run the hyperparameter sweep, e.g. --algo dqn --workers 6.")

    commands.add_parser("sweep-report", help="Build the report tables from the sweep summaries.")

    arguments, extra_options = parser.parse_known_args()

    if arguments.command == "episode":
        run_episode(arguments.policy, arguments.seed)

    elif arguments.command == "baselines":
        baselines.main()

    elif arguments.command == "design-checks":
        runpy.run_path("scripts/design_checks.py", run_name="__main__")

    elif arguments.command == "sweep":
        from training import sweep

        sys.argv = ["sweep"] + extra_options

        sweep.main()

    elif arguments.command == "sweep-report":
        from training import sweep_report

        sweep_report.main()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
