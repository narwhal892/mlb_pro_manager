from dataclasses import dataclass, field
import random

from player_gen_with_superstars_bust import (
    gen_hitter,
    gen_pitcher,
    assign_salary_hitter,
    assign_salary_pitcher,
)

SCOUT_MARKET_NAMES = {
    "pacific": "Pacific Circuit",
    "caribbean": "Caribbean Pipeline",
    "peninsula": "Peninsula League",
}

SCOUT_STAR_COSTS = {
    1: 1_500_000,
    2: 3_500_000,
    3: 6_500_000,
}

SCOUT_DISCOUNTS = {
    1: 0.90,   # 10% off
    2: 0.78,   # 22% off
    3: 0.65,   # 35% off
}

CARIBBEAN_FIRST = [
    "Juan", "Luis", "Carlos", "Miguel", "Jose", "Rafael", "Pedro", "Diego", "Victor", "Santiago",
    "Andres", "Javier", "Fernando", "Ricardo", "Manuel"
]

CARIBBEAN_LAST = [
    "Rodriguez", "Martinez", "Gonzalez", "Perez", "Hernandez", "Lopez", "Diaz", "Cruz",
    "Torres", "Rivera", "Ramirez", "Castillo", "Morales"
]

JAPANESE_FIRST = [
    "Hiroshi", "Takumi", "Yuki", "Daichi", "Kaito", "Ren", "Sota", "Riku", "Haruto", "Shota"
]

JAPANESE_LAST = [
    "Tanaka", "Suzuki", "Sato", "Takahashi", "Watanabe", "Ito", "Yamamoto", "Nakamura"
]

KOREAN_FIRST = [
    "Min-Jun", "Ji-Hoon", "Hyun-Woo", "Seung-Hyun", "Jae-Won", "Dong-Hyun"
]

KOREAN_LAST = [
    "Kim", "Lee", "Park", "Choi", "Jung", "Kang"
]

CHINESE_FIRST = [
    "Wei", "Jun", "Hao", "Jian", "Lei", "Ming", "Tao", "Peng"
]

CHINESE_LAST = [
    "Wang", "Li", "Zhang", "Liu", "Chen", "Yang", "Huang"
]
@dataclass
class ScoutedProspect:
    player: object
    source_key: str
    source_name: str
    scout_stars: int
    original_salary: int
    discounted_salary: int
    games_left: int = 12  # how long they stay on board before vanishing

    @property
    def discount_pct(self):
        return int(round((1.0 - (self.discounted_salary / max(1, self.original_salary))) * 100))


def weighted_region_choice():
    r = random.random()
    if r < 0.34:
        return "pacific"
    if r < 0.67:
        return "caribbean"
    return "peninsula"


def boost_overseas_hitter(h, region_key):
    # Make these players feel elite and distinct
    if region_key == "pacific":
        h.average = min(400, h.average + random.randint(12, 28))
        h.obp = min(500, h.obp + random.randint(10, 25))
        h.ops = min(1300, h.ops + random.randint(25, 70))
    elif region_key == "caribbean":
        h.slugging = min(900, h.slugging + random.randint(30, 85))
        h.ops = min(1300, h.ops + random.randint(35, 95))
    elif region_key == "peninsula":
        h.obp = min(500, h.obp + random.randint(14, 30))
        h.average = min(400, h.average + random.randint(8, 18))
        h.ops = min(1300, h.ops + random.randint(25, 65))

    h.age = random.randint(20, 28)
    h.tier = "superstar" if random.random() < 0.45 else h.tier
    return h
def generate_region_name(region_key):
    if region_key == "caribbean":
        return f"{random.choice(CARIBBEAN_FIRST)} {random.choice(CARIBBEAN_LAST)}"

    elif region_key == "pacific":
        return f"{random.choice(JAPANESE_FIRST)} {random.choice(JAPANESE_LAST)}"

    elif region_key == "peninsula":
        # mix Chinese + Korean
        if random.random() < 0.5:
            return f"{random.choice(KOREAN_FIRST)} {random.choice(KOREAN_LAST)}"
        else:
            return f"{random.choice(CHINESE_FIRST)} {random.choice(CHINESE_LAST)}"

    return None

def boost_overseas_pitcher(p, region_key):
    if region_key == "pacific":
        p.average_minus = min(120, p.average_minus + random.randint(8, 18))
        p.slugging_minus = min(200, p.slugging_minus + random.randint(12, 28))
    elif region_key == "caribbean":
        p.average_minus = min(120, p.average_minus + random.randint(10, 22))
        p.obp_minus = min(160, p.obp_minus + random.randint(8, 18))
        p.stamina = min(95, p.stamina + random.randint(2, 8))
    elif region_key == "peninsula":
        p.obp_minus = min(160, p.obp_minus + random.randint(12, 25))
        p.slugging_minus = min(200, p.slugging_minus + random.randint(10, 24))

    p.age = random.randint(20, 29)
    p.tier = "superstar" if random.random() < 0.45 else p.tier
    return p


