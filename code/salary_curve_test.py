from player_gen_with_superstars_bust import MIN_SALARY

# =========================
# CHOOSE YOUR SALARY FUNCTION
# =========================

def score_to_salary(score: float) -> int:
    # --- OPTION 1: Current exponential (no cap) ---
    # multiplier = 2 ** (score * 1.55)
    # salary = int(5_000_000 * multiplier)
    # return max(MIN_SALARY, salary)

    # --- OPTION 2: Cubic MLB-style curve (recommended) ---
    normalized = max(0.0, score)

    base = MIN_SALARY
    middle = 4_000_000 * normalized
    quality = 8_000_000 * (normalized ** 2)
    star = 22_000_000 * (normalized ** 3)

    salary = int(base + middle + quality + star)
    return max(MIN_SALARY, salary)


# =========================
# GENERATE TABLE
# =========================

def fmt_money(n: int) -> str:
    return f"${n:,.0f}"


def print_salary_table():
    print("\nSALARY CURVE TEST\n")
    print(f"{'Score':<10}{'Salary':<20}")
    print("-" * 30)

    # Test a range of scores
    for i in range(0, 101):
        score = i / 100  # 0.00 → 1.00
        salary = score_to_salary(score)
        print(f"{score:<10.2f}{fmt_money(salary):<20}")


def print_key_points():
    print("\nKEY PLAYER TIERS\n")

    test_scores = [
        ("Replacement", 0.20),
        ("Bench / RP", 0.35),
        ("Average Starter", 0.50),
        ("Above Avg", 0.65),
        ("All-Star", 0.80),
        ("Superstar", 0.95),
        ("Elite MVP", 1.10),
    ]

    for label, score in test_scores:
        salary = score_to_salary(score)
        print(f"{label:<15} Score {score:<5} → {fmt_money(salary)}")


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    print_salary_table()
    print_key_points()