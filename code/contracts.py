from dataclasses import dataclass
import random

from player_gen_with_superstars_bust import (
    MAX_CONTRACT_GAMES,
    MIN_CONTRACT_GAMES,
    hitter_performance_score,
    pitcher_performance_score,
    score_to_salary,
    MIN_SALARY,
    MAX_SALARY,
)


@dataclass
class NegotiationState:
    player: object
    games_offer: int = 30
    salary_offer: int = 1_000_000
    response: str = ""
    resolved: bool = False
    accepted: bool = False


@dataclass
class ContractEvent:
    kind: str
    player: object
    message: str


def player_value_score(player) -> float:
    if hasattr(player, "ops"):  # hitter
        return (
            getattr(player, "display_average", 250) +
            getattr(player, "display_obp", 320) +
            getattr(player, "display_ops", 730)
        )

    if hasattr(player, "average_minus"):  # pitcher
        return (
            getattr(player, "display_average_minus", 50) +
            getattr(player, "display_obp_minus", 50) +
            getattr(player, "display_slugging_minus", 50)
        )

    if hasattr(player, "ops_boost"):  # hitting coach
        return (
            getattr(player, "avg_boost", 0) +
            getattr(player, "obp_boost", 0) +
            getattr(player, "ops_boost", 0)
        )

    # pitching coach
    return (
        getattr(player, "avg_boost", 0) +
        getattr(player, "obp_boost", 0) +
        getattr(player, "slg_boost", 0)
    )


def expected_length_games(player) -> int:
    age = getattr(player, "age", 27)
    if age <= 25:
        return 100
    if age <= 29:
        return 80
    if age <= 33:
        return 65
    return 50


def loyalty_premium(player) -> float:
    team_time_games = getattr(player, "season_games", 0) + max(
        0,
        getattr(player, "contract_length", 0) - getattr(player, "contract_games_remaining", 0)
    )

    if team_time_games >= 240:
        return 1.20
    if team_time_games >= 160:
        return 1.12
    if team_time_games >= 80:
        return 1.06
    return 1.00


def hitter_contract_score(player) -> float:
    score = hitter_performance_score(player)

    # coaching bonuses
    score += getattr(player, "coach_avg_bonus", 0) * 1.0
    score += getattr(player, "coach_obp_bonus", 0) * 1.2
    score += getattr(player, "coach_ops_bonus", 0) * 0.8

    return score


def pitcher_contract_score(player) -> float:
    score = pitcher_performance_score(player)

    # coaching bonuses
    score += getattr(player, "coach_avg_bonus", 0) * 1.0
    score += getattr(player, "coach_obp_bonus", 0) * 1.0
    score += getattr(player, "coach_slg_bonus", 0) * 1.0

    # spin rate lab bonus
    score += getattr(player, "spin_rate_lab_bonus", 0) * 2.0

    return score


def expected_salary(player) -> int:
    old_salary = max(MIN_SALARY, int(getattr(player, "salary", MIN_SALARY)))
    minimum_raise_salary = int(old_salary * 1.20)

    if hasattr(player, "ops"):  # hitter
        score = hitter_contract_score(player)
        ask = score_to_salary(score)

        if getattr(player, "tier", "normal") == "superstar":
            ask = max(MIN_SALARY, int(ask * 1.25))
        elif getattr(player, "tier", "normal") == "bust":
            ask = max(MIN_SALARY, int(ask * 0.85))

    elif hasattr(player, "average_minus"):  # pitcher
        score = pitcher_contract_score(player)
        ask = score_to_salary(score)

        if getattr(player, "tier", "normal") == "superstar":
            ask = max(MIN_SALARY, int(ask * 1.25))
        elif getattr(player, "tier", "normal") == "bust":
            ask = max(MIN_SALARY, int(ask * 0.85))

    elif hasattr(player, "ops_boost"):  # hitting coach
        value = (
            getattr(player, "avg_boost", 0) +
            getattr(player, "obp_boost", 0) +
            getattr(player, "ops_boost", 0)
        )
        ask = 900_000 + value * 250_000

    else:  # pitching coach
        value = (
            getattr(player, "avg_boost", 0) +
            getattr(player, "obp_boost", 0) +
            getattr(player, "slg_boost", 0)
        )
        ask = 900_000 + value * 250_000

    games_with_team = max(
        0,
        getattr(player, "contract_length", 0) - getattr(player, "contract_games_remaining", 0)
    ) + getattr(player, "season_games", 0)

    if games_with_team >= 240:
        ask = int(ask * 1.20)
    elif games_with_team >= 160:
        ask = int(ask * 1.12)
    elif games_with_team >= 80:
        ask = int(ask * 1.06)

    # always at least 20% better than old contract
    ask = max(ask, minimum_raise_salary)

    return min(MAX_SALARY, max(MIN_SALARY, ask))


def expected_contract_value(player) -> float:
    ask_salary = expected_salary(player)
    ask_games = expected_length_games(player)
    return ask_salary / max(1, ask_games)


def offer_contract_value(salary_offer: int, games_offer: int) -> float:
    return salary_offer / max(1, games_offer)


def attempt_negotiation(player, salary_offer: int, games_offer: int):
    ask_games = expected_length_games(player)
    ask_value_per_game = expected_contract_value(player)
    offer_value_per_game = offer_contract_value(salary_offer, games_offer)

    value_ratio = offer_value_per_game / max(1e-9, ask_value_per_game)
    randomness = random.uniform(-0.08, 0.08)

    score = 1.00 * value_ratio + randomness
    accepted = score >= 1.0

    if accepted:
        player.salary = salary_offer
        player.contract_length = games_offer
        player.contract_games_remaining = games_offer
        msg = f"{player.name} accepted {games_offer}G / ${salary_offer:,.0f}."
    else:
        msg = f"{player.name} rejected {games_offer}G / ${salary_offer:,.0f}."
    return accepted, msg


def scan_contract_events(team):
    events = []
    for p in team.players_nearing_expiry(8):
        games = getattr(p, "contract_games_remaining", 0)
        events.append(ContractEvent("warning", p, f"{p.name} has {games} games left on his contract."))
    return events