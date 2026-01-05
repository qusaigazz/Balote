from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Any, Literal, Optional
import json

StartPhase = Literal["BIDDING", "PLAYING"]
ActionType = Literal["PASS", "BID_SUN", "BID_ASHKAL", "BID_HOKM", "BID_HOKM_THANI", "RAISE", "FINALIZE_CONTRACT", "PLAY_CARD",]


# --- Initial snapshots ---

@dataclass(frozen=True)
class BiddingInitial:
    dealer: int
    current_player: int           # who bids first (derived, but store for simplicity)
    hands_5: dict[int, tuple[str, ...]]   # all hands(for reproducability) written in card codes, e.g. "QS"
    floor_card: str               # revealed card in the middle, e.g. "7H"
    stock: tuple[str, ...]        # remaining undealt cards in order (for deterministic completion)

@dataclass(frozen=True)
class PlayingInitial:
    dealer: int                   # optional but useful metadata
    leader: int
    contract_mode: Literal["SUN", "HOKM"]
    trump_suit: Optional[str]     # None for SUN, e.g. "H" for HOKM
    hands_8: dict[int, tuple[str, ...]]

@dataclass(frozen=True)
class InitialSnapshot:
    """
    Holds exactly what existed BEFORE the first player decision.
    Can represent either 'BIDDING' start or 'PLAYING' start.
    """
    version: int
    start_phase: StartPhase
    bidding: Optional[BiddingInitial] = None
    playing: Optional[PlayingInitial] = None
    meta: dict[str, Any] = field(default_factory=dict)  # optional: seed, rules toggles, etc.

    def __post_init__(self):
        # Minimal invariants so you don't create impossible snapshots
        if self.start_phase == "BIDDING" and self.bidding is None:
            raise ValueError("start_phase=BIDDING requires bidding initial.")
        if self.start_phase == "PLAYING" and self.playing is None:
            raise ValueError("start_phase=PLAYING requires playing initial.")


# --- Actions (timeline) ---

@dataclass(frozen=True)
class Action:
    player: int
    type: ActionType
    payload: dict[str, Any]

# --- SaveGame (initial + timeline) ---

@dataclass(frozen=True)
class SaveGame:
    version: int
    initial: InitialSnapshot
    actions: tuple[Action, ...] = ()

    def append(self, action: Action) -> "SaveGame": #creates new savegame with appended action
        return SaveGame(
            version=self.version,
            initial=self.initial,
            actions=self.actions + (action,),
        )

    def to_json(self) -> str:
        # dataclasses -> dict (including nested dataclasses)
        d = asdict(self)
        return json.dumps(d, ensure_ascii=False, indent=2)

    @staticmethod
    def from_json(s: str) -> "SaveGame":
        d = json.loads(s)

        # Rebuild InitialSnapshot + nested initial types
        init = d["initial"]
        bidding = init.get("bidding")
        playing = init.get("playing")

        bidding_obj = BiddingInitial(
            dealer=bidding["dealer"],
            current_player=bidding["current_player"],
            hands_5={int(k): tuple(v) for k, v in bidding["hands_5"].items()},
            floor_card=bidding["floor_card"],
            stock=tuple(bidding["stock"]),
        ) if bidding else None

        playing_obj = PlayingInitial(
            dealer=playing["dealer"],
            leader=playing["leader"],
            contract_mode=playing["contract_mode"],
            trump_suit=playing["trump_suit"],
            hands_8={int(k): tuple(v) for k, v in playing["hands_8"].items()},
        ) if playing else None

        init_obj = InitialSnapshot(
            version=init["version"],
            start_phase=init["start_phase"],
            bidding=bidding_obj,
            playing=playing_obj,
            meta=init.get("meta") or {},
        )

        actions = tuple(Action(**a) for a in d["actions"])
        return SaveGame(version=d["version"], initial=init_obj, actions=actions)
