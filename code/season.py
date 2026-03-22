from team import generate_team
from sim.game_sim import simulate_game

def play_next_game_day(season, user_team):
    if season.current_day >= len(season.schedule):
        return None

    away, home = season.schedule[season.current_day]
    season.current_day += 1

    away_score, home_score, box = simulate_game(
        away.lineup,
        home.lineup,
        away.starter,
        home.starter,
        verbose=False
    )

    if away_score > home_score:
        away.add_win()
        home.add_loss()
    else:
        home.add_win()
        away.add_loss()

    return {
        "away_team": away,
        "home_team": home,
        "away_score": away_score,
        "home_score": home_score,
        "box": box
    }

DEFAULT_TEAM_NAMES = [
    "Sharks", "Kings", "Falcons", "Wolves",
    "Knights", "Storm", "Heat", "Titans"
]

class Season:
    def __init__(self, user_team_name="Player Team", cpu_team_names=None):
        if cpu_team_names is None:
            cpu_team_names = DEFAULT_TEAM_NAMES[:7]

        self.teams = [generate_team(user_team_name)]
        for name in cpu_team_names:
            self.teams.append(generate_team(name))

        self.schedule = self.build_schedule(self.teams)
        self.current_day = 0

    def build_schedule(self, teams):
        schedule = []
        n = len(teams)

        for _round in range(2):  # double round robin
            for i in range(n):
                for j in range(i + 1, n):
                    schedule.append((teams[i], teams[j]))
        return schedule

    def standings(self):
        return sorted(
            self.teams,
            key=lambda t: (t.win_pct, t.wins),
            reverse=True
        )

    def remaining_games(self):
        return len(self.schedule) - self.current_day