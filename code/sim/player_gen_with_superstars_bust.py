import random
from dataclasses import dataclass, field

AVG_MLB_SALARY = 5_000_000
MIN_SALARY = 750_000
MAX_SALARY = 60_000_000

SEASON_GAMES = 60
MIN_CONTRACT_GAMES = 30
MAX_CONTRACT_GAMES = 180

SUPERSTAR_CHANCE = 0.06
BUST_CHANCE = 0.08
SALARY_VOLATILITY = 1.25

LEAGUE = {
    "hitter": {"average": 250, "obp": 320, "slugging": 410, "ops": 730},
    "pitcher": {"average_minus": 30, "slugging_minus": 60, "obp_minus": 42},
}

HITTER_WEIGHTS = {"average": 0.25, "obp": 0.35, "slugging": 0.25, "ops": 0.15}
PITCHER_WEIGHTS = {"average_minus": 0.40, "slugging_minus": 0.35, "obp_minus": 0.25}

HITTER_SDS = {"average": 20, "obp": 25, "slugging": 60, "ops": 90}
PITCHER_SDS = {"average_minus": 15, "slugging_minus": 30, "obp_minus": 18}

HITTER_STAR_BOOST = {"average": 40, "obp": 50, "slugging": 140, "ops": 220}
HITTER_BUST_DROP = {"average": 30, "obp": 35, "slugging": 90, "ops": 140}

# Higher minus values are better in this game
PITCHER_STAR_BOOST = {"average_minus": 20, "slugging_minus": 40, "obp_minus": 22}
PITCHER_BUST_DROP = {"average_minus": 15, "slugging_minus": 30, "obp_minus": 18}

HITTER_RANGES = {
    "average": (150, 400),
    "obp": (200, 500),
    "slugging": (250, 900),
    "ops": (500, 1300),
}
PITCHER_RANGES = {
    "average_minus": (0, 120),
    "slugging_minus": (0, 200),
    "obp_minus": (0, 160),
}

FIRST_NAMES = [
    "Jake", "Mike", "Luis", "Andre", "Noah", "Eli", "Carter", "Dylan",
    "Rafael", "Troy", "Marcus", "Owen", "Julian", "Xavier", "Isaac",
    "Roman", "Miles", "Avery", "Logan", "Caleb", "Jaden", "Blake",
    "Tyler", "Ethan", "Mason", "Liam", "Wyatt", "Hunter", "Tristan",
    "Cole", "Bryce", "Garrett", "Parker", "Luca", "Damian", "Adrian",
    "Nolan", "Griffin", "Chase", "Aidan", "Jordan", "Kevin", "Nico",
    "Antonio", "Matteo", "Asher", "Diego", "Victor", "Jonah", "Max",
    "Preston", "Simon", "Emmett", "Hayden", "Zane", "Kaden", "Brady",
    "Trevor", "Colin", "Malik", "Derek", "Finn", "Jayden", "Riley",
    "Brody", "Beckett", "Wesley", "Archer", "Holden", "Spencer",
    "Tatum", "Micah", "Alex", "Eric", "Leon", "Chris", "Quinn",
    "Raul", "Oscar", "Mario", "Joel", "Cesar", "Felix", "Hector",
    "Pedro", "Enzo", "Ruben", "Saul", "Kobe", "Shawn", "Tanner",
    "Mitchell", "Grant", "Maddox", "Brendan", "Kyle", "Devon"
]

LAST_NAMES = [
    "Stone", "Ramirez", "Kim", "Johnson", "Walker", "Santos", "Reed",
    "Morales", "Nguyen", "Harper", "Coleman", "Diaz", "Parker", "Bennett",
    "Foster", "Allen", "Baker", "Jenkins", "Perry", "Price", "Vasquez",
    "Torres", "Medina", "Castillo", "Rivera", "Delgado", "Ortega",
    "Mendoza", "Salazar", "Rios", "Gutierrez", "Lopez", "Sanchez",
    "Flores", "Cruz", "Herrera", "Jimenez", "Suarez", "Navarro",
    "Vega", "Molina", "Silva", "Nunez", "Rojas", "Acosta", "Leon",
    "Morris", "Powell", "Bryant", "Russell", "Ward", "Hughes", "West",
    "Sanders", "Woods", "Cole", "Bishop", "Carson", "Hansen", "Rhodes",
    "Owens", "Webb", "Holland", "Porter", "Hicks", "Fisher", "Ray",
    "Stephens", "Burke", "Meyer", "Mills", "Warren", "Fox", "Greene",
    "Soto", "Vargas", "Macias", "Pena", "Cabrera", "Alvarez", "Bravo",
    "Ibarra", "Rosales", "Mejia", "Serrano", "Bautista", "Rosario",
    "Hernandez", "Cordero", "Padilla", "Valencia", "Lucero", "Montoya",
    "Yates", "Barton", "Ellis", "Barrett"
]

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def choose_tier():
    r = random.random()
    if r < SUPERSTAR_CHANCE:
        return "superstar"
    if r < SUPERSTAR_CHANCE + BUST_CHANCE:
        return "bust"
    return "normal"

