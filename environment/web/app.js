// ThinBook Pension in the browser: the controls, the game stream and the end screen.
// The server plays the game (environment/rendering.py); this page only shows what it sends.
//
// Page options (used by play.py and for screenshots):
// ?player=ppo&seed=100000&market=normal&speed=5&autoplay=1&pause_at=30&detailed=1

import { createScene, sceneDay, resetScene, resetView, setAutoOrbit, setFund, setDetailed, setStartHoldings } from "./scene.js";
import { drawPriceChart, drawPointsChart } from "./charts.js";
import { budgetPoints, naira, plainOutcome, resetPayouts, showPreview, updatePayouts, updateStatus } from "./panels.js";

const SPEEDS = ["slow", "1", "5", "20", "instant"];

const FRIENDLY_NAMES = {
  ppo: "PPO agent",
  dqn: "DQN agent",
  a2c: "A2C agent",
  reinforce: "REINFORCE agent",
  block_dealer: "Simple rule (no learning)",
  perfect_foresight: "Fortune teller (sees the future)",
  random: "Random moves",
};

let socket = null;
let meta = null;
let speed = "slow";
let gameRunning = false;

let pauseAtDay = 0;

// Skip to the end only speeds up the lost game; the speed chosen before it comes back for the next game.
let speedBeforeSkip = "";
let gameFinished = false;
let paused = false;
let priceHistory = [];
let pointsHistory = [];
let lastMessage = null;
let gameSettingsKey = "";

let startState = null;

// Every day received this game, so past days can be shown again. viewing is the day on screen, or -1 for
// the latest one.
let dayLog = [];

let viewing = -1;

const elements = {
  player: document.getElementById("player"),
  seed: document.getElementById("seed"),
  market: document.getElementById("market"),
  play: document.getElementById("play"),
  pause: document.getElementById("pause"),
  step: document.getElementById("step"),
  randomGame: document.getElementById("random-game"),
  help: document.getElementById("help"),
  helpOverlay: document.getElementById("help-overlay"),
  helpClose: document.getElementById("help-close"),
  resetView: document.getElementById("reset-view"),
  autoOrbit: document.getElementById("auto-orbit"),
  showHidden: document.getElementById("show-hidden"),
  showDetails: document.getElementById("show-details"),
  endOverlay: document.getElementById("end-overlay"),
  playAgain: document.getElementById("play-again"),
  newGame: document.getElementById("new-game"),
  priceCanvas: document.getElementById("price-chart"),
  pointsCanvas: document.getElementById("points-chart"),
  playerLabel: document.getElementById("player-label"),
  notice: document.getElementById("notice"),
};

function settingsKey() {
  return `${elements.player.value}|${elements.seed.value}|${elements.market.value}`;
}

function showNotice(text, kind) {
  elements.notice.textContent = text;

  elements.notice.className = kind === "info" ? "notice notice-info" : "notice";

  elements.notice.hidden = text === "";
}

// Waking a sleeping server. On Render's free plan the server sleeps after about 15 minutes without
// visitors; a request then waits while it starts again (up to about a minute). Before a game starts, the
// page asks /health; if there is no answer within a few seconds it says the server is waking up, keeps
// asking, and starts the game once it answers.
const HEALTH_TIMEOUT_MS = 5000;

const WAKE_POLL_MS = 3000;

const WAKE_LIMIT_MS = 90000;

// Render only sleeps after about 15 minutes without visitors, so if the page heard from the server in the
// last few minutes it is awake and the check is skipped.
const RECENT_CONTACT_MS = 5 * 60 * 1000;

let waking = false;

let lastContact = 0;

function heardFromServer() {
  lastContact = Date.now();
}

function wait(milliseconds) {
  return new Promise(function after(resolve) {
    setTimeout(resolve, milliseconds);
  });
}

