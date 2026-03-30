import random
from dataclasses import dataclass
from typing import Optional

AVG_MLB_SALARY = 5_000_000
MIN_SALARY = 750_000
MAX_SALARY = 60_000_000

SEASON_GAMES = 60
MIN_CONTRACT_GAMES = 40
MAX_CONTRACT_GAMES = 100

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

FIELDING_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
BENCH_POSITIONS = ["UTIL", "UTIL", "OF", "INF", "C"]
PITCHER_ROLES = ["SP", "RP", "CL"]

FIRST_NAMES = [
    "Jake", "Mike", "Luis", "Andre", "Noah", "Eli", "Carter", "Dylan", "Rafael", "Troy",
    "Marcus", "Owen", "Julian", "Xavier", "Isaac", "Roman", "Miles", "Avery", "Logan", "Caleb",
    "Jaden", "Blake", "Tyler", "Ethan", "Mason", "Liam", "Wyatt", "Hunter", "Tristan", "Cole",
    "Bryce", "Garrett", "Parker", "Luca", "Damian", "Adrian", "Nolan", "Griffin", "Chase", "Aidan",
    "Jordan", "Kevin", "Nico", "Antonio", "Matteo", "Asher", "Diego", "Victor", "Jonah", "Max",

    "Zach", "Trevor", "Spencer", "Colton", "Derek", "Austin", "Brandon", "Cody", "Corey", "Drew",
    "Evan", "Gavin", "Hayden", "Ian", "Jesse", "Kyle", "Levi", "Maddox", "Nate", "Oscar",
    "Preston", "Quinn", "Riley", "Shane", "Tanner", "Uriah", "Vince", "Wesley", "Zane", "Brady",
    "Casey", "Dominic", "Emilio", "Felix", "Giovanni", "Hector", "Ismael", "Jorge", "Kendall", "Leon",
    "Marco", "Nestor", "Orlando", "Randy","Paolo", "Quentin", "Raul", "Sergio", "Teo", "Ulises", "Victorino",

    "Alonzo", "Brett", "Cesar", "Desmond", "Erick", "Francisco", "Gabe", "Hugo", "Ivan", "Jaime",
    "Kenny", "Lorenzo", "Martin", "Nelson", "Octavio", "Pablo", "Ramon", "Salvador", "Tomas", "Uriel",
    "Vladimir", "Wilson", "Xander", "Yahir", "Zion", "Abel", "Brayan", "Cristian", "Dario", "Edwin",
    "Fabian", "Gerardo", "Hernan", "Isidro", "Javier", "Kelvin", "Luciano", "Mauricio", "Nico", "Omar",
    "Pedro", "Ricardo", "Sebastian", "Thiago", "Ubaldo", "Valentin", "Wilmer", "Ximenez", "Yordan", "Zavion"
]
LAST_NAMES = [
    "Stone", "Ramirez", "Kim", "Johnson", "Walker", "Santos", "Reed", "Morales", "Nguyen", "Harper",
    "Coleman", "Diaz", "Parker", "Bennett", "Foster", "Allen", "Baker", "Jenkins", "Perry", "Price",
    "Vasquez", "Torres", "Medina", "Castillo", "Rivera", "Delgado", "Ortega", "Mendoza", "Salazar",
    "Rios", "Gutierrez", "Lopez", "Sanchez", "Flores", "Cruz", "Herrera", "Jimenez", "Suarez", "Navarro",

    "Martinez", "Gonzalez", "Rodriguez", "Perez", "Hernandez", "Garcia", "Martinez", "Alvarez", "Castro", "Vargas",
    "Sandoval", "Valdez", "Escobar", "Montoya", "Rosales", "Zamora", "Pacheco", "Cardenas", "Cabrera", "Bravo",
    "Montes", "Cuevas", "Espinoza", "Quintero", "Benitez", "Gallegos", "Rangel", "Ochoa", "Padilla", "Zuniga",
    "Campos", "Corona", "Renteria", "Solano", "Velasquez", "Villanueva", "Aguilar", "Barajas", "Bautista", "Calderon",

    "Harris", "Young", "King", "Wright", "Scott", "Green", "Adams", "Nelson", "Hill", "Campbell",
    "Mitchell", "Roberts", "Carter", "Phillips", "Evans", "Turner", "Diaz", "Patterson", "Edwards", "Collins",
    "Stewart", "Morris", "Rogers", "Reyes", "Cook", "Morgan", "Bell", "Murphy", "Bailey", "Rivera",
    "Cooper", "Richardson", "Cox", "Howard", "Ward", "Peterson", "Gray", "James", "Watson", "Brooks"
]
SCANDAL_TYPES = [
    "seen out late before a road series",
    "arguing with a reporter on live TV",
    "missed a team photo shoot",
    "accused of clubhouse drama",
    "spotted at a casino the night before a game",
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
    position: str = "UTIL"
    bats: str = "R"
    throws: str = "R"
    tier: str = "normal"
    age: int = 26
    salary: int = 0
    contract_games_remaining: int = 0
    contract_length: int = 0
    injured_games_remaining: int = 0

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

    hot_streak_bonus: int = 0
    cold_streak_penalty: int = 0

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
        return self.average + self.coach_avg_bonus + self.hot_streak_bonus - self.cold_streak_penalty

    @property
    def display_obp(self):
        return self.obp + self.coach_obp_bonus + self.hot_streak_bonus - self.cold_streak_penalty

    @property
    def display_slugging(self):
        return self.slugging + max(0, self.coach_ops_bonus // 2) + (self.hot_streak_bonus * 2) - (self.cold_streak_penalty * 2)

    @property
    def display_ops(self):
        return self.ops + self.coach_ops_bonus + (self.hot_streak_bonus * 2) - (self.cold_streak_penalty * 2)

    @property
    def avg_text(self):
        return f"{(self.hits / self.ab):.3f}" if self.ab else ".000"

    @property
    def obp_text(self):
        denom = self.ab + self.walks + self.hbp
        return f"{((self.hits + self.walks + self.hbp) / denom):.3f}" if denom else ".000"

    @property
    def slg_text(self):
        tb = self.singles + 2 * self.doubles + 3 * self.triples + 4 * self.homeruns
        return f"{(tb / self.ab):.3f}" if self.ab else ".000"

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
        self.injured_games_remaining = 0
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
    role: str = "SP"
    throws: str = "R"
    tier: str = "normal"
    age: int = 27
    salary: int = 0
    contract_games_remaining: int = 0
    contract_length: int = 0
    injured_games_remaining: int = 0

    coach_avg_bonus: int = 0
    coach_obp_bonus: int = 0
    coach_slg_bonus: int = 0
    coach_progress_games: int = 0

    fatigue: float = 0.0
    stamina: int = 70

    hot_streak_bonus: int = 0
    cold_streak_penalty: int = 0

    @property
    def max_stamina(self):
        return max(1, self.stamina)

    @property
    def remaining_stamina(self):
        return max(0, int(round(self.max_stamina - self.fatigue)))

    @property
    def stamina_ratio_text(self):
        return f"{self.remaining_stamina}/{self.max_stamina}"
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
    def max_average_minus(self):
        return self.average_minus + self.hot_streak_bonus - self.cold_streak_penalty

    @property
    def max_obp_minus(self):
        return self.obp_minus + self.hot_streak_bonus - self.cold_streak_penalty

    @property
    def max_slugging_minus(self):
        return self.slugging_minus + self.hot_streak_bonus - self.cold_streak_penalty

    @property
    def peak_average_minus(self):
        return self.max_average_minus

    @property
    def peak_obp_minus(self):
        return self.max_obp_minus

    @property
    def peak_slugging_minus(self):
        return self.max_slugging_minus

    def _fatigue_penalty(self, severe_cap=14, light_cap=2):
        ratio = self.remaining_stamina / max(1.0, float(self.max_stamina))
        if ratio >= 0.5:
            near_max = (1.0 - ratio) / 0.5
            return int(round(light_cap * near_max))
        deep_fatigue = (0.5 - ratio) / 0.5
        return light_cap + int(round(severe_cap * deep_fatigue))

    @property
    def display_average_minus(self):
        return max(0, self.max_average_minus - self._fatigue_penalty(severe_cap=14, light_cap=2))

    @property
    def display_obp_minus(self):
        return max(0, self.max_obp_minus - self._fatigue_penalty(severe_cap=14, light_cap=2))

    @property
    def display_slugging_minus(self):
        return max(0, self.max_slugging_minus - self._fatigue_penalty(severe_cap=16, light_cap=2))

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
        parts.append(f"STA {self.stamina_ratio_text}")
        return ", ".join(parts)

    def reset_season_stats(self):
        self.injured_games_remaining = 0
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


def gen_hitter(position: Optional[str] = None):
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
        position=position or random.choice(FIELDING_POSITIONS + ["UTIL"] * 2),
        bats=random.choice(["R", "L", "S"]),
        throws=random.choice(["R", "R", "R", "L"]),
        age=random.randint(20, 36),
        tier=tier,
    )


def gen_pitcher(role: Optional[str] = None):
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
        role=role or random.choice(["SP", "SP", "RP", "RP", "CL"]),
        throws=random.choice(["R", "R", "R", "L"]),
        age=random.randint(21, 38),
        stamina=random.randint(60, 95) if role in (None, "SP") else random.randint(35, 70),
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
    if h.position in {"C", "SS", "CF"}:
        score += 0.10
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
    score += (p.stamina - 60) / 200.0
    if p.role == "CL":
        score += 0.08
    return clamp(score / 2.0, -1.5, 1.5)


def score_to_salary(score: float) -> int:
    normalized = clamp(score, -1.5, 1.5)

    # map score from [-1.5, 1.5] to [0.0, 1.0]
    t = (normalized + 1.5) / 3.0

    # tuned so:
    # bad players ~= 1M-3M
    # most players ~= 5M-10M
    # elite/generational ~= 20M-30M
    salary = int(
        1_000_000
        + 2_000_000 * t
        + 8_000_000 * (t ** 2)
        + 17_000_000 * (t ** 4)
    )

    return max(MIN_SALARY, salary)


def assign_contract(obj, low=MIN_CONTRACT_GAMES, high=MAX_CONTRACT_GAMES, active=True, fixed_length=None):
    obj.contract_length = fixed_length if fixed_length is not None else random.randint(low, high)
    obj.contract_games_remaining = obj.contract_length if active else 0
    return obj


def activate_contract(obj):
    if getattr(obj, "contract_length", 0) <= 0:
        return obj
    if getattr(obj, "contract_games_remaining", 0) <= 0:
        obj.contract_games_remaining = obj.contract_length
    return obj


def assign_salary_hitter(h: Hitter) -> Hitter:
    score = hitter_performance_score(h)
    h.salary = score_to_salary(score)
    if h.tier == "superstar":
        h.salary = max(MIN_SALARY, int(h.salary * 1.25))
    elif h.tier == "bust":
        h.salary = max(MIN_SALARY, int(h.salary * 0.85))
    return assign_contract(h, active=True)


def assign_salary_pitcher(p: Pitcher) -> Pitcher:
    score = pitcher_performance_score(p)
    p.salary = score_to_salary(score)
    if p.tier == "superstar":
        p.salary = max(MIN_SALARY, int(p.salary * 1.25))
    elif p.tier == "bust":
        p.salary = max(MIN_SALARY, int(p.salary * 0.85))
    return assign_contract(p, active=True)


def assign_minor_salary_hitter(h: Hitter) -> Hitter:
    score = hitter_performance_score(h)
    mlb_salary = score_to_salary(score)
    h.salary = clamp(int(1_000_000 + (mlb_salary - 1_000_000) * 0.22), 1_000_000, 3_000_000)
    return assign_contract(h, active=False)


def assign_minor_salary_pitcher(p: Pitcher) -> Pitcher:
    score = pitcher_performance_score(p)
    mlb_salary = score_to_salary(score)
    p.salary = clamp(int(1_000_000 + (mlb_salary - 1_000_000) * 0.22), 1_000_000, 3_000_000)
    return assign_contract(p, active=False)


def gen_pitching_coach():
    c = PitchingCoach(
        name=random_name(),
        avg_boost=random.randint(2, 7),
        obp_boost=random.randint(2, 7),
        slg_boost=random.randint(3, 9),
        salary=random.randint(900_000, 5_000_000),
    )
    return assign_contract(c, 60, 180, active=False)


def gen_hitting_coach():
    c = HittingCoach(
        name=random_name(),
        avg_boost=random.randint(2, 7),
        obp_boost=random.randint(2, 7),
        ops_boost=random.randint(4, 12),
        salary=random.randint(900_000, 5_000_000),
    )
    return assign_contract(c, 60, 180, active=False)


def make_scandal_news(player_name: str) -> str:
    return f"{player_name} is {random.choice(SCANDAL_TYPES)}."
