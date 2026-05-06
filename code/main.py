import copy
import random
import pygame

import os

ASSETS_DIR = "assets"
SPRITE_DIR = os.path.join(ASSETS_DIR, "game art")
from settings import WIDTH, HEIGHT, FPS
from season import Season
from team import REQUIRED_LINEUP_POSITIONS
from player_gen_with_superstars_bust import gen_pitcher, assign_salary_pitcher, MAX_CONTRACT_GAMES
from league import (
    generate_free_agents,
    generate_coach_markets,
    cpu_generate_trade_offer,
    evaluate_trade_acceptance,
    evaluate_user_trade_offer,
    compute_awards,
    run_offseason,
    player_value,
    fill_cpu_rosters_from_market,
    push_cpu_team_toward_budget,
)
from franchise_culture import (
    apply_random_morale_streaks,
    culture_profile,
    decrement_streaks,
    ensure_franchise_culture_state,
    franchise_revenue_bonus,
    player_streak_tag,
    recalc_morale,
    refresh_budget_from_culture,
    sync_team_streak_display,
)

from minor_league_farm import (
    ensure_farm_state,
    advance_farm_system,
    farm_players,
    hire_farm_coach,
    rename_farm,
)

from game_sim import simulate_half_inning
from lineup import build_lineup_plan, apply_lineup_plan
from contracts import NegotiationState, attempt_negotiation, scan_contract_events, expected_salary
from news import NewsFeed, build_contract_news, generate_cpu_news
from game_sim import simulate_half_inning, simulate_half_inning_detailed
from save_system import save_game_state, load_game_state, has_save_file
from scouting import (
    SCOUT_STAR_COSTS,
    hire_scout,
    fire_scout,
    advance_scouting,
    sign_scouted_prospect,
)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("MLB Pro Manager")
clock = pygame.time.Clock()

TITLE_FONT = pygame.font.SysFont("courier", 34, bold=True)
HEADER_FONT = pygame.font.SysFont("courier", 24, bold=True)
BODY_FONT = pygame.font.SysFont("courier", 16, bold=True)
SMALL_FONT = pygame.font.SysFont("courier", 14, bold=True)
TINY_FONT = pygame.font.SysFont("courier", 12, bold=True)


try:
    raw_logo = pygame.image.load("new_logo.png").convert_alpha()
    LOGO_SURF = pygame.transform.smoothscale(raw_logo, (520, 520))
except Exception:
    LOGO_SURF = None

try:
    WORLD_SERIES_CHAMPIONS_SURF = pygame.image.load("world_series_champions.png").convert_alpha()
except Exception:
    WORLD_SERIES_CHAMPIONS_SURF = None


def get_player_name(player):
    return getattr(player, "character_name", getattr(player, "name", "Unknown"))


def fmt_stat(v):
    return f".{int(v):03d}" if isinstance(v, int) else str(v)


def fmt_money(n):
    return "${:,.0f}".format(n)


def fmt_money_short(n):
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"${n/1_000:.0f}K"
    return f"${n}"


def short_name(name, n=14):
    return name[:n]


def clamp_index(value, size):
    if size <= 0:
        return 0
    return max(0, min(value, size - 1))


def is_empty_slot(player):
    return getattr(player, "name", "") == "EMPTY SLOT"


def draw_text(text, x, y, color=(230, 230, 230), font=BODY_FONT):
    screen.blit(font.render(text, True, color), (x, y))

def draw_detailed_half_inning(x, y, title, half_log, batting_team_name, fielding_team_name):
    draw_box_frame(f"{title} - {batting_team_name} batting", x, y, 560, 300, False)
    draw_text(
        f"Pitcher: {half_log['pitcher']}   Runs: {half_log['runs']}   Hits: {half_log['hits']}",
        x + 14, y + 38, (180, 210, 255), SMALL_FONT
    )

    row_y = y + 66
    for play in half_log["plays"][:8]:
        line = (
            f"{play['outs_before']} out | "
            f"{bases_text(play['bases_before']):8} | "
            f"{short_name(play['hitter'], 12):12} | "
            f"{play['outcome_text']}"
        )
        if play["runs_scored"] > 0:
            line += f" (+{play['runs_scored']} R)"
        draw_text(line, x + 14, row_y, (230, 230, 230), TINY_FONT)
        row_y += 24

def save_current_game(filename="autosave.pkl"):
    global status_message
    try:
        save_game_state(build_save_state(), filename)
        status_message = "Game saved."
    except Exception as e:
        status_message = f"Save failed: {e}"


def load_saved_game(filename="autosave.pkl"):
    global status_message
    try:
        state = load_game_state(filename)
        apply_loaded_state(state)
        status_message = "Save loaded."
    except FileNotFoundError:
        status_message = "No save file found."
    except Exception as e:
        status_message = f"Load failed: {e}"

def refill_coach_markets(target_size=8):
    global free_agent_hitting_coaches, free_agent_pitching_coaches

    new_hitting, new_pitching = generate_coach_markets()

    while len(free_agent_hitting_coaches) < target_size and new_hitting:
        free_agent_hitting_coaches.append(new_hitting.pop(0))

    while len(free_agent_pitching_coaches) < target_size and new_pitching:
        free_agent_pitching_coaches.append(new_pitching.pop(0))

def load_sprite(filename):
    try:
        return pygame.image.load(os.path.join(SPRITE_DIR, filename)).convert_alpha()
    except Exception:
        return None

def scale_sprite(sprite, size):
    if sprite is None:
        return None
    return pygame.transform.scale(sprite, size)

SPIN_LAB_BG = scale_sprite(load_sprite("spin_lab_bg.png"), (WIDTH, HEIGHT))
SPIN_BALL_1 = scale_sprite(load_sprite("spin_ball_1.png"), (192, 192))
SPIN_BALL_2 = scale_sprite(load_sprite("spin_ball_2.png"), (192, 192))
SPIN_BALL_3 = scale_sprite(load_sprite("spin_ball_3.png"), (192, 192))
SPIN_BALL_4 = scale_sprite(load_sprite("spin_ball_4.png"), (192, 192))

SPIN_BALL_FRAMES = [frame for frame in [SPIN_BALL_1, SPIN_BALL_2, SPIN_BALL_3, SPIN_BALL_4] if frame]

def draw_box_frame(title, x, y, w, h, focused=False):
    pygame.draw.rect(screen, (18, 25, 45), (x, y, w, h), border_radius=6)
    border = (255, 225, 120) if focused else (120, 145, 170)
    pygame.draw.rect(screen, border, (x, y, w, h), 2, border_radius=6)
    draw_text(title, x + 10, y + 8, border, HEADER_FONT)

def draw_panel(x, y, w, h, title=None, accent=(80, 180, 255), fill=(10, 18, 34), focused=False):
    pygame.draw.rect(screen, fill, (x, y, w, h), border_radius=12)
    border = (255, 225, 120) if focused else accent
    pygame.draw.rect(screen, border, (x, y, w, h), 3, border_radius=12)
    if title:
        draw_text(title, x + 16, y + 10, border, HEADER_FONT)

def draw_progress_bar(x, y, w, h, value, max_value, fill_color=(90, 220, 140), back_color=(35, 50, 70)):
    pygame.draw.rect(screen, back_color, (x, y, w, h), border_radius=8)
    if max_value > 0:
        inner_w = int((value / max_value) * w)
        pygame.draw.rect(screen, fill_color, (x, y, inner_w, h), border_radius=8)
    pygame.draw.rect(screen, (180, 200, 220), (x, y, w, h), 2, border_radius=8)