async function serverAnswers() {
  const controller = new AbortController();

  const timer = setTimeout(function giveUp() {
    controller.abort();
  }, HEALTH_TIMEOUT_MS);

  try {
    const response = await fetch("/health", { cache: "no-store", signal: controller.signal });

    return response.ok;
  } catch (error) {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function showWaking(seconds) {
  const counter = seconds > 0 ? ` (${seconds}s so far)` : "";

  showNotice(`The game server is waking up${counter}. Free hosting puts it to sleep when nobody has played for a while, so this can take up to a minute. The game will start by itself.`, "info");
}

async function wakeServer() {
  if (await serverAnswers()) {
    heardFromServer();

    return true;
  }

  const started = Date.now();

  showWaking(0);

  while (Date.now() - started < WAKE_LIMIT_MS) {
    await wait(WAKE_POLL_MS);

    showWaking(Math.round((Date.now() - started) / 1000));

    if (await serverAnswers()) {
      heardFromServer();

      showNotice("");

      return true;
    }
  }

  showNotice("The game server did not wake up. Please refresh the page in a minute and press Play again.");

  return false;
}

async function startGame(options) {
  if (Date.now() - lastContact < RECENT_CONTACT_MS) {
    openGame(options);

    return;
  }

  if (waking) {
    return;
  }

  waking = true;

  const awake = await wakeServer();

  waking = false;

  if (awake) {
    openGame(options);
  }
}

function friendlyName(entry) {
  const name = FRIENDLY_NAMES[entry.player] || entry.label;

  if (!entry.available) {
    return `${name} (not trained yet)`;
  }

  if (entry.held_out_win_rate === null || entry.held_out_win_rate === undefined) {
    return name;
  }

  return `${name} (won ${(entry.held_out_win_rate * 100).toFixed(0)}%)`;
}

function playerLine(meta) {
  const name = FRIENDLY_NAMES[meta.player] || meta.player_label;

  const match = meta.player_label.match(/wins ([0-9.]+%)/);

  const record = match ? `, won ${match[1]} of test games` : "";

  return `${name}${record} · game ${meta.seed}, ${meta.market} market`;
}

async function loadPlayers(preferred) {
  const response = await fetch("/models");

  const body = await response.json();

  heardFromServer();

  elements.player.innerHTML = "";

  for (const entry of body.players) {
    const option = document.createElement("option");

    option.value = entry.player;

    option.textContent = friendlyName(entry);

    option.disabled = !entry.available;

    elements.player.appendChild(option);
  }

  const wanted = body.players.find((entry) => entry.player === preferred && entry.available);

  const firstAvailable = body.players.find((entry) => entry.available);

  elements.player.value = wanted ? wanted.player : firstAvailable.player;
}

function setSpeed(value) {
  speed = value;

  for (const button of document.querySelectorAll(".speed")) {
    button.classList.toggle("selected", button.dataset.speed === value);
  }

  send({ type: "speed", speed: value });
}

function send(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
  }
}

function updateButtons() {
  elements.play.disabled = gameRunning && !paused && !gameFinished;

  elements.pause.disabled = !gameRunning || paused || gameFinished;

  elements.step.disabled = gameRunning && !paused && !gameFinished;
}

function resetGameView() {
  dayLog = [];

  viewing = -1;

  priceHistory = [];

  pointsHistory = [];

  lastMessage = null;

  resetPayouts();

  resetScene();

  elements.endOverlay.hidden = true;

  document.getElementById("lost-banner").hidden = true;

  showNotice("");

  drawCharts();
}

function openGame(options) {
  if (speedBeforeSkip !== "") {
    setSpeed(speedBeforeSkip);

    speedBeforeSkip = "";
  }

  if (socket) {
    socket.onclose = null;

    socket.close();
  }

  resetGameView();

  gameSettingsKey = settingsKey();

  gameRunning = true;

  gameFinished = false;

  paused = options.paused;

  pauseAtDay = options.pauseAt || 0;

  updateButtons();

  const protocol = location.protocol === "https:" ? "wss" : "ws";

  socket = new WebSocket(`${protocol}://${location.host}/ws/game`);

  socket.onopen = () => {
    socket.send(JSON.stringify({
      player: elements.player.value,
      seed: Number(elements.seed.value),
      market: elements.market.value,
      speed: speed,
      paused: options.paused,
      pause_at: options.pauseAt || 0,
    }));
  };

  socket.onmessage = (event) => {
    heardFromServer();

    handleMessage(JSON.parse(event.data));
  };

  socket.onclose = () => {
    gameRunning = false;

    updateButtons();

    if (!gameFinished) {
      showNotice("Lost the connection to the game server (it may have gone to sleep). Press Play to wake it and start again.", "info");
    }
  };
}

function recordDay(message) {
  const state = message.state;

  if (state.day === 0) {
    startState = state;

    setStartHoldings(state);
  }

  let sold = false;

  let bigBuyer = false;

  for (const trade of state.trades) {
    if (trade.asset === "small_caps" && trade.reason === "agent") {
      sold = true;
    }

    if (trade.reason === "big buyer") {
      bigBuyer = true;
    }
  }

  priceHistory.push({ day: state.day, board: state.small_caps_board_price, real: state.small_caps_real_price, sold, bigBuyer });

  pointsHistory.push({ day: state.day, total: (meta ? budgetPoints(meta) : 0) + state.total_points, reward: state.day === 0 ? 0 : message.reward });
}

function drawCharts() {
  const horizon = meta ? meta.horizon_days : 60;

  drawPriceChart(elements.priceCanvas, priceHistory, horizon, document.body.classList.contains("detailed"));

  drawPointsChart(elements.pointsCanvas, pointsHistory, horizon);
}

function applyDetails(detailed) {
  document.body.classList.toggle("detailed", detailed);

  elements.showDetails.textContent = detailed ? "Hide details" : "Show details";

  elements.showDetails.setAttribute("aria-pressed", detailed ? "true" : "false");

  localStorage.setItem("thinbook-detailed", detailed ? "1" : "0");

  setDetailed(detailed);

  if (lastMessage && meta) {
    updateStatus(lastMessage, meta);

    showPreview(meta);
  }

  drawCharts();
}

function showDay(message, instant) {
  sceneDay(message, meta, instant);

  updateStatus(message, meta);

  drawCharts();
}

// The end screen's "Where the fund went": each holding on day 0 and at the end, valued like the towers
// (shares at their starting prices, the way the limits are measured), and the change.
function holdingsOf(state) {
  return [
    { name: "Cash", value: state.cash_naira + state.settling_naira },
    { name: "Government bills", value: state.tbills_naira },
    { name: "Bank shares", value: state.banks_naira_book },
    { name: "Small-company shares", value: state.small_caps_naira_book },
  ];
}

function signedNaira(amount) {
  if (Math.abs(amount) < 500) {
    return "no change";
  }

  return `${amount > 0 ? "+" : "−"}${naira(Math.abs(amount))}`;
}

function showHoldingsChange(state, lost) {
  const body = document.getElementById("end-holdings");

  body.innerHTML = "";

  if (!startState) {
    return;
  }

  const before = holdingsOf(startState);

  const after = holdingsOf(state);

  let totalBefore = 0;

  let totalAfter = 0;

  for (let index = 0; index < before.length; index++) {
    totalBefore = totalBefore + before[index].value;

    totalAfter = totalAfter + after[index].value;

    const change = after[index].value - before[index].value;

    const row = document.createElement("tr");

    row.innerHTML = `<td>${before[index].name}</td><td>${naira(before[index].value)}</td><td class="change">${signedNaira(change)}</td><td>${naira(after[index].value)}</td>`;

    body.appendChild(row);
  }

  const total = document.createElement("tr");

  total.className = "end-total";

  total.innerHTML = `<td>Whole fund</td><td>${naira(totalBefore)}</td><td>${signedNaira(totalAfter - totalBefore)}</td><td>${naira(totalAfter)}</td>`;

  body.appendChild(total);

  document.getElementById("end-day-label").textContent = `Day ${state.day}`;

  const allowed = (meta.won_cost_bps / 10_000) * meta.fund_naira;

  const under = allowed - lost;

  const verdict = under >= 0 ? `<b class="budget-ok">${naira(under)} under budget</b>` : `<b class="budget-over">${naira(-under)} over budget</b>`;

  document.getElementById("end-holdings-note").innerHTML = `The fund shrinks because it does its job: it paid <b>${naira(state.paid_out_naira)}</b> to retirees. The part that shows the agent's skill is selling: it spent <b>${naira(lost)}</b> on exchange fees and price dips, against a <b>${naira(allowed)}</b> selling budget - ${verdict}. Shares are valued at their starting prices, as on the towers.`;
}

// A yardstick on the same game: the fortune teller (the planner that sees the future), played by the server.
// It is not always the best possible result, so the page only compares, it does not call it perfect.
function fundTotal(state) {
  return state.cash_naira + state.settling_naira + state.tbills_naira + state.banks_naira_book + state.small_caps_naira_book;
}

async function showBenchmark(state) {
  const box = document.getElementById("end-benchmark");

  box.hidden = true;

  if (!meta || meta.player === "perfect_foresight") {
    return;
  }

  try {
    const response = await fetch("/episode", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ player: "perfect_foresight", seed: meta.seed, market: meta.market }),
    });

    if (!response.ok) {
      return;
    }

    const log = await response.json();

    const teller = log.days[log.days.length - 1].state;

    const allowed = (meta.won_cost_bps / 10_000) * meta.fund_naira;

    const agentLeft = allowed - (state.cost_bps / 10_000) * meta.fund_naira;

    const tellerLeft = allowed - (teller.cost_bps / 10_000) * meta.fund_naira;

    const tellerResult = teller.outcome === "won" ? "won" : "lost";

    let verdict = `The agent finished ${naira(tellerLeft - agentLeft)} of budget behind a player that sees the future.`;

    if (agentLeft >= tellerLeft) {
      verdict = "The agent did as well as or better than a player that sees the future.";
    }

    box.innerHTML = `<p class="end-sub">Compared with the fortune teller</p><p>On this same game, a player that can see the future ${tellerResult}, with <b>${naira(Math.max(tellerLeft, 0))}</b> of budget left and a fund of <b>${naira(fundTotal(teller))}</b> at the end (the agent: ${naira(Math.max(agentLeft, 0))} left, ${naira(fundTotal(state))}). ${verdict}</p>`;

    box.hidden = false;
  } catch (error) {
    box.hidden = true;
  }
}