def random_contract_games():
    return random.randint(MIN_CONTRACT_GAMES, MAX_CONTRACT_GAMES)

@dataclass
class Hitter:
    name: str
    average: int
    obp: int
    slugging: int
    ops: int
    tier: str = "normal"
    salary: int = 0
    contract_games_remaining: int = 0
    contract_length: int = 0

    coach_avg_bonus: int = 0
    coach_obp_bonus: int = 0
    coach_ops_bonus: int = 0
    coach_progress_games: int = 0

    season_games: int = 0
    pa: int = 0
    ab: int = 0
    singles: int = 0
    doubles: int = 0
    triples: int = 0
    homeruns: int = 0
    hits: int = 0
    rbi: int = 0
    runs: int = 0
    walks: int = 0
    hbp: int = 0
    strikeouts: int = 0
    outs: int = 0

    @property
    def character_name(self):
        return self.name

    @property
    def bb_rate(self):
        return 0.90

    @property
    def hbp_rate(self):
        return 0.10

    @property
    def display_average(self):
        return self.average + self.coach_avg_bonus

    @property
    def display_obp(self):
        return self.obp + self.coach_obp_bonus

    @property
    def display_ops(self):
        return self.ops + self.coach_ops_bonus

    def coach_bonus_string(self):
        parts = []
        if self.coach_avg_bonus > 0:
            parts.append(f"AVG +{self.coach_avg_bonus}")
        if self.coach_obp_bonus > 0:
            parts.append(f"OBP +{self.coach_obp_bonus}")
        if self.coach_ops_bonus > 0:
            parts.append(f"OPS +{self.coach_ops_bonus}")
        return ", ".join(parts)

    def reset_season_stats(self):
        self.season_games = 0
        self.pa = 0
        self.ab = 0
        self.singles = 0
        self.doubles = 0
        self.triples = 0
        self.homeruns = 0
        self.hits = 0
        self.rbi = 0
        self.runs = 0
        self.walks = 0
        self.hbp = 0
        self.strikeouts = 0
        self.outs = 0

