import random
from typing import List

from player_gen_with_superstars_bust import (
    MAX_CONTRACT_GAMES,
    assign_salary_hitter,
    assign_salary_pitcher,
    gen_hitter,
    gen_hitting_coach,
    gen_pitcher,
    gen_pitching_coach,
)
from team import REQUIRED_LINEUP_POSITIONS, TARGET_BULLPEN_SIZE, generate_team

DIVISIONS = {
    "North": ["Kings", "Sharks", "Falcons", "Wolves"],
    "South": ["Heat", "Titans", "Storm", "Knights"],
    "West": ["Comets", "Blaze", "Rangers", "Bears"],
    "Pacific": ["Aces", "Pilots", "Raiders", "Foxes"],
}

CPU_BUDGET_TARGET_BUFFER = 1_500_000
CPU_BUDGET_MIN_RATIO = 0.97


def generate_free_agents(num_hitters=120, num_pitchers=500):
    free_agent_hitters = [assign_salary_hitter(gen_hitter()) for _ in range(num_hitters)]
    free_agent_pitchers = [assign_salary_pitcher(gen_pitcher()) for _ in range(num_pitchers)]
    for player in free_agent_hitters + free_agent_pitchers:
        player.contract_length = MAX_CONTRACT_GAMES
        player.contract_games_remaining = MAX_CONTRACT_GAMES
    return free_agent_hitters, free_agent_pitchers


def generate_coach_markets(num_hitting=16, num_pitching=16):
    hitting = [gen_hitting_coach() for _ in range(num_hitting)]
    pitching = [gen_pitching_coach() for _ in range(num_pitching)]
    for coach in hitting + pitching:
        if getattr(coach, "contract_length", 0) <= 0:
            coach.contract_length = 180
        coach.contract_games_remaining = 0
    return hitting, pitching


def _cpu_active_hitters(team):
    return [p for p in (team.lineup + team.bench) if getattr(p, "name", "") != "EMPTY SLOT"]


def _cpu_active_pitchers(team):
    return [p for p in (team.rotation + team.bullpen) if getattr(p, "name", "") != "EMPTY SLOT"]


def _current_lineup_positions(team):
    return {getattr(p, "position", None) for p in team.lineup if getattr(p, "name", "") != "EMPTY SLOT"}


def _budget_gap(team):
    return max(0, team.budget - team.total_salary())


def _budget_close_enough(team):
    return team.total_salary() >= int(team.budget * CPU_BUDGET_MIN_RATIO) or _budget_gap(team) <= CPU_BUDGET_TARGET_BUFFER


def _affordable_candidates(candidates, team, outgoing_salary=0):
    return [p for p in candidates if team.can_afford(getattr(p, "salary", 0), outgoing_salary=outgoing_salary)]


def _best_fit_player(candidates, team, outgoing_salary=0, salary_floor=0, salary_ceiling=None):
    fits = []
    for player in candidates:
        salary = getattr(player, "salary", 0)
        if salary < salary_floor:
            continue
        if salary_ceiling is not None and salary > salary_ceiling:
            continue
        if team.can_afford(salary, outgoing_salary=outgoing_salary):
            fits.append(player)
    if not fits:
        return None
    gap_after = lambda p: abs(team.budget - team.projected_salary_after_add(getattr(p, "salary", 0), outgoing_salary))
    return max(fits, key=lambda p: (player_value(p), -gap_after(p), getattr(p, "salary", 0)))


