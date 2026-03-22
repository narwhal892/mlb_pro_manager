# player_generator_salary.py
import random
from dataclasses import dataclass

AVG_MLB_SALARY = 5_000_000

# ----------------------------
# League average baselines (edit these)
# Stats are in "points" like 280 = .280
# Pitcher modifiers are "minus points" (lower is better for hitters facing them)
# ----------------------------
LEAGUE = {
    "hitter": {
        "average": 250,
        "obp": 320,
        "slugging": 410,
        "ops": 730,
    },
    "pitcher": {
        "average_minus": 30,   # how many points they reduce hitter AVG
        "slugging_minus": 60,  # how many points they reduce hitter SLG
    }
}

# ----------------------------
# Weights (edit these to tune salary sensitivity)
# ----------------------------
HITTER_WEIGHTS = {
    "average": 0.25,
    "obp": 0.35,
    "slugging": 0.25,
    "ops": 0.15,
}
PITCHER_WEIGHTS = {
    "average_minus": 0.50,
    "slugging_minus": 0.50,
}

# How aggressive salary responds to performance score.
# performance_score is around -1.0..+1.0 for typical players
SALARY_VOLATILITY = 1.25  # 1.0 = moderate, 2.0 = very swingy

# Salary bounds (keeps things sane)
MIN_SALARY = 750_000
MAX_SALARY = 60_000_000


@dataclass
class Hitter:
    name: str
    average: int
    obp: int
    slugging: int
    ops: int
    salary: int = 0


@dataclass
class Pitcher:
    name: str
    average_minus: int
    slugging_minus: int
    salary: int = 0


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def random_name():
    first = ["Jake", "Mike", "Luis", "Andre", "Noah", "Eli", "Carter", "Dylan", "Rafael", "Troy"]
    last = ["Stone", "Ramirez", "Kim", "Johnson", "Walker", "Santos", "Reed", "Morales", "Nguyen", "Harper"]
    return f"{random.choice(first)} {random.choice(last)}"


# ----------------------------
# Random stat generation
# Use a normal distribution around league average.
# ----------------------------
def gen_hitter():
    base = LEAGUE["hitter"]
    avg = int(random.gauss(base["average"], 20))     # +/- ~20 points typical
    obp = int(random.gauss(base["obp"], 25))
    slg = int(random.gauss(base["slugging"], 60))
    ops = int(random.gauss(base["ops"], 90))

    # clamp to reasonable ranges
    avg = clamp(avg, 150, 400)
    obp = clamp(obp, 200, 500)
    slg = clamp(slg, 250, 800)
    ops = clamp(ops, 500, 1200)

    return Hitter(random_name(), avg, obp, slg, ops)


def gen_pitcher():
    base = LEAGUE["pitcher"]
    avg_minus = int(random.gauss(base["average_minus"], 15))   # lower is better
    slg_minus = int(random.gauss(base["slugging_minus"], 30))  # lower is better

    avg_minus = clamp(avg_minus, 0, 120)
    slg_minus = clamp(slg_minus, 0, 200)

    return Pitcher(random_name(), avg_minus, slg_minus)


# ----------------------------
# Performance score -> salary
# Score is a weighted normalized difference from league average.
# For hitters: higher stats = better (positive score).
# For pitchers: LOWER "minus" stats = better (positive score).
# ----------------------------
def hitter_performance_score(h: Hitter) -> float:
    base = LEAGUE["hitter"]

    def norm(stat, mean, scale):
        # (stat - mean) / scale gives ~ -2..+2 for most generated players
        return (stat - mean) / scale

    z_avg = norm(h.average, base["average"], 20)
    z_obp = norm(h.obp, base["obp"], 25)
    z_slg = norm(h.slugging, base["slugging"], 60)
    z_ops = norm(h.ops, base["ops"], 90)

    score = (
        HITTER_WEIGHTS["average"] * z_avg +
        HITTER_WEIGHTS["obp"] * z_obp +
        HITTER_WEIGHTS["slugging"] * z_slg +
        HITTER_WEIGHTS["ops"] * z_ops
    )

    # squish into a nice range roughly -1..+1
    return clamp(score / 2.0, -1.5, 1.5)


def pitcher_performance_score(p: Pitcher) -> float:
    base = LEAGUE["pitcher"]

    def norm_higher_is_better(stat, mean, scale):
        # invert: higher-than-average becomes positive
        return (stat - mean) / scale

    z_avgm = norm_higher_is_better(p.average_minus, base["average_minus"], 15)
    z_slgm = norm_higher_is_better(p.slugging_minus, base["slugging_minus"], 30)

    score = (
        PITCHER_WEIGHTS["average_minus"] * z_avgm +
        PITCHER_WEIGHTS["slugging_minus"] * z_slgm
    )

    return clamp(score / 2.0, -1.5, 1.5)


def score_to_salary(score: float) -> int:
    """
    Convert performance score into salary.
    Uses exponential-ish scaling so stars get paid and bad players drop.
    """
    # Example: score=0 -> 1.0x; score=1 -> ~3.5x if volatility is 1.25
    multiplier = 2 ** (score * SALARY_VOLATILITY)
    salary = int(AVG_MLB_SALARY * multiplier)
    return clamp(salary, MIN_SALARY, MAX_SALARY)


def assign_salary_hitter(h: Hitter) -> Hitter:
    score = hitter_performance_score(h)
    h.salary = score_to_salary(score)
    return h


def assign_salary_pitcher(p: Pitcher) -> Pitcher:
    score = pitcher_performance_score(p)
    p.salary = score_to_salary(score)
    return p


def money(n: int) -> str:
    return "${:,.0f}".format(n)


def main():
    hitter = assign_salary_hitter(gen_hitter())
    pitcher = assign_salary_pitcher(gen_pitcher())

    print("\n=== RANDOM HITTER ===")
    print(f"Name:     {hitter.name}")
    print(f"AVG:      {hitter.average}  (.{hitter.average:03d})")
    print(f"OBP:      {hitter.obp}  (.{hitter.obp:03d})")
    print(f"SLG:      {hitter.slugging}  (.{hitter.slugging:03d})")
    print(f"OPS:      {hitter.ops}")
    print(f"Salary:   {money(hitter.salary)}")

    print("\n=== RANDOM PITCHER ===")
    print(f"Name:     {pitcher.name}")
    print(f"AVG-:     {pitcher.average_minus} points (higher is better)")
    print(f"SLG-:     {pitcher.slugging_minus} points (higher is better)")
    print(f"Salary:   {money(pitcher.salary)}\n")


if __name__ == "__main__":
    main()
