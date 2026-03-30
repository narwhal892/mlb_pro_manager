import random
from dataclasses import dataclass, field

from franchise_culture import (
    ensure_franchise_culture_state,
    franchise_revenue_bonus,
    refresh_budget_from_culture,
    recalc_morale,
    apply_random_morale_streaks,
    decrement_streaks,
    sync_team_streak_display,
    HOT_HITTER_BONUS,
    COLD_HITTER_PENALTY,
    HOT_PITCHER_BONUS,
    COLD_PITCHER_PENALTY,
)

# -----------------------------
# Minimal fake player/team setup
# -----------------------------

@dataclass
class FakeHitter:
    name: str
    ops: int = 700
    injured_games_remaining: int = 0
    hot_streak_bonus: int = 0
    cold_streak_penalty: int = 0


@dataclass
class FakePitcher:
    name: str
    average_minus: int = 50
    injured_games_remaining: int = 0
    hot_streak_bonus: int = 0
    cold_streak_penalty: int = 0


@dataclass
class FakeTeam:
    ticket_price_level: int = 5
    vendor_price_level: int = 5
    wins: int = 0
    losses: int = 0
    morale: int = 500
    budget: int = 165_000_000
    active_hot_streaks: list = field(default_factory=list)
    active_cold_streaks: list = field(default_factory=list)
    lineup: list = field(default_factory=list)
    bench: list = field(default_factory=list)
    rotation: list = field(default_factory=list)
    bullpen: list = field(default_factory=list)

    def is_empty_slot(self, obj):
        return False


def make_test_team(ticket_level: int, vendor_level: int, wins: int, losses: int) -> FakeTeam:
    team = FakeTeam(
        ticket_price_level=ticket_level,
        vendor_price_level=vendor_level,
        wins=wins,
        losses=losses,
    )

    # 9 hitters + 4 bench + 5 rotation + 3 bullpen
    team.lineup = [FakeHitter(f"Hitter{i+1}") for i in range(9)]
    team.bench = [FakeHitter(f"Bench{i+1}") for i in range(4)]
    team.rotation = [FakePitcher(f"Starter{i+1}") for i in range(5)]
    team.bullpen = [FakePitcher(f"Reliever{i+1}") for i in range(3)]

    ensure_franchise_culture_state(team)
    recalc_morale(team)
    refresh_budget_from_culture(team)
    sync_team_streak_display(team)
    return team


# -----------------------------
# Helpers
# -----------------------------

def streak_chances_from_morale(morale: int):
    hot_chance = 0.0
    cold_chance = 0.0

    if morale >= 650:
        hot_chance = 0.28
    elif morale >= 580:
        hot_chance = 0.16

    if morale <= 350:
        cold_chance = 0.30
    elif morale <= 430:
        cold_chance = 0.16

    return hot_chance, cold_chance


def simulate_until_first_streak(ticket_level: int, vendor_level: int, wins: int, losses: int, max_games: int = 200):
    team = make_test_team(ticket_level, vendor_level, wins, losses)

    first_hot_game = None
    first_cold_game = None

    for game_no in range(1, max_games + 1):
        created = apply_random_morale_streaks(team)
        sync_team_streak_display(team)

        if created:
            streak_type, _names = created
            if streak_type == "hot" and first_hot_game is None:
                first_hot_game = game_no
            elif streak_type == "cold" and first_cold_game is None:
                first_cold_game = game_no

        decrement_streaks(team, 1)

        if first_hot_game is not None and first_cold_game is not None:
            break

    return first_hot_game, first_cold_game


def average_games_to_streak(ticket_level: int, vendor_level: int, wins: int, losses: int, trials: int = 1000):
    hot_results = []
    cold_results = []

    for _ in range(trials):
        first_hot, first_cold = simulate_until_first_streak(ticket_level, vendor_level, wins, losses)

        if first_hot is not None:
            hot_results.append(first_hot)
        if first_cold is not None:
            cold_results.append(first_cold)

    avg_hot = sum(hot_results) / len(hot_results) if hot_results else None
    avg_cold = sum(cold_results) / len(cold_results) if cold_results else None

    return {
        "avg_hot_games": avg_hot,
        "avg_cold_games": avg_cold,
        "hot_seen_rate": len(hot_results) / trials,
        "cold_seen_rate": len(cold_results) / trials,
    }


# -----------------------------
# Main program
# -----------------------------

def main():
    print("=== Franchise Culture Streak Test ===")
    print("Enter levels from 1 to 10.\n")

    try:
        ticket_level = int(input("Ticket price level (1-10): ").strip())
        vendor_level = int(input("Vendor price level (1-10): ").strip())
        wins_raw = input("Wins (default 0): ").strip()
        losses_raw = input("Losses (default 0): ").strip()
        trials_raw = input("Simulation trials (default 1000): ").strip()

        wins = int(wins_raw) if wins_raw else 0
        losses = int(losses_raw) if losses_raw else 0
        trials = int(trials_raw) if trials_raw else 1000

    except ValueError:
        print("Invalid input. Please enter whole numbers only.")
        return

    if not (1 <= ticket_level <= 10 and 1 <= vendor_level <= 10):
        print("Ticket and vendor levels must both be between 1 and 10.")
        return

    team = make_test_team(ticket_level, vendor_level, wins, losses)
    morale = team.morale
    budget = team.budget
    revenue_bonus = franchise_revenue_bonus(team)
    hot_chance, cold_chance = streak_chances_from_morale(morale)

    stats = average_games_to_streak(ticket_level, vendor_level, wins, losses, trials=trials)

    print("\n=== Results ===")
    print(f"Ticket price level: {ticket_level}")
    print(f"Vendor price level: {vendor_level}")
    print(f"Record used for morale: {wins}-{losses}")
    print(f"Morale: {morale}")
    print(f"Revenue bonus: ${revenue_bonus:,.0f}")
    print(f"Budget: ${budget:,.0f}")

    print("\n=== Streak trigger chances per game ===")
    print(f"Hot streak chance:  {hot_chance * 100:.1f}%")
    print(f"Cold streak chance: {cold_chance * 100:.1f}%")

    print("\n=== Average games until first streak ===")
    if stats["avg_hot_games"] is None:
        print("Hot streak: never triggered in these trials")
    else:
        print(f"Hot streak:  {stats['avg_hot_games']:.2f} games on average")
        print(f"Hot streak seen in {stats['hot_seen_rate'] * 100:.1f}% of trials")

    if stats["avg_cold_games"] is None:
        print("Cold streak: never triggered in these trials")
    else:
        print(f"Cold streak: {stats['avg_cold_games']:.2f} games on average")
        print(f"Cold streak seen in {stats['cold_seen_rate'] * 100:.1f}% of trials")

    print("\n=== Streak impact on players ===")
    print(f"Hot hitter bonus:     +{HOT_HITTER_BONUS}")
    print(f"Cold hitter penalty:  -{COLD_HITTER_PENALTY}")
    print(f"Hot pitcher bonus:    +{HOT_PITCHER_BONUS}")
    print(f"Cold pitcher penalty: -{COLD_PITCHER_PENALTY}")

    print("\nNote:")
    print("This estimates how long it takes for the FIRST streak to appear,")
    print("not how long a full season takes to become hot/cold overall.")


if __name__ == "__main__":
    main()