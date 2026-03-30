import random

from league import generate_league
from player_gen_with_superstars_bust import SEASON_GAMES


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
        self.user_stat_history = []
        self.playoff_history = {"Divisional": [], "Pennant": [], "World Series": []}
        self.playoff_seeds = []
        self.playoff_mvp = None
        self.all_star_day = max(1, (len(self.schedule) * 2) // 3)
        self.all_star_played = False

    def build_schedule(self, teams):
        days = []
        teams = teams[:]
        if len(teams) % 2 == 1:
            teams.append(None)
        n = len(teams)
        for cycle in range(4):
            rotation = teams[:]
            for day_idx in range(n - 1):
                day_games = []
                for i in range(n // 2):
                    t1 = rotation[i]
                    t2 = rotation[n - 1 - i]
                    if t1 is None or t2 is None:
                        continue
                    if (cycle + day_idx + i) % 2 == 0:
                        day_games.append((t1, t2))
                    else:
                        day_games.append((t2, t1))
                days.append(day_games)
                rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]
        random.Random(21).shuffle(days)
        return days[:SEASON_GAMES]

    def standings(self):
        return sorted(self.teams, key=lambda t: ((t.wins / (t.wins + t.losses)) if (t.wins + t.losses) > 0 else 0.0, t.wins), reverse=True)

    def division_standings(self, division):
        return sorted([t for t in self.teams if t.division == division], key=lambda t: ((t.wins / (t.wins + t.losses)) if (t.wins + t.losses) > 0 else 0.0, t.wins), reverse=True)

    def regular_season_over(self):
        return self.current_day >= len(self.schedule)

    def remaining_days(self):
        return len(self.schedule) - self.current_day

    def archive_user_stats(self):
        roster = []
        for p in self.user_team.lineup + self.user_team.bench + self.user_team.rotation + self.user_team.bullpen:
            if getattr(self.user_team, "is_empty_slot", lambda _p: False)(p):
                continue
            if hasattr(p, "ops"):
                avg = round((p.hits / max(1, p.ab)), 3) if getattr(p, "ab", 0) > 0 else 0.0
                obp_denom = getattr(p, "ab", 0) + getattr(p, "walks", 0) + getattr(p, "hbp", 0)
                obp = round((p.hits + p.walks + p.hbp) / max(1, obp_denom), 3) if obp_denom > 0 else 0.0
                slg = round((p.singles + 2 * p.doubles + 3 * p.triples + 4 * p.homeruns) / max(1, p.ab), 3) if getattr(p, "ab", 0) > 0 else 0.0
                roster.append({
                    "kind": "hitter",
                    "name": p.name,
                    "position": getattr(p, "position", "---"),
                    "avg": avg,
                    "obp": obp,
                    "slg": slg,
                    "doubles": getattr(p, "doubles", 0),
                    "triples": getattr(p, "triples", 0),
                    "homeruns": getattr(p, "homeruns", 0),
                    "rbi": getattr(p, "rbi", 0),
                })
            else:
                roster.append({
                    "kind": "pitcher",
                    "name": p.name,
                    "role": getattr(p, "role", "--"),
                    "ip": getattr(p, "innings_pitched_text", "0.0"),
                    "era": getattr(p, "era", 0.0),
                    "strikeouts": getattr(p, "strikeouts", 0),
                    "walks": getattr(p, "walks", 0),
                    "stamina_ratio_text": getattr(p, "stamina_ratio_text", "0/0"),
                })
        self.user_stat_history.append({
            "year": self.year,
            "team_name": self.user_team.name,
            "wins": self.user_team.wins,
            "losses": self.user_team.losses,
            "champion": self.champion.name if self.champion else None,
            "roster": roster,
        })

    def start_playoffs(self):
        divisions = sorted({t.division for t in self.teams})
        seeds = []
        for division in divisions:
            seeds.append(self.division_standings(division)[0])
        remaining = [t for t in self.standings() if t not in seeds]
        seeds.extend(remaining[:4])
        seeds = seeds[:8]
        self.playoff_seeds = seeds[:]
        self.playoff_history = {"Divisional": [], "Pennant": [], "World Series": []}
        self.playoff_mvp = None
        self.playoff_round = "Divisional"
        self.playoff_matchups = [(seeds[0], seeds[7]), (seeds[1], seeds[6]), (seeds[2], seeds[5]), (seeds[3], seeds[4])]

    def play_playoff_round(self, game_runner):
        current_round = self.playoff_round
        results = []
        for away_team, home_team in self.playoff_matchups:
            results.append(game_runner(away_team, home_team, current_round))
        self.playoff_history[current_round] = results[:]
        winners = [r["winner"] for r in results]
        if current_round == "Divisional":
            self.playoff_round = "Pennant"
            self.playoff_matchups = [(winners[0], winners[3]), (winners[1], winners[2])]
        elif current_round == "Pennant":
            self.playoff_round = "World Series"
            self.playoff_matchups = [(winners[0], winners[1])]
        else:
            self.playoff_round = "Complete"
            self.champion = winners[0]
            self.playoff_matchups = []
        self.playoff_mvp = self.compute_playoff_mvp()
        return results

    def _all_postseason_players(self):
        seen = set()
        for round_results in self.playoff_history.values():
            for result in round_results:
                for team_key in ("away_team", "home_team"):
                    team = result.get(team_key)
                    if team is None:
                        continue
                    for player in team.lineup + team.bench + team.rotation + team.bullpen:
                        if getattr(team, "is_empty_slot", lambda _p: False)(player):
                            continue
                        if id(player) not in seen:
                            seen.add(id(player))
                            yield player

    def compute_playoff_mvp(self):
        best = None
        best_score = None
        for player in self._all_postseason_players():
            if hasattr(player, "ops"):
                score = (
                    getattr(player, "homeruns", 0) * 12
                    + getattr(player, "rbi", 0) * 5
                    + getattr(player, "hits", 0) * 2
                    + getattr(player, "walks", 0)
                )
            else:
                outs = getattr(player, "outs_recorded", 0)
                score = (
                    getattr(player, "strikeouts", 0) * 3
                    + outs
                    - getattr(player, "walks", 0) * 2
                    - getattr(player, "hits_allowed", 0)
                )
            if best is None or score > best_score:
                best = player
                best_score = score
        return best