def _upgrade_cpu_hitter_slot(team, slot_collection_name, slot_index, free_agent_hitters):
    collection = getattr(team, slot_collection_name)
    current = collection[slot_index]
    current_salary = getattr(current, "salary", 0)
    current_value = player_value(current)
    remaining_gap = _budget_gap(team)
    min_raise = max(0, min(remaining_gap, 1_000_000))
    best = None
    for candidate in free_agent_hitters:
        if slot_collection_name == "lineup":
            required_pos = REQUIRED_LINEUP_POSITIONS[slot_index]
            if required_pos not in team.eligible_lineup_positions_for(candidate):
                continue
        salary = getattr(candidate, "salary", 0)
        if salary <= current_salary:
            continue
        if salary - current_salary < min_raise and remaining_gap > CPU_BUDGET_TARGET_BUFFER:
            continue
        if not team.can_afford(salary, outgoing_salary=current_salary):
            continue
        if player_value(candidate) <= current_value:
            continue
        gap_after = abs(team.budget - team.projected_salary_after_add(salary, current_salary))
        rank = (player_value(candidate) - current_value, -gap_after, salary)
        if best is None or rank > best[0]:
            best = (rank, candidate)
    if best is None:
        return False
    candidate = best[1]
    free_agent_hitters.remove(candidate)
    free_agent_hitters.append(current)
    if slot_collection_name == "lineup":
        candidate.position = REQUIRED_LINEUP_POSITIONS[slot_index]
    collection[slot_index] = candidate
    return True


def _upgrade_cpu_pitcher_slot(team, slot_collection_name, slot_index, free_agent_pitchers):
    collection = getattr(team, slot_collection_name)
    current = collection[slot_index]
    current_salary = getattr(current, "salary", 0)
    current_value = player_value(current)
    remaining_gap = _budget_gap(team)
    min_raise = max(0, min(remaining_gap, 1_000_000))
    desired_role = "SP" if slot_collection_name == "rotation" else getattr(current, "role", "RP")
    best = None
    for candidate in free_agent_pitchers:
        salary = getattr(candidate, "salary", 0)
        if salary <= current_salary:
            continue
        if salary - current_salary < min_raise and remaining_gap > CPU_BUDGET_TARGET_BUFFER:
            continue
        if not team.can_afford(salary, outgoing_salary=current_salary):
            continue
        if player_value(candidate) <= current_value:
            continue
        if slot_collection_name == "rotation" and getattr(candidate, "role", None) not in {"SP", "RP", "CL"}:
            continue
        if slot_collection_name == "bullpen" and desired_role == "CL" and getattr(candidate, "role", None) == "SP":
            continue
        gap_after = abs(team.budget - team.projected_salary_after_add(salary, current_salary))
        role_bonus = 1 if getattr(candidate, "role", None) == desired_role else 0
        rank = (player_value(candidate) - current_value, role_bonus, -gap_after, salary)
        if best is None or rank > best[0]:
            best = (rank, candidate)
    if best is None:
        return False
    candidate = best[1]
    free_agent_pitchers.remove(candidate)
    free_agent_pitchers.append(current)
    if slot_collection_name == "rotation":
        candidate.role = "SP"
    collection[slot_index] = candidate
    return True


def push_cpu_team_toward_budget(team, free_agent_hitters, free_agent_pitchers):
    if getattr(team, "budget", 0) <= 0:
        return

    team.repair_roster_structure()
    team.refresh_roles()

    improved = True
    safety = 0
    while improved and not _budget_close_enough(team) and safety < 200:
        safety += 1
        improved = False

        hitter_slots = []
        for idx, player in enumerate(team.lineup):
            if getattr(player, "name", "") != "EMPTY SLOT":
                hitter_slots.append(("lineup", idx, player))
        for idx, player in enumerate(team.bench):
            if getattr(player, "name", "") != "EMPTY SLOT":
                hitter_slots.append(("bench", idx, player))
        hitter_slots.sort(key=lambda item: (player_value(item[2]), getattr(item[2], "salary", 0)))

        for slot_collection_name, idx, _player in hitter_slots:
            if _upgrade_cpu_hitter_slot(team, slot_collection_name, idx, free_agent_hitters):
                improved = True
                break

        if improved:
            continue

        pitcher_slots = []
        for idx, player in enumerate(team.rotation):
            if getattr(player, "name", "") != "EMPTY SLOT":
                pitcher_slots.append(("rotation", idx, player))
        for idx, player in enumerate(team.bullpen):
            if getattr(player, "name", "") != "EMPTY SLOT":
                pitcher_slots.append(("bullpen", idx, player))
        pitcher_slots.sort(key=lambda item: (player_value(item[2]), getattr(item[2], "salary", 0)))

        for slot_collection_name, idx, _player in pitcher_slots:
            if _upgrade_cpu_pitcher_slot(team, slot_collection_name, idx, free_agent_pitchers):
                improved = True
                break

    team.repair_roster_structure()
    team.refresh_roles()


