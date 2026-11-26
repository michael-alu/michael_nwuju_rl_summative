// The 3D fund vault (three.js): three towers (T-bills, bank shares, small-cap shares), a cash pile,
// the investment limits drawn on the towers, a big-buyer marker and fire-sale flashes, plus the
// fund manager's office (office.js). Tower heights follow the value held at starting prices, the
// same way the limits are measured. setDetailed switches the labels between plain and detailed words.

import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/CSS2DRenderer.js";
import { createOffice, officeDay, animateOffice, resetOffice } from "./office.js";

const HEIGHT_FOR_WHOLE_FUND = 12;
const TOWER_WIDTH = 1.8;
const CASH_RADIUS = 0.95;
const FLASH_SECONDS = 1.6;
const CAMERA_START = new THREE.Vector3(0, 8.8, 20.5);
const CAMERA_TARGET = new THREE.Vector3(-2.3, 2.9, 0);
const LABEL_FRONT = 2.0;

const COLOURS = {
  tbills: 0x2a9d8f,
  banks: 0x3b6fb6,
  smallCaps: 0xe09f3e,
  cash: 0x5aae61,
  forced: 0xd64545,
  limitRing: 0xd64545,
  limitBand: 0x3fa34d,
  platform: 0xdfe5ec,
  briefcase: 0xf2c14e,
};

const TOWER_NAMES = { tbills: "T-bills", banks: "Bank shares", small_caps: "Small-cap shares" };

const SIMPLE_NAMES = { tbills: "Government bills", banks: "Bank shares", small_caps: "Small-company shares" };

let renderer;
let labelRenderer;
let scene;
let camera;
let controls;
let clock;
let towers = {};
let cash;
let banksBand;
let smallCapsRing;
let briefcase;
let breachLabel;
let fundNaira = 10_000_000;
let ringPulsing = false;
let detailed = false;
let lastState = null;
let lastMeta = null;

function naira(amount) {
  if (Math.abs(amount) >= 999_500) {
    return `₦${(amount / 1_000_000).toFixed(2)}M`;
  }

  if (Math.abs(amount) < 500) {
    return "₦0";
  }

  return `₦${(amount / 1_000).toFixed(0)}K`;
}

function heightFor(amount) {
  return Math.max((amount / fundNaira) * HEIGHT_FOR_WHOLE_FUND, 0.02);
}

function makeLabel(className) {
  const element = document.createElement("div");

  element.className = className;

  return new CSS2DObject(element);
}

function makeTower(key, x, colour) {
  const material = new THREE.MeshStandardMaterial({ color: colour, roughness: 0.55, metalness: 0.05 });

  const mesh = new THREE.Mesh(new THREE.BoxGeometry(TOWER_WIDTH, 1, TOWER_WIDTH), material);

  mesh.position.set(x, 0.5, 0);

  mesh.castShadow = true;

  scene.add(mesh);

  const label = makeLabel("tower-label");

  label.visible = false;

  scene.add(label);

  const forcedLabel = makeLabel("forced-label");

  forcedLabel.element.textContent = "FORCED SALE";

  forcedLabel.visible = false;

  scene.add(forcedLabel);

  return { key, x, mesh, material, colour: new THREE.Color(colour), label, forcedLabel, height: 0.02, targetHeight: 0.02, flashLeft: 0 };
}

function makeCash(x) {
  const material = new THREE.MeshStandardMaterial({ color: COLOURS.cash, roughness: 0.6 });

  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(CASH_RADIUS, CASH_RADIUS, 1, 40), material);

  mesh.position.set(x, 0.5, 0);

  scene.add(mesh);

  const ghostMaterial = new THREE.MeshStandardMaterial({ color: COLOURS.cash, transparent: true, opacity: 0.28 });

  const ghost = new THREE.Mesh(new THREE.CylinderGeometry(CASH_RADIUS, CASH_RADIUS, 1, 40), ghostMaterial);

  ghost.position.set(x, 0.5, 0);

  scene.add(ghost);

  const label = makeLabel("tower-label");

  label.visible = false;

  scene.add(label);

  return { x, mesh, ghost, label, height: 0.02, targetHeight: 0.02, ghostHeight: 0.0, targetGhostHeight: 0.0 };
}

