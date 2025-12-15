import os
import random
from datetime import datetime

from balote_engine.deck import make_deck, deal
from balote_engine.gamestate import GameState
from balote_engine.cards import Suit
from balote_engine.rules import legal_moves, apply_move
from balote_engine.terminal import is_terminal

from balote_engine.savegame import SaveGame, Action
from balote_engine.serialization import card_to_code

from datetime import datetime, timezone
from balote_engine.savegame import SaveGame
from balote_engine.replay import replay



def total_cards_in_game(state: GameState) -> int:
    """Total cards currently in hands + current trick."""
    return sum(len(hand) for hand in state.hands) + len(state.trick)


def main():
    rng_seed = 0
    rng = random.Random(rng_seed)  # fixed seed for reproducibility

    SAVE_THIS_GAME = True
    SAVE_DIR = "games"

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

    # --- SaveGame: snapshot the starting world ONCE, before any player acts ---
    savegame = SaveGame(
        version=1,
        initial=state.to_initial_snapshot(
            dealer=0,                 # placeholder until bidding exists
            meta={"rng_seed": rng_seed}
        ),
    )

    # 4) Play until terminal
    while not is_terminal(state):
        before_trick = state.trick_number
        before_total_cards = total_cards_in_game(state)

        moves = legal_moves(state)
        assert len(moves) > 0, "No legal moves available"

        card = rng.choice(moves)

        # SaveGame logging needs the actor (player) BEFORE apply_move changes to_play
        actor = state.to_play

        # --- SaveGame: log the move as an Action (event log) ---
        savegame = savegame.append(Action(
            player=actor,
            type="PLAY_CARD",
            payload={"card": card_to_code(card)},
        ))

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

    # --- SaveGame: write to disk (optional) ---
    if SAVE_THIS_GAME:
        os.makedirs(SAVE_DIR, exist_ok=True)

        # filename helps you identify contract + seed quickly
        mode = "SUN" if trump is None else f"HOKM_{trump.value}"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{stamp}_{mode}_seed{rng_seed}.json"

        path = os.path.join(SAVE_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            f.write(savegame.to_json())

        print(f"Saved game to: {path}")

    # --- Replay verification: load JSON -> replay -> assert final matches live ---
    loaded = SaveGame.from_json(savegame.to_json())
    replayed_final = replay(loaded)

    assert replayed_final == state, "Replay mismatch: final state differs from live run"
    print("Replay verified: final state matches live run ✅")


if __name__ == "__main__":
    main()
