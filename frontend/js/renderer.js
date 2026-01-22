function renderHand(el, cards, hide) {
  const badge = el.querySelector(".player-badge");
  el.innerHTML = "";
  if (badge) {
    el.appendChild(badge);
  }
  for (const c of cards) {
    const div = document.createElement("div");
    div.className = "card";
    if (hide) {
      div.classList.add("back");
      div.textContent = "";
    } else {
      renderCardFace(div, c);
    }
    el.appendChild(div);
  }
}

function renderCardFace(el, card) {
  const suitMap = { S: "♠", H: "♥", D: "♦", C: "♣" };
  if (!card) {
    el.textContent = "-";
    return;
  }
  const suit = card.slice(-1);
  const rankRaw = card.slice(0, -1);
  const rank = rankRaw === "T" ? "10" : rankRaw;

  el.classList.add("face", `suit-${suit}`);
  el.innerHTML = "";

  const rankEl = document.createElement("span");
  rankEl.className = "card-rank";
  rankEl.textContent = rank;

  const suitEl = document.createElement("span");
  suitEl.className = "card-suit";
  suitEl.textContent = suitMap[suit] ?? suit;

  el.appendChild(rankEl);
  el.appendChild(suitEl);
}

function getSeatMap(povPlayer) {
  const seats = [
    { handId: "hand-0", slotIndex: 0, name: "bottom" },
    { handId: "hand-3", slotIndex: 3, name: "right" },
    { handId: "hand-1", slotIndex: 2, name: "top" },
    { handId: "hand-2", slotIndex: 1, name: "left" },
  ];

  const players = [
    povPlayer,
    (povPlayer + 1) % 4,
    (povPlayer + 2) % 4,
    (povPlayer + 3) % 4,
  ];

  const byPlayer = {};
  const bySeat = {};
  seats.forEach((seat, idx) => {
    const player = players[idx];
    byPlayer[player] = seat;
    bySeat[seat.handId] = player;
  });

  return { byPlayer, bySeat };
}

function updateBadge(handEl, playerId, isDealer) {
  const badge = handEl.querySelector(".player-badge");
  if (!badge) return;
  badge.textContent = `P${playerId}`;
  badge.className = `player-badge player-${playerId}`;
  if (isDealer) {
    badge.classList.add("dealer");
  }
}

function updateHandPlayerClass(handEl, playerId) {
  handEl.classList.remove("player-0", "player-1", "player-2", "player-3");
  handEl.classList.add(`player-${playerId}`);
}

export function render(state, lastAction, prevState, povPlayer, showAll) {
  const seatMap = getSeatMap(povPlayer);

  // Clear all active highlights
  for (let p = 0; p < 4; p++) {
    const handEl = document.getElementById(`hand-${p}`);
    handEl.classList.remove("active");
  }

  // Highlight current player
  const activeSeat = seatMap.byPlayer[state.currentPlayer];
  const activeHand = activeSeat ? document.getElementById(activeSeat.handId) : null;
  if (activeHand) {
    activeHand.classList.add("active");
  }

  // Render hands
  for (let p = 0; p < 4; p++) {
    const handEl = document.getElementById(`hand-${p}`);
    const playerId = seatMap.bySeat[handEl.id];
    const cards = state.hands[playerId] ?? [];
    renderHand(handEl, cards, !showAll && playerId !== povPlayer);
    updateBadge(handEl, playerId, playerId === state.dealer);
    updateHandPlayerClass(handEl, playerId);
  }

  // Trick clear
  for (let i = 0; i < 4; i++) {
    const slot = document.getElementById(`trick-${i}`);
    slot.innerHTML = "";
  }

  // Render trick
  const trickCards = state.trick;

  for (let i = 0; i < trickCards.length; i++) {
    const { card, player } = trickCards[i];
    const slotIndex = seatMap.byPlayer[player]?.slotIndex ?? i;
    const slot = document.getElementById(`trick-${slotIndex}`);

    const div = document.createElement("div");
    div.className = "card";
    if (
      lastAction &&
      lastAction.type === "PLAY_CARD" &&
      lastAction.player === player &&
      lastAction.payload?.card === card &&
      prevState &&
      prevState.trick.length === trickCards.length - 1
    ) {
      div.classList.add("in-play");
    }
    if (
      lastAction &&
      lastAction.type === "PLAY_CARD" &&
      lastAction.player === player &&
      lastAction.payload?.card === card
    ) {
      div.classList.add("last");
    }
    renderCardFace(div, card);
    slot.appendChild(div);
  }

  document.getElementById("contract").textContent = state.mode ?? "-";

  const floorWrap = document.getElementById("floor-card");
  if (floorWrap) {
    floorWrap.innerHTML = "";
    const cardEl = document.createElement("div");
    cardEl.className = "card floor";
    if (state.floorCard) {
      renderCardFace(cardEl, state.floorCard);
    } else {
      cardEl.textContent = "-";
    }
    floorWrap.appendChild(cardEl);
  }
}
