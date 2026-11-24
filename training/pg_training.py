"""
Policy-gradient training for ThinBook Pension with TorchRL: PPO, A2C and REINFORCE.

1. Wrap the frozen env for TorchRL (training/common.py). The env reports raw points; one
   training-only scale factor shrinks the reward the learner sees.
2. Collect rollouts and compute advantages with GAE:
   - PPO: clipped loss, several epochs of minibatches per rollout.
   - A2C: one update per short rollout.
   - REINFORCE: Monte-Carlo returns (GAE with lambda = 1), one update per batch of whole games.
     With --baseline on, a learned value is subtracted; with --baseline off the value is zero.
   Advantages are normalised per batch for all three.
3. Every few batches, play the greedy policy on the validation seeds and keep the checkpoint
   with the best win rate (mean points break ties). The final weights are saved too.
4. Score the best checkpoint on the held-out seeds and write the summary.

Outputs (in --log-dir): <name>_training.csv, <name>_episodes.csv, <name>_summary.json.
Models (in --model-dir): <name>_best.pt and <name>_final.pt.

Run from the project root:
uv run python -m training.pg_training --name ppo_test --algorithm ppo --frames 300000
"""

import argparse
import csv
import json
import time
from pathlib import Path

import torch
from tensordict import TensorDict, TensorDictBase
from tensordict.nn import TensorDictModule
from torch import nn
from torch.distributions import Categorical
from torchrl.collectors import SyncDataCollector
from torchrl.modules import ProbabilisticActor, ValueOperator
from torchrl.objectives import A2CLoss, ClipPPOLoss, LossModule, ReinforceLoss
from torchrl.objectives.value import GAE

from classes import EpisodeLogger, ThinBookPensionEnv, ZeroValue
from custom_types import PgSettings, PolicyUpdate, RunSummary, Scorecard
from environment.custom_env import load_config
from training.common import (
    DEVICE,
    PROJECT_ROOT,
    held_out_scorecard,
    is_better,
    make_network,
    make_training_env,
    score_network,
    validation_seeds,
)

DEFAULT_LOG_DIR = PROJECT_ROOT / "logs" / "runs"

DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "pg"

EVALUATE_EVERY_FRAMES = 24_000

MAX_GRADIENT_NORM = 0.5


def policy_entropy(logits_network: nn.Module, data: TensorDictBase) -> torch.Tensor:
    logits = logits_network(data["observation"])

    return Categorical(logits=logits).entropy().mean()


def make_loss(arguments: argparse.Namespace, actor: ProbabilisticActor, critic: ValueOperator) -> LossModule:
    if arguments.algorithm == "a2c":
        return A2CLoss(actor_network=actor, critic_network=critic, entropy_coef=arguments.entropy, critic_coef=arguments.value_coefficient)

    if arguments.algorithm == "reinforce":
        return ReinforceLoss(actor_network=actor, critic_network=critic)

    return ClipPPOLoss(
        actor_network=actor,

        critic_network=critic,

        clip_epsilon=arguments.clip,

        entropy_coef=arguments.entropy,

        critic_coef=arguments.value_coefficient,
    )


def make_critic(arguments: argparse.Namespace) -> ValueOperator:
    no_baseline = arguments.algorithm == "reinforce" and arguments.baseline == "off"

    if no_baseline:
        return ValueOperator(ZeroValue(), in_keys=["observation"])

    return ValueOperator(make_network(1, arguments.hidden_size), in_keys=["observation"])


def update_policy(arguments: argparse.Namespace, batch: TensorDictBase, advantage_module: GAE, loss_module: LossModule, optimizer: torch.optim.Optimizer, logits_network: nn.Module) -> PolicyUpdate:
    epochs = arguments.epochs if arguments.algorithm == "ppo" else 1

    minibatch_size = arguments.minibatch if arguments.algorithm == "ppo" else arguments.rollout

    losses: TensorDictBase = TensorDict({}, batch_size=[])

    for _ in range(epochs):
        with torch.no_grad():
            advantage_module(batch)

        flat_batch = batch.reshape(-1)

        order = torch.randperm(flat_batch.numel())

        for start in range(0, flat_batch.numel(), minibatch_size):
            minibatch = flat_batch[order[start:start + minibatch_size]]

            losses = loss_module(minibatch)

            loss_terms: list[torch.Tensor] = []

            for key, value in losses.items():
                if key.startswith("loss_"):
                    loss_terms.append(value)

            total_loss = torch.stack(loss_terms).sum()

            if arguments.algorithm == "reinforce":
                total_loss = total_loss - arguments.entropy * policy_entropy(logits_network, minibatch)

            optimizer.zero_grad()

            total_loss.backward()

            torch.nn.utils.clip_grad_norm_(loss_module.parameters(), MAX_GRADIENT_NORM)

            optimizer.step()

    policy_loss = losses["loss_objective"] if "loss_objective" in losses.keys() else losses["loss_actor"]

    value_loss = losses["loss_critic"] if "loss_critic" in losses.keys() else losses["loss_value"]

    with torch.no_grad():
        entropy = float(policy_entropy(logits_network, batch.reshape(-1)))

    update: PolicyUpdate = {"policy_loss": float(policy_loss), "value_loss": float(value_loss), "entropy": entropy}

    return update


