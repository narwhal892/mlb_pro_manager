from dataclasses import dataclass, field
from typing import Optional
from scouting import ScoutedProspect
from franchise_culture import ensure_franchise_culture_state

from player_gen_with_superstars_bust import (
    BENCH_POSITIONS,
    activate_contract,
    assign_minor_salary_hitter,
    assign_minor_salary_pitcher,
    assign_salary_hitter,
    assign_salary_pitcher,
    gen_hitter,
    gen_pitcher,
)

SEASON_GAMES = 60
REQUIRED_LINEUP_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
TARGET_BENCH_SIZE = 9
TARGET_MINORS_HITTERS_SIZE = 10
TARGET_MINORS_PITCHERS_SIZE = 8
TARGET_BULLPEN_SIZE = 8
scout_stars: int = 0
scout_salary: int = 0
scout_games_until_report: int = 0
scouted_prospects: list = field(default_factory=list)

@dataclass
class EmptyRosterSlot:
    slot_type: str = "bench"
    side: str = "hitter"
    name: str = "EMPTY SLOT"
    salary: int = 0
    contract_games_remaining: int = 0
    contract_length: int = 0
    position: str = "---"
    role: str = "--"
    fatigue: float = 0.0
    stamina: int = 0

    @property
    def character_name(self):
        return self.name


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
    batting_order: list = field(default_factory=list)
    next_game_starter_name: Optional[str] = None
    next_game_reliever_names: list = field(default_factory=list)
    wins: int = 0
    losses: int = 0
    budget: int = 165_000_000
    spin_rate_lab_slots: list = field(default_factory=list)
    spin_rate_lab_progress: dict = field(default_factory=dict)
    ticket_price_level: int = 5
    vendor_price_level: int = 5
    morale: int = 500
    active_hot_streaks: list = field(default_factory=list)
    active_cold_streaks: list = field(default_factory=list)

    def __post_init__(self):
        self.repair_roster_structure()
        self.ensure_spin_rate_lab_state()
        self.ensure_scouting_state()
        ensure_franchise_culture_state(self)
        self.refresh_roles()
        self.ensure_batting_order()

    def is_empty_slot(self, obj):
        return isinstance(obj, EmptyRosterSlot)

    def real_hitters(self):
        return [p for p in self.lineup + self.bench + self.minors_hitters if not self.is_empty_slot(p)]
    
    def ensure_scouting_state(self):
        if not hasattr(self, "scout_stars") or self.scout_stars is None:
            self.scout_stars = 0
        if not hasattr(self, "scout_salary") or self.scout_salary is None:
            self.scout_salary = 0
        if not hasattr(self, "scout_games_until_report") or self.scout_games_until_report is None:
            self.scout_games_until_report = 0
        if not hasattr(self, "scouted_prospects") or self.scouted_prospects is None:
            self.scouted_prospects = []

    def total_salary(self):
        scout_cost = getattr(self, "scout_salary", 0)
        return sum(getattr(obj, "salary", 0) for obj in self.all_people()) + scout_cost

    def real_pitchers(self):
        return [p for p in self.rotation + self.bullpen + self.minors_pitchers if not self.is_empty_slot(p)]

    def all_hitters(self):
        return [p for p in self.lineup + self.bench if not self.is_empty_slot(p)]

    def all_pitchers(self):
        return [p for p in self.rotation + self.bullpen if not self.is_empty_slot(p)]

    def all_people(self):
        out = self.all_hitters() + self.all_pitchers()
        if self.pitching_coach:
            out.append(self.pitching_coach)
        out.extend(self.hitting_coaches)
        return out

    def player_is_injured(self, player):
        return getattr(player, "injured_games_remaining", 0) > 0

    def decrement_injuries(self, games=1):
        healed = []
        for player in self.lineup + self.bench + self.rotation + self.bullpen + self.minors_hitters + self.minors_pitchers:
            if self.is_empty_slot(player):
                continue
            if getattr(player, "injured_games_remaining", 0) > 0:
                player.injured_games_remaining = max(0, player.injured_games_remaining - games)
                if player.injured_games_remaining == 0:
                    healed.append(player)
        return healed

    def active_roster_players(self):
        return [p for p in (self.lineup + self.bench + self.rotation + self.bullpen) if not self.is_empty_slot(p)]

    def total_salary(self):
        return sum(getattr(obj, "salary", 0) for obj in self.all_people())

    def projected_salary_after_add(self, incoming_salary, outgoing_salary=0):
        return self.total_salary() - outgoing_salary + incoming_salary

    def can_afford(self, incoming_salary, outgoing_salary=0):
        return self.projected_salary_after_add(incoming_salary, outgoing_salary) <= self.budget

    def budget_room(self):
        return self.budget - self.total_salary()

    def make_empty_hitter_slot(self, slot_type="bench"):
        return EmptyRosterSlot(slot_type=slot_type, side="hitter", position="---", role="--")

    def make_empty_pitcher_slot(self, slot_type="minors"):
        return EmptyRosterSlot(slot_type=slot_type, side="pitcher", position="---", role="--")

    def normalize_optional_slots(self):
        self.rotation = list(self.rotation[:5])
        while len(self.rotation) < 5:
            self.rotation.append(self.make_empty_pitcher_slot("rotation"))

        self.bench = list(self.bench[:TARGET_BENCH_SIZE])
        while len(self.bench) < TARGET_BENCH_SIZE:
            self.bench.append(self.make_empty_hitter_slot("bench"))

        self.minors_hitters = list(self.minors_hitters[:TARGET_MINORS_HITTERS_SIZE])
        while len(self.minors_hitters) < TARGET_MINORS_HITTERS_SIZE:
            self.minors_hitters.append(self.make_empty_hitter_slot("minors"))

        self.bullpen = list(self.bullpen[:TARGET_BULLPEN_SIZE])
        while len(self.bullpen) < TARGET_BULLPEN_SIZE:
            self.bullpen.append(self.make_empty_pitcher_slot("bullpen"))

        self.minors_pitchers = list(self.minors_pitchers[:TARGET_MINORS_PITCHERS_SIZE])
        while len(self.minors_pitchers) < TARGET_MINORS_PITCHERS_SIZE:
            self.minors_pitchers.append(self.make_empty_pitcher_slot("minors"))

    def cycle_rotation(self):
        real_rotation = self.real_rotation()
        if real_rotation:
            self.rotation_slot = (self.rotation_slot + 1) % len(real_rotation)
            self.starter = real_rotation[self.rotation_slot]
            self.next_game_starter_name = self.starter.name

    def real_rotation(self):
        return [p for p in self.rotation if not self.is_empty_slot(p)]

    def real_bullpen(self):
        return [p for p in self.bullpen if not self.is_empty_slot(p)]

    def refresh_roles(self):
        real_rotation = self.real_rotation()
        real_bullpen = self.real_bullpen()
        if real_rotation:
            self.rotation_slot = self.rotation_slot % len(real_rotation)
            if self.starter is None or self.starter not in real_rotation:
                self.starter = real_rotation[self.rotation_slot]
        else:
            self.rotation_slot = 0
            self.starter = None
        if real_bullpen and (self.middle_reliever is None or self.middle_reliever not in real_bullpen):
            self.middle_reliever = real_bullpen[0]
        elif not real_bullpen:
            self.middle_reliever = None
        if len(real_bullpen) > 1 and (self.closer is None or self.closer not in real_bullpen):
            self.closer = real_bullpen[1]
        elif real_bullpen and self.closer not in real_bullpen:
            self.closer = real_bullpen[0]
        elif not real_bullpen:
            self.closer = None
        self.next_game_starter_name = self.starter.name if self.starter else None
        self.next_game_reliever_names = [p.name for p in [self.middle_reliever, self.closer] if p]

    def ensure_batting_order(self):
        self.repair_roster_structure()
        real_lineup = [p for p in self.lineup if not self.is_empty_slot(p)]
        if not self.batting_order or any(p not in real_lineup for p in self.batting_order):
            self.batting_order = real_lineup[:]
        if len(self.batting_order) > len(real_lineup):
            self.batting_order = [p for p in self.batting_order if p in real_lineup]
        for p in real_lineup:
            if p not in self.batting_order:
                self.batting_order.append(p)
        self.batting_order = self.batting_order[:9]

    def get_active_lineup_for_game(self):
        self.ensure_batting_order()
        return self.batting_order[:]

    def validate_lineup_positions(self):
        for idx, pos in enumerate(REQUIRED_LINEUP_POSITIONS):
            if idx >= len(self.lineup):
                return False, REQUIRED_LINEUP_POSITIONS[idx:]
            player = self.lineup[idx]
            if self.is_empty_slot(player):
                return False, [pos]
            if self.player_is_injured(player):
                return False, [f"{pos} ({player.name} injured)"]
            if pos not in self.eligible_lineup_positions_for(player):
                return False, [pos]
        return True, []

    def repair_roster_structure(self):
        lineup_pool = [p for p in self.lineup if not self.is_empty_slot(p)]
        bench_pool = [p for p in self.bench if not self.is_empty_slot(p)]
        self.lineup = self._ensure_positions(lineup_pool, bench_pool, REQUIRED_LINEUP_POSITIONS)
        leftovers = [p for p in lineup_pool + bench_pool if p not in self.lineup]
        self.bench = leftovers[:TARGET_BENCH_SIZE]
        self.normalize_optional_slots()

    def _ensure_positions(self, lineup, bench, required_positions):
        lineup = list(lineup)
        bench = list(bench)
        everyone = lineup + bench
        used = set()
        ordered = []

        for idx, pos in enumerate(required_positions):
            chosen = None

            # 1. preserve whoever is already in this lineup slot if they can legally play it
            if idx < len(lineup):
                current = lineup[idx]
                if current and not self.is_empty_slot(current):
                    if pos in self.eligible_lineup_positions_for(current):
                        chosen = current

            # 2. exact match from remaining players
            if chosen is None:
                for p in everyone:
                    if id(p) in used:
                        continue
                    if getattr(p, "position", None) == pos:
                        chosen = p
                        break

            # 3. flexible-role match from remaining players
            if chosen is None:
                for p in everyone:
                    if id(p) in used:
                        continue
                    if pos in self.eligible_lineup_positions_for(p):
                        chosen = p
                        break

            # 4. fallback filler
            if chosen is None:
                chosen = make_paid_hitter(pos)

            used.add(id(chosen))
            ordered.append(chosen)

        return ordered

    def assign_pitching_coach_to_pitcher(self, pitcher_name: Optional[str]):
        self.pitching_assignment_name = pitcher_name

    def assign_hitting_coach_to_hitter(self, hitter_name: str, slot_index: Optional[int] = None):
        if slot_index is None:
            if hitter_name not in self.hitting_assignment_names and len(self.hitting_assignment_names) < 2:
                self.hitting_assignment_names.append(hitter_name)
            return
        while len(self.hitting_assignment_names) <= slot_index:
            self.hitting_assignment_names.append("")
        self.hitting_assignment_names[slot_index] = hitter_name
        while self.hitting_assignment_names and self.hitting_assignment_names[-1] == "":
            self.hitting_assignment_names.pop()

    def clear_hitting_assignments(self):
        self.hitting_assignment_names = []

    def apply_coaching_progress(self):
        if self.pitching_coach and self.pitching_assignment_name:
            for p in self.all_pitchers():
                if p.name == self.pitching_assignment_name:
                    p.coach_progress_games += 1
                    if p.coach_progress_games % 8 == 0:
                        p.coach_avg_bonus += self.pitching_coach.avg_boost
                        p.coach_obp_bonus += self.pitching_coach.obp_boost
                        p.coach_slg_bonus += self.pitching_coach.slg_boost
        for coach in self.hitting_coaches:
            for h in self.all_hitters():
                if h.name in self.hitting_assignment_names:
                    h.coach_progress_games += 1
                    if h.coach_progress_games % 8 == 0:
                        h.coach_avg_bonus += coach.avg_boost
                        h.coach_obp_bonus += coach.obp_boost
                        h.coach_ops_bonus += coach.ops_boost

    def coached_player_names(self):
        out = []
        if self.pitching_assignment_name:
            out.append(self.pitching_assignment_name)
        out.extend([name for name in self.hitting_assignment_names if name])
        return out

    def eligible_lineup_positions_for(self, player):
        pos = getattr(player, "position", None)

        # Exact position players (C, 1B, etc.)
        if pos in REQUIRED_LINEUP_POSITIONS:
            return [pos]

        # Utility = anywhere except catcher
        if pos == "UTIL":
            return [p for p in REQUIRED_LINEUP_POSITIONS if p != "C"]

        # Outfielders can play LF/CF/RF
        if pos == "OF":
            return ["LF", "CF", "RF"]

        # Infielders can play 1B/2B/3B/SS
        if pos == "INF":
            return ["1B", "2B", "3B", "SS"]

        return []

    def can_start_at_lineup_index(self, player, index):
        if self.is_empty_slot(player):
            return False
        if not (0 <= index < len(REQUIRED_LINEUP_POSITIONS)):
            return False
        return REQUIRED_LINEUP_POSITIONS[index] in self.eligible_lineup_positions_for(player)

    def cycle_hitting_assignment(self, slot_index=0):
        hitters = self.real_hitters()
        if not hitters:
            return None
        current = self.hitting_assignment_names[slot_index] if slot_index < len(self.hitting_assignment_names) else None
        names = [h.name for h in hitters]
        if current not in names:
            chosen = hitters[0].name
        else:
            chosen = hitters[(names.index(current) + 1) % len(hitters)].name
        self.assign_hitting_coach_to_hitter(chosen, slot_index)
        return chosen

    def cycle_pitching_assignment(self):
        pitchers = [p for p in self.all_pitchers() if getattr(p, "remaining_stamina", 0) > 0]
        if not pitchers:
            pitchers = self.all_pitchers()
        if not pitchers:
            self.pitching_assignment_name = None
            return None
        names = [p.name for p in pitchers]
        current = self.pitching_assignment_name
        if current not in names:
            self.pitching_assignment_name = names[0]
        else:
            self.pitching_assignment_name = names[(names.index(current) + 1) % len(names)]
        return self.pitching_assignment_name

    def ensure_spin_rate_lab_state(self):
        if not hasattr(self, "spin_rate_lab_slots") or self.spin_rate_lab_slots is None:
            self.spin_rate_lab_slots = []
        if not hasattr(self, "spin_rate_lab_progress") or self.spin_rate_lab_progress is None:
            self.spin_rate_lab_progress = {}
        valid_names = {p.name for p in self.available_spin_lab_pitchers()}
        cleaned_slots = []
        for name in self.spin_rate_lab_slots:
            if name in valid_names and name not in cleaned_slots:
                cleaned_slots.append(name)
        self.spin_rate_lab_slots = cleaned_slots[:2]
        self.spin_rate_lab_progress = {name: int(self.spin_rate_lab_progress.get(name, 0)) for name in self.spin_rate_lab_slots}

    def available_spin_lab_pitchers(self):
        return [p for p in (self.rotation[:5] + self.bullpen) if not self.is_empty_slot(p)]

    def toggle_spin_rate_lab_pitcher(self, pitcher_name):
        self.ensure_spin_rate_lab_state()
        available = {p.name for p in self.available_spin_lab_pitchers()}
        if pitcher_name not in available:
            return False, "That pitcher is not in your current starter/reliever pool."
        if pitcher_name in self.spin_rate_lab_slots:
            self.spin_rate_lab_slots.remove(pitcher_name)
            self.spin_rate_lab_progress.pop(pitcher_name, None)
            return True, f"Removed {pitcher_name} from Spin Rate Lab."
        if len(self.spin_rate_lab_slots) >= 2:
            return False, "Spin Rate Lab is full (2 pitchers max)."
        self.spin_rate_lab_slots.append(pitcher_name)
        self.spin_rate_lab_progress.setdefault(pitcher_name, 0)
        return True, f"Added {pitcher_name} to Spin Rate Lab."

    def apply_spin_rate_lab_progress(self, games=1, boost_amount=2, games_per_boost=5):
        self.ensure_spin_rate_lab_state()
        if not self.spin_rate_lab_slots:
            return []
        boosted = []
        name_to_pitcher = {p.name: p for p in self.available_spin_lab_pitchers()}
        for name in list(self.spin_rate_lab_slots):
            pitcher = name_to_pitcher.get(name)
            if pitcher is None:
                self.spin_rate_lab_progress.pop(name, None)
                continue
            progress = int(self.spin_rate_lab_progress.get(name, 0)) + games
            while progress >= games_per_boost:
                pitcher.average_minus += boost_amount
                progress -= games_per_boost
                boosted.append((name, boost_amount))
            self.spin_rate_lab_progress[name] = progress
        self.ensure_spin_rate_lab_state()
        return boosted

    def apply_spin_rate_lab(self, games=1, boost_amount=2, games_per_boost=5):
        boosted = self.apply_spin_rate_lab_progress(games=games, boost_amount=boost_amount, games_per_boost=games_per_boost)
        if not self.spin_rate_lab_slots:
            return False, "Spin Rate Lab is empty."
        if boosted:
            details = ", ".join(f"{name} +{amount} AVG-" for name, amount in boosted)
            return True, f"Spin Rate Lab development applied: {details}"
        return True, "Spin Rate Lab progress saved."

    def recover_pitcher_fatigue(self, used_names: set[str]):
        for p in self.all_pitchers():
            if p.name not in used_names:
                recovery = max(4.0, p.max_stamina / 5.0)
                p.fatigue = max(0.0, p.fatigue - recovery)

    def apply_postgame_fatigue(self, usage: dict[str, float]):
        name_to_pitcher = {p.name: p for p in self.all_pitchers()}
        for name, innings in usage.items():
            if name in name_to_pitcher:
                p = name_to_pitcher[name]
                if p.role == "SP":
                    target_empty_innings = max(5.0, 9.0 + ((p.max_stamina - 70) / 10.0))
                else:
                    target_empty_innings = max(1.5, 3.0 + ((p.max_stamina - 50) / 18.0))
                drain_per_inning = p.max_stamina / max(1.0, target_empty_innings)
                p.fatigue = min(float(p.max_stamina), p.fatigue + innings * drain_per_inning)

    def decrement_contracts(self, games=1):
        expired = []
        for obj in self.all_people():
            if hasattr(obj, "contract_games_remaining") and getattr(obj, "contract_games_remaining", 0) > 0:
                obj.contract_games_remaining = max(0, obj.contract_games_remaining - games)
                if obj.contract_games_remaining <= 0:
                    expired.append(obj)
        return expired

    def players_nearing_expiry(self, threshold=8):
        return [p for p in self.all_people() if hasattr(p, "contract_games_remaining") and 0 < p.contract_games_remaining <= threshold]

    def remove_person(self, obj):
        for group_name in ["lineup", "bench", "rotation", "bullpen", "minors_hitters", "minors_pitchers", "hitting_coaches", "batting_order"]:
            group = getattr(self, group_name)
            if obj in group:
                idx = group.index(obj)
                if group_name == "bench":
                    group[idx] = self.make_empty_hitter_slot("bench")
                elif group_name == "minors_hitters":
                    group[idx] = self.make_empty_hitter_slot("minors")
                elif group_name == "minors_pitchers":
                    group[idx] = self.make_empty_pitcher_slot("minors")
                else:
                    group.remove(obj)
                self.ensure_batting_order()
                self.refresh_roles()
                self.normalize_optional_slots()
                return True
        if self.pitching_coach == obj:
            self.pitching_coach = None
            return True
        return False

    def add_free_agent_to_bench(self, player):
        for idx, slot in enumerate(self.bench):
            if self.is_empty_slot(slot):
                activate_contract(player)
                self.bench[idx] = player
                self.ensure_batting_order()
                self.normalize_optional_slots()
                return
        activate_contract(player)
        self.bench.append(player)
        self.normalize_optional_slots()
        self.ensure_batting_order()

    def add_free_agent_to_minors(self, player):
        target = self.minors_pitchers if hasattr(player, "role") else self.minors_hitters
        slot_factory = self.make_empty_pitcher_slot if hasattr(player, "role") else self.make_empty_hitter_slot
        slot_kind = "minors"
        for idx, slot in enumerate(target):
            if self.is_empty_slot(slot):
                activate_contract(player)
                target[idx] = player
                self.normalize_optional_slots()
                return
        activate_contract(player)
        target.append(player)
        self.normalize_optional_slots()

    def refill_minor_league_slots(self):
        for idx, player in enumerate(self.minors_hitters):
            if self.is_empty_slot(player):
                self.minors_hitters[idx] = make_minor_hitter()
        for idx, player in enumerate(self.minors_pitchers):
            if self.is_empty_slot(player):
                role = "SP" if idx < 3 else "RP"
                self.minors_pitchers[idx] = make_minor_pitcher(role)
        self.normalize_optional_slots()

    def call_up_minor_hitter(self, minor_index):
        if not (0 <= minor_index < len(self.minors_hitters)):
            return False, "Invalid minor league hitter slot."
        player = self.minors_hitters[minor_index]
        if self.is_empty_slot(player):
            return False, "That minor league slot is empty."
        empty_bench = next((i for i, p in enumerate(self.bench) if self.is_empty_slot(p)), None)
        if empty_bench is None:
            return False, "Bench is full. Drop or send down a bench player first."
        activate_contract(player)
        self.bench[empty_bench] = player
        self.minors_hitters[minor_index] = self.make_empty_hitter_slot("minors")
        self.ensure_batting_order()
        self.normalize_optional_slots()
        return True, f"Called up {player.name} to the bench."

    def send_down_bench_hitter(self, bench_index):
        if not (0 <= bench_index < len(self.bench)):
            return False, "Invalid bench slot."
        player = self.bench[bench_index]
        if self.is_empty_slot(player):
            return False, "That bench slot is empty."
        empty_minor = next((i for i, p in enumerate(self.minors_hitters) if self.is_empty_slot(p)), None)
        if empty_minor is None:
            return False, "Minor league hitter slots are full."
        self.minors_hitters[empty_minor] = player
        self.bench[bench_index] = self.make_empty_hitter_slot("bench")
        if player in self.batting_order:
            self.batting_order = [p for p in self.batting_order if p != player]
        self.ensure_batting_order()
        self.normalize_optional_slots()
        return True, f"Sent {player.name} down to the minors."

    def call_up_minor_pitcher(self, minor_index):
        if not (0 <= minor_index < len(self.minors_pitchers)):
            return False, "Invalid minor league pitcher slot."
        player = self.minors_pitchers[minor_index]
        if self.is_empty_slot(player):
            return False, "That minor league slot is empty."
        empty_bullpen = next((i for i, p in enumerate(self.bullpen) if self.is_empty_slot(p)), None)
        if empty_bullpen is None:
            return False, "Bullpen is full. Drop or send down a pitcher first."
        activate_contract(player)
        self.bullpen[empty_bullpen] = player
        self.minors_pitchers[minor_index] = self.make_empty_pitcher_slot("minors")
        self.refresh_roles()
        self.normalize_optional_slots()
        return True, f"Called up {player.name} to the bullpen."

    def send_down_bullpen_pitcher(self, bullpen_index):
        if not (0 <= bullpen_index < len(self.bullpen)):
            return False, "Invalid bullpen slot."
        player = self.bullpen[bullpen_index]
        if self.is_empty_slot(player):
            return False, "That bullpen slot is empty."
        empty_minor = next((i for i, p in enumerate(self.minors_pitchers) if self.is_empty_slot(p)), None)
        if empty_minor is None:
            return False, "Minor league pitcher slots are full."
        if player in [self.middle_reliever, self.closer]:
            return False, "Reassign relief roles before sending that pitcher down."
        self.minors_pitchers[empty_minor] = player
        self.bullpen[bullpen_index] = self.make_empty_pitcher_slot("bullpen")
        self.refresh_roles()
        self.normalize_optional_slots()
        return True, f"Sent {player.name} down to the minors."

    def drop_player_from_optional_group(self, group_name, index):
        groups = {
            "bench": (self.bench, self.make_empty_hitter_slot),
            "minors_hitters": (self.minors_hitters, self.make_empty_hitter_slot),
            "minors_pitchers": (self.minors_pitchers, self.make_empty_pitcher_slot),
        }
        if group_name not in groups:
            return False, "Only bench or minors players can be dropped."
        group, factory = groups[group_name]
        if not (0 <= index < len(group)):
            return False, "Invalid roster slot."
        player = group[index]
        if self.is_empty_slot(player):
            return False, "That slot is already empty."
        group[index] = factory("minors" if "minors" in group_name else "bench")
        if player in self.batting_order:
            self.batting_order = [p for p in self.batting_order if p != player]
        self.refresh_roles()
        self.ensure_batting_order()
        self.normalize_optional_slots()
        return True, f"Dropped {player.name} and opened a salary slot."

    def budget_cut_candidates(self):
        candidates = []
        for name in ["minors_hitters", "minors_pitchers", "bench"]:
            for idx, player in enumerate(getattr(self, name)):
                if not self.is_empty_slot(player):
                    candidates.append((name, idx, player))
        candidates.sort(key=lambda x: (getattr(x[2], "salary", 0), getattr(x[2], "age", 25)), reverse=True)
        return candidates

    def ensure_within_budget(self):
        self.normalize_optional_slots()
        while self.total_salary() > self.budget:
            candidates = self.budget_cut_candidates()
            if not candidates:
                break
            name, idx, _player = candidates[0]
            self.drop_player_from_optional_group(name, idx)
        return self.total_salary() <= self.budget

    def reset_team_for_new_season(self):
        self.wins = 0
        self.losses = 0
        self.refresh_roles()
        self.ensure_batting_order()
        self.ensure_within_budget()
        for h in self.all_hitters():
            h.reset_season_stats()
        for p in self.all_pitchers():
            p.reset_season_stats()

    def find_player(self, name):
        for p in self.all_people():
            if getattr(p, "name", None) == name:
                return p
        return None


