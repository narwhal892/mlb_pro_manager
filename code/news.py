import random
from dataclasses import dataclass, field

from contracts import scan_contract_events
from player_gen_with_superstars_bust import make_scandal_news


@dataclass
class NewsFeed:
    stories: list[str] = field(default_factory=list)

    def push(self, story: str):
        if story and story not in self.stories:
            self.stories.insert(0, story)
        self.stories = self.stories[:14]

    def extend(self, stories):
        for s in stories:
            self.push(s)

    def top(self, n=8):
        return self.stories[:n]


def build_contract_news(team):
    return [evt.message for evt in scan_contract_events(team)]


def generate_cpu_news(teams):
    rng = random.Random()
    out = []
    cpu_teams = teams[1:]
    if not cpu_teams:
        return out

    if rng.random() < 0.45:
        team = rng.choice(cpu_teams)
        out.append(f"{team.name} hired a new development coach behind the scenes.")

    if rng.random() < 0.35:
        team = rng.choice(cpu_teams)
        player = None
        roster = team.lineup + team.rotation + team.bench
        if roster:
            player = rng.choice(roster)
            out.append(make_scandal_news(player.name))

    expiring = []
    for t in cpu_teams:
        expiring.extend([p for p in t.lineup + t.rotation if getattr(p, 'contract_games_remaining', 999) <= 8])
    if expiring:
        candidate = max(expiring, key=lambda p: getattr(p, 'salary', 0))
        out.append(f"League buzz: {candidate.name} could hit free agency soon.")
    return out
