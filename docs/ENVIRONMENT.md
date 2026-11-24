# ThinBook Pension: environment

All settings are in `configs/market.yaml` (frozen: 5 actions, X = 125 bps, end scores +/-7). Every assumption is listed in `docs/ASSUMPTIONS.md`; calibrated values and their sources and date ranges are in `configs/calibration.yaml`. How the game got here is in `docs/HISTORY.md`.

## The game

The agent manages a N10m Nigerian pension fund for 60 trading days, one decision per day. Retirees collect their retirement money. Scheduled retirements are known in advance (5 to 15 trading days of notice). Early withdrawals (for example after a job loss) and death benefits paid to families are claimed at short notice (due 2 to 3 days later) and are twice as likely on stormy market days (an assumption). Each game has 3 to 8 payouts totalling 20% to 50% of the starting fund.

The manager must pay every payout on time and keep the fund inside its PenCom-style investment limits (these are NOT the exact PenCom figures): small caps at most 35% of the fund, banks between 35% and 70%. It wants to lose as little as possible to selling costs.

Agent: one pension fund manager (dealing desk), one discrete action per trading day.

## Assets

| Asset | Real-world analogue | In the simulator |
|---|---|---|
| Cash | Fund bank account | Pays nothing; payouts are paid from it |
| T-bills | 91-day CBN Treasury bills | Sold the same day, tiny fee, no price impact |
| Big-banks basket | ZENITHBANK, GTCO, ACCESSCORP, UBA, FIRSTHOLDCO | Liquid, NGX sell fees, tiny impact, cash arrives T+1 |
| Small-caps basket | Bottom third of NGX by market cap | Thin: zero-volume days, droughts, 20% volume cap, price impact, stale board price, cash arrives T+1 |

## Actions (5, discrete)