def generate_league(user_team_name):
    teams = []
    placed_user = False
    seed_hitters, seed_pitchers = generate_free_agents(280, 260)
    for division, names in DIVISIONS.items():
        for name in names:
            if not placed_user:
                user_team = generate_team(user_team_name, division=division)
                user_team.budget = 165_000_000
                teams.append(user_team)
                placed_user = True
                if name == user_team_name:
                    continue
            if name != user_team_name:
                cpu_team = generate_team(name, division=division)
                cpu_team.budget = 200_000_000
                push_cpu_team_toward_budget(cpu_team, seed_hitters, seed_pitchers)
                teams.append(cpu_team)
    return teams


def player_value(player):
    if player is None or getattr(player, "name", "") == "EMPTY SLOT" or getattr(player, "salary", None) == 0:
        return -999999
    if hasattr(player, "ops"):
        return player.display_ops + player.display_obp + player.display_average + (20 if getattr(player, "position", None) in {"C", "SS", "CF"} else 0)
    return player.display_average_minus + player.display_obp_minus + player.display_slugging_minus + getattr(player, "stamina", 0) // 2


def cpu_generate_trade_offer(user_team, cpu_teams):
    candidates = []
    for cpu in cpu_teams:
        user_trade_pool = [p for p in (user_team.bench + user_team.bullpen) if player_value(p) > -999999]
        cpu_trade_pool = [p for p in (cpu.lineup + cpu.rotation[:2]) if player_value(p) > -999999]
        if not cpu_trade_pool or not user_trade_pool:
            continue
        cpu_best = max(cpu_trade_pool, key=player_value)
        user_piece = random.choice(user_trade_pool)
        diff = player_value(cpu_best) - player_value(user_piece)
        if -80 <= diff <= 220:
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
    return player_value(incoming_player) >= player_value(cpu_player) - random.randint(20, 50)


def evaluate_user_trade_offer(cpu_team, cpu_player, user_player):
    threshold = player_value(cpu_player) - random.randint(0, 35)
    return player_value(user_player) >= threshold


def compute_awards(teams):
    hitters = []
    pitchers = []
    for team in teams:
        for p in (team.lineup + team.bench):
            if hasattr(p, "ops"):
                setattr(p, "team_name", team.name)
                hitters.append(p)
        for p in (team.rotation + team.bullpen):
            if hasattr(p, "average_minus"):
                setattr(p, "team_name", team.name)
                pitchers.append(p)
    if not hitters or not pitchers:
        return {"mvp": None, "batting": None, "cy": None}

    def avg(h):
        return h.hits / h.ab if h.ab > 0 else 0.0

    mvp = max(hitters, key=lambda h: (h.homeruns * 4 + h.rbi + h.hits + h.walks))
    batting = max(hitters, key=avg)
    eligible_pitchers = [p for p in pitchers if (getattr(p, "outs_recorded", 0) / 3.0) >= 22]
    cy_pool = eligible_pitchers or pitchers
    cy = min(cy_pool, key=lambda p: (p.era if p.outs_recorded > 0 else 99, -p.outs_recorded, p.walks))
    return {"mvp": mvp, "batting": batting, "cy": cy}


