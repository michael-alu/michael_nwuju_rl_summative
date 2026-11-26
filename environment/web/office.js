// The fund manager's office beside the vault: the agent as a character at a desk.
// Every day it turns to the tower it sells (or stays put when it waits), says what it is doing,
// and the day's reward floats up from its head, so the score visibly rises and falls.

import * as THREE from "three";
import { CSS2DObject } from "three/addons/CSS2DRenderer.js";

export const OFFICE_X = -10.2;

const AGENT_Z = -0.3;
const ACTION_SECONDS = 1.1;
const SHAKE_SECONDS = 0.8;

const COLOURS = {
  floor: 0xe9dfd0,
  wall: 0xf7f3ec,
  desk: 0xa47148,
  chair: 0x3a3f47,
  suit: 0x2d3e5c,
  shirt: 0xf5f5f5,
  tie: 0xc0392b,
  skin: 0x8d5524,
  eyes: 0x1b1b1b,
  screenIdle: 0x9fc5e8,
  plant: 0x4f8a3c,
  pot: 0xc4774b,
};

const SCREEN_COLOURS = {
  Wait: 0x9fc5e8,
  "Sell T-bills": 0x2a9d8f,
  "Sell bank shares": 0x3b6fb6,
  "Sell small-cap shares": 0xe09f3e,
  "Call a big buyer": 0xf2c14e,
};

const SPEECH = {
  Wait: "I'll wait today",
  "Sell T-bills": "Selling government bills",
  "Sell bank shares": "Selling bank shares",
  "Sell small-cap shares": "Selling small-company shares",
  "Call a big buyer": "Calling the big buyer!",
};

let swivel;
let rightArm;
let leftArm;
let head;
let screen;
let speech;
let rewardPop;
let scoreboard;
let targetAngle = 0;
let actionLeft = 0;
let shakeLeft = 0;
let alarmLeft = 0;
let ending = "";

function material(colour) {
  return new THREE.MeshStandardMaterial({ color: colour, roughness: 0.7 });
}

function box(width, height, depth, colour) {
  return new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), material(colour));
}

function label(className) {
  const element = document.createElement("div");

  element.className = className;

  return new CSS2DObject(element);
}

function makeArm(side) {
  const shoulder = new THREE.Group();

  shoulder.position.set(side * 0.52, 2.12, 0);

  const arm = new THREE.Mesh(new THREE.CapsuleGeometry(0.11, 0.55, 4, 10), material(COLOURS.suit));

  arm.position.y = -0.38;

  const hand = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 10), material(COLOURS.skin));

  hand.position.y = -0.72;

  shoulder.add(arm);

  shoulder.add(hand);

  shoulder.rotation.x = -0.9;

  return shoulder;
}

function makeAgent() {
  const group = new THREE.Group();

  const seat = box(1.0, 0.14, 1.0, COLOURS.chair);

  seat.position.y = 0.95;

  const back = box(1.0, 1.2, 0.12, COLOURS.chair);

  back.position.set(0, 1.6, -0.5);

  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.9, 10), material(COLOURS.chair));

  post.position.y = 0.45;

  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.42, 0.62, 6, 16), material(COLOURS.suit));

  torso.position.y = 1.78;

  const shirt = box(0.3, 0.5, 0.05, COLOURS.shirt);

  shirt.position.set(0, 1.98, 0.4);

  const tie = box(0.11, 0.46, 0.06, COLOURS.tie);

  tie.position.set(0, 1.94, 0.43);

  head = new THREE.Group();

  head.position.y = 2.68;

  const face = new THREE.Mesh(new THREE.SphereGeometry(0.36, 24, 18), material(COLOURS.skin));

  const leftEye = new THREE.Mesh(new THREE.SphereGeometry(0.045, 10, 8), material(COLOURS.eyes));

  leftEye.position.set(-0.12, 0.06, 0.32);

  const rightEye = leftEye.clone();

  rightEye.position.x = 0.12;

  head.add(face);

  head.add(leftEye);

  head.add(rightEye);

  rightArm = makeArm(1);

  leftArm = makeArm(-1);

  for (const part of [seat, back, post, torso, shirt, tie, head, rightArm, leftArm]) {
    group.add(part);
  }

  return group;
}

