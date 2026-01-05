from __future__ import annotations

"""
Bidding -> Playing resolver (deterministic).

Converts:
- BiddingInitial (hands_5 + floor_card + stock)
- bidding action log (must include FINALIZE_CONTRACT)

Into:
- PlayingInitial (hands_8 + contract_mode + trump_suit + leader)
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from .savegame import Action, BiddingInitial, PlayingInitial


def right_of_dealer(dealer: int) -> int:
    """Player index to the right of dealer (first bidder / first trick leader)."""
    return (dealer + 1) % 4


@dataclass(frozen=True)
class FinalizedContract:
    mode: str  # "SUN" | "HOKM"
    trump_suit: Optional[str]  # None for SUN, else "H"/"S"/"D"/"C"
    winning_bidder: int
    floor_taker: int
    bid_kind: str  # "SUN" | "ASHKAL" | "HOKM" | "HOKM_THANI"


def _find_finalized_contract(actions: Iterable[Action]) -> FinalizedContract:
    finals = [a for a in actions if a.type == "FINALIZE_CONTRACT"]
    if not finals:
        raise ValueError("BIDDING replay requires a FINALIZE_CONTRACT action (not found).")
    if len(finals) > 1:
        raise ValueError("Multiple FINALIZE_CONTRACT actions found.")

    a = finals[0]
    p = a.payload
    try:
        mode = p["mode"]
        trump_suit = p.get("trump_suit")
        winning_bidder = int(p["winning_bidder"])
        floor_taker = int(p["floor_taker"])
        bid_kind = p["bid_kind"]
    except KeyError as e:
        raise ValueError(f"FINALIZE_CONTRACT missing payload field: {e}") from e

    if mode not in ("SUN", "HOKM"):
        raise ValueError(f"Invalid contract mode: {mode}")
    if mode == "SUN" and trump_suit is not None:
        raise ValueError("SUN contract must have trump_suit=None")
    if mode == "HOKM" and trump_suit is None:
        raise ValueError("HOKM contract requires trump_suit")
    if bid_kind not in ("SUN", "ASHKAL", "HOKM", "HOKM_THANI"):
        raise ValueError(f"Invalid bid_kind: {bid_kind}")

    return FinalizedContract(
        mode=mode,
        trump_suit=trump_suit,
        winning_bidder=winning_bidder,
        floor_taker=floor_taker,
        bid_kind=bid_kind,
    )


def _complete_deal_to_8(
    *,
    hands_5: Dict[int, Tuple[str, ...]],
    floor_card: str,
    stock: Tuple[str, ...],
    floor_taker: int,
    dealer: int,
) -> Dict[int, Tuple[str, ...]]:
    """
    Complete the 5-card + floor-card deal into full 8-card hands.

    Rules:
    - floor_taker receives the floor_card (5 -> 6)
    - then deal remaining cards from stock in table order starting from right_of_dealer(dealer)
      until each player has 8 cards (floor_taker needs 2, others need 3)
    """
    hands: Dict[int, list[str]] = {i: list(hands_5[i]) for i in range(4)}

    if any(len(hands[i]) != 5 for i in range(4)):
        raise ValueError("Expected hands_5 to contain exactly 5 cards per player")

    hands[floor_taker].append(floor_card)

    start = right_of_dealer(dealer)

    stock_i = 0
    for k in range(4):
        i = (start + k) % 4
        need = 8 - len(hands[i])
        if need < 0:
            raise ValueError("A hand exceeded 8 cards during deal completion")
        if stock_i + need > len(stock):
            raise ValueError("Not enough cards in stock to complete deal")
        hands[i].extend(stock[stock_i : stock_i + need])
        stock_i += need

    if any(len(hands[i]) != 8 for i in range(4)):
        raise ValueError("Deal completion failed: not all hands reached 8 cards")
    if stock_i != len(stock):
        raise ValueError(f"Stock not fully consumed: used {stock_i} of {len(stock)}")

    return {i: tuple(hands[i]) for i in range(4)}


def resolve_bidding_to_playing_initial(
    bidding: BiddingInitial,
    actions: Iterable[Action],
) -> PlayingInitial:
    """
    Convert bidding snapshot + action log to the PlayingInitial snapshot.
    """
    final = _find_finalized_contract(actions)

    hands_8 = _complete_deal_to_8(
        hands_5=bidding.hands_5,
        floor_card=bidding.floor_card,
        stock=bidding.stock,
        floor_taker=final.floor_taker,
        dealer=bidding.dealer,
    )

    leader = right_of_dealer(bidding.dealer)

    return PlayingInitial(
        dealer=bidding.dealer,
        leader=leader,
        contract_mode=final.mode,  # "SUN" or "HOKM"
        trump_suit=final.trump_suit,
        hands_8=hands_8,
    )