Each sale is one fixed slice of the STARTING fund value, clipped by holdings (and, for small caps, by 20% of the day's volume).

| # | Action | What it does | Slice |
|---|---|---|---|
| 0 | Wait | Nothing | - |
| 1 | Sell T-bills | T-bills to cash, same day | `tbill_slice` |
| 2 | Sell bank shares | Banks sold on the exchange, cash T+1 | `banks_slice` = half the median single payout |
| 3 | Sell small-cap shares | Small caps sold on the exchange, capped at 20% of the day's volume, cash T+1 | `small_caps_slice` = the median game's required small-cap sale spread over 60 days |
| 4 | Call a big buyer | Only on days one is offered: a negotiated block of small caps at a discount, off the exchange, cash T+1 | `big_buyer_slice` |

The bank and small-cap slices were sized from the game's structure (`scripts/size_simple_slices.py`), never from results. Invalid actions (selling what the fund does not hold, calling a big buyer when none is offered) act as Wait, cost 1 point and are counted. Stock buying is not allowed: this is a payout game.

## Observation space

15 floats, all in [0, 1]. Every value is something a real fund knows at the end of a trading day. The agent never sees fair values, regimes, future volume or payouts that have not been claimed or announced yet. Holdings are weighted at their starting prices (book weights), the same basis the limits use.

| Observation | Description | Source (Sensor/Camera/API/Dataset) | Encoding / Range | Data Type |
|---|---|---|---|---|
| days_left | Trading days left in the 60-day game | Dataset: fund calendar | days left / 60, [0, 1] | float32 |
| tbills_share | T-bills as a share of the fund (book) | Dataset: custodian statement | share, [0, 1] | float32 |
| banks_vs_limits | Banks share relative to the 35% to 70% limits | Dataset: custodian statement and fund mandate | (share - 0.35 + 0.35) / 1.05, clipped to [0, 1]; 1/3 = lower limit, 2/3 = upper limit | float32 |
| small_caps_vs_limit | Small-caps share relative to its 35% limit | Dataset: custodian statement and fund mandate | share / 0.70, clipped to [0, 1]; 0.5 = at the limit | float32 |
| cash_share | Cash as a share of the fund | Dataset: fund bank account | share, [0, 1] | float32 |
| settling_cash_share | Sale cash arriving tomorrow (T+1) | Dataset: broker contract notes, CSCS settlement report | share, [0, 1] | float32 |
| due_within_5_days | Known payouts due in the next 5 trading days | Dataset: pension administrator's payout schedule and claims register | naira / (0.5 x starting fund), clipped to [0, 1] | float32 |
| due_within_15_days | Known payouts due in the next 15 trading days | Dataset: payout schedule and claims register | naira / (0.5 x starting fund), clipped to [0, 1] | float32 |
| days_to_next_due | Days until the next known payout | Dataset: payout schedule | days / 15, clipped to [0, 1]; 1 if none | float32 |
| grace_days_left | Days left before forced sales if the fund is over a limit | Derived: from the mandate rule and custodian holdings | days / 10; 1 if not over a limit | float32 |
| small_caps_days_since_board_move | Days since the small-caps board price last changed | API: NGX daily price list (official close) | days / 20, clipped to [0, 1] | float32 |
| small_caps_volume_yesterday | Yesterday's small-cap volume vs its normal (median) day | API: NGX daily price list (volume) | log(1 + ratio) / log(1 + 20), clipped to [0, 1] | float32 |
| small_caps_volume_5_days | Mean small-cap volume over 5 days vs normal | Derived: from the API feed over a rolling 5-day window | log(1 + ratio) / log(1 + 20), clipped to [0, 1] | float32 |
| banks_recent_volatility | Banks basket daily volatility over 20 days (storm clue) | Derived: from the API feed over a rolling 20-day window | std / 0.08, clipped to [0, 1] | float32 |
| big_buyer_offered | A broker has a block buyer for small caps today | API: broker indication logged by the desk | 0 or 1 | float32 |

Rubric fields for the same observations:

| Observation | Simulation rule | Update cadence | Agent input path |
|---|---|---|---|
| days_left | (60 - day) / 60 | Each trading day | Index 0 of `observation`, TorchRL key `observation`, input to the policy, value and Q networks |
| tbills_share | Falls with T-bill sales and forced sales | Each trading day | Index 1 |
| banks_vs_limits | Book share; moves only with sales and payouts, never with market prices | Each trading day | Index 2 |
| small_caps_vs_limit | Same rule for small caps | Each trading day | Index 3 |
| cash_share | Rises with sales (T-bills same day, stocks next day), falls with payouts | Each trading day | Index 4 |
| settling_cash_share | Stock sale proceeds after fees, paid out next morning | Each trading day | Index 5 |
| due_within_5_days | Sum of known unpaid payouts due within 5 days | Each trading day | Index 6 |
| due_within_15_days | Same within 15 days | Each trading day | Index 7 |
| days_to_next_due | Earliest known due date minus tomorrow | Each trading day | Index 8 |
| grace_days_left | Starts at 10 when a limit is breached, counts down | Each trading day | Index 9 |
| small_caps_days_since_board_move | Board moves only on days with 100,000+ shares traded (NGX rule, applied to daily volume) | Each trading day | Index 10 |
| small_caps_volume_yesterday | Zero-volume days and droughts from a calibrated chain; log volume has day-to-day persistence 0.519 (calibrated) | Each trading day | Index 11 |
| small_caps_volume_5_days | Mean of the last 5 days of the same series | Each trading day | Index 12 |
| banks_recent_volatility | Zero-drift random walk; calm/stormy chain doubles volatility in storms (calibrated on the ASI) | Each trading day | Index 13 |
| big_buyer_offered | Drawn daily, less likely in droughts (assumption) | Each morning | Index 14 |

## Scoring and reward

Score is selling cost only, so market direction can never change it. Every sale scores

    points = (proceeds - fair value of what was sold - fees) / 10,000

so 1 point is N10,000 lost to selling. Fair value excludes the fund's own price impact and has zero drift. T-bill sales cost only their fee; cash and T-bills earn no score. The headline figure is total selling cost in basis points of the starting fund.

Daily reward = points from today's sales (including any forced sales) - 1 point per invalid action. On day 60 the end score is added: Won +7, Lost -7 (half the standard deviation of the best simple baseline's total points).

TorchRL training multiplies the reward by one training-only scale factor (0.1). The env and all logs report raw points.

## Forced sales

- Payout due and cash short: the env force-sells T-bills, then banks (2% fire-sale discount), then small caps (15% fire-sale discount, limited by the volume cap, beyond it only as a last resort).
- Over a limit for more than 10 trading days, or still over any limit on day 60: forced fire sales (or a forced bank purchase at +5% if banks fall below 35%).

## Outcome

Won = no forced sale of any kind during the game AND total selling cost below X = 125 bps of the starting fund. Otherwise Lost, recorded as "forced sale" or "too costly". X was set as the round number where the best simple baseline (block_dealer) wins 30% to 40% (it wins 37.6%).

## Start state

