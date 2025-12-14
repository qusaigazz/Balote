from __future__ import annotations

import random
from typing import Tuple, List

from .cards import Card, Suit, Rank


def make_deck() -> List[Card]:
    """32-card Baloot deck: ranks 7..A in 4 suits."""
    ranks = (Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.TEN, Rank.ACE)
    deck = [Card(suit, rank) for suit in Suit for rank in ranks]
    return deck


def deal(deck: List[Card], rng: random.Random | None = None) -> Tuple[Tuple[Card, ...], ...]:
    """Shuffle and deal 8 cards to each of 4 players.
        
    To do:
    - When bidding phase is implemented, update dealing to:
      * deal initial partial hands (e.g. 5 cards)
      * run bidding
      * deal remaining cards after contract is chosen
    """
    
    rng = rng or random.Random()
    rng.shuffle(deck)
    hands = [tuple(deck[i*8:(i+1)*8]) for i in range(4)]
    return tuple(hands)