def create_scouted_player(region_key):
    # Slightly favor hitters, but still mix in pitchers
    if random.random() < 0.58:
        hitter = gen_hitter()
        hitter = boost_overseas_hitter(hitter, region_key)
        hitter = assign_salary_hitter(hitter)
        
        new_name = generate_region_name(region_key)
        if new_name:
            hitter.name = new_name

        return hitter
    pitcher = gen_pitcher()
    pitcher = boost_overseas_pitcher(pitcher, region_key)
    pitcher = assign_salary_pitcher(pitcher)
    new_name = generate_region_name(region_key)
    if new_name:
        pitcher.name = new_name

    return pitcher


def generate_scouted_prospect(stars):
    region_key = weighted_region_choice()
    player = create_scouted_player(region_key)

    original_salary = int(getattr(player, "salary", 1_000_000))
    discount_mult = SCOUT_DISCOUNTS.get(stars, 0.90)
    discounted_salary = max(750_000, int(original_salary * discount_mult))

    player.salary = discounted_salary

    return ScoutedProspect(
        player=player,
        source_key=region_key,
        source_name=SCOUT_MARKET_NAMES[region_key],
        scout_stars=stars,
        original_salary=original_salary,
        discounted_salary=discounted_salary,
        games_left=12,
    )


def hire_scout(team, stars):
    if stars not in (1, 2, 3):
        return False, "Scout stars must be 1, 2, or 3."

    scout_cost = SCOUT_STAR_COSTS[stars]
    current_cost = SCOUT_STAR_COSTS.get(getattr(team, "scout_stars", 0), 0)
    new_total = team.total_salary() - current_cost + scout_cost

    if new_total > team.budget:
        return False, "You cannot afford that scout."

    team.scout_stars = stars
    team.scout_salary = scout_cost
    team.scout_games_until_report = 3
    return True, f"Hired a {stars}-star scout for ${scout_cost:,.0f}."


def fire_scout(team):
    team.scout_stars = 0
    team.scout_salary = 0
    team.scout_games_until_report = 0
    return True, "Scout released."


def advance_scouting(team, games=1):
    """
    Call once after each completed team game.
    Only one active scouted prospect is kept at a time.
    A newly discovered prospect replaces the previous one.
    """
    if getattr(team, "scout_stars", 0) <= 0:
        return []

    if not hasattr(team, "scouted_prospects") or team.scouted_prospects is None:
        team.scouted_prospects = []

    created = []

    for _ in range(games):
        team.scout_games_until_report -= 1

        if team.scout_games_until_report <= 0:
            prospect = generate_scouted_prospect(team.scout_stars)

            # keep only one report at a time
            team.scouted_prospects = [prospect]

            created.append(prospect)
            team.scout_games_until_report = 3

        # age out current report if one exists
        if team.scouted_prospects:
            team.scouted_prospects[0].games_left -= 1
            if team.scouted_prospects[0].games_left <= 0:
                team.scouted_prospects = []

    return created

def sign_scouted_prospect(team, prospect):
    player = prospect.player

    if not team.can_afford(player.salary):
        return False, "You do not have enough budget room."

    if hasattr(player, "ops"):
        # hitter
        placed = False
        for i, p in enumerate(team.bench):
            if team.is_empty_slot(p):
                team.bench[i] = player
                placed = True
                break
        if not placed:
            for i, p in enumerate(team.minors_hitters):
                if team.is_empty_slot(p):
                    team.minors_hitters[i] = player
                    placed = True
                    break
        if not placed:
            return False, "No hitter space available on bench or in minors."

    elif hasattr(player, "average_minus"):
        # pitcher
        placed = False
        for i, p in enumerate(team.bullpen):
            if team.is_empty_slot(p):
                team.bullpen[i] = player
                placed = True
                break
        if not placed:
            for i, p in enumerate(team.minors_pitchers):
                if team.is_empty_slot(p):
                    team.minors_pitchers[i] = player
                    placed = True
                    break
        if not placed:
            return False, "No pitcher space available in bullpen or minors."

    else:
        return False, "Invalid prospect type."

    if prospect in team.scouted_prospects:
        team.scouted_prospects.remove(prospect)

    team.refresh_roles()
    team.ensure_batting_order()
    team.normalize_optional_slots()
    return True, f"Signed {player.name} from the {prospect.source_name}."