Day 1, fund fully invested: 15% T-bills, 55% banks, 30% small caps (a holding of 110 days of the median small cap's daily volume). No cash. Regimes drawn from their long-run frequencies, then 20 warm-up days of market history. All payouts for the game are drawn at reset; the agent only learns about each one when it is announced or claimed.

## Terminal condition

After day 60 (`terminated = True`). There is no early ending: every payout must be met within the 60 days.

## Why RL

Today's choice changes tomorrow's options. Selling small caps now moves their price for the next few days; cash from stock sales arrives a day late; a limit breach starts a 10-day clock; a big buyer appears only some days; early withdrawals and death benefits arrive without warning, so cash held back today avoids a fire sale later. Volume persists from day to day, so yesterday's busy market is a clue about today's. The best action depends on the whole path, not on one day's data, which is a sequential decision problem under partial observation.

## Visualisation

`uv run play.py` (or `uv run main.py`) opens a three.js view of one game, fast-forwarded day by day. Three towers on a platform show the T-bills, bank shares and small-cap shares held, valued at starting prices, which is also how the limits are measured. Beside them, a cash pile has a faded layer on top for cash arriving tomorrow (stock sales settle T+1). A red ring marks the 35% small-cap limit and a green band the 35% to 70% bank range; a breach shows a grace countdown. A briefcase appears on days a big buyer is offered, and a tower flashes red with "FORCED SALE" when the env fire-sells. Side panels show the payout queue and the score; a bottom chart shows the small-cap board price against the real price. Beside the vault, the agent is drawn as a fund manager at a desk: each day it turns to the tower it sells, says what it is doing, and that day's reward (the env's own reward, sent by the server with every day) floats up beside it, while a wall scoreboard shows the running total. The page opens in a simple view in plain words; "Show details" switches to the detailed view with the finance terms (shares of the fund, basis points, limit figures, the observable market signals and the hidden state).

The view only reads `env.to_json_state()` and the info dict; it never changes the game. Everything the agent can observe is shown normally. Three things are hidden from the agent and are marked as such on screen: the real small-cap price (the agent only sees the stale board price, which is the point of the game), and the calm/stormy and drought regimes (shown only behind a "Show hidden state" box). The planner is labelled "Perfect foresight (cheats: sees the future)".

## Integration

`step()` returns an info dict with everything a frontend needs: day, action name, trades with their costs, book weights, cash and settling cash, known payouts (kind, amount, due day), limit status and grace days, board and fair prices, volume, big-buyer offer, regimes (UI and debugging only, never in the observation), points, cost in bps, forced events and the outcome. `env.to_json_state()` returns the same as JSON plus the named observation.

The server in `environment/rendering.py` (FastAPI) exposes it; the endpoints are documented with examples in the README and at `/docs`:

| Endpoint | What it does |
|---|---|
| `GET /health` | status and the trained agents loaded |
| `GET /models` | every player and its source run, plus the observation order and action names |
| `POST /act` | one observation (15 numbers between 0 and 1, in the order above) in, one action out, with action probabilities for policy-gradient agents; 422 on a wrong length or range |
| `POST /episode` | plays a whole game (player, seed, market) and returns every day plus the outcome, so another app can replay it |
| `WS /ws/game` | streams a game day by day to the browser; pause, step and speed changes go over the same socket |

Serialization path. Trained networks are saved as `torch.save(network.state_dict())` in `models/<pg|dqn>/<run>_best.pt`. The network shape needed to rebuild one is fixed except for its width: 15 observation numbers in, two hidden layers of `settings["hidden_size"]` units with Tanh, 5 action scores out (`training/common.py`, `make_network`); the width is read from the run's `_summary.json`. To load: `network = make_network(5, hidden_size)`, then `network.load_state_dict(torch.load(path))`, then feed it a float32 tensor of the 15 observation numbers and take the highest score. `environment/model_registry.py` does this for the best run of each algorithm (best held-out win rate, mean points break ties).

## Limitations

- Most market settings are calibrated from NGX data, but fees, impact coefficients, the big buyer, the limits and the payout process are assumptions (see `docs/ASSUMPTIONS.md`).
- The perfect-foresight planner (an analysis tool for the report, never used in training) gets its edge mainly from knowing early withdrawals and death benefits before they are claimed, which no real fund can know; the reachable headroom for a learning agent is smaller.
- In about a third of games the small-cap position cannot be brought inside its limit through the exchange alone (mostly drought games); only the big buyer can help there.