function makeDesk() {
  const desk = new THREE.Group();

  const top = box(2.6, 0.12, 1.15, COLOURS.desk);

  top.position.y = 1.3;

  desk.add(top);

  for (const [x, z] of [[-1.2, -0.48], [1.2, -0.48], [-1.2, 0.48], [1.2, 0.48]]) {
    const leg = box(0.1, 1.25, 0.1, COLOURS.desk);

    leg.position.set(x, 0.63, z);

    desk.add(leg);
  }

  const stand = box(0.08, 0.35, 0.08, COLOURS.chair);

  stand.position.set(-0.75, 1.52, 0.15);

  desk.add(stand);

  const frame = box(1.0, 0.65, 0.06, COLOURS.chair);

  frame.position.set(-0.75, 1.98, 0.15);

  frame.rotation.y = 0.5;

  desk.add(frame);

  screen = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.55), new THREE.MeshStandardMaterial({ color: COLOURS.screenIdle, emissive: COLOURS.screenIdle, emissiveIntensity: 0.6, side: THREE.DoubleSide }));

  screen.position.set(-0.75, 1.98, 0.19);

  screen.rotation.y = 0.5;

  desk.add(screen);

  desk.position.set(OFFICE_X, 0, 0.75);

  return desk;
}

function makePlant() {
  const plant = new THREE.Group();

  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.22, 0.5, 14), material(COLOURS.pot));

  pot.position.y = 0.25;

  const leaves = new THREE.Mesh(new THREE.SphereGeometry(0.5, 14, 12), material(COLOURS.plant));

  leaves.position.y = 0.9;

  plant.add(pot);

  plant.add(leaves);

  plant.position.set(OFFICE_X - 1.7, 0, -1.6);

  return plant;
}

export function createOffice(scene) {
  const floor = box(4.8, 0.3, 5.5, COLOURS.floor);

  floor.position.set(OFFICE_X, -0.15, 0);

  floor.receiveShadow = true;

  scene.add(floor);

  const wall = box(4.8, 3.6, 0.15, COLOURS.wall);

  wall.position.set(OFFICE_X, 1.8, -2.7);

  scene.add(wall);

  scene.add(makeDesk());

  scene.add(makePlant());

  swivel = makeAgent();

  swivel.position.set(OFFICE_X, 0, AGENT_Z);

  swivel.traverse((part) => { part.castShadow = true; });

  scene.add(swivel);

  scoreboard = label("scoreboard");

  scoreboard.position.set(OFFICE_X, 4.85, -2.6);

  scene.add(scoreboard);

  speech = label("speech-bubble");

  speech.position.set(OFFICE_X, 3.55, AGENT_Z);

  speech.visible = false;

  scene.add(speech);

  rewardPop = label("reward-pop-anchor");

  rewardPop.position.set(OFFICE_X + 2.4, 2.7, AGENT_Z + 0.6);

  scene.add(rewardPop);

  setBudgetBoard(null, 0, 0, null, 0);
}

function angleTowards(x, z) {
  return Math.atan2(x - OFFICE_X, z - AGENT_Z);
}

function setScoreboard(total, change, day) {
  const arrow = change > 0.005 ? "&#9650;" : change < -0.005 ? "&#9660;" : "&#9679;";

  const direction = change > 0.005 ? "up" : change < -0.005 ? "down" : "flat";

  scoreboard.element.innerHTML = `<span class="scoreboard-title">Score</span><strong>${total.toFixed(2)}</strong><span class="scoreboard-change scoreboard-${direction}">${arrow} ${change >= 0 ? "+" : ""}${change.toFixed(2)}</span>`;

  scoreboard.element.dataset.day = String(day);
}

function isDetailed() {
  return document.body.classList.contains("detailed");
}

