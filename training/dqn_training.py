"""
DQN for ThinBook Pension with TorchRL.

1. Wrap the frozen env for TorchRL (training/common.py), same reward scale as the other trainers.
2. A Q-network (two hidden layers) picks actions epsilon-greedily; epsilon falls linearly from
   its start to its end value over --epsilon-decay-frames.
3. Transitions go into a replay buffer. After a warm-up, each batch of new frames triggers
   several updates of the DQN loss (smooth L1 TD error), with a target network updated softly
   (tau) or hard (every N updates). TD loss is logged on every batch.
4. Every few batches the greedy policy plays the validation seeds; the best checkpoint (win
   rate, then mean points) is kept, the final weights are saved too, and the best checkpoint
   is scored on the held-out seeds.

Outputs (in --log-dir): <name>_training.csv, <name>_episodes.csv, <name>_summary.json.
Models (in --model-dir): <name>_best.pt and <name>_final.pt.

Run from the project root:
uv run python -m training.dqn_training --name dqn_test --frames 300000
"""

import argparse
import csv
import json
import time
from pathlib import Path

import torch
from tensordict.nn import TensorDictSequential
from torchrl.collectors import SyncDataCollector
from torchrl.data import LazyTensorStorage, TensorDictReplayBuffer
from torchrl.modules import EGreedyModule, QValueActor
from torchrl.objectives import DQNLoss, HardUpdate, SoftUpdate

from classes import EpisodeLogger, ThinBookPensionEnv
from custom_types import DqnSettings, RunSummary, Scorecard
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

DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "dqn"

EVALUATE_EVERY_FRAMES = 24_000

