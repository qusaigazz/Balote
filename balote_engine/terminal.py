from __future__ import annotations

from .gamestate import GameState

def is_terminal(state: GameState) -> bool:
    """
    Return True if the current round is finished.

    For 32-card Saudi Baloot:
    - 8 tricks total
    - Round ends when the 8th trick has been resolved
    """
    return state.trick_number == 8 and len(state.trick) == 0

'This file answers the question: “Is this game state finished, meaning no more actions should be played?”'