@dataclass
class Pitcher:
    name: str
    average_minus: int
    slugging_minus: int
    obp_minus: int
    tier: str = "normal"
    salary: int = 0
    contract_games_remaining: int = 0
    contract_length: int = 0

    coach_avg_bonus: int = 0
    coach_obp_bonus: int = 0
    coach_slg_bonus: int = 0
    coach_progress_games: int = 0

    fatigue: float = 0.0
    bb_plus: int = 0
    hbp_plus: int = 0

    season_games: int = 0
    games_started: int = 0
    outs_recorded: int = 0
    hits_allowed: int = 0
    runs_allowed: int = 0
    earned_runs: int = 0
    walks: int = 0
    hbps: int = 0
    strikeouts: int = 0

    @property
    def character_name(self):
        return self.name

    @property
    def display_average_minus(self):
        fatigue_penalty = int(self.fatigue // 5)
        return max(0, self.average_minus + self.coach_avg_bonus - fatigue_penalty)

    @property
    def display_obp_minus(self):
        fatigue_penalty = int(self.fatigue // 5)
        return max(0, self.obp_minus + self.coach_obp_bonus - fatigue_penalty)

    @property
    def display_slugging_minus(self):
        fatigue_penalty = int(self.fatigue // 4)
        return max(0, self.slugging_minus + self.coach_slg_bonus - fatigue_penalty)

    @property
    def era(self):
        ip = self.outs_recorded / 3
        if ip <= 0:
            return 0.00
        return round((self.earned_runs * 9) / ip, 2)

    @property
    def innings_pitched_text(self):
        whole = self.outs_recorded // 3
        frac = self.outs_recorded % 3
        return f"{whole}.{frac}"

    def coach_bonus_string(self):
        parts = []
        if self.coach_avg_bonus > 0:
            parts.append(f"AVG- +{self.coach_avg_bonus}")
        if self.coach_obp_bonus > 0:
            parts.append(f"OBP- +{self.coach_obp_bonus}")
        if self.coach_slg_bonus > 0:
            parts.append(f"SLG- +{self.coach_slg_bonus}")
        if self.fatigue > 0:
            parts.append(f"FAT {int(self.fatigue)}")
        return ", ".join(parts)

    def reset_season_stats(self):
        self.season_games = 0
        self.games_started = 0
        self.outs_recorded = 0
        self.hits_allowed = 0
        self.runs_allowed = 0
        self.earned_runs = 0
        self.walks = 0
        self.hbps = 0
        self.strikeouts = 0
        self.fatigue = 0.0

@dataclass
class PitchingCoach:
    name: str
    avg_boost: int
    obp_boost: int
    slg_boost: int
    salary: int
    contract_games_remaining: int = 0
    contract_length: int = 0

@dataclass
class HittingCoach:
    name: str
    avg_boost: int
    obp_boost: int
    ops_boost: int
    salary: int
    contract_games_remaining: int = 0
    contract_length: int = 0

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

    estimated_ops = stats["obp"] + stats["slugging"]
    stats["ops"] = clamp(int((stats["ops"] * 0.55) + (estimated_ops * 0.45)), *HITTER_RANGES["ops"])

    return Hitter(
        name=random_name(),
        average=stats["average"],
        obp=stats["obp"],
        slugging=stats["slugging"],
        ops=stats["ops"],
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
            mean += PITCHER_STAR_BOOST[k]
            sd *= 0.75
        elif tier == "bust":
            mean -= PITCHER_BUST_DROP[k]
            sd *= 1.05

        val = int(random.gauss(mean, sd))
        lo, hi = PITCHER_RANGES[k]
        stats[k] = clamp(val, lo, hi)

    p = Pitcher(
        name=random_name(),
        average_minus=stats["average_minus"],
        slugging_minus=stats["slugging_minus"],
        obp_minus=stats["obp_minus"],
        tier=tier,
    )

    p.bb_plus = clamp(int(max(0, 80 - p.obp_minus) * 0.9), 0, 120)
    p.hbp_plus = clamp(int(max(0, 70 - p.average_minus) * 0.25), 0, 50)
    return p

def hitter_performance_score(h: Hitter) -> float:
    base = LEAGUE["hitter"]

    def z(stat, mean, scale):
        return (stat - mean) / scale

    score = (
        HITTER_WEIGHTS["average"] * z(h.average, base["average"], HITTER_SDS["average"]) +
        HITTER_WEIGHTS["obp"] * z(h.obp, base["obp"], HITTER_SDS["obp"]) +
        HITTER_WEIGHTS["slugging"] * z(h.slugging, base["slugging"], HITTER_SDS["slugging"]) +
        HITTER_WEIGHTS["ops"] * z(h.ops, base["ops"], HITTER_SDS["ops"])
    )
    return clamp(score / 2.0, -1.5, 1.5)

def pitcher_performance_score(p: Pitcher) -> float:
    base = LEAGUE["pitcher"]

    def z(stat, mean, scale):
        return (stat - mean) / scale

    score = (
        PITCHER_WEIGHTS["average_minus"] * z(p.average_minus, base["average_minus"], PITCHER_SDS["average_minus"]) +
        PITCHER_WEIGHTS["slugging_minus"] * z(p.slugging_minus, base["slugging_minus"], PITCHER_SDS["slugging_minus"]) +
        PITCHER_WEIGHTS["obp_minus"] * z(p.obp_minus, base["obp_minus"], PITCHER_SDS["obp_minus"])
    )
    return clamp(score / 2.0, -1.5, 1.5)

def score_to_salary(score: float) -> int:
    multiplier = 2 ** (score * SALARY_VOLATILITY)
    salary = int(AVG_MLB_SALARY * multiplier)
    return clamp(salary, MIN_SALARY, MAX_SALARY)

def assign_contract(obj, low=MIN_CONTRACT_GAMES, high=MAX_CONTRACT_GAMES):
    obj.contract_length = random.randint(low, high)
    obj.contract_games_remaining = obj.contract_length
    return obj

def assign_salary_hitter(h: Hitter) -> Hitter:
    score = hitter_performance_score(h)
    h.salary = score_to_salary(score)

    if h.tier == "superstar":
        h.salary = clamp(int(h.salary * 1.25), MIN_SALARY, MAX_SALARY)
    elif h.tier == "bust":
        h.salary = clamp(int(h.salary * 0.85), MIN_SALARY, MAX_SALARY)

    return assign_contract(h)

def assign_salary_pitcher(p: Pitcher) -> Pitcher:
    score = pitcher_performance_score(p)
    p.salary = score_to_salary(score)

    if p.tier == "superstar":
        p.salary = clamp(int(p.salary * 1.25), MIN_SALARY, MAX_SALARY)
    elif p.tier == "bust":
        p.salary = clamp(int(p.salary * 0.85), MIN_SALARY, MAX_SALARY)

    return assign_contract(p)

def assign_minor_salary_hitter(h: Hitter) -> Hitter:
    h = assign_salary_hitter(h)
    h.salary = max(MIN_SALARY, int(h.salary * 0.35))
    return h

def assign_minor_salary_pitcher(p: Pitcher) -> Pitcher:
    p = assign_salary_pitcher(p)
    p.salary = max(MIN_SALARY, int(p.salary * 0.35))
    return p

def gen_pitching_coach():
    c = PitchingCoach(
        name=random_name(),
        avg_boost=random.randint(2, 7),
        obp_boost=random.randint(2, 7),
        slg_boost=random.randint(3, 9),
        salary=random.randint(900_000, 5_000_000),
    )
    return assign_contract(c, 60, 180)

def gen_hitting_coach():
    c = HittingCoach(
        name=random_name(),
        avg_boost=random.randint(2, 7),
        obp_boost=random.randint(2, 7),
        ops_boost=random.randint(4, 12),
        salary=random.randint(900_000, 5_000_000),
    )
    return assign_contract(c, 60, 180)