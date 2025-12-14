from .cards import Card, Suit, Rank

# -------------------------------
# Card <-> string encoding
# Used by SaveGame / replay
# -------------------------------

_RANK_TO_CODE = {
    Rank.SEVEN: "7",
    Rank.EIGHT: "8",
    Rank.NINE: "9",
    Rank.TEN: "T",
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
}

_CODE_TO_RANK = {v: k for k, v in _RANK_TO_CODE.items()}


def card_to_code(card: Card) -> str:
    """
    Convert a Card to a stable 2-character code.

    Examples:
        QS = Queen of Spades
        TH = Ten of Hearts
        7D = Seven of Diamonds
    """
    return f"{_RANK_TO_CODE[card.rank]}{card.suit.value}"


def code_to_card(code: str) -> Card:
    """
    Convert a 2-character card code back to a Card.

    Examples:
        QS -> Card(SPADES, QUEEN)
        TH -> Card(HEARTS, TEN)
    """
    if len(code) != 2:
        raise ValueError(f"Invalid card code: {code}")

    rank_code, suit_code = code[0], code[1]

    try:
        rank = _CODE_TO_RANK[rank_code]
        suit = Suit(suit_code)
    except KeyError as e:
        raise ValueError(f"Invalid card code: {code}") from e

    return Card(suit=suit, rank=rank)
