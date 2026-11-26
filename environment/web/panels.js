// The two side panels: retirees to pay (left), and the agent's move and whether it is winning (right),
// plus one plain sentence on what is happening each day. Everything is in plain words; the detailed view
// adds the points, basis points and market signals, and what the agent cannot see behind a tick box.

const PAYOUT_LABELS = {
  scheduled_retirement: "Retirement",
  early_withdrawal: "Early withdrawal",
  death_benefit: "Death benefit",
};

const BANK_SWINGS_STORMY_LEVEL = 0.34;

let cards = new Map();

let paidSummary = { paid: 0, forced: 0 };

export function naira(amount) {
  const size = Math.abs(amount);

  if (size >= 999_500) {
    return `₦${(amount / 1_000_000).toFixed(2)}M`;
  }

  if (size >= 9_995) {
    return `₦${(amount / 1_000).toFixed(0)}K`;
  }

  if (size >= 999.5) {
    return `₦${(amount / 1_000).toFixed(1)}K`;
  }

  return `₦${Math.round(amount)}`;
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

  paidSummary = { paid: 0, forced: 0 };

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

    status = `New ${label.toLowerCase()} - ${status}`;
  }

  if (card.paid) {
    className = card.fireSale ? "payout-card payout-fire" : "payout-card payout-paid";

    status = card.fireSale ? `paid by a forced sale on day ${card.paidDay}` : `paid on time, day ${card.paidDay}`;
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

  paidSummary = { paid: 0, forced: 0 };

  for (const card of cards.values()) {
    if (card.paid) {
      paidSummary.paid = paidSummary.paid + 1;

      if (card.fireSale) {
        paidSummary.forced = paidSummary.forced + 1;
      }
    }
  }

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

const ASSET_WORDS = { tbills: "government bills", banks: "bank shares", small_caps: "small-company shares" };

const FORCED_WHY = {
  "forced: payout": "there was not enough cash to pay a retiree",
  "forced: payout, beyond volume cap": "there was not enough cash to pay a retiree",
  "forced: small caps over limit": "the small-company rule was not fixed in time",
  "forced: banks over limit": "the bank-share rule was not fixed in time",
  "forced: banks below lower limit": "bank shares fell below their minimum",
  "forced: raise cash for limit buy": "it needed cash to fix a rule",
};

// The game shows " - " where a sentence would use a colon, including in the server's own sentences.
export function withoutColons(text) {
  return text.replace(/: /g, " - ");
}

// 1 point = ₦10,000 lost when selling (points_per_naira in configs/market.yaml), so the 125 bps win line on
// the ₦10 million fund is 12.5 points. The score shown is 12.5 plus the total points, as in the report.
const NAIRA_PER_POINT = 10_000;

export function budgetPoints(meta) {
  return ((meta.won_cost_bps / 10_000) * meta.fund_naira) / NAIRA_PER_POINT;
}

function isDetailed() {
  return document.body.classList.contains("detailed");
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function inDays(days) {
  if (days <= 0) {
    return "today";
  }

  if (days === 1) {
    return "tomorrow";
  }

  return `in ${days} days`;
}

function forcedTrade(state) {
  for (const trade of state.trades) {
    if (trade.reason.startsWith("forced")) {
      return trade;
    }
  }

  return null;
}

function chosenSale(state) {
  let proceeds = 0;

  let cost = 0;

  let asset = "";

  for (const trade of state.trades) {
    if (trade.reason === "agent" || trade.reason === "big buyer") {
      proceeds = proceeds + trade.proceeds;

      cost = cost + trade.cost;

      asset = trade.asset;
    }
  }

  return { proceeds, cost, asset };
}

function brokenRule(state, meta) {
  if (!state.in_breach) {
    return "";
  }

  if (state.weights.small_caps > meta.small_caps_max_share) {
    return "small";
  }

  if (state.weights.banks > meta.banks_max_share || state.weights.banks < meta.banks_min_share) {
    return "bank";
  }

  return "";
}

function nextPayout(state) {
  let nearest = null;

  for (const payout of state.known_payouts) {
    if (payout.due_day >= state.day && (nearest === null || payout.due_day < nearest.due_day)) {
      nearest = payout;
    }
  }

  return nearest;
}

function surprisePayout(state) {
  for (const payout of state.known_payouts) {
    const card = cards.get(payoutKey(payout));

    if (card && card.firstSeen === state.day && state.day > 0 && payout.kind !== "scheduled_retirement") {
      return payout;
    }
  }

  return null;
}

function cashContext(state) {
  const next = nextPayout(state);

  if (!next) {
    return "No retiree is waiting right now.";
  }

  const ready = state.cash_naira + state.settling_naira;

  const who = (PAYOUT_LABELS[next.kind] || "Payout").toLowerCase();

  const enough = ready >= next.amount ? "There is enough cash ready." : `Only ${naira(ready)} cash is ready.`;

  return `Next - a ${who} of ${naira(next.amount)} ${inDays(next.due_day - state.day)}. ${enough}`;
}

// The server's own reason for the result, in plain words for the simple view (the reason is not changed).
export function plainOutcome(message, meta) {
  const text = message.outcome_text;

  if (text.startsWith("Lost: selling cost")) {
    const lost = (message.state.cost_bps / 10_000) * meta.fund_naira;

    const allowed = (meta.won_cost_bps / 10_000) * meta.fund_naira;

    return `Lost - it went over its ${naira(allowed)} selling budget by ${naira(lost - allowed)}`;
  }

  if (text.startsWith("Won")) {
    const lost = (message.state.cost_bps / 10_000) * meta.fund_naira;

    const allowed = (meta.won_cost_bps / 10_000) * meta.fund_naira;

    return `Won - every retiree was paid on time, nothing was forced, and it finished with ${naira(allowed - lost)} of its ${naira(allowed)} selling budget left`;
  }

  return withoutColons(text.replace("fire sale", "forced sale").replace("small caps", "small-company shares").replace("after the limit grace ran out", "because a rule was not fixed in time"));
}

function storyFor(message, meta) {
  const state = message.state;

  if (state.day === 0) {
    return `An agent looks after a ${naira(meta.fund_naira)} pension fund for ${meta.horizon_days} days. It has a ${naira((meta.won_cost_bps / 10_000) * meta.fund_naira)} selling budget, and every sale uses a little of it. To win it must pay every retiree on time, never be forced to sell, and finish with budget left.`;
  }

  if (message.finished) {
    return `Game over. ${plainOutcome(message, meta)}.`;
  }

  const forced = forcedTrade(state);

  if (forced) {
    return `Forced sale! The game sold ${ASSET_WORDS[forced.asset] || forced.asset} for the agent at a bad price, because ${FORCED_WHY[forced.reason] || "the rules required it"}. One forced sale loses the game.`;
  }

  if (state.invalid_action) {
    const tried = state.action_name === "Call a big buyer" ? "called a big buyer, but none was around" : "tried to sell something the fund no longer has";

    return `The agent ${tried}. Wasted move - it costs 1 point.`;
  }

  const surprise = surprisePayout(state);

  if (surprise) {
    return `Surprise - a ${(PAYOUT_LABELS[surprise.kind] || "payout").toLowerCase()} of ${naira(surprise.amount)} must be paid ${inDays(surprise.due_day - state.day)}. The agent needs cash ready.`;
  }

  const broken = brokenRule(state, meta);

  if (broken !== "") {
    const days = state.grace_days_left;

    const what = broken === "small" ? `Too much of the fund is in small-company shares (${(state.weights.small_caps * 100).toFixed(0)}%, the limit is ${(meta.small_caps_max_share * 100).toFixed(0)}%)` : `Bank shares are outside their allowed range (${(state.weights.banks * 100).toFixed(0)}%)`;

    return days > 0 ? `${what}. The agent has ${plural(days, "day")} to fix it, or the game will force a sale.` : `${what}. Time is up - the game will force a sale.`;
  }

  const sale = chosenSale(state);

  if (state.action_name !== "Wait" && sale.proceeds > 0) {
    return `The agent sold ${naira(sale.proceeds)} of ${ASSET_WORDS[sale.asset] || sale.asset} to raise cash, using ${naira(sale.cost)} of its budget. ${cashContext(state)}`;
  }

  if (state.action_name !== "Wait") {
    return `The agent tried to sell small-company shares, but nobody was trading them today. ${cashContext(state)}`;
  }

  return `The agent waited today. ${cashContext(state)}`;
}

function moveText(message) {
  const state = message.state;

  if (isDetailed() || state.day === 0) {
    return withoutColons(message.action_text);
  }

  if (state.invalid_action) {
    return state.action_name === "Call a big buyer" ? "Called a big buyer who was not there - wasted move, −1 point" : "Tried to sell something the fund no longer has - wasted move, −1 point";
  }

  const sale = chosenSale(state);

  if (state.action_name === "Wait") {
    return "Waited - nothing sold, nothing lost";
  }

  if (sale.proceeds <= 0) {
    return "Tried to sell small-company shares, but nobody was trading them";
  }

  const buyer = state.action_name === "Call a big buyer" ? " to the big buyer" : "";

  return `Sold ${naira(sale.proceeds)} of ${ASSET_WORDS[sale.asset] || sale.asset}${buyer}`;
}

function setCheck(id, status, text) {
  document.getElementById(id).className = `check check-${status}`;

  document.getElementById(`${id}-text`).textContent = text;
}

function showChecks(message, meta) {
  const state = message.state;

  const detailed = isDetailed();

  if (paidSummary.forced > 0) {
    setCheck("check-paid", "bad", `${plural(paidSummary.forced, "retiree")} only paid through a forced sale`);
  } else {
    setCheck("check-paid", paidSummary.paid > 0 ? "good" : "wait", paidSummary.paid > 0 ? `${paidSummary.paid} paid on time so far` : "Nobody due yet");
  }

  const forced = state.forced_event_count;

  if (forced > 0) {
    setCheck("check-forced", "bad", `${plural(forced, "forced sale")}: this game is lost`);
  } else if (state.in_breach) {
    setCheck("check-forced", "warn", state.grace_days_left > 0 ? `None yet, but a rule is broken - ${plural(state.grace_days_left, "day")} to fix it` : "None yet, but time is up on a broken rule");
  } else {
    setCheck("check-forced", "good", "None so far");
  }

  const line = meta.won_cost_bps;

  const lost = (state.cost_bps / 10_000) * meta.fund_naira;

  const allowed = (line / 10_000) * meta.fund_naira;

  const used = state.cost_bps / line;

  document.getElementById("cost-limit").textContent = naira(allowed);

  const left = allowed - lost;

  const leftText = left >= 0 ? `${naira(left)} of ${naira(allowed)} left` : `Over budget by ${naira(-left)}`;

  setCheck("check-cost", used >= 1 ? "bad" : used >= 0.8 ? "warn" : "good", detailed ? `${leftText} (${naira(lost)} used, ${(state.cost_bps / 100).toFixed(2)}% of the fund)` : leftText);

  const fill = document.getElementById("cost-fill");

  fill.style.width = `${Math.max(1 - used, 0) * 100}%`;

  fill.className = used >= 1 ? "gauge-fill gauge-bad" : used >= 0.8 ? "gauge-fill gauge-warn" : "gauge-fill gauge-good";

  document.getElementById("cost-line").style.left = "100%";

  document.getElementById("cost-bps").textContent = `${(state.cost_bps / 100).toFixed(2)}% of the fund used`;

  document.getElementById("cost-line-text").textContent = `limit ${(line / 100).toFixed(2)}%`;

  let text = "Yes, so far";

  let kind = "verdict-good";

  if (message.finished) {
    text = state.outcome === "won" ? "Yes - it won" : "No - it lost";

    kind = state.outcome === "won" ? "verdict-good" : "verdict-bad";
  } else if (forced > 0 || used >= 1) {
    text = "No - this game is lost";

    kind = "verdict-bad";
  } else if (state.in_breach || used >= 0.8) {
    text = "At risk";

    kind = "verdict-warn";
  }

  const verdict = document.getElementById("verdict");

  verdict.textContent = text;

  verdict.className = `verdict ${kind}`;
}

export function updateStatus(message, meta) {
  const state = message.state;

  const horizon = meta.horizon_days;

  document.getElementById("day-text").textContent = `Day ${state.day} of ${horizon}`;

  document.getElementById("day-bar").style.width = `${(state.day / horizon) * 100}%`;

  const story = document.getElementById("story");

  document.getElementById("story-text").textContent = storyFor(message, meta);

  story.className = forcedTrade(state) ? "story story-bad" : state.invalid_action || state.in_breach ? "story story-warn" : "story";

  const action = document.getElementById("action-text");

  action.textContent = moveText(message);

  action.className = state.invalid_action ? "action action-invalid" : "action";

  showChecks(message, meta);

  const reward = state.day === 0 ? 0 : message.reward;

  const rewardElement = document.getElementById("points-today");

  rewardElement.textContent = `${reward > 0.005 ? "+" : ""}${reward.toFixed(2)}`;

  rewardElement.className = reward > 0.005 ? "value-up" : reward < -0.005 ? "value-down" : "";

  document.getElementById("points-total").textContent = (budgetPoints(meta) + state.total_points).toFixed(2);

  document.getElementById("score-now").textContent = (budgetPoints(meta) + state.total_points).toFixed(2);

  const today = document.getElementById("score-today");

  today.textContent = state.day === 0 ? "" : `${reward > 0.005 ? "+" : reward < -0.005 ? "−" : ""}${Math.abs(reward).toFixed(2)} today`;

  today.className = reward > 0.005 ? "score-today value-up" : reward < -0.005 ? "score-today value-down" : "score-today";

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

// What to expect in this game, counted by the server from the market and payouts it drew at the start.
function previewLine(list, text) {
  const item = document.createElement("li");

  item.textContent = text;

  list.appendChild(item);
}

export function showPreview(meta) {
  const preview = meta.preview;

  const box = document.getElementById("preview");

  if (!preview) {
    box.hidden = true;

    return;
  }

  const days = meta.horizon_days;

  const thin = preview.no_trade_days >= days / 4;

  const stormy = preview.stormy_days >= days / 4;

  document.getElementById("preview-title").textContent = `${thin ? "A thin market" : "A busy market"} with ${stormy ? "stormy" : "calm"} prices`;

  const list = document.getElementById("preview-list");

  list.innerHTML = "";

  const surprises = preview.surprise_payouts > 0 ? `, ${preview.surprise_payouts} of them surprises with only 2 or 3 days' notice` : "";

  previewLine(list, `${plural(preview.payouts, "retiree")} to pay, ${naira(preview.payout_total_naira)} in total${surprises}.`);

  if (preview.no_trade_days > 0) {
    previewLine(list, `On ${preview.no_trade_days} of ${days} days nobody trades small-company shares at all, so they cannot be sold those days.`);
  } else {
    previewLine(list, "Small-company shares trade every day.");
  }

  previewLine(list, preview.stormy_days > 0 ? `Prices swing a lot on ${plural(preview.stormy_days, "day")}.` : "Prices stay calm all game.");

  previewLine(list, preview.big_buyer_days > 0 ? `A big buyer turns up on ${plural(preview.big_buyer_days, "day")}.` : "No big buyer turns up.");

  if (isDetailed()) {
    previewLine(list, `Small caps are in a dry spell (much less trading) on ${preview.dry_spell_days} of ${days} days.`);
  }

  box.hidden = false;
}
