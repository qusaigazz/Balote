from typing import Tuple, Optional


def _round_nc_points(nc_raw: int) -> int:
    """
    Apply NC rounding rule:
    - If last digit >= 5 → round UP to nearest 10
    - Else → round DOWN (truncate)
    """
    remainder = nc_raw % 10
    if remainder >= 5:
        return nc_raw + (10 - remainder)
    return nc_raw - remainder


def settle_round_cards(
    card_points: Tuple[int, int],
    contract_team: int,      # 0 or 1
    mode: str                # "SUN" or "HOKM"
) -> Tuple[int, int]:
    """
    Settle ONE round based on raw card points only (no projects).

    Returns final round score units for (team0, team1).
    """

    if mode not in ("SUN", "HOKM"):
        raise ValueError(f"Invalid mode: {mode}")

    # Identify teams
    ct = contract_team
    nc = 1 - ct

    ct_raw = card_points[ct]
    nc_raw = card_points[nc]

    # --- Special case: NC gets 0 ---
    if nc_raw == 0:
        if mode == "SUN":
            scores = [0, 0]
            scores[ct] = 44
            return tuple(scores)
        else:  # HOKM
            scores = [0, 0]
            scores[ct] = 25
            return tuple(scores)

    # --- Base settlement ---
    nc_rounded = _round_nc_points(nc_raw)
    nc_tens = nc_rounded // 10

    if mode == "SUN":
        nc_base = nc_tens * 2
        total = 26
    else:  # HOKM
        nc_base = nc_tens
        total = 16

    ct_base = total - nc_base

    # --- NC takes all ---
    if nc_raw > ct_raw:
        scores = [0, 0]
        scores[nc] = total
        return tuple(scores)

    # --- Hokm draw resolution (ONLY if base is 8|8) ---
    if mode == "HOKM" and nc_base == ct_base == 8:
        if nc_raw > ct_raw:
            scores = [0, 0]
            scores[nc] = total
            return tuple(scores)
        elif ct_raw > nc_raw:
            scores = [0, 0]
            scores[ct] = total
            return tuple(scores)
        # else: exact tie → keep 8|8

    # --- Normal case ---
    scores = [0, 0]
    scores[nc] = nc_base
    scores[ct] = ct_base
    return tuple(scores)



def finalize_with_projects(
    base_score: Tuple[int, int],
    *,
    mode: str,                    # "SUN" or "HOKM"
    contract_team: int,           # 0 or 1
    projects_winner_team: Optional[int],
    projects_units: int,
    trick_wins: Tuple[int, int],
) -> Tuple[int, int]:
    """
    Final round score after cards + projects + NC takeover rule.

    Rules:
    - Projects add after base_score.
    - Projects apply only if winner_team won >= 1 trick.
    - After projects, if NC score > CT score, NC takes ALL.
    - No raw-point draw resolution after projects.
    """
    total = 26 if mode == "SUN" else 16
    ct = contract_team
    nc = 1 - ct

    s0, s1 = base_score

    # Apply projects if eligible
    if (
        projects_winner_team is not None
        and projects_units > 0
        and trick_wins[projects_winner_team] > 0
    ):
        if projects_winner_team == 0:
            s0 += projects_units
        else:
            s1 += projects_units

    # Post-project NC takeover
    scores = [s0, s1]
    if scores[nc] > scores[ct]:
        out = [0, 0]
        out[nc] = total
        return tuple(out)

    return (s0, s1)