function makeBanksBand(x) {
  const material = new THREE.MeshBasicMaterial({ color: COLOURS.limitBand, transparent: true, opacity: 0.16, depthWrite: false });

  const mesh = new THREE.Mesh(new THREE.BoxGeometry(TOWER_WIDTH + 0.5, 1, TOWER_WIDTH + 0.5), material);

  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({ color: COLOURS.limitBand }));

  mesh.add(edges);

  mesh.position.set(x, 1, 0);

  scene.add(mesh);

  const label = makeLabel("limit-label limit-label-green");

  label.element.textContent = "allowed zone";

  scene.add(label);

  return { mesh, label, bottom: 0, top: 1, targetBottom: 0, targetTop: 1 };
}

function makeSmallCapsRing(x) {
  const material = new THREE.MeshStandardMaterial({ color: COLOURS.limitRing, emissive: COLOURS.limitRing, emissiveIntensity: 0.2 });

  const mesh = new THREE.Mesh(new THREE.TorusGeometry(TOWER_WIDTH * 0.85, 0.07, 12, 60), material);

  mesh.rotation.x = Math.PI / 2;

  mesh.position.set(x, 1, 0);

  scene.add(mesh);

  const label = makeLabel("limit-label limit-label-red");

  label.element.textContent = "max 35%";

  scene.add(label);

  return { mesh, material, label, height: 1, targetHeight: 1 };
}

function makeBriefcase(x) {
  const group = new THREE.Group();

  const material = new THREE.MeshStandardMaterial({ color: COLOURS.briefcase, emissive: COLOURS.briefcase, emissiveIntensity: 0.6 });

  const body = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.75, 0.35), material);

  const handle = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.05, 8, 24, Math.PI), material);

  handle.position.y = 0.37;

  group.add(body);

  group.add(handle);

  group.position.set(x, 4, 0);

  group.visible = false;

  scene.add(group);

  const label = makeLabel("buyer-label");

  label.element.textContent = "A big buyer is here today";

  label.visible = false;

  group.add(label);

  label.position.set(0, 0.9, 0);

  group.userData.label = label;

  return group;
}

export function createScene(container) {
  scene = new THREE.Scene();

  scene.background = new THREE.Color(0xf1f4f8);

  camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);

  renderer = new THREE.WebGLRenderer({ antialias: true });

  renderer.setPixelRatio(window.devicePixelRatio);

  renderer.shadowMap.enabled = true;

  container.appendChild(renderer.domElement);

  labelRenderer = new CSS2DRenderer();

  labelRenderer.domElement.className = "label-layer";

  container.appendChild(labelRenderer.domElement);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xb8c2cc, 1.6));

  const sun = new THREE.DirectionalLight(0xffffff, 1.4);

  sun.position.set(6, 14, 8);

  sun.castShadow = true;

  scene.add(sun);

  const platform = new THREE.Mesh(new THREE.BoxGeometry(14.5, 0.4, 5.5), new THREE.MeshStandardMaterial({ color: COLOURS.platform, roughness: 0.9 }));

  platform.position.y = -0.2;

  platform.receiveShadow = true;

  scene.add(platform);

  createOffice(scene);

  towers = {
    tbills: makeTower("tbills", -4.8, COLOURS.tbills),
    banks: makeTower("banks", -1.6, COLOURS.banks),
    small_caps: makeTower("small_caps", 1.6, COLOURS.smallCaps),
  };

  cash = makeCash(4.8);

  banksBand = makeBanksBand(-1.6);

  smallCapsRing = makeSmallCapsRing(1.6);

  briefcase = makeBriefcase(1.6);

  breachLabel = makeLabel("breach-label");

  breachLabel.visible = false;

  scene.add(breachLabel);

  controls = new OrbitControls(camera, renderer.domElement);

  controls.enableDamping = true;

  controls.autoRotateSpeed = 0.6;

  controls.maxPolarAngle = Math.PI * 0.48;

  controls.minDistance = 8;

  controls.maxDistance = 40;

  resetView();

  clock = new THREE.Clock();

  resizeScene(container);

  window.addEventListener("resize", () => resizeScene(container));

  renderer.setAnimationLoop(animate);
}

export function resetView() {
  camera.position.copy(CAMERA_START);

  controls.target.copy(CAMERA_TARGET);

  controls.update();
}

export function setAutoOrbit(enabled) {
  controls.autoRotate = enabled;
}