def make_paid_hitter(position=None):
    return assign_salary_hitter(gen_hitter(position))


def make_paid_pitcher(role=None):
    return assign_salary_pitcher(gen_pitcher(role))


def make_minor_hitter(position=None):
    return assign_minor_salary_hitter(gen_hitter(position))


def make_minor_pitcher(role=None):
    return assign_minor_salary_pitcher(gen_pitcher(role))


def generate_team(
    name,
    division="East",
    bench_size=TARGET_BENCH_SIZE,
    rotation_size=5,
    bullpen_size=TARGET_BULLPEN_SIZE,
    minors_hitters_size=TARGET_MINORS_HITTERS_SIZE,
    minors_pitchers_size=TARGET_MINORS_PITCHERS_SIZE,
):
    lineup = [make_paid_hitter(pos) for pos in REQUIRED_LINEUP_POSITIONS]
    bench = [make_paid_hitter(pos) for pos in BENCH_POSITIONS[:min(bench_size, len(BENCH_POSITIONS))]]
    while len(bench) < bench_size:
        bench.append(make_paid_hitter("UTIL"))
    rotation = [make_paid_pitcher("SP") for _ in range(rotation_size)]
    bullpen = [make_paid_pitcher("RP") for _ in range(max(0, bullpen_size - 1))] + [make_paid_pitcher("CL")]
    minors_hitters = [make_minor_hitter() for _ in range(minors_hitters_size)]
    minors_pitchers = [make_minor_pitcher("SP" if i < 3 else "RP") for i in range(minors_pitchers_size)]
    team = Team(
        name=name,
        division=division,
        lineup=lineup,
        bench=bench,
        rotation=rotation,
        bullpen=bullpen,
        minors_hitters=minors_hitters,
        minors_pitchers=minors_pitchers,
        starter=rotation[0],
        middle_reliever=bullpen[0],
        closer=bullpen[-1],
        budget=165_000_000,
    )
    team.ensure_within_budget()
    return team
