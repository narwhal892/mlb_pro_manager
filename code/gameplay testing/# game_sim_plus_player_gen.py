# full_game_with_player_gen.py
# Generates 9 hitters + 1 pitcher for each team, then simulates a 9-inning game.
# Includes OBP-driven outs plus walks + HBP, hit types from SLG.
# Pitchers affect AVG/SLG AND OBP (via obp_minus), so editing pitchers matters.

import random
from dataclasses import dataclass

# ----------------------------
# TUNABLE SETTINGS
# ----------------------------
SUPERSTAR_CHANCE = 0.06
BUST_CHANCE = 0.08

# If you want fewer/more base runners overall, tune OBP league avg or obp_minus avg
LEAGUE = {
    "hitter": {"average": 250, "obp": 320, "slugging": 410, "ops": 730},
    "pitcher": {"average_minus": 30, "slugging_minus": 60, "obp_minus": 30},  # lower is better for hitters
}

HITTER_SDS = {"average": 20, "obp": 25, "slugging": 60, "ops": 90}
PITCHER_SDS = {"average_minus": 15, "slugging_minus": 30, "obp_minus": 20}

HITTER_STAR_BOOST = {"average": 40, "obp": 50, "slugging": 140, "ops": 220}
HITTER_BUST_DROP  = {"average": 30, "obp": 35, "slugging": 90,  "ops": 140}

# Pitchers: LOWER minus is better => superstar boosts are negative
PITCHER_STAR_BOOST = {"average_minus": -20, "slugging_minus": -40, "obp_minus": -20}
PITCHER_BUST_DROP  = {"average_minus":  15, "slugging_minus":  30, "obp_minus":  15}

HITTER_RANGES = {"average": (150, 400), "obp": (200, 500), "slugging": (250, 900), "ops": (500, 1300)}
PITCHER_RANGES = {"average_minus": (0, 120), "slugging_minus": (0, 200), "obp_minus": (0, 120)}

# Split between walk and HBP when a PA is "non-hit on base"
DEFAULT_BB_RATE = 0.90
DEFAULT_HBP_RATE = 0.10

# ----------------------------
# DATA CLASSES
# ----------------------------
@dataclass
class Hitter:
    character_name: str
    average: int
    obp: int
    slugging: int
    ops: int
    bb_rate: float = DEFAULT_BB_RATE
    hbp_rate: float = DEFAULT_HBP_RATE
    tier: str = "normal"

@dataclass
class Pitcher:
    character_name: str
    average_minus: int
    slugging_minus: int
    obp_minus: int
    bb_plus: int = 0
    hbp_plus: int = 0
    tier: str = "normal"

# ----------------------------
# UTIL
# ----------------------------
def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def pct(x_0_to_1000):
    return x_0_to_1000 / 1000.0

def random_name():
    first = ["Jake", "Mike", "Luis", "Andre", "Noah", "Eli", "Carter", "Dylan", "Rafael", "Troy",
             "Mason", "Cole", "Jaden", "Brady", "Theo", "Aiden"]
    last = ["Stone", "Ramirez", "Kim", "Johnson", "Walker", "Santos", "Reed", "Morales",
            "Nguyen", "Harper", "Bennett", "Hughes", "Fisher", "Torres", "Parker"]
    return f"{random.choice(first)} {random.choice(last)}"

def choose_tier():
    r = random.random()
    if r < SUPERSTAR_CHANCE:
        return "superstar"
    if r < SUPERSTAR_CHANCE + BUST_CHANCE:
        return "bust"
    return "normal"

# ----------------------------
# PLAYER GENERATION
# ----------------------------
def gen_hitter():
    tier = choose_tier()
    base = LEAGUE["hitter"]
    stats = {}

    for k in ("average", "obp", "slugging", "ops"):
        mean = base[k]
        sd = HITTER_SDS[k]

        if tier == "superstar":
            mean += HITTER_STAR_BOOST[k]
            sd *= 0.70
        elif tier == "bust":
            mean -= HITTER_BUST_DROP[k]
            sd *= 1.05

        val = int(random.gauss(mean, sd))
        lo, hi = HITTER_RANGES[k]
        stats[k] = clamp(val, lo, hi)

    # Slightly better plate discipline for stars, worse for busts (optional)
    if tier == "superstar":
        bb_rate, hbp_rate = 0.93, 0.07
    elif tier == "bust":
        bb_rate, hbp_rate = 0.87, 0.13
    else:
        bb_rate, hbp_rate = DEFAULT_BB_RATE, DEFAULT_HBP_RATE

    return Hitter(
        character_name=random_name(),
        average=stats["average"],
        obp=stats["obp"],
        slugging=stats["slugging"],
        ops=stats["ops"],
        bb_rate=bb_rate,
        hbp_rate=hbp_rate,
        tier=tier,
    )

