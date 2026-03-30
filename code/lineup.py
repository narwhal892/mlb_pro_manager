from dataclasses import dataclass, field


@dataclass
class LineupPlan:
    batting_order: list = field(default_factory=list)
    starter_name: str = ""
    reliever_names: list = field(default_factory=list)


def build_lineup_plan(team):
    team.ensure_batting_order()
    return LineupPlan(
        batting_order=team.batting_order[:],
        starter_name=team.starter.name if team.starter else "",
        reliever_names=[p.name for p in [team.middle_reliever, team.closer] if p],
    )


def apply_lineup_plan(team, plan: LineupPlan):
    team.batting_order = [p for p in plan.batting_order if p in team.lineup]
    if len(team.batting_order) < len(team.lineup):
        for p in team.lineup:
            if p not in team.batting_order:
                team.batting_order.append(p)

    all_pitchers = [p for p in team.rotation + team.bullpen if getattr(p, "name", None)]

    starter = None
    for p in all_pitchers:
        if p.name == plan.starter_name:
            starter = p
            break

    relievers = []
    for name in plan.reliever_names:
        for p in all_pitchers:
            if p.name == name and p != starter and p not in relievers:
                relievers.append(p)
                break

    if starter:
        starter.role = "SP"
        if starter in team.bullpen:
            team.bullpen.remove(starter)
        if starter not in team.rotation:
            team.rotation.insert(0, starter)
        team.rotation = [starter] + [p for p in team.rotation if p != starter][:4]
        team.starter = starter

    if relievers:
        relievers[0].role = "RP"
        team.middle_reliever = relievers[0]
    if len(relievers) > 1:
        relievers[1].role = "CL"
        team.closer = relievers[1]

    bullpen_rebuild = []
    if team.middle_reliever:
        bullpen_rebuild.append(team.middle_reliever)
    if team.closer and team.closer is not team.middle_reliever:
        bullpen_rebuild.append(team.closer)

    protected = {id(p) for p in bullpen_rebuild + team.rotation}
    for p in all_pitchers:
        if id(p) not in protected:
            if getattr(p, "role", None) == "SP":
                p.role = "RP"
            bullpen_rebuild.append(p)

    team.bullpen = bullpen_rebuild
    team.refresh_roles()
    team.ensure_batting_order()
