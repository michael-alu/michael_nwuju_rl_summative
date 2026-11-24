# ThinBook Fund: Redemptions (merged game test, archived 2026-11-23)

A 60-day redemption game: the fund starts in a target mix (T-bills 30%, big banks 45%, small caps 25%),
pays random investor cash requests, must stay inside mandate-style bands (target +/- 10 points), and is
scored against a frictionless copy of itself. Market: the fund game's fitted bad/flat/good modes.
(Its code has since been removed from the repository.)

Why it was archived (500 held-out seeds, rules fixed before results):
- Won threshold X came out at 0 bps by the pre-set rule (best simple baseline closest to 35%).
- Pass mark a FAILED: the fair oracle (sees market mode, droughts, next-day volume, upcoming requests)
  beat the best simple baseline (banks_first) by 5.6 points of win rate; 10 were required.
- Pass mark b FAILED: banks_first and pro_rata won at about the same rate in every starting situation
  checked (calm, bad, drought, no requests, 2+ requests), so no baseline wins in different situations.
- Pass mark c (PPO) was not run.
- With the cash-request rates carried over from the fund game, games average 0.81 requests and 43% have
  none, so outcomes are mostly decided by tracking noise against the benchmark rather than by decisions.