function showEnd(message) {
  const state = message.state;

  const won = state.outcome === "won";

  document.getElementById("end-title").textContent = won ? "WON" : "LOST";

  document.getElementById("end-title").className = won ? "end-title end-won" : "end-title end-lost";

  document.getElementById("end-reason").textContent = plainOutcome(message, meta);

  document.getElementById("end-points").textContent = (budgetPoints(meta) + state.total_points).toFixed(2);

  const lost = (state.cost_bps / 10_000) * meta.fund_naira;

  const allowed = (meta.won_cost_bps / 10_000) * meta.fund_naira;

  document.getElementById("end-budget").textContent = lost <= allowed ? naira(allowed - lost) : `over by ${naira(lost - allowed)}`;

  document.getElementById("end-cost").textContent = naira(lost);

  document.getElementById("end-forced").textContent = state.forced_event_count;

  document.getElementById("end-invalid").textContent = state.invalid_actions;

  document.getElementById("end-paid").textContent = naira(state.paid_out_naira);

  showHoldingsChange(state, lost);

  showBenchmark(state);

  elements.endOverlay.hidden = false;
}

// Once a forced sale happens the game is lost, but every game runs its full 60 days (the rules and every
// result depend on that), so the page says so and offers to jump to the end.
function firstForcedDay(state) {
  if (state.forced_events.length === 0) {
    return 0;
  }

  return Number(state.forced_events[0].split(":")[0].replace("day ", ""));
}

