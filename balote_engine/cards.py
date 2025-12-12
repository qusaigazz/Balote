from enum import Enum
from dataclasses import dataclass


class Suit(Enum):
    HEARTS = "H"
    SPADES = "S"
    DIAMONDS = "D"
    CLUBS = "C"


class Rank(Enum):
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    JACK = 11
    QUEEN = 12
    KING = 13
    TEN = 10
    ACE = 14


@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: Rank