function naira(amount) {
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

// The simple view's scoreboard: the selling budget left (the win line minus the money lost when selling so
// far) and what today used of it. Budget left above zero is the same test as the game's own cost rule.
function signedPoints(value) {
  if (value > 0.005) {
    return `+${value.toFixed(2)}`;
  }

  if (value < -0.005) {
    return `−${Math.abs(value).toFixed(2)}`;
  }

  return "0.00";
}

function setBudgetBoard(left, spentToday, day, score, reward) {
  const title = left === null ? "Budget left" : left >= 0 ? "Budget left" : "Over budget";

  const value = left === null ? "₦125K" : naira(Math.abs(left));

  const direction = spentToday > 0.5 ? "down" : "flat";

  const change = spentToday > 0.5 ? `&#9660; ${naira(spentToday)} used today` : "&#9679; nothing used today";

  const scoreLine = score === null ? "Score 12.50" : `Score ${score.toFixed(2)} (${signedPoints(reward)} today)`;

  scoreboard.element.innerHTML = `<span class="scoreboard-title">${title}</span><strong>${value}</strong><span class="scoreboard-change scoreboard-${direction}">${change}</span><span class="scoreboard-points">${scoreLine}</span>`;

  scoreboard.element.dataset.day = String(day);
}

function spentToday(state) {
  let spent = 0;

  for (const trade of state.trades) {
    spent = spent + trade.cost;
  }

  return spent;
}

function popSpend(state, finished, reward) {
  const element = rewardPop.element;

  const spent = spentToday(state);

  let forced = false;

  for (const trade of state.trades) {
    if (trade.reason.startsWith("forced")) {
      forced = true;
    }
  }

  let text = spent > 0.5 ? `−${naira(spent)}` : "₦0";

  let caption = `${signedPoints(reward)} points today`;

  let kind = spent > 0.5 ? "reward-down" : "reward-flat";

  if (state.invalid_action) {
    text = "Wasted move";

    caption = `nothing happened, ${signedPoints(reward)} point`;

    kind = "reward-down";
  }

  if (forced) {
    caption = `forced sale, ${signedPoints(reward)} points`;

    kind = "reward-down";
  }

  if (finished) {
    text = state.outcome === "won" ? "WON" : "LOST";

    caption = `${signedPoints(reward)} points today`;

    kind = state.outcome === "won" ? "reward-up" : "reward-down";
  }

  element.innerHTML = `<div class="reward-pop ${kind}"><strong>${text}</strong><span>${caption}</span></div>`;
}

function popReward(reward, caption) {
  const element = rewardPop.element;

  const sign = reward > 0.005 ? "+" : "";

  const kind = reward > 0.005 ? "reward-up" : reward < -0.005 ? "reward-down" : "reward-flat";

  element.innerHTML = `<div class="reward-pop ${kind}"><strong>${sign}${reward.toFixed(2)}</strong><span>${caption}</span></div>`;
}

function rewardCaption(state, reward, finished) {
  if (finished) {
    return state.outcome === "won" ? "win bonus included" : "loss penalty included";
  }

  if (state.invalid_action) {
    return "wasted move";
  }

  if (state.forced_event_count > 0 && state.trades.some((trade) => trade.reason.startsWith("forced"))) {
    return "forced sale";
  }

  if (Math.abs(reward) <= 0.005) {
    return "nothing lost today";
  }

  return "lost when selling";
}

export function officeDay(message, targets, instant, meta) {
  const state = message.state;

  const reward = message.reward;

  const change = state.day === 0 ? 0 : reward;

  const allowed = (meta.won_cost_bps / 10_000) * meta.fund_naira;

  const left = allowed - (state.cost_bps / 10_000) * meta.fund_naira;

  const budgetPoints = allowed / 10_000;

  if (isDetailed()) {
    setScoreboard(budgetPoints + state.total_points, change, state.day);
  } else {
    setBudgetBoard(left, state.day === 0 ? 0 : spentToday(state), state.day, budgetPoints + state.total_points, change);
  }

  if (state.day === 0) {
    ending = "";

    speech.visible = true;

    speech.element.textContent = "Ready for day 1";

    rewardPop.element.innerHTML = "";

    return;
  }

  const name = state.action_name;

  let words = SPEECH[name] || name;

  let forced = false;

  for (const trade of state.trades) {
    if (trade.reason.startsWith("forced")) {
      forced = true;
    }
  }

  if (state.invalid_action) {
    words = name === "Call a big buyer" ? "No big buyer today. Wasted move." : "Nothing left to sell. Wasted move.";

    shakeLeft = SHAKE_SECONDS;
  }

  if (forced) {
    words = "Forced to sell!";

    alarmLeft = ACTION_SECONDS * 1.5;
  }

  if (message.finished) {
    ending = state.outcome;

    words = state.outcome === "won" ? "We did it!" : "We lost this one";
  }

  speech.visible = true;

  speech.element.textContent = words;

  speech.element.className = forced || state.invalid_action ? "speech-bubble speech-alarm" : "speech-bubble";

  const target = targets[name];

  targetAngle = target && !state.invalid_action ? angleTowards(target.x, target.z) : 0;

  actionLeft = target && !state.invalid_action ? ACTION_SECONDS : 0;

  screen.material.color.set(SCREEN_COLOURS[name] || COLOURS.screenIdle);

  screen.material.emissive.set(SCREEN_COLOURS[name] || COLOURS.screenIdle);

  if (isDetailed()) {
    popReward(reward, rewardCaption(state, reward, message.finished));
  } else {
    popSpend(state, message.finished, reward);
  }
}

export function resetOffice() {
  ending = "";

  actionLeft = 0;

  shakeLeft = 0;

  alarmLeft = 0;

  targetAngle = 0;

  rewardPop.element.innerHTML = "";

  speech.visible = false;

  if (isDetailed()) {
    setScoreboard(0, 0, 0);
  } else {
    setBudgetBoard(null, 0, 0, null, 0);
  }
}

function approach(current, target, amount) {
  return current + (target - current) * amount;
}

export function animateOffice(seconds, time) {
  const amount = Math.min(seconds * 7, 1);

  actionLeft = Math.max(actionLeft - seconds, 0);

  shakeLeft = Math.max(shakeLeft - seconds, 0);

  alarmLeft = Math.max(alarmLeft - seconds, 0);

  const facing = actionLeft > 0 ? targetAngle : 0;

  swivel.rotation.y = approach(swivel.rotation.y, facing, amount);

  const pointing = actionLeft > 0 ? -2.2 : -0.9 + Math.sin(time * 9) * 0.08;

  rightArm.rotation.x = approach(rightArm.rotation.x, pointing, amount);

  leftArm.rotation.x = approach(leftArm.rotation.x, -0.9 + Math.sin(time * 9 + 1.5) * 0.08, amount);

  head.rotation.y = shakeLeft > 0 ? Math.sin(time * 22) * 0.45 : approach(head.rotation.y, 0, amount);

  head.rotation.x = approach(head.rotation.x, ending === "lost" ? 0.45 : 0, amount);

  swivel.position.y = 0;

  if (alarmLeft > 0) {
    swivel.position.y = Math.abs(Math.sin(time * 16)) * 0.18;

    screen.material.emissive.set(Math.sin(time * 18) > 0 ? 0xd64545 : 0x5a1010);
  }

  if (ending === "won") {
    swivel.position.y = Math.abs(Math.sin(time * 5)) * 0.35;

    rightArm.rotation.x = approach(rightArm.rotation.x, -3.0, amount);

    leftArm.rotation.x = approach(leftArm.rotation.x, -3.0, amount);
  }

  if (ending === "lost") {
    rightArm.rotation.x = approach(rightArm.rotation.x, -0.2, amount);

    leftArm.rotation.x = approach(leftArm.rotation.x, -0.2, amount);
  }
}
