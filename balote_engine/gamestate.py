from dataclasses import dataclass
from typing import Tuple

from .cards import Card, Suit


@dataclass
class GameState:
    hands: Tuple[Tuple[Card, ...], ...]   # 4 players
    trump: Suit | None                   # None = Sun
    leader: int                          # player who led current trick
    to_play: int                         # whose turn it is now
    trick: Tuple[Card, ...]              # cards played in current trick
    scores: Tuple[int, int]              # team scores
    trick_number: int                    # 0..7 (8 tricks total)
