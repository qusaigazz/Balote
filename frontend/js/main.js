import { loadRound } from "./loader.js";
import { computeStateAt } from "./state.js";
import { render } from "./renderer.js";
import { setupControls } from "./controls.js";
import { buildTimeline, highlightStep } from "./timeline.js";

const ROUND_FILE = "../../games/20260122_181710_SUN_seed0_round10.json";

let json = null;
let currentStep = 0;
let povPlayer = 0;
let showAll = false;
let lastPopupStep = -1;
let toastTimer = null;

async function main() {
  json = await loadRound(ROUND_FILE);

  const maxStep = json.actions.length;

  function update(step) {
    currentStep = step;
    const state = computeStateAt(json, step);
    const prevState = step > 0 ? computeStateAt(json, step - 1) : null;

    const lastAction = step > 0 ? json.actions[step - 1] : null;
    const nextAction = step < json.actions.length ? json.actions[step] : null;
    if (lastAction && Number.isInteger(lastAction.player)) {
      state.currentPlayer = lastAction.player;
    } else if (nextAction && Number.isInteger(nextAction.player)) {
      state.currentPlayer = nextAction.player;
    }

    render(state, lastAction, prevState, povPlayer, showAll);

    highlightStep(Math.max(0, step - 1));

    if (step < lastPopupStep) {
      lastPopupStep = -1;
    }
    if (lastAction && lastAction.type === "PLAY_CARD" && state.trickComplete && step !== lastPopupStep) {
      const winner = nextAction && nextAction.type === "PLAY_CARD"
        ? nextAction.player
        : lastAction.player;
      showToast(`P${winner} won this trick`);
      lastPopupStep = step;
    }
}

  const povOptions = document.getElementById("pov-options");
  if (povOptions) {
    const povButtons = Array.from(povOptions.querySelectorAll("button[data-pov]"));
    const setActivePov = () => {
      povButtons.forEach(btn => {
        btn.classList.toggle("active", Number(btn.dataset.pov) === povPlayer);
      });
    };
    setActivePov();
    povButtons.forEach(btn => {
      btn.onclick = () => {
        povPlayer = Number(btn.dataset.pov);
        setActivePov();
        update(currentStep);
      };
    });
  }

  const showAllBtn = document.getElementById("show-all");
  if (showAllBtn) {
    showAllBtn.onclick = () => {
      showAll = !showAll;
      showAllBtn.setAttribute("aria-pressed", String(showAll));
      showAllBtn.textContent = showAll ? "Hide Hands" : "Show All";
      update(currentStep);
    };
  }

  buildTimeline(json.actions, (i) => setStep(i));

  const setStep = setupControls(maxStep, update);

  setStep(0);
}

function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  if (toastTimer) {
    clearTimeout(toastTimer);
  }
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 900);
}

main();