MAX_GRADIENT_NORM = 10.0


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

    q_network = make_network(action_count, arguments.hidden_size)

    actor = QValueActor(q_network, in_keys=["observation"], spec=env.action_spec)

    exploration = EGreedyModule(env.action_spec, eps_init=arguments.epsilon_start, eps_end=arguments.epsilon_end, annealing_num_steps=arguments.epsilon_decay_frames)

    exploring_policy = TensorDictSequential(actor, exploration)

    loss_module = DQNLoss(actor, delay_value=True, loss_function="smooth_l1")

    loss_module.make_value_estimator(gamma=arguments.gamma)

    target_updater: SoftUpdate | HardUpdate

    if arguments.target_update == "soft":
        target_updater = SoftUpdate(loss_module, tau=arguments.tau)

    else:
        target_updater = HardUpdate(loss_module, value_network_update_interval=arguments.hard_update_every)

    optimizer = torch.optim.Adam(loss_module.parameters(), lr=arguments.learning_rate)

    replay_buffer = TensorDictReplayBuffer(storage=LazyTensorStorage(arguments.buffer_size), batch_size=arguments.batch_size)

    collector = SyncDataCollector(env, exploring_policy, frames_per_batch=arguments.frames_per_batch, total_frames=arguments.frames, device=DEVICE, init_random_frames=arguments.warmup_frames)

    episode_logger = EpisodeLogger(log_dir / f"{arguments.name}_episodes.csv")

    training_file = open(log_dir / f"{arguments.name}_training.csv", "w", newline="", encoding="utf-8")

    training_writer = csv.writer(training_file)

    training_writer.writerow(["batch", "frames", "epsilon", "td_loss", "validation_win_rate", "validation_mean_points", "seconds"])

    best_card: Scorecard | None = None

    best_frames = 0

    frames_done = 0

    next_evaluation = 0

    td_loss = float("nan")

    start_time = time.time()

    for batch_index, batch in enumerate(collector):
        episode_logger.log_batch(batch, frames_done)

        frames_done = frames_done + batch.numel()

        replay_buffer.extend(batch.reshape(-1))

        exploration.step(batch.numel())

        if frames_done >= arguments.warmup_frames:
            for _ in range(arguments.updates_per_batch):
                losses = loss_module(replay_buffer.sample())

                optimizer.zero_grad()

                losses["loss"].backward()

                torch.nn.utils.clip_grad_norm_(loss_module.parameters(), MAX_GRADIENT_NORM)

                optimizer.step()

                target_updater.step()

                td_loss = float(losses["loss"])

        collector.update_policy_weights_()

        validation_card: Scorecard | None = None

        if frames_done >= next_evaluation or frames_done >= arguments.frames:
            next_evaluation = next_evaluation + EVALUATE_EVERY_FRAMES

            validation_card = score_network(q_network, config, validation_seeds())

            if is_better(validation_card, best_card):
                best_card = validation_card

                best_frames = frames_done

                torch.save(q_network.state_dict(), model_dir / f"{arguments.name}_best.pt")

            print(f"[{arguments.name}] frames {frames_done:>8} epsilon {float(exploration.eps):.3f} td loss {td_loss:.4f} validation win {validation_card['win_rate']:.1%} points {validation_card['mean_points']:.1f} ({time.time() - start_time:.0f}s)", flush=True)

        training_writer.writerow([
            batch_index,
            frames_done,
            round(float(exploration.eps), 4),
            round(td_loss, 5),
            round(validation_card["win_rate"] if validation_card is not None else float("nan"), 4),
            round(validation_card["mean_points"] if validation_card is not None else float("nan"), 3),
            round(time.time() - start_time, 1),
        ])

        training_file.flush()

    training_file.close()

    episode_logger.close()

    collector.shutdown()

    torch.save(q_network.state_dict(), model_dir / f"{arguments.name}_final.pt")

    held_out = held_out_scorecard(make_network(action_count, arguments.hidden_size), model_dir / f"{arguments.name}_best.pt", config)

    settings: DqnSettings = {
        "tau": arguments.tau,
        "name": arguments.name,
        "seed": arguments.seed,
        "gamma": arguments.gamma,
        "frames": arguments.frames,
        "threads": arguments.threads,
        "batch_size": arguments.batch_size,
        "buffer_size": arguments.buffer_size,
        "epsilon_end": arguments.epsilon_end,
        "hidden_size": arguments.hidden_size,
        "reward_scale": arguments.reward_scale,
        "warmup_frames": arguments.warmup_frames,
        "epsilon_start": arguments.epsilon_start,
        "learning_rate": arguments.learning_rate,
        "target_update": arguments.target_update,
        "frames_per_batch": arguments.frames_per_batch,
        "updates_per_batch": arguments.updates_per_batch,
        "hard_update_every": arguments.hard_update_every,
        "epsilon_decay_frames": arguments.epsilon_decay_frames,
    }

    summary: RunSummary = {
        "algorithm": "dqn",
        "settings": settings,
        "held_out": held_out,
        "frames": frames_done,
        "name": arguments.name,
        "best_frames": best_frames,
        "validation_best": best_card,
        "episodes": episode_logger.episodes,
        "seconds": round(time.time() - start_time, 1),
    }

    (log_dir / f"{arguments.name}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DQN for ThinBook Pension.")

    parser.add_argument("--name", required=True)

    parser.add_argument("--frames", type=int, default=1_000_000)

    parser.add_argument("--learning-rate", type=float, default=5e-4)

    parser.add_argument("--gamma", type=float, default=0.995)

    parser.add_argument("--batch-size", type=int, default=128)

    parser.add_argument("--buffer-size", type=int, default=100_000)

    parser.add_argument("--frames-per-batch", type=int, default=120)

    parser.add_argument("--updates-per-batch", type=int, default=4)

    parser.add_argument("--warmup-frames", type=int, default=6000)

    parser.add_argument("--epsilon-start", type=float, default=1.0)

    parser.add_argument("--epsilon-end", type=float, default=0.05)

    parser.add_argument("--epsilon-decay-frames", type=int, default=150_000)

    parser.add_argument("--target-update", choices=["soft", "hard"], default="soft")

    parser.add_argument("--tau", type=float, default=0.005)

    parser.add_argument("--hard-update-every", type=int, default=1000)

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
