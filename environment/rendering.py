from custom_types.step_info import StepInfo
"""
Shows ThinBook Pension games to a person (terminal view, one line per day).

The three.js browser view is added here in a later step.
"""


DAY_HEADER = (
    f"{'day':>3} {'action':<32}{'cash':>7}{'tbills':>7}{'banks':>7}{'small':>7}{'sc %':>6}"
    f"{'vol/norm':>9}{'stale':>6}{'pts':>7}{'cost bps':>9}  notes"
)


def short_naira(amount: float) -> str:
    return f"{amount / 1_000_000:.2f}m"


def format_day_line(info: StepInfo, median_volume: float) -> str:
    notes: list[str] = []

    if info["invalid_action"]:
        notes.append("INVALID")

    for trade in info["trades"]:
        notes.append(f"{trade['reason']}: {trade['asset']} N{trade['proceeds']:,.0f} (cost N{trade['cost']:,.0f})")

    upcoming: list[str] = []

    for payout in info["known_payouts"]:
        kind = payout["kind"].replace("_", " ")

        upcoming.append(f"{kind} N{payout['amount'] / 1e6:.2f}m due d{payout['due_day']}")

    if upcoming:
        notes.append("known: " + ", ".join(upcoming))

    if info["in_breach"]:
        notes.append(f"OVER INVESTMENT LIMIT, grace {info['grace_days_left']}d")

    if info["big_buyer_offered_today"]:
        notes.append("big buyer offered")

    notes.append("[stormy]" if info["stormy"] else "[calm]")

    if info["drought"]:
        notes.append("[drought]")

    weights = info["weights"]

    line = (
        f"{info['day']:>3} {info['action_name']:<32}{short_naira(info['cash_naira'] + info['settling_naira']):>7}"
        f"{short_naira(info['tbills_naira']):>7}{short_naira(info['banks_naira']):>7}{short_naira(info['small_caps_naira_board']):>7}"
        f"{weights['small_caps']:>6.0%}{info['small_caps_volume_yesterday'] / median_volume:>9.2f}{info['small_caps_days_since_board_move']:>6}"
        f"{info['points_today']:>7.2f}{info['cost_bps']:>9.1f}  {'; '.join(notes)}"
    )

    return line


def format_game_summary(info: StepInfo) -> str:
    reason = f" ({info['outcome_reason']})" if info["outcome_reason"] else ""

    summary = (
        f"Outcome: {info['outcome'].upper()}{reason}. Selling cost {info['cost_bps']:.1f} bps of the starting fund, "
        f"paid to retirees and families N{info['paid_out_naira']:,.0f}, total points {info['total_points']:.1f}, forced events {len(info['forced_events'])}, invalid actions {info['invalid_actions']}."
    )

    return summary
