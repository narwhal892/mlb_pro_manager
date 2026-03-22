import copy
import random
import pygame

from settings import WIDTH, HEIGHT, FPS
from team import generate_team
from league import (
    generate_free_agents,
    generate_coach_markets,
    generate_league,
    cpu_generate_trade_offer,
    evaluate_trade_acceptance,
    evaluate_user_trade_offer,
    compute_awards,
    run_offseason,
    player_value,
)
from sim.game_sim import simulate_half_inning
from sim.player_gen_with_superstars_bust import SEASON_GAMES

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MLB Pro Manager")
clock = pygame.time.Clock()

TITLE_FONT = pygame.font.SysFont("courier", 34, bold=True)
HEADER_FONT = pygame.font.SysFont("courier", 24, bold=True)
BODY_FONT = pygame.font.SysFont("courier", 16, bold=True)
SMALL_FONT = pygame.font.SysFont("courier", 14, bold=True)

# --------------------------------------------------
# helpers
# --------------------------------------------------

def get_player_name(player):
    return getattr(player, "character_name", getattr(player, "name", "Unknown"))

def fmt_stat(v):
    return f".{int(v):03d}"

def fmt_money(n):
    return "${:,.0f}".format(n)

def fmt_money_short(n):
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"${n/1_000:.0f}K"
    return f"${n}"

def short_name(name, n=12):
    return name[:n]

def clamp_index(value, size):
    if size <= 0:
        return 0
    return max(0, min(value, size - 1))

def team_total_salary(team):
    return team.total_salary()

def draw_budget_top_right(team):
    text = f"Budget: {fmt_money_short(team_total_salary(team))} / {fmt_money_short(team.budget)}"
    surf = HEADER_FONT.render(text, True, (255, 225, 120))
    screen.blit(surf, (WIDTH - surf.get_width() - 24, 24))

# --------------------------------------------------
# pixel backgrounds
# --------------------------------------------------

def draw_pixel_stars(surface, seed, count=180):
    rng = random.Random(seed)
    for _ in range(count):
        x = rng.randint(0, WIDTH - 2)
        y = rng.randint(0, HEIGHT - 2)
        c = rng.choice([(255, 220, 120), (220, 235, 255), (255, 255, 255)])
        surface.fill(c, pygame.Rect(x, y, 2, 2))

