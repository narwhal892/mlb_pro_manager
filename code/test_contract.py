from dataclasses import dataclass
from typing import Optional
import random

from player_gen_with_superstars_bust import (
    hitter_performance_score,
    pitcher_performance_score,
    score_to_salary,
    MIN_SALARY,
    MAX_SALARY,
)

from contracts import expected_length_games


@dataclass
class TestHitter:
    name: str
    average: int
    obp: int
    slugging: int
    ops: int
    position: str
    tier: str = "normal"
    age: int = 27


@dataclass
class TestPitcher:
    name: str
    average_minus: int
    obp_minus: int
    slugging_minus: int
    stamina: int
    role: str
    tier: str = "normal"
    age: int = 27


def fmt_money(n: int) -> str:
    return f"${n:,.0f}"


def ask_int(prompt: str, default: Optional[int] = None) -> int:
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Enter a whole number.")


def ask_str(prompt: str, default: Optional[str] = None) -> str:
    raw = input(prompt).strip()
    if raw == "" and default is not None:
        return default
    return raw


def expected_salary_for_hitter(h: TestHitter):
    score = hitter_performance_score(h)
    salary = score_to_salary(score)

    if h.tier == "superstar":
        salary = min(MAX_SALARY, int(salary * 1.25))
    elif h.tier == "bust":
        salary = max(MIN_SALARY, int(salary * 0.85))

    return salary, score


def expected_salary_for_pitcher(p: TestPitcher):
    score = pitcher_performance_score(p)
    salary = score_to_salary(score)

    if p.tier == "superstar":
        salary = min(MAX_SALARY, int(salary * 1.25))
    elif p.tier == "bust":
        salary = max(MIN_SALARY, int(salary * 0.85))

    return salary, score


def value_per_game(salary: int, games: int) -> float:
    return salary / max(1, games)


def negotiate(expected_salary: int, expected_games: int, offer_salary: int, offer_games: int):
    ask_vpg = value_per_game(expected_salary, expected_games)
    offer_vpg = value_per_game(offer_salary, offer_games)

    value_ratio = offer_vpg / max(1e-9, ask_vpg)
    length_ratio = offer_games / max(1, expected_games)
    randomness = random.uniform(-0.08, 0.08)

    score = 1.00 * value_ratio + randomness
    
    accepted = score >= 1.0

    return {
        "ask_vpg": ask_vpg,
        "offer_vpg": offer_vpg,
        "value_ratio": value_ratio,
        "length_ratio": length_ratio,
        "randomness": randomness,
        "score": score,
        "accepted": accepted,
    }


def print_negotiation_result(expected_salary: int, expected_games: int, offer_salary: int, offer_games: int):
    result = negotiate(expected_salary, expected_games, offer_salary, offer_games)

    print("\nNEGOTIATION TEST")
    print(f"Expected salary: {fmt_money(expected_salary)}")
    print(f"Expected length: {expected_games} games")
    print(f"Expected value/game: {fmt_money(int(result['ask_vpg']))}")

    print(f"\nOffer salary: {fmt_money(offer_salary)}")
    print(f"Offer length: {offer_games} games")
    print(f"Offer value/game: {fmt_money(int(result['offer_vpg']))}")

    print(f"\nValue ratio: {result['value_ratio']:.3f}")
    print(f"Length ratio: {result['length_ratio']:.3f}")
    print(f"Randomness: {result['randomness']:+.3f}")
    print(f"Final score: {result['score']:.3f}")
    print(f"Result: {'ACCEPTED' if result['accepted'] else 'REJECTED'}")


def run_hitter_test():
    print("\n--- HITTER CONTRACT TEST ---")

    name = ask_str("Name: ", "Test Hitter")
    age = ask_int("Age (27): ", 27)
    average = ask_int("AVG (275): ", 275)
    obp = ask_int("OBP (345): ", 345)
    slugging = ask_int("SLG (460): ", 460)
    ops = ask_int("OPS (805): ", 805)
    position = ask_str("Position (C/1B/2B/3B/SS/LF/CF/RF/DH): ", "DH").upper()
    tier = ask_str("Tier (normal/superstar/bust): ", "normal").lower()

    h = TestHitter(name, average, obp, slugging, ops, position, tier, age)

    expected_salary, score = expected_salary_for_hitter(h)
    expected_games = expected_length_games(h)

    print("\nPLAYER RESULT")
    print(f"Name: {h.name}")
    print(f"Type: Hitter")
    print(f"Age: {h.age}")
    print(f"Stats: AVG .{h.average:03d} / OBP .{h.obp:03d} / SLG .{h.slugging:03d} / OPS .{h.ops:03d}")
    print(f"Position: {h.position}")
    print(f"Tier: {h.tier}")
    print(f"Performance score: {score:.3f}")
    print(f"Expected salary: {fmt_money(expected_salary)}")
    print(f"Expected length: {expected_games} games")
    print(f"Expected value/game: {fmt_money(int(value_per_game(expected_salary, expected_games)))}")

    print("\nENTER OFFER TO TEST")
    offer_salary = ask_int(f"Offer salary ({expected_salary}): ", expected_salary)
    offer_games = ask_int(f"Offer length in games ({expected_games}): ", expected_games)

    print_negotiation_result(expected_salary, expected_games, offer_salary, offer_games)


def run_pitcher_test():
    print("\n--- PITCHER CONTRACT TEST ---")

    name = ask_str("Name: ", "Test Pitcher")
    age = ask_int("Age (27): ", 27)
    average_minus = ask_int("AVG- (62): ", 62)
    obp_minus = ask_int("OBP- (59): ", 59)
    slugging_minus = ask_int("SLG- (65): ", 65)
    stamina = ask_int("Stamina (75): ", 75)
    role = ask_str("Role (SP/RP/CL): ", "SP").upper()
    tier = ask_str("Tier (normal/superstar/bust): ", "normal").lower()

    p = TestPitcher(name, average_minus, obp_minus, slugging_minus, stamina, role, tier, age)

    expected_salary, score = expected_salary_for_pitcher(p)
    expected_games = expected_length_games(p)

    print("\nPLAYER RESULT")
    print(f"Name: {p.name}")
    print(f"Type: Pitcher")
    print(f"Age: {p.age}")
    print(f"Stats: AVG- {p.average_minus} / OBP- {p.obp_minus} / SLG- {p.slugging_minus}")
    print(f"Stamina: {p.stamina}")
    print(f"Role: {p.role}")
    print(f"Tier: {p.tier}")
    print(f"Performance score: {score:.3f}")
    print(f"Expected salary: {fmt_money(expected_salary)}")
    print(f"Expected length: {expected_games} games")
    print(f"Expected value/game: {fmt_money(int(value_per_game(expected_salary, expected_games)))}")

    print("\nENTER OFFER TO TEST")
    offer_salary = ask_int(f"Offer salary ({expected_salary}): ", expected_salary)
    offer_games = ask_int(f"Offer length in games ({expected_games}): ", expected_games)

    print_negotiation_result(expected_salary, expected_games, offer_salary, offer_games)


def main():
    print("MLB Pro Manager - Contract Negotiation Tester")
    print("1) Test hitter")
    print("2) Test pitcher")

    choice = ask_str("Choose 1 or 2: ")

    if choice == "1":
        run_hitter_test()
    elif choice == "2":
        run_pitcher_test()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()