def gen_pitcher():
    tier = choose_tier()
    base = LEAGUE["pitcher"]
    stats = {}

    for k in ("average_minus", "slugging_minus", "obp_minus"):
        mean = base[k]
        sd = PITCHER_SDS[k]

        if tier == "superstar":
            mean += PITCHER_STAR_BOOST[k]  # negative improves
            sd *= 0.75
        elif tier == "bust":
            mean += PITCHER_BUST_DROP[k]
            sd *= 1.05

        val = int(random.gauss(mean, sd))
        lo, hi = PITCHER_RANGES[k]
        stats[k] = clamp(val, lo, hi)

    # Optional: wild pitchers add walks/HBP, stars reduce them
    if tier == "bust":
        bb_plus, hbp_plus = 20, 5
    elif tier == "superstar":
        bb_plus, hbp_plus = -10, -2
    else:
        bb_plus, hbp_plus = 0, 0

    return Pitcher(
        character_name=random_name(),
        average_minus=stats["average_minus"],
        slugging_minus=stats["slugging_minus"],
        obp_minus=stats["obp_minus"],
        bb_plus=bb_plus,
        hbp_plus=hbp_plus,
        tier=tier,
    )

def gen_team(team_name):
    lineup = [gen_hitter() for _ in range(9)]
    pitcher = gen_pitcher()
    return team_name, lineup, pitcher

# ----------------------------
# GAME SIM LOGIC
# ----------------------------
def bases_str(b):
    return f"[1B={'X' if b[0] else '-'} 2B={'X' if b[1] else '-'} 3B={'X' if b[2] else '-'}]"

def plate_appearance(hitter, pitcher):
    avg_pts = hitter.average
    slg_pts = hitter.slugging
    obp_pts = hitter.obp

    eff_avg = clamp(avg_pts - pitcher.average_minus, 0, 1000)
    eff_slg = clamp(slg_pts - pitcher.slugging_minus, 0, 2000)

    # KEY: pitcher affects OBP (outs) via obp_minus
    eff_obp = clamp(obp_pts - pitcher.obp_minus + pitcher.bb_plus + pitcher.hbp_plus, 0, 1000)

    # Out vs reach base
    if random.random() > pct(eff_obp):
        return "out"

    # Decide if reach base is a hit or BB/HBP
    walk_hbp_pts = max(eff_obp - eff_avg, 0)
    p_walk_or_hbp = walk_hbp_pts / 1000.0

    if random.random() < p_walk_or_hbp:
        bb_rate = hitter.bb_rate
        hbp_rate = hitter.hbp_rate
        total = bb_rate + hbp_rate
        if total <= 0:
            bb_rate, hbp_rate = 0.90, 0.10
        else:
            bb_rate, hbp_rate = bb_rate / total, hbp_rate / total
        return "walk" if random.random() < bb_rate else "hbp"

    # Hit type from SLG (arcade biased)
    slg = eff_slg / 1000.0
    extra_boost = clamp((slg - 0.300) / 0.500, 0.0, 1.0)

    w_1b = 0.65 - 0.25 * extra_boost
    w_2b = 0.20 + 0.10 * extra_boost
    w_3b = 0.05
    w_hr = 0.10 + 0.15 * extra_boost

    total = w_1b + w_2b + w_3b + w_hr
    w_1b, w_2b, w_3b, w_hr = w_1b/total, w_2b/total, w_3b/total, w_hr/total

    r = random.random()
    if r < w_hr:
        return "homerun"
    elif r < w_hr + w_3b:
        return "triple"
    elif r < w_hr + w_3b + w_2b:
        return "double"
    else:
        return "single"

def apply_walk_or_hbp(bases):
    on_1st, on_2nd, on_3rd = bases
    runs = 0

    if on_1st:
        if on_2nd:
            if on_3rd:
                runs += 1
            on_3rd = True
        on_2nd = True
    on_1st = True

    return [on_1st, on_2nd, on_3rd], runs

