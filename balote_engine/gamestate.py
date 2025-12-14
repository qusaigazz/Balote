from dataclasses import dataclass
from typing import Tuple
from .savegame import InitialSnapshot, PlayingInitial
from .serialization import card_to_code
from .cards import Card, Suit


@dataclass(frozen=True)
class GameState:
    hands: Tuple[Tuple[Card, ...], ...]   # 4 players
    trump: Suit | None                   # None = Sun
    leader: int                          # player who led current trick
    to_play: int                         # whose turn it is now
    trick: Tuple[Card, ...]              # cards played in current trick
    scores: Tuple[int, int]              # team scores
    trick_number: int                    # 0..7 (8 tricks total)


    # for taking initial gamestate and using it for replay analysis 
    def to_initial_snapshot(self, *, version: int = 1, meta: dict | None = None) -> InitialSnapshot:
        hands_codes = tuple(
            tuple(card_to_code(c) for c in hand)
            for hand in self.hands
        )
        trump_code = self.trump.value if self.trump is not None else None

        return InitialSnapshot(
            version=version,
            start_phase="PLAYING",
            playing=PlayingInitial(
                hands_8=hands_codes,
                trump=trump_code,
                leader=self.leader,
                to_play=self.to_play,
            ),
            meta=meta or {},
        )

