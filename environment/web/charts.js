// Two small charts drawn on plain 2D canvas: the stale-price chart (bottom strip) and the running
// total of points (right panel).

const BOARD_COLOUR = "#3b6fb6";
const REAL_COLOUR = "#e07a1f";
const GAP_COLOUR = "rgba(214, 69, 69, 0.16)";
const AXIS_COLOUR = "#9aa5b1";
const TEXT_COLOUR = "#4a5563";
const SALE_COLOUR = "#1f2937";
const BUYER_COLOUR = "#c99a1c";

function prepareCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;

  const width = canvas.clientWidth;

  const height = canvas.clientHeight;

  canvas.width = Math.round(width * ratio);

  canvas.height = Math.round(height * ratio);

  const context = canvas.getContext("2d");

  context.setTransform(ratio, 0, 0, ratio, 0, 0);

  context.clearRect(0, 0, width, height);

  return { context, width, height };
}

function valueRange(lists) {
  let lowest = Infinity;

  let highest = -Infinity;

  for (const list of lists) {
    for (const value of list) {
      lowest = Math.min(lowest, value);

      highest = Math.max(highest, value);
    }
  }

  if (lowest === highest) {
    lowest = lowest - 1;

    highest = highest + 1;
  }

  const padding = (highest - lowest) * 0.12;

  return { lowest: lowest - padding, highest: highest + padding };
}

function drawDayAxis(context, area, horizon, step, prefix) {
  context.strokeStyle = AXIS_COLOUR;

  context.lineWidth = 1;

  context.beginPath();

  context.moveTo(area.left, area.bottom);

  context.lineTo(area.right, area.bottom);

  context.stroke();

  context.fillStyle = TEXT_COLOUR;

  context.font = "11px system-ui, sans-serif";

  for (let day = 0; day <= horizon; day += step) {
    const x = area.left + (day / horizon) * (area.right - area.left);

    context.textAlign = day === horizon ? "right" : day === 0 ? "left" : "center";

    context.fillText(`${prefix}${day}`, x, area.bottom + 14);
  }
}

export function drawPriceChart(canvas, history, horizon, detailed) {
  const { context, width, height } = prepareCanvas(canvas);

  const area = { left: 64, right: width - 16, top: 30, bottom: height - 24 };

  const board = history.map((day) => day.board);

  const real = history.map((day) => day.real);

  drawDayAxis(context, area, horizon, 10, "day ");

  context.fillStyle = TEXT_COLOUR;

  context.font = "600 13px system-ui, sans-serif";

  context.textAlign = "left";

  context.fillText(detailed ? "Small-cap share price" : "Small-company share price - what the agent sees and the real price", 12, 18);

  if (history.length === 0) {
    return;
  }

  const range = valueRange([board, real]);

  const xFor = (day) => area.left + (day / horizon) * (area.right - area.left);

  const yFor = (price) => area.bottom - ((price - range.lowest) / (range.highest - range.lowest)) * (area.bottom - area.top);

  context.font = "11px system-ui, sans-serif";

  context.textAlign = "right";

  context.fillStyle = TEXT_COLOUR;

  const decimals = range.highest - range.lowest < 0.05 ? 3 : 2;

  context.fillText(`₦${range.highest.toFixed(decimals)}`, area.left - 6, area.top + 4);

  context.fillText(`₦${range.lowest.toFixed(decimals)}`, area.left - 6, area.bottom);

  context.fillStyle = GAP_COLOUR;

  for (let index = 0; index < history.length; index++) {
    const day = history[index].day;

    const nextX = index + 1 < history.length ? xFor(history[index + 1].day) : xFor(day) + 2;

    const top = Math.min(yFor(board[index]), yFor(real[index]));

    const bottom = Math.max(yFor(board[index]), yFor(real[index]));

    context.fillRect(xFor(day), top, nextX - xFor(day), bottom - top);
  }

  context.strokeStyle = REAL_COLOUR;

  context.lineWidth = 2;

  context.setLineDash([6, 4]);

  context.beginPath();

  for (let index = 0; index < history.length; index++) {
    const x = xFor(history[index].day);

    const y = yFor(real[index]);

    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  }

  context.stroke();

  context.setLineDash([]);

  context.strokeStyle = BOARD_COLOUR;

  context.lineWidth = 2.5;

  context.beginPath();

  for (let index = 0; index < history.length; index++) {
    const x = xFor(history[index].day);

    const y = yFor(board[index]);

    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, yFor(board[index - 1]));

      context.lineTo(x, y);
    }
  }

  context.stroke();

  let widestIndex = 0;

  for (let index = 0; index < history.length; index++) {
    if (Math.abs(board[index] - real[index]) > Math.abs(board[widestIndex] - real[widestIndex])) {
      widestIndex = index;
    }
  }

  for (const day of history) {
    if (!day.sold && !day.bigBuyer) {
      continue;
    }

    context.fillStyle = day.bigBuyer ? BUYER_COLOUR : SALE_COLOUR;

    context.beginPath();

    context.arc(xFor(day.day), yFor(day.board), day.bigBuyer ? 5 : 3.5, 0, Math.PI * 2);

    context.fill();
  }

  if (Math.abs(board[widestIndex] - real[widestIndex]) > 0) {
    const x = xFor(history[widestIndex].day);

    const upper = Math.min(yFor(board[widestIndex]), yFor(real[widestIndex]));

    const lower = Math.max(yFor(board[widestIndex]), yFor(real[widestIndex]));

    let y = (upper + lower) / 2 + 4;

    if (upper - 14 > area.top) {
      y = upper - 10;
    } else if (lower + 16 < area.bottom) {
      y = lower + 14;
    }

    context.fillStyle = "#b03a3a";

    context.font = "600 12px system-ui, sans-serif";

    context.textAlign = x > (area.left + area.right) / 2 ? "right" : "left";

    const offset = context.textAlign === "right" ? -10 : 10;

    context.fillText(detailed ? "The stale-price gap - what the board hides" : "The difference the agent cannot see", x + offset, y + 4);
  }
}

