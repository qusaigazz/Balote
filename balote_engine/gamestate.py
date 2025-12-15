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
    def to_initial_snapshot(
        self, *, version: int = 1, dealer: int = 0, meta: dict | None = None
    ) -> InitialSnapshot:

        contract_mode = "SUN" if self.trump is None else "HOKM"
        trump_suit = None if self.trump is None else self.trump.value

        hands_8 = {
            i: tuple(card_to_code(c) for c in self.hands[i])
            for i in range(4)
        }

        return InitialSnapshot(
            version=version,
            start_phase="PLAYING",
            playing=PlayingInitial(
                dealer=dealer,
                leader=self.leader,
                contract_mode=contract_mode,
                trump_suit=trump_suit,
                hands_8=hands_8,
            ),
            meta=meta or {},
        )


