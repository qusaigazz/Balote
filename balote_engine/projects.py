from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional, Tuple

from .cards import Card, Rank, Suit


# -----------------------
# Project unit mapping
# (FINAL score units)
# -----------------------
# Sun: sira=4, 50=10, 100=20, 400=40
# Hokm: sira=2, 50=5, 100=10 (and 4 aces treated as 100)
_SUN_SEQ_UNITS = {3: 4, 4: 10, 5: 20}
_HOKM_SEQ_UNITS = {3: 2, 4: 5, 5: 10}

_SUN_FOUR_UNITS = {
    Rank.TEN: 20,
    Rank.JACK: 20,
    Rank.QUEEN: 20,
    Rank.KING: 20,
    Rank.ACE: 40,   # 4 aces = 400 -> 40 units in Sun
}

_HOKM_FOUR_UNITS = {
    Rank.TEN: 10,
    Rank.JACK: 10,
    Rank.QUEEN: 10,
    Rank.KING: 10,
    Rank.ACE: 10,   # 4 aces treated as 100 -> 10 units in Hokm
}

# Sequence rank order for projects (standard consecutive order)
_SEQ_ORDER: Tuple[Rank, ...] = (
    Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN,
    Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE
)
_SEQ_INDEX = {r: i for i, r in enumerate(_SEQ_ORDER)}

# For tie-break strength of four-of-kind
_FOUR_STRENGTH = {
    Rank.TEN: 0,
    Rank.JACK: 1,
    Rank.QUEEN: 2,
    Rank.KING: 3,
    Rank.ACE: 4,
}


@dataclass(frozen=True)
class Meld:
    """
    A single meld (project) that is fully contained within ONE player's hand.
    points_units: FINAL score units based on mode (SUN/HOKM)
    strength_key: used to compare melds of same points_units
    """
    kind: str                    # "SEQ" or "FOUR"
    points_units: int
    cards: FrozenSet[Card]
    strength_key: Tuple[int, ...]
    owner_player: int            # which player hand this meld belongs to

    def short(self) -> str:
        if self.kind == "SEQ":
            # highest rank index is strength_key[0]
            return f"SEQ({self.points_units})"
        return f"FOUR({self.points_units})"


# -----------------------
# Helpers
# -----------------------

def _seq_units(mode: str, length: int) -> int:
    if mode == "SUN":
        return _SUN_SEQ_UNITS[length]
    if mode == "HOKM":
        return _HOKM_SEQ_UNITS[length]
    raise ValueError(f"Invalid mode: {mode}")


def _four_units(mode: str, rank: Rank) -> int:
    if mode == "SUN":
        return _SUN_FOUR_UNITS.get(rank, 0)
    if mode == "HOKM":
        return _HOKM_FOUR_UNITS.get(rank, 0)
    raise ValueError(f"Invalid mode: {mode}")


def _authority_team(authority_player: int) -> int:
    # Team 0: players 0 & 2, Team 1: players 1 & 3
    return authority_player % 2


def _team_players(team: int) -> Tuple[int, int]:
    return (0, 2) if team == 0 else (1, 3)


# -----------------------
# Candidate generation (per HAND)
# -----------------------

def _all_sequence_melds_for_hand(hand: Tuple[Card, ...], owner_player: int, mode: str) -> List[Meld]:
    """
    Generate sequence meld candidates (length 3/4/5) fully inside ONE hand.
    Sequences are same-suit and consecutive in standard order 7-8-9-10-J-Q-K-A.
    """
    by_suit: dict[Suit, List[Card]] = {}
    for c in hand:
        by_suit.setdefault(c.suit, []).append(c)

    melds: List[Meld] = []

    for suit, cards in by_suit.items():
        # sort by sequence rank index
        cards_sorted = sorted(cards, key=lambda c: _SEQ_INDEX[c.rank])
        idxs = [_SEQ_INDEX[c.rank] for c in cards_sorted]

        # find consecutive runs in these indices
        start = 0
        while start < len(cards_sorted):
            end = start
            while end + 1 < len(cards_sorted) and idxs[end + 1] == idxs[end] + 1:
                end += 1

            run_cards = cards_sorted[start:end + 1]
            run_len = len(run_cards)

            # From a run, generate candidates of length 3/4/5.
            # We generate ALL windows so we don't miss disjoint possibilities.
            for L in (5, 4, 3):
                if run_len >= L:
                    for i in range(0, run_len - L + 1):
                        window = run_cards[i:i + L]
                        top_rank = window[-1].rank  # highest rank in the sequence
                        top_idx = _SEQ_INDEX[top_rank]

                        units = _seq_units(mode, L)
                        melds.append(
                            Meld(
                                kind="SEQ",
                                points_units=units,
                                cards=frozenset(window),
                                # strength: higher top_idx is stronger; also include length for stability
                                strength_key=(top_idx, L),
                                owner_player=owner_player,
                            )
                        )

            start = end + 1

    return melds


def _all_four_melds_for_hand(hand: Tuple[Card, ...], owner_player: int, mode: str) -> List[Meld]:
    """
    Generate four-of-a-kind meld candidates fully inside ONE hand.
    Only ranks: 10/J/Q/K/A are considered based on your rules.
    """
    by_rank: dict[Rank, List[Card]] = {}
    for c in hand:
        by_rank.setdefault(c.rank, []).append(c)

    melds: List[Meld] = []

    for rank, cards in by_rank.items():
        if len(cards) == 4 and rank in (Rank.TEN, Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE):
            units = _four_units(mode, rank)
            if units <= 0:
                continue
            melds.append(
                Meld(
                    kind="FOUR",
                    points_units=units,
                    cards=frozenset(cards),
                    strength_key=(_FOUR_STRENGTH[rank],),
                    owner_player=owner_player,
                )
            )

    return melds


