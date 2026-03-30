import random

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def pct(x_0_to_1000):
    return x_0_to_1000 / 1000.0

def effective_hitter_avg(hitter):
    return getattr(hitter, "display_average", getattr(hitter, "average", 250))

def effective_hitter_obp(hitter):
    return getattr(hitter, "display_obp", getattr(hitter, "obp", 320))

def effective_hitter_ops(hitter):
    return getattr(hitter, "display_ops", getattr(hitter, "ops", 730))

def effective_pitcher_avg_minus(pitcher):
    return getattr(pitcher, "display_average_minus", getattr(pitcher, "average_minus", 0))

def effective_pitcher_obp_minus(pitcher):
    return getattr(pitcher, "display_obp_minus", getattr(pitcher, "obp_minus", 0))

def effective_pitcher_slg_minus(pitcher):
    return getattr(pitcher, "display_slugging_minus", getattr(pitcher, "slugging_minus", 0))

def plate_appearance(hitter, pitcher):
    avg_pts = effective_hitter_avg(hitter)
    obp_pts = effective_hitter_obp(hitter)
    ops_pts = effective_hitter_ops(hitter)

    slg_pts = clamp(ops_pts - obp_pts, 200, 1000)

    avg_minus = effective_pitcher_avg_minus(pitcher)
    obp_minus = effective_pitcher_obp_minus(pitcher)
    slg_minus = effective_pitcher_slg_minus(pitcher)

    bb_plus = getattr(pitcher, "bb_plus", 0)
    hbp_plus = getattr(pitcher, "hbp_plus", 0)

    eff_avg = clamp(avg_pts - avg_minus, 0, 1000)
    eff_obp = clamp(obp_pts - obp_minus + bb_plus + hbp_plus, 0, 1000)
    eff_slg = clamp(slg_pts - slg_minus, 0, 2000)

    # A small strikeout model
    so_chance = clamp(0.18 + (avg_minus / 1000.0), 0.08, 0.42)

    if random.random() > pct(eff_obp):
        return "strikeout" if random.random() < so_chance else "out"

    walk_hbp_pts = max(eff_obp - eff_avg, 0)
    p_walk_or_hbp = walk_hbp_pts / 1000.0

    if random.random() < p_walk_or_hbp:
        bb_rate = getattr(hitter, "bb_rate", 0.90)
        hbp_rate = getattr(hitter, "hbp_rate", 0.10)
        total = bb_rate + hbp_rate
        bb_rate = bb_rate / total
        return "walk" if random.random() < bb_rate else "hbp"

    slg = eff_slg / 1000.0
    extra_boost = clamp((slg - 0.300) / 0.500, 0.0, 1.0)

    w_1b = 0.65 - 0.25 * extra_boost
    w_2b = 0.20 + 0.10 * extra_boost
    w_3b = 0.05
    w_hr = 0.10 + 0.15 * extra_boost

    total = w_1b + w_2b + w_3b + w_hr
    w_1b, w_2b, w_3b, w_hr = w_1b / total, w_2b / total, w_3b / total, w_hr / total

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

def bases_text(bases):
    labels = []
    if bases[0]:
        labels.append("1B")
    if bases[1]:
        labels.append("2B")
    if bases[2]:
        labels.append("3B")
    return "Empty" if not labels else "-".join(labels)


def outcome_text(outcome):
    mapping = {
        "out": "ground/fly out",
        "strikeout": "strikeout",
        "walk": "walk",
        "hbp": "hit by pitch",
        "single": "single",
        "double": "double",
        "triple": "triple",
        "homerun": "home run",
    }
    return mapping.get(outcome, outcome)

def apply_hit(bases, hit_type):
    on_1st, on_2nd, on_3rd = bases
    runs = 0

    if hit_type == "homerun":
        runs += int(on_1st) + int(on_2nd) + int(on_3rd) + 1
        return [False, False, False], runs, 1

    rbis = 0
    if on_2nd:
        runs += 1
        rbis += 1
        on_2nd = False
    if on_3rd:
        runs += 1
        rbis += 1
        on_3rd = False

    new_bases = [False, False, False]

    if on_1st:
        if hit_type == "single":
            new_bases[1] = True
        elif hit_type == "double":
            runs += 1
            rbis += 1
        elif hit_type == "triple":
            runs += 1
            rbis += 1

    if hit_type == "single":
        new_bases[0] = True
    elif hit_type == "double":
        new_bases[1] = True
    elif hit_type == "triple":
        new_bases[2] = True

    rbis += 1 if runs > 0 and hit_type != "single" else 0
    return new_bases, runs, max(1, rbis if runs > 0 else 1)

