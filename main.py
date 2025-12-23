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

from balote_engine.settlement import settle_round_cards, finalize_with_projects

from balote_engine.projects import compute_projects_settlement
from balote_engine.serialization import code_to_card




def total_cards_in_game(state: GameState) -> int:
    """Total cards currently in hands + current trick."""
    return sum(len(hand) for hand in state.hands) + len(state.trick)


def main():
    rng_seed = 0
    rng = random.Random(rng_seed)  # fixed seed for reproducibility

    SAVE_THIS_GAME = False
    SAVE_DIR = "games"

    match_score = [0, 0]
    round_no = 0

    while match_score[0] < 152 and match_score[1] < 152:
        round_no += 1
        print(f"\n================ ROUND {round_no} ================\n")

        # 1) Build and deal the deck
        deck = make_deck()
        hands = deal(deck, rng=rng)

        # Sanity: correct deal
        assert len(hands) == 4
        assert all(len(hand) == 8 for hand in hands)
        assert sum(len(hand) for hand in hands) == 32

        # 2) Choose a contract (temporary)
        trump = Suit.HEARTS      # Hokm example
        # trump = None           # Uncomment for Sun

        # 3) Initial state
        state = GameState(
            hands=hands,
            trump=trump,
            leader=0,
            to_play=0,
            trick=tuple(),
            scores=(0, 0),        # scoring later
            trick_number=0,
            card_points=(0, 0),
            trick_wins=(0, 0),
        )

        # Sanity: total cards at start
        assert total_cards_in_game(state) == 32

        # --- SaveGame: snapshot the starting world ONCE, before any player acts ---
        savegame = SaveGame(
            version=1,
            initial=state.to_initial_snapshot(
                dealer=0,                 # placeholder until bidding exists
                meta={"rng_seed": rng_seed, "round_no": round_no}
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

        # --- TEMP until bidding exists ---
        contract_team = 0  # TEMP placeholder

        round_score = settle_round_cards(
            card_points=state.card_points,
            contract_team=contract_team,
            mode="SUN" if state.trump is None else "HOKM",
        )

        print("=== ROUND FINAL SCORE (cards only) ===")
        print(f"Team 0: {round_score[0]}")
        print(f"Team 1: {round_score[1]}")
        print("=====================================")

        # sanity check for points
        if trump is None:
            assert sum(state.card_points) == 130, f"Expected 130, got {sum(state.card_points)}"
        else:
            assert sum(state.card_points) == 162, f"Expected 162, got {sum(state.card_points)}"

        print("Round finished successfully after 8 tricks.")

        # projects eligibility
        mode = "SUN" if state.trump is None else "HOKM"

        # Build hands (Cards) from the initial snapshot (since end-of-round hands are empty)
        p = savegame.initial.playing
        assert p is not None
        initial_hands = tuple(
            tuple(code_to_card(code) for code in p.hands_8[i])
            for i in range(4)
        )

        # Authority player for tie-breaks: use initial leader (for now)
        authority_player = p.leader

        winner_team, winner_units, winner_melds = compute_projects_settlement(
            initial_hands,
            mode,
            authority_player=authority_player,
        )

        print("=== PROJECTS (final units) ===")
        print(f"Winner team: {winner_team}")
        print(f"Winner units: {winner_units}")
        print(f"Meld count: {len(winner_melds)}")
        print("================================")

        if winner_team is not None and state.trick_wins[winner_team] > 0:
            print("Projects are eligible (winner won at least one trick).")
        else:
            print("Projects NOT eligible (winner did not win any trick or no winner).")

        # --------------------------------------------------
        # ROUND SETTLEMENT (cards + projects)
        # --------------------------------------------------

        base_score = settle_round_cards(
            card_points=state.card_points,
            contract_team=contract_team,
            mode=mode,
        )

        final_score = finalize_with_projects(
            base_score,
            mode=mode,
            contract_team=contract_team,
            projects_winner_team=winner_team,
            projects_units=winner_units,
            trick_wins=state.trick_wins,
        )

        print("\n===== DEBUG: ROUND SUMMARY =====")
        print("Mode:", "SUN" if state.trump is None else "HOKM")
        print("Contract team (CT):", contract_team)
        print("Non-contract team (NC):", 1 - contract_team)
        print("Raw card points:", state.card_points)
        print("Trick wins:", state.trick_wins)
        print("\n--- Cards-only settlement ---")
        print("Base round score:", base_score)
        print("\n--- Projects detection ---")
        print("Projects winner team:", winner_team)
        print("Project units:", winner_units)

        if winner_melds:
            print("Winning melds:")
            for m in winner_melds:
                print(
                    f"  Player {m.owner_player} | "
                    f"{m.kind} | units={m.points_units} | "
                    f"cards={[str(c) for c in m.cards]}"
                )
        else:
            print("No projects detected")

        print("\n--- Final round settlement ---")
        print("Final round score:", final_score)

        ct = contract_team
        nc = 1 - ct
        if final_score[nc] > 0 and final_score[ct] == 0:
            print("NC TAKEOVER occurred ✅")

        print("===== END DEBUG =====\n")

        # --- UPDATE MATCH SCORE ---
        match_score[0] += final_score[0]
        match_score[1] += final_score[1]
        print(f"=== MATCH SCORE after round {round_no}: {match_score[0]} | {match_score[1]} ===")

        # --- SaveGame: write to disk (optional) ---
        if SAVE_THIS_GAME:
            os.makedirs(SAVE_DIR, exist_ok=True)

            mode_name = "SUN" if trump is None else f"HOKM_{trump.value}"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{stamp}_{mode_name}_seed{rng_seed}_round{round_no}.json"

            path = os.path.join(SAVE_DIR, filename)

            with open(path, "w", encoding="utf-8") as f:
                f.write(savegame.to_json())

            print(f"Saved game to: {path}")

        # --- Replay verification: load JSON -> replay -> assert final matches live ---
        loaded = SaveGame.from_json(savegame.to_json())
        replayed_final = replay(loaded)

        assert replayed_final == state, "Replay mismatch: final state differs from live run"
        print("Replay verified: final state matches live run ✅")

    print("\n================ MATCH OVER ================")
    print(f"FINAL MATCH SCORE: {match_score[0]} | {match_score[1]}")



if __name__ == "__main__":
    main()