def all_meld_candidates_for_hand(hand: Tuple[Card, ...], owner_player: int, mode: str) -> List[Meld]:
    return _all_sequence_melds_for_hand(hand, owner_player, mode) + _all_four_melds_for_hand(hand, owner_player, mode)


# -----------------------
# Best non-overlapping selection (per HAND)
# -----------------------

def best_meld_set_for_hand(hand: Tuple[Card, ...], owner_player: int, mode: str) -> Tuple[int, Tuple[Meld, ...]]:
    """
    Choose the best set of melds for ONE hand, with the constraint:
    - No card may appear in more than one counted meld (prevents overlap double-counting).

    Returns (total_units, chosen_melds).
    """
    candidates = all_meld_candidates_for_hand(hand, owner_player, mode)
    n = len(candidates)
    if n == 0:
        return 0, tuple()

    best_units = -1
    best_choice: Tuple[Meld, ...] = tuple()

    # brute force over subsets (n is small because a hand is only 8 cards)
    for mask in range(1 << n):
        used: set[Card] = set()
        total = 0
        chosen: List[Meld] = []
        ok = True

        for i in range(n):
            if (mask >> i) & 1:
                m = candidates[i]
                # overlap check
                if any(c in used for c in m.cards):
                    ok = False
                    break
                used.update(m.cards)
                total += m.points_units
                chosen.append(m)

        if not ok:
            continue

        # tie-break for "best" within a hand:
        # 1) higher total units
        # 2) higher sorted list of meld values (prefers big melds)
        # 3) higher sorted strength keys (stable deterministic)
        chosen_t = tuple(sorted(chosen, key=lambda m: (m.points_units, m.strength_key), reverse=True))
        value_profile = tuple(m.points_units for m in chosen_t)
        strength_profile = tuple(m.strength_key for m in chosen_t)

        if total > best_units:
            best_units = total
            best_choice = chosen_t
        elif total == best_units:
            best_value_profile = tuple(m.points_units for m in best_choice)
            if value_profile > best_value_profile:
                best_choice = chosen_t
            else:
                best_strength_profile = tuple(m.strength_key for m in best_choice)
                if value_profile == best_value_profile and strength_profile > best_strength_profile:
                    best_choice = chosen_t

    return best_units, best_choice


# -----------------------
# Team aggregation (two hands, but NEVER combine melds across hands)
# -----------------------

def compute_team_projects_from_hands(
    hands: Tuple[Tuple[Card, ...], ...],
    team: int,
    mode: str
) -> Tuple[int, Tuple[Meld, ...]]:
    """
    Compute team projects as the sum of best meld sets from the TWO individual hands on that team.
    Critical rule: melds must be fully present in ONE hand (no cross-hand meld).
    """
    p1, p2 = _team_players(team)

    units1, melds1 = best_meld_set_for_hand(hands[p1], owner_player=p1, mode=mode)
    units2, melds2 = best_meld_set_for_hand(hands[p2], owner_player=p2, mode=mode)

    return units1 + units2, melds1 + melds2


# -----------------------
# Comparing projects between teams
# -----------------------

def _top_meld(melds: Tuple[Meld, ...]) -> Optional[Meld]:
    if not melds:
        return None
    # top meld = max by (points_units, strength_key)
    return max(melds, key=lambda m: (m.points_units, m.strength_key))


def projects_winner(
    team0_melds: Tuple[Meld, ...],
    team1_melds: Tuple[Meld, ...],
    *,
    authority_player: int
) -> Optional[int]:
    """
    Decide which team wins the project settlement.

    Rules implemented:
    1) Compare by highest project (points_units)
    2) If tie, compare by strength (e.g., higher top sequence rank, higher four rank)
    3) If still tie, authority goes to earlier player (we approximate with authority_player)

    Returns: 0 or 1, or None (no projects for both teams).
    """
    t0_top = _top_meld(team0_melds)
    t1_top = _top_meld(team1_melds)

    if t0_top is None and t1_top is None:
        return None
    if t0_top is not None and t1_top is None:
        return 0
    if t1_top is not None and t0_top is None:
        return 1

    assert t0_top is not None and t1_top is not None

    k0 = (t0_top.points_units, t0_top.strength_key)
    k1 = (t1_top.points_units, t1_top.strength_key)

    if k0 > k1:
        return 0
    if k1 > k0:
        return 1

    # exact tie -> authority
    return _authority_team(authority_player)


def compute_projects_settlement(
    hands: Tuple[Tuple[Card, ...], ...],
    mode: str,
    *,
    authority_player: int
) -> Tuple[Optional[int], int, Tuple[Meld, ...]]:
    """
    Returns:
      (winner_team_or_None, winner_units, winner_melds)

    This does NOT check "must win a trick" eligibility.
    It only computes what projects exist and who wins them.
    """
    t0_units, t0_melds = compute_team_projects_from_hands(hands, team=0, mode=mode)
    t1_units, t1_melds = compute_team_projects_from_hands(hands, team=1, mode=mode)

    winner = projects_winner(t0_melds, t1_melds, authority_player=authority_player)
    if winner is None:
        return None, 0, tuple()

    if winner == 0:
        return 0, t0_units, t0_melds
    else:
        return 1, t1_units, t1_melds
