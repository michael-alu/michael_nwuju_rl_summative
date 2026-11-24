"""Writes one CSV row per finished training episode."""

import csv
from pathlib import Path

import torch
from tensordict import TensorDictBase


class EpisodeLogger:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        self.file = open(path, "w", newline="", encoding="utf-8")

        self.writer = csv.writer(self.file)

        self.writer.writerow(["episode", "frames", "points", "cost_bps", "forced_events", "invalid_actions", "won"])

        self.episodes = 0

    def log_batch(self, batch: TensorDictBase, frames_before: int) -> None:
        done = batch["next", "done"].reshape(-1)

        finished_steps = torch.nonzero(done).flatten().tolist()

        flat = batch.reshape(-1)

        for step in finished_steps:
            self.episodes = self.episodes + 1

            row = [
                self.episodes,
                frames_before + step + 1,
                round(float(flat["next", "episode_reward"][step]), 3),
                round(float(flat["next", "cost_bps"][step]), 2),
                int(flat["next", "forced_event_count"][step]),
                int(flat["next", "invalid_actions"][step]),
                int(flat["next", "won_flag"][step]),
            ]

            self.writer.writerow(row)

        self.file.flush()

    def close(self) -> None:
        self.file.close()
