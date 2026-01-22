import os
import random
from datetime import datetime, timezone

from balote_engine.deck import make_deck
from balote_engine.gamestate import GameState
from balote_engine.cards import Suit
from balote_engine.rules import legal_moves, apply_move
from balote_engine.terminal import is_terminal

from balote_engine.savegame import (
    SaveGame, Action,
    InitialSnapshot, BiddingInitial
)
from balote_engine.serialization import card_to_code

from balote_engine.replay import replay, build_initial_state

from balote_engine.settlement import settle_round_cards, finalize_with_projects
from balote_engine.projects import compute_projects_settlement
from balote_engine.serialization import code_to_card

from balote_engine.bidding import resolve_bidding_to_playing_initial


def total_cards_in_game(state: GameState) -> int:
    """Total cards currently in hands + current trick."""
    return sum(len(hand) for hand in state.hands) + len(state.trick)


def team_of_player(p: int) -> int:
    return p % 2


def partner_of(p: int) -> int:
    return (p + 2) % 4


def right_of_dealer(dealer: int) -> int:
    # by your indexing: if dealer=0, player 1 bids first/leads first
    return (dealer + 1) % 4


def left_of_dealer(dealer: int) -> int:
    return (dealer + 3) % 4


def authority_order(dealer: int) -> list[int]:
    start = right_of_dealer(dealer)
    return [(start + i) % 4 for i in range(4)]


def can_ashkal(player: int, dealer: int) -> bool:
    return player == dealer or player == left_of_dealer(dealer)


def deal_bidding_snapshot(deck_cards, dealer: int):
    """
    Deterministic split:
    - hands_5: 5 cards each (20)
    - floor_card: 1 card (21st)
    - stock: remaining 11 cards
    """
    hands_5 = {
        i: tuple(deck_cards[i * 5:(i + 1) * 5])
        for i in range(4)
    }
    floor_card = deck_cards[20]
    stock = tuple(deck_cards[21:])

    hands_5_codes = {i: tuple(card_to_code(c) for c in hands_5[i]) for i in range(4)}
    floor_code = card_to_code(floor_card)
    stock_codes = tuple(card_to_code(c) for c in stock)

    return hands_5_codes, floor_code, stock_codes


def choose_random_bid_action(rng: random.Random, player: int, dealer: int, *, allow_hokm: bool, allow_hokm_thani: bool):
    """
    Random bidder:
    returns one of: "PASS", "BID_SUN", "BID_ASHKAL", "BID_HOKM", "BID_HOKM_THANI"
    (but constrained by round options + ashkal eligibility)
    """
    options = ["PASS", "BID_SUN"]
    if can_ashkal(player, dealer):
        options.append("BID_ASHKAL")
    if allow_hokm:
        options.append("BID_HOKM")
    if allow_hokm_thani:
        options.append("BID_HOKM_THANI")
    return rng.choice(options)


def pick_random_trump_thani(rng: random.Random, floor_suit_code: str) -> str:
    suits = ["S", "H", "D", "C"]
    suits.remove(floor_suit_code)
    return rng.choice(suits)


def resolve_sun_ladder(
    savegame: SaveGame,
    rng: random.Random,
    dealer: int,
    initial_holder: int,
    initial_bid_kind: str,  # "SUN" or "ASHKAL"
) -> tuple[SaveGame, int, str]:
    """
    Resolve SUN/ASHKAL by the ladder rule:

    - Only higher-authority OPPONENTS can challenge.
    - Stepwise upward (immediate higher first, then next, ...).
    - Teammates are skipped automatically.
    - Challenger can PASS or take SUN (or ASHKAL if eligible).

    Returns: (savegame, final_holder, final_bid_kind)
    """
    order = authority_order(dealer)  # high -> low
    holder = initial_holder
    bid_kind = initial_bid_kind  # "SUN" or "ASHKAL"

    while True:
        holder_team = team_of_player(holder)
        holder_idx = order.index(holder)

        # higher authority players above holder, closest first
        higher = order[:holder_idx]              # high -> (just above holder)
        challengers = list(reversed(higher))     # immediate higher first

        took = False

        for ch in challengers:
            # Only opponents can challenge (teammates skipped)
            if team_of_player(ch) == holder_team:
                continue

            options = ["PASS", "BID_SUN"]
            if can_ashkal(ch, dealer):
                options.append("BID_ASHKAL")
            choice = rng.choice(options)

            if choice == "PASS":
                savegame = savegame.append(Action(player=ch, type="PASS", payload={}))
                continue

            # challenger takes it -> holder changes, restart ladder from new holder
            savegame = savegame.append(Action(player=ch, type=choice, payload={}))
            holder = ch
            bid_kind = "ASHKAL" if choice == "BID_ASHKAL" else "SUN"
            took = True
            break

        if not took:
            # no eligible opponent above holder took it -> done
            return savegame, holder, bid_kind


