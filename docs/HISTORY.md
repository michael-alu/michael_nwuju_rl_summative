# How ThinBook Pension was designed

This file records every game design we tried, why each was rejected, and how the final game was chosen. Every number below is copied from a saved output in `logs/history/` (file named in brackets).

The code for the rejected designs (the fund game, the replay and signal-check experiments, the market-mode fitting, merged game v1, the selling game, the 8-action version, its oracle and the pass-mark scripts) was removed from the repository once ThinBook Pension was frozen. Their saved outputs stay in `logs/history/`; the numbers below come only from those files. The "fair oracle" named below is the analysis tool now called the perfect-foresight planner. Held-out results use 500 seeds that no policy or agent was tuned on.

## 0. Selling-only game (first idea, later the fallback)

A fund sells one large block of a thin stock within 30 days. Kept as a fallback, then set aside (no saved output; this section reports only the design reasons). It worked as an environment, but with order sizes as a share of what was left, TWAP could never finish the block, and with weak impact, "sell as fast as allowed" was simply best. It was set aside for a richer fund game.

## 1. ThinBook Fund (beat Treasury bills)

The agent ran a N10m fund across cash, T-bills, a bank stock and a thin small cap, and won by beating an all-T-bills fund.

| Round | What changed | Result | Why it failed |
|---|---|---|---|
| 60 days, assumed returns [02] | first version | 60/40 won 30.8%, oracle 35.2% | stocks earned less than T-bills after fees; no headroom |
| 60 days, PPO [03] | baskets, locked end scores | PPO won 4.8%, mean return 2.49% vs T-bills 3.10% | PPO learned to sit in T-bills |
| 60 days, baskets [04] | baskets, calm +20%/stormy -30% (assumed) | fair oracle 37.2% vs 60/40 30.6% (+6.6) | pass mark needed +10 |
| 120 days, returns calibrated from NGX [05] | real 2021-26 returns | all_stocks_max won 55.0%, fair oracle 45.6% | 2021-26 was a one-way rally: holding the most stocks always won |
| Real market replay [06] | every game replays a real 120-day NGX window | stocks beat T-bills in 97.1% of the newest held-out windows; 73.9% with blocked hold-out; AUC 0.747 | one real downturn (2018) in the data |
| Fitted simulator [07] | bad/flat/good modes fitted to real windows | fair oracle 61.2% vs all_stocks_max 67.2% | stocks still won without timing |

Lesson: a game scored against market returns is decided by the market, not by decisions.

## 2. Merged game v1 (redemptions against a frictionless benchmark)

Scored against a frictionless copy of the fund [08]. Only 0.81 requests per game (43% of games had none), so noise decided games: fair oracle 41.6% vs best simple baseline 36.0% (+5.6, needed +10), and banks-first and pro-rata tied in every situation.

## 3. Merged game v2, now ThinBook Pension (selling cost only)

Scoring changed to selling cost only (fair value with zero drift), so market direction cannot change the score. 3 to 8 payouts per game, PenCom-style limits with a 10-day grace, a fixed design-check gate before any baseline, and real small-cap volume persistence calibrated from NGX data.

Two bugs found and fixed before any pass mark was accepted: policies raised cash too late for large payouts, and limits measured at market prices let price drift alone force sales in 13% of games (limits now use starting-price book weights).

| Result [09, 10] | Value |
|---|---|
| X (best simple baseline wins 30-40%) | 150 bps, volume_aware_trimmer 37.2% |
| Fair oracle (8 actions) | 75.0% (+37.8) |
| PPO, 8 actions, one seed | 54.2% (+17.0) |
| Check b (two baselines win in different situations) | failed: only one listed baseline managed the small-cap limit |

A block-dealer baseline (small caps leave only through negotiated block deals) was then added. It ties overall but leads in droughts and light-payout games, while the volume-aware trimmer leads in heavy-payout and no-drought games.

## 4. Pension story, and 8 actions vs 5 actions

The story became ThinBook Pension (scheduled retirements, early withdrawals, death benefits). Logic and numbers did not change. Adding block_dealer made it the best simple baseline, so X became 125 bps by the same rule; end scores stayed at +/-7.

### Round 1 (tools built for 8 actions) [11, 12, 13]

