import random

from balote_engine.deck import make_deck, deal
from balote_engine.gamestate import GameState
from balote_engine.cards import Suit
from balote_engine.rules import legal_moves, apply_move
from balote_engine.terminal import is_terminal


def total_cards_in_game(state: GameState) -> int:
    """Total cards currently in hands + current trick."""
    return sum(len(hand) for hand in state.hands) + len(state.trick)


def main():
    rng = random.Random(0)  # fixed seed for reproducibility

    # 1) Build and deal the deck
    deck = make_deck()
    hands = deal(deck, rng=rng)

    # Sanity: correct deal
    assert len(hands) == 4
    assert all(len(hand) == 8 for hand in hands)
    assert sum(len(hand) for hand in hands) == 32

    # 2) Choose a contract (temporary)
    #trump = Suit.HEARTS      # Hokm example
    trump = None           # Uncomment for Sun

    # 3) Initial state
    state = GameState(
        hands=hands,
        trump=trump,
        leader=0,
        to_play=0,
        trick=tuple(),
        scores=(0, 0),        # scoring later
        trick_number=0,
    )

    # Sanity: total cards at start
    assert total_cards_in_game(state) == 32

    # 4) Play until terminal
    while not is_terminal(state):
        before_trick = state.trick_number
        before_total_cards = total_cards_in_game(state)

        moves = legal_moves(state)
        assert len(moves) > 0, "No legal moves available"

        card = rng.choice(moves)
        state = apply_move(state, card)

        # Sanity: exactly one card played
        'Although after a trick is played by a player, a card has been removed from their hand,'
        'but the card is still in-game (in the floor) so we check after every trick round that 4 cards '
        'have been removed '''

        after_total = total_cards_in_game(state)

        assert (
            after_total == before_total_cards or
            after_total == before_total_cards - 4
        ), f"Card count mismatch: before={before_total_cards}, after={after_total}"


        # If a trick just ended, check consistency
        if state.trick_number != before_trick:
            print(f"Trick {before_trick + 1} completed. Leader is now Player {state.leader}")

            # After trick resolution:
            assert len(state.trick) == 0, "Trick should be cleared after resolution"
            assert state.to_play == state.leader, "Leader must start next trick"

    # 5) Final sanity
    assert state.trick_number == 8
    assert total_cards_in_game(state) == 0

    print("Round finished successfully after 8 tricks.")


if __name__ == "__main__":
    main()
