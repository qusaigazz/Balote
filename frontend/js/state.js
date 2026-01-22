export function buildInitialState(json) {
  const hands = {};

  for (const p in json.initial.bidding.hands_5) {
    hands[p] = [...json.initial.bidding.hands_5[p]];
  }

  return {
    phase: json.initial.start_phase,
    dealer: json.initial.meta.dealer,
    currentPlayer: json.initial.bidding.current_player,
    floorCard: json.initial.bidding.floor_card,

    hands,
    trick: [],
    trickComplete: false,
    tricksWon: { 0: 0, 1: 0, 2: 0, 3: 0 },

    mode: null,
    trump: null,
  };
}

export function applyAction(state, action) {
  const s = structuredClone(state);

  if (s.trickComplete) {
    s.trick = [];
    s.trickComplete = false;
  }

  if (action.type === "FINALIZE_CONTRACT") {
    s.phase = "PLAYING";
    s.mode = action.payload.mode;
    s.trump = action.payload.trump_suit;
    s.currentPlayer = action.payload.floor_taker;
  }

  if (action.type === "PLAY_CARD") {
    const p = action.player;
    const card = action.payload.card;

    s.hands[p] = s.hands[p].filter(c => c !== card);
    s.trick.push({ player: p, card });

    if (s.trick.length === 4) {
      const winner = p;
      s.currentPlayer = winner;
      s.trickComplete = true;
    } else {
      s.currentPlayer = (p + 1) % 4;
    }
  }

  return s;
}

export function computeStateAt(json, step) {
  let state = buildInitialState(json);

  for (let i = 0; i < step; i++) {
    state = applyAction(state, json.actions[i]);
  }

  return state;
}