export function drawPointsChart(canvas, totals, horizon) {
  const { context, width, height } = prepareCanvas(canvas);

  const area = { left: 34, right: width - 8, top: 8, bottom: height - 20 };

  drawDayAxis(context, area, horizon, 20, "day ");

  if (totals.length === 0) {
    return;
  }

  const values = totals.map((point) => point.total);

  const rewards = totals.map((point) => point.reward);

  const range = valueRange([values, rewards, [0]]);

  const xFor = (day) => area.left + (day / horizon) * (area.right - area.left);

  const yFor = (value) => area.bottom - ((value - range.lowest) / (range.highest - range.lowest)) * (area.bottom - area.top);

  context.strokeStyle = "#cfd6de";

  context.setLineDash([3, 3]);

  context.beginPath();

  context.moveTo(area.left, yFor(0));

  context.lineTo(area.right, yFor(0));

  context.stroke();

  context.setLineDash([]);

  context.fillStyle = TEXT_COLOUR;

  context.font = "10px system-ui, sans-serif";

  context.textAlign = "right";

  context.fillText("0", area.left - 4, yFor(0) + 3);

  const lowestText = Math.abs(range.lowest) < 10 ? range.lowest.toFixed(1) : range.lowest.toFixed(0);

  context.fillText(lowestText, area.left - 4, area.bottom);

  const barWidth = Math.max(((area.right - area.left) / horizon) * 0.7, 1);

  for (const point of totals) {
    if (point.day === 0 || Math.abs(point.reward) < 0.005) {
      continue;
    }

    const top = Math.min(yFor(0), yFor(point.reward));

    const height = Math.max(Math.abs(yFor(point.reward) - yFor(0)), 1);

    context.fillStyle = point.reward > 0 ? "rgba(63, 163, 77, 0.7)" : "rgba(214, 69, 69, 0.55)";

    context.fillRect(xFor(point.day) - barWidth / 2, top, barWidth, height);
  }

  context.strokeStyle = values[values.length - 1] < 0 ? "#b03a3a" : "#3fa34d";

  context.lineWidth = 2;

  context.beginPath();

  for (let index = 0; index < totals.length; index++) {
    const x = xFor(totals[index].day);

    const y = yFor(values[index]);

    if (index === 0) {
      context.moveTo(x, y);
    } else {
      context.lineTo(x, y);
    }
  }

  context.stroke();
}
