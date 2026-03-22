from dataclasses import dataclass, field
from typing import Optional
from sim.player_gen_with_superstars_bust import (
    gen_hitter,
    gen_pitcher,
    assign_salary_hitter,
    assign_salary_pitcher,
    assign_minor_salary_hitter,
    assign_minor_salary_pitcher,
)

SEASON_GAMES = 60

@dataclass
class Team:
    name: str
    division: str = "East"
    lineup: list = field(default_factory=list)
    bench: list = field(default_factory=list)

    rotation: list = field(default_factory=list)
    rotation_slot: int = 0
    bullpen: list = field(default_factory=list)

    minors_hitters: list = field(default_factory=list)
    minors_pitchers: list = field(default_factory=list)

    starter: object = None
    middle_reliever: object = None
    closer: object = None

    pitching_coach: object = None
    hitting_coaches: list = field(default_factory=list)
    pitching_assignment_name: Optional[str] = None
    hitting_assignment_names: list = field(default_factory=list)

    wins: int = 0
    losses: int = 0
    budget: int = 180_000_000

    def total_salary(self):
        total = 0
        for group in [self.lineup, self.bench, self.rotation, self.bullpen, self.minors_hitters, self.minors_pitchers]:
            for player in group:
                total += getattr(player, "salary", 0)

        if self.pitching_coach:
            total += self.pitching_coach.salary
        for coach in self.hitting_coaches:
            total += coach.salary
        return total

    def can_afford(self, incoming_salary, outgoing_salary=0):
        return self.total_salary() - outgoing_salary + incoming_salary <= self.budget

    def cycle_rotation(self):
        if self.rotation:
            self.rotation_slot = (self.rotation_slot + 1) % len(self.rotation)
            self.starter = self.rotation[self.rotation_slot]

    def refresh_roles(self):
        if self.rotation and (self.starter is None or self.starter not in self.rotation):
            self.starter = self.rotation[self.rotation_slot % len(self.rotation)]
        if self.bullpen and (self.middle_reliever is None or self.middle_reliever not in self.bullpen):
            self.middle_reliever = self.bullpen[0]
        if len(self.bullpen) > 1 and (self.closer is None or self.closer not in self.bullpen):
            self.closer = self.bullpen[1]

    def assign_pitching_coach_to_pitcher(self, pitcher_name: str | None):
        self.pitching_assignment_name = pitcher_name

    def assign_hitting_coach_to_hitter(self, hitter_name: str):
        if hitter_name not in self.hitting_assignment_names and len(self.hitting_assignment_names) < 2:
            self.hitting_assignment_names.append(hitter_name)

    def clear_hitting_assignments(self):
        self.hitting_assignment_names = []

    def apply_coaching_progress(self):
        if self.pitching_coach and self.pitching_assignment_name:
            for p in self.rotation + self.bullpen + self.minors_pitchers:
                if p.name == self.pitching_assignment_name:
                    p.coach_progress_games += 1
                    if p.coach_progress_games % 4 == 0:
                        p.coach_avg_bonus += self.pitching_coach.avg_boost
                        p.coach_obp_bonus += self.pitching_coach.obp_boost
                        p.coach_slg_bonus += self.pitching_coach.slg_boost

        for coach in self.hitting_coaches:
            for h in self.lineup + self.bench + self.minors_hitters:
                if h.name in self.hitting_assignment_names:
                    h.coach_progress_games += 1
                    if h.coach_progress_games % 4 == 0:
                        h.coach_avg_bonus += coach.avg_boost
                        h.coach_obp_bonus += coach.obp_boost
                        h.coach_ops_bonus += coach.ops_boost

    def recover_pitcher_fatigue(self, used_names: set[str]):
        everyone = self.rotation + self.bullpen + self.minors_pitchers
        for p in everyone:
            if p.name not in used_names:
                p.fatigue = max(0.0, p.fatigue - 8.0)

    def apply_postgame_fatigue(self, usage: dict[str, float]):
        everyone = self.rotation + self.bullpen + self.minors_pitchers
        name_to_pitcher = {p.name: p for p in everyone}
        for name, innings in usage.items():
            if name in name_to_pitcher:
                p = name_to_pitcher[name]
                p.fatigue = min(100.0, p.fatigue + innings * 5.0)

    def decrement_contracts(self, season_games=SEASON_GAMES):
        expired = []
        for obj in (
            self.lineup + self.bench + self.rotation + self.bullpen +
            self.minors_hitters + self.minors_pitchers +
            ([self.pitching_coach] if self.pitching_coach else []) +
            self.hitting_coaches
        ):
            if hasattr(obj, "contract_games_remaining"):
                obj.contract_games_remaining -= season_games
                if obj.contract_games_remaining <= 0:
                    expired.append(obj)
        return expired

    def remove_person(self, obj):
        for group_name in ["lineup", "bench", "rotation", "bullpen", "minors_hitters", "minors_pitchers", "hitting_coaches"]:
            group = getattr(self, group_name)
            if obj in group:
                group.remove(obj)
                return True
        if self.pitching_coach == obj:
            self.pitching_coach = None
            return True
        return False

    def reset_team_for_new_season(self):
        self.wins = 0
        self.losses = 0
        self.refresh_roles()
        for h in self.lineup + self.bench + self.minors_hitters:
            h.reset_season_stats()
        for p in self.rotation + self.bullpen + self.minors_pitchers:
            p.reset_season_stats()

def make_paid_hitter():
    return assign_salary_hitter(gen_hitter())

def make_paid_pitcher():
    return assign_salary_pitcher(gen_pitcher())

def make_minor_hitter():
    return assign_minor_salary_hitter(gen_hitter())

def make_minor_pitcher():
    return assign_minor_salary_pitcher(gen_pitcher())

def generate_team(
    name,
    division="East",
    lineup_size=9,
    bench_size=5,
    rotation_size=5,
    bullpen_size=7,
    minors_hitters_size=10,
    minors_pitchers_size=8,
):
    lineup = [make_paid_hitter() for _ in range(lineup_size)]
    bench = [make_paid_hitter() for _ in range(bench_size)]
    rotation = [make_paid_pitcher() for _ in range(rotation_size)]
    bullpen = [make_paid_pitcher() for _ in range(bullpen_size)]
    minors_hitters = [make_minor_hitter() for _ in range(minors_hitters_size)]
    minors_pitchers = [make_minor_pitcher() for _ in range(minors_pitchers_size)]

    team = Team(
        name=name,
        division=division,
        lineup=lineup,
        bench=bench,
        rotation=rotation,
        bullpen=bullpen,
        minors_hitters=minors_hitters,
        minors_pitchers=minors_pitchers,
        starter=rotation[0] if rotation else None,
        middle_reliever=bullpen[0] if bullpen else None,
        closer=bullpen[1] if len(bullpen) > 1 else (bullpen[0] if bullpen else None),
        budget=180_000_000,
    )
    return team