function resizeScene(container) {
  const width = container.clientWidth;

  const height = container.clientHeight;

  camera.aspect = width / height;

  camera.updateProjectionMatrix();

  renderer.setSize(width, height);

  labelRenderer.setSize(width, height);
}

export function setFund(amount) {
  fundNaira = amount;
}

// What the fund held on day 0, so each tower can show how much it has changed since the start.
let startHoldings = null;

export function setStartHoldings(state) {
  startHoldings = {
    cash: state.cash_naira + state.settling_naira,
    tbills: state.tbills_naira,
    banks: state.banks_naira_book,
    small_caps: state.small_caps_naira_book,
  };
}

function sinceStart(key, now, day) {
  if (!startHoldings || day === 0) {
    return "";
  }

  const change = now - startHoldings[key];

  if (Math.abs(change) < 500) {
    return "<em>no change since day 1</em>";
  }

  const sign = change > 0 ? "+" : "−";

  return `<em class="since">${sign}${naira(Math.abs(change))} since day 1</em>`;
}

function towerLabelText(key, amount, share, day) {
  const name = detailed ? TOWER_NAMES[key] : SIMPLE_NAMES[key];

  const shareLine = detailed ? `<em>${(share * 100).toFixed(0)}% of the fund</em>` : "";

  return `<strong>${name}</strong><span>${naira(amount)}</span>${sinceStart(key, amount, day)}${shareLine}`;
}

export function setDetailed(flag) {
  detailed = flag;

  smallCapsRing.label.element.textContent = detailed ? "limit 35% of the fund" : "max 35%";

  banksBand.label.element.textContent = detailed ? "allowed 35% to 70%" : "allowed zone";

  if (lastState) {
    updateScene(lastState, lastMeta, true);
  }
}

export function sceneDay(message, meta, instant) {
  updateScene(message.state, meta, instant);

  const targets = {
    "Sell T-bills": { x: towers.tbills.x, z: 0 },
    "Sell bank shares": { x: towers.banks.x, z: 0 },
    "Sell small-cap shares": { x: towers.small_caps.x, z: 0 },
    "Call a big buyer": { x: towers.small_caps.x, z: 0 },
  };

  officeDay(message, targets, instant, meta);
}

export function resetScene() {
  startHoldings = null;

  resetOffice();
}

function flashForcedSales(state) {
  for (const trade of state.trades) {
    if (!trade.reason.startsWith("forced")) {
      continue;
    }

    const tower = towers[trade.asset];

    if (tower) {
      tower.flashLeft = FLASH_SECONDS;
    }
  }
}

function breachedTower(state, meta) {
  const weights = state.weights;

  if (weights.small_caps > meta.small_caps_max_share) {
    return "small_caps";
  }

  if (weights.banks > meta.banks_max_share || weights.banks < meta.banks_min_share) {
    return "banks";
  }

  return "";
}

export function updateScene(state, meta, instant) {
  lastState = state;

  lastMeta = meta;

  const bookValue = state.book_value_naira;

  towers.tbills.targetHeight = heightFor(state.tbills_naira);

  towers.banks.targetHeight = heightFor(state.banks_naira_book);

  towers.small_caps.targetHeight = heightFor(state.small_caps_naira_book);

  towers.tbills.label.element.innerHTML = towerLabelText("tbills", state.tbills_naira, state.weights.tbills, state.day);

  towers.banks.label.element.innerHTML = towerLabelText("banks", state.banks_naira_book, state.weights.banks, state.day);

  towers.small_caps.label.element.innerHTML = towerLabelText("small_caps", state.small_caps_naira_book, state.weights.small_caps, state.day);

  cash.targetHeight = heightFor(state.cash_naira);

  cash.targetGhostHeight = state.settling_naira > 0 ? heightFor(state.settling_naira) : 0;

  const arriving = state.settling_naira > 0 ? `<em>+${naira(state.settling_naira)} coming tomorrow</em>` : "";

  cash.label.element.innerHTML = `<strong>Cash</strong><span>${naira(state.cash_naira)}</span>${arriving}${sinceStart("cash", state.cash_naira + state.settling_naira, state.day)}`;

  banksBand.targetBottom = heightFor(meta.banks_min_share * bookValue);

  banksBand.targetTop = heightFor(meta.banks_max_share * bookValue);

  smallCapsRing.targetHeight = heightFor(meta.small_caps_max_share * bookValue);

  briefcase.visible = state.big_buyer_offered_today;

  briefcase.userData.label.visible = state.big_buyer_offered_today;

  showLabels();

  const breached = state.in_breach ? breachedTower(state, meta) : "";

  ringPulsing = breached === "small_caps";

  breachLabel.visible = breached !== "";

  if (breached !== "") {
    const days = state.grace_days_left;

    const what = detailed ? "Over the limit" : breached === "small_caps" ? "Too many small-company shares" : "Bank shares outside their zone";

    breachLabel.element.textContent = days > 0 ? `${what} - ${days} day${days === 1 ? "" : "s"} to fix it` : `${what} - no time left`;

    breachLabel.userData.tower = breached;
  }

  flashForcedSales(state);

  if (instant) {
    snapToTargets();
  }
}

