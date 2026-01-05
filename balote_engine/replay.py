from __future__ import annotations
from typing import Iterable

from .savegame import SaveGame
from .gamestate import GameState
from .serialization import code_to_card
from .cards import Suit
from .rules import apply_action

# NEW: bidding -> playing resolver
from .bidding import resolve_bidding_to_playing_initial


def build_initial_state(save: SaveGame) -> GameState:
    """
    Build the initial GameState from SaveGame.initial.

    Supports:
    - start_phase=PLAYING (existing behavior)
    - start_phase=BIDDING (resolve to PlayingInitial first)
    """
    init = save.initial

    if init.start_phase == "PLAYING":
        p = init.playing
        if p is None:
            raise ValueError("start_phase=PLAYING requires playing initial.")
    elif init.start_phase == "BIDDING":
        b = init.bidding
        if b is None:
            raise ValueError("start_phase=BIDDING requires bidding initial.")
        p = resolve_bidding_to_playing_initial(b, save.actions)
    else:
        raise ValueError(f"Unknown start_phase: {init.start_phase}")

    # hands_8 is stored as: {0: ("QS","7H",...), 1: (...), 2: (...), 3: (...)}
    hands = tuple(
        tuple(code_to_card(code) for code in p.hands_8[i])
        for i in range(4)
    )

    trump = Suit(p.trump_suit) if p.trump_suit is not None else None

    return GameState(
        hands=hands,
        trump=trump,
        leader=p.leader,
        to_play=p.leader,     # leader plays first at trick start
        trick=tuple(),
        scores=(0, 0),
        trick_number=0,
        card_points=(0, 0),
        trick_wins=(0, 0),
    )


def replay(save: SaveGame) -> GameState:
    """
    Replay all actions and return the final GameState.

    Note:
    - Bidding actions are ignored here because they are consumed
      by resolve_bidding_to_playing_initial(...) when start_phase=BIDDING.
    - Only PLAY_CARD actions affect GameState.
    """
    state = build_initial_state(save)
    for action in save.actions:
        if action.type != "PLAY_CARD":
            continue
        state = apply_action(state, action)
    return state


def replay_states(save: SaveGame) -> Iterable[GameState]:
    """
    Yields the state BEFORE any action, then after each PLAY_CARD action.
    (Bidding actions are skipped because they don't change GameState.)
    """
    state = build_initial_state(save)
    yield state
    for action in save.actions:
        if action.type != "PLAY_CARD":
            continue
        state = apply_action(state, action)
        yield state
