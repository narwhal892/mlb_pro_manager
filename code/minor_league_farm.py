"""
Minor league farm system for MLB Pro Manager.

This module adds a named minor league affiliate and a farm director/coach.
The coach can improve scouting quality, player development speed, or loyalty.
"""
from dataclasses import dataclass, field
import random


@dataclass
class MinorLeagueCoach:
    name: str
    archetype: str
    scouting_boost: int = 0
    development_boost: int = 0
    loyalty_boost: int = 0
    salary: int = 1_000_000
    contract_length: int = 120
    contract_games_remaining: int = 120

    @property
    def character_name(self):
        return self.name

    def summary(self):
        return (
            f"{self.archetype} | Scout +{self.scouting_boost} "
            f"Dev +{self.development_boost} Loyalty +{self.loyalty_boost}"
        )


@dataclass
class MinorLeagueFarm:
    team_name: str = "Rookie Club"
    coach: object = None
    development_log: list = field(default_factory=list)
    discovered_players: list = field(default_factory=list)
    games_until_discovery: int = 8


def default_farm_name(parent_team_name):
    return f"{parent_team_name} Prospects"


def generate_farm_coach_market():
    return [
        MinorLeagueCoach("Ray Calderon", "Talent Hawk", scouting_boost=4, development_boost=1, loyalty_boost=1, salary=1_400_000),
        MinorLeagueCoach("Mack Sullivan", "Player Developer", scouting_boost=1, development_boost=4, loyalty_boost=1, salary=1_500_000),
        MinorLeagueCoach("Kenji Watanabe", "Clubhouse Mentor", scouting_boost=1, development_boost=1, loyalty_boost=4, salary=1_250_000),
        MinorLeagueCoach("Oscar Bennett", "Balanced Builder", scouting_boost=2, development_boost=2, loyalty_boost=2, salary=1_350_000),
        MinorLeagueCoach("Luis Navarro", "International Scout", scouting_boost=5, development_boost=0, loyalty_boost=1, salary=1_600_000),
        MinorLeagueCoach("Troy Walker", "Mechanics Guru", scouting_boost=0, development_boost=5, loyalty_boost=1, salary=1_700_000),
    ]


def ensure_farm_state(team):
    if not hasattr(team, "minor_league_farm") or team.minor_league_farm is None:
        team.minor_league_farm = MinorLeagueFarm(default_farm_name(team.name))
    if not hasattr(team, "farm_coach_market") or team.farm_coach_market is None:
        team.farm_coach_market = generate_farm_coach_market()
    if not hasattr(team.minor_league_farm, "development_log") or team.minor_league_farm.development_log is None:
        team.minor_league_farm.development_log = []
    if not hasattr(team.minor_league_farm, "discovered_players") or team.minor_league_farm.discovered_players is None:
        team.minor_league_farm.discovered_players = []
    return team.minor_league_farm


def farm_players(team):
    farm = []
    for p in getattr(team, "minors_hitters", []):
        if getattr(p, "name", "") != "EMPTY SLOT":
            farm.append(p)
    for p in getattr(team, "minors_pitchers", []):
        if getattr(p, "name", "") != "EMPTY SLOT":
            farm.append(p)
    return farm


def hire_farm_coach(team, market_index):
    ensure_farm_state(team)
    market = team.farm_coach_market
    if not (0 <= market_index < len(market)):
        return False, "Invalid farm coach."
    coach = market[market_index]
    current = team.minor_league_farm.coach
    outgoing = getattr(current, "salary", 0) if current else 0
    if hasattr(team, "can_afford") and not team.can_afford(coach.salary, outgoing_salary=outgoing):
        return False, "Cannot afford that farm coach."
    team.minor_league_farm.coach = coach
    if current:
        market[market_index] = current
    else:
        market.pop(market_index)
    if hasattr(team, "ensure_within_budget"):
        team.ensure_within_budget()
    return True, f"Hired {coach.name} to run {team.minor_league_farm.team_name}."


def rename_farm(team, new_name):
    farm = ensure_farm_state(team)
    cleaned = new_name.strip()
    if not cleaned:
        return False, "Farm team name cannot be empty."
    farm.team_name = cleaned[:28]
    return True, f"Minor league team renamed to {farm.team_name}."


def _boost_hitter(player, amount, coach=None):
    dev = getattr(coach, "development_boost", 0)

    if dev >= 4:
        choices = ["average", "obp", "slugging", "ops", "ops"]
    else:
        choices = ["average", "obp", "slugging", "ops"]

    choice = random.choice(choices)

    if choice == "average":
        player.coach_avg_bonus = getattr(player, "coach_avg_bonus", 0) + amount
    elif choice == "obp":
        player.coach_obp_bonus = getattr(player, "coach_obp_bonus", 0) + amount
    else:
        player.coach_ops_bonus = getattr(player, "coach_ops_bonus", 0) + amount

    return choice.upper(), amount


def _boost_pitcher(player, amount, coach=None):
    dev = getattr(coach, "development_boost", 0)

    if dev >= 4:
        choices = ["average_minus", "obp_minus", "slugging_minus", "average_minus"]
    else:
        choices = ["average_minus", "obp_minus", "slugging_minus"]

    choice = random.choice(choices)

    if choice == "average_minus":
        player.coach_avg_bonus = getattr(player, "coach_avg_bonus", 0) + amount
    elif choice == "obp_minus":
        player.coach_obp_bonus = getattr(player, "coach_obp_bonus", 0) + amount
    else:
        player.coach_slg_bonus = getattr(player, "coach_slg_bonus", 0) + amount

    label = {"average_minus": "AVG-", "obp_minus": "OBP-", "slugging_minus": "SLG-"}[choice]
    return label, amount


def advance_farm_system(team, games=1):
    """Call once after each game/day. Returns list of text events."""
    farm = ensure_farm_state(team)
    coach = farm.coach
    if coach is None:
        return []

    events = []
    dev_rate = max(1, 9 - int(getattr(coach, "development_boost", 0)))
    loyalty_gain = max(0, int(getattr(coach, "loyalty_boost", 0)))

    for player in farm_players(team):
        player.farm_progress_games = getattr(player, "farm_progress_games", 0) + games
        if loyalty_gain:
            player.minor_league_loyalty = getattr(player, "minor_league_loyalty", 0) + loyalty_gain
            if getattr(player, "contract_games_remaining", 0) > 0 and random.random() < min(0.05, loyalty_gain * 0.01):
                player.contract_games_remaining += 1
                player.contract_length += 1
        if player.farm_progress_games >= dev_rate:
            player.farm_progress_games = 0
            amount = 1 + (1 if getattr(coach, "development_boost", 0) >= 4 and random.random() < 0.35 else 0)
            if hasattr(player, "ops"):
                stat, amt = _boost_hitter(player, amount, coach)
            else:
                stat, amt = _boost_pitcher(player, amount, coach)
            msg = f"{player.name} improved {stat} +{amt} at {farm.team_name}."
            farm.development_log.insert(0, msg)
            events.append(msg)

    farm.games_until_discovery -= games
    if farm.games_until_discovery <= 0:
        scout = max(0, int(getattr(coach, "scouting_boost", 0)))
        farm.games_until_discovery = max(4, 12 - scout)
        if random.random() < min(0.85, 0.25 + scout * 0.10):
            msg = f"{coach.name} identified a promising minor league target."
            farm.discovered_players.insert(0, msg)
            farm.development_log.insert(0, msg)
            events.append(msg)

    farm.development_log = farm.development_log[:8]
    farm.discovered_players = farm.discovered_players[:8]
    return events