function showLabels() {
  for (const tower of Object.values(towers)) {
    tower.label.visible = true;
  }

  cash.label.visible = true;
}

function snapToTargets() {
  for (const tower of Object.values(towers)) {
    tower.height = tower.targetHeight;
  }

  cash.height = cash.targetHeight;

  cash.ghostHeight = cash.targetGhostHeight;

  banksBand.bottom = banksBand.targetBottom;

  banksBand.top = banksBand.targetTop;

  smallCapsRing.height = smallCapsRing.targetHeight;
}

function approach(current, target, amount) {
  return current + (target - current) * amount;
}

function animate() {
  const seconds = clock.getDelta();

  const amount = Math.min(seconds * 6, 1);

  const time = clock.elapsedTime;

  for (const tower of Object.values(towers)) {
    tower.height = approach(tower.height, tower.targetHeight, amount);

    tower.mesh.scale.y = tower.height;

    tower.mesh.position.y = tower.height / 2;

    tower.label.position.set(tower.x, 0, LABEL_FRONT);

    tower.forcedLabel.position.set(tower.x, tower.height + 0.8, 0);

    tower.flashLeft = Math.max(tower.flashLeft - seconds, 0);

    const flashing = tower.flashLeft > 0 && Math.sin(time * 18) > -0.3;

    tower.material.color.set(flashing ? COLOURS.forced : tower.colour);

    tower.forcedLabel.visible = tower.flashLeft > 0;
  }

  cash.height = approach(cash.height, cash.targetHeight, amount);

  cash.ghostHeight = approach(cash.ghostHeight, cash.targetGhostHeight, amount);

  cash.mesh.scale.y = Math.max(cash.height, 0.02);

  cash.mesh.position.y = cash.mesh.scale.y / 2;

  cash.ghost.visible = cash.ghostHeight > 0.01;

  cash.ghost.scale.y = Math.max(cash.ghostHeight, 0.01);

  cash.ghost.position.y = cash.mesh.scale.y + cash.ghost.scale.y / 2;

  cash.label.position.set(cash.x, 0, LABEL_FRONT);

  banksBand.bottom = approach(banksBand.bottom, banksBand.targetBottom, amount);

  banksBand.top = approach(banksBand.top, banksBand.targetTop, amount);

  banksBand.mesh.scale.y = Math.max(banksBand.top - banksBand.bottom, 0.02);

  banksBand.mesh.position.y = (banksBand.top + banksBand.bottom) / 2;

  banksBand.label.position.set(towers.banks.x - 2.3, banksBand.top - 0.3, 0);

  smallCapsRing.height = approach(smallCapsRing.height, smallCapsRing.targetHeight, amount);

  smallCapsRing.mesh.position.y = smallCapsRing.height;

  smallCapsRing.label.position.set(towers.small_caps.x + 1.9, smallCapsRing.height, 0);

  const pulse = ringPulsing ? 0.5 + 0.5 * Math.sin(time * 6) : 0;

  smallCapsRing.material.emissiveIntensity = 0.2 + pulse * 1.4;

  smallCapsRing.mesh.scale.setScalar(1 + pulse * 0.12);

  const top = towers.small_caps.height;

  briefcase.position.y = Math.max(top, smallCapsRing.height) + 2.6 + Math.sin(time * 2.2) * 0.15;

  briefcase.rotation.y = Math.sin(time * 0.8) * 0.4;

  if (breachLabel.visible) {
    const tower = towers[breachLabel.userData.tower];

    breachLabel.position.set(tower.x, tower.height + 1.0, 0);
  }

  animateOffice(seconds, time);

  controls.update();

  renderer.render(scene, camera);

  labelRenderer.render(scene, camera);
}