function showLostBanner(message) {
  const banner = document.getElementById("lost-banner");

  const lost = message.state.forced_event_count > 0 && !message.finished;

  banner.hidden = !lost;

  if (!lost) {
    return;
  }

  document.getElementById("lost-text").textContent = `This game is lost - forced sale on day ${firstForcedDay(message.state)}. The agent keeps playing to day ${meta ? meta.horizon_days : 60}, because every game runs its full length.`;

  document.getElementById("skip-end").hidden = !gameRunning;
}

function skipToEnd() {
  if (speedBeforeSkip === "" && speed !== "instant") {
    speedBeforeSkip = speed;
  }

  setSpeed("instant");

  if (paused) {
    paused = false;

    send({ type: "play" });
  }

  updateButtons();

  document.getElementById("lost-banner").hidden = true;
}

function handleMessage(message) {
  if (message.type === "error") {
    showNotice(message.message);

    return;
  }

  if (message.type === "meta") {
    meta = message.meta;

    setFund(meta.fund_naira);

    elements.playerLabel.textContent = playerLine(meta);

    showPreview(meta);

    return;
  }

  recordDay(message);

  updatePayouts(message.state);

  lastMessage = message;

  dayLog.push(message);

  const instant = speed === "instant";

  if (!instant || message.finished || paused) {
    showDay(message, instant);

    showLostBanner(message);
  }

  if (pauseAtDay > 0 && message.state.day === pauseAtDay) {
    paused = true;

    updateButtons();
  }

  if (message.finished) {
    gameFinished = true;

    updateButtons();

    showEnd(message);
  }

  updateReview();
}

