# ThinBook Pension

A reinforcement learning summative (ALU, BSc Software Engineering, ML track).

The agent manages a N10m Nigerian pension fund for 60 trading days. Retirees collect their retirement money: scheduled retirements are known in advance, while early withdrawals (for example after a job loss) and death benefits paid to families arrive at short notice. The manager must pay every payout on time and keep the fund inside its PenCom-style investment limits (not the exact PenCom figures), while losing as little as possible to selling costs.

Each day the manager picks one of 5 actions: wait, sell T-bills, sell bank shares, sell small-cap shares, or call a big buyer (a negotiated block deal for small caps, offered on some days). The game is frozen: see `docs/ENVIRONMENT.md` for the full specification and `docs/HISTORY.md` for how it was designed.

The fund holds T-bills, a big-banks basket and a small-caps basket. Small caps trade thinly on NGX: many days have no trades, the board price only moves on days with 100,000+ shares traded, sales are capped at 20% of the day's volume, and selling moves the price. Market settings are calibrated from NGX data where possible and listed with their sources in `configs/market.yaml` and `configs/calibration.yaml`.

## Run it (uv only)

```
uv sync
uv run main.py episode --policy block_dealer --seed 100000
uv run main.py baselines
uv run main.py design-checks
uv run pytest
```

## Layout

- `environment/custom_env.py`: the game's rules in words, its constants (actions, observation names) and the config loaders
- `environment/baselines.py`: plays and scores the baselines and the perfect-foresight planner (an analysis tool, never used in training)
- `environment/policy_helpers.py`: shared cash-planning helpers for the baselines
- `classes/`: every class with behaviour in its own file: the gymnasium environment (`classes/thin_book_pension_env.py`), the baseline policies, the planner, `TorchPolicy`, `EpisodeLogger`, `ZeroValue`; import them with `from classes import ThinBookPensionEnv`
- `custom_types/`: every data type (TypedDict) in its own file: the config, the info dict, payouts, trades and results; import them with `from custom_types import StepInfo`
- `environment/rendering.py`: day-by-day terminal view
- `training/pg_training.py`: PPO, A2C and REINFORCE with TorchRL
- `training/dqn_training.py`: DQN with TorchRL
- `training/sweep.py`, `training/sweep_report.py`: the hyperparameter sweep and its report tables
- `notebooks/colab_sweep.ipynb`: run a slice of the sweep on Colab
- `configs/`: frozen game settings, hard market, calibration summary, proposed sweep configs (`configs/sweeps/`)
- `scripts/`: calibration, design checks, slice sizing, agent evaluation, agents-vs-baselines tables, determinism check
- `docs/`: environment spec, assumptions, design history

Work in progress: the hyperparameter sweeps, figures, the three.js view and the report come next.
