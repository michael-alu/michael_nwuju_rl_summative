// The two side panels: retirees waiting for their money (left) and score and status (right).
// Everything shown is in plain words; only what the agent itself can see is shown, unless the
// "show hidden state" box is ticked.

const PAYOUT_LABELS = {
  scheduled_retirement: "Retirement",
  early_withdrawal: "Early withdrawal",
  death_benefit: "Death benefit",
};

const BANK_SWINGS_STORMY_LEVEL = 0.34;

let cards = new Map();

export function naira(amount) {
  if (Math.abs(amount) >= 999_500) {
    return `₦${(amount / 1_000_000).toFixed(2)}M`;
  }

  if (Math.abs(amount) < 500) {
    return "₦0";
  }

  return `₦${(amount / 1_000).toFixed(0)}K`;
}

function payoutKey(payout) {
  return `${payout.kind}-${payout.due_day}-${Math.round(payout.amount)}`;
}

function daysText(days) {
  if (days <= 0) {
    return "due today";
  }

  if (days === 1) {
    return "due tomorrow";
  }

  return `due in ${days} days`;
}

export function resetPayouts() {
  cards = new Map();

  document.getElementById("payout-list").innerHTML = "";
}

function paidByFireSale(state) {
  for (const trade of state.trades) {
    if (trade.reason.startsWith("forced: payout")) {
      return true;
    }
  }

  return false;
}

function renderCard(card, today) {
  const label = PAYOUT_LABELS[card.payout.kind] || "Payout";

  let status = daysText(card.payout.due_day - today);

  let className = "payout-card";

  if (card.isNew) {
    className = className + " payout-new";

    status = `New: ${label.toLowerCase()}, ${status}`;
  }

  if (card.paid) {
    className = card.fireSale ? "payout-card payout-fire" : "payout-card payout-paid";

    status = card.fireSale ? `paid by fire sale on day ${card.paidDay}` : `paid on day ${card.paidDay}`;
  }

  const mark = card.paid ? (card.fireSale ? "!" : "&#10003;") : "";

  card.element.className = className;

  card.element.innerHTML = `<div class="payout-top"><span class="payout-kind">${label}</span><span class="payout-amount">${naira(card.payout.amount)}</span></div><div class="payout-status"><span class="payout-mark">${mark}</span>${status}</div>`;
}

export function updatePayouts(state) {
  const list = document.getElementById("payout-list");

  const knownNow = new Set();

  for (const payout of state.known_payouts) {
    const key = payoutKey(payout);

    knownNow.add(key);

    if (!cards.has(key)) {
      const element = document.createElement("div");

      const sudden = payout.kind !== "scheduled_retirement";

      cards.set(key, { payout, element, paid: false, fireSale: false, paidDay: 0, isNew: sudden && state.day > 0, firstSeen: state.day });
    }
  }

  for (const [key, card] of cards) {
    if (!card.paid && !knownNow.has(key) && card.payout.due_day <= state.day) {
      card.paid = true;

      card.paidDay = state.day;

      card.fireSale = paidByFireSale(state);
    }

    if (card.isNew && state.day - card.firstSeen >= 1) {
      card.isNew = false;
    }
  }

  const ordered = [...cards.values()].sort((first, second) => {
    if (first.paid !== second.paid) {
      return first.paid ? 1 : -1;
    }

    return first.paid ? second.payout.due_day - first.payout.due_day : first.payout.due_day - second.payout.due_day;
  });

  list.innerHTML = "";

  let waitingTotal = 0;

  let waitingCount = 0;

  for (const card of ordered) {
    renderCard(card, state.day);

    list.appendChild(card.element);

    if (!card.paid) {
      waitingTotal = waitingTotal + card.payout.amount;

      waitingCount = waitingCount + 1;
    }
  }

  const summary = waitingCount === 0 ? "Nobody is waiting right now" : `${waitingCount} waiting, ${naira(waitingTotal)} in total`;

  document.getElementById("payout-summary").textContent = summary;
}

function tradingLevel(state, meta) {
  const ratio = state.small_caps_volume_yesterday / meta.small_caps_median_volume;

  if (state.small_caps_volume_yesterday <= 0) {
    return "no trades";
  }

  if (ratio < 0.5) {
    return "quiet";
  }

  if (ratio <= 2) {
    return "normal";
  }

  return "busy";
}

export function updateStatus(message, meta) {
  const state = message.state;

  const horizon = meta.horizon_days;

  document.getElementById("day-text").textContent = `Day ${state.day} of ${horizon}`;

  document.getElementById("day-bar").style.width = `${(state.day / horizon) * 100}%`;

  const action = document.getElementById("action-text");

  action.textContent = message.action_text;

  action.className = state.invalid_action ? "action action-invalid" : "action";

  const reward = state.day === 0 ? 0 : message.reward;

  const rewardElement = document.getElementById("points-today");

  rewardElement.textContent = `${reward > 0.005 ? "+" : ""}${reward.toFixed(2)}`;

  rewardElement.className = reward > 0.005 ? "value-up" : reward < -0.005 ? "value-down" : "";

  document.getElementById("points-total").textContent = state.total_points.toFixed(2);

  const line = meta.won_cost_bps;

  const scale = line * 2;

  const fill = document.getElementById("cost-fill");

  fill.style.width = `${Math.min(state.cost_bps / scale, 1) * 100}%`;

  fill.className = state.cost_bps < line ? "gauge-fill gauge-good" : "gauge-fill gauge-bad";

  document.getElementById("cost-line").style.left = `${(line / scale) * 100}%`;

  const detailed = document.body.classList.contains("detailed");

  const lostNaira = (state.cost_bps / 10_000) * meta.fund_naira;

  const allowedNaira = (line / 10_000) * meta.fund_naira;

  document.getElementById("cost-text").textContent = detailed ? `${state.cost_bps.toFixed(1)} bps` : `${naira(lostNaira)} lost`;

  document.getElementById("cost-line-text").textContent = detailed ? `win line ${line.toFixed(0)} bps` : `limit to win: ${naira(allowedNaira)}`;

  document.getElementById("forced-count").textContent = state.forced_event_count;

  document.getElementById("invalid-count").textContent = state.invalid_actions;

  const staleDays = state.small_caps_days_since_board_move;

  document.getElementById("stale-text").textContent = staleDays === 0 ? "updated today" : `last updated ${staleDays} day${staleDays === 1 ? "" : "s"} ago`;

  document.getElementById("trading-text").textContent = tradingLevel(state, meta);

  const swings = state.observation.banks_recent_volatility > BANK_SWINGS_STORMY_LEVEL ? "swinging a lot" : "calm";

  document.getElementById("swings-text").textContent = swings;

  document.getElementById("hidden-mood").textContent = state.stormy ? "stormy" : "calm";

  document.getElementById("hidden-drought").textContent = state.drought ? "yes" : "no";

  document.getElementById("hidden-real-price").textContent = `₦${state.small_caps_real_price.toFixed(2)} (board shows ₦${state.small_caps_board_price.toFixed(2)})`;
}