// Rewind: redraw the screen exactly as it was on an earlier day, rebuilding the charts and the payout queue
// from day 0 up to that day. The game itself is not replayed; these are the days the server already sent.
function rebuildUpTo(index) {
  priceHistory = [];

  pointsHistory = [];

  resetPayouts();

  for (let day = 0; day <= index; day++) {
    recordDay(dayLog[day]);

    updatePayouts(dayLog[day].state);
  }
}

function showLoggedDay(index) {
  const last = dayLog.length - 1;

  const target = Math.min(Math.max(index, 0), last);

  if (gameRunning && !paused && !gameFinished) {
    onPause();
  }

  viewing = target === last ? -1 : target;

  rebuildUpTo(target);

  showDay(dayLog[target], true);

  showLostBanner(dayLog[target]);

  elements.endOverlay.hidden = true;

  updateReview();
}

function updateReview() {
  const review = document.getElementById("review");

  const note = document.getElementById("review-note");

  const canReview = dayLog.length > 1 && (paused || gameFinished || !gameRunning);

  review.hidden = !canReview;

  if (!canReview) {
    note.hidden = true;

    return;
  }

  const last = dayLog.length - 1;

  const shown = viewing === -1 ? last : viewing;

  const slider = document.getElementById("day-slider");

  slider.max = String(last);

  slider.value = String(shown);

  document.getElementById("day-back").disabled = shown <= 0;

  document.getElementById("day-forward").disabled = shown >= last;

  document.getElementById("day-latest").disabled = viewing === -1;

  note.hidden = viewing === -1;

  note.textContent = `Looking back at day ${dayLog[shown].state.day}. The game has reached day ${dayLog[last].state.day}; press Latest or Play to return.`;
}

function stepBack() {
  const last = dayLog.length - 1;

  showLoggedDay((viewing === -1 ? last : viewing) - 1);
}

function stepForward() {
  const last = dayLog.length - 1;

  showLoggedDay((viewing === -1 ? last : viewing) + 1);
}

function showLatest() {
  showLoggedDay(dayLog.length - 1);
}

function onPlay() {
  const settingsChanged = settingsKey() !== gameSettingsKey;

  if (viewing !== -1 && dayLog.length > 0) {
    showLatest();
  }

  if (!gameRunning || gameFinished || settingsChanged) {
    startGame({ paused: false });

    return;
  }

  paused = false;

  send({ type: "play" });

  updateButtons();
}

function onPause() {
  paused = true;

  send({ type: "pause" });

  if (lastMessage && viewing === -1) {
    showDay(lastMessage, true);
  }

  updateButtons();

  updateReview();
}

function onStep() {
  const settingsChanged = settingsKey() !== gameSettingsKey;

  if (viewing !== -1 && dayLog.length > 0) {
    showLatest();
  }

  if (!gameRunning || gameFinished || settingsChanged) {
    startGame({ paused: true });

    return;
  }

  paused = true;

  send({ type: "pause" });

  send({ type: "step" });

  updateButtons();
}

// Changing the player, game or market starts that game straight away, keeping the chosen speed.
function restartWithNewSettings() {
  if (settingsKey() === gameSettingsKey && gameRunning) {
    return;
  }

  startGame({ paused: false });
}

