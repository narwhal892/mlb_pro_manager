import random

BASE_BUDGET = 165_000_000
MIN_BUDGET = 120_000_000

HOT_HITTER_BONUS = 12
COLD_HITTER_PENALTY = 12
HOT_PITCHER_BONUS = 8
COLD_PITCHER_PENALTY = 8


def ensure_franchise_culture_state(team):
    if not hasattr(team, "ticket_price_level") or team.ticket_price_level is None:
        team.ticket_price_level = 5
    if not hasattr(team, "vendor_price_level") or team.vendor_price_level is None:
        team.vendor_price_level = 5
    if not hasattr(team, "morale") or team.morale is None:
        team.morale = 500
    if not hasattr(team, "active_hot_streaks") or team.active_hot_streaks is None:
        team.active_hot_streaks = []
    if not hasattr(team, "active_cold_streaks") or team.active_cold_streaks is None:
        team.active_cold_streaks = []


def franchise_revenue_bonus(team):
    ensure_franchise_culture_state(team)
    ticket_bonus = (team.ticket_price_level - 5) * 1_400_000
    vendor_bonus = (team.vendor_price_level - 5) * 700_000
    return max(-8_000_000, ticket_bonus + vendor_bonus)


def refresh_budget_from_culture(team, base_budget=BASE_BUDGET):
    ensure_franchise_culture_state(team)
    team.budget = max(MIN_BUDGET, base_budget + franchise_revenue_bonus(team))
    return team.budget


def recalc_morale(team):
    ensure_franchise_culture_state(team)

    # Higher prices hurt morale
    price_penalty = (team.ticket_price_level - 5) * 55 + (team.vendor_price_level - 5) * 30

    # Winning helps morale
    win_bonus = (getattr(team, "wins", 0) - getattr(team, "losses", 0)) * 3

    team.morale = max(0, min(1000, 500 + win_bonus - price_penalty))
    return team.morale


def culture_profile(team):
    """
    Returns a descriptive lean, not a locked-in identity.
    """
    ensure_franchise_culture_state(team)
    morale = recalc_morale(team)
    revenue = franchise_revenue_bonus(team)

    if revenue >= 5_000_000 and morale <= 430:
        return "Superstar Lean"
    if morale >= 620 and revenue <= 2_000_000:
        return "Chemistry Lean"
    return "Balanced"


def player_streak_state(team, player):
    name = getattr(player, "name", "")
    for entry in getattr(team, "active_hot_streaks", []):
        if entry.get("name") == name:
            return "HOT", entry.get("games_left", 0)
    for entry in getattr(team, "active_cold_streaks", []):
        if entry.get("name") == name:
            return "COLD", entry.get("games_left", 0)
    return "", 0


def clear_expired_streaks(team):
    ensure_franchise_culture_state(team)
    team.active_hot_streaks = [s for s in team.active_hot_streaks if s.get("games_left", 0) > 0]
    team.active_cold_streaks = [s for s in team.active_cold_streaks if s.get("games_left", 0) > 0]


def decrement_streaks(team, games=1):
    ensure_franchise_culture_state(team)
    for bucket in (team.active_hot_streaks, team.active_cold_streaks):
        for streak in bucket:
            streak["games_left"] = max(0, int(streak.get("games_left", 0)) - games)
    clear_expired_streaks(team)


def active_roster_players(team):
    players = []
    for group_name in ["lineup", "bench", "rotation", "bullpen"]:
        for p in getattr(team, group_name, []):
            if p and not team.is_empty_slot(p):
                players.append(p)
    return players


def apply_random_morale_streaks(team):
    ensure_franchise_culture_state(team)
    clear_expired_streaks(team)
    morale = recalc_morale(team)

    priority_players = []
    priority_players.extend([p for p in getattr(team, "lineup", []) if not team.is_empty_slot(p)])
    priority_players.extend([p for p in getattr(team, "rotation", [])[:5] if not team.is_empty_slot(p)])
    priority_players.extend([p for p in getattr(team, "bullpen", [])[:3] if not team.is_empty_slot(p)])

    # dedupe by name and remove injured players
    seen = set()
    players = []
    for p in priority_players:
        if getattr(p, "injured_games_remaining", 0) > 0:
            continue
        if p.name in seen:
            continue
        seen.add(p.name)
        players.append(p)

    if not players:
        return None

    hot_chance = 0.0
    cold_chance = 0.0

    if morale >= 650:
        hot_chance = 0.28
    elif morale >= 580:
        hot_chance = 0.16

    if morale <= 430:
        cold_chance = 0.7
    elif morale <= 600:
        cold_chance = 0.7

    created = None

    if hot_chance > 0 and random.random() < hot_chance:
        eligible = [p for p in players if player_streak_state(team, p)[0] == ""]
        if eligible:
            chosen = random.sample(eligible, min(3, len(eligible)))
            for p in chosen:
                team.active_hot_streaks.append({
                    "name": p.name,
                    "games_left": random.randint(3, 6),
                })
            created = ("hot", [p.name for p in chosen])

    if cold_chance > 0 and random.random() < cold_chance:
        eligible = [p for p in players if player_streak_state(team, p)[0] == ""]
        if eligible:
            chosen = random.sample(eligible, min(3, len(eligible)))
            for p in chosen:
                team.active_cold_streaks.append({
                    "name": p.name,
                    "games_left": random.randint(3, 6),
                })
            created = ("cold", [p.name for p in chosen])

    return created


def sync_team_streak_display(team):
    ensure_franchise_culture_state(team)

    for player in active_roster_players(team):
        if hasattr(player, "hot_streak_bonus"):
            player.hot_streak_bonus = 0
        if hasattr(player, "cold_streak_penalty"):
            player.cold_streak_penalty = 0

        state, _ = player_streak_state(team, player)

        if state == "HOT":
            if hasattr(player, "ops"):
                player.hot_streak_bonus = HOT_HITTER_BONUS
            else:
                player.hot_streak_bonus = HOT_PITCHER_BONUS

        elif state == "COLD":
            if hasattr(player, "ops"):
                player.cold_streak_penalty = COLD_HITTER_PENALTY
            else:
                player.cold_streak_penalty = COLD_PITCHER_PENALTY


def player_streak_tag(player):
    if getattr(player, "hot_streak_bonus", 0) > 0:
        return " HOT"
    if getattr(player, "cold_streak_penalty", 0) > 0:
        return " COLD"
    return ""