def apply_hit(bases, hit_type):
    # Your arcade rule: runners on 2nd & 3rd score on any hit.
    on_1st, on_2nd, on_3rd = bases
    runs = 0

    if hit_type == "homerun":
        runs += int(on_1st) + int(on_2nd) + int(on_3rd) + 1
        return [False, False, False], runs

    if on_2nd:
        runs += 1
        on_2nd = False
    if on_3rd:
        runs += 1
        on_3rd = False

    new_bases = [False, False, False]

    if on_1st:
        if hit_type == "single":
            new_bases[1] = True
        elif hit_type in ("double", "triple"):
            runs += 1

    if hit_type == "single":
        new_bases[0] = True
    elif hit_type == "double":
        new_bases[1] = True
    elif hit_type == "triple":
        new_bases[2] = True

    return new_bases, runs

def simulate_half_inning(lineup, pitcher, start_idx=0, verbose=True):
    outs = 0
    runs = 0
    bases = [False, False, False]
    i = start_idx

    while outs < 3:
        hitter = lineup[i]
        outcome = plate_appearance(hitter, pitcher)

        if outcome == "out":
            outs += 1
            if verbose:
                print(f"{hitter.character_name}: OUT | Outs {outs} | Bases {bases_str(bases)}")
        elif outcome in ("walk", "hbp"):
            bases, scored = apply_walk_or_hbp(bases)
            runs += scored
            if verbose:
                print(f"{hitter.character_name}: {outcome.upper()} (+{scored} R) | Outs {outs} | Bases {bases_str(bases)} | Runs {runs}")
        else:
            bases, scored = apply_hit(bases, outcome)
            runs += scored
            if verbose:
                print(f"{hitter.character_name}: {outcome.upper()} (+{scored} R) | Outs {outs} | Bases {bases_str(bases)} | Runs {runs}")

        i = (i + 1) % len(lineup)

    return runs, i

def print_lineup(team_name, lineup, pitcher):
    print("\n======================")
    print(f"{team_name} LINEUP")
    print("======================")

    print(
        f"SP: {pitcher.character_name:18} "
        f"({pitcher.tier.upper():9})  "
        f"AVG- {pitcher.average_minus:3}  "
        f"SLG- {pitcher.slugging_minus:3}  "
        f"OBP- {pitcher.obp_minus:3}"
    )

    print("\nBatting Order:")
    print(" #  Name               Tier        AVG    OBP    SLG    OPS")
    print("--------------------------------------------------------------")

    for i, h in enumerate(lineup, start=1):
        print(
            f"{i:2d}. {h.character_name:18} "
            f"{h.tier.upper():10} "
            f".{h.average:03d}  "
            f".{h.obp:03d}  "
            f".{h.slugging:03d}  "
            f"{h.ops:4d}"
        )


def simulate_game(away_team, home_team, away_lineup, home_lineup, away_pitcher, home_pitcher, verbose=True):
    away_score = 0
    home_score = 0
    away_idx = 0
    home_idx = 0

    if verbose:
        print("\n======================")
        print(f"   {away_team} @ {home_team}")
        print("======================")

        print_lineup(away_team, away_lineup, away_pitcher)
        print_lineup(home_team, home_lineup, home_pitcher)

    for inning in range(1, 10):
        if verbose:
            print(f"\n--- INNING {inning} (TOP) {away_team} bats ---")
        r, away_idx = simulate_half_inning(away_lineup, home_pitcher, away_idx, verbose)
        away_score += r
        if verbose:
            print(f"End Top {inning}: {away_team} {away_score} - {home_team} {home_score}")

        if verbose:
            print(f"\n--- INNING {inning} (BOTTOM) {home_team} bats ---")
        r, home_idx = simulate_half_inning(home_lineup, away_pitcher, home_idx, verbose)
        home_score += r
        if verbose:
            print(f"End Inning {inning}: {away_team} {away_score} - {home_team} {home_score}")

    if verbose:
        print("\n======================")
        print("      FINAL SCORE")
        print("======================")
        print(f"{away_team}: {away_score}")
        print(f"{home_team}: {home_score}")

    return away_score, home_score

# ----------------------------
# RUN IT
# ----------------------------
if __name__ == "__main__":
    away_team, away_lineup, away_pitcher = gen_team("AWAY")
    home_team, home_lineup, home_pitcher = gen_team("HOME")

    simulate_game(away_team, home_team, away_lineup, home_lineup, away_pitcher, home_pitcher, verbose=True)