function randomSeed() {
  elements.seed.value = String(Math.floor(Math.random() * 900_000) + 100_000);
}

function connectControls() {
  elements.play.addEventListener("click", onPlay);

  elements.pause.addEventListener("click", onPause);

  elements.step.addEventListener("click", onStep);

  document.getElementById("skip-end").addEventListener("click", skipToEnd);

  document.getElementById("day-back").addEventListener("click", stepBack);

  document.getElementById("day-forward").addEventListener("click", stepForward);

  document.getElementById("day-latest").addEventListener("click", showLatest);

  document.getElementById("day-slider").addEventListener("input", function onSlide(event) {
    showLoggedDay(Number(event.target.value));
  });

  window.addEventListener("keydown", function onArrow(event) {
    if (event.target.tagName === "INPUT" || event.target.tagName === "SELECT" || dayLog.length < 2) {
      return;
    }

    if (event.key === "ArrowLeft") {
      stepBack();
    }

    if (event.key === "ArrowRight" && (paused || gameFinished || !gameRunning)) {
      stepForward();
    }
  });

  elements.randomGame.addEventListener("click", function onRandomClick() {
    randomSeed();

    restartWithNewSettings();
  });

  elements.player.addEventListener("change", restartWithNewSettings);

  elements.market.addEventListener("change", restartWithNewSettings);

  elements.seed.addEventListener("change", restartWithNewSettings);

  for (const button of document.querySelectorAll(".speed")) {
    button.addEventListener("click", () => setSpeed(button.dataset.speed));
  }

  elements.help.addEventListener("click", () => { elements.helpOverlay.hidden = false; });

  elements.helpClose.addEventListener("click", () => { elements.helpOverlay.hidden = true; });

  elements.resetView.addEventListener("click", resetView);

  elements.autoOrbit.addEventListener("change", () => setAutoOrbit(elements.autoOrbit.checked));

  elements.showHidden.addEventListener("change", () => document.body.classList.toggle("show-hidden", elements.showHidden.checked));

  elements.showDetails.addEventListener("click", function onDetailsClick() {
    applyDetails(!document.body.classList.contains("detailed"));
  });

  elements.playAgain.addEventListener("click", () => startGame({ paused: false }));

  elements.newGame.addEventListener("click", () => {
    randomSeed();

    startGame({ paused: false });
  });

  window.addEventListener("resize", drawCharts);
}

async function replayGame(pauseAt) {
  resetGameView();

  const response = await fetch("/episode", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ player: elements.player.value, seed: Number(elements.seed.value), market: elements.market.value }),
  });

  const log = await response.json();

  if (!response.ok) {
    showNotice(log.detail);

    return;
  }

  handleMessage({ type: "meta", meta: log.meta });

  const lastDay = pauseAt > 0 ? pauseAt : log.days.length - 1;

  for (let index = 0; index <= lastDay; index++) {
    recordDay(log.days[index]);

    updatePayouts(log.days[index].state);

    lastMessage = log.days[index];

    dayLog.push(log.days[index]);
  }

  showDay(lastMessage, true);

  updateReview();

  showLostBanner(lastMessage);

  if (lastMessage.finished) {
    showEnd(lastMessage);
  }
}

async function main() {
  const options = new URLSearchParams(location.search);

  createScene(document.getElementById("scene"));

  connectControls();

  const savedDetails = localStorage.getItem("thinbook-detailed") === "1";

  applyDetails(options.has("detailed") ? options.get("detailed") === "1" : savedDetails);

  await loadPlayers(options.get("player") || "ppo");

  elements.seed.value = options.get("seed") || "100000";

  elements.market.value = options.get("market") === "hard" ? "hard" : "normal";

  const wantedSpeed = options.get("speed");

  setSpeed(SPEEDS.includes(wantedSpeed) ? wantedSpeed : "slow");

  updateButtons();

  drawCharts();

  if (options.get("replay") === "1") {
    await replayGame(Number(options.get("pause_at") || 0));

    return;
  }

  if (options.get("autoplay") === "1") {
    startGame({ paused: false, pauseAt: Number(options.get("pause_at") || 0) });
  }
}

main();
