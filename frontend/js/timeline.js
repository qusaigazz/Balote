export function buildTimeline(actions, onSelect) {
  const tl = document.getElementById("timeline");
  tl.innerHTML = "";

  let inPlaying = false;
  let playsInPhase = 0;

  actions.forEach((a, i) => {
    if (a.type === "FINALIZE_CONTRACT") {
      inPlaying = true;
      playsInPhase = 0;
    }

    const row = document.createElement("div");
    row.className = "timeline-row";
    if (Number.isInteger(a.player)) {
      row.classList.add(`player-${a.player}`);
    }

    const stepEl = document.createElement("span");
    stepEl.className = "timeline-step";
    stepEl.textContent = `[${i}]`;

    const textEl = document.createElement("span");
    textEl.className = "timeline-text";
    textEl.textContent = formatActionLabel(a);

    if (a.type === "FINALIZE_CONTRACT") {
      row.classList.add("contract");
    }

    if (inPlaying && a.type === "PLAY_CARD") {
      if (playsInPhase > 0 && playsInPhase % 4 === 0) {
        row.classList.add("trick-winner");
      }
      playsInPhase += 1;
    }

    row.appendChild(stepEl);
    row.appendChild(textEl);

    row.onclick = () => onSelect(i + 1);

    tl.appendChild(row);
  });
}

export function highlightStep(step) {
  const rows = document.querySelectorAll(".timeline-row");
  rows.forEach((r, i) => {
    r.classList.toggle("active", i === step);
  });
}

function formatActionLabel(action) {
  if (action.type === "PLAY_CARD") {
    return `P${action.player} PLAY ${action.payload?.card ?? "-"}`;
  }

  if (action.type === "FINALIZE_CONTRACT") {
    const mode = action.payload?.mode ?? "-";
    const trump = action.payload?.trump_suit ?? "-";
    return `CONTRACT FINALIZED: ${mode} (${trump})`;
  }

  if (action.type === "PASS") {
    return `P${action.player} PASS`;
  }

  if (action.type?.startsWith("BID_")) {
    return `P${action.player} ${action.type.replace("BID_", "BID ")}`;
  }

  return `P${action.player ?? "-"} ${action.type}`;
}