def train(arguments: argparse.Namespace) -> RunSummary:
    torch.manual_seed(arguments.seed)

    torch.set_num_threads(arguments.threads)

    config = load_config()

    log_dir = Path(arguments.log_dir)

    model_dir = Path(arguments.model_dir)

    log_dir.mkdir(parents=True, exist_ok=True)

    model_dir.mkdir(parents=True, exist_ok=True)

    env = make_training_env(arguments.seed, arguments.reward_scale, config)

    action_count = len(ThinBookPensionEnv(config).action_names)

    logits_network = make_network(action_count, arguments.hidden_size)

    actor = ProbabilisticActor(
        module=TensorDictModule(logits_network, in_keys=["observation"], out_keys=["logits"]),

        in_keys=["logits"],

        spec=env.action_spec,

        distribution_class=Categorical,

        return_log_prob=True,
    )

    critic = make_critic(arguments)

    gae_lambda = 1.0 if arguments.algorithm == "reinforce" else arguments.gae_lambda

    advantage_module = GAE(gamma=arguments.gamma, lmbda=gae_lambda, value_network=critic, average_gae=True)

    loss_module = make_loss(arguments, actor, critic)

    optimizer = torch.optim.Adam(loss_module.parameters(), lr=arguments.learning_rate)

    collector = SyncDataCollector(env, actor, frames_per_batch=arguments.rollout, total_frames=arguments.frames, device=DEVICE)

    episode_logger = EpisodeLogger(log_dir / f"{arguments.name}_episodes.csv")

    training_file = open(log_dir / f"{arguments.name}_training.csv", "w", newline="", encoding="utf-8")

    training_writer = csv.writer(training_file)

    training_writer.writerow(["batch", "frames", "entropy", "policy_loss", "value_loss", "validation_win_rate", "validation_mean_points", "seconds"])

    best_card: Scorecard | None = None

    best_frames = 0

    frames_done = 0

    next_evaluation = 0

    start_time = time.time()

    for batch_index, batch in enumerate(collector):
        episode_logger.log_batch(batch, frames_done)

        frames_done = frames_done + batch.numel()

        update = update_policy(arguments, batch, advantage_module, loss_module, optimizer, logits_network)

        collector.update_policy_weights_()

        validation_card: Scorecard | None = None

        if frames_done >= next_evaluation or frames_done >= arguments.frames:
            next_evaluation = next_evaluation + EVALUATE_EVERY_FRAMES

            validation_card = score_network(logits_network, config, validation_seeds())

            if is_better(validation_card, best_card):
                best_card = validation_card

                best_frames = frames_done

                torch.save(logits_network.state_dict(), model_dir / f"{arguments.name}_best.pt")

            print(f"[{arguments.name}] frames {frames_done:>8} entropy {update['entropy']:.3f} validation win {validation_card['win_rate']:.1%} points {validation_card['mean_points']:.1f} ({time.time() - start_time:.0f}s)", flush=True)

        training_writer.writerow([
            batch_index,
            frames_done,
            round(update["entropy"], 4),
            round(update["policy_loss"], 5),
            round(update["value_loss"], 5),
            round(validation_card["win_rate"] if validation_card is not None else float("nan"), 4),
            round(validation_card["mean_points"] if validation_card is not None else float("nan"), 3),
            round(time.time() - start_time, 1),
        ])

        training_file.flush()

    training_file.close()

    episode_logger.close()

    collector.shutdown()

    torch.save(logits_network.state_dict(), model_dir / f"{arguments.name}_final.pt")

    held_out = held_out_scorecard(make_network(action_count, arguments.hidden_size), model_dir / f"{arguments.name}_best.pt", config)

    settings: PgSettings = {
        "name": arguments.name,
        "clip": arguments.clip,
        "seed": arguments.seed,
        "gamma": arguments.gamma,
        "frames": arguments.frames,
        "epochs": arguments.epochs,
        "rollout": arguments.rollout,
        "entropy": arguments.entropy,
        "threads": arguments.threads,
        "baseline": arguments.baseline,
        "algorithm": arguments.algorithm,
        "minibatch": arguments.minibatch,
        "gae_lambda": arguments.gae_lambda,
        "hidden_size": arguments.hidden_size,
        "reward_scale": arguments.reward_scale,
        "learning_rate": arguments.learning_rate,
        "value_coefficient": arguments.value_coefficient,
    }

    summary: RunSummary = {
        "settings": settings,
        "held_out": held_out,
        "name": arguments.name,
        "frames": frames_done,
        "best_frames": best_frames,
        "validation_best": best_card,
        "algorithm": arguments.algorithm,
        "episodes": episode_logger.episodes,
        "seconds": round(time.time() - start_time, 1),
    }

    (log_dir / f"{arguments.name}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PPO, A2C or REINFORCE for ThinBook Pension.")

    parser.add_argument("--name", required=True)

    parser.add_argument("--algorithm", choices=["ppo", "a2c", "reinforce"], default="ppo")

    parser.add_argument("--frames", type=int, default=1_000_000)

    parser.add_argument("--learning-rate", type=float, default=1e-3)

    parser.add_argument("--rollout", type=int, default=2400)

    parser.add_argument("--minibatch", type=int, default=240)

    parser.add_argument("--epochs", type=int, default=4)

    parser.add_argument("--entropy", type=float, default=0.01)

    parser.add_argument("--gae-lambda", type=float, default=0.95)

    parser.add_argument("--clip", type=float, default=0.2)

    parser.add_argument("--gamma", type=float, default=0.995)

    parser.add_argument("--value-coefficient", type=float, default=0.5)

    parser.add_argument("--baseline", choices=["on", "off"], default="on", help="REINFORCE only: subtract a learned value baseline")

    parser.add_argument("--hidden-size", type=int, default=128)

    parser.add_argument("--reward-scale", type=float, default=0.1)

    parser.add_argument("--seed", type=int, default=0)

    parser.add_argument("--threads", type=int, default=1)

    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))

    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))

    return parser


def main() -> None:
    arguments = build_parser().parse_args()

    summary = train(arguments)

    print(json.dumps(summary["held_out"], indent=2))


if __name__ == "__main__":
    main()
