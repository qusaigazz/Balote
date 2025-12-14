from __future__ import annotations
from typing import Iterable
from .savegame import SaveGame, Action
from .gamestate import GameState, code_to_card
from .cards import Suit
from .rules import apply_action  # or whatever your transition function is

def build_initial_state(save: SaveGame) -> GameState:
    p = save.initial.playing
    hands = tuple(
        tuple(code_to_card(code) for code in hand_codes)
        for hand_codes in p.hands_8
    )
    trump = Suit(p.trump) if p.trump is not None else None

    return GameState(
        hands=hands,
        trump=trump,
        leader=p.leader,
        to_play=p.to_play,
        trick=(),
        scores=(0, 0),
        trick_number=0,
    )

def replay(save: SaveGame) -> GameState:
    state = build_initial_state(save)
    for action in save.actions:
        state = apply_action(state, action)
    return state

def replay_states(save: SaveGame) -> Iterable[GameState]:
    """Yields the state BEFORE any action, then after each action."""
    state = build_initial_state(save)
    yield state
    for action in save.actions:
        state = apply_action(state, action)
        yield state