def build_gameday_bg():
    bg = pygame.Surface((WIDTH, HEIGHT))
    bg.fill((10, 14, 42))
    draw_pixel_stars(bg, 101, 220)
    pygame.draw.rect(bg, (22, 30, 58), (25, 18, WIDTH - 50, 80), border_radius=8)
    pygame.draw.rect(bg, (212, 180, 88), (25, 18, WIDTH - 50, 80), 3, border_radius=8)
    pygame.draw.rect(bg, (20, 28, 52), (WIDTH // 2 - 95, 112, 190, 52), border_radius=6)
    pygame.draw.rect(bg, (180, 210, 255), (WIDTH // 2 - 95, 112, 190, 52), 2, border_radius=6)
    start_y = 205
    row_h = 88
    for i in range(8):
        y = start_y + i * row_h
        pygame.draw.rect(bg, (15, 22, 42), (55, y, WIDTH - 110, 68), border_radius=6)
        pygame.draw.rect(bg, (120, 145, 175), (55, y, WIDTH - 110, 68), 2, border_radius=6)
    pygame.draw.rect(bg, (18, 28, 50), (35, HEIGHT - 55, WIDTH - 70, 32), border_radius=5)
    return bg

def build_boxscore_bg():
    bg = pygame.Surface((WIDTH, HEIGHT))
    bg.fill((8, 18, 44))
    draw_pixel_stars(bg, 202, 220)
    pygame.draw.rect(bg, (22, 30, 58), (25, 18, WIDTH - 50, 80), border_radius=8)
    pygame.draw.rect(bg, (212, 180, 88), (25, 18, WIDTH - 50, 80), 3, border_radius=8)
    pygame.draw.rect(bg, (16, 22, 42), (40, 145, WIDTH - 80, 200), border_radius=8)
    pygame.draw.rect(bg, (120, 145, 175), (40, 145, WIDTH - 80, 200), 2, border_radius=8)
    pygame.draw.rect(bg, (16, 22, 42), (40, 372, WIDTH - 80, 110), border_radius=8)
    pygame.draw.rect(bg, (120, 145, 175), (40, 372, WIDTH - 80, 110), 2, border_radius=8)
    pygame.draw.rect(bg, (18, 28, 50), (35, HEIGHT - 55, WIDTH - 70, 32), border_radius=5)
    return bg

def build_playoff_bg():
    bg = pygame.Surface((WIDTH, HEIGHT))
    bg.fill((8, 16, 48))
    draw_pixel_stars(bg, 303, 250)

    pygame.draw.rect(bg, (22, 30, 58), (25, 18, WIDTH - 50, 80), border_radius=8)
    pygame.draw.rect(bg, (212, 180, 88), (25, 18, WIDTH - 50, 80), 3, border_radius=8)

    left_boxes = [(60, 205), (60, 290), (60, 455), (60, 540)]
    for x, y in left_boxes:
        pygame.draw.rect(bg, (16, 22, 42), (x, y, 280, 58), border_radius=6)
        pygame.draw.rect(bg, (120, 145, 175), (x, y, 280, 58), 2, border_radius=6)

    pygame.draw.rect(bg, (16, 22, 42), (495, 330, 295, 68), border_radius=6)
    pygame.draw.rect(bg, (120, 145, 175), (495, 330, 295, 68), 2, border_radius=6)

    pygame.draw.rect(bg, (16, 22, 42), (355, 735, 420, 88), border_radius=6)
    pygame.draw.rect(bg, (212, 180, 88), (355, 735, 420, 88), 3, border_radius=6)

    lc = (185, 220, 255)
    pygame.draw.line(bg, lc, (340, 234), (430, 234), 4)
    pygame.draw.line(bg, lc, (340, 319), (430, 319), 4)
    pygame.draw.line(bg, lc, (430, 234), (430, 319), 4)
    pygame.draw.line(bg, lc, (430, 276), (495, 276), 4)
    pygame.draw.line(bg, lc, (495, 276), (495, 364), 4)

    pygame.draw.line(bg, lc, (340, 484), (430, 484), 4)
    pygame.draw.line(bg, lc, (340, 569), (430, 569), 4)
    pygame.draw.line(bg, lc, (430, 484), (430, 569), 4)
    pygame.draw.line(bg, lc, (430, 526), (495, 526), 4)
    pygame.draw.line(bg, lc, (495, 526), (495, 364), 4)

    pygame.draw.line(bg, lc, (642, 398), (642, 685), 4)
    pygame.draw.line(bg, lc, (560, 685), (724, 685), 4)

    pygame.draw.rect(bg, (18, 28, 50), (35, HEIGHT - 55, WIDTH - 70, 32), border_radius=5)
    return bg

GAME_DAY_BG = build_gameday_bg()
BOX_SCORE_BG = build_boxscore_bg()
PLAYOFF_BG = build_playoff_bg()

# --------------------------------------------------
# season
# --------------------------------------------------

class Season:
    def __init__(self, user_team_name):
        self.year = 1
        self.teams = generate_league(user_team_name)
        self.user_team = self.teams[0]
        self.schedule = self.build_schedule(self.teams)
        self.current_day = 0
        self.playoff_round = None
        self.playoff_matchups = []
        self.champion = None
        self.awards = None

    def build_schedule(self, teams):
        teams = teams[:]
        if len(teams) % 2 == 1:
            teams.append(None)

        days = []
        n = len(teams)
        for cycle in range(4):
            rotation = teams[:]
            for day_idx in range(n - 1):
                day_games = []
                for i in range(n // 2):
                    t1 = rotation[i]
                    t2 = rotation[n - 1 - i]
                    if t1 is not None and t2 is not None:
                        if (cycle + day_idx + i) % 2 == 0:
                            day_games.append((t1, t2))
                        else:
                            day_games.append((t2, t1))
                days.append(day_games)
                rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]
        random.Random(21).shuffle(days)
        return days[:SEASON_GAMES]

    def standings(self):
        return sorted(
            self.teams,
            key=lambda t: ((t.wins / (t.wins + t.losses)) if (t.wins + t.losses) > 0 else 0.0, t.wins),
            reverse=True
        )

    def division_standings(self, division):
        return sorted(
            [t for t in self.teams if t.division == division],
            key=lambda t: ((t.wins / (t.wins + t.losses)) if (t.wins + t.losses) > 0 else 0.0, t.wins),
            reverse=True
        )

    def regular_season_over(self):
        return self.current_day >= len(self.schedule)

    def remaining_days(self):
        return len(self.schedule) - self.current_day

    def start_playoffs(self):
        east = self.division_standings("East")[:2]
        west = self.division_standings("West")[:2]
        seeds = sorted(east + west, key=lambda t: ((t.wins / (t.wins + t.losses)) if (t.wins + t.losses) > 0 else 0.0, t.wins), reverse=True)
        self.playoff_round = "Semifinals"
        self.playoff_matchups = [(seeds[0], seeds[3]), (seeds[1], seeds[2])]

    def get_tradeable_user_players():
        return user_team.lineup + user_team.bench

    def get_tradeable_cpu_team():
        cpu_teams = season.teams[1:]
        if not cpu_teams:
            return None
        return cpu_teams[selected_trade_cpu_team]

    def get_tradeable_cpu_players():
        cpu_team = get_tradeable_cpu_team()
        if cpu_team is None:
            return []
        return cpu_team.lineup + cpu_team.bench

    def play_playoff_round(self):
        results = []
        for away_team, home_team in self.playoff_matchups:
            game = simulate_game_with_box(away_team, home_team)
            away_score = game["away_score"]
            home_score = game["home_score"]
            winner = away_team if away_score > home_score else home_team

            results.append({
                "title": self.playoff_round,
                "away_team": away_team,
                "home_team": home_team,
                "away_score": away_score,
                "home_score": home_score,
                "away_by_inning": game["away_by_inning"],
                "home_by_inning": game["home_by_inning"],
                "winner": winner,
                "usage": game["usage"],
            })

            finalize_team_game(away_team, game["usage"].get(away_team.name, {}))
            finalize_team_game(home_team, game["usage"].get(home_team.name, {}))

        winners = [r["winner"] for r in results]
        if self.playoff_round == "Semifinals":
            self.playoff_round = "Finals"
            self.playoff_matchups = [(winners[0], winners[1])]
        else:
            self.playoff_round = "Complete"
            self.champion = winners[0]
            self.playoff_matchups = []

        return results

# --------------------------------------------------
# coaching + fatigue + sim wrappers
# --------------------------------------------------

def apply_pitching_coach(team, pitcher):
    coach = team.pitching_coach
    if coach is None or team.pitching_assignment_name != pitcher.name:
        return pitcher

    boosted = copy.copy(pitcher)
    boosted.average_minus = pitcher.display_average_minus
    boosted.obp_minus = pitcher.display_obp_minus
    boosted.slugging_minus = pitcher.display_slugging_minus
    boosted.bb_plus = max(0, pitcher.bb_plus - max(1, coach.obp_boost // 2))
    boosted.hbp_plus = max(0, pitcher.hbp_plus - max(0, coach.avg_boost // 3))
    return boosted

def get_pitcher_for_inning(team, inning):
    if inning <= 5:
        p = team.starter
    elif inning <= 7:
        p = team.middle_reliever if team.middle_reliever else team.starter
    else:
        p = team.closer if team.closer else (team.middle_reliever or team.starter)
    return apply_pitching_coach(team, p)

def simulate_game_with_box(away_team, home_team):
    away_score = 0
    home_score = 0
    away_idx = 0
    home_idx = 0
    away_by_inning = []
    home_by_inning = []

    usage = {
        away_team.name: {away_team.starter.name: 5, away_team.middle_reliever.name if away_team.middle_reliever else "": 2, away_team.closer.name if away_team.closer else "": 2},
        home_team.name: {home_team.starter.name: 5, home_team.middle_reliever.name if home_team.middle_reliever else "": 2, home_team.closer.name if home_team.closer else "": 2},
    }

    for inning in range(1, 10):
        home_pitcher = get_pitcher_for_inning(home_team, inning)
        away_pitcher = get_pitcher_for_inning(away_team, inning)

        r, away_idx = simulate_half_inning(away_team.lineup, home_pitcher, away_idx, verbose=False)
        away_score += r
        away_by_inning.append(r)

        r, home_idx = simulate_half_inning(home_team.lineup, away_pitcher, home_idx, verbose=False)
        home_score += r
        home_by_inning.append(r)

    return {
        "away_score": away_score,
        "home_score": home_score,
        "away_by_inning": away_by_inning,
        "home_by_inning": home_by_inning,
        "usage": usage,
    }

def finalize_team_game(team, usage_map):
    used_names = set(name for name in usage_map if name)
    team.apply_coaching_progress()
    team.apply_postgame_fatigue(usage_map)
    team.recover_pitcher_fatigue(used_names)

    for h in team.lineup:
        h.season_games += 1
    for name in used_names:
        for p in team.rotation + team.bullpen:
            if p.name == name:
                p.season_games += 1
                if p == team.starter:
                    p.games_started += 1

    team.cycle_rotation()
    team.refresh_roles()

# --------------------------------------------------
# ui state
# --------------------------------------------------

game_state = "name_input"
typed_team_name = ""
trade_mode = "incoming"   # incoming or outgoing
selected_trade_cpu_team = 0
selected_trade_user_player = 0
selected_trade_cpu_player = 0
season = None
user_team = None

free_agent_hitters = []
free_agent_pitchers = []
free_agent_hitting_coaches = []
free_agent_pitching_coaches = []

status_message = "Welcome to MLB Pro Manager"
all_games_today = []
selected_game_index = 0
viewed_team_index = 0

roster_tab = "hitters"  # hitters, pitchers, coaches, stats
roster_focus = "lineup"
pending_selection = None

selection_index = {
    "lineup": 0,
    "bench": 0,
    "minors_hitters": 0,
    "fa_hitters": 0,
    "rotation_roles": 0,
    "bullpen": 0,
    "minors_pitchers": 0,
    "fa_pitchers": 0,
    "pitching_coach_slot": 0,
    "pitching_coach_market": 0,
    "hitting_coach_slot": 0,
    "hitting_coach_market": 0,
    "stats_roster": 0,
}

playoff_selected_matchup = 0
playoff_anim_tick = 0

current_trade_offer = None
current_awards = None

# --------------------------------------------------
# roster selection helpers
# --------------------------------------------------

def hitter_lists():
    return {
        "lineup": user_team.lineup,
        "bench": user_team.bench,
        "minors_hitters": user_team.minors_hitters,
        "fa_hitters": free_agent_hitters,
    }

def pitcher_role_list(team):
    return team.rotation[:5] + [team.middle_reliever, team.closer]

def pitcher_lists():
    return {
        "rotation_roles": pitcher_role_list(user_team),
        "bullpen": user_team.bullpen,
        "minors_pitchers": user_team.minors_pitchers,
        "fa_pitchers": free_agent_pitchers,
    }

def coach_lists():
    return {
        "pitching_coach_slot": [user_team.pitching_coach] if user_team.pitching_coach else [],
        "pitching_coach_market": free_agent_pitching_coaches,
        "hitting_coach_slot": user_team.hitting_coaches,
        "hitting_coach_market": free_agent_hitting_coaches,
    }

def move_selection(delta):
    if roster_tab == "hitters":
        size = len(hitter_lists()[roster_focus])
    elif roster_tab == "pitchers":
        size = len(pitcher_lists()[roster_focus])
    elif roster_tab == "coaches":
        size = len(coach_lists()[roster_focus])
    else:
        size = len(user_team.lineup + user_team.bench + user_team.rotation + user_team.bullpen)
    selection_index[roster_focus] = clamp_index(selection_index[roster_focus] + delta, size)

def handle_roster_select():
    global pending_selection, status_message

    if roster_tab == "hitters":
        lists = hitter_lists()
    elif roster_tab == "pitchers":
        lists = pitcher_lists()
    elif roster_tab == "coaches":
        lists = coach_lists()
    else:
        return

    idx = selection_index[roster_focus]
    cur = lists[roster_focus]

    if len(cur) == 0:
        status_message = "That list is empty."
        return

    if pending_selection is None or pending_selection["tab"] != roster_tab:
        pending_selection = {"tab": roster_tab, "list_name": roster_focus, "index": idx}
        status_message = f"Selected {roster_focus} #{idx + 1}"
        return

    src_name = pending_selection["list_name"]
    src_idx = pending_selection["index"]
    dst_name = roster_focus
    dst_idx = idx

    if roster_tab == "hitters":
        status_message = perform_hitter_move(src_name, src_idx, dst_name, dst_idx)
    elif roster_tab == "pitchers":
        status_message = perform_pitcher_move(src_name, src_idx, dst_name, dst_idx)
    else:
        status_message = perform_coach_move(src_name, src_idx, dst_name, dst_idx)

    pending_selection = None

def perform_hitter_move(src_name, src_idx, dst_name, dst_idx):
    lists = hitter_lists()
    src = lists[src_name]
    dst = lists[dst_name]

    if not (0 <= src_idx < len(src) and 0 <= dst_idx < len(dst)):
        return "Invalid hitter move."

    if src_name == dst_name:
        src[src_idx], src[dst_idx] = src[dst_idx], src[src_idx]
        return "Swapped hitters."

    if "fa" in (src_name, dst_name):
        fa_player = src[src_idx] if src_name == "fa_hitters" else dst[dst_idx]
        outgoing = src[src_idx] if src_name != "fa_hitters" else dst[dst_idx]
        if not user_team.can_afford(fa_player.salary, outgoing.salary):
            return "Cannot afford that free agent."
    src[src_idx], dst[dst_idx] = dst[dst_idx], src[src_idx]
    return "Moved hitter."

def perform_pitcher_move(src_name, src_idx, dst_name, dst_idx):
    lists = pitcher_lists()
    src = lists[src_name]
    dst = lists[dst_name]

    if not (0 <= src_idx < len(src) and 0 <= dst_idx < len(dst)):
        return "Invalid pitcher move."

    if src_name == dst_name:
        src[src_idx], src[dst_idx] = src[dst_idx], src[src_idx]
        user_team.refresh_roles()
        return "Swapped pitchers."

    if "fa" in (src_name, dst_name):
        fa_player = src[src_idx] if src_name == "fa_pitchers" else dst[dst_idx]
        outgoing = src[src_idx] if src_name != "fa_pitchers" else dst[dst_idx]
        if not user_team.can_afford(fa_player.salary, outgoing.salary):
            return "Cannot afford that free-agent pitcher."

    src[src_idx], dst[dst_idx] = dst[dst_idx], src[src_idx]

    # roles are first 5 rotation + middle reliever + closer
    if src_name == "rotation_roles" or dst_name == "rotation_roles":
        flat = lists["rotation_roles"]
        user_team.rotation = flat[:5]
        user_team.middle_reliever = flat[5]
        user_team.closer = flat[6]
    user_team.refresh_roles()
    return "Moved pitcher."

def perform_coach_move(src_name, src_idx, dst_name, dst_idx):
    if src_name == dst_name:
        return "Pick a coach from market and a destination slot."

    if {src_name, dst_name} == {"pitching_coach_slot", "pitching_coach_market"}:
        idx = src_idx if src_name == "pitching_coach_market" else dst_idx
        market_coach = free_agent_pitching_coaches[idx]
        current = user_team.pitching_coach
        outgoing_salary = current.salary if current else 0
        if not user_team.can_afford(market_coach.salary, outgoing_salary):
            return "Cannot afford pitching coach."
        user_team.pitching_coach = market_coach
        if current:
            free_agent_pitching_coaches[idx] = current
        else:
            free_agent_pitching_coaches.pop(idx)
        return f"Hired pitching coach {market_coach.name}."

    if {src_name, dst_name} == {"hitting_coach_slot", "hitting_coach_market"}:
        idx = src_idx if src_name == "hitting_coach_market" else dst_idx
        market_coach = free_agent_hitting_coaches[idx]
        if len(user_team.hitting_coaches) >= 2 and src_name == "hitting_coach_market":
            replaced = user_team.hitting_coaches[dst_idx]
            if not user_team.can_afford(market_coach.salary, replaced.salary):
                return "Cannot afford hitting coach."
            user_team.hitting_coaches[dst_idx] = market_coach
            free_agent_hitting_coaches[idx] = replaced
            return f"Replaced hitting coach with {market_coach.name}."
        if len(user_team.hitting_coaches) < 2:
            if not user_team.can_afford(market_coach.salary, 0):
                return "Cannot afford hitting coach."
            user_team.hitting_coaches.append(market_coach)
            free_agent_hitting_coaches.pop(idx)
            return f"Hired hitting coach {market_coach.name}."
    return "Coach move not allowed."

# --------------------------------------------------
# drawing helpers
# --------------------------------------------------

def draw_box_frame(title, x, y, w, h, focused=False):
    pygame.draw.rect(screen, (18, 25, 45), (x, y, w, h), border_radius=6)
    border = (255, 225, 120) if focused else (120, 145, 170)
    pygame.draw.rect(screen, border, (x, y, w, h), 2, border_radius=6)
    screen.blit(HEADER_FONT.render(title, True, border), (x + 10, y + 8))

def draw_hitter_row(x, y, w, hitter, selected=False, focused=False, show_num=None):
    color = (255, 225, 120) if selected and focused else (230, 230, 230)
    prefix = ">" if selected else " "
    num = f"{show_num}. " if show_num is not None else ""
    screen.blit(BODY_FONT.render(prefix + num + short_name(get_player_name(hitter), 11), True, color), (x, y))
    screen.blit(BODY_FONT.render(fmt_stat(hitter.display_average), True, color), (x + 190, y))
    screen.blit(BODY_FONT.render(fmt_stat(hitter.display_obp), True, color), (x + 270, y))
    screen.blit(BODY_FONT.render(fmt_stat(hitter.display_ops), True, color), (x + 350, y))
    screen.blit(BODY_FONT.render(fmt_money_short(hitter.salary), True, color), (x + w - 85, y))
    bonus = hitter.coach_bonus_string()
    if bonus:
        screen.blit(SMALL_FONT.render(bonus[:22], True, (120, 255, 140)), (x + 500, y))

def draw_pitcher_row(x, y, w, pitcher, selected=False, focused=False):
    color = (255, 225, 120) if selected and focused else (230, 230, 230)
    prefix = ">" if selected else " "
    screen.blit(BODY_FONT.render(prefix + short_name(get_player_name(pitcher), 11), True, color), (x, y))
    screen.blit(BODY_FONT.render(str(pitcher.display_average_minus), True, color), (x + 190, y))
    screen.blit(BODY_FONT.render(str(pitcher.display_obp_minus), True, color), (x + 260, y))
    screen.blit(BODY_FONT.render(str(pitcher.display_slugging_minus), True, color), (x + 330, y))
    screen.blit(BODY_FONT.render(fmt_money_short(pitcher.salary), True, color), (x + w - 85, y))
    bonus = pitcher.coach_bonus_string()
    if bonus:
        screen.blit(SMALL_FONT.render(bonus[:22], True, (120, 255, 140)), (x + 470, y))

def draw_hitter_list_box(title, items, x, y, w, h, selected_idx=None, focused=False, lineup_numbers=False):
    draw_box_frame(title, x, y, w, h, focused)
    screen.blit(SMALL_FONT.render("NAME", True, (180, 210, 255)), (x + 18, y + 40))
    screen.blit(SMALL_FONT.render("AVG", True, (180, 210, 255)), (x + 190, y + 40))
    screen.blit(SMALL_FONT.render("OBP", True, (180, 210, 255)), (x + 270, y + 40))
    screen.blit(SMALL_FONT.render("OPS", True, (180, 210, 255)), (x + 350, y + 40))
    screen.blit(SMALL_FONT.render("SAL", True, (180, 210, 255)), (x + w - 85, y + 40))

    row_y = y + 66
    max_rows = min((h - 80) // 24, len(items))
    for i in range(max_rows):
        draw_hitter_row(x + 10, row_y, w - 20, items[i], i == selected_idx, focused, i + 1 if lineup_numbers else None)
        row_y += 24

def draw_pitcher_list_box(title, items, x, y, w, h, selected_idx=None, focused=False):
    draw_box_frame(title, x, y, w, h, focused)
    screen.blit(SMALL_FONT.render("NAME", True, (180, 210, 255)), (x + 18, y + 40))
    screen.blit(SMALL_FONT.render("AVG-", True, (180, 210, 255)), (x + 190, y + 40))
    screen.blit(SMALL_FONT.render("OBP-", True, (180, 210, 255)), (x + 260, y + 40))
    screen.blit(SMALL_FONT.render("SLG-", True, (180, 210, 255)), (x + 330, y + 40))
    screen.blit(SMALL_FONT.render("SAL", True, (180, 210, 255)), (x + w - 85, y + 40))

    row_y = y + 66
    max_rows = min((h - 80) // 24, len(items))
    for i in range(max_rows):
        draw_pitcher_row(x + 10, row_y, w - 20, items[i], i == selected_idx, focused)
        row_y += 24

def draw_stats_tab():
    screen.fill((14, 14, 30))
    screen.blit(TITLE_FONT.render(f"{user_team.name.upper()} PLAYER STATS", True, (255, 225, 120)), (30, 20))
    draw_budget_top_right(user_team)
    screen.blit(BODY_FONT.render("1 Hitters | 2 Pitchers | 3 Coaches | 4 Stats | Up/Down scroll | M Menu", True, (190, 190, 190)), (30, 70))

    roster = user_team.lineup + user_team.bench + user_team.rotation + user_team.bullpen
    start = max(0, selection_index["stats_roster"] - 6)
    view = roster[start:start + 12]

    y = 120
    for i, p in enumerate(view):
        selected = (start + i == selection_index["stats_roster"])
        color = (255, 225, 120) if selected else (230, 230, 230)

        if hasattr(p, "ops"):
            avg = round((p.hits / p.ab), 3) if p.ab > 0 else 0.0
            text = (
                f"{short_name(p.name, 12):12} "
                f"H {p.hits:3} 2B {p.doubles:2} 1B {p.singles:2} HR {p.homeruns:2} "
                f"RBI {p.rbi:3} BB {p.walks:2} SO {p.strikeouts:2} AVG {avg:.3f}"
            )
        else:
            text = (
                f"{short_name(p.name, 12):12} IP {p.innings_pitched_text:>4} "
                f"ERA {p.era:>4} H {p.hits_allowed:3} BB {p.walks:2} SO {p.strikeouts:2} "
                f"FAT {int(p.fatigue):2}"
            )

        prefix = ">" if selected else " "
        screen.blit(BODY_FONT.render(prefix + text, True, color), (40, y))
        y += 28

def draw_hitter_roster():
    screen.fill((14, 14, 30))
    screen.blit(TITLE_FONT.render(f"{user_team.name.upper()} HITTERS", True, (255, 225, 120)), (30, 20))
    draw_budget_top_right(user_team)
    screen.blit(BODY_FONT.render("A Lineup | W Bench | F Minors | G FA | Up/Down Move | S Select/Swap | 2 Pitchers | 3 Coaches | 4 Stats | M Menu", True, (190, 190, 190)), (30, 70))

    lists = hitter_lists()
    draw_hitter_list_box("LINEUP", lists["lineup"], 30, 115, 575, 315, selection_index["lineup"], roster_focus == "lineup", lineup_numbers=True)
    draw_hitter_list_box("BENCH", lists["bench"], 30, 450, 575, 185, selection_index["bench"], roster_focus == "bench")
    draw_hitter_list_box("MINOR HITTERS", lists["minors_hitters"], 635, 115, 575, 240, selection_index["minors_hitters"], roster_focus == "minors_hitters")
    draw_hitter_list_box("FA HITTERS", lists["fa_hitters"], 635, 375, 575, 260, selection_index["fa_hitters"], roster_focus == "fa_hitters")

    sel = "NONE" if pending_selection is None else f"{pending_selection['list_name']} #{pending_selection['index'] + 1}"
    screen.blit(BODY_FONT.render(f"Selected: {sel}", True, (120, 255, 140)), (30, HEIGHT - 55))
    screen.blit(BODY_FONT.render(status_message, True, (255, 210, 90)), (30, HEIGHT - 30))

def draw_pitcher_roster():
    screen.fill((14, 14, 30))
    screen.blit(TITLE_FONT.render(f"{user_team.name.upper()} PITCHERS", True, (255, 225, 120)), (30, 20))
    draw_budget_top_right(user_team)
    screen.blit(BODY_FONT.render("A Rotation/Roles | W Bullpen | F Minors | G FA | Up/Down Move | S Select/Swap | 1 Hitters | 3 Coaches | 4 Stats | M Menu", True, (190, 190, 190)), (30, 70))

    roles = user_team.rotation[:5] + [user_team.middle_reliever, user_team.closer]
    draw_pitcher_list_box("ROTATION + RELIEF ROLES", roles, 30, 115, 575, 260, selection_index["rotation_roles"], roster_focus == "rotation_roles")
    draw_pitcher_list_box("BULLPEN", user_team.bullpen, 30, 395, 575, 240, selection_index["bullpen"], roster_focus == "bullpen")
    draw_pitcher_list_box("MINOR PITCHERS", user_team.minors_pitchers, 635, 115, 575, 240, selection_index["minors_pitchers"], roster_focus == "minors_pitchers")
    draw_pitcher_list_box("FA PITCHERS", free_agent_pitchers, 635, 375, 575, 260, selection_index["fa_pitchers"], roster_focus == "fa_pitchers")

    sel = "NONE" if pending_selection is None else f"{pending_selection['list_name']} #{pending_selection['index'] + 1}"
    screen.blit(BODY_FONT.render(f"Selected: {sel}", True, (120, 255, 140)), (30, HEIGHT - 55))
    screen.blit(BODY_FONT.render(status_message, True, (255, 210, 90)), (30, HEIGHT - 30))

def draw_coach_row(x, y, coach, color):
    if hasattr(coach, "ops_boost"):
        text = f"{short_name(coach.name,12):12} AVG+{coach.avg_boost:2} OBP+{coach.obp_boost:2} OPS+{coach.ops_boost:2} {fmt_money_short(coach.salary)}"
    else:
        text = f"{short_name(coach.name,12):12} AVG+{coach.avg_boost:2} OBP+{coach.obp_boost:2} SLG+{coach.slg_boost:2} {fmt_money_short(coach.salary)}"
    screen.blit(BODY_FONT.render(text, True, color), (x, y))

def draw_coaches_tab():
    screen.fill((14, 14, 30))
    screen.blit(TITLE_FONT.render(f"{user_team.name.upper()} COACHES", True, (255, 225, 120)), (30, 20))
    draw_budget_top_right(user_team)
    screen.blit(BODY_FONT.render("A Pitching Coach | W Pitching Market | F Hitting Coaches | G Hitting Market | Up/Down Move | S Select/Hire | 1 Hitters | 2 Pitchers | 4 Stats | M Menu", True, (190, 190, 190)), (30, 70))

    draw_box_frame("ACTIVE PITCHING COACH", 30, 120, 560, 150, roster_focus == "pitching_coach_slot")
    if user_team.pitching_coach:
        draw_coach_row(42, 185, user_team.pitching_coach, (230,230,230))
        assign_text = f"Assigned pitcher: {user_team.pitching_assignment_name or 'None'}"
        screen.blit(BODY_FONT.render(assign_text, True, (120,255,140)), (42, 215))

    draw_box_frame("PITCHING MARKET", 30, 295, 560, 250, roster_focus == "pitching_coach_market")
    y = 340
    for i, coach in enumerate(free_agent_pitching_coaches[:7]):
        color = (255,225,120) if i == selection_index["pitching_coach_market"] and roster_focus == "pitching_coach_market" else (230,230,230)
        prefix = ">" if i == selection_index["pitching_coach_market"] and roster_focus == "pitching_coach_market" else " "
        screen.blit(BODY_FONT.render(prefix, True, color), (42, y))
        draw_coach_row(58, y, coach, color)
        y += 28

    draw_box_frame("ACTIVE HITTING COACHES", 635, 120, 560, 180, roster_focus == "hitting_coach_slot")
    y = 165
    for i, coach in enumerate(user_team.hitting_coaches[:2]):
        color = (255,225,120) if i == selection_index["hitting_coach_slot"] and roster_focus == "hitting_coach_slot" else (230,230,230)
        prefix = ">" if i == selection_index["hitting_coach_slot"] and roster_focus == "hitting_coach_slot" else " "
        screen.blit(BODY_FONT.render(prefix, True, color), (647, y))
        draw_coach_row(663, y, coach, color)
        y += 28

    assigned = ", ".join(user_team.hitting_assignment_names) if user_team.hitting_assignment_names else "None"
    screen.blit(BODY_FONT.render(f"Assigned hitters: {assigned}", True, (120,255,140)), (647, 255))

    draw_box_frame("HITTING MARKET", 635, 325, 560, 250, roster_focus == "hitting_coach_market")
    y = 370
    for i, coach in enumerate(free_agent_hitting_coaches[:7]):
        color = (255,225,120) if i == selection_index["hitting_coach_market"] and roster_focus == "hitting_coach_market" else (230,230,230)
        prefix = ">" if i == selection_index["hitting_coach_market"] and roster_focus == "hitting_coach_market" else " "
        screen.blit(BODY_FONT.render(prefix, True, color), (647, y))
        draw_coach_row(663, y, coach, color)
        y += 28

    screen.blit(BODY_FONT.render("Use K to assign selected pitching coach to selected pitcher from pitcher tab.", True, (180,210,255)), (30, HEIGHT - 55))
    screen.blit(BODY_FONT.render(status_message, True, (255,210,90)), (30, HEIGHT - 30))

def draw_user_roster():
    if roster_tab == "hitters":
        draw_hitter_roster()
    elif roster_tab == "pitchers":
        draw_pitcher_roster()
    elif roster_tab == "coaches":
        draw_coaches_tab()
    else:
        draw_stats_tab()

def draw_game_day():
    screen.blit(GAME_DAY_BG, (0, 0))
    title = all_games_today[0]["title"] if all_games_today else "Game Day Results"
    screen.blit(TITLE_FONT.render(title.upper(), True, (255, 225, 120)), (60, 36))
    label = f"DAY {season.current_day}" if not season.regular_season_over() else "PLAYOFFS"
    screen.blit(HEADER_FONT.render(label, True, (240, 240, 240)), (WIDTH // 2 - 40, 125))

    y = 212
    for i, game in enumerate(all_games_today[:8]):
        selected = i == selected_game_index
        color = (255,225,120) if selected else (235,235,235)
        prefix = ">" if selected else " "
        text = f"{prefix} {game['away_team'].name:<10} {game['away_score']} - {game['home_team'].name:<10} {game['home_score']}"
        screen.blit(HEADER_FONT.render(text, True, color), (78, y))
        y += 66

    screen.blit(BODY_FONT.render("UP/DOWN = game | S = box score | M = menu", True, (210,210,210)), (60, HEIGHT - 44))

def draw_box_score():
    screen.blit(BOX_SCORE_BG, (0, 0))
    screen.blit(TITLE_FONT.render("BOX SCORE", True, (255,225,120)), (60, 36))
    if not all_games_today:
        return
    game = all_games_today[selected_game_index]
    screen.blit(HEADER_FONT.render(f"{game['away_team'].name} at {game['home_team'].name}", True, (240,240,240)), (60, 86))

    start_x = 350
    gap = 70
    for inn in range(1, 10):
        screen.blit(BODY_FONT.render(str(inn), True, (180,210,255)), (start_x + (inn - 1) * gap, 176))
    screen.blit(BODY_FONT.render("R", True, (255,225,120)), (1010, 176))

    away_y = 220
    home_y = 265
    screen.blit(HEADER_FONT.render(short_name(game["away_team"].name, 12), True, (235,235,235)), (80, away_y))
    screen.blit(HEADER_FONT.render(short_name(game["home_team"].name, 12), True, (235,235,235)), (80, home_y))

    for i, r in enumerate(game["away_by_inning"]):
        screen.blit(HEADER_FONT.render(str(r), True, (235,235,235)), (start_x + i * gap, away_y))
    for i, r in enumerate(game["home_by_inning"]):
        screen.blit(HEADER_FONT.render(str(r), True, (235,235,235)), (start_x + i * gap, home_y))

    screen.blit(HEADER_FONT.render(str(game["away_score"]), True, (255,225,120)), (1010, away_y))
    screen.blit(HEADER_FONT.render(str(game["home_score"]), True, (255,225,120)), (1010, home_y))
    winner = game["away_team"].name if game["away_score"] > game["home_score"] else game["home_team"].name
    screen.blit(HEADER_FONT.render(f"Winner: {winner}", True, (120,255,140)), (80, 400))
    screen.blit(BODY_FONT.render("LEFT/RIGHT = change game | M = menu", True, (210,210,210)), (60, HEIGHT - 44))

def draw_playoff_bracket():
    global playoff_anim_tick
    screen.blit(PLAYOFF_BG, (0, 0))
    playoff_anim_tick += 1
    pulse = 220 + int(25 * abs((playoff_anim_tick % 60) - 30) / 30)
    pulse_color = (255, pulse, 120)

    screen.blit(TITLE_FONT.render("PLAYOFF BRACKET", True, (255,225,120)), (60, 36))
    top4 = sorted(season.division_standings("East")[:2] + season.division_standings("West")[:2],
                  key=lambda t: ((t.wins / (t.wins + t.losses)) if (t.wins + t.losses) > 0 else 0.0, t.wins),
                  reverse=True)

    positions = [(85,220), (85,305), (85,470), (85,555)]
    for i, team in enumerate(top4):
        screen.blit(HEADER_FONT.render(f"#{i+1}: {team.name}", True, (240,240,240)), positions[i])

    semiboxes = [pygame.Rect(60,205,280,58), pygame.Rect(60,455,280,58)]
    for i, rect in enumerate(semiboxes):
        if playoff_selected_matchup == i:
            pygame.draw.rect(screen, pulse_color, rect, 3, border_radius=6)

    if len(top4) >= 4:
        screen.blit(BODY_FONT.render(f"{top4[0].name} vs {top4[3].name}", True, (240,240,240)), (365,248))
        screen.blit(BODY_FONT.render(f"{top4[1].name} vs {top4[2].name}", True, (240,240,240)), (365,498))

    screen.blit(HEADER_FONT.render("FINAL", True, (180,210,255)), (585,295))
    screen.blit(HEADER_FONT.render("CHAMPION", True, (255,225,120)), (450,710))

    if season.playoff_round in ("Finals", "Complete") and season.playoff_matchups:
        t1, t2 = season.playoff_matchups[0]
        final_rect = pygame.Rect(495,330,295,68)
        if playoff_selected_matchup == 2:
            pygame.draw.rect(screen, pulse_color, final_rect, 3, border_radius=6)
        screen.blit(HEADER_FONT.render(t1.name, True, (240,240,240)), (530,347))
        screen.blit(HEADER_FONT.render(t2.name, True, (240,240,240)), (530,378))

    if season.champion:
        champ_rect = pygame.Rect(355,735,420,88)
        pygame.draw.rect(screen, pulse_color, champ_rect, 3, border_radius=6)
        screen.blit(HEADER_FONT.render(season.champion.name, True, (255,225,120)), (455,775))

    lines = [
        "LEFT/RIGHT = select matchup",
        "S = view selected matchup box score",
        "ENTER = next playoff round",
        "M = menu",
    ]
    y = HEIGHT - 120
    for line in lines:
        screen.blit(BODY_FONT.render(line, True, (210,210,210)), (60, y))
        y += 22

def draw_cpu_roster():
    screen.fill((14,14,30))
    cpu_teams = season.teams[1:]
    t = cpu_teams[viewed_team_index]
    screen.blit(TITLE_FONT.render(f"CPU TEAM: {t.name.upper()}", True, (255,225,120)), (30,20))
    screen.blit(BODY_FONT.render("LEFT/RIGHT = change team | M = menu", True, (190,190,190)), (30,70))
    draw_hitter_list_box("LINEUP", t.lineup, 30, 115, 575, 315, None, False, lineup_numbers=True)
    draw_hitter_list_box("BENCH", t.bench, 30, 450, 575, 185, None, False)
    draw_pitcher_list_box("ROTATION", t.rotation, 635, 115, 575, 240, None, False)
    draw_pitcher_list_box("BULLPEN", t.bullpen, 635, 375, 575, 260, None, False)

def draw_trade_screen():
    screen.fill((14, 14, 30))
    screen.blit(TITLE_FONT.render("TRADES", True, (255, 225, 120)), (30, 20))

    mode_text = "Mode: Incoming Offers" if trade_mode == "incoming" else "Mode: Make Offer"
    screen.blit(BODY_FONT.render(mode_text, True, (190, 190, 190)), (30, 70))
    screen.blit(BODY_FONT.render("Q = incoming offers | E = make offer | T = refresh | Y = accept/send | N = reject/cancel | M = menu", True, (190, 190, 190)), (30, 100))

    if trade_mode == "incoming":
        if not current_trade_offer:
            screen.blit(HEADER_FONT.render("No incoming trade offer available.", True, (230, 230, 230)), (30, 160))
            return

        offer = current_trade_offer
        screen.blit(HEADER_FONT.render(f"{offer['cpu_team'].name} OFFER", True, (120, 255, 140)), (30, 160))
        screen.blit(BODY_FONT.render(f"They offer: {offer['offer_player'].name}", True, (230, 230, 230)), (30, 210))
        screen.blit(BODY_FONT.render(f"They want:  {offer['request_player'].name}", True, (230, 230, 230)), (30, 240))
        screen.blit(BODY_FONT.render(f"Offer value: {player_value(offer['offer_player'])}", True, (230, 230, 230)), (30, 285))
        screen.blit(BODY_FONT.render(f"Your player value: {player_value(offer['request_player'])}", True, (230, 230, 230)), (30, 315))

    else:
        cpu_team = get_tradeable_cpu_team()
        user_players = get_tradeable_user_players()
        cpu_players = get_tradeable_cpu_players()

        if cpu_team is None or not user_players or not cpu_players:
            screen.blit(HEADER_FONT.render("Trade screen unavailable.", True, (230, 230, 230)), (30, 160))
            return

        selected_trade_user_player_clamped = clamp_index(selected_trade_user_player, len(user_players))
        selected_trade_cpu_player_clamped = clamp_index(selected_trade_cpu_player, len(cpu_players))

        screen.blit(HEADER_FONT.render("MAKE TRADE OFFER", True, (120, 255, 140)), (30, 150))
        screen.blit(BODY_FONT.render("A/D = choose CPU team | W/S = your player | UP/DOWN = CPU player", True, (190, 190, 190)), (30, 185))

        screen.blit(HEADER_FONT.render(f"CPU Team: {cpu_team.name}", True, (255, 225, 120)), (30, 235))

        your_player = user_players[selected_trade_user_player_clamped]
        cpu_player = cpu_players[selected_trade_cpu_player_clamped]

        screen.blit(BODY_FONT.render("YOUR PLAYER", True, (180, 210, 255)), (30, 290))
        screen.blit(BODY_FONT.render(f"> {your_player.name}", True, (230, 230, 230)), (30, 320))
        screen.blit(BODY_FONT.render(f"Value: {player_value(your_player)}", True, (230, 230, 230)), (30, 348))

        screen.blit(BODY_FONT.render("CPU PLAYER", True, (180, 210, 255)), (30, 410))
        screen.blit(BODY_FONT.render(f"> {cpu_player.name}", True, (230, 230, 230)), (30, 440))
        screen.blit(BODY_FONT.render(f"Value: {player_value(cpu_player)}", True, (230, 230, 230)), (30, 468))

        delta = player_value(your_player) - player_value(cpu_player)
        screen.blit(BODY_FONT.render(f"Value difference (you - CPU): {delta}", True, (230, 230, 230)), (30, 530))

def draw_awards_screen():
    screen.fill((14,14,30))
    screen.blit(TITLE_FONT.render("SEASON AWARDS", True, (255,225,120)), (30,20))
    screen.blit(BODY_FONT.render("M = menu | N = next season", True, (190,190,190)), (30,70))
    if not current_awards:
        return
    screen.blit(HEADER_FONT.render(f"MVP: {current_awards['mvp'].name}", True, (230,230,230)), (30,150))
    screen.blit(HEADER_FONT.render(f"Cy Young: {current_awards['cy'].name}", True, (230,230,230)), (30,200))
    screen.blit(HEADER_FONT.render(f"Batting Leader: {current_awards['batting'].name}", True, (230,230,230)), (30,250))

def draw_menu():
    screen.fill((16,16,32))
    screen.blit(TITLE_FONT.render("MLB PRO MANAGER", True, (255,225,120)), (60,40))
    screen.blit(HEADER_FONT.render(f"Team: {user_team.name} | Year {season.year}", True, (240,240,240)), (60,100))

    lines = [
        "ENTER = play next day / next playoff round",
        "R = roster management",
        "T = trades",
        "D = game day results",
        "B = box score",
        "S = standings",
        "P = playoff bracket",
        "C = CPU rosters",
        "A = awards",
        "M = menu",
    ]
    y = 170
    for line in lines:
        screen.blit(HEADER_FONT.render(line, True, (225,225,225)), (60, y))
        y += 35

    if not season.regular_season_over():
        season_line = f"Remaining regular season days: {season.remaining_days()}"
    else:
        if season.playoff_round is None:
            season_line = "Regular season complete. Press ENTER to start playoffs."
        elif season.playoff_round == "Finals":
            season_line = "Press ENTER to play the championship."
        elif season.playoff_round == "Complete":
            season_line = f"Champion: {season.champion.name} | Press N for next season."
        else:
            season_line = "Press ENTER to continue playoffs."

    screen.blit(HEADER_FONT.render(season_line, True, (120,255,140)), (60, 540))
    screen.blit(HEADER_FONT.render(status_message, True, (255,210,90)), (60, 585))

# --------------------------------------------------
# flow
# --------------------------------------------------

def refresh_trade_offer():
    global current_trade_offer
    current_trade_offer = cpu_generate_trade_offer(user_team, season.teams[1:])

def play_next_day():
    global status_message, all_games_today, selected_game_index, game_state, current_trade_offer

    if season.regular_season_over():
        status_message = "Regular season complete."
        return

    today_games = season.schedule[season.current_day]
    season.current_day += 1
    all_games_today = []

    for away_team, home_team in today_games:
        result = simulate_game_with_box(away_team, home_team)
        if result["away_score"] > result["home_score"]:
            away_team.wins += 1
            home_team.losses += 1
        else:
            home_team.wins += 1
            away_team.losses += 1

        finalize_team_game(away_team, result["usage"].get(away_team.name, {}))
        finalize_team_game(home_team, result["usage"].get(home_team.name, {}))

        all_games_today.append({
            "title": f"Day {season.current_day} Results",
            "away_team": away_team,
            "home_team": home_team,
            "away_score": result["away_score"],
            "home_score": result["home_score"],
            "away_by_inning": result["away_by_inning"],
            "home_by_inning": result["home_by_inning"],
        })

    selected_game_index = 0
    refresh_trade_offer()
    status_message = f"Day {season.current_day} complete."
    game_state = "game_day"

def play_next_playoff_round():
    global all_games_today, selected_game_index, status_message, game_state, current_awards

    if season.playoff_round is None:
        season.start_playoffs()

    if season.playoff_round == "Complete":
        status_message = f"Champion: {season.champion.name}"
        current_awards = compute_awards(season.teams)
        game_state = "awards"
        return

    all_games_today = season.play_playoff_round()
    selected_game_index = 0

    if season.playoff_round == "Finals":
        status_message = "Semifinals complete. Press ENTER for the championship."
    elif season.playoff_round == "Complete":
        status_message = f"Champion: {season.champion.name}"
        current_awards = compute_awards(season.teams)
        game_state = "awards"
        return
    else:
        status_message = "Playoff round complete."

    game_state = "game_day"

def start_next_season():
    global season, user_team, status_message, all_games_today, current_awards
    run_offseason(
        season.teams,
        free_agent_hitters,
        free_agent_pitchers,
        free_agent_hitting_coaches,
        free_agent_pitching_coaches,
    )
    season.year += 1
    season.schedule = season.build_schedule(season.teams)
    season.current_day = 0
    season.playoff_round = None
    season.playoff_matchups = []
    season.champion = None
    season.awards = None
    user_team = season.user_team
    all_games_today = []
    current_awards = None
    status_message = f"Year {season.year} begins."

# --------------------------------------------------
# main loop
# --------------------------------------------------

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if game_state == "name_input":
                if event.key == pygame.K_RETURN and typed_team_name.strip():
                    season = Season(typed_team_name.strip())
                    user_team = season.user_team
                    free_agent_hitters, free_agent_pitchers = generate_free_agents()
                    free_agent_hitting_coaches, free_agent_pitching_coaches = generate_coach_markets()
                    refresh_trade_offer()
                    game_state = "menu"
                    status_message = "Team created. Welcome to the league."
                elif event.key == pygame.K_BACKSPACE:
                    typed_team_name = typed_team_name[:-1]
                else:
                    if len(typed_team_name) < 18 and event.unicode.isprintable():
                        typed_team_name += event.unicode

            elif game_state == "menu":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_r:
                    game_state = "roster"
                elif event.key == pygame.K_t:
                    game_state = "trades"
                elif event.key == pygame.K_d and all_games_today:
                    game_state = "game_day"
                elif event.key == pygame.K_b and all_games_today:
                    game_state = "box_score"
                elif event.key == pygame.K_s:
                    game_state = "standings"
                elif event.key == pygame.K_p:
                    game_state = "playoffs"
                elif event.key == pygame.K_c:
                    game_state = "cpu_roster"
                elif event.key == pygame.K_a and current_awards:
                    game_state = "awards"
                elif event.key == pygame.K_n and season.playoff_round == "Complete":
                    start_next_season()
                elif event.key == pygame.K_RETURN:
                    if not season.regular_season_over():
                        play_next_day()
                    else:
                        if season.playoff_round != "Complete":
                            play_next_playoff_round()
                        else:
                            current_awards = compute_awards(season.teams)
                            game_state = "awards"

            elif game_state == "game_day":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_UP:
                    selected_game_index = clamp_index(selected_game_index - 1, len(all_games_today))
                elif event.key == pygame.K_DOWN:
                    selected_game_index = clamp_index(selected_game_index + 1, len(all_games_today))
                elif event.key == pygame.K_s and all_games_today:
                    game_state = "box_score"

            elif game_state == "box_score":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_LEFT:
                    selected_game_index = clamp_index(selected_game_index - 1, len(all_games_today))
                elif event.key == pygame.K_RIGHT:
                    selected_game_index = clamp_index(selected_game_index + 1, len(all_games_today))

            elif game_state == "standings":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_c:
                    game_state = "cpu_roster"
                elif event.key == pygame.K_p:
                    game_state = "playoffs"

            elif game_state == "playoffs":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_LEFT:
                    playoff_selected_matchup = max(0, playoff_selected_matchup - 1)
                elif event.key == pygame.K_RIGHT:
                    max_match = 1 if season.playoff_round in (None, "Semifinals") else 2
                    playoff_selected_matchup = min(max_match, playoff_selected_matchup + 1)
                elif event.key == pygame.K_s and all_games_today:
                    if playoff_selected_matchup < len(all_games_today):
                        selected_game_index = playoff_selected_matchup
                        game_state = "box_score"
                elif event.key == pygame.K_RETURN:
                    if season.regular_season_over() and season.playoff_round != "Complete":
                        play_next_playoff_round()

            elif game_state == "cpu_roster":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_LEFT:
                    viewed_team_index = clamp_index(viewed_team_index - 1, len(season.teams[1:]))
                elif event.key == pygame.K_RIGHT:
                    viewed_team_index = clamp_index(viewed_team_index + 1, len(season.teams[1:]))

            elif game_state == "trades":

                if event.key == pygame.K_m:
                    game_state = "menu"

                elif event.key == pygame.K_q:
                    trade_mode = "incoming"

                elif event.key == pygame.K_e:
                    trade_mode = "outgoing"

                elif event.key == pygame.K_t:
                    if trade_mode == "incoming":
                        refresh_trade_offer()

                elif trade_mode == "incoming":
                    if event.key == pygame.K_y and current_trade_offer:
                        cpu = current_trade_offer["cpu_team"]
                        offered = current_trade_offer["offer_player"]
                        requested = current_trade_offer["request_player"]

                        if requested in user_team.bench and offered in cpu.lineup:
                            if evaluate_trade_acceptance(cpu, offered, requested):
                                user_team.bench[user_team.bench.index(requested)] = offered
                                cpu.lineup[cpu.lineup.index(offered)] = requested
                                status_message = "Trade accepted."
                            else:
                                status_message = "CPU changed its mind."
                                current_trade_offer = None

                    elif event.key == pygame.K_n:
                        current_trade_offer = None
                        status_message = "Trade rejected."

                else:
                    cpu_teams = season.teams[1:]
                    user_players = get_tradeable_user_players()
                    cpu_team = get_tradeable_cpu_team()
                    cpu_players = get_tradeable_cpu_players()

                    if event.key == pygame.K_a:
                        selected_trade_cpu_team = clamp_index(selected_trade_cpu_team - 1, len(cpu_teams))
                        selected_trade_cpu_player = 0

                    elif event.key == pygame.K_d:
                        selected_trade_cpu_team = clamp_index(selected_trade_cpu_team + 1, len(cpu_teams))
                        selected_trade_cpu_player = 0

                    elif event.key == pygame.K_w:
                        selected_trade_user_player = clamp_index(selected_trade_user_player - 1, len(user_players))

                    elif event.key == pygame.K_s:
                        selected_trade_user_player = clamp_index(selected_trade_user_player + 1, len(user_players))

                    elif event.key == pygame.K_UP:
                        selected_trade_cpu_player = clamp_index(selected_trade_cpu_player - 1, len(cpu_players))

                    elif event.key == pygame.K_DOWN:
                        selected_trade_cpu_player = clamp_index(selected_trade_cpu_player + 1, len(cpu_players))

                    elif event.key == pygame.K_y:
                        if cpu_team and user_players and cpu_players:
                            user_player = user_players[clamp_index(selected_trade_user_player, len(user_players))]
                            cpu_player = cpu_players[clamp_index(selected_trade_cpu_player, len(cpu_players))]

                            accepted = evaluate_user_trade_offer(cpu_team, cpu_player, user_player)

                            if accepted:
                            # replace on each team
                                if user_player in user_team.lineup:
                                    user_team.lineup[user_team.lineup.index(user_player)] = cpu_player
                                elif user_player in user_team.bench:
                                    user_team.bench[user_team.bench.index(user_player)] = cpu_player

                                if cpu_player in cpu_team.lineup:
                                    cpu_team.lineup[cpu_team.lineup.index(cpu_player)] = user_player
                                elif cpu_player in cpu_team.bench:
                                    cpu_team.bench[cpu_team.bench.index(cpu_player)] = user_player

                                status_message = f"{cpu_team.name} accepted your trade offer."
                            else:
                                status_message = f"{cpu_team.name} rejected your trade offer."

                    elif event.key == pygame.K_n:
                        status_message = "Trade offer canceled."

            elif game_state == "awards":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_n:
                    start_next_season()
                    game_state = "menu"

            elif game_state == "roster":
                if event.key == pygame.K_m:
                    game_state = "menu"
                elif event.key == pygame.K_1:
                    roster_tab = "hitters"
                    roster_focus = "lineup"
                    pending_selection = None
                elif event.key == pygame.K_2:
                    roster_tab = "pitchers"
                    roster_focus = "rotation_roles"
                    pending_selection = None
                elif event.key == pygame.K_3:
                    roster_tab = "coaches"
                    roster_focus = "pitching_coach_slot"
                    pending_selection = None
                elif event.key == pygame.K_4:
                    roster_tab = "stats"
                    roster_focus = "stats_roster"
                    pending_selection = None

                elif roster_tab == "hitters":
                    if event.key == pygame.K_a:
                        roster_focus = "lineup"
                    elif event.key == pygame.K_w:
                        roster_focus = "bench"
                    elif event.key == pygame.K_f:
                        roster_focus = "minors_hitters"
                    elif event.key == pygame.K_g:
                        roster_focus = "fa_hitters"
                    elif event.key == pygame.K_UP:
                        move_selection(-1)
                    elif event.key == pygame.K_DOWN:
                        move_selection(1)
                    elif event.key == pygame.K_s:
                        handle_roster_select()

                elif roster_tab == "pitchers":
                    if event.key == pygame.K_a:
                        roster_focus = "rotation_roles"
                    elif event.key == pygame.K_w:
                        roster_focus = "bullpen"
                    elif event.key == pygame.K_f:
                        roster_focus = "minors_pitchers"
                    elif event.key == pygame.K_g:
                        roster_focus = "fa_pitchers"
                    elif event.key == pygame.K_UP:
                        move_selection(-1)
                    elif event.key == pygame.K_DOWN:
                        move_selection(1)
                    elif event.key == pygame.K_s:
                        handle_roster_select()
                    elif event.key == pygame.K_k:
                        role_list = pitcher_role_list(user_team)
                        idx = selection_index["rotation_roles"]
                        if 0 <= idx < len(role_list) and user_team.pitching_coach:
                            user_team.assign_pitching_coach_to_pitcher(role_list[idx].name)
                            status_message = f"Pitching coach assigned to {role_list[idx].name}"

                elif roster_tab == "coaches":
                    if event.key == pygame.K_a:
                        roster_focus = "pitching_coach_slot"
                    elif event.key == pygame.K_w:
                        roster_focus = "pitching_coach_market"
                    elif event.key == pygame.K_f:
                        roster_focus = "hitting_coach_slot"
                    elif event.key == pygame.K_g:
                        roster_focus = "hitting_coach_market"
                    elif event.key == pygame.K_UP:
                        move_selection(-1)
                    elif event.key == pygame.K_DOWN:
                        move_selection(1)
                    elif event.key == pygame.K_s:
                        handle_roster_select()

                elif roster_tab == "stats":
                    if event.key == pygame.K_UP:
                        move_selection(-1)
                    elif event.key == pygame.K_DOWN:
                        move_selection(1)

    if game_state == "name_input":
        draw_name_input()
    elif game_state == "menu":
        draw_menu()
    elif game_state == "game_day":
        draw_game_day()
    elif game_state == "box_score":
        draw_box_score()
    elif game_state == "standings":
        draw_standings()
    elif game_state == "playoffs":
        draw_playoff_bracket()
    elif game_state == "cpu_roster":
        draw_cpu_roster()
    elif game_state == "roster":
        draw_user_roster()
    elif game_state == "trades":
        draw_trade_screen()
    elif game_state == "awards":
        draw_awards_screen()

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()