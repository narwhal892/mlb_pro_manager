from league import generate_team, push_cpu_team_toward_budget, generate_free_agents

def test_cpu_team_payroll(num_teams=10):
    seed_hitters, seed_pitchers = generate_free_agents(400, 250)

    teams = []
    for i in range(num_teams):
        team = generate_team(f"CPU Team {i+1}", division="Test")
        team.budget = 200_000_000
        push_cpu_team_toward_budget(team, seed_hitters, seed_pitchers)
        teams.append(team)

    print("\nCPU TEAM PAYROLL TEST")
    print("-" * 72)
    print(f"{'TEAM':<18}{'PAYROLL':>14}{'BUDGET':>14}{'UNDER 190M?':>14}{'GAP TO 200M':>12}")
    print("-" * 72)

    for team in teams:
        payroll = team.total_salary()
        budget = team.budget
        under_floor = "YES" if payroll < 190_000_000 else "NO"
        gap = budget - payroll
        print(
            f"{team.name:<18}"
            f"${payroll/1_000_000:>11.1f}M"
            f"${budget/1_000_000:>11.1f}M"
            f"{under_floor:>14}"
            f"${gap/1_000_000:>9.1f}M"
        )

    print("-" * 72)
    min_payroll = min(team.total_salary() for team in teams)
    max_payroll = max(team.total_salary() for team in teams)
    avg_payroll = sum(team.total_salary() for team in teams) / len(teams)

    print(f"MIN PAYROLL: ${min_payroll/1_000_000:.1f}M")
    print(f"MAX PAYROLL: ${max_payroll/1_000_000:.1f}M")
    print(f"AVG PAYROLL: ${avg_payroll/1_000_000:.1f}M")

    failures = [team for team in teams if team.total_salary() < 190_000_000]
    if failures:
        print("\nFAILED FLOOR CHECK:")
        for team in failures:
            print(f" - {team.name}: ${team.total_salary()/1_000_000:.1f}M")
    else:
        print("\nAll CPU teams passed the 190M payroll floor.")

if __name__ == "__main__":
    test_cpu_team_payroll()