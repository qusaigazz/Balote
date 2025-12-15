from __future__ import annotations

from typing import List, Tuple

from .cards import Card, Rank, Suit
from .gamestate import GameState

from .savegame import Action
from .serialization import code_to_card

SUN_ORDER = (
    Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.JACK,
    Rank.QUEEN, Rank.KING, Rank.TEN, Rank.ACE
)

HOKM_TRUMP_ORDER = (
    Rank.SEVEN, Rank.EIGHT, Rank.QUEEN, Rank.KING,
    Rank.TEN, Rank.ACE, Rank.NINE, Rank.JACK
)

# Strength lookup tables (bigger = stronger)
SUN_STRENGTH = {r: i for i, r in enumerate(SUN_ORDER)}
TRUMP_STRENGTH = {r: i for i, r in enumerate(HOKM_TRUMP_ORDER)}


def leading_suit(state: GameState) -> Suit | None:
    """Suit of the first card in the current trick, or None if trick empty."""
    if len(state.trick) == 0:
        return None
    return state.trick[0].suit


def trick_players(leader: int, n_cards: int) -> Tuple[int, ...]:
    """Players who have played so far in this trick, in order."""
    return tuple((leader + i) % 4 for i in range(n_cards))


def current_trick_winner(state: GameState) -> tuple[int, Card]:
    """
    Returns (winner_player_index, winning_card) among the cards currently in state.trick.
    Works for partial tricks too (1..4 cards), important for hokm.
    """
    if not state.trick:
        raise ValueError("No cards in trick")

    lead = state.trick[0].suit
    players = trick_players(state.leader, len(state.trick))

    def strength(card: Card) -> int:
        # Sun: only lead suit can win
        if state.trump is None:
            return SUN_STRENGTH[card.rank] if card.suit is lead else -1

        # Hokm:
        trump = state.trump
        if card.suit is trump:
            return 100 + TRUMP_STRENGTH[card.rank]  # any trump beats any non-trump
        if card.suit is lead:
            return SUN_STRENGTH[card.rank]
        return -1

    best_i = 0
    best_s = strength(state.trick[0])
    for i in range(1, len(state.trick)):
        s = strength(state.trick[i])
        if s > best_s:
            best_s = s
            best_i = i

    return players[best_i], state.trick[best_i]


def legal_moves(state: GameState) -> Tuple[Card, ...]:
    """
    Saudi Baloot legality (Hokm/Sun), based on your rules:

    Always:
    - If trick is empty: any card can be led.
    - Otherwise: must follow leading suit if you have it.

    Sun:
    - If void in leading suit: you may play anything.

    Hokm (trump exists):
    If void in leading suit:
    - If your partner is currently winning the trick: you may play anything (no need to trump).
    - Else if an opponent is currently winning WITH trump:
        - If you have a higher trump: you must overtrump (play a higher trump).
        - If you do NOT have a higher trump: you do not need to trump (may play anything).
    - Else (partner not winning, and no trump currently winning): you must play trump if you have any.

    Also: overtrumping is required whenever you are playing trump into a trick where a trump is already winning,
    but only if you have a higher trump available.

    Things to add (double, triple, etc betting)
    """
    hand = state.hands[state.to_play]  # "what cards does this player have"
    lead = leading_suit(state)

    # If trick is empty: any card can be led.
    if lead is None:
        return hand

    # Must follow leading suit if possible
    follow = tuple(c for c in hand if c.suit is lead)
    if follow:
        # Special case: if the lead suit is trump (Hokm), enforce overtrump if possible
        if state.trump is not None and lead is state.trump and len(state.trick) > 0:
            winner_player, winner_card = current_trick_winner(state)
            if winner_card.suit is state.trump:
                higher = tuple(
                    c for c in follow
                    if TRUMP_STRENGTH[c.rank] > TRUMP_STRENGTH[winner_card.rank]
                )
                return higher if higher else follow
        return follow

    # If void in lead suit:
    if state.trump is None:
        # Sun: may play anything
        return hand

    # Hokm: check trump rules
    trump = state.trump
    trumps_in_hand = tuple(c for c in hand if c.suit is trump)
    if not trumps_in_hand:
        return hand  # can't trump

    winner_player, winner_card = current_trick_winner(state)
    partner = (state.to_play + 2) % 4

    # If partner currently winning: no need to trump
    if winner_player == partner:
        return hand

    # If opponent currently winning with trump: overtrump if possible, else no need to trump
    if winner_card.suit is trump:
        higher_trumps = tuple(
            c for c in trumps_in_hand
            if TRUMP_STRENGTH[c.rank] > TRUMP_STRENGTH[winner_card.rank]
        )
        return higher_trumps if higher_trumps else hand

    # Otherwise: must play trump (any trump)
    return trumps_in_hand


def remove_card_from_hand(hand: Tuple[Card, ...], card: Card) -> Tuple[Card, ...]:
    """Remove one occurrence of card from a tuple-hand. (creates a new tuple, doesnt modify old)"""
    removed = False
    new_hand: List[Card] = []
    for c in hand:
        if not removed and c == card:
            removed = True
            continue
        new_hand.append(c)
    if not removed:
        raise ValueError("Tried to play a card not in hand")
    return tuple(new_hand)


def apply_move(state: GameState, card: Card) -> GameState:
    """
    Play a card and return the next GameState.

    New behavior:
    - When the 4th card is played (len(trick)==4), we resolve the trick:
      winner becomes next leader & to_play, trick clears, trick_number increments.
    (Scoring will be added later.)
    """
    if card not in legal_moves(state):
        raise ValueError("Illegal move")

    # update hands
    hands = list(state.hands)
    hands[state.to_play] = remove_card_from_hand(hands[state.to_play], card)

    # add to trick
    new_trick = state.trick + (card,)

    # advance turn (temporary; might be overridden if trick completes)
    next_player = (state.to_play + 1) % 4

    # If trick completes, resolve winner and reset trick
    if len(new_trick) == 4:
        temp_state = GameState(
            hands=tuple(hands),
            trump=state.trump,
            leader=state.leader,
            to_play=next_player,
            trick=new_trick,
            scores=state.scores,
            trick_number=state.trick_number,
        )
        winner, _ = current_trick_winner(temp_state)

        return GameState(
            hands=tuple(hands),
            trump=state.trump,
            leader=winner,
            to_play=winner,
            trick=tuple(),
            scores=state.scores,              # scoring later
            trick_number=state.trick_number + 1,
        )

    # Otherwise, trick still in progress
    return GameState(
        hands=tuple(hands),
        trump=state.trump,
        leader=state.leader,
        to_play=next_player,
        trick=new_trick,
        scores=state.scores,
        trick_number=state.trick_number,
    )


# for replay and savegame 

def apply_action(state: GameState, action: Action) -> GameState:
    """
    Apply a logged Action to the GameState.

    This function exists ONLY to support:
    - SaveGame replay
    - analyzer / solver stepping
    - bot-vs-bot simulations

    It is a thin wrapper that decodes the Action payload
    and forwards the move to the real game logic.
    """

    # optional but very useful sanity check during replay/logging
    if action.player != state.to_play:
        raise ValueError(
            f"Action player mismatch: action.player={action.player}, state.to_play={state.to_play}"
        )

    if action.type == "PLAY_CARD":
        # Decode card code (e.g. "QS") back into Card object
        card = code_to_card(action.payload["card"])

        # Delegate to existing rule logic
        return apply_move(state, card)

    raise ValueError(f"Unsupported action type: {action.type}")
