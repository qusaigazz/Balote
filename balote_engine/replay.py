from __future__ import annotations
from typing import Iterable

from .savegame import SaveGame
from .gamestate import GameState
from .serialization import code_to_card
from .cards import Suit
from .rules import apply_action


def build_initial_state(save: SaveGame) -> GameState:
    """
    Build the initial GameState from SaveGame.initial (PLAYING only for now).
    """
    p = save.initial.playing
    if p is None:
        raise ValueError("Replay currently supports only start_phase=PLAYING")

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
        scores=(0, 0),        # scoring later
        trick_number=0,
    )


def replay(save: SaveGame) -> GameState:
    """
    Replay all actions and return the final GameState.
    """
    state = build_initial_state(save)
    for action in save.actions:
        state = apply_action(state, action)
    return state


def replay_states(save: SaveGame) -> Iterable[GameState]:
    """
    Yields the state BEFORE any action, then after each action.
    Useful for UI / analyzer stepping.
    """
    state = build_initial_state(save)
    yield state
    for action in save.actions:
        state = apply_action(state, action)
        yield state