| | 8 actions | 5 actions |
|---|---|---|
| Best simple baseline (block_dealer) | 37.4% | 37.6% |
| Fair oracle | 66.6% | 34.2% (8-action planner mapped onto 5 actions) |
| PPO, best of 2 seeds | 36.6% | 46.6% |

The pre-set rule (keep 5 actions only if PPO leads the best baseline by 10+ points) picked 8 actions: the 5-action PPO led by 9.0. Two things made that test unfair to 5 actions: the oracle was an 8-action planner whose "sell a lot" became the tiny 5-action slice, and the decision rested on single PPO seeds.

### Round 2 (fair re-test) [14, 15]

| Check (5 actions, rules fixed before running) | Result |
|---|---|
| 5-action fair oracle vs best simple baseline (needs +10) | 53.6% vs 37.6% (+16.0): PASS |
| PPO, 3 seeds, held out | 46.6%, 45.6%, 43.8%; mean 45.3% (std 1.2%) |
| Mean PPO vs block_dealer (needs to beat it) | 45.3% vs 37.6%: PASS |
| Hard market, PPO mean vs block_dealer | 15.5% vs 12.0% |

The fair re-test, with an oracle written for 5 actions and three PPO seeds, is what decided: the game was frozen with 5 actions, X = 125 bps and end scores +/-7. The 8-action version was then removed from the code.

## 5. Baseline fix after the freeze [11, 17]

After the game was frozen, a code review found that the simple baselines still planned with the 8-action slice sizes: their cash planning assumed one bank sale raised 7.5% of the fund (the real 5-action slice is 2.507%), pro_rata counted 2.5% or 7.5% per bank sale and 1.5% per small-cap sale, and steady_trimmer timed its trims as if each sold 0.5% of the fund (the real slice is 0.121%). The baselines therefore started raising cash too late and trimmed too rarely: they were weaker than they really are. They now plan with the real `banks_slice` and `small_caps_slice` from the config. X stayed frozen at 125 bps; nothing was retrained.

The random baseline was also corrected: it drew from the 8 old action names and mapped them, so it was not uniform over the 5 real actions; it now picks uniformly from the 5.

| Normal market, 500 held-out seeds | Win rate before [11] | Win rate after [17] |
|---|---|---|
| liquidity_ladder | 0.0% | 0.0% |
| pro_rata | 0.0% | 0.0% |
| steady_trimmer | 0.0% | 4.8% |
| volume_aware_trimmer | 23.8% | 24.0% |
| block_dealer | 37.6% | 37.6% |
| random | 0.4% | 3.8% |
| trusts_the_board | 0.0% | 0.0% |

After the fix [17], on the same seeds:

| Normal market | Win rate | Mean points | Mean cost (bps) | Forced-sale rate | Invalid actions per game |
|---|---|---|---|---|---|
| block_dealer (best simple baseline) | 37.6% | -18.29 | 165.6 | 42.8% | 0.00 |
| perfect_foresight_planner (analysis tool) | 53.6% | -14.71 | 152.2 | 16.6% | 0.00 |
| PPO, mean of 3 seeds | 45.3% | -15.30 | 145.3 | 47.3% | 0.12 |

| Hard market | Win rate | Mean points | Mean cost (bps) | Forced-sale rate | Invalid actions per game |
|---|---|---|---|---|---|
| block_dealer (best simple baseline) | 11.8% | -31.12 | 257.7 | 65.6% | 0.00 |
| perfect_foresight_planner (analysis tool) | 21.6% | -27.84 | 238.7 | 37.0% | 0.00 |
| PPO, mean of 3 seeds | 15.5% | -27.05 | 214.3 | 74.5% | 0.79 |

PPO still beats the best simple baseline: by 7.7 points of win rate on the normal market (45.3% vs 37.6%) and 3.7 points on the hard market (15.5% vs 11.8%), with lower selling cost in both. The fix mainly helped the weaker baselines (steady_trimmer); block_dealer's win rate did not change. The determinism reference (`logs/determinism_reference.json`) was re-saved after this fix, with a note; the PPO model, random play and the planner matched the old reference exactly, only block_dealer's numbers moved.

## What the history teaches

1. If market direction can decide the score, it will; score decisions, not luck.
2. A pass mark is only as fair as the tools that measure it: an oracle and baselines must be built for the action space being tested.
3. Single seeds mislead; the 8-vs-5 choice flipped once three seeds were compared.