def update_hitter_stats(hitter, outcome, rbis=0):
    hitter.pa += 1

    if outcome not in ("walk", "hbp"):
        hitter.ab += 1

    if outcome == "single":
        hitter.singles += 1
        hitter.hits += 1
        hitter.rbi += rbis
    elif outcome == "double":
        hitter.doubles += 1
        hitter.hits += 1
        hitter.rbi += rbis
    elif outcome == "triple":
        hitter.triples += 1
        hitter.hits += 1
        hitter.rbi += rbis
    elif outcome == "homerun":
        hitter.homeruns += 1
        hitter.hits += 1
        hitter.rbi += max(1, rbis)
        hitter.runs += 1
    elif outcome == "walk":
        hitter.walks += 1
    elif outcome == "hbp":
        hitter.hbp += 1
    elif outcome == "strikeout":
        hitter.strikeouts += 1
        hitter.outs += 1
    elif outcome == "out":
        hitter.outs += 1

def update_pitcher_stats(pitcher, outcome, runs_scored):
    target = getattr(pitcher, "_stat_target", pitcher)
    if outcome in ("single", "double", "triple", "homerun"):
        target.hits_allowed += 1
    elif outcome == "walk":
        target.walks += 1
    elif outcome == "hbp":
        target.hbps += 1
    elif outcome == "strikeout":
        target.strikeouts += 1

    target.runs_allowed += runs_scored
    target.earned_runs += runs_scored

def simulate_half_inning_detailed(lineup, pitcher, start_idx=0):
    outs = 0
    runs = 0
    bases = [False, False, False]
    i = start_idx
    n = len(lineup)
    plays = []
    hits_in_inning = 0
    stat_pitcher = getattr(pitcher, "_stat_target", pitcher)

    while outs < 3:
        hitter = lineup[i]
        before_bases = bases[:]
        before_outs = outs
        outcome = plate_appearance(hitter, pitcher)
        scored = 0
        rbis = 0

        if outcome == "out":
            outs += 1
            update_hitter_stats(hitter, "out")
            stat_pitcher.outs_recorded += 1

        elif outcome == "strikeout":
            outs += 1
            update_hitter_stats(hitter, "strikeout")
            update_pitcher_stats(pitcher, "strikeout", 0)
            stat_pitcher.outs_recorded += 1

        elif outcome in ("walk", "hbp"):
            bases, scored = apply_walk_or_hbp(bases)
            runs += scored
            update_hitter_stats(hitter, outcome)
            update_pitcher_stats(pitcher, outcome, scored)

        else:
            bases, scored, rbis = apply_hit(bases, outcome)
            runs += scored
            hits_in_inning += 1
            update_hitter_stats(hitter, outcome, rbis)
            update_pitcher_stats(pitcher, outcome, scored)

        plays.append({
            "pitcher": pitcher.name,
            "hitter": hitter.name,
            "outs_before": before_outs,
            "outs_after": outs,
            "bases_before": before_bases,
            "bases_after": bases[:],
            "outcome": outcome,
            "outcome_text": outcome_text(outcome),
            "runs_scored": scored,
            "rbis": rbis,
        })

        i = (i + 1) % n

    return {
        "runs": runs,
        "next_idx": i,
        "hits": hits_in_inning,
        "pitcher": pitcher.name,
        "plays": plays,
    }

def simulate_half_inning(lineup, pitcher, start_idx=0, verbose=False):
    outs = 0
    runs = 0
    bases = [False, False, False]
    i = start_idx
    n = len(lineup)
    stat_pitcher = getattr(pitcher, "_stat_target", pitcher)

    while outs < 3:
        hitter = lineup[i]
        outcome = plate_appearance(hitter, pitcher)

        if outcome == "out":
            outs += 1
            update_hitter_stats(hitter, "out")
            stat_pitcher.outs_recorded += 1

        elif outcome == "strikeout":
            outs += 1
            update_hitter_stats(hitter, "strikeout")
            update_pitcher_stats(pitcher, "strikeout", 0)
            stat_pitcher.outs_recorded += 1

        elif outcome in ("walk", "hbp"):
            bases, scored = apply_walk_or_hbp(bases)
            runs += scored
            update_hitter_stats(hitter, outcome)
            update_pitcher_stats(pitcher, outcome, scored)

        else:
            bases, scored, rbis = apply_hit(bases, outcome)
            runs += scored
            update_hitter_stats(hitter, outcome, rbis)
            update_pitcher_stats(pitcher, outcome, scored)

        i = (i + 1) % n

    return runs, i

def simulate_game(away_lineup, home_lineup, away_pitcher, home_pitcher, verbose=False):
    away_score = 0
    home_score = 0
    away_idx = 0
    home_idx = 0
    away_by_inning = []
    home_by_inning = []
    for _inning in range(1, 10):
        r, away_idx = simulate_half_inning(away_lineup, home_pitcher, away_idx, verbose=verbose)
        away_score += r
        away_by_inning.append(r)
        r, home_idx = simulate_half_inning(home_lineup, away_pitcher, home_idx, verbose=verbose)
        home_score += r
        home_by_inning.append(r)
    return away_score, home_score, {"away_by_inning": away_by_inning, "home_by_inning": home_by_inning}