def current_spin_ball_frame():
    if not SPIN_BALL_FRAMES:
        return None
    tick = (pygame.time.get_ticks() // 120) % len(SPIN_BALL_FRAMES)
    return SPIN_BALL_FRAMES[tick]

def build_save_state():
    return {
        "season": season,
        "user_team": user_team,
        "game_state": game_state,
        "typed_team_name": typed_team_name,
        "status_message": status_message,
        "all_games_today": all_games_today,
        "selected_game_index": selected_game_index,
        "box_inning_index": box_inning_index,
        "viewed_team_index": viewed_team_index,
        "trade_mode": trade_mode,
        "selected_trade_cpu_team": selected_trade_cpu_team,
        "selected_trade_user_player": selected_trade_user_player,
        "selected_trade_cpu_player": selected_trade_cpu_player,
        "roster_tab": roster_tab,
        "roster_focus": roster_focus,
        "roster_pitcher_focus": roster_pitcher_focus,
        "pending_selection": pending_selection,
        "current_trade_offer": current_trade_offer,
        "current_awards": current_awards,
        "scouting_selection": scouting_selection,
        "scouting_focus": scouting_focus,
        "free_agent_hitters": free_agent_hitters,
        "free_agent_pitchers": free_agent_pitchers,
        "free_agent_hitting_coaches": free_agent_hitting_coaches,
        "free_agent_pitching_coaches": free_agent_pitching_coaches,
        "franchise_history": franchise_history,
        "selection_index": selection_index,
        "player_detail": player_detail,
        "lineup_plan": lineup_plan,
        "lineup_focus": lineup_focus,
        "lineup_pending": lineup_pending,
        "free_agent_tab": free_agent_tab,
        "free_agent_confirm": free_agent_confirm,
        "pending_confirmation": pending_confirmation,
        "negotiation_queue": negotiation_queue,
        "active_negotiation": active_negotiation,
        "playoff_selected_matchup": playoff_selected_matchup,
        "news_feed": news_feed,
        "all_star_preview": all_star_preview,
        "contract_check_day": contract_check_day,
        "stats_year_index": stats_year_index,
        "playoff_round_state": playoff_round_state,
    }


def apply_loaded_state(state):
    global season, user_team, game_state, typed_team_name, status_message
    global all_games_today, selected_game_index, box_inning_index, viewed_team_index
    global trade_mode, selected_trade_cpu_team, selected_trade_user_player, selected_trade_cpu_player
    global roster_tab, roster_focus, roster_pitcher_focus, pending_selection, current_trade_offer
    global current_awards, free_agent_hitters, free_agent_pitchers
    global free_agent_hitting_coaches, free_agent_pitching_coaches
    global franchise_history, selection_index, player_detail
    global lineup_plan, lineup_focus, lineup_pending
    global scouting_selection, scouting_focus
    global free_agent_tab, free_agent_confirm, pending_confirmation
    global negotiation_queue, active_negotiation, playoff_selected_matchup, news_feed
    global all_star_preview, contract_check_day, stats_year_index, playoff_round_state
    global farm_name_editing, farm_name_text, status_message, game_state

    season = state["season"]
    user_team = state["user_team"]
    game_state = state["game_state"]
    typed_team_name = state["typed_team_name"]
    status_message = state["status_message"]
    all_games_today = state["all_games_today"]
    selected_game_index = state["selected_game_index"]
    box_inning_index = state["box_inning_index"]
    viewed_team_index = state["viewed_team_index"]
    trade_mode = state["trade_mode"]
    selected_trade_cpu_team = state["selected_trade_cpu_team"]
    selected_trade_user_player = state["selected_trade_user_player"]
    selected_trade_cpu_player = state["selected_trade_cpu_player"]
    roster_tab = state["roster_tab"]
    roster_focus = state["roster_focus"]
    roster_pitcher_focus = state["roster_pitcher_focus"]
    pending_selection = state["pending_selection"]
    current_trade_offer = state["current_trade_offer"]
    current_awards = state["current_awards"]
    free_agent_hitters = state["free_agent_hitters"]
    free_agent_pitchers = state["free_agent_pitchers"]
    free_agent_hitting_coaches = state["free_agent_hitting_coaches"]
    free_agent_pitching_coaches = state["free_agent_pitching_coaches"]
    franchise_history = state["franchise_history"]
    selection_index = state["selection_index"]
    selection_index.setdefault("culture_controls", 0)
    ensure_franchise_culture_state(user_team)
    recalc_morale(user_team)
    refresh_budget_from_culture(user_team, base_budget=165_000_000)
    sync_team_streak_display(user_team)
    selection_index.setdefault("scouting_market", 0)
    selection_index.setdefault("scouting_reports", 0)
    player_detail = state["player_detail"]
    lineup_plan = state["lineup_plan"]
    lineup_focus = state["lineup_focus"]
    lineup_pending = state["lineup_pending"]
    free_agent_tab = state["free_agent_tab"]
    free_agent_confirm = state["free_agent_confirm"]
    pending_confirmation = state["pending_confirmation"]
    negotiation_queue = state["negotiation_queue"]
    active_negotiation = state["active_negotiation"]
    playoff_selected_matchup = state["playoff_selected_matchup"]
    news_feed = state["news_feed"]
    scouting_selection = state.get("scouting_selection", 0)
    scouting_focus = state.get("scouting_focus", "market")
    all_star_preview = state.get("all_star_preview")
    contract_check_day = state.get("contract_check_day", -1)
    stats_year_index = state.get("stats_year_index", 0)
    playoff_round_state = state.get("playoff_round_state")
    for idx, tm in enumerate(getattr(season, "teams", [])):
        tm.budget = 165_000_000 if idx == 0 else 200_000_000

def draw_budget_top_right(team):
    text = f"Budget: {fmt_money_short(team.total_salary())} / {fmt_money_short(team.budget)}"
    surf = HEADER_FONT.render(text, True, (255, 225, 120))
    screen.blit(surf, (WIDTH - surf.get_width() - 24, 24))


def player_avg_text(h):
    if not h or is_empty_slot(h):
        return "---"
    return fmt_stat(getattr(h, "display_average", getattr(h, "average", 0)))


def player_obp_text(h):
    if not h or is_empty_slot(h):
        return "---"
    return fmt_stat(getattr(h, "display_obp", getattr(h, "obp", 0)))


def player_slg_text(h):
    if not h or is_empty_slot(h):
        return "---"
    return fmt_stat(getattr(h, "display_slugging", getattr(h, "slugging", 0)))


def player_season_avg_text(h):
    return h.avg_text if hasattr(h, "avg_text") else player_avg_text(h)


def player_season_obp_text(h):
    return h.obp_text if hasattr(h, "obp_text") else player_obp_text(h)


def player_season_slg_text(h):
    return h.slg_text if hasattr(h, "slg_text") else player_slg_text(h)


def season_avg(player):
    ab = getattr(player, "ab", 0)
    return (getattr(player, "hits", 0) / ab) if ab > 0 else 0.0

def draw_minor_league_farm_page():
    ensure_farm_state(user_team)

    screen.fill((8, 18, 44))
    draw_text("MINOR LEAGUE FARM SYSTEM", 60, 36, (255, 225, 120), TITLE_FONT)

    farm = user_team.minor_league_farm
    coach = farm.coach

    draw_text(f"Affiliate: {farm.team_name}", 60, 90, (240, 240, 240), HEADER_FONT)
    if farm_name_editing:
        draw_text(f"Typing new name: {farm_name_text}_", 60, HEIGHT - 70, (255, 225, 120))
        draw_text("ENTER = save | ESC = cancel", 60, HEIGHT - 44, (210, 210, 210))
    else:
        draw_text("N = rename farm | 1-6 = hire coach | M = menu", 60, HEIGHT - 44, (210, 210, 210))

    if coach:
        draw_text(
            f"Farm Coach: {coach.name} | {coach.summary()} | Salary {fmt_money_short(coach.salary)}",
            60, 130,
            (180, 220, 255),
            SMALL_FONT
        )
    else:
        draw_text("Farm Coach: None hired", 60, 130, (220, 180, 180), SMALL_FONT)

    draw_text("COACH MARKET - Press 1-6 to hire", 60, 175, (255, 225, 120), HEADER_FONT)
    draw_text("DEVELOPMENT LOG", 720, 175, (255, 225, 120), HEADER_FONT)

    log_y = 215
    for msg in user_team.minor_league_farm.development_log[:6]:
        draw_text(msg, 720, log_y, (180, 240, 180), TINY_FONT)
        log_y += 24
    y = 215
    for i, c in enumerate(user_team.farm_coach_market[:6]):
        draw_text(
            f"{i + 1}. {c.name:<18} {c.summary():<42} {fmt_money_short(c.salary)}",
            80,
            y,
            (235, 235, 235),
            SMALL_FONT
        )
        y += 26

    draw_text("HITTERS", 60, 385, (255, 225, 120), HEADER_FONT)
    y = 420
    for p in user_team.minors_hitters[:6]:
        if is_empty_slot(p):
            continue
        draw_text(
            f"{p.name:<18} {getattr(p, 'position', '---'):<3} AVG {player_avg_text(p)} OBP {player_obp_text(p)} SLG {player_slg_text(p)} Contract {getattr(p, 'contract_games_remaining', 0)}G",
            80,
            y,
            (235, 235, 235),
            SMALL_FONT
        )
        y += 40
    draw_text(
    f"Bonuses: AVG +{getattr(p, 'coach_avg_bonus', 0)} "
    f"OBP +{getattr(p, 'coach_obp_bonus', 0)} "
    f"OPS +{getattr(p, 'coach_ops_bonus', 0)} "
    f"Prog {getattr(p, 'farm_progress_games', 0)}",
    100,
    y + 16,
    (140, 220, 140),
    TINY_FONT
)
    draw_text("PITCHERS", 60, 590, (255, 225, 120), HEADER_FONT)
    y = 625
    for p in user_team.minors_pitchers[:4]:
        if is_empty_slot(p):
            continue
        draw_text(
            f"{p.name:<18} {getattr(p, 'role', '--'):<3} {pitcher_minus_slash_text(p)} Contract {getattr(p, 'contract_games_remaining', 0)}G",
            80,
            y,
            (235, 235, 235),
            SMALL_FONT
        )
        y += 40
        draw_text(
    f"Bonuses: AVG- +{getattr(p, 'coach_avg_bonus', 0)} "
    f"OBP- +{getattr(p, 'coach_obp_bonus', 0)} "
    f"SLG- +{getattr(p, 'coach_slg_bonus', 0)} "
    f"Prog {getattr(p, 'farm_progress_games', 0)}",
    100,
    y + 16,
    (140, 220, 140),
    TINY_FONT
)

    draw_text("M = menu", 60, HEIGHT - 44, (210, 210, 210))

def season_obp(player):
    ab = getattr(player, "ab", 0)
    walks = getattr(player, "walks", 0)
    hbp = getattr(player, "hbp", 0)
    denom = ab + walks + hbp
    return ((getattr(player, "hits", 0) + walks + hbp) / denom) if denom > 0 else 0.0


def season_slg(player):
    ab = getattr(player, "ab", 0)
    if ab <= 0:
        return 0.0
    total_bases = (
        getattr(player, "singles", 0)
        + 2 * getattr(player, "doubles", 0)
        + 3 * getattr(player, "triples", 0)
        + 4 * getattr(player, "homeruns", 0)
    )
    return total_bases / ab


def season_whip(player):
    innings = getattr(player, "outs_recorded", 0) / 3.0
    if innings <= 0:
        return 0.0
    return (getattr(player, "walks", 0) + getattr(player, "hits_allowed", 0)) / innings


def snapshot_award_player(player):
    if player is None:
        return None
    if hasattr(player, "average_minus"):
        return {
            "name": player.name,
            "era": float(getattr(player, "era", 0.0)),
            "whip": float(season_whip(player)),
            "strikeouts": int(getattr(player, "strikeouts", 0)),
            "innings_pitched_text": getattr(player, "innings_pitched_text", "0.0"),
        }
    return {
        "name": player.name,
        "avg": float(season_avg(player)),
        "obp": float(season_obp(player)),
        "slg": float(season_slg(player)),
        "homeruns": int(getattr(player, "homeruns", 0)),
        "rbi": int(getattr(player, "rbi", 0)),
    }


def snapshot_awards(awards):
    if not awards:
        return awards
    return {key: snapshot_award_player(value) for key, value in awards.items()}


def award_name(player):
    return player.get("name", "Unknown") if isinstance(player, dict) else getattr(player, "name", "Unknown")


def award_pitcher_era(player):
    return player.get("era", 0.0) if isinstance(player, dict) else getattr(player, "era", 0.0)


def award_pitcher_whip(player):
    return player.get("whip", 0.0) if isinstance(player, dict) else season_whip(player)


def award_pitcher_strikeouts(player):
    return player.get("strikeouts", 0) if isinstance(player, dict) else getattr(player, "strikeouts", 0)


def award_pitcher_ip_text(player):
    return player.get("innings_pitched_text", "0.0") if isinstance(player, dict) else getattr(player, "innings_pitched_text", "0.0")


def award_hitter_avg(player):
    return player.get("avg", 0.0) if isinstance(player, dict) else season_avg(player)


def award_hitter_obp(player):
    return player.get("obp", 0.0) if isinstance(player, dict) else season_obp(player)


def award_hitter_slg(player):
    return player.get("slg", 0.0) if isinstance(player, dict) else season_slg(player)


def award_hitter_hr(player):
    return player.get("homeruns", 0) if isinstance(player, dict) else getattr(player, "homeruns", 0)


def award_hitter_rbi(player):
    return player.get("rbi", 0) if isinstance(player, dict) else getattr(player, "rbi", 0)


def next_opponent_text():
    if playoff_round_state and playoff_round_state.get("current_series"):
        series = playoff_round_state["current_series"]
        away = series["away_team"]
        home = series["home_team"]
        return f"Playoff Opponent: {'at ' + home.name if away == user_team else 'vs ' + away.name}"
    if not season or season.regular_season_over():
        return "No regular-season opponent scheduled."
    for away, home in season.schedule[season.current_day]:
        if away == user_team:
            return f"Next Opponent: at {home.name}"
        if home == user_team:
            return f"Next Opponent: vs {away.name}"
    return "Next Opponent: Off day"


def pitcher_minus_slash_text(pitcher):
    if not pitcher or is_empty_slot(pitcher):
        return "---/---/---/ ERA:---"
    return f"{pitcher.display_average_minus:02d}/{pitcher.display_obp_minus:02d}/{pitcher.display_slugging_minus:02d}/ ERA:{pitcher.era:.1f}"


def run_pregame_contract_check():
    global contract_check_day
    if not season or season.regular_season_over():
        return False
    if contract_check_day == season.current_day:
        return active_negotiation is not None
    contract_check_day = season.current_day
    user_team.ensure_within_budget()
    refresh_news()
    check_user_contracts()
    return active_negotiation is not None


def build_all_star_preview():
    pools = {
        "West & South": [t for t in season.teams if t.division in {"West", "South"}],
        "North & Pacific": [t for t in season.teams if t.division in {"North", "Pacific"}],
    }

    def hitter_score(h):
        return (season_obp(h) * 1000.0) + (season_slg(h) * 900.0) + getattr(h, "homeruns", 0) * 8 + getattr(h, "rbi", 0) * 2

    def pitcher_score(p):
        innings = getattr(p, "outs_recorded", 0) / 3.0
        if innings <= 0:
            return -9999
        return 100.0 - getattr(p, "era", 99.0) * 10.0 + innings + getattr(p, "strikeouts", 0) * 0.5

    preview = {}
    for label, teams_in_pool in pools.items():
        hitters = []
        pitchers = []
        for tm in teams_in_pool:
            hitters.extend([(h, tm) for h in (tm.lineup + tm.bench) if not is_empty_slot(h) and hasattr(h, "ops")])
            pitchers.extend([(p, tm) for p in (tm.rotation + tm.bullpen) if not is_empty_slot(p) and hasattr(p, "average_minus")])
        hitters.sort(key=lambda item: hitter_score(item[0]), reverse=True)
        pitchers.sort(key=lambda item: pitcher_score(item[0]), reverse=True)
        preview[label] = {"hitters": hitters[:9], "pitchers": pitchers[:3]}
    return preview


class ExhibitionTeam:
    def __init__(self, name, hitters, pitchers):
        self.name = name
        self.lineup = [h for h, _tm in hitters][:9]
        self.batting_order = self.lineup[:]
        self.bench = []
        real_pitchers = [p for p, _tm in pitchers]
        self.rotation = real_pitchers[:1]
        self.bullpen = real_pitchers[1:]
        self.starter = self.rotation[0] if self.rotation else None
        self.middle_reliever = self.bullpen[0] if self.bullpen else self.starter
        self.closer = self.bullpen[1] if len(self.bullpen) > 1 else self.middle_reliever

    def ensure_batting_order(self):
        self.batting_order = self.lineup[:]

    def get_active_lineup_for_game(self):
        self.ensure_batting_order()
        return self.batting_order[:]


def play_all_star_game():
    global all_games_today, selected_game_index, game_state, status_message

    season.all_star_played = True
    all_games_today = []
    selected_game_index = 0
    status_message = "All-Star break complete."
    game_state = "menu"
    save_current_game()


# --------------------------------------------------
# simulation wrappers
# --------------------------------------------------

def apply_pitching_coach(team, pitcher):
    if pitcher is None:
        return None

    coach = team.pitching_coach
    if coach is None or team.pitching_assignment_name != pitcher.name:
        return pitcher

    boosted = copy.copy(pitcher)
    boosted._stat_target = pitcher
    boosted.average_minus = pitcher.display_average_minus
    boosted.obp_minus = pitcher.display_obp_minus
    boosted.slugging_minus = pitcher.display_slugging_minus
    boosted.bb_plus = max(0, pitcher.bb_plus - max(1, coach.obp_boost // 2))
    boosted.hbp_plus = max(0, pitcher.hbp_plus - max(0, coach.avg_boost // 3))
    return boosted

def get_pitcher_for_inning(team, inning, lineup_plan=None):
    if lineup_plan:
        starter_name = lineup_plan.starter_name
        relievers = lineup_plan.reliever_names
    else:
        starter_name = team.starter.name if team.starter else ""
        relievers = [p.name for p in [team.middle_reliever, team.closer] if p]

    all_pitchers = [p for p in (team.rotation + team.bullpen) if not is_empty_slot(p)]
    by_name = {p.name: p for p in all_pitchers}

    if inning <= 5:
        preferred = by_name.get(starter_name, team.starter)
    elif inning <= 7:
        preferred = by_name.get(relievers[0], team.middle_reliever) if relievers else team.middle_reliever
    else:
        preferred = by_name.get(relievers[1], team.closer) if len(relievers) > 1 else (team.closer or team.middle_reliever)

    eligible = [p for p in all_pitchers if getattr(p, "remaining_stamina", 0) > 0]
    if preferred and getattr(preferred, "remaining_stamina", 0) > 0:
        p = preferred
    elif eligible:
        role_match = [cand for cand in eligible if getattr(cand, "role", None) == getattr(preferred, "role", None)] if preferred else []
        p = max(role_match or eligible, key=lambda cand: (cand.remaining_stamina, cand.display_average_minus + cand.display_obp_minus + cand.display_slugging_minus))
    else:
        p = max(all_pitchers, key=lambda cand: getattr(cand, "remaining_stamina", 0), default=preferred)
    return apply_pitching_coach(team, p)


def simulate_game_with_box(away_team, home_team):
    ensure_cpu_team_can_play(away_team)
    ensure_cpu_team_can_play(home_team)

    away_score = 0
    home_score = 0
    away_idx = 0
    home_idx = 0
    away_by_inning = []
    home_by_inning = []
    inning_logs = []

    away_lineup = away_team.get_active_lineup_for_game()
    home_lineup = home_team.get_active_lineup_for_game()
    away_plan = build_lineup_plan(away_team)
    home_plan = build_lineup_plan(home_team)

    usage = {away_team.name: {}, home_team.name: {}}

    inning = 1
    while True:
        home_pitcher = get_pitcher_for_inning(home_team, inning, home_plan)
        away_pitcher = get_pitcher_for_inning(away_team, inning, away_plan)

        if home_pitcher is None:
            ensure_cpu_team_can_play(home_team)
            home_lineup = home_team.get_active_lineup_for_game()
            home_plan = build_lineup_plan(home_team)
            home_pitcher = get_pitcher_for_inning(home_team, inning, home_plan)

        if away_pitcher is None:
            ensure_cpu_team_can_play(away_team)
            away_lineup = away_team.get_active_lineup_for_game()
            away_plan = build_lineup_plan(away_team)
            away_pitcher = get_pitcher_for_inning(away_team, inning, away_plan)

        if home_pitcher is None or away_pitcher is None:
            status_message = f"Emergency roster fill failed for {away_team.name if away_pitcher is None else home_team.name}."
            return {
                "away_score": 0,
                "home_score": 0,
                "away_by_inning": [],
                "home_by_inning": [],
                "usage": usage,
                "inning_logs": [],
            }

        usage[home_team.name][home_pitcher.name] = usage[home_team.name].get(home_pitcher.name, 0) + 1
        usage[away_team.name][away_pitcher.name] = usage[away_team.name].get(away_pitcher.name, 0) + 1

        top = simulate_half_inning_detailed(away_lineup, home_pitcher, away_idx)
        away_idx = top["next_idx"]
        away_score += top["runs"]
        away_by_inning.append(top["runs"])

        bottom = simulate_half_inning_detailed(home_lineup, away_pitcher, home_idx)
        home_idx = bottom["next_idx"]
        home_score += bottom["runs"]
        home_by_inning.append(bottom["runs"])

        inning_logs.append({
            "inning": inning,
            "top": top,
            "bottom": bottom,
        })

        if inning >= 9 and away_score != home_score:
            break
        inning += 1

    return {
        "away_score": away_score,
        "home_score": home_score,
        "away_by_inning": away_by_inning,
        "home_by_inning": home_by_inning,
        "usage": usage,
        "inning_logs": inning_logs,
    }
def finalize_team_game(team, usage_map):
    global status_message
    if team is user_team:
        ensure_farm_state(team)
        advance_farm_system(team)
    used_names = set(name for name in usage_map if name)
    team.apply_coaching_progress()

    team.apply_spin_rate_lab_progress(games_per_boost=5)
    ensure_franchise_culture_state(team)
    decrement_streaks(team, 1)
    recalc_morale(team)

    if team is user_team:
        refresh_budget_from_culture(team, base_budget=165_000_000)

    streak_event = apply_random_morale_streaks(team)
    sync_team_streak_display(team)

    if team is user_team and streak_event:
        streak_type, names = streak_event
        if streak_type == "hot":
            status_message = f"Clubhouse hot streak: {', '.join(names[:3])} heating up."
        else:
            status_message = f"Cold streak: {', '.join(names[:3])} have cooled off."
    # NEW: scouting progression
    if hasattr(team, "ensure_scouting_state"):
        team.ensure_scouting_state()
        new_reports = advance_scouting(team, games=1)
        if team is user_team and new_reports:
            first = new_reports[0]
            status_message = f"Scouting report: {first.player.name} found in the {first.source_name}."

    team.apply_postgame_fatigue(usage_map)
    team.recover_pitcher_fatigue(used_names)
    team.decrement_injuries(1)

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
# global state
# --------------------------------------------------

game_state = "title_screen"
title_screen_selection = 0
typed_team_name = ""
scouting_selection = 0
scouting_focus = "market"   # "market" or "reports"
season = None
user_team = None
news_feed = NewsFeed()
minor_callup_contract = None
minor_contract_days = 40
minor_contract_salary = 750_000
status_message = "Welcome to MLB Pro Manager"
all_games_today = []
farm_name_editing = False
farm_name_text = ""
selected_game_index = 0
box_inning_index = 0
viewed_team_index = 0
trade_mode = "incoming"
reveal_inning_index = 0
last_playoff_game = None
media_stories = []
selected_trade_cpu_team = 0
selected_trade_user_player = 0
selected_trade_cpu_player = 0
roster_tab = "hitters"
roster_focus = "lineup"
pending_selection = None
current_trade_offer = None
current_awards = None
free_agent_hitters = []
free_agent_pitchers = []
culture_focus = 0   
franchise_history = []
free_agent_hitting_coaches = []
free_agent_pitching_coaches = []
selection_index = {
    "lineup": 0,
    "bench": 0,
    "minors_hitters": 0,
    "rotation_roles": 0,
    "bullpen": 0,
    "minors_pitchers": 0,
    "pitcher_rotation": 0,
    "pitcher_bullpen": 0,
    "pitcher_minors": 0,
    "pitching_coach_slot": 0,
    "pitching_coach_market": 0,
    "hitting_coach_slot": 0,
    "hitting_coach_market": 0,
    "stats_roster": 0,
    "scouting_market": 0,
    "scouting_reports": 0,
    "culture_controls": 0,
    "free_agent_hitters": 0,
    "free_agent_pitchers": 0,
    "lineup_hitters": 0,
    "lineup_pitchers": 0,
    "menu_news": 0,
    "spin_lab_pool": 0,
}
player_detail = None
lineup_plan = None
lineup_focus = "batting_order"
roster_pitcher_focus = "rotation"
lineup_pending = None
free_agent_tab = "hitters"
free_agent_confirm = None
pending_confirmation = None
negotiation_queue = []
active_negotiation = None
playoff_selected_matchup = 0
all_star_preview = None
contract_check_day = -1
stats_year_index = 0
playoff_round_state = None


# --------------------------------------------------
# helpers
# --------------------------------------------------

def start_minor_callup_contract(player, player_type, minor_index):
    global minor_callup_contract, minor_contract_days, minor_contract_salary, game_state

    minor_callup_contract = {
        "player": player,
        "player_type": player_type,
        "minor_index": minor_index,
    }

    minor_contract_days = 40
    minor_contract_salary = 750_000
    game_state = "minor_callup_contract"

def hitter_lists():
    return {
        "lineup": user_team.lineup,
        "bench": user_team.bench,
        "minors_hitters": user_team.minors_hitters,
    }


def pitcher_role_list(team):
    return team.rotation[:5] + [team.middle_reliever, team.closer]


def pitcher_lists():
    return {
        "rotation": user_team.rotation,
        "bullpen": user_team.bullpen,
        "minors": user_team.minors_pitchers,
    }
INJURY_TYPES = [
    "pulled groin",
    "hamstring strain",
    "sprained ankle",
    "wrist soreness",
    "back tightness",
    "shoulder inflammation",
    "elbow soreness",
    "knee bruise",
    "oblique strain",
    "quad strain",
]

def player_injury_text(player):
    games_left = getattr(player, "injured_games_remaining", 0)
    if games_left <= 0:
        return ""

    injury_name = getattr(player, "injury_name", "")
    if not injury_name:
        injury_name = "pulled groin"

    game_word = "game" if games_left == 1 else "games"
    return f"{player.name} out {games_left} {game_word} - {injury_name}"

def coach_lists():
    return {
        "pitching_coach_slot": [user_team.pitching_coach] if user_team.pitching_coach else [],
        "pitching_coach_market": free_agent_pitching_coaches,
        "hitting_coach_slot": user_team.hitting_coaches,
        "hitting_coach_market": free_agent_hitting_coaches,
    }


def get_tradeable_user_players():
    return [p for p in (user_team.lineup + user_team.bench + user_team.rotation + user_team.bullpen) if not is_empty_slot(p)]


def get_tradeable_cpu_team():
    cpu_teams = season.teams[1:]
    if not cpu_teams:
        return None
    return cpu_teams[selected_trade_cpu_team]


def get_tradeable_cpu_players():
    cpu_team = get_tradeable_cpu_team()
    if cpu_team is None:
        return []
    return [p for p in (cpu_team.lineup + cpu_team.bench + cpu_team.rotation + cpu_team.bullpen) if not is_empty_slot(p)]


def move_selection(delta):
    if roster_tab == "hitters":
        size = len(hitter_lists()[roster_focus])
        selection_index[roster_focus] = clamp_index(selection_index[roster_focus] + delta, size)
    elif roster_tab == "pitchers":
        key_map = {
            "rotation": "pitcher_rotation",
            "bullpen": "pitcher_bullpen",
            "minors": "pitcher_minors",
        }
        focus = roster_pitcher_focus
        size = len(pitcher_lists()[focus])
        selection_index[key_map[focus]] = clamp_index(selection_index[key_map[focus]] + delta, size)
    elif roster_tab == "coaches":
        size = len(coach_lists()[roster_focus])
        selection_index[roster_focus] = clamp_index(selection_index[roster_focus] + delta, size)
    else:
        size = len(user_team.lineup + user_team.bench + user_team.rotation + user_team.bullpen)
        selection_index[roster_focus] = clamp_index(selection_index[roster_focus] + delta, size)


def open_player_detail(player):
    global player_detail, game_state, status_message
    if not player or is_empty_slot(player):
        status_message = "That roster slot is empty."
        return
    player_detail = player
    game_state = "player_detail"


def refresh_trade_offer():
    global current_trade_offer
    current_trade_offer = cpu_generate_trade_offer(user_team, season.teams[1:])


def refresh_news():
    global news_feed
    if not season:
        return
    news_feed.extend(build_contract_news(user_team))
    news_feed.extend(generate_cpu_news(season.teams))


def check_user_contracts():
    global active_negotiation, game_state, status_message
    expired = []
    for obj in user_team.all_people():
        if hasattr(obj, "contract_games_remaining") and obj.contract_games_remaining <= 0:
            expired.append(obj)
    for obj in expired:
        if obj not in negotiation_queue and active_negotiation is None:
            active_negotiation = NegotiationState(player=obj, games_offer=max(10, min(162, getattr(obj, "contract_length", 30) or 30)), salary_offer=max(750_000, getattr(obj, "salary", 750_000)))
            game_state = "contract_negotiation"
            status_message = f"{obj.name} needs a new deal."
            break


def consume_contract_day():
    expired_hitters = []
    expired_pitchers = []
    expired_hitting_coaches = []
    expired_pitching_coaches = []

    for idx, team in enumerate(season.teams):
        expired = team.decrement_contracts(1)

        for obj in expired:
            if idx == 0:
                # user team: keep player on team and force negotiation screen
                continue

            team.remove_person(obj)

            if hasattr(obj, "ops"):
                expired_hitters.append(obj)
            elif hasattr(obj, "average_minus"):
                expired_pitchers.append(obj)
            elif hasattr(obj, "ops_boost"):
                expired_hitting_coaches.append(obj)
            else:
                expired_pitching_coaches.append(obj)

        team.refresh_roles()
        if hasattr(team, "repair_roster_structure"):
            team.repair_roster_structure()

    free_agent_hitters.extend(expired_hitters)
    free_agent_pitchers.extend(expired_pitchers)
    free_agent_hitting_coaches.extend(expired_hitting_coaches)
    free_agent_pitching_coaches.extend(expired_pitching_coaches)

    for cpu_team in season.teams[1:]:
        fill_cpu_rosters_from_market(cpu_team, free_agent_hitters, free_agent_pitchers)

        if free_agent_hitting_coaches and len(cpu_team.hitting_coaches) < 2:
            affordable = [c for c in free_agent_hitting_coaches if cpu_team.can_afford(c.salary)]
            if affordable:
                coach = affordable[0]
                free_agent_hitting_coaches.remove(coach)
                cpu_team.hitting_coaches.append(coach)

        if free_agent_pitching_coaches and cpu_team.pitching_coach is None:
            affordable = [c for c in free_agent_pitching_coaches if cpu_team.can_afford(c.salary)]
            if affordable:
                coach = affordable[0]
                free_agent_pitching_coaches.remove(coach)
                cpu_team.pitching_coach = coach

        if hasattr(cpu_team, "repair_roster_structure"):
            cpu_team.repair_roster_structure()
        cpu_team.refresh_roles()
        cpu_team.ensure_batting_order()
       

        push_cpu_team_toward_budget(cpu_team, free_agent_hitters, free_agent_pitchers)

        # Final repair pass so the upgraded roster is still valid/full
        if hasattr(cpu_team, "repair_roster_structure"):
            cpu_team.repair_roster_structure()
        cpu_team.refresh_roles()
        cpu_team.ensure_batting_order()

    user_team.ensure_within_budget()
    refresh_news()
    check_user_contracts()
    refill_coach_markets()


def run_pregame_contract_check():
    global contract_check_day, game_state, status_message

    if not season:
        return False

    user_team.ensure_within_budget()
    refresh_news()
    check_user_contracts()

    if active_negotiation is not None:
        game_state = "contract_negotiation"
        status_message = f"{active_negotiation.player.name} needs a new deal before you can play."
        return True

    return False

def player_is_unavailable(player):
    return getattr(player, "injured_games_remaining", 0) > 0


def validate_lineup_health(team, plan):
    injured_hitters = [p.name for p in getattr(plan, "batting_order", []) if player_is_unavailable(p)]
    if injured_hitters:
        return False, f"Injured hitters in lineup: {', '.join(injured_hitters)}."
    starter, relievers = all_lineup_pitchers_for_plan(team, plan)
    pitchers = [p for p in [starter] + relievers if p is not None]
    injured_pitchers = [p.name for p in pitchers if player_is_unavailable(p)]
    if injured_pitchers:
        return False, f"Injured pitchers selected: {', '.join(injured_pitchers)}."
    return True, ""


def maybe_apply_random_injury(team, allow_playoffs=False):
    global status_message
    if team is None:
        return None
    if not allow_playoffs and season and season.regular_season_over():
        return None
    if random.random() > 0.05:
        return None
    candidates = [p for p in team.active_roster_players() if getattr(p, "injured_games_remaining", 0) <= 0]
    if not candidates:
        return None
    weights = []
    for p in candidates:
        weight = 1.0
        if hasattr(p, "remaining_stamina"):
            weight += (1.0 - (p.remaining_stamina / max(1, p.max_stamina))) * 1.5
        weights.append(max(0.2, weight))
    injured = random.choices(candidates, weights=weights, k=1)[0]
    injured.injured_games_remaining = random.randint(2, 8)
    status_message = f"Injury update: {injured.name} is out for {injured.injured_games_remaining} games."
    return injured


def ensure_cpu_team_can_play(team):
    if team is user_team:
        return

    if hasattr(team, "repair_roster_structure"):
        team.repair_roster_structure()
    if hasattr(team, "refresh_roles"):
        team.refresh_roles()
    if hasattr(team, "ensure_batting_order"):
        team.ensure_batting_order()

    active_lineup = team.get_active_lineup_for_game() if hasattr(team, "get_active_lineup_for_game") else getattr(team, "lineup", [])
    real_lineup_count = len([p for p in active_lineup if not is_empty_slot(p)])

    real_rotation = team.real_rotation() if hasattr(team, "real_rotation") else [p for p in getattr(team, "rotation", []) if p and not is_empty_slot(p)]
    real_bullpen = team.real_bullpen() if hasattr(team, "real_bullpen") else [p for p in getattr(team, "bullpen", []) if p and not is_empty_slot(p)]

    lineup_ok = real_lineup_count >= 9
    rotation_ok = len(real_rotation) >= 5
    bullpen_ok = len(real_bullpen) >= 8
    pitching_ok = rotation_ok and bullpen_ok

    if lineup_ok and pitching_ok:
        return

    fill_cpu_rosters_from_market(team, free_agent_hitters, free_agent_pitchers)

    if hasattr(team, "repair_roster_structure"):
        team.repair_roster_structure()
    if hasattr(team, "refresh_roles"):
        team.refresh_roles()
    if hasattr(team, "ensure_batting_order"):
        team.ensure_batting_order()

    # emergency second check in case market fill still leaves holes
    real_rotation = team.real_rotation() if hasattr(team, "real_rotation") else [p for p in getattr(team, "rotation", []) if p and not is_empty_slot(p)]
    real_bullpen = team.real_bullpen() if hasattr(team, "real_bullpen") else [p for p in getattr(team, "bullpen", []) if p and not is_empty_slot(p)]

    while len(real_rotation) < 5:
        p = assign_salary_pitcher(gen_pitcher())
        p.contract_length = MAX_CONTRACT_GAMES
        p.contract_games_remaining = MAX_CONTRACT_GAMES
        p.role = "SP"
        team.rotation.append(p)
        real_rotation = team.real_rotation() if hasattr(team, "real_rotation") else [x for x in team.rotation if x and not is_empty_slot(x)]

    while len(real_bullpen) < 8:
        p = assign_salary_pitcher(gen_pitcher())
        p.contract_length = MAX_CONTRACT_GAMES
        p.contract_games_remaining = MAX_CONTRACT_GAMES
        p.role = "RP"
        team.bullpen.append(p)
        real_bullpen = team.real_bullpen() if hasattr(team, "real_bullpen") else [x for x in team.bullpen if x and not is_empty_slot(x)]

    if hasattr(team, "repair_roster_structure"):
        team.repair_roster_structure()
    if hasattr(team, "refresh_roles"):
        team.refresh_roles()
    if hasattr(team, "ensure_batting_order"):
        team.ensure_batting_order()

def start_free_agent_confirmation(player, source_market):
    global pending_confirmation, game_state
    pending_confirmation = {
        "kind": "free_agent",
        "player": player,
        "source": source_market,
        "message": f"Sign {player.name} for {fmt_money(player.salary)}?",
    }
    game_state = "confirm"

def bases_text(bases):
    labels = []
    if len(bases) > 0 and bases[0]:
        labels.append("1B")
    if len(bases) > 1 and bases[1]:
        labels.append("2B")
    if len(bases) > 2 and bases[2]:
        labels.append("3B")
    return "Empty" if not labels else "-".join(labels)


def draw_half_inning_panel(title, half_log, x, y, w, h):
    pygame.draw.rect(screen, (18, 32, 68), (x, y, w, h))
    pygame.draw.rect(screen, (100, 150, 230), (x, y, w, h), 2)

    draw_text(title, x + 12, y + 10, (255, 225, 120), HEADER_FONT)

    pitcher_name = half_log.get("pitcher", "Unknown")
    runs = half_log.get("runs", 0)
    hits = half_log.get("hits", 0)

    draw_text(
        f"Pitcher: {pitcher_name}   Runs: {runs}   Hits: {hits}",
        x + 12, y + 46, (200, 220, 255), SMALL_FONT
    )

    plays = half_log.get("plays", [])
    row_y = y + 82

    for play in plays[:8]:
        hitter = short_name(play.get("hitter", "Unknown"), 14)
        bases_before = bases_text(play.get("bases_before", [False, False, False]))
        outcome = play.get("outcome_text", play.get("outcome", ""))
        outs_before = play.get("outs_before", 0)
        runs_scored = play.get("runs_scored", 0)

        line = f"{outs_before} out | {bases_before:8} | {hitter:14} | {outcome}"
        if runs_scored > 0:
            line += f" (+{runs_scored} R)"

        draw_text(line, x + 12, row_y, (235, 235, 235), TINY_FONT)
        row_y += 24

def start_coach_confirmation(coach, coach_type, market_index, replacement_index=None):
    global pending_confirmation, game_state
    pending_confirmation = {
        "kind": "coach",
        "coach": coach,
        "coach_type": coach_type,
        "market_index": market_index,
        "replacement_index": replacement_index,
        "message": f"Hire {coach.name} for {fmt_money(coach.salary)}?",
    }
    game_state = "confirm"


def complete_confirmation(accepted):
    global pending_confirmation, game_state, status_message
    if not pending_confirmation:
        game_state = "menu"
        return
    if not accepted:
        status_message = "Decision canceled."
        pending_confirmation = None
        game_state = "free_agents" if free_agent_tab in ("hitters", "pitchers") else "roster"
        return

    if pending_confirmation["kind"] == "free_agent":
        player = pending_confirmation["player"]
        market = free_agent_pitchers if hasattr(player, "role") else free_agent_hitters
        if player in market:
            if user_team.can_afford(player.salary):
                market.remove(player)
                # HITTER
                if hasattr(player, "position"):
                    user_team.add_free_agent_to_bench(player)

                # PITCHER
                else:
                    # Try to add to bullpen first
                    placed = False

                    for i in range(len(user_team.bullpen)):
                        if is_empty_slot(user_team.bullpen[i]):
                            user_team.bullpen[i] = player
                            player.role = "RP"
                            placed = True
                            break

                    # If bullpen full → send to minors
                    if not placed:
                        for i in range(len(user_team.minors_pitchers)):
                            if is_empty_slot(user_team.minors_pitchers[i]):
                                user_team.minors_pitchers[i] = player
                                player.role = "SP"
                                placed = True
                                break

                    if not placed:
                        status_message = "No room for pitcher."
                        return
                user_team.refresh_roles()
                user_team.ensure_within_budget()
                status_message = f"Signed {player.name}."
            else:
                status_message = "Cannot afford that signing."
    else:
        coach = pending_confirmation["coach"]
        if pending_confirmation["coach_type"] == "pitching":
            idx = pending_confirmation["market_index"]
            current = user_team.pitching_coach
            if user_team.can_afford(coach.salary, current.salary if current else 0):
                if getattr(coach, "contract_length", 0) > 0 and getattr(coach, "contract_games_remaining", 0) <= 0:
                    coach.contract_games_remaining = coach.contract_length
                user_team.pitching_coach = coach
                if current:
                    free_agent_pitching_coaches[idx] = current
                else:
                    free_agent_pitching_coaches.pop(idx)
                user_team.ensure_within_budget()
                status_message = f"Hired pitching coach {coach.name}."
            else:
                status_message = "Cannot afford pitching coach."
        else:
            idx = pending_confirmation["market_index"]
            rep = pending_confirmation["replacement_index"]
            if rep is not None and rep < len(user_team.hitting_coaches):
                replaced = user_team.hitting_coaches[rep]
                if user_team.can_afford(coach.salary, replaced.salary):
                    if getattr(coach, "contract_length", 0) > 0 and getattr(coach, "contract_games_remaining", 0) <= 0:
                        coach.contract_games_remaining = coach.contract_length
                    user_team.hitting_coaches[rep] = coach
                    free_agent_hitting_coaches[idx] = replaced
                    user_team.ensure_within_budget()
                    status_message = f"Replaced hitting coach with {coach.name}."
                else:
                    status_message = "Cannot afford hitting coach."
            else:
                if user_team.can_afford(coach.salary):
                    if getattr(coach, "contract_length", 0) > 0 and getattr(coach, "contract_games_remaining", 0) <= 0:
                        coach.contract_games_remaining = coach.contract_length
                    user_team.hitting_coaches.append(coach)
                    free_agent_hitting_coaches.pop(idx)
                    user_team.ensure_within_budget()
                    status_message = f"Hired hitting coach {coach.name}."
                else:
                    status_message = "Cannot afford hitting coach."
    pending_confirmation = None
    game_state = "roster"


def perform_hitter_move(src_name, src_idx, dst_name, dst_idx):
    lists = hitter_lists()
    src = lists[src_name]
    dst = lists[dst_name]
    if not (0 <= src_idx < len(src) and 0 <= dst_idx < len(dst)):
        return "Invalid hitter move."
    moving = src[src_idx]
    target = dst[dst_idx]
    if is_empty_slot(moving):
        return "That slot is empty."
    if {src_name, dst_name} == {"lineup", "minors_hitters"}:
        return "Minor league players must be called up to the bench before entering the lineup."
    if src_name == dst_name:
        src[src_idx], src[dst_idx] = src[dst_idx], src[src_idx]
        user_team.ensure_batting_order()
        return "Swapped hitters."
    if dst_name == "lineup" and not user_team.can_start_at_lineup_index(moving, dst_idx):
        needed = REQUIRED_LINEUP_POSITIONS[dst_idx]
        return f"{moving.name} cannot start at {needed}."
    if src_name == "lineup" and not is_empty_slot(target) and not user_team.can_start_at_lineup_index(target, src_idx):
        needed = REQUIRED_LINEUP_POSITIONS[src_idx]
        return f"{target.name} cannot move into {needed}."
    src[src_idx], dst[dst_idx] = target, moving
    user_team.ensure_batting_order()
    user_team.normalize_optional_slots()
    return "Moved hitter."

def all_lineup_pitchers_for_plan(team, plan):
    all_pitchers = [p for p in (team.rotation + team.bullpen) if not is_empty_slot(p)]
    by_name = {p.name: p for p in all_pitchers}
    starter = by_name.get(plan.starter_name)
    relievers = [by_name.get(name) for name in plan.reliever_names]
    relievers = [p for p in relievers if p is not None]
    return starter, relievers


def validate_lineup_pitching_plan(team, plan):
    starter, relievers = all_lineup_pitchers_for_plan(team, plan)

    if starter is None:
        return False, "You must select a starting pitcher."

    if getattr(starter, "remaining_stamina", 0) <= 0:
        return False, f"{starter.name} is out and cannot start."

    # pick your threshold here
    min_starter_stamina = max(1, int(getattr(starter, "max_stamina", 0) * 0.35))
    if getattr(starter, "remaining_stamina", 0) < min_starter_stamina:
        return False, f"{starter.name} does not have enough stamina to start."

    if len(relievers) < 2:
        return False, "You must select both a middle reliever and a closer."

    seen = {starter.name}
    for p in relievers:
        if p.name in seen:
            return False, "Starter, middle reliever, and closer must all be different pitchers."
        seen.add(p.name)

        if getattr(p, "remaining_stamina", 0) <= 0:
            return False, f"{p.name} is out and cannot pitch."

        min_relief_stamina = max(1, int(getattr(p, "max_stamina", 0) * 0.20))
        if getattr(p, "remaining_stamina", 0) < min_relief_stamina:
            return False, f"{p.name} does not have enough stamina for relief."

    return True, ""
def draw_minor_callup_contract_screen():
    screen.fill((10, 18, 34))

    if not minor_callup_contract:
        draw_text("No minor league call-up pending.", 60, 80, (255, 120, 120), HEADER_FONT)
        return

    player = minor_callup_contract["player"]

    draw_text("MINOR LEAGUE CALL-UP CONTRACT", 60, 50, (255, 225, 120), TITLE_FONT)
    draw_text(f"Player: {player.name}", 60, 120, (240, 240, 240), HEADER_FONT)
    draw_text(f"Offer: {minor_contract_days} games / {fmt_money(minor_contract_salary)}", 60, 170, (180, 220, 255), HEADER_FONT)

    draw_text("UP/DOWN = salary  |  LEFT/RIGHT = days", 60, 250, (220, 220, 220))
    draw_text("ENTER = sign and call up  |  ESC = cancel", 60, 285, (220, 220, 220))
    draw_text("Minor league call-ups accept low rookie contracts.", 60, 340, (180, 180, 180))
def confirm_minor_callup_contract():
    global minor_callup_contract, game_state, status_message

    if not minor_callup_contract:
        game_state = "roster"
        return

    player = minor_callup_contract["player"]
    player_type = minor_callup_contract["player_type"]
    idx = minor_callup_contract["minor_index"]

    if not user_team.can_afford(minor_contract_salary):
        status_message = f"Cannot call up {player.name} — not enough budget."
        return

    player.salary = minor_contract_salary
    player.contract_length = minor_contract_days
    player.contract_games_remaining = minor_contract_days

    if player_type == "hitter":
        _ok, msg = user_team.call_up_minor_hitter(idx)
    else:
        _ok, msg = user_team.call_up_minor_pitcher(idx)

    user_team.ensure_within_budget()
    status_message = msg
    minor_callup_contract = None
    game_state = "roster"
def perform_pitcher_move(src_name, src_idx, dst_name, dst_idx):
    lists = pitcher_lists()
    src = lists[src_name]
    dst = lists[dst_name]

    if not (0 <= src_idx < len(src) and 0 <= dst_idx < len(dst)):
        return "Invalid pitcher move."

    moving = src[src_idx]
    target = dst[dst_idx]

    if is_empty_slot(moving):
        return "That slot is empty."

    src[src_idx], dst[dst_idx] = target, moving

    if src_name == dst_name:
        if src_name == "rotation":
            for pitcher in user_team.rotation:
                if not is_empty_slot(pitcher):
                    pitcher.role = "SP"
        elif src_name == "bullpen":
            for idx, pitcher in enumerate(user_team.bullpen):
                if is_empty_slot(pitcher):
                    continue
                pitcher.role = "CL" if idx == 1 else "RP"
        user_team.refresh_roles()
        user_team.normalize_optional_slots()
        return "Swapped pitchers."

    if src_name == "rotation":
        if not is_empty_slot(target):
            target.role = "RP"
        moving.role = "RP"
    elif dst_name == "rotation":
        if not is_empty_slot(target):
            target.role = "RP"
        moving.role = "SP"

    if src_name == "bullpen":
        moving.role = "SP" if dst_name == "rotation" else "RP"
    elif src_name == "minors":
        moving.role = "SP" if dst_name == "rotation" else "RP"

    if dst_name == "bullpen":
        if not is_empty_slot(moving):
            moving.role = "CL" if dst_idx == 1 else "RP"
    if src_name == "bullpen" and not is_empty_slot(target):
        target.role = "CL" if src_idx == 1 else "RP"

    for pitcher in user_team.rotation:
        if not is_empty_slot(pitcher):
            pitcher.role = "SP"
    for idx, pitcher in enumerate(user_team.bullpen):
        if not is_empty_slot(pitcher):
            pitcher.role = "CL" if idx == 1 else "RP"

    user_team.refresh_roles()
    user_team.normalize_optional_slots()
    return "Moved pitcher."


def drop_selected_player():
    global status_message, pending_selection
    if roster_tab == "hitters" and roster_focus in {"bench", "minors_hitters"}:
        _ok, msg = user_team.drop_player_from_optional_group(roster_focus, selection_index[roster_focus])
        pending_selection = None
        status_message = msg
        return
    if roster_tab == "pitchers" and roster_pitcher_focus == "minors":
        _ok, msg = user_team.drop_player_from_optional_group("minors_pitchers", selection_index["pitcher_minors"])
        pending_selection = None
        status_message = msg
        return
    status_message = "You can only drop players from the bench or minors."


def handle_callup_senddown():
    global pending_selection, status_message
    pending_selection = None

    # -------- HITTERS --------
    if roster_tab == "hitters":

        # CALL UP HITTER
        if roster_focus == "minors_hitters":
            player = user_team.minors_hitters[selection_index["minors_hitters"]]

            if is_empty_slot(player):
                status_message = "That minor league slot is empty."
                return

            start_minor_callup_contract(player, "hitter", selection_index["minors_hitters"])
            return

        # SEND DOWN HITTER
        if roster_focus == "bench":
            _ok, status_message = user_team.send_down_bench_hitter(selection_index["bench"])
            return

    # -------- PITCHERS --------
    elif roster_tab == "pitchers":

        # CALL UP PITCHER
        if roster_pitcher_focus == "minors":
            player = user_team.minors_pitchers[selection_index["pitcher_minors"]]

            if is_empty_slot(player):
                status_message = "That minor league slot is empty."
                return

            start_minor_callup_contract(player, "pitcher", selection_index["pitcher_minors"])
            return

        # SEND DOWN PITCHER
        if roster_pitcher_focus == "bullpen":
            _ok, status_message = user_team.send_down_bullpen_pitcher(selection_index["pitcher_bullpen"])
            return

    status_message = "Use C on minors to call up or on bench/bullpen to send down."

def handle_roster_select():
    global pending_selection, status_message
    if roster_tab == "hitters":
        lists = hitter_lists()
    elif roster_tab == "pitchers":
        lists = pitcher_lists()
    elif roster_tab == "coaches":
        lists = coach_lists()
        if roster_focus == "pitching_coach_market":
            if free_agent_pitching_coaches:
                idx = clamp_index(selection_index["pitching_coach_market"], len(free_agent_pitching_coaches))
                start_coach_confirmation(free_agent_pitching_coaches[idx], "pitching", idx)
            else:
                status_message = "No pitching coaches available."
            pending_selection = None
            return
        if roster_focus == "hitting_coach_market":
            if free_agent_hitting_coaches:
                idx = clamp_index(selection_index["hitting_coach_market"], len(free_agent_hitting_coaches))
                replacement_idx = 0 if len(user_team.hitting_coaches) >= 2 else None
                start_coach_confirmation(free_agent_hitting_coaches[idx], "hitting", idx, replacement_idx)
            else:
                status_message = "No hitting coaches available."
            pending_selection = None
            return
    else:
        return

    if roster_tab == "pitchers":
        idx_key = {
            "rotation": "pitcher_rotation",
            "bullpen": "pitcher_bullpen",
            "minors": "pitcher_minors",
        }[roster_pitcher_focus]
        idx = selection_index[idx_key]
        cur = lists[roster_pitcher_focus]
        current_list_name = roster_pitcher_focus
    else:
        idx = selection_index[roster_focus]
        cur = lists[roster_focus]
        current_list_name = roster_focus

    if len(cur) == 0:
        status_message = "That list is empty."
        return
    if pending_selection is None or pending_selection["tab"] != roster_tab:
        pending_selection = {"tab": roster_tab, "list_name": current_list_name, "index": idx}
        status_message = f"Selected {current_list_name} #{idx + 1}"
        return
    src_name = pending_selection["list_name"]
    src_idx = pending_selection["index"]
    dst_name = roster_pitcher_focus if roster_tab == "pitchers" else roster_focus
    dst_idx = idx
    if roster_tab == "hitters":
        status_message = perform_hitter_move(src_name, src_idx, dst_name, dst_idx)
    elif roster_tab == "pitchers":
        status_message = perform_pitcher_move(src_name, src_idx, dst_name, dst_idx)
    pending_selection = None


def play_next_day():
    global status_message, all_games_today, selected_game_index, game_state
    if season.regular_season_over():
        status_message = "Regular season complete."
        return
    valid, missing = user_team.validate_lineup_positions()
    if not valid:
        status_message = "Missing positions: " + ", ".join(missing)
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
            "usage": result["usage"],
            "inning_logs": result["inning_logs"],
        })
    selected_game_index = 0
    consume_contract_day()
    for team in season.teams:
        if hasattr(team, "refill_minor_league_slots"):
            team.refill_minor_league_slots()
    maybe_apply_random_injury(user_team)
    if season.current_day % 10 == 0:
        free_agent_hitters[:], free_agent_pitchers[:] = generate_free_agents()
        status_message = f"Day {season.current_day} complete. Free agents refreshed."
    else:
        status_message = f"Day {season.current_day} complete."
    refresh_trade_offer()
    game_state = "contract_negotiation" if active_negotiation else "game_day"
    save_current_game()

def release_active_negotiation_to_free_agency():
    global active_negotiation, status_message, game_state

    if not active_negotiation:
        return

    p = active_negotiation.player

    user_team.remove_person(p)

    if hasattr(p, "ops"):
        free_agent_hitters.append(p)
    elif hasattr(p, "average_minus"):
        free_agent_pitchers.append(p)
    elif hasattr(p, "ops_boost"):
        free_agent_hitting_coaches.append(p)
    else:
        free_agent_pitching_coaches.append(p)

    status_message = f"{p.name} was released to free agency."
    active_negotiation = None
    check_user_contracts()
    game_state = "contract_negotiation" if active_negotiation else "menu"

def simulate_playoff_series(away_team, home_team, current_round):
    series_length = 1 if current_round == "Divisional" else 3
    wins_needed = 1 if series_length == 1 else 2
    away_wins = 0
    home_wins = 0
    series_games = []
    while away_wins < wins_needed and home_wins < wins_needed:
        game = simulate_game_with_box(away_team, home_team)
        winner = away_team if game["away_score"] > game["home_score"] else home_team
        if winner == away_team:
            away_wins += 1
        else:
            home_wins += 1
        game_data = {
            "title": f"{current_round} Results",
            "away_team": away_team,
            "home_team": home_team,
            "away_score": game["away_score"],
            "home_score": game["home_score"],
            "away_by_inning": game["away_by_inning"],
            "home_by_inning": game["home_by_inning"],
            "usage": game["usage"],
            "inning_logs": game["inning_logs"],
            "winner": winner,
        }
        series_games.append(game_data)
        finalize_team_game(away_team, game["usage"].get(away_team.name, {}))
        finalize_team_game(home_team, game["usage"].get(home_team.name, {}))
    series_winner = away_team if away_wins > home_wins else home_team
    return {
        "title": f"{current_round} Results",
        "away_team": away_team,
        "home_team": home_team,
        "winner": series_winner,
        "series_games": series_games,
        "series_score": (away_wins, home_wins),
        "series_text": f"{away_wins}-{home_wins}",
    }


def finalize_playoff_round_results(current_round, results):
    global status_message, game_state, current_awards, playoff_selected_matchup, playoff_round_state
    season.playoff_history[current_round] = results[:]
    winners = [r["winner"] for r in results]
    if current_round == "Divisional":
        season.playoff_round = "Pennant"
        season.playoff_matchups = [(winners[0], winners[3]), (winners[1], winners[2])]
    elif current_round == "Pennant":
        season.playoff_round = "World Series"
        season.playoff_matchups = [(winners[0], winners[1])]
    else:
        season.playoff_round = "Complete"
        season.champion = winners[0]
        season.playoff_matchups = []
        for result in getattr(season, "playoff_history", {}).get("Pennant", []):
            winner = result.get("winner")
            if winner and winner.name == user_team.name:
                pennant_entry = f"Pennant winner in Year {season.year}"
                if pennant_entry not in franchise_history:
                    franchise_history.append(pennant_entry)
        if season.champion and season.champion.name == user_team.name:
            world_series_entry = f"World Series winner in Year {season.year}"
            if world_series_entry not in franchise_history:
                franchise_history.append(world_series_entry)

    season.playoff_mvp = season.compute_playoff_mvp() if hasattr(season, "compute_playoff_mvp") else None
    playoff_selected_matchup = 0
    playoff_round_state = None
    status_message = f"{current_round} complete."
    if season.playoff_round == "Complete":
        current_awards = snapshot_awards(compute_awards(season.teams))
        if season.champion == user_team:
            game_state = "world_series_champions"
        else:
            game_state = "awards"
    else:
        game_state = "game_day"
    save_current_game()


def initialize_playoff_round_state():
    global playoff_round_state, all_games_today
    current_round = season.playoff_round
    states = []
    results = []
    all_games_today = []
    for away_team, home_team in season.playoff_matchups:
        involves_user = away_team == user_team or home_team == user_team
        if involves_user:
            series_length = 1 if current_round == "Divisional" else 3
            wins_needed = 1 if series_length == 1 else 2
            states.append({
                "away_team": away_team,
                "home_team": home_team,
                "away_wins": 0,
                "home_wins": 0,
                "wins_needed": wins_needed,
                "series_games": [],
            })
        else:
            result = simulate_playoff_series(away_team, home_team, current_round)
            results.append(result)
            all_games_today.extend(result["series_games"])
    playoff_round_state = {
        "round": current_round,
        "cpu_results": results,
        "user_series_states": states,
        "current_user_series_index": 0,
        "current_series": states[0] if states else None,
    }


def advance_playoff_round_if_ready():
    if not playoff_round_state:
        return False
    if any(s["away_wins"] < s["wins_needed"] and s["home_wins"] < s["wins_needed"] for s in playoff_round_state["user_series_states"]):
        return False
    current_round = playoff_round_state["round"]
    results = list(playoff_round_state["cpu_results"])
    for state in playoff_round_state["user_series_states"]:
        series_winner = state["away_team"] if state["away_wins"] > state["home_wins"] else state["home_team"]
        results.append({
            "title": f"{current_round} Results",
            "away_team": state["away_team"],
            "home_team": state["home_team"],
            "winner": series_winner,
            "series_games": state["series_games"],
            "series_score": (state["away_wins"], state["home_wins"]),
            "series_text": f"{state['away_wins']}-{state['home_wins']}",
        })
    ordered = []
    for away_team, home_team in season.playoff_matchups:
        for result in results:
            if result["away_team"] == away_team and result["home_team"] == home_team:
                ordered.append(result)
                break
    finalize_playoff_round_results(current_round, ordered)
    return True


def play_next_playoff_game():
    global all_games_today, selected_game_index, status_message, game_state
    global current_awards, playoff_selected_matchup, playoff_round_state, lineup_plan

    if season.playoff_round is None:
        season.start_playoffs()
    if season.playoff_round == "Complete":
        current_awards = snapshot_awards(compute_awards(season.teams))
        game_state = "world_series_champions" if season.champion == user_team else "awards"
        return
    if playoff_round_state is None or playoff_round_state.get("round") != season.playoff_round:
        initialize_playoff_round_state()
        if not playoff_round_state.get("user_series_states"):
            finalize_playoff_round_results(season.playoff_round, playoff_round_state["cpu_results"])
            return

    series = playoff_round_state.get("current_series")
    if not series:
        if advance_playoff_round_if_ready():
            return
        status_message = "No active playoff series."
        game_state = "playoffs"
        return

    away_team = series["away_team"]
    home_team = series["home_team"]
    game = simulate_game_with_box(away_team, home_team)
    winner = away_team if game["away_score"] > game["home_score"] else home_team
    if winner == away_team:
        series["away_wins"] += 1
    else:
        series["home_wins"] += 1
    game_data = {
        "title": f"{season.playoff_round} Results",
        "away_team": away_team,
        "home_team": home_team,
        "away_score": game["away_score"],
        "home_score": game["home_score"],
        "away_by_inning": game["away_by_inning"],
        "home_by_inning": game["home_by_inning"],
        "usage": game["usage"],
        "inning_logs": game["inning_logs"],
        "winner": winner,
    }
    series["series_games"].append(game_data)
    all_games_today.append(game_data)
    selected_game_index = max(0, len(all_games_today) - 1)
    finalize_team_game(away_team, game["usage"].get(away_team.name, {}))
    finalize_team_game(home_team, game["usage"].get(home_team.name, {}))
    maybe_apply_random_injury(user_team, allow_playoffs=True)

    if series["away_wins"] >= series["wins_needed"] or series["home_wins"] >= series["wins_needed"]:
        playoff_round_state["current_user_series_index"] += 1
        idx = playoff_round_state["current_user_series_index"]
        playoff_round_state["current_series"] = playoff_round_state["user_series_states"][idx] if idx < len(playoff_round_state["user_series_states"]) else None
        if advance_playoff_round_if_ready():
            return
        status_message = f"{season.playoff_round} series game complete."
        game_state = "game_day"
    else:
        lineup_plan = build_lineup_plan(user_team)
        status_message = f"Series tied {series['away_wins']}-{series['home_wins']}. Set your lineup for the next playoff game."
        game_state = "lineup"
    save_current_game()


def play_next_playoff_round():
    global playoff_round_state, status_message, lineup_plan, game_state, current_awards

    if season.playoff_round is None:
        season.start_playoffs()

    if season.playoff_round == "Complete":
        current_awards = snapshot_awards(compute_awards(season.teams))
        game_state = "world_series_champions" if season.champion == user_team else "awards"
        return

    # If this round is already initialized and user still has a live series,
    # go to lineup before the next playoff game.
    if playoff_round_state is not None and playoff_round_state.get("round") == season.playoff_round:
        if playoff_round_state.get("current_series"):
            lineup_plan = build_lineup_plan(user_team)
            status_message = "Set your lineup for the next playoff game."
            game_state = "lineup"
            return

    playoff_round_state = None
    initialize_playoff_round_state()

    # User has an active series this round
    if playoff_round_state and playoff_round_state.get("current_series"):
        lineup_plan = build_lineup_plan(user_team)
        status_message = "Set your lineup for the next playoff game."
        game_state = "lineup"
        return

    # No active user series in this initialized round.
    # If all user series are complete, advance the round properly.
    if advance_playoff_round_if_ready():
        if season.playoff_round == "Complete":
            current_awards = snapshot_awards(compute_awards(season.teams))
            game_state = "world_series_champions" if season.champion == user_team else "awards"
        else:
            initialize_playoff_round_state()
            if playoff_round_state and playoff_round_state.get("current_series"):
                lineup_plan = build_lineup_plan(user_team)
                status_message = "Set your lineup for the next playoff game."
                game_state = "lineup"
            else:
                game_state = "playoffs"
        return

    status_message = "No active playoff series."
    game_state = "playoffs"
def finalize_team_game(team, usage_map):
    global status_message

    used_names = set(name for name in usage_map if name)
    team.apply_coaching_progress()
    team.apply_spin_rate_lab_progress(games_per_boost=5)

    # NEW: scouting progression
    if hasattr(team, "ensure_scouting_state"):
        team.ensure_scouting_state()
        new_reports = advance_scouting(team, games=1)
        if team is user_team and new_reports:
            first = new_reports[0]
            status_message = f"Scouting report: {first.player.name} found in the {first.source_name}."

    team.apply_postgame_fatigue(usage_map)
    team.recover_pitcher_fatigue(used_names)
    team.decrement_injuries(1)

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
    
def start_next_season():
    global status_message, all_games_today, current_awards, active_negotiation, game_state, stats_year_index
    season.archive_user_stats()
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
    season.all_star_day = max(1, (len(season.schedule) * 2) // 3)
    season.all_star_played = False
    for idx, tm in enumerate(season.teams):
        tm.budget = 165_000_000 if idx == 0 else 200_000_000
    all_games_today = []
    current_awards = None
    active_negotiation = None
    stats_year_index = len(getattr(season, "user_stat_history", []))
    refresh_news()
    check_user_contracts()
    if active_negotiation:
        status_message = f"Spring training negotiation: {active_negotiation.player.name} needs a new deal before Opening Day."
        game_state = "contract_negotiation"
    else:
        status_message = f"Year {season.year} begins."
        game_state = "menu"



def draw_hitter_row(x, y, width, hitter, selected, focused, order_num=None):
    base_color = (255, 225, 120) if selected and focused else (230, 230, 230)
    selected_prefix = ">" if selected and focused else " "

    if not hitter or is_empty_slot(hitter):
        draw_text(f"{selected_prefix} -- EMPTY SLOT", x, y, base_color)
        return

    # column positions (tight + safe inside box)
    marker_x = x
    pos_x = x + 18
    name_x = x + 58
    avg_x = x + width - 270
    obp_x = x + width - 200
    slg_x = x + width - 130
    sal_x = x + width - 80
    streak_x = x + width - 20   # far right edge

    injured = getattr(hitter, "injured_games_remaining", 0) > 0
    name_color = (255, 120, 120) if injured else base_color

    # streak detection
    streak_tag = ""
    if getattr(hitter, "hot_streak_bonus", 0) > 0:
        streak_tag = "HOT"
    elif getattr(hitter, "cold_streak_penalty", 0) > 0:
        streak_tag = "COLD"

    # draw row
    draw_text(selected_prefix, marker_x, y, base_color)
    draw_text(str(getattr(hitter, "position", "--")), pos_x, y, base_color)
    draw_text(short_name(hitter.name, 13), name_x, y, name_color)
    draw_text(player_avg_text(hitter), avg_x, y, base_color)
    draw_text(player_obp_text(hitter), obp_x, y, base_color)
    draw_text(player_slg_text(hitter), slg_x, y, base_color)
    draw_text(fmt_money_short(getattr(hitter, "salary", 0)), sal_x, y, base_color)

    # draw streak (no header, color coded)
    if streak_tag == "HOT":
        draw_text("HOT", streak_x, y, (120, 255, 140))
    elif streak_tag == "COLD":
        draw_text("COLD", streak_x, y, (255, 140, 120))

def draw_franchise_culture_page():
    screen.fill((10, 14, 28))
    ensure_franchise_culture_state(user_team)
    recalc_morale(user_team)
    refresh_budget_from_culture(user_team, base_budget=165_000_000)

    draw_text("FRANCHISE CULTURE", 36, 24, (255, 225, 120), TITLE_FONT)
    draw_text(
        "Shape your club through pricing, morale, and the streaks that follow.",
        36, 68, (220, 230, 240), SMALL_FONT
    )
    draw_text(
        "UP/DOWN choose | A/D adjust | M menu",
        36, 94, (180, 190, 205), SMALL_FONT
    )

    draw_panel(30, 140, 560, 550, "CULTURE OVERVIEW", accent=(120, 210, 255), focused=False)

    draw_text(f"Current Lean: {culture_profile(user_team)}", 50, 190, (245, 245, 245), HEADER_FONT)
    draw_text(f"Morale: {user_team.morale}/1000", 50, 235, (245, 245, 245), HEADER_FONT)
    draw_progress_bar(50, 270, 500, 20, user_team.morale, 1000)

    draw_text("HOW IT WORKS", 50, 330, (255, 225, 120), HEADER_FONT)
    draw_text("Higher prices raise budget but can drag morale down.", 50, 370, (215, 225, 238), SMALL_FONT)
    draw_text("Low morale increases cold-streak risk.", 50, 402, (255, 145, 120), SMALL_FONT)
    draw_text("High morale increases hot-streak chances.", 50, 434, (120, 255, 145), SMALL_FONT)
    draw_text("This does not lock you into one team identity.", 50, 466, (215, 225, 238), SMALL_FONT)
    draw_text("Your club can shift over time.", 50, 498, (215, 225, 238), SMALL_FONT)

    hot_names = [s["name"] for s in user_team.active_hot_streaks[:4]]
    cold_names = [s["name"] for s in user_team.active_cold_streaks[:4]]

    draw_text("HOT: " + (", ".join(hot_names) if hot_names else "None"), 50, 560, (120, 255, 145), SMALL_FONT)
    draw_text("COLD: " + (", ".join(cold_names) if cold_names else "None"), 50, 592, (255, 145, 120), SMALL_FONT)

    draw_panel(620, 140, 565, 550, "PRICING CONTROLS", accent=(120, 255, 180), focused=True)

    controls = [
        ("Ticket Price", user_team.ticket_price_level),
        ("Vendor Price", user_team.vendor_price_level),
    ]

    y = 220
    for i, (label, value) in enumerate(controls):
        selected = selection_index.get("culture_controls", 0) == i
        fill = (28, 40, 62) if not selected else (42, 58, 88)
        border = (90, 120, 160) if not selected else (255, 225, 120)

        pygame.draw.rect(screen, fill, (640, y, 520, 62), border_radius=10)
        pygame.draw.rect(screen, border, (640, y, 520, 62), 2, border_radius=10)

        draw_text(label, 662, y + 10, (245, 245, 245), HEADER_FONT)
        draw_text(f"Level {value}", 980, y + 10, (120, 210, 255), HEADER_FONT)
        draw_text("A/D to adjust", 662, y + 36, (180, 190, 205), SMALL_FONT)
        y += 88

    draw_text(f"Revenue Impact: {fmt_money(franchise_revenue_bonus(user_team))}", 650, 430, (120, 255, 145), HEADER_FONT)
    draw_text(f"Budget: {fmt_money(user_team.budget)}", 650, 470, (255, 225, 120), HEADER_FONT)

    if user_team.morale >= 650:
        summary = "High morale: stronger hot-streak potential."
        color = (120, 255, 145)
    elif user_team.morale <= 400:
        summary = "Low morale: higher slump risk."
        color = (255, 145, 120)
    else:
        summary = "Morale is stable."
        color = (215, 225, 238)

    draw_text(summary, 650, 520, color, HEADER_FONT)
    draw_text(status_message, 36, HEIGHT - 28, (255, 210, 90), SMALL_FONT)

def draw_pitcher_row(x, y, w, pitcher, selected=False, focused=False, show_salary=True, is_active=False):
    color = (255, 225, 120) if selected and focused else (230, 230, 230)
    prefix = ">" if selected else " "

    # column layout
    role_x = x
    name_x = x + 42
    avg_x = x + 245
    obp_x = x + 305
    slg_x = x + 365
    era_x = x + 425
    sta_x = x + 485
    sal_x = x + 545

    if not pitcher or is_empty_slot(pitcher):
        draw_text(f"{prefix} -- EMPTY SLOT", role_x, y, color)
        return

    role = getattr(pitcher, "role", "--")
    injured = getattr(pitcher, "injured_games_remaining", 0) > 0
    if injured:
        name_color = (255, 120, 120)
    elif is_active:
        name_color = (120, 255, 140)   # green highlight
    else:
        name_color = color

    era_text = getattr(pitcher, "era", "---")
    stamina_text = getattr(
        pitcher,
        "stamina_ratio_text",
        f"{getattr(pitcher, 'remaining_stamina', 0)}/{getattr(pitcher, 'max_stamina', 0)}"
    )

    salary = getattr(pitcher, "salary", 0)

    # compact salary text so it stays inside the box
    if salary >= 1000000:
        sal_text = f"{salary / 1000000:.1f}M"
    elif salary >= 1000:
        sal_text = f"{salary / 1000:.0f}K"
    else:
        sal_text = str(salary)

    draw_text(prefix, role_x, y, color)
    draw_text(f"{role:>2}", role_x + 16, y, color)
    draw_text(short_name(get_player_name(pitcher), 14), name_x, y, name_color)

    draw_text(
        str(getattr(pitcher, "peak_average_minus", getattr(pitcher, "display_average_minus", "---"))),
        avg_x, y, color
    )
    draw_text(
        str(getattr(pitcher, "peak_obp_minus", getattr(pitcher, "display_obp_minus", "---"))),
        obp_x, y, color
    )
    draw_text(
        str(getattr(pitcher, "peak_slugging_minus", getattr(pitcher, "display_slugging_minus", "---"))),
        slg_x, y, color
    )

    draw_text(f"{era_text}", era_x, y, color)
    draw_text(f"{stamina_text}", sta_x, y, color)
    if show_salary:
        draw_text(sal_text, sal_x, y, color)
def draw_scouting_page():
    screen.fill((7, 14, 28))
    draw_text("GLOBAL SCOUTING", 36, 24, (255, 225, 120), TITLE_FONT)
    draw_budget_top_right(user_team)

    scout_stars = getattr(user_team, "scout_stars", 0)
    scout_salary = getattr(user_team, "scout_salary", 0)
    games_left = getattr(user_team, "scout_games_until_report", 0)
    reports = getattr(user_team, "scouted_prospects", [])

    current_label = "No scout hired" if scout_stars == 0 else f"{scout_stars}-Star Scout"
    progress_label = "--" if scout_stars == 0 else f"{games_left} games to next report"

    draw_text(
        "Hire scouts, discover overseas elite talent, and sign them at a discount.",
        38, 68, (205, 225, 240), SMALL_FONT
    )
    draw_text(
        "UP/DOWN move | LEFT/RIGHT switch panel | S/ENTER select | F fire scout | M menu",
        38, 96, (175, 190, 205), SMALL_FONT
    )

    # LEFT PANEL: scout market
    market_focused = scouting_focus == "market"
    draw_panel(30, 140, 540, 560, "SCOUT MARKET", accent=(90, 180, 255), focused=market_focused)

    draw_text(f"Current Scout: {current_label}", 48, 184, (245, 245, 245), HEADER_FONT)
    draw_text(f"Scout Cost: {fmt_money(scout_salary)}", 48, 216, (180, 220, 255), SMALL_FONT)
    draw_text(f"Next Report: {progress_label}", 48, 242, (180, 220, 255), SMALL_FONT)

    draw_text("REGIONS", 48, 286, (120, 210, 255), SMALL_FONT)
    draw_text("Pacific Circuit  | high-contact / command stars", 48, 314, (220, 230, 240), SMALL_FONT)
    draw_text("Caribbean Pipeline | power bats / explosive arms", 48, 340, (220, 230, 240), SMALL_FONT)
    draw_text("Peninsula League | disciplined hitters / polished arms", 48, 366, (220, 230, 240), SMALL_FONT)

    scout_options = [
        (1, "1-Star Scout", SCOUT_STAR_COSTS[1], "10% discount"),
        (2, "2-Star Scout", SCOUT_STAR_COSTS[2], "22% discount"),
        (3, "3-Star Scout", SCOUT_STAR_COSTS[3], "35% discount"),
    ]

    draw_text("HIRE OPTIONS", 48, 420, (255, 225, 120), HEADER_FONT)
    for i, (stars, label, cost, bonus) in enumerate(scout_options):
        selected = market_focused and selection_index["scouting_market"] == i
        y = 466 + i * 60
        fill = (26, 36, 56) if not selected else (42, 58, 88)
        border = (90, 120, 155) if not selected else (255, 225, 120)

        pygame.draw.rect(screen, fill, (48, y, 500, 44), border_radius=8)
        pygame.draw.rect(screen, border, (48, y, 500, 44), 2, border_radius=8)

        draw_text(label, 64, y + 8, (245, 245, 245), HEADER_FONT)
        draw_text(fmt_money(cost), 270, y + 10, (120, 210, 255), SMALL_FONT)
        draw_text(bonus, 400, y + 10, (140, 255, 180), SMALL_FONT)

    # RIGHT PANEL: reports
    reports_focused = scouting_focus == "reports"
    draw_panel(600, 140, 610, 560, "SCOUT REPORTS", accent=(120, 255, 180), focused=reports_focused)

    draw_text("Reports arrive every 3 completed team games.", 620, 184, (220, 235, 245), SMALL_FONT)
    draw_text("Sign discovered players directly to your organization.", 620, 210, (220, 235, 245), SMALL_FONT)

    if not reports:
        draw_text("No active scouting reports.", 620, 270, (210, 210, 210), HEADER_FONT)
        draw_text("Hire a scout and play games to generate reports.", 620, 304, (170, 180, 195), SMALL_FONT)
    else:
        start = max(0, selection_index["scouting_reports"] - 4)
        view = reports[start:start + 7]
        row_y = 250

        for i, report in enumerate(view):
            actual = start + i
            selected = reports_focused and selection_index["scouting_reports"] == actual
            p = report.player

            fill = (24, 36, 58) if not selected else (40, 58, 88)
            border = (80, 120, 170) if not selected else (255, 225, 120)

            pygame.draw.rect(screen, fill, (620, row_y, 565, 58), border_radius=8)
            pygame.draw.rect(screen, border, (620, row_y, 565, 58), 2, border_radius=8)

            player_type = "BAT" if hasattr(p, "ops") else "ARM"
            price_text = f"{fmt_money_short(report.discounted_salary)} ({report.discount_pct}% off)"
            source_text = f"{report.source_name} | {report.games_left}G left"

            draw_text(f"{player_type}  {short_name(p.name, 18)}", 634, row_y + 8, (245, 245, 245), HEADER_FONT)
            draw_text(source_text, 634, row_y + 34, (120, 210, 255), TINY_FONT)

            if hasattr(p, "ops"):
                draw_text(
                    f"AVG {fmt_stat(p.average)}  OBP {fmt_stat(p.obp)}  SLG {fmt_stat(p.slugging)}  OPS {fmt_stat(p.ops)}",
                    845, row_y + 8, (220, 235, 245), TINY_FONT
                )
            else:
                draw_text(
                    f"AVG- {p.average_minus:02d}  OBP- {p.obp_minus:02d}  SLG- {p.slugging_minus:02d}  STA {p.stamina}",
                    845, row_y + 8, (220, 235, 245), TINY_FONT
                )

            draw_text(price_text, 845, row_y + 34, (140, 255, 180), SMALL_FONT)
            row_y += 68

    draw_text(status_message, 30, HEIGHT - 28, (255, 210, 90), SMALL_FONT)

def draw_hitter_list_box(title, items, x, y, w, h, selected_idx=None, focused=False, lineup_numbers=False):
    draw_box_frame(title, x, y, w, h, focused)

    row_y = y + 62
    header_y = y + 38
    visible_rows = max(1, (h - 88) // 24)
    total_rows = len(items)
    selected_idx = 0 if selected_idx is None else selected_idx

    start = 0
    if total_rows > visible_rows:
        start = max(0, min(selected_idx - visible_rows // 2, total_rows - visible_rows))
    end = min(total_rows, start + visible_rows)

    draw_text("P",    x + 28,      header_y, (180, 180, 180), SMALL_FONT)
    draw_text("NAME", x + 68,      header_y, (180, 180, 180), SMALL_FONT)
    draw_text("AVG",  x + w - 270, header_y, (180, 180, 180), SMALL_FONT)
    draw_text("OBP",  x + w - 200, header_y, (180, 180, 180), SMALL_FONT)
    draw_text("SLG",  x + w - 130, header_y, (180, 180, 180), SMALL_FONT)
    draw_text("SAL",  x + w - 80,  header_y, (180, 180, 180), SMALL_FONT)

    for actual_i in range(start, end):
        draw_hitter_row(
            x + 10,
            row_y,
            w - 20,
            items[actual_i],
            actual_i == selected_idx,
            focused,
            actual_i + 1 if lineup_numbers else None,
        )
        row_y += 24

    if total_rows > visible_rows:
        draw_text(f"{start + 1}-{end} / {total_rows}", x + w - 125, y + h - 24, (120, 255, 140), TINY_FONT)


def draw_pitcher_list_box(title, items, x, y, w, h, selected_idx=None, focused=False):
    draw_box_frame(title, x, y, w, h, focused)

    # column positions
    col_role = x 
    col_name = x + 42
    col_avg  = x + 245
    col_obp  = x + 305
    col_slg  = x + 365
    col_era  = x + 425
    col_sta  = x + 485
    col_sal  = x + 545   # safe as long as box is ~600 wide or less

    header_y = y + 40
    row_y = y + 66
    row_h = 24

    # headers
    draw_text("ROLE", col_role, header_y, (180, 210, 255), SMALL_FONT)
    draw_text("NAME", col_name, header_y, (180, 210, 255), SMALL_FONT)
    draw_text("AVG-", col_avg, header_y, (180, 210, 255), SMALL_FONT)
    draw_text("OBP-", col_obp, header_y, (180, 210, 255), SMALL_FONT)
    draw_text("SLG-", col_slg, header_y, (180, 210, 255), SMALL_FONT)
    draw_text("ERA",  col_era, header_y, (180, 210, 255), SMALL_FONT)
    draw_text("STA",  col_sta, header_y, (180, 210, 255), SMALL_FONT)
    draw_text("SAL",  col_sal, header_y, (180, 210, 255), SMALL_FONT)

    visible_rows = max(1, (h - 80) // row_h)
    total_rows = len(items)
    selected_idx = 0 if selected_idx is None else selected_idx

    start = 0
    if total_rows > visible_rows:
        start = max(0, min(selected_idx - visible_rows // 2, total_rows - visible_rows))
    end = min(total_rows, start + visible_rows)

    for actual_i in range(start, end):
        draw_pitcher_row(
            x + 10,
            row_y,
            w - 20,
            items[actual_i],
            actual_i == selected_idx,
            focused
        )
        row_y += row_h

    if total_rows > visible_rows:
        draw_text(
            f"{start + 1}-{end} / {total_rows}",
            x + w - 125,
            y + h - 24,
            (120, 255, 140),
            TINY_FONT
        )
def draw_stats_tab():
    screen.fill((14, 14, 30))
    draw_text(f"{user_team.name.upper()} PLAYER STATS", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_budget_top_right(user_team)
    archived = list(getattr(season, "user_stat_history", []))
    current_snapshot = {
        "year": season.year,
        "roster": [p for p in (user_team.lineup + user_team.bench + user_team.rotation + user_team.bullpen) if not is_empty_slot(p)],
        "is_current": True,
    }
    stat_views = archived + [current_snapshot]
    idx = clamp_index(stats_year_index, len(stat_views))
    view_state = stat_views[idx] if stat_views else current_snapshot
    year_label = f"Year {view_state['year']}" + (" (Current)" if view_state.get("is_current") else "")
    draw_text("1 Hitters | 2 Pitchers | 3 Coaches | 4 Stats | LEFT/RIGHT year | I Detail | M Menu", 30, 70, (190, 190, 190))
    draw_text(year_label, 30, 96, (120, 255, 140), HEADER_FONT)
    roster = view_state["roster"]
    selection_index["stats_roster"] = clamp_index(selection_index["stats_roster"], len(roster))
    start = max(0, selection_index["stats_roster"] - 8)
    view = roster[start:start + 16]
    y = 135
    for i, p in enumerate(view):
        selected = (start + i == selection_index["stats_roster"])
        color = (255, 225, 120) if selected else (230, 230, 230)
        if isinstance(p, dict):
            if p.get("kind") == "hitter":
                text = f"{p.get('position','---'):>3} {short_name(p.get('name','Unknown'), 15):15} AVG {p.get('avg',0):.3f} OBP {p.get('obp',0):.3f} SLG {p.get('slg',0):.3f} 2B {p.get('doubles',0):2} 3B {p.get('triples',0):2} HR {p.get('homeruns',0):2}"
            else:
                text = f"{p.get('role','--'):>2} {short_name(p.get('name','Unknown'), 15):15} IP {p.get('ip','0.0'):>4} ERA {p.get('era',0.0):>4} SO {p.get('strikeouts',0):2} BB {p.get('walks',0):2} STA {p.get('stamina_ratio_text','0/0'):>7}"
        elif hasattr(p, "ops"):
            text = f"{p.position:>3} {short_name(p.name, 15):15} AVG {player_season_avg_text(p)} OBP {player_season_obp_text(p)} SLG {player_season_slg_text(p)} 2B {p.doubles:2} 3B {p.triples:2} HR {p.homeruns:2}"
        else:
            text = f"{p.role:>2} {short_name(p.name, 15):15} IP {p.innings_pitched_text:>4} ERA {p.era:>4} SO {p.strikeouts:2} BB {p.walks:2} STA {p.stamina_ratio_text:>7}"
        draw_text((">" if selected else " ") + text, 40, y, color)
        y += 28


def draw_hitter_roster():
    screen.fill((14, 14, 30))
    draw_text(f"{user_team.name.upper()} HITTERS", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_budget_top_right(user_team)
    draw_text("LEFT/RIGHT switch boxes | A/W/F quick jump | S Select/Swap | C Call Up/Send Down | X Drop | I Detail | 2 Pitchers | 3 Coaches | 4 Stats | H FA Portal | L Lineup | M Menu", 30, 70, (190, 190, 190))
    lists = hitter_lists()
    draw_hitter_list_box("LINEUP", lists["lineup"], 30, 115, 575, 315, selection_index["lineup"], roster_focus == "lineup", lineup_numbers=True)
    draw_hitter_list_box("BENCH", lists["bench"], 30, 450, 575, 225, selection_index["bench"], roster_focus == "bench")
    draw_hitter_list_box("MINOR HITTERS", lists["minors_hitters"], 635, 115, 575, 560, selection_index["minors_hitters"], roster_focus == "minors_hitters")
    sel = "NONE" if pending_selection is None else f"{pending_selection['list_name']} #{pending_selection['index'] + 1}"
    draw_text(f"Selected: {sel}", 30, HEIGHT - 55, (120, 255, 140))
    draw_text(status_message, 30, HEIGHT - 30, (255, 210, 90))


def draw_pitcher_roster_page():
    screen.fill((12, 16, 30))
    draw_text("ROSTER MANAGEMENT - PITCHERS", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_text(
        "LEFT/RIGHT switch boxes | UP/DOWN move | S select/swap | C call up/send down | X drop | I detail | 5 spin lab | M menu",
        30, 64, (190, 190, 190), SMALL_FONT
    )

    rotation = user_team.rotation[:5]
    relief_pitchers = user_team.bullpen[:8]
    minor_pitchers = user_team.minors_pitchers

    draw_pitcher_list_box(
        "ROTATION",
        rotation,
        30, 110, 600, 280,
        selection_index["pitcher_rotation"],
        roster_pitcher_focus == "rotation"
    )

    draw_pitcher_list_box(
        "RELIEF / CLOSERS",
        relief_pitchers,
        30, 415, 600, 280,
        selection_index["pitcher_bullpen"],
        roster_pitcher_focus == "bullpen"
    )

    draw_pitcher_list_box(
        "MINOR LEAGUE PITCHERS",
        minor_pitchers,
        635, 110, 600, 585,
        selection_index["pitcher_minors"],
        roster_pitcher_focus == "minors"
    )

    sel = "NONE" if pending_selection is None else f"{pending_selection['list_name']} #{pending_selection['index'] + 1}"
    draw_text(f"Selected: {sel}", 30, HEIGHT - 55, (120, 255, 140))
    draw_text(status_message, 30, HEIGHT - 30, (255, 210, 90))

def draw_title_screen():
    screen.fill((8, 12, 28))

    if LOGO_SURF:
        logo_x = WIDTH // 2 - LOGO_SURF.get_width() // 2
        screen.blit(LOGO_SURF, (logo_x, 40))
    else:
        draw_text("MLB PRO MANAGER", WIDTH // 2 - 180, 120, (255, 225, 120), TITLE_FONT)

    draw_text("Choose an option", WIDTH // 2 - 110, 590, (230, 230, 230), HEADER_FONT)

    options = ["Start New Game", "Load Previous Game"]
    y_start = 640

    for i, option in enumerate(options):
        selected = i == title_screen_selection
        color = (255, 225, 120) if selected else (220, 220, 220)
        prefix = "> " if selected else "  "

        if option == "Load Previous Game" and not has_save_file():
            color = (120, 120, 120)
            label = prefix + option + " (No save found)"
        else:
            label = prefix + option

        draw_text(label, WIDTH // 2 - 160, y_start + i * 40, color, HEADER_FONT)

    draw_text("UP/DOWN to choose | ENTER to confirm", WIDTH // 2 - 180, 735, (180, 180, 180), SMALL_FONT)

def draw_spin_rate_lab():
    screen.fill((8, 12, 24))

    if SPIN_LAB_BG:
        screen.blit(SPIN_LAB_BG, (0, 0))
    else:
        pygame.draw.rect(screen, (6, 10, 22), (0, 0, WIDTH, HEIGHT))
        pygame.draw.rect(screen, (12, 22, 42), (0, 0, WIDTH, 170))

    draw_text("SPIN RATE LAB", 36, 24, (255, 225, 120), TITLE_FONT)
    draw_budget_top_right(user_team)

    draw_text("Pitch Design Facility", 38, 64, (120, 210, 255), HEADER_FONT)
    draw_text("Improve movement and strikeout ability over time.", 38, 94, (210, 230, 245), SMALL_FONT)
    draw_text(
        "UP/DOWN choose | S add/remove | Auto boost every 5 team games | 1 Hitters | 2 Pitchers | 3 Coaches | 4 Stats | M menu",
        38, 122, (180, 190, 205), SMALL_FONT
    )

    # Top left: active slots
    draw_panel(30, 170, 560, 215, "ACTIVE DEVELOPMENT", accent=(90, 180, 255), focused=False)

    slots = [user_team.find_player(name) for name in getattr(user_team, "spin_rate_lab_slots", [])]

    for i in range(2):
        card_y = 212 + i * 82
        pitcher = slots[i] if i < len(slots) else None

        pygame.draw.rect(screen, (18, 28, 48), (48, card_y, 524, 62), border_radius=10)
        pygame.draw.rect(screen, (70, 110, 155), (48, card_y, 524, 62), 2, border_radius=10)

        draw_text(f"SLOT {i + 1}", 62, card_y + 8, (120, 210, 255), SMALL_FONT)

        if pitcher:
            progress = getattr(user_team, "spin_rate_lab_progress", {}).get(pitcher.name, 0)
            draw_text(short_name(pitcher.name, 18), 138, card_y + 6, (245, 245, 245), HEADER_FONT)
            draw_text(
                f"{pitcher.role}  AVG- {pitcher.average_minus}  ERA {pitcher.era:.2f}  SO {pitcher.strikeouts}",
                138, card_y + 34, (200, 220, 240), SMALL_FONT
            )
            draw_progress_bar(392, card_y + 20, 140, 14, progress, 5)
            draw_text(f"{progress}/5", 540, card_y + 18, (255, 225, 120), TINY_FONT)
        else:
            draw_text("EMPTY", 138, card_y + 18, (210, 210, 210), HEADER_FONT)
            draw_text("Choose a pitcher from the pool below.", 138, card_y + 40, (160, 175, 190), SMALL_FONT)

    # Top right: lab info
    draw_panel(620, 170, 590, 215, "LAB ANALYTICS", accent=(100, 255, 180), focused=False)

    frame = current_spin_ball_frame()
    if frame:
        screen.blit(frame, (980, 190))

    draw_text("LAB EFFECT", 645, 214, (120, 255, 180), SMALL_FONT)
    draw_text("+AVG- every 5 completed team games", 760, 214, (235, 235, 235), SMALL_FONT)

    draw_text("FOCUS", 645, 252, (120, 255, 180), SMALL_FONT)
    draw_text("Developing changeups and sweepers that increase strikouts", 760, 252, (235, 235, 235), SMALL_FONT)

    draw_text("ELIGIBLE ARMS", 645, 290, (120, 255, 180), SMALL_FONT)
    draw_text("Current rotation and bullpen only", 760, 290, (235, 235, 235), SMALL_FONT)

    draw_text("CAPACITY", 645, 328, (120, 255, 180), SMALL_FONT)
    draw_text("2 pitchers max at one time", 760, 328, (235, 235, 235), SMALL_FONT)

    # Bottom: pitcher pool
    draw_panel(30, 405, 1180, 285, "PITCHER POOL", accent=(255, 225, 120), focused=True)
    draw_text("Choose up to 2 pitchers from your current rotation and bullpen.", 48, 438, (180, 190, 205), SMALL_FONT)

    header_y = 466
    draw_text("ROLE",     52,  header_y, (120, 210, 255), SMALL_FONT)
    draw_text("NAME",     112, header_y, (120, 210, 255), SMALL_FONT)
    draw_text("AVG-",     320, header_y, (120, 210, 255), SMALL_FONT)
    draw_text("ERA",      398, header_y, (120, 210, 255), SMALL_FONT)
    draw_text("SO",       470, header_y, (120, 210, 255), SMALL_FONT)
    draw_text("PROGRESS", 560, header_y, (120, 210, 255), SMALL_FONT)
    draw_text("STATUS",   760, header_y, (120, 210, 255), SMALL_FONT)
    draw_text("STA",      910, header_y, (120, 210, 255), SMALL_FONT)

    pool = user_team.available_spin_lab_pitchers() if hasattr(user_team, "available_spin_lab_pitchers") else []
    start = max(0, selection_index["spin_lab_pool"] - 3)
    view = pool[start:start + 6]

    row_y = 494
    for i, pitcher in enumerate(view):
        actual = start + i
        selected = actual == selection_index["spin_lab_pool"]
        in_lab = pitcher.name in getattr(user_team, "spin_rate_lab_slots", [])
        progress = getattr(user_team, "spin_rate_lab_progress", {}).get(pitcher.name, 0)

        fill = (24, 36, 58) if not selected else (40, 58, 88)
        border = (80, 120, 170) if not selected else (255, 225, 120)

        pygame.draw.rect(screen, fill, (46, row_y, 1148, 24), border_radius=6)
        pygame.draw.rect(screen, border, (46, row_y, 1148, 24), 2, border_radius=6)

        text_color = (245, 245, 245) if selected else (225, 225, 225)
        stamina_text = getattr(
            pitcher,
            "stamina_ratio_text",
            f"{getattr(pitcher, 'remaining_stamina', 0)}/{getattr(pitcher, 'max_stamina', 0)}"
        )

        draw_text(f"{pitcher.role:>2}", 58, row_y + 4, text_color, TINY_FONT)
        draw_text(short_name(pitcher.name, 18), 112, row_y + 4, text_color, TINY_FONT)
        draw_text(f"{pitcher.average_minus:>3}", 328, row_y + 4, (220, 240, 255), TINY_FONT)
        draw_text(f"{pitcher.era:>4.2f}", 396, row_y + 4, (220, 240, 255), TINY_FONT)
        draw_text(f"{pitcher.strikeouts:>3}", 472, row_y + 4, (220, 240, 255), TINY_FONT)

        draw_progress_bar(560, row_y + 5, 120, 12, progress, 5)
        draw_text(f"{progress}/5", 690, row_y + 4, (255, 225, 120), TINY_FONT)

        status_text = "ACTIVE" if in_lab else "AVAILABLE"
        status_color = (120, 255, 180) if in_lab else (180, 190, 205)
        draw_text(status_text, 760, row_y + 4, status_color, TINY_FONT)
        draw_text(stamina_text, 910, row_y + 4, (220, 240, 255), TINY_FONT)

        row_y += 30

    if len(pool) > 6:
        draw_text(f"{start + 1}-{start + len(view)} / {len(pool)}", 1080, 660, (120, 255, 140), TINY_FONT)

    draw_text(status_message, 30, HEIGHT - 30, (255, 210, 90), SMALL_FONT)
def draw_coach_row(x, y, coach, color):
    if hasattr(coach, "ops_boost"):
        text = f"{short_name(coach.name, 12):12} AVG+{coach.avg_boost:2} OBP+{coach.obp_boost:2} OPS+{coach.ops_boost:2} {fmt_money_short(coach.salary)}"
    else:
        text = f"{short_name(coach.name, 12):12} AVG+{coach.avg_boost:2} OBP+{coach.obp_boost:2} SLG+{coach.slg_boost:2} {fmt_money_short(coach.salary)}"
    draw_text(text, x, y, color)


def draw_coaches_tab():
    screen.fill((14, 14, 30))
    draw_text(f"{user_team.name.upper()} COACHES", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_budget_top_right(user_team)
    draw_text("LEFT/RIGHT switch boxes | A Pitch Coach | W Pitch Market | F Hit Coaches | G Hit Market | S Hire | K Assign | I Detail | M Menu", 30, 70, (190, 190, 190))
    draw_box_frame("ACTIVE PITCHING COACH", 30, 120, 560, 170, roster_focus == "pitching_coach_slot")
    if user_team.pitching_coach:
        draw_coach_row(42, 185, user_team.pitching_coach, (230, 230, 230))
        draw_text(f"Active coach: {user_team.pitching_coach.name}", 42, 215, (120, 255, 140))
        draw_text(f"Coached pitcher: {user_team.pitching_assignment_name or 'None'}", 42, 240, (120, 255, 140))
        assigned_pitcher = user_team.find_player(user_team.pitching_assignment_name) if user_team.pitching_assignment_name else None
        if assigned_pitcher:
            draw_text(f"Boosted target: {assigned_pitcher.name}  STA {assigned_pitcher.stamina_ratio_text}", 42, 265, (180, 210, 255))
    draw_box_frame("PITCHING MARKET", 30, 315, 560, 250, roster_focus == "pitching_coach_market")
    y = 360
    for i, coach in enumerate(free_agent_pitching_coaches[:7]):
        color = (255, 225, 120) if i == selection_index["pitching_coach_market"] and roster_focus == "pitching_coach_market" else (230, 230, 230)
        draw_text(">" if i == selection_index["pitching_coach_market"] and roster_focus == "pitching_coach_market" else " ", 42, y, color)
        draw_coach_row(58, y, coach, color)
        y += 28
    draw_box_frame("ACTIVE HITTING COACHES", 635, 120, 560, 210, roster_focus == "hitting_coach_slot")
    y = 165
    for i, coach in enumerate(user_team.hitting_coaches[:2]):
        color = (255, 225, 120) if i == selection_index["hitting_coach_slot"] and roster_focus == "hitting_coach_slot" else (230, 230, 230)
        draw_text(">" if i == selection_index["hitting_coach_slot"] and roster_focus == "hitting_coach_slot" else " ", 647, y, color)
        draw_coach_row(663, y, coach, color)
        y += 28
    assigned = ", ".join([name for name in user_team.hitting_assignment_names if name]) if user_team.hitting_assignment_names else "None"
    draw_text(f"Coached hitters: {assigned}", 647, 255, (120, 255, 140))
    if user_team.hitting_coaches:
        for idx, coach in enumerate(user_team.hitting_coaches[:2]):
            assigned_name = user_team.hitting_assignment_names[idx] if idx < len(user_team.hitting_assignment_names) and user_team.hitting_assignment_names[idx] else "None"
            draw_text(f"Coach {idx + 1} target: {assigned_name}", 647, 278 + idx * 22, (180, 210, 255))
    draw_box_frame("HITTING MARKET", 635, 355, 560, 250, roster_focus == "hitting_coach_market")
    y = 400
    for i, coach in enumerate(free_agent_hitting_coaches[:7]):
        color = (255, 225, 120) if i == selection_index["hitting_coach_market"] and roster_focus == "hitting_coach_market" else (230, 230, 230)
        draw_text(">" if i == selection_index["hitting_coach_market"] and roster_focus == "hitting_coach_market" else " ", 647, y, color)
        draw_coach_row(663, y, coach, color)
        y += 28
    draw_text(status_message, 30, HEIGHT - 30, (255, 210, 90))


def draw_user_roster():
    if roster_tab == "hitters":
        draw_hitter_roster()
    elif roster_tab == "pitchers":
        draw_pitcher_roster_page()
    elif roster_tab == "coaches":
        draw_coaches_tab()
    elif roster_tab == "spin_lab":
        draw_spin_rate_lab()
    else:
        draw_stats_tab()


def draw_free_agent_portal():
    screen.fill((14, 14, 30))
    title = "FREE AGENT PORTAL - HITTERS" if free_agent_tab == "hitters" else "FREE AGENT PORTAL - PITCHERS"
    draw_text(title, 30, 20, (255, 225, 120), TITLE_FONT)
    draw_budget_top_right(user_team)
    draw_text("1 Hitters | 2 Pitchers | UP/DOWN scroll | ENTER/S Sign player | I Detail | M Back", 30, 70, (190, 190, 190))
    if free_agent_tab == "hitters":
        draw_hitter_list_box("FREE AGENT HITTERS", free_agent_hitters, 30, 115, 1180, 620, selection_index["free_agent_hitters"], True)
    else:
        draw_pitcher_list_box("FREE AGENT PITCHERS", free_agent_pitchers, 30, 115, 1180, 620, selection_index["free_agent_pitchers"], True)
    draw_text("Signed free agents are added to your bench or bullpen.", 30, HEIGHT - 55, (120, 255, 140))
    draw_text(status_message, 30, HEIGHT - 30, (255, 210, 90))

def draw_lineup_page():
    screen.fill((12, 16, 30))
    draw_text("LINEUP / PREGAME PAGE", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_text(next_opponent_text(), 30, 64, (120, 255, 140), HEADER_FONT)
    draw_text(
        "LEFT/RIGHT switch boxes | A/D quick jump | S select/swap | I detail | ENTER save/play | M menu",
        30, 96, (190, 190, 190), SMALL_FONT
    )

    batting = lineup_plan.batting_order if lineup_plan else user_team.get_active_lineup_for_game()
    rotation_slots = user_team.rotation[:5]

    relief_slots = [p for p in [user_team.middle_reliever, user_team.closer] if p]
    extra_bullpen = [p for p in user_team.bullpen if not is_empty_slot(p) and p not in relief_slots]
    relief_pitchers = relief_slots + extra_bullpen

    # ---------- Layout ----------
    batting_x = 30
    batting_y = 135
    batting_w = 560
    batting_h = 620

    right_x = 635
    top_y = 135
    right_w = 560
    rotation_h = 250

    relief_y = 405
    relief_h = 350

    row_h = 28
    header_offset = 40
    first_row_offset = 68

    # ---------- Left box: batting ----------
    draw_box_frame("BATTING ORDER", batting_x, batting_y, batting_w, batting_h, lineup_focus == "batting_order")

    batting_header_y = batting_y + header_offset
    batting_row_y = batting_y + first_row_offset

    # Batting columns
    bx_pos   = batting_x + 14
    bx_name  = batting_x + 58
    bx_avg   = batting_x + 330
    bx_obp   = batting_x + 395
    bx_slg   = batting_x + 460
    bx_sal   = batting_x + 515

    draw_text("POS",  bx_pos,  batting_header_y, (180, 180, 180), SMALL_FONT)
    draw_text("NAME", bx_name, batting_header_y, (180, 180, 180), SMALL_FONT)
    draw_text("AVG",  bx_avg,  batting_header_y, (180, 180, 180), SMALL_FONT)
    draw_text("OBP",  bx_obp,  batting_header_y, (180, 180, 180), SMALL_FONT)
    draw_text("SLG",  bx_slg,  batting_header_y, (180, 180, 180), SMALL_FONT)
    draw_text("SAL",  bx_sal,  batting_header_y, (180, 180, 180), SMALL_FONT)

    for i, hitter in enumerate(batting[:18]):
        draw_hitter_row(
            batting_x + 10,
            batting_row_y,
            batting_w - 20,
            hitter,
            i == selection_index["lineup_hitters"],
            lineup_focus == "batting_order",
            None
        )
        batting_row_y += row_h

    # ---------- Right top box: rotation ----------
    draw_box_frame("ROTATION (5)", right_x, top_y, right_w, rotation_h, lineup_focus == "pitchers")

    rotation_header_y = top_y + header_offset
    rotation_row_y = top_y + first_row_offset

    # Pitching columns
    px_role   = right_x + 14
    px_name   = right_x + 62
    px_avg    = right_x + 285
    px_obp    = right_x + 345
    px_slg    = right_x + 405
    px_era    = right_x + 465
    px_sta    = right_x + 515

    draw_text("ROLE", px_role, rotation_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("NAME", px_name, rotation_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("AVG-", px_avg, rotation_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("OBP-", px_obp, rotation_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("SLG-", px_slg, rotation_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("ERA",  px_era, rotation_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("STA",  px_sta, rotation_header_y, (180, 210, 255), SMALL_FONT)

    for i in range(5):
        pitcher = rotation_slots[i] if i < len(rotation_slots) else None
        if pitcher and not is_empty_slot(pitcher):
            pitcher.role = "SP"
        is_active = (
            pitcher and lineup_plan and pitcher.name == lineup_plan.starter_name
        )
        draw_pitcher_row(
            right_x + 10,
            rotation_row_y,
            right_w - 20,
            pitcher,
            i == selection_index["lineup_pitchers"],
            lineup_focus == "pitchers",
            show_salary=False,
            is_active=is_active
        )


        rotation_row_y += row_h

    # ---------- Right bottom box: relievers ----------
    draw_box_frame("RELIEF / CLOSERS", right_x, relief_y, right_w, relief_h, lineup_focus == "pitchers")

    relief_header_y = relief_y + header_offset
    relief_row_y = relief_y + first_row_offset

    draw_text("ROLE", px_role, relief_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("NAME", px_name, relief_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("AVG-", px_avg, relief_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("OBP-", px_obp, relief_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("SLG-", px_slg, relief_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("ERA",  px_era, relief_header_y, (180, 210, 255), SMALL_FONT)
    draw_text("STA",  px_sta, relief_header_y, (180, 210, 255), SMALL_FONT)

    for j, pitcher in enumerate(relief_pitchers[:9]):
        overall_idx = j + 5

        if pitcher == user_team.middle_reliever:
            pitcher.role = "MR"
        elif pitcher == user_team.closer:
            pitcher.role = "CL"
        elif pitcher and not is_empty_slot(pitcher):
            pitcher.role = "RP"
        is_active = False
        if lineup_plan and lineup_plan.reliever_names and pitcher:
            if pitcher.name in lineup_plan.reliever_names:
                is_active = True
        draw_pitcher_row(
            right_x + 10,
            relief_row_y,
            right_w - 20,
            pitcher,
            overall_idx == selection_index["lineup_pitchers"],
            lineup_focus == "pitchers",
            show_salary=False,
            is_active=is_active
        )

        relief_row_y += row_h

    draw_text(status_message, 30, HEIGHT - 28, (255, 210, 90), SMALL_FONT)
def draw_player_detail():
    p = player_detail
    screen.fill((10, 14, 28))
    draw_text("PLAYER DETAIL", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_text("M = back", 30, 68, (190, 190, 190))
    if not p:
        return
    draw_box_frame(short_name(p.name, 25), 30, 110, 1180, 700, False)
    left = 60
    y = 165
    draw_text(f"Name: {p.name}", left, y, (230, 230, 230), HEADER_FONT)
    y += 42
    injury_msg = player_injury_text(p)
    if injury_msg:
        draw_text(injury_msg, left, y, (255, 120, 120), HEADER_FONT)
        y += 38
    if hasattr(p, "ops"):
        draw_text(f"Position: {p.position}   Age: {getattr(p, 'age', 'N/A')}   B/T: {getattr(p, 'bats', 'R')}/{getattr(p, 'throws', 'R')}", left, y)
        y += 30
        draw_text(f"AVG: {player_avg_text(p)}   OBP: {player_obp_text(p)}   SLG: {player_slg_text(p)}", left, y)
        y += 30
        draw_text(f"Hits: {p.hits}   2B: {p.doubles}   3B: {p.triples}   HR: {p.homeruns}   RBI: {p.rbi}", left, y)
        y += 30
        draw_text(f"Walks: {p.walks}   SO: {p.strikeouts}   Games: {p.season_games}", left, y)
        y += 30
        draw_text(f"Coach improvement: {p.coach_bonus_string() or 'None'}", left, y, (120, 255, 140))
    elif hasattr(p, "average_minus"):
        draw_text(f"Role: {p.role}   Age: {getattr(p, 'age', 'N/A')}   Throws: {getattr(p, 'throws', 'R')}", left, y)
        y += 30
        draw_text(f"AVG-: {p.display_average_minus}   OBP-: {p.display_obp_minus}   SLG-: {p.display_slugging_minus}", left, y)
        y += 30
        draw_text(f"ERA: {p.era}   IP: {p.innings_pitched_text}   SO: {p.strikeouts}   BB: {p.walks}", left, y)
        y += 30
        draw_text(f"Stamina: {p.stamina_ratio_text}", left, y)
        y += 30
        draw_text(f"Coach improvement: {p.coach_bonus_string() or 'None'}", left, y, (120, 255, 140))
    else:
        draw_text(f"Coach bonuses: {getattr(p, 'avg_boost', 0)} / {getattr(p, 'obp_boost', 0)}", left, y)
        y += 30
    y += 30
    draw_text(f"Salary: {fmt_money(p.salary)}", left, y)
    y += 30
    draw_text(f"Contract length: {getattr(p, 'contract_length', 0)} games", left, y)
    y += 30
    draw_text(f"Games remaining: {getattr(p, 'contract_games_remaining', 0)}", left, y, (255, 210, 90) if getattr(p, 'contract_games_remaining', 99) <= 8 else (230, 230, 230))
def draw_playoff_intro():
    screen.fill((10, 14, 42))

    if not playoff_round_state:
        draw_text("PLAYOFFS", WIDTH // 2 - 90, 60, (255, 215, 0), TITLE_FONT)
        draw_text("No active playoff series.", WIDTH // 2 - 140, 180, (240, 240, 240), HEADER_FONT)
        draw_text("Press M to return to menu.", WIDTH // 2 - 140, 240, (180, 180, 180), SMALL_FONT)
        return

    series = playoff_round_state.get("current_series")
    if not series:
        draw_text("PLAYOFFS", WIDTH // 2 - 90, 60, (255, 215, 0), TITLE_FONT)
        draw_text("No active user playoff series.", WIDTH // 2 - 175, 180, (240, 240, 240), HEADER_FONT)
        draw_text("Press ENTER to continue.", WIDTH // 2 - 135, 240, (180, 180, 180), SMALL_FONT)
        return

    away = series["away_team"]
    home = series["home_team"]
    round_name = playoff_round_state.get("round", season.playoff_round or "Playoffs")

    draw_text(round_name.upper(), WIDTH // 2 - 140, 60, (255, 215, 0), TITLE_FONT)
    draw_text(f"{away.name} @ {home.name}", WIDTH // 2 - 170, 160, (240, 240, 240), HEADER_FONT)

    game_num = series["away_wins"] + series["home_wins"] + 1
    draw_text(f"Game {game_num}", WIDTH // 2 - 55, 220, (120, 255, 140), HEADER_FONT)
    draw_text(
        f"Series: {away.name} {series['away_wins']} - {series['home_wins']} {home.name}",
        WIDTH // 2 - 220, 270, (220, 220, 220), SMALL_FONT
    )
    draw_text("Press ENTER to start", WIDTH // 2 - 120, 360, (180, 180, 180), SMALL_FONT)
def draw_inning_reveal():
    screen.fill((8, 18, 44))

    if not last_playoff_game:
        return

    logs = last_playoff_game["inning_logs"]

    draw_text("GAME REVEAL", 60, 40, (255,215,0), TITLE_FONT)

    y = 120

    for i in range(min(reveal_inning_index, len(logs))):
        inning = logs[i]

        draw_text(f"Inning {inning['inning']}", 60, y, (200,200,255))
        y += 30

        draw_text(f"Top: {inning['top']['runs']} runs", 80, y)
        y += 25
        draw_text(f"Bot: {inning['bottom']['runs']} runs", 80, y)
        y += 40

    draw_text("SPACE = next inning", 60, HEIGHT - 80)
def draw_all_star_page():
    screen.fill((12, 16, 30))
    draw_text("ALL-STAR GAME", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_text("ENTER continue | M menu", 30, 64, (190, 190, 190), SMALL_FONT)
    preview = all_star_preview or build_all_star_preview()
    labels = list(preview.keys())
    draw_box_frame(labels[0], 30, 105, 575, 620, False)
    draw_box_frame(labels[1], 635, 105, 575, 620, False)
    def draw_side(x, side):
        row = 145
        draw_text("LINEUP", x + 12, row, (120, 255, 140), SMALL_FONT)
        row += 28
        for hitter, tm in side["hitters"]:
            draw_text(f"{short_name(hitter.name, 14):14} {short_name(tm.name, 10):10} {player_season_avg_text(hitter)}/{player_season_obp_text(hitter)}/{player_season_slg_text(hitter)}", x + 12, row, (230, 230, 230), TINY_FONT)
            row += 24
        row += 12
        draw_text("PITCHERS", x + 12, row, (120, 255, 140), SMALL_FONT)
        row += 28
        for pitcher, tm in side["pitchers"]:
            draw_text(f"{pitcher.role:>2} {short_name(pitcher.name, 14):14} {short_name(tm.name, 10):10} ERA {pitcher.era:>4} {pitcher.display_average_minus:02d}/{pitcher.display_obp_minus:02d}/{pitcher.display_slugging_minus:02d}", x + 12, row, (230, 230, 230), TINY_FONT)
            row += 24
    draw_side(30, preview[labels[0]])
    draw_side(635, preview[labels[1]])
    draw_text(status_message, 30, HEIGHT - 30, (255, 210, 90))


def draw_contract_negotiation():
    screen.fill((10, 14, 42))
    draw_text("CONTRACT NEGOTIATION", 60, 36, (255, 225, 120), TITLE_FONT)
    draw_budget_top_right(user_team)

    if not active_negotiation:
        draw_text("No active negotiations.", 60, 120, (230, 230, 230), HEADER_FONT)
        return

    p = active_negotiation.player

    draw_text(f"Name: {p.name}", 600, 195, (230, 230, 230), HEADER_FONT)

    # --- TYPE-SAFE DISPLAY (THIS FIXES YOUR CRASH) ---
    if hasattr(p, "position"):  # hitter
        draw_text(
            f"Position: {p.position}   AVG {player_avg_text(p)}   OBP {player_obp_text(p)}   SLG {player_slg_text(p)}",
            600, 235
        )

    elif hasattr(p, "average_minus"):  # pitcher
        draw_text(
            f"Role: {getattr(p, 'role', '--')}   "
            f"AVG- {p.display_average_minus}   "
            f"OBP- {p.display_obp_minus}   "
            f"SLG- {p.display_slugging_minus}",
            600, 235
        )

    elif hasattr(p, "ops_boost"):  # hitting coach
        draw_text(
            f"Hitting Coach   "
            f"AVG +{getattr(p, 'avg_boost', 0)}   "
            f"OBP +{getattr(p, 'obp_boost', 0)}   "
            f"OPS +{getattr(p, 'ops_boost', 0)}",
            600, 235
        )

    else:  # pitching coach
        draw_text(
            f"Pitching Coach   "
            f"AVG- +{getattr(p, 'avg_boost', 0)}   "
            f"OBP- +{getattr(p, 'obp_boost', 0)}   "
            f"SLG- +{getattr(p, 'slg_boost', 0)}",
            600, 235
        )

        # --- CONTRACT INFO ---
    ask_salary = expected_salary(p)

    draw_text(f"Current salary: {fmt_money(getattr(p, 'salary', 0))}", 600, 275)
    draw_text(f"Expected salary: {fmt_money(ask_salary)}", 600, 305, (120, 255, 140))
    draw_text(f"Old contract: {getattr(p, 'contract_length', 0)} games", 600, 335)
    draw_text(f"Games remaining: {getattr(p, 'contract_games_remaining', 0)}", 600, 365)

    # --- OFFER INPUT ---
    draw_text(f"Offer salary: {fmt_money(active_negotiation.salary_offer)}", 600, 425)
    draw_text(f"Offer length: {active_negotiation.games_offer} games", 600, 455)

    draw_text("UP/DOWN adjust salary | LEFT/RIGHT adjust length | ENTER submit | N release to free agency | M menu", 60, 550, (200, 200, 200), SMALL_FONT)

    if active_negotiation.response:
        draw_text(active_negotiation.response, 60, HEIGHT - 40, (255, 210, 90))


def draw_confirm_screen():
    screen.fill((12, 14, 30))
    draw_text("CONFIRM DECISION", 30, 20, (255, 225, 120), TITLE_FONT)
    msg = pending_confirmation["message"] if pending_confirmation else "No pending decision."
    draw_box_frame("ARE YOU SURE?", 200, 220, 880, 240, True)
    draw_text(msg, 250, 300, (230, 230, 230), HEADER_FONT)
    draw_text("Y = confirm   N = cancel", 250, 360, (120, 255, 140), HEADER_FONT)
def draw_media_page():
    screen.fill((10,14,42))

    draw_text("POSTGAME MEDIA", 60, 40, (255,215,0), TITLE_FONT)

    series = playoff_round_state["current_series"]

    stories = generate_playoff_media(series, last_playoff_game)

    y = 140
    for s in stories:
        draw_text(f"- {s}", 60, y)
        y += 40

    draw_text("ENTER to continue", 60, HEIGHT - 80)
def generate_playoff_media(series, game):
    away = series["away_team"]
    home = series["home_team"]

    stories = []

    if game["away_score"] > game["home_score"]:
        stories.append(f"{away.name} take control of the series.")
    else:
        stories.append(f"{home.name} respond with a huge win.")

    if abs(game["away_score"] - game["home_score"]) >= 5:
        stories.append("A dominant performance shakes momentum.")

    stories.append("Analysts: Pitching depth will decide this series.")
    stories.append("Ticket sales surge across the league.")

    return stories
def draw_celebration(team, round_name):
    screen.fill((0,0,0))

    draw_text(f"{team.name} WIN THE {round_name.upper()}!", 60, 120, (255,215,0), TITLE_FONT)

    draw_text("Press ENTER to continue", 60, 400)

def draw_game_day():
    screen.fill((10, 14, 42))
    title = all_games_today[0].get("title", "Game Day Results") if all_games_today else "Game Day Results"
    draw_text(title.upper(), 60, 36, (255, 225, 120), TITLE_FONT)

    label = f"DAY {season.current_day}" if not season.regular_season_over() else "PLAYOFFS"
    draw_text(label, WIDTH // 2 - 40, 100, (240, 240, 240), HEADER_FONT)

    y = 180
    for i, game in enumerate(all_games_today[:12]):
        selected = i == selected_game_index
        color = (255, 225, 120) if selected else (235, 235, 235)

        away_team = game.get("away_team")
        home_team = game.get("home_team")
        away_name = away_team.name if away_team else "Away"
        home_name = home_team.name if home_team else "Home"
        away_score = game.get("away_score", 0)
        home_score = game.get("home_score", 0)

        draw_text(
            (" >" if selected else "  ") + f"{away_name:<10} {away_score} - {home_name:<10} {home_score}",
            78, y, color, HEADER_FONT
        )
        y += 44

    footer = "UP/DOWN = game | S = box score | ENTER = bracket | M = menu" if season and season.regular_season_over() else "UP/DOWN = game | S = box score | ENTER = menu | M = menu"
    draw_text(footer, 60, HEIGHT - 44, (210, 210, 210))
def draw_box_score():
    screen.fill((8, 18, 44))
    draw_text("BOX SCORE", 60, 36, (255, 225, 120), TITLE_FONT)

    if not all_games_today:
        draw_text("No games available.", 60, 100, (220, 220, 220), HEADER_FONT)
        return

    game = all_games_today[selected_game_index]

    draw_text(
        f"{game['away_team'].name} at {game['home_team'].name}",
        60, 86, (240, 240, 240), HEADER_FONT
    )

    # -------- LINE SCORE --------
    start_x = 350
    gap = 70

    for inn in range(1, 10):
        draw_text(str(inn), start_x + (inn - 1) * gap, 176, (180, 210, 255))

    draw_text("R", 1010, 176, (255, 225, 120))

    away_y = 220
    home_y = 265

    draw_text(short_name(game["away_team"].name, 12), 80, away_y, (235, 235, 235), HEADER_FONT)
    draw_text(short_name(game["home_team"].name, 12), 80, home_y, (235, 235, 235), HEADER_FONT)

    for i, r in enumerate(game["away_by_inning"]):
        draw_text(str(r), start_x + i * gap, away_y, (235, 235, 235), HEADER_FONT)

    for i, r in enumerate(game["home_by_inning"]):
        draw_text(str(r), start_x + i * gap, home_y, (235, 235, 235), HEADER_FONT)

    draw_text(str(game["away_score"]), 1010, away_y, (255, 225, 120), HEADER_FONT)
    draw_text(str(game["home_score"]), 1010, home_y, (255, 225, 120), HEADER_FONT)

    winner = game["away_team"].name if game["away_score"] > game["home_score"] else game["home_team"].name
    draw_text(f"Winner: {winner}", 80, 320, (120, 255, 140), HEADER_FONT)

    # -------- PITCHER USAGE --------
    usage = game.get("usage", {})
    away_usage = usage.get(game["away_team"].name, {})
    home_usage = usage.get(game["home_team"].name, {})

    draw_text("Pitching Usage", 80, 360, (255, 225, 120), HEADER_FONT)

    y = 400
    for name, innings in away_usage.items():
        draw_text(f"{short_name(name, 18)} - {innings} inn", 80, y, (230, 230, 230), SMALL_FONT)
        y += 24

    y = 400
    for name, innings in home_usage.items():
        draw_text(f"{short_name(name, 18)} - {innings} inn", 350, y, (230, 230, 230), SMALL_FONT)
        y += 24

    # -------- INNING DETAIL --------
    inning_logs = game.get("inning_logs", [])

    if inning_logs:
        idx = max(0, min(box_inning_index, len(inning_logs) - 1))
        inning_log = inning_logs[idx]

        draw_text(
            f"Inning Detail: {inning_log['inning']}",
            60, 500, (255, 225, 120), HEADER_FONT
        )

        draw_half_inning_panel(
            f"Top {inning_log['inning']} - {game['away_team'].name}",
            inning_log["top"],
            60, 540, 540, 250
        )

        draw_half_inning_panel(
            f"Bot {inning_log['inning']} - {game['home_team'].name}",
            inning_log["bottom"],
            640, 540, 540, 250
        )

    draw_text(
        "LEFT/RIGHT = change game | UP/DOWN = change inning | M = menu",
        60, HEIGHT - 44, (210, 210, 210)
    )

def draw_cpu_roster():
    screen.fill((14, 14, 30))
    cpu_teams = season.teams[1:]
    t = cpu_teams[viewed_team_index]
    draw_text(f"CPU TEAM: {t.name.upper()}", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_text("LEFT/RIGHT = change team | M = menu", 30, 70, (190, 190, 190))
    draw_hitter_list_box("LINEUP", t.lineup, 30, 115, 575, 315, None, False, lineup_numbers=True)
    draw_hitter_list_box("BENCH", t.bench, 30, 450, 575, 225, None, False)
    draw_pitcher_list_box("ROTATION", t.rotation, 635, 115, 575, 260, None, False)
    draw_pitcher_list_box("BULLPEN", t.bullpen, 635, 395, 575, 280, None, False)


def draw_trade_screen():
    screen.fill((14, 14, 30))
    draw_text("TRADES", 30, 20, (255, 225, 120), TITLE_FONT)
    mode_text = "Mode: Incoming Offers" if trade_mode == "incoming" else "Mode: Make Offer"
    draw_text(mode_text, 30, 65, (120, 255, 140), HEADER_FONT)
    draw_text("Q = incoming offers | E = make offer | T = refresh | Y = accept/send | N = reject/cancel | M = menu", 30, 100, (190, 190, 190))
    if trade_mode == "incoming":
        if not current_trade_offer:
            draw_text("No incoming trade offer available.", 30, 160, (230, 230, 230), HEADER_FONT)
        else:
            offer = current_trade_offer
            draw_text(offer["text"], 30, 160, (230, 230, 230), HEADER_FONT)
            draw_text(f"Offer value: {player_value(offer['offer_player']):.1f}", 30, 220)
            draw_text(f"Request value: {player_value(offer['request_player']):.1f}", 30, 250)
    else:
        cpu_team = get_tradeable_cpu_team()
        user_players = get_tradeable_user_players()
        cpu_players = get_tradeable_cpu_players()
        draw_text(f"CPU Team: {cpu_team.name if cpu_team else 'None'}", 30, 150, (120, 255, 140), HEADER_FONT)
        draw_box_frame("YOUR PLAYER", 30, 190, 560, 520, True)
        draw_box_frame("CPU PLAYER", 635, 190, 560, 520, True)
        if user_players:
            u = user_players[clamp_index(selected_trade_user_player, len(user_players))]
            draw_text(f"> {u.name}", 50, 240, (255, 225, 120), HEADER_FONT)
            open_lines = [f"Salary {fmt_money_short(u.salary)}", f"Value {player_value(u):.1f}"]
            yy = 280
            for line in open_lines:
                draw_text(line, 50, yy)
                yy += 28
        if cpu_players:
            c = cpu_players[clamp_index(selected_trade_cpu_player, len(cpu_players))]
            draw_text(f"> {c.name}", 655, 240, (255, 225, 120), HEADER_FONT)
            yy = 280
            for line in [f"Salary {fmt_money_short(c.salary)}", f"Value {player_value(c):.1f}"]:
                draw_text(line, 655, yy)
                yy += 28
    draw_text(status_message, 30, HEIGHT - 30, (255, 210, 90))

def draw_series_update(series):
    screen.fill((10, 14, 42))

    if not series:
        draw_text("SERIES UPDATE", 60, 40, (255, 215, 0), TITLE_FONT)
        draw_text("No active series.", 60, 140, (230, 230, 230), HEADER_FONT)
        draw_text("Press ENTER to continue.", 60, 200, (180, 180, 180), SMALL_FONT)
        return

    away = series["away_team"]
    home = series["home_team"]
    round_name = playoff_round_state["round"] if playoff_round_state else (season.playoff_round or "Playoffs")

    draw_text(f"{round_name.upper()} SERIES UPDATE", 40, 30, (255, 215, 0), TITLE_FONT)
    draw_text(f"{away.name} vs {home.name}", 60, 120, (240, 240, 240), HEADER_FONT)
    draw_text(f"Series Score: {away.name} {series['away_wins']} - {series['home_wins']} {home.name}", 60, 170, (120, 255, 140), HEADER_FONT)

    if last_playoff_game:
        draw_text(
            f"Latest: {away.name} {last_playoff_game['away_score']} - {last_playoff_game['home_score']} {home.name}",
            60, 240, (230, 230, 230), HEADER_FONT
        )

    eliminated = (
        series["away_wins"] >= series["wins_needed"] or
        series["home_wins"] >= series["wins_needed"]
    )
    draw_text(
        "Press ENTER to advance." if eliminated else "Press ENTER for the next lineup screen.",
        60, 330, (180, 180, 180), SMALL_FONT
    )
def draw_world_series_champions_screen():
    screen.fill((6, 8, 24))

    if WORLD_SERIES_CHAMPIONS_SURF is not None:
        img = WORLD_SERIES_CHAMPIONS_SURF
        iw, ih = img.get_width(), img.get_height()
        scale = min(WIDTH / max(1, iw), HEIGHT / max(1, ih))
        new_size = (max(1, int(iw * scale)), max(1, int(ih * scale)))
        scaled = pygame.transform.smoothscale(img, new_size)
        x = (WIDTH - scaled.get_width()) // 2
        y = (HEIGHT - scaled.get_height()) // 2
        screen.blit(scaled, (x, y))
    else:
        draw_text("WORLD SERIES CHAMPIONS!", 120, 120, (255, 225, 120), TITLE_FONT)

    banner = f"{user_team.name.upper()} WIN THE WORLD SERIES!"
    prompt = "ENTER = awards | M = menu"

    shadow = HEADER_FONT.render(banner, True, (0, 0, 0))
    screen.blit(shadow, (42, HEIGHT - 88))
    screen.blit(HEADER_FONT.render(banner, True, (255, 245, 180)), (40, HEIGHT - 90))

    screen.blit(SMALL_FONT.render(prompt, True, (255, 255, 255)), (40, HEIGHT - 52))


def draw_awards_screen():
    screen.fill((16, 16, 32))
    draw_text("SEASON AWARDS", 30, 20, (255, 225, 120), TITLE_FONT)
    draw_text("M = menu | N = next season", 30, 70, (190, 190, 190))
    if not current_awards:
        return
    y = 150
    for label, player in [("MVP", current_awards["mvp"]), ("Batting Title", current_awards["batting"])]:
        if player is None:
            text = f"{label}: None"
        else:
            text = (
                f"{label}: {award_name(player)} | AVG: {award_hitter_avg(player):.3f} "
                f"OBP: {award_hitter_obp(player):.3f} SLG: {award_hitter_slg(player):.3f} "
                f"HR: {award_hitter_hr(player)} RBI: {award_hitter_rbi(player)}"
            )
        draw_text(text, 60, y, (230, 230, 230), HEADER_FONT)
        y += 48
    cy = current_awards["cy"]
    if cy is None:
        text = "Cy Young: None"
    else:
        text = (
            f"Cy Young: {award_name(cy)} | ERA: {award_pitcher_era(cy):.2f} "
            f"WHIP: {award_pitcher_whip(cy):.2f} K: {award_pitcher_strikeouts(cy)} "
            f"IP: {award_pitcher_ip_text(cy)}"
        )
    draw_text(text, 60, y, (230, 230, 230), HEADER_FONT)


def draw_name_input():
    screen.fill((16, 16, 32))
    draw_text("ENTER YOUR TEAM NAME", 60, 90, (255, 225, 120), TITLE_FONT)
    draw_text(typed_team_name if typed_team_name else "_", 60, 170, (240, 240, 240), TITLE_FONT)
    draw_text("TYPE A NAME AND PRESS ENTER", 60, 240, (180, 210, 255), HEADER_FONT)


def draw_standings():
    screen.fill((16, 16, 32))
    draw_text("LEAGUE STANDINGS", 40, 28, (255, 225, 120), TITLE_FONT)
    divisions = sorted({t.division for t in season.teams})
    xs = [40, 650, 40, 650]
    ys = [90, 90, 420, 420]
    for di, division in enumerate(divisions[:4]):
        draw_text(f"{division.upper()} DIVISION", xs[di], ys[di], (180, 210, 255), HEADER_FONT)
        y = ys[di] + 40
        for idx, team in enumerate(season.division_standings(division), start=1):
            gp = team.wins + team.losses
            pct = team.wins / gp if gp > 0 else 0.0
            row = f"{idx:>2}. {team.name:<16} {team.wins:>2}-{team.losses:<2}  {pct:.3f}"
            color = (120, 255, 140) if team == user_team else (235, 235, 235)
            draw_text(row, xs[di], y, color, BODY_FONT)
            y += 26
    draw_text("C = CPU rosters | P = playoff bracket | M = menu", 40, HEIGHT - 34, (180, 180, 180))



def playoff_round_title(round_key):
    return {
        "Divisional": "DIVISIONAL ROUND",
        "Pennant": "PENNANT",
        "World Series": "WORLD SERIES",
        "Complete": "WORLD SERIES",
    }.get(round_key, round_key.upper())


def get_round_matchups_for_display(round_key):
    if round_key == "Divisional":
        if getattr(season, "playoff_history", {}).get("Divisional"):
            return [(r["away_team"], r["home_team"], r["winner"], r.get("series_text", "1-0")) for r in season.playoff_history["Divisional"]]
        seeds = getattr(season, "playoff_seeds", [])
        if len(seeds) >= 8:
            return [(seeds[0], seeds[7], None, "0-0"), (seeds[1], seeds[6], None, "0-0"), (seeds[2], seeds[5], None, "0-0"), (seeds[3], seeds[4], None, "0-0")]
    if round_key == "Pennant":
        if getattr(season, "playoff_history", {}).get("Pennant"):
            return [(r["away_team"], r["home_team"], r["winner"], r.get("series_text", "2-0")) for r in season.playoff_history["Pennant"]]
        if season.playoff_round == "Pennant":
            return [(a, h, None, "0-0") for a, h in season.playoff_matchups]
    if round_key == "World Series":
        if getattr(season, "playoff_history", {}).get("World Series"):
            return [(r["away_team"], r["home_team"], r["winner"], r.get("series_text", "2-0")) for r in season.playoff_history["World Series"]]
        if season.playoff_round == "World Series":
            return [(a, h, None, "0-0") for a, h in season.playoff_matchups]
    return []


def get_selected_playoff_result():
    if season.playoff_round is None:
        return None
    round_results = getattr(season, "playoff_history", {}).get(season.playoff_round, [])
    if not round_results:
        return None
    idx = clamp_index(playoff_selected_matchup, len(round_results))
    return round_results[idx] if round_results else None


def current_playoff_matchup_rects():
    if season.playoff_round is None:
        return []
    count = len(season.playoff_matchups) if season.playoff_matchups else len(getattr(season, "playoff_history", {}).get(season.playoff_round, []))
    rects = []
    y = 545
    for i in range(count):
        rects.append(pygame.Rect(780, y + i * 58, 390, 46))
    return rects

def draw_playoff_bracket():
    screen.fill((8, 16, 48))
    line_color = (80, 200, 255)
    dim_line = (45, 90, 140)
    gold = (255, 225, 120)
    white = (235, 235, 235)
    green = (120, 255, 140)
    pulse = 0.55 + 0.45 * ((pygame.time.get_ticks() % 1000) / 1000.0)
    pulse_color = (
        min(255, int(line_color[0] + 90 * pulse)),
        min(255, int(line_color[1] + 40 * pulse)),
        min(255, int(line_color[2] + 20 * pulse)),
    )

    draw_text("PLAYOFF BRACKET", 50, 28, gold, TITLE_FONT)
    draw_text("DIVISIONAL ROUND", 90, 95, gold, HEADER_FONT)
    draw_text("PENNANT", 430, 95, gold, HEADER_FONT)
    draw_text("WORLD SERIES", 760, 95, gold, HEADER_FONT)
    draw_text("LEFT/RIGHT or CLICK = select matchup | ENTER = advance | S = box score | M = menu", 50, HEIGHT - 32, (210, 210, 210), SMALL_FONT)

    if season.playoff_round is None and not getattr(season, "playoff_seeds", None):
        draw_text("Regular season must end before the bracket is seeded.", 60, 165, white, HEADER_FONT)
        return

    divisional = get_round_matchups_for_display("Divisional")
    pennant = get_round_matchups_for_display("Pennant")
    finals = get_round_matchups_for_display("World Series")

    # background panels
    for rect in [pygame.Rect(40, 130, 700, 610), pygame.Rect(760, 130, 430, 610)]:
        pygame.draw.rect(screen, (15, 22, 42), rect, border_radius=8)
        pygame.draw.rect(screen, (75, 95, 135), rect, 2, border_radius=8)

    # coordinates
    div_y = [180, 300, 470, 590]
    pen_y = [250, 530]
    ws_y = 390

    # divisional column
    for idx, matchup in enumerate(divisional):
        away, home, winner, series_text = matchup
        top_y = div_y[idx]
        bottom_y = top_y + 42
        selected = season.playoff_round in ("Divisional", "Complete") and idx == playoff_selected_matchup and (season.playoff_round == "Divisional" or season.playoff_round == "Complete")
        row_color = gold if selected else white
        draw_text(f"({idx + 1}) {away.name[:12]}", 62, top_y, row_color, BODY_FONT)
        draw_text(f"({8 - idx}) {home.name[:12]}", 62, bottom_y, row_color, BODY_FONT)
        sc = series_text if winner else "0-0"
        draw_text(sc, 225, top_y + 21, green if winner else (170, 185, 205), BODY_FONT)
        active_line = pulse_color if selected else (line_color if winner else dim_line)
        pygame.draw.line(screen, active_line, (210, top_y + 8), (260, top_y + 8), 3)
        pygame.draw.line(screen, active_line, (210, bottom_y + 8), (260, bottom_y + 8), 3)
        pygame.draw.line(screen, active_line, (260, top_y + 8), (260, bottom_y + 8), 3)
        pygame.draw.line(screen, active_line, (260, (top_y + bottom_y)//2 + 8), (340, (top_y + bottom_y)//2 + 8), 3)
        if winner:
            draw_text(winner.name[:13], 348, (top_y + bottom_y)//2 - 4, green, BODY_FONT)

    # pennant column
    for idx, matchup in enumerate(pennant):
        away, home, winner, series_text = matchup
        top_y = pen_y[idx]
        bottom_y = top_y + 54
        selected = season.playoff_round == "Pennant" and idx == playoff_selected_matchup
        row_color = gold if selected else white
        draw_text(away.name[:14], 392, top_y, row_color, BODY_FONT)
        draw_text(home.name[:14], 392, bottom_y, row_color, BODY_FONT)
        sc = series_text if winner else "0-0"
        draw_text(sc, 550, top_y + 26, green if winner else (170, 185, 205), BODY_FONT)
        active_line = pulse_color if selected else (line_color if winner else dim_line)
        pygame.draw.line(screen, active_line, (535, top_y + 8), (585, top_y + 8), 3)
        pygame.draw.line(screen, active_line, (535, bottom_y + 8), (585, bottom_y + 8), 3)
        pygame.draw.line(screen, active_line, (585, top_y + 8), (585, bottom_y + 8), 3)
        pygame.draw.line(screen, active_line, (585, (top_y + bottom_y)//2 + 8), (665, (top_y + bottom_y)//2 + 8), 3)
        if winner:
            draw_text(winner.name[:15], 673, (top_y + bottom_y)//2 - 4, green, BODY_FONT)

    # world series column
    if finals:
        away, home, winner, series_text = finals[0]
        selected = season.playoff_round == "World Series" and playoff_selected_matchup == 0
        row_color = gold if selected else white
        draw_text(away.name[:15], 735, ws_y, row_color, BODY_FONT)
        draw_text(home.name[:15], 735, ws_y + 56, row_color, BODY_FONT)
        sc = series_text if winner else "0-0"
        draw_text(sc, 900, ws_y + 28, green if winner else (170, 185, 205), BODY_FONT)
        active_line = pulse_color if selected else (line_color if winner else dim_line)
        pygame.draw.line(screen, active_line, (885, ws_y + 8), (935, ws_y + 8), 3)
        pygame.draw.line(screen, active_line, (885, ws_y + 64), (935, ws_y + 64), 3)
        pygame.draw.line(screen, active_line, (935, ws_y + 8), (935, ws_y + 64), 3)
        pygame.draw.line(screen, active_line, (935, ws_y + 36), (1015, ws_y + 36), 3)
        if winner:
            draw_text(winner.name[:15], 1022, ws_y + 24, green, BODY_FONT)

    # champion + mvp sidebar
    pygame.draw.rect(screen, (19, 28, 52), (780, 160, 390, 150), border_radius=8)
    pygame.draw.rect(screen, gold, (780, 160, 390, 150), 2, border_radius=8)
    draw_text("POSTSEASON SNAPSHOT", 800, 180, gold, HEADER_FONT)
    draw_text(f"Current Round: {playoff_round_title(season.playoff_round or 'Divisional')}", 800, 220, green, BODY_FONT)
    if season.champion:
        draw_text(f"Champion: {season.champion.name}", 800, 252, white, HEADER_FONT)
    else:
        draw_text("Champion: TBD", 800, 252, white, HEADER_FONT)

    pygame.draw.rect(screen, (19, 28, 52), (780, 330, 390, 170), border_radius=8)
    pygame.draw.rect(screen, (75, 95, 135), (780, 330, 390, 170), 2, border_radius=8)
    draw_text("PLAYOFF MVP", 800, 350, gold, HEADER_FONT)
    mvp = getattr(season, "playoff_mvp", None)
    if mvp:
        draw_text(short_name(mvp.name, 24), 800, 390, white, HEADER_FONT)
        if hasattr(mvp, "ops"):
            draw_text(f"AVG {season_avg(mvp):.3f}  HR {getattr(mvp, 'homeruns', 0)}  RBI {getattr(mvp, 'rbi', 0)}", 800, 425, green, BODY_FONT)
        else:
            draw_text(f"ERA {getattr(mvp, 'era', 0.0):.2f}  K {getattr(mvp, 'strikeouts', 0)}  IP {getattr(mvp, 'innings_pitched_text', '0.0')}", 800, 425, green, BODY_FONT)
    else:
        draw_text("No playoff MVP yet.", 800, 395, white, BODY_FONT)

    pygame.draw.rect(screen, (19, 28, 52), (780, 520, 390, 180), border_radius=8)
    pygame.draw.rect(screen, (75, 95, 135), (780, 520, 390, 180), 2, border_radius=8)
    draw_text("CLICKABLE MATCHUPS", 800, 540, gold, HEADER_FONT)
    active_results = season.playoff_matchups if season.playoff_matchups else []
    if season.playoff_round and season.playoff_round != "Complete":
        for i, (away, home) in enumerate(active_results):
            rect = pygame.Rect(790, 545 + i * 58, 370, 44)
            pygame.draw.rect(screen, (27, 37, 67), rect, border_radius=6)
            border = gold if i == playoff_selected_matchup else (75, 95, 135)
            pygame.draw.rect(screen, border, rect, 2, border_radius=6)
            draw_text(f"{away.name[:12]} vs {home.name[:12]}", rect.x + 12, rect.y + 12, white if i != playoff_selected_matchup else gold, BODY_FONT)
    elif season.champion:
        draw_text("Bracket complete.", 800, 585, white, BODY_FONT)
        draw_text(f"Winner: {season.champion.name}", 800, 620, green, HEADER_FONT)


def draw_menu():
    screen.fill((16, 16, 32))
    gold = (255, 225, 120)
    white = (240, 240, 240)
    green = (120, 255, 140)
    gray = (225, 225, 225)

    draw_text("MLB PRO MANAGER", 60, 40, gold, TITLE_FONT)
    draw_text(f"Team: {user_team.name} | Year {season.year}", 60, 100, white, HEADER_FONT)

    lines = [
        "ENTER = play next day / next playoff round",
        "L = lineup page",
        "R = roster management",
        "H = free agent portal",
        "T = trades",
        "D = game day results",
        "B = box score",
        "S = standings",
        "P = playoff bracket",
        "C = CPU rosters",
        "A = awards",
        "G = global scouting",
        "F = minor league farm",
    ]

    y = 165
    for line in lines:
        draw_text(line, 60, y, gray, HEADER_FONT)
        y += 30

    if not season.regular_season_over():
        season_line = f"Remaining regular season days: {season.remaining_days()}"
    else:
        season_line = "Regular season complete. Press ENTER to advance playoffs."

    # Put this directly under the franchise culture line
    draw_text(season_line, 60, y + 8, green, HEADER_FONT)
    draw_text(status_message, 60, y + 50, (255, 210, 90), HEADER_FONT)

    draw_box_frame("LEAGUE NEWS", 700, 120, 510, 320, False)
    news_y = 165
    for story in news_feed.top(8):
        draw_text("- " + story[:64], 720, news_y, (230, 230, 230), SMALL_FONT)
        news_y += 34

    draw_box_frame("FRANCHISE HISTORY", 700, 470, 510, 210, False)
    hist_y = 515
    recent_history = [
        story for story in franchise_history
        if "Pennant winner" in story or "World Series winner" in story
    ][-5:] if franchise_history else []

    if recent_history:
        for story in reversed(recent_history):
            draw_text("- " + story[:64], 720, hist_y, (230, 230, 230), SMALL_FONT)
            hist_y += 30
    else:
        draw_text("No pennant or World Series winners yet.", 720, hist_y, (180, 180, 180), SMALL_FONT)

# --------------------------------------------------
# main loop
# --------------------------------------------------
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            continue

        if event.type == pygame.MOUSEBUTTONDOWN:
            if game_state == "playoffs" and event.button == 1:
                for idx, rect in enumerate(current_playoff_matchup_rects()):
                    if rect.collidepoint(event.pos):
                        playoff_selected_matchup = idx
                        break
            continue

        if event.type != pygame.KEYDOWN:
            continue

        # --------------------------------------------------
        # global hotkeys
        # --------------------------------------------------
        if event.key == pygame.K_F5:
            save_current_game()
            continue
        if event.key == pygame.K_F9:
            load_saved_game()
            if season is not None and user_team is not None:
                game_state = "menu"
            continue
        # --------------------------------------------------
        # minor league farm
        # --------------------------------------------------
        elif game_state == "minor_league_farm":
            if farm_name_editing:
                if event.key == pygame.K_RETURN:
                    ok, msg = rename_farm(user_team, farm_name_text)
                    status_message = msg
                    farm_name_editing = False
                    farm_name_text = ""

                elif event.key == pygame.K_ESCAPE:
                    farm_name_editing = False
                    farm_name_text = ""
                    status_message = "Rename canceled."

                elif event.key == pygame.K_BACKSPACE:
                    farm_name_text = farm_name_text[:-1]

                else:
                    if event.unicode and len(farm_name_text) < 28:
                        farm_name_text += event.unicode

            else:
                if event.key == pygame.K_m:
                    game_state = "menu"

                elif event.key == pygame.K_n:
                    ensure_farm_state(user_team)
                    farm_name_editing = True
                    farm_name_text = user_team.minor_league_farm.team_name

                elif pygame.K_1 <= event.key <= pygame.K_6:
                    idx = event.key - pygame.K_1
                    ok, msg = hire_farm_coach(user_team, idx)
                    status_message = msg
        # --------------------------------------------------
        # title screen
        # --------------------------------------------------
        if game_state == "title_screen":
            if event.key == pygame.K_UP:
                title_screen_selection = max(0, title_screen_selection - 1)
            elif event.key == pygame.K_DOWN:
                title_screen_selection = min(1, title_screen_selection + 1)
            elif event.key == pygame.K_RETURN:
                if title_screen_selection == 0:
                    typed_team_name = ""
                    status_message = "Enter your team name."
                    game_state = "name_input"
                else:
                    if has_save_file():
                        load_saved_game()
                        if season is not None and user_team is not None:
                            game_state = "menu"
                    else:
                        status_message = "No save file found."
            continue

        # --------------------------------------------------
        # name input
        # --------------------------------------------------
        if game_state == "name_input":
            if event.key == pygame.K_RETURN and typed_team_name.strip():
                season = Season(typed_team_name.strip())
                user_team = season.user_team
                for idx, tm in enumerate(season.teams):
                    tm.budget = 165_000_000 if idx == 0 else 200_000_000
                free_agent_hitters, free_agent_pitchers = generate_free_agents()
                free_agent_hitting_coaches, free_agent_pitching_coaches = generate_coach_markets()
                refresh_trade_offer()
                refresh_news()
                lineup_plan = build_lineup_plan(user_team)
                game_state = "menu"
            elif event.key == pygame.K_BACKSPACE:
                typed_team_name = typed_team_name[:-1]
            elif len(typed_team_name) < 16 and event.unicode.isprintable():
                typed_team_name += event.unicode
            continue

        # --------------------------------------------------
        # global menu access
        # --------------------------------------------------
        if event.key == pygame.K_m and game_state not in {"title_screen", "name_input", "confirm"}:
            if game_state == "player_detail":
                game_state = "roster"
            else:
                game_state = "menu"
            continue
        # --------------------------------------------------
        # menu
        # --------------------------------------------------
        if game_state == "menu":
            if event.key == pygame.K_RETURN:
                if run_pregame_contract_check():
                    continue
                if season.regular_season_over():
                    if season.playoff_round == "Complete":
                        current_awards = snapshot_awards(compute_awards(season.teams))
                        game_state = "world_series_champions" if season.champion == user_team else "awards"
                    else:
                        play_next_playoff_round()
                        if season.playoff_round == "Complete":
                            current_awards = snapshot_awards(compute_awards(season.teams))
                            game_state = "world_series_champions" if season.champion == user_team else "awards"
                        elif playoff_round_state and playoff_round_state.get("current_series"):
                            lineup_plan = build_lineup_plan(user_team)
                            status_message = "Set your lineup for the next playoff game."
                            game_state = "lineup"
                        else:
                            game_state = "playoffs"
                else:
                    lineup_plan = build_lineup_plan(user_team)
                    status_message = "Set your lineup for today's game."
                    game_state = "lineup"

            elif event.key == pygame.K_l:
                lineup_plan = build_lineup_plan(user_team)
                game_state = "lineup"
            elif event.key == pygame.K_g:
                game_state = "scouting"
            elif event.key == pygame.K_r:
                game_state = "roster"
            elif event.key == pygame.K_h:
                game_state = "free_agents"
            elif event.key == pygame.K_t:
                game_state = "trades"
            elif event.key == pygame.K_f:
                ensure_farm_state(user_team)
                game_state = "minor_league_farm"
            elif event.key == pygame.K_d:
                game_state = "game_day"
            elif event.key == pygame.K_b:
                game_state = "box_score"
            elif event.key == pygame.K_s:
                game_state = "standings"
            elif event.key == pygame.K_p:
                game_state = "playoffs"
            elif event.key == pygame.K_c:
                game_state = "cpu_roster"
            elif event.key == pygame.K_a:
                current_awards = snapshot_awards(compute_awards(season.teams))
                game_state = "awards"
            continue

        # --------------------------------------------------
        # playoff intro
        # --------------------------------------------------
        if game_state == "playoff_intro":
            if event.key == pygame.K_RETURN:
                if not playoff_round_state or not playoff_round_state.get("current_series"):
                    status_message = "No active playoff series."
                    game_state = "playoffs"
                else:
                    series = playoff_round_state["current_series"]
                    game = simulate_game_with_box(series["away_team"], series["home_team"])
                    last_playoff_game = game
                    reveal_inning_index = 0
                    game_state = "inning_reveal"
            continue

        # --------------------------------------------------
        # inning reveal
        # --------------------------------------------------
        if game_state == "inning_reveal":
            if event.key == pygame.K_SPACE:
                if not last_playoff_game:
                    game_state = "playoffs"
                else:
                    reveal_inning_index += 1
                    if reveal_inning_index > len(last_playoff_game["inning_logs"]):
                        game_state = "media"
            continue

        # --------------------------------------------------
        # media page
        # --------------------------------------------------
        if game_state == "media":
            if event.key == pygame.K_RETURN:
                game_state = "series_update"
            continue

        # --------------------------------------------------
        # series update
        # --------------------------------------------------
        if game_state == "series_update":
            if event.key == pygame.K_RETURN:
                if not playoff_round_state or not playoff_round_state.get("current_series") or not last_playoff_game:
                    status_message = "No active playoff series."
                    game_state = "playoffs"
                else:
                    series = playoff_round_state["current_series"]
                    away_team = series["away_team"]
                    home_team = series["home_team"]

                    winner = away_team if last_playoff_game["away_score"] > last_playoff_game["home_score"] else home_team
                    if winner == away_team:
                        series["away_wins"] += 1
                    else:
                        series["home_wins"] += 1

                    game_data = {
                        "title": f"{playoff_round_state['round']} Results",
                        "away_team": away_team,
                        "home_team": home_team,
                        "away_score": last_playoff_game["away_score"],
                        "home_score": last_playoff_game["home_score"],
                        "away_by_inning": last_playoff_game["away_by_inning"],
                        "home_by_inning": last_playoff_game["home_by_inning"],
                        "usage": last_playoff_game["usage"],
                        "inning_logs": last_playoff_game["inning_logs"],
                        "winner": winner,
                    }

                    series["series_games"].append(game_data)
                    all_games_today.append(game_data)
                    selected_game_index = max(0, len(all_games_today) - 1)

                    finalize_team_game(away_team, last_playoff_game["usage"].get(away_team.name, {}))
                    finalize_team_game(home_team, last_playoff_game["usage"].get(home_team.name, {}))
                    maybe_apply_random_injury(user_team, allow_playoffs=True)

                    last_playoff_game["winner"] = winner

                    if series["away_wins"] >= series["wins_needed"] or series["home_wins"] >= series["wins_needed"]:
                        game_state = "celebration"
                    else:
                        lineup_plan = build_lineup_plan(user_team)
                        status_message = f"Series now {series['away_wins']}-{series['home_wins']}. Set your lineup for the next playoff game."
                        game_state = "lineup"
            continue

        # --------------------------------------------------
        # celebration
        # --------------------------------------------------
        if game_state == "celebration":
            if event.key == pygame.K_RETURN:
                if playoff_round_state and playoff_round_state.get("current_series"):
                    playoff_round_state["current_user_series_index"] += 1
                    idx = playoff_round_state["current_user_series_index"]
                    playoff_round_state["current_series"] = (
                        playoff_round_state["user_series_states"][idx]
                        if idx < len(playoff_round_state["user_series_states"])
                        else None
                    )

                if advance_playoff_round_if_ready():
                    if season.playoff_round == "Complete":
                        current_awards = snapshot_awards(compute_awards(season.teams))
                        game_state = "awards"
                    else:
                        initialize_playoff_round_state()
                        if playoff_round_state and playoff_round_state.get("current_series"):
                            lineup_plan = build_lineup_plan(user_team)
                            status_message = "Set your lineup for the next playoff game."
                            game_state = "lineup"
                        else:
                            game_state = "playoffs"
                else:
                    if playoff_round_state and playoff_round_state.get("current_series"):
                        lineup_plan = build_lineup_plan(user_team)
                        status_message = "Set your lineup for the next playoff game."
                        game_state = "lineup"
                    else:
                        game_state = "playoffs"
            continue

        # --------------------------------------------------
        # lineup
        # --------------------------------------------------
        if game_state == "lineup":
            if event.key == pygame.K_RETURN:
                valid_hitters, missing = user_team.validate_lineup_positions()
                if not valid_hitters:
                    status_message = "Missing positions: " + ", ".join(missing)
                else:
                    valid_pitchers, msg = validate_lineup_pitching_plan(user_team, lineup_plan)
                    if not valid_pitchers:
                        status_message = msg
                    else:
                        apply_lineup_plan(user_team, lineup_plan)

                        if season.regular_season_over():
                            if season.playoff_round is None:
                                season.start_playoffs()

                            if playoff_round_state is None or playoff_round_state.get("round") != season.playoff_round:
                                initialize_playoff_round_state()

                            if playoff_round_state and playoff_round_state.get("current_series"):
                                play_next_playoff_game()
                            else:
                                game_state = "playoffs"
                        else:
                            play_next_day()

            elif event.key == pygame.K_a:
                lineup_focus = "batting_order"
            elif event.key == pygame.K_d:
                lineup_focus = "pitchers"
            elif event.key == pygame.K_LEFT:
                lineup_focus = "batting_order"
            elif event.key == pygame.K_RIGHT:
                lineup_focus = "pitchers"
            elif event.key == pygame.K_UP:
                key = "lineup_hitters" if lineup_focus == "batting_order" else "lineup_pitchers"
                items = lineup_plan.batting_order if lineup_focus == "batting_order" else user_team.rotation + user_team.bullpen
                selection_index[key] = clamp_index(selection_index[key] - 1, len(items))
            elif event.key == pygame.K_DOWN:
                key = "lineup_hitters" if lineup_focus == "batting_order" else "lineup_pitchers"
                items = lineup_plan.batting_order if lineup_focus == "batting_order" else user_team.rotation + user_team.bullpen
                selection_index[key] = clamp_index(selection_index[key] + 1, len(items))
            elif event.key == pygame.K_s and lineup_focus == "batting_order":
                idx = selection_index["lineup_hitters"]
                if lineup_pending is None:
                    lineup_pending = idx
                    status_message = f"Selected batting slot {idx + 1}."
                else:
                    lineup_plan.batting_order[idx], lineup_plan.batting_order[lineup_pending] = lineup_plan.batting_order[lineup_pending], lineup_plan.batting_order[idx]
                    lineup_pending = None
                    status_message = "Updated batting order."
            elif event.key == pygame.K_s and lineup_focus == "pitchers":
                pitchers = user_team.rotation + user_team.bullpen
                idx = clamp_index(selection_index["lineup_pitchers"], len(pitchers))
                if pitchers:
                    p = pitchers[idx]
                    if getattr(p, "remaining_stamina", 0) <= 0:
                        status_message = f"{p.name} is out of stamina and cannot pitch."
                    elif not lineup_plan.starter_name:
                        lineup_plan.starter_name = p.name
                    elif not lineup_plan.reliever_names:
                        if p.name != lineup_plan.starter_name:
                            lineup_plan.reliever_names = [p.name]
                    elif len(lineup_plan.reliever_names) == 1:
                        if p.name != lineup_plan.starter_name and p.name != lineup_plan.reliever_names[0]:
                            lineup_plan.reliever_names.append(p.name)
                    else:
                        lineup_plan.starter_name = p.name
                        lineup_plan.reliever_names = []
                    status_message = f"Updated staff assignment with {p.name}."
            elif event.key == pygame.K_i:
                if lineup_focus == "batting_order" and lineup_plan.batting_order:
                    open_player_detail(lineup_plan.batting_order[selection_index["lineup_hitters"]])
                else:
                    pitchers = user_team.rotation + user_team.bullpen
                    if pitchers:
                        open_player_detail(pitchers[selection_index["lineup_pitchers"]])
            continue

        # --------------------------------------------------
        # franchise culture
        # --------------------------------------------------
        if game_state == "franchise_culture":
            ensure_franchise_culture_state(user_team)

            if event.key == pygame.K_UP:
                selection_index["culture_controls"] = max(0, selection_index.get("culture_controls", 0) - 1)
            elif event.key == pygame.K_DOWN:
                selection_index["culture_controls"] = min(1, selection_index.get("culture_controls", 0) + 1)
            elif event.key == pygame.K_a:
                if selection_index.get("culture_controls", 0) == 0:
                    user_team.ticket_price_level = max(1, user_team.ticket_price_level - 1)
                else:
                    user_team.vendor_price_level = max(1, user_team.vendor_price_level - 1)
                recalc_morale(user_team)
                refresh_budget_from_culture(user_team, base_budget=165_000_000)
                status_message = "Franchise pricing updated."
            elif event.key == pygame.K_d:
                if selection_index.get("culture_controls", 0) == 0:
                    user_team.ticket_price_level = min(10, user_team.ticket_price_level + 1)
                else:
                    user_team.vendor_price_level = min(10, user_team.vendor_price_level + 1)
                recalc_morale(user_team)
                refresh_budget_from_culture(user_team, base_budget=165_000_000)
                status_message = "Franchise pricing updated."
            continue

        # --------------------------------------------------
        # scouting
        # --------------------------------------------------
        if game_state == "scouting":
            reports = getattr(user_team, "scouted_prospects", [])

            if event.key == pygame.K_LEFT:
                scouting_focus = "market"
            elif event.key == pygame.K_RIGHT:
                scouting_focus = "reports"
            elif event.key == pygame.K_UP:
                if scouting_focus == "market":
                    selection_index["scouting_market"] = clamp_index(selection_index["scouting_market"] - 1, 3)
                else:
                    selection_index["scouting_reports"] = clamp_index(selection_index["scouting_reports"] - 1, len(reports))
            elif event.key == pygame.K_DOWN:
                if scouting_focus == "market":
                    selection_index["scouting_market"] = clamp_index(selection_index["scouting_market"] + 1, 3)
                else:
                    selection_index["scouting_reports"] = clamp_index(selection_index["scouting_reports"] + 1, len(reports))
            elif event.key == pygame.K_f:
                ok, msg = fire_scout(user_team)
                status_message = msg
            elif event.key in (pygame.K_s, pygame.K_RETURN):
                if scouting_focus == "market":
                    stars = selection_index["scouting_market"] + 1
                    ok, msg = hire_scout(user_team, stars)
                    status_message = msg
                else:
                    if reports:
                        idx = clamp_index(selection_index["scouting_reports"], len(reports))
                        ok, msg = sign_scouted_prospect(user_team, reports[idx])
                        status_message = msg
            continue

        # --------------------------------------------------
        # roster
        # --------------------------------------------------
        if game_state == "roster":
            if event.key == pygame.K_h:
                game_state = "free_agents"
            elif event.key == pygame.K_l:
                lineup_plan = build_lineup_plan(user_team)
                game_state = "lineup"
            elif event.key == pygame.K_1:
                roster_tab = "hitters"; roster_focus = "lineup"; pending_selection = None
            elif event.key == pygame.K_2:
                roster_tab = "pitchers"; roster_pitcher_focus = "rotation"; pending_selection = None
            elif event.key == pygame.K_3:
                roster_tab = "coaches"; roster_focus = "pitching_coach_slot"; pending_selection = None
            elif event.key == pygame.K_4:
                roster_tab = "stats"; roster_focus = "stats_roster"; pending_selection = None
            elif event.key == pygame.K_5:
                roster_tab = "spin_lab"; pending_selection = None
            elif roster_tab == "hitters":
                if event.key == pygame.K_a:
                    roster_focus = "lineup"
                elif event.key == pygame.K_w:
                    roster_focus = "bench"
                elif event.key == pygame.K_f:
                    roster_focus = "minors_hitters"
                elif event.key == pygame.K_LEFT:
                    if roster_focus == "bench":
                        roster_focus = "lineup"
                    elif roster_focus == "minors_hitters":
                        roster_focus = "bench"
                elif event.key == pygame.K_RIGHT:
                    if roster_focus == "lineup":
                        roster_focus = "bench"
                    elif roster_focus == "bench":
                        roster_focus = "minors_hitters"
                elif event.key == pygame.K_UP:
                    move_selection(-1)
                elif event.key == pygame.K_DOWN:
                    move_selection(1)
                elif event.key == pygame.K_s:
                    handle_roster_select()
                elif event.key == pygame.K_x:
                    drop_selected_player()
                elif event.key == pygame.K_c:
                    handle_callup_senddown()
                elif event.key == pygame.K_i:
                    items = hitter_lists()[roster_focus]
                    if items:
                        open_player_detail(items[selection_index[roster_focus]])

            elif roster_tab == "pitchers":
                if event.key == pygame.K_a:
                    roster_pitcher_focus = "rotation"
                elif event.key == pygame.K_w:
                    roster_pitcher_focus = "bullpen"
                elif event.key == pygame.K_f:
                    roster_pitcher_focus = "minors"
                elif event.key == pygame.K_LEFT:
                    if roster_pitcher_focus == "bullpen":
                        roster_pitcher_focus = "rotation"
                    elif roster_pitcher_focus == "minors":
                        roster_pitcher_focus = "bullpen"
                elif event.key == pygame.K_RIGHT:
                    if roster_pitcher_focus == "rotation":
                        roster_pitcher_focus = "bullpen"
                    elif roster_pitcher_focus == "bullpen":
                        roster_pitcher_focus = "minors"
                elif event.key == pygame.K_UP:
                    move_selection(-1)
                elif event.key == pygame.K_DOWN:
                    move_selection(1)
                elif event.key == pygame.K_s:
                    handle_roster_select()
                elif event.key == pygame.K_x:
                    drop_selected_player()
                elif event.key == pygame.K_c:
                    handle_callup_senddown()
                elif event.key == pygame.K_k:
                    if roster_pitcher_focus == "rotation":
                        items = user_team.rotation[:5]
                        idx = selection_index["pitcher_rotation"]
                    elif roster_pitcher_focus == "bullpen":
                        items = user_team.bullpen
                        idx = selection_index["pitcher_bullpen"]
                    else:
                        items = user_team.minors_pitchers
                        idx = selection_index["pitcher_minors"]
                    if 0 <= idx < len(items) and not is_empty_slot(items[idx]) and user_team.pitching_coach:
                        user_team.assign_pitching_coach_to_pitcher(items[idx].name)
                        status_message = f"Pitching coach assigned to {items[idx].name}."
                elif event.key == pygame.K_i:
                    items = pitcher_lists()[roster_pitcher_focus]
                    idx_key = {
                        "rotation": "pitcher_rotation",
                        "bullpen": "pitcher_bullpen",
                        "minors": "pitcher_minors",
                    }[roster_pitcher_focus]
                    if items:
                        open_player_detail(items[selection_index[idx_key]])

            elif roster_tab == "coaches":
                if event.key == pygame.K_a:
                    roster_focus = "pitching_coach_slot"
                elif event.key == pygame.K_w:
                    roster_focus = "pitching_coach_market"
                elif event.key == pygame.K_f:
                    roster_focus = "hitting_coach_slot"
                elif event.key == pygame.K_g:
                    roster_focus = "hitting_coach_market"
                elif event.key == pygame.K_LEFT:
                    if roster_focus == "pitching_coach_market":
                        roster_focus = "pitching_coach_slot"
                    elif roster_focus == "hitting_coach_slot":
                        roster_focus = "pitching_coach_slot"
                    elif roster_focus == "hitting_coach_market":
                        roster_focus = "pitching_coach_market"
                elif event.key == pygame.K_RIGHT:
                    if roster_focus == "pitching_coach_slot":
                        roster_focus = "hitting_coach_slot"
                    elif roster_focus == "pitching_coach_market":
                        roster_focus = "hitting_coach_market"
                    elif roster_focus == "hitting_coach_slot":
                        roster_focus = "hitting_coach_market"
                elif event.key == pygame.K_UP:
                    move_selection(-1)
                elif event.key == pygame.K_DOWN:
                    move_selection(1)
                elif event.key == pygame.K_s:
                    handle_roster_select()
                elif event.key == pygame.K_k:
                    if roster_focus == "pitching_coach_slot" and user_team.pitching_coach:
                        chosen = user_team.cycle_pitching_assignment()
                        status_message = f"Pitching coach assigned to {chosen}." if chosen else "No pitchers available."
                    elif roster_focus == "hitting_coach_slot" and user_team.hitting_coaches:
                        slot = clamp_index(selection_index["hitting_coach_slot"], len(user_team.hitting_coaches))
                        chosen = user_team.cycle_hitting_assignment(slot)
                        status_message = f"Hitting coach {slot + 1} assigned to {chosen}." if chosen else "No hitters available."
                elif event.key == pygame.K_i:
                    items = coach_lists()[roster_focus]
                    if items:
                        open_player_detail(items[selection_index[roster_focus]])

            elif roster_tab == "spin_lab":
                pool = user_team.available_spin_lab_pitchers() if hasattr(user_team, "available_spin_lab_pitchers") else []
                if event.key == pygame.K_UP:
                    selection_index["spin_lab_pool"] = clamp_index(selection_index["spin_lab_pool"] - 1, len(pool))
                elif event.key == pygame.K_DOWN:
                    selection_index["spin_lab_pool"] = clamp_index(selection_index["spin_lab_pool"] + 1, len(pool))
                elif event.key == pygame.K_s and pool:
                    ok, status_message = user_team.toggle_spin_rate_lab_pitcher(pool[selection_index["spin_lab_pool"]].name)
                elif event.key == pygame.K_i and pool:
                    open_player_detail(pool[selection_index["spin_lab_pool"]])

            elif roster_tab == "stats":
                archived = list(getattr(season, "user_stat_history", []))
                stat_views = archived + [{
                    "year": season.year,
                    "roster": [p for p in (user_team.lineup + user_team.bench + user_team.rotation + user_team.bullpen) if not is_empty_slot(p)],
                    "is_current": True,
                }]

                if event.key == pygame.K_LEFT:
                    stats_year_index = clamp_index(stats_year_index - 1, len(stat_views))
                    selection_index["stats_roster"] = 0
                elif event.key == pygame.K_RIGHT:
                    stats_year_index = clamp_index(stats_year_index + 1, len(stat_views))
                    selection_index["stats_roster"] = 0
                elif event.key == pygame.K_UP:
                    roster = stat_views[clamp_index(stats_year_index, len(stat_views))]["roster"]
                    selection_index["stats_roster"] = clamp_index(selection_index["stats_roster"] - 1, len(roster))
                elif event.key == pygame.K_DOWN:
                    roster = stat_views[clamp_index(stats_year_index, len(stat_views))]["roster"]
                    selection_index["stats_roster"] = clamp_index(selection_index["stats_roster"] + 1, len(roster))
                elif event.key == pygame.K_i:
                    view_state = stat_views[clamp_index(stats_year_index, len(stat_views))]
                    roster = view_state["roster"]
                    if roster:
                        selected_item = roster[clamp_index(selection_index["stats_roster"], len(roster))]
                        if not isinstance(selected_item, dict):
                            open_player_detail(selected_item)
                        else:
                            status_message = "Archived seasons use the stats list only."
            continue

        # --------------------------------------------------
        # all-star
        # --------------------------------------------------
        if game_state == "allstar":
            if event.key == pygame.K_RETURN:
                play_all_star_game()
            continue

        # --------------------------------------------------
        # free agents
        # --------------------------------------------------
        if game_state == "free_agents":
            if event.key == pygame.K_1:
                free_agent_tab = "hitters"
            elif event.key == pygame.K_2:
                free_agent_tab = "pitchers"
            elif event.key == pygame.K_UP:
                key = "free_agent_hitters" if free_agent_tab == "hitters" else "free_agent_pitchers"
                market = free_agent_hitters if free_agent_tab == "hitters" else free_agent_pitchers
                selection_index[key] = clamp_index(selection_index[key] - 1, len(market))
            elif event.key == pygame.K_DOWN:
                key = "free_agent_hitters" if free_agent_tab == "hitters" else "free_agent_pitchers"
                market = free_agent_hitters if free_agent_tab == "hitters" else free_agent_pitchers
                selection_index[key] = clamp_index(selection_index[key] + 1, len(market))
            elif event.key in (pygame.K_RETURN, pygame.K_s):
                market = free_agent_hitters if free_agent_tab == "hitters" else free_agent_pitchers
                if market:
                    idx = selection_index["free_agent_hitters" if free_agent_tab == "hitters" else "free_agent_pitchers"]
                    start_free_agent_confirmation(market[idx], free_agent_tab)
            elif event.key == pygame.K_i:
                market = free_agent_hitters if free_agent_tab == "hitters" else free_agent_pitchers
                if market:
                    idx = selection_index["free_agent_hitters" if free_agent_tab == "hitters" else "free_agent_pitchers"]
                    open_player_detail(market[idx])
            continue

        # --------------------------------------------------
        # confirm
        # --------------------------------------------------
        if game_state == "confirm":
            if event.key == pygame.K_y:
                complete_confirmation(True)
            elif event.key == pygame.K_n:
                complete_confirmation(False)
            continue

        # --------------------------------------------------
        # player detail
        # --------------------------------------------------
        if game_state == "player_detail":
            continue

        # --------------------------------------------------
        # contract negotiation
        # --------------------------------------------------
        if game_state == "contract_negotiation":
            if event.key == pygame.K_LEFT:
                active_negotiation.games_offer = max(10, active_negotiation.games_offer - 5)
            elif event.key == pygame.K_RIGHT:
                active_negotiation.games_offer = min(300, active_negotiation.games_offer + 5)
            elif event.key == pygame.K_UP:
                active_negotiation.salary_offer += 250_000
            elif event.key == pygame.K_DOWN:
                active_negotiation.salary_offer = max(750_000, active_negotiation.salary_offer - 250_000)
            elif event.key == pygame.K_RETURN:
                player = active_negotiation.player
                old_salary = getattr(player, "salary", 0)

                if not user_team.can_afford(active_negotiation.salary_offer, outgoing_salary=old_salary):
                    msg = f"Offer rejected: payroll would exceed budget ({fmt_money(user_team.budget)})."
                    active_negotiation.response = msg
                    status_message = msg
                else:
                    accepted, msg = attempt_negotiation(
                        player,
                        active_negotiation.salary_offer,
                        active_negotiation.games_offer
                    )
                    active_negotiation.response = msg
                    if accepted:
                        status_message = msg
                        active_negotiation = None
                        check_user_contracts()
                        game_state = "contract_negotiation" if active_negotiation else "menu"
                    else:
                        status_message = msg
            elif event.key == pygame.K_n:
                release_active_negotiation_to_free_agency()
            elif event.key == pygame.K_m:
                game_state = "menu"
                status_message = "Contract negotiation paused."
            continue

        # --------------------------------------------------
        # game day
        # --------------------------------------------------
        if game_state == "game_day":
            if event.key == pygame.K_UP:
                selected_game_index = clamp_index(selected_game_index - 1, len(all_games_today))
            elif event.key == pygame.K_DOWN:
                selected_game_index = clamp_index(selected_game_index + 1, len(all_games_today))
            elif event.key == pygame.K_s:
                game_state = "box_score"
            elif event.key == pygame.K_RETURN:
                game_state = "playoffs" if season and season.regular_season_over() else "menu"
            continue

        # --------------------------------------------------
        # box score
        # --------------------------------------------------
        if game_state == "box_score":
            if event.key == pygame.K_LEFT:
                selected_game_index = (selected_game_index - 1) % len(all_games_today)
                box_inning_index = 0
            elif event.key == pygame.K_RIGHT:
                selected_game_index = (selected_game_index + 1) % len(all_games_today)
                box_inning_index = 0
            elif event.key == pygame.K_UP:
                box_inning_index = max(0, box_inning_index - 1)
            elif event.key == pygame.K_DOWN:
                game = all_games_today[selected_game_index]
                max_idx = max(0, len(game.get("inning_logs", [])) - 1)
                box_inning_index = min(max_idx, box_inning_index + 1)
            continue

        # --------------------------------------------------
        # standings
        # --------------------------------------------------
        if game_state == "standings":
            if event.key == pygame.K_c:
                game_state = "cpu_roster"
            elif event.key == pygame.K_p:
                game_state = "playoffs"
            continue
        # --------------------------------------------------
        # minor league call-up contract
        # --------------------------------------------------
        if game_state == "minor_callup_contract":
            if event.key == pygame.K_ESCAPE:
                    minor_callup_contract = None
                    game_state = "roster"

            elif event.key == pygame.K_LEFT:
                    minor_contract_days = max(10, minor_contract_days - 10)

            elif event.key == pygame.K_RIGHT:
                    minor_contract_days = min(100, minor_contract_days + 10)

            elif event.key == pygame.K_DOWN:
                    minor_contract_salary = max(250_000, minor_contract_salary - 50_000)

            elif event.key == pygame.K_UP:
                    minor_contract_salary = min(1_500_000, minor_contract_salary + 50_000)

            elif event.key == pygame.K_RETURN:
                    confirm_minor_callup_contract()
        # --------------------------------------------------
        # cpu roster
        # --------------------------------------------------
        if game_state == "cpu_roster":
            if event.key == pygame.K_LEFT:
                viewed_team_index = clamp_index(viewed_team_index - 1, len(season.teams[1:]))
            elif event.key == pygame.K_RIGHT:
                viewed_team_index = clamp_index(viewed_team_index + 1, len(season.teams[1:]))
            continue

        # --------------------------------------------------
        # trades
        # --------------------------------------------------
        if game_state == "trades":
            if event.key == pygame.K_q:
                trade_mode = "incoming"
            elif event.key == pygame.K_e:
                trade_mode = "outgoing"
            elif event.key == pygame.K_t and trade_mode == "incoming":
                refresh_trade_offer()
            elif trade_mode == "incoming":
                if event.key == pygame.K_y and current_trade_offer:
                    cpu = current_trade_offer["cpu_team"]
                    offered = current_trade_offer["offer_player"]
                    requested = current_trade_offer["request_player"]
                    if requested in user_team.bench and offered in cpu.lineup and evaluate_trade_acceptance(cpu, offered, requested):
                        user_team.bench[user_team.bench.index(requested)] = offered
                        cpu.lineup[cpu.lineup.index(offered)] = requested
                        status_message = "Trade accepted."
                    else:
                        status_message = "Trade rejected."
                elif event.key == pygame.K_n:
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
                elif event.key == pygame.K_y and cpu_team and user_players and cpu_players:
                    user_player = user_players[clamp_index(selected_trade_user_player, len(user_players))]
                    cpu_player = cpu_players[clamp_index(selected_trade_cpu_player, len(cpu_players))]
                    if not user_team.can_afford(cpu_player.salary, user_player.salary):
                        accepted = False
                        status_message = "Trade rejected: it would put you over budget."
                    else:
                        accepted = evaluate_user_trade_offer(cpu_team, cpu_player, user_player)
                    if accepted:
                        if user_player in user_team.lineup:
                            user_team.lineup[user_team.lineup.index(user_player)] = cpu_player
                        elif user_player in user_team.bench:
                            user_team.bench[user_team.bench.index(user_player)] = cpu_player
                        elif user_player in user_team.rotation:
                            user_team.rotation[user_team.rotation.index(user_player)] = cpu_player
                        elif user_player in user_team.bullpen:
                            user_team.bullpen[user_team.bullpen.index(user_player)] = cpu_player

                        if cpu_player in cpu_team.lineup:
                            cpu_team.lineup[cpu_team.lineup.index(cpu_player)] = user_player
                        elif cpu_player in cpu_team.bench:
                            cpu_team.bench[cpu_team.bench.index(cpu_player)] = user_player
                        elif cpu_player in cpu_team.rotation:
                            cpu_team.rotation[cpu_team.rotation.index(cpu_player)] = user_player
                        elif cpu_player in cpu_team.bullpen:
                            cpu_team.bullpen[cpu_team.bullpen.index(cpu_player)] = user_player

                        user_team.repair_roster_structure()
                        user_team.refresh_roles()
                        user_team.ensure_batting_order()

                        cpu_team.repair_roster_structure()
                        cpu_team.refresh_roles()
                        cpu_team.ensure_batting_order()
                        user_team.ensure_within_budget()
                        status_message = f"{cpu_team.name} accepted your trade offer."
                    else:
                        status_message = f"{cpu_team.name} rejected your trade offer."
                elif event.key == pygame.K_n:
                    status_message = "Trade offer canceled."
            continue

        # --------------------------------------------------
        # awards
        # --------------------------------------------------
        if game_state == "awards":
            if event.key == pygame.K_n:
                start_next_season()
            continue

        # --------------------------------------------------
        # world series champions
        # --------------------------------------------------
        if game_state == "world_series_champions":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                game_state = "awards"
            elif event.key == pygame.K_n:
                start_next_season()
            continue

        # --------------------------------------------------
        # playoffs
        # --------------------------------------------------
        if game_state == "playoffs":
            if event.key == pygame.K_LEFT:
                count = len(season.playoff_matchups) if season.playoff_matchups else len(getattr(season, "playoff_history", {}).get(season.playoff_round, []))
                playoff_selected_matchup = clamp_index(playoff_selected_matchup - 1, count)
            elif event.key == pygame.K_RIGHT:
                count = len(season.playoff_matchups) if season.playoff_matchups else len(getattr(season, "playoff_history", {}).get(season.playoff_round, []))
                playoff_selected_matchup = clamp_index(playoff_selected_matchup + 1, count)
            elif event.key == pygame.K_RETURN and season.regular_season_over():
                play_next_playoff_round()
                if season.playoff_round == "Complete":
                    current_awards = snapshot_awards(compute_awards(season.teams))
                    game_state = "world_series_champions" if season.champion == user_team else "awards"
                elif playoff_round_state and playoff_round_state.get("current_series"):
                    lineup_plan = build_lineup_plan(user_team)
                    status_message = "Set your lineup for the next playoff game."
                    game_state = "lineup"
            elif event.key == pygame.K_s:
                selected_game_index = clamp_index(playoff_selected_matchup, len(all_games_today))
                if all_games_today:
                    game_state = "box_score"

    # ------------------ draw ------------------

    if game_state == "title_screen":
        draw_title_screen()
    if game_state == "name_input":
        draw_name_input()
    elif game_state == "menu":
        draw_menu()
    elif game_state == "lineup":
        draw_lineup_page()
    elif game_state == "roster":
        draw_user_roster()
    elif game_state == "free_agents":
        draw_free_agent_portal()
    elif game_state == "confirm":
        draw_confirm_screen()
    elif game_state == "player_detail":
        draw_player_detail()
    elif game_state == "allstar":
        draw_all_star_page()
    elif game_state == "contract_negotiation":
        draw_contract_negotiation()
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
    elif game_state == "trades":
        draw_trade_screen()
    elif game_state == "awards":
        draw_awards_screen()
    elif game_state == "world_series_champions":
        draw_world_series_champions_screen()
    elif game_state == "scouting":
        draw_scouting_page()
    elif game_state == "franchise_culture":
        draw_franchise_culture_page()
    elif game_state == "playoff_intro":
        draw_playoff_intro()
    elif game_state == "minor_league_farm":
        draw_minor_league_farm_page()
    elif game_state == "minor_callup_contract":
        draw_minor_callup_contract_screen()
    elif game_state == "inning_reveal":
        draw_inning_reveal()

    elif game_state == "media":
        draw_media_page()

    elif game_state == "series_update":
        draw_series_update(playoff_round_state["current_series"])

    elif game_state == "celebration":
        draw_celebration(last_playoff_game["winner"], season.playoff_round)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()