def simulate_random_bidding(savegame: SaveGame, rng: random.Random) -> tuple[SaveGame, dict]:
    """
    Simulate bidding according to your rules, randomly.

    Returns:
      (updated_savegame, contract_info_dict)

    contract_info_dict keys:
      mode: "SUN"|"HOKM"
      trump_suit: str|None
      winning_bidder: int
      floor_taker: int
      bid_kind: "SUN"|"ASHKAL"|"HOKM"|"HOKM_THANI"
    """
    init = savegame.initial
    b = init.bidding
    assert b is not None

    dealer = b.dealer
    order = authority_order(dealer)
    floor_suit_code = b.floor_card[1]

    # --------------------------
    # ROUND 1: SUN / HOKM / PASS (+ ASHKAL)
    # --------------------------
    hokm_bidder = None

    for p in order:
        action_type = choose_random_bid_action(
            rng, p, dealer,
            allow_hokm=True,
            allow_hokm_thani=False,
        )

        if action_type == "PASS":
            savegame = savegame.append(Action(player=p, type="PASS", payload={}))
            continue

        if action_type in ("BID_SUN", "BID_ASHKAL"):
            savegame = savegame.append(Action(player=p, type=action_type, payload={}))
            start_kind = "ASHKAL" if action_type == "BID_ASHKAL" else "SUN"

            savegame, winning_bidder, bid_kind = resolve_sun_ladder(
                savegame, rng, dealer, initial_holder=p, initial_bid_kind=start_kind
            )

            finalize_payload = {
                "mode": "SUN",
                "trump_suit": None,
                "winning_bidder": winning_bidder,
                "floor_taker": partner_of(winning_bidder) if bid_kind == "ASHKAL" else winning_bidder,
                "bid_kind": bid_kind,
            }
            savegame = savegame.append(
                Action(player=winning_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
            )
            return savegame, finalize_payload

        if action_type == "BID_HOKM":
            savegame = savegame.append(Action(player=p, type="BID_HOKM", payload={}))
            hokm_bidder = p
            break

    if hokm_bidder is not None:
        # SUN override window (authority order)
        for p in order:
            options = ["PASS", "BID_SUN"]
            if can_ashkal(p, dealer):
                options.append("BID_ASHKAL")
            choice = rng.choice(options)

            if choice == "PASS":
                savegame = savegame.append(Action(player=p, type="PASS", payload={}))
                continue

            savegame = savegame.append(Action(player=p, type=choice, payload={}))
            start_kind = "ASHKAL" if choice == "BID_ASHKAL" else "SUN"

            savegame, winning_bidder, bid_kind = resolve_sun_ladder(
                savegame, rng, dealer, initial_holder=p, initial_bid_kind=start_kind
            )

            finalize_payload = {
                "mode": "SUN",
                "trump_suit": None,
                "winning_bidder": winning_bidder,
                "floor_taker": partner_of(winning_bidder) if bid_kind == "ASHKAL" else winning_bidder,
                "bid_kind": bid_kind,
            }
            savegame = savegame.append(
                Action(player=winning_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
            )
            return savegame, finalize_payload

        # No SUN override: special round-1 switch rule
        if hokm_bidder == right_of_dealer(dealer) and rng.choice([False, True]):
            if can_ashkal(hokm_bidder, dealer) and rng.choice([False, True]):
                bid_kind = "ASHKAL"
                savegame = savegame.append(Action(player=hokm_bidder, type="BID_ASHKAL", payload={}))
                floor_taker = partner_of(hokm_bidder)
            else:
                bid_kind = "SUN"
                savegame = savegame.append(Action(player=hokm_bidder, type="BID_SUN", payload={}))
                floor_taker = hokm_bidder

            finalize_payload = {
                "mode": "SUN",
                "trump_suit": None,
                "winning_bidder": hokm_bidder,
                "floor_taker": floor_taker,
                "bid_kind": bid_kind,
            }
            savegame = savegame.append(
                Action(player=hokm_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
            )
            return savegame, finalize_payload

        # Finalize HOKM
        finalize_payload = {
            "mode": "HOKM",
            "trump_suit": floor_suit_code,
            "winning_bidder": hokm_bidder,
            "floor_taker": hokm_bidder,
            "bid_kind": "HOKM",
        }
        savegame = savegame.append(
            Action(player=hokm_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
        )
        return savegame, finalize_payload

    # --------------------------
    # ROUND 2: SUN / HOKM_THANI / PASS (+ ASHKAL)
    # --------------------------
    hokm_thani_bidder = None

    for p in order:
        action_type = choose_random_bid_action(
            rng, p, dealer,
            allow_hokm=False,
            allow_hokm_thani=True,
        )

        if action_type == "PASS":
            savegame = savegame.append(Action(player=p, type="PASS", payload={}))
            continue

        if action_type in ("BID_SUN", "BID_ASHKAL"):
            savegame = savegame.append(Action(player=p, type=action_type, payload={}))
            start_kind = "ASHKAL" if action_type == "BID_ASHKAL" else "SUN"

            savegame, winning_bidder, bid_kind = resolve_sun_ladder(
                savegame, rng, dealer, initial_holder=p, initial_bid_kind=start_kind
            )

            finalize_payload = {
                "mode": "SUN",
                "trump_suit": None,
                "winning_bidder": winning_bidder,
                "floor_taker": partner_of(winning_bidder) if bid_kind == "ASHKAL" else winning_bidder,
                "bid_kind": bid_kind,
            }
            savegame = savegame.append(
                Action(player=winning_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
            )
            return savegame, finalize_payload

        if action_type == "BID_HOKM_THANI":
            savegame = savegame.append(Action(player=p, type="BID_HOKM_THANI", payload={}))
            hokm_thani_bidder = p
            break

    if hokm_thani_bidder is not None:
        # SUN override window (authority order)
        for p in order:
            options = ["PASS", "BID_SUN"]
            if can_ashkal(p, dealer):
                options.append("BID_ASHKAL")
            choice = rng.choice(options)

            if choice == "PASS":
                savegame = savegame.append(Action(player=p, type="PASS", payload={}))
                continue

            savegame = savegame.append(Action(player=p, type=choice, payload={}))
            start_kind = "ASHKAL" if choice == "BID_ASHKAL" else "SUN"

            savegame, winning_bidder, bid_kind = resolve_sun_ladder(
                savegame, rng, dealer, initial_holder=p, initial_bid_kind=start_kind
            )

            finalize_payload = {
                "mode": "SUN",
                "trump_suit": None,
                "winning_bidder": winning_bidder,
                "floor_taker": partner_of(winning_bidder) if bid_kind == "ASHKAL" else winning_bidder,
                "bid_kind": bid_kind,
            }
            savegame = savegame.append(
                Action(player=winning_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
            )
            return savegame, finalize_payload

        # No SUN override: bidder chooses SUN or HOKM_THANI trump
        if rng.choice([False, True]):
            if can_ashkal(hokm_thani_bidder, dealer) and rng.choice([False, True]):
                bid_kind = "ASHKAL"
                savegame = savegame.append(Action(player=hokm_thani_bidder, type="BID_ASHKAL", payload={}))
                floor_taker = partner_of(hokm_thani_bidder)
            else:
                bid_kind = "SUN"
                savegame = savegame.append(Action(player=hokm_thani_bidder, type="BID_SUN", payload={}))
                floor_taker = hokm_thani_bidder

            finalize_payload = {
                "mode": "SUN",
                "trump_suit": None,
                "winning_bidder": hokm_thani_bidder,
                "floor_taker": floor_taker,
                "bid_kind": bid_kind,
            }
            savegame = savegame.append(
                Action(player=hokm_thani_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
            )
            return savegame, finalize_payload

        chosen_trump = pick_random_trump_thani(rng, floor_suit_code)
        finalize_payload = {
            "mode": "HOKM",
            "trump_suit": chosen_trump,
            "winning_bidder": hokm_thani_bidder,
            "floor_taker": hokm_thani_bidder,
            "bid_kind": "HOKM_THANI",
        }
        savegame = savegame.append(
            Action(player=hokm_thani_bidder, type="FINALIZE_CONTRACT", payload=finalize_payload)
        )
        return savegame, finalize_payload

    # Nobody bought in round 1 or 2 -> redeal
    return savegame, {"REDEAL": True}


def format_contract_line(contract_info: dict) -> str:
    if contract_info.get("REDEAL"):
        return "Contract: REDEAL"
    mode = contract_info["mode"]
    bid_kind = contract_info["bid_kind"]
    trump = contract_info["trump_suit"]
    winner = contract_info["winning_bidder"]
    floor_taker = contract_info["floor_taker"]
    return (
        f"Contract: {mode} ({bid_kind}) | "
        f"Winner=P{winner} | Floor->P{floor_taker} | Trump={trump} | Mult=x1"
    )


def print_round_report(
    round_no: int,
    dealer: int,
    floor_code: str,
    contract_info: dict,
    state: GameState,
    trick_winners: list[int],
    base_score,
    final_score,
    winner_team,
    winner_units,
    winner_melds,
    match_score,
):
    order = authority_order(dealer)

    print(f"\n=== ROUND {round_no} ===")
    print("Teams:")
    print("T0: P0 & P2, T1: P1 & P3")
    print(f"Dealer=P{dealer} | Authority={order} | Leader(trick1)=P{right_of_dealer(dealer)} | Floor={floor_code}")
    print(format_contract_line(contract_info))

    # Trick summary (derived in main loop)
    print(f"Tricks: winners={trick_winners} | Team tricks: T0={state.trick_wins[0]} T1={state.trick_wins[1]}")

    total = sum(state.card_points)
    print(f"Card points: T0={state.card_points[0]} T1={state.card_points[1]} (total={total})")
    print(f"Cards-only settle: {base_score[0]} | {base_score[1]}")

    if winner_team is None:
        print("Projects: none")
    else:
        eligible = (state.trick_wins[winner_team] > 0)
        if eligible:
            print(f"Projects: winner=T{winner_team} | units={winner_units} | melds={len(winner_melds)}")
        else:
            print(f"Projects: winner=T{winner_team} | units={winner_units} but INELIGIBLE (no tricks)")

    print(f"Final settle: {final_score[0]} | {final_score[1]}")
    print(f"Match score (before add): {match_score[0]} | {match_score[1]}")


def main():
    rng_seed = 0
    rng = random.Random(rng_seed)  # fixed seed for reproducibility

    SAVE_THIS_GAME = True
    SAVE_DIR = "games"

    # Output toggles (keeps main.py clean by default)
    PRINT_TRICK_PROGRESS = False       # "Trick X completed..." lines
    PRINT_BIDDING_DEBUG = False        # your current === BIDDING RESULT === block
    PRINT_DEBUG_SUMMARY = False        # your big DEBUG: ROUND SUMMARY block
    PRINT_MELDS_DETAILS = False        # meld card-by-card listing

    match_score = [0, 0]
    round_no = 0

    dealer = 0  # we now track dealer (needed for bidding)

    while match_score[0] < 152 and match_score[1] < 152:
        round_no += 1

        # ---------------------------------------------------------
        # BIDDING LOOP: may redeal if nobody buys after 2 rounds
        # ---------------------------------------------------------
        while True:
            # 1) Build and shuffle deck deterministically
            deck = list(make_deck())
            rng.shuffle(deck)

            # 2) Create bidding snapshot: hands_5 + floor + stock
            hands_5_codes, floor_code, stock_codes = deal_bidding_snapshot(deck, dealer)

            bidding_init = BiddingInitial(
                dealer=dealer,
                current_player=right_of_dealer(dealer),
                hands_5=hands_5_codes,
                floor_card=floor_code,
                stock=stock_codes,
            )

            savegame = SaveGame(
                version=1,
                initial=InitialSnapshot(
                    version=1,
                    start_phase="BIDDING",
                    bidding=bidding_init,
                    meta={"rng_seed": rng_seed, "round_no": round_no, "dealer": dealer},
                ),
            )

            # 3) Simulate random bidding (for now)
            savegame, contract_info = simulate_random_bidding(savegame, rng)

            # 4) Handle redeal if nobody bought
            if contract_info.get("REDEAL"):
                print(f"\n=== ROUND {round_no} ===")
                print(f"Dealer=P{dealer} | Authority={authority_order(dealer)} | Floor={floor_code}")
                print("No one bought in Round 1 or 2. Redealing...")
                dealer = right_of_dealer(dealer)  # dealer becomes player on the right of dealer
                continue

            # Contract finalized ✅
            break

        # Resolve to PlayingInitial (for things outside GameState, like projects/hands snapshot)
        b = savegame.initial.bidding
        assert b is not None
        playing_initial = resolve_bidding_to_playing_initial(b, savegame.actions)

        # Build initial GameState from SaveGame (works for BIDDING or PLAYING)
        state = build_initial_state(savegame)

        # Sanity: total cards at start
        assert total_cards_in_game(state) == 32

        # Contract info (used later for settlement)
        winning_bidder = int(contract_info["winning_bidder"])
        contract_team = team_of_player(winning_bidder)

        if PRINT_BIDDING_DEBUG:
            # Keep these prints for debugging / confidence
            print("=== BIDDING RESULT ===")
            print("Dealer:", dealer)
            print("Leader (trick 1):", state.leader)
            print("Winning bidder:", winning_bidder)
            print("Contract team:", contract_team)
            print("Mode:", contract_info["mode"])
            print("Trump suit:", contract_info["trump_suit"])
            print("Floor taker:", contract_info["floor_taker"])
            print("Bid kind:", contract_info["bid_kind"])
            print("======================")

        # 4) Play until terminal
        trick_winners: list[int] = []

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

            # If a trick just ended, record winner and optionally print progress
            if state.trick_number != before_trick:
                # After resolution, state.leader is the winner of the trick that ended
                trick_winners.append(state.leader)

                if PRINT_TRICK_PROGRESS:
                    print(f"Trick {before_trick + 1} completed. Winner/Next leader is Player {state.leader}")

                # After trick resolution:
                assert len(state.trick) == 0, "Trick should be cleared after resolution"
                assert state.to_play == state.leader, "Leader must start next trick"

        # 5) Final sanity
        assert state.trick_number == 8
        assert total_cards_in_game(state) == 0
        assert len(trick_winners) == 8

        mode = "SUN" if state.trump is None else "HOKM"

        # Base cards-only settlement
        base_score = settle_round_cards(
            card_points=state.card_points,
            contract_team=contract_team,
            mode=mode,
        )

        # sanity check for points
        if state.trump is None:
            assert sum(state.card_points) == 130, f"Expected 130, got {sum(state.card_points)}"
        else:
            assert sum(state.card_points) == 162, f"Expected 162, got {sum(state.card_points)}"

        # projects eligibility
        # Build hands (Cards) from the PLAYING snapshot we derived (since end-of-round hands are empty)
        initial_hands = tuple(
            tuple(code_to_card(code) for code in playing_initial.hands_8[i])
            for i in range(4)
        )

        # Authority player for tie-breaks: use initial leader (right of dealer)
        authority_player = playing_initial.leader

        winner_team, winner_units, winner_melds = compute_projects_settlement(
            initial_hands,
            mode,
            authority_player=authority_player,
            trump=state.trump,   # None in SUN, Suit in HOKM
        )

        # Final settlement (cards + projects)
        final_score = finalize_with_projects(
            base_score,
            mode=mode,
            contract_team=contract_team,
            projects_winner_team=winner_team,
            projects_units=winner_units,
            trick_wins=state.trick_wins,
            winner_melds=winner_melds, 
        )

        # ---- Clean, minimal round report (always) ----
        print_round_report(
            round_no=round_no,
            dealer=dealer,
            floor_code=floor_code,
            contract_info=contract_info,
            state=state,
            trick_winners=trick_winners,
            base_score=base_score,
            final_score=final_score,
            winner_team=winner_team,
            winner_units=winner_units,
            winner_melds=winner_melds,
            match_score=match_score,
        )

        # ---- Optional detailed debug (your existing block, gated) ----
        if PRINT_DEBUG_SUMMARY:
            print("\n===== DEBUG: ROUND SUMMARY =====")
            print("Mode:", mode)
            print("Contract team (CT):", contract_team)
            print("Non-contract team (NC):", 1 - contract_team)
            print("Raw card points:", state.card_points)
            print("Trick wins:", state.trick_wins)
            print("Trick winners:", trick_winners)

            print("\n--- Cards-only settlement ---")
            print("Base round score:", base_score)

            print("\n--- Projects detection ---")
            print("Projects winner team:", winner_team)
            print("Project units:", winner_units)

            if PRINT_MELDS_DETAILS:
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
        print(f"Match score (after add): {match_score[0]} | {match_score[1]}")

        # --- SaveGame: write to disk (optional) ---
        if SAVE_THIS_GAME:
            os.makedirs(SAVE_DIR, exist_ok=True)

            mode_name = "SUN" if state.trump is None else f"HOKM_{state.trump.value}"
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
        print("Replay verified ✅")

        # next round dealer rotates normally
        dealer = right_of_dealer(dealer)

    print("\n================ MATCH OVER ================")
    print(f"FINAL MATCH SCORE: {match_score[0]} | {match_score[1]} ===")


if __name__ == "__main__":
    main()