def fill_cpu_rosters_from_market(team, free_agent_hitters, free_agent_pitchers):
    current_positions = _current_lineup_positions(team)
    needed_positions = [pos for pos in REQUIRED_LINEUP_POSITIONS if pos not in current_positions]
    while needed_positions and free_agent_hitters:
        pos = needed_positions.pop(0)
        match = _best_fit_player(
            [p for p in free_agent_hitters if getattr(p, "position", None) == pos],
            team,
        )
        if match is None:
            eligible = [p for p in free_agent_hitters if pos in team.eligible_lineup_positions_for(p)]
            match = _best_fit_player(eligible, team)
        if match is None:
            affordable = _affordable_candidates(free_agent_hitters, team)
            match = max(affordable, key=player_value) if affordable else None
        if match is None:
            break
        free_agent_hitters.remove(match)
        match.position = pos
        team.lineup.append(match)
        current_positions.add(pos)

    while len(_cpu_active_hitters(team)) < len(REQUIRED_LINEUP_POSITIONS) + 7 and free_agent_hitters:
        affordable = _affordable_candidates(free_agent_hitters, team)
        if not affordable:
            break
        pick = _best_fit_player(affordable, team)
        free_agent_hitters.remove(pick)
        team.bench.append(pick)

    while len(team.real_rotation()) < 5 and free_agent_pitchers:
        starters = [p for p in free_agent_pitchers if getattr(p, "role", None) == "SP"]
        pick = _best_fit_player(starters or free_agent_pitchers, team)
        if pick is None:
            break
        free_agent_pitchers.remove(pick)
        pick.role = "SP"
        empty_idx = next((i for i, p in enumerate(team.rotation) if team.is_empty_slot(p)), None)
        if empty_idx is not None:
            team.rotation[empty_idx] = pick
        else:
            team.rotation.append(pick)

    while len(team.real_bullpen()) < TARGET_BULLPEN_SIZE and free_agent_pitchers:
        relievers = [p for p in free_agent_pitchers if getattr(p, "role", None) != "SP"]
        pick = _best_fit_player(relievers or free_agent_pitchers, team)
        if pick is None:
            break
        free_agent_pitchers.remove(pick)
        pick.role = "RP" if getattr(pick, "role", None) == "SP" else getattr(pick, "role", "RP")
        empty_idx = next((i for i, p in enumerate(team.bullpen) if team.is_empty_slot(p)), None)
        if empty_idx is not None:
            team.bullpen[empty_idx] = pick
        else:
            team.bullpen.append(pick)

    while len(team.real_rotation()) < 5:
        filler = assign_salary_pitcher(gen_pitcher("SP"))
        filler.contract_length = MAX_CONTRACT_GAMES
        filler.contract_games_remaining = MAX_CONTRACT_GAMES
        filler.role = "SP"
        empty_idx = next((i for i, p in enumerate(team.rotation) if team.is_empty_slot(p)), None)
        if empty_idx is not None:
            team.rotation[empty_idx] = filler
        else:
            team.rotation.append(filler)

    while len(team.real_bullpen()) < TARGET_BULLPEN_SIZE:
        filler_role = "CL" if len(team.real_bullpen()) == TARGET_BULLPEN_SIZE - 1 else "RP"
        filler = assign_salary_pitcher(gen_pitcher(filler_role))
        filler.contract_length = MAX_CONTRACT_GAMES
        filler.contract_games_remaining = MAX_CONTRACT_GAMES
        filler.role = filler_role
        empty_idx = next((i for i, p in enumerate(team.bullpen) if team.is_empty_slot(p)), None)
        if empty_idx is not None:
            team.bullpen[empty_idx] = filler
        else:
            team.bullpen.append(filler)

    team.repair_roster_structure()
    team.refresh_roles()
    team.ensure_batting_order()


def run_offseason(teams, free_agent_hitters, free_agent_pitchers, hitting_coach_market, pitching_coach_market):
    expired_hitters = []
    expired_pitchers = []
    expired_hitting_coaches = []
    expired_pitching_coaches = []
    for idx, team in enumerate(teams):
        if idx == 0:
            team.reset_team_for_new_season()
            continue
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
    for team in teams[1:]:
        fill_cpu_rosters_from_market(team, free_agent_hitters, free_agent_pitchers)
        if hitting_coach_market and random.random() < 0.45 and len(team.hitting_coaches) < 2:
            coach = hitting_coach_market.pop(0)
            if team.can_afford(coach.salary):
                team.hitting_coaches.append(coach)
        if pitching_coach_market and random.random() < 0.45 and team.pitching_coach is None:
            coach = pitching_coach_market.pop(0)
            if team.can_afford(coach.salary):
                team.pitching_coach = coach
        push_cpu_team_toward_budget(team, free_agent_hitters, free_agent_pitchers)
        team.repair_roster_structure()
        team.refresh_roles()
        team.ensure_batting_order()
