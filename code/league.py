import random
from sim.player_gen_with_superstars_bust import (
    gen_hitter,
    gen_pitcher,
    gen_hitting_coach,
    gen_pitching_coach,
    assign_salary_hitter,
    assign_salary_pitcher,
)
from team import generate_team

EAST_NAMES = ["Kings", "Sharks", "Falcons", "Wolves", "Heat", "Titans", "Storm", "Knights"]
WEST_NAMES = ["Comets", "Blaze", "Rangers", "Bears", "Aces", "Pilots", "Raiders", "Foxes"]

def generate_free_agents(num_hitters=40, num_pitchers=24):
    free_agent_hitters = [assign_salary_hitter(gen_hitter()) for _ in range(num_hitters)]
    free_agent_pitchers = [assign_salary_pitcher(gen_pitcher()) for _ in range(num_pitchers)]
    return free_agent_hitters, free_agent_pitchers

def generate_coach_markets(num_hitting=10, num_pitching=10):
    return [gen_hitting_coach() for _ in range(num_hitting)], [gen_pitching_coach() for _ in range(num_pitching)]

def generate_league(user_team_name):
    teams = []

    east_user = generate_team(user_team_name, division="East")
    teams.append(east_user)

    for name in EAST_NAMES:
        if name != user_team_name:
            teams.append(generate_team(name, division="East"))

    for name in WEST_NAMES:
        teams.append(generate_team(name, division="West"))

    return teams

def player_value(player):
    if hasattr(player, "ops"):
        return player.display_ops + player.display_obp + player.display_average
    return player.display_average_minus + player.display_obp_minus + player.display_slugging_minus

def cpu_generate_trade_offer(user_team, cpu_teams):
    candidates = []
    for cpu in cpu_teams:
        if not cpu.lineup or not user_team.bench:
            continue
        cpu_best = max(cpu.lineup, key=player_value)
        user_piece = random.choice(user_team.bench)
        diff = player_value(cpu_best) - player_value(user_piece)
        if -150 <= diff <= 250:
            candidates.append((cpu, cpu_best, user_piece))

    if not candidates:
        return None

    cpu, offered, requested = random.choice(candidates)
    return {
        "cpu_team": cpu,
        "offer_player": offered,
        "request_player": requested,
        "text": f"{cpu.name} offers {offered.name} for {requested.name}",
    }

def evaluate_trade_acceptance(cpu_team, cpu_player, incoming_player):
    return player_value(incoming_player) >= player_value(cpu_player) - 40

def compute_awards(teams):
    hitters = []
    pitchers = []
    for team in teams:
        hitters.extend(team.lineup + team.bench)
        pitchers.extend(team.rotation + team.bullpen)

    def avg(h):
        return h.hits / h.ab if h.ab > 0 else 0.0

    mvp = max(hitters, key=lambda h: (h.homeruns * 4 + h.rbi + h.hits + h.walks))
    batting = max(hitters, key=avg)
    cy = min(pitchers, key=lambda p: (p.era if p.outs_recorded > 0 else 99, -p.outs_recorded, p.walks))

    return {
        "mvp": mvp,
        "batting": batting,
        "cy": cy,
    }

def run_offseason(teams, free_agent_hitters, free_agent_pitchers, hitting_coach_market, pitching_coach_market):
    expired_hitters = []
    expired_pitchers = []
    expired_hitting_coaches = []
    expired_pitching_coaches = []

    for team in teams:
        expired = team.decrement_contracts(60)
        for obj in expired:
            team.remove_person(obj)
            if hasattr(obj, "ops"):
                expired_hitters.append(obj)
            elif hasattr(obj, "average_minus"):
                expired_pitchers.append(obj)
            elif hasattr(obj, "ops_boost"):
                expired_hitting_coaches.append(obj)
            else:
                expired_pitching_coaches.append(obj)

        team.reset_team_for_new_season()

    free_agent_hitters.extend(expired_hitters)
    free_agent_pitchers.extend(expired_pitchers)
    hitting_coach_market.extend(expired_hitting_coaches)
    pitching_coach_market.extend(expired_pitching_coaches)

    # CPU auto-bids on some FAs
    cpu_teams = teams[1:]
    rng = random.Random(99)

    for team in cpu_teams:
        # fill lineup/bench
        while len(team.lineup) < 9 and free_agent_hitters:
            best = max(free_agent_hitters, key=player_value)
            if team.can_afford(best.salary):
                free_agent_hitters.remove(best)
                best.contract_games_remaining = rng.randint(60, 180)
                best.contract_length = best.contract_games_remaining
                team.lineup.append(best)
            else:
                break

        while len(team.rotation) < 5 and free_agent_pitchers:
            best = max(free_agent_pitchers, key=player_value)
            if team.can_afford(best.salary):
                free_agent_pitchers.remove(best)
                best.contract_games_remaining = rng.randint(60, 180)
                best.contract_length = best.contract_games_remaining
                team.rotation.append(best)
            else:
                break

        while len(team.bullpen) < 7 and free_agent_pitchers:
            best = random.choice(free_agent_pitchers)
            if team.can_afford(best.salary):
                free_agent_pitchers.remove(best)
                best.contract_games_remaining = rng.randint(60, 180)
                best.contract_length = best.contract_games_remaining
                team.bullpen.append(best)
            else:
                break

        team.refresh_roles()

        def evaluate_user_trade_offer(cpu_team, cpu_player, user_player):
            cpu_gives = player_value(cpu_player)
            cpu_gets = player_value(user_player)

            # CPU accepts if it gets close value or better
            # Add a small random factor so trades are not perfectly predictable
            import random
            threshold = cpu_gives - random.randint(0, 35)

            return cpu_gets >= threshold