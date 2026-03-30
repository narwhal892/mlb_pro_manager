import random
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import league
import season
import team
import player_gen_with_superstars_bust as pgen


class TestNewMLBManagerFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main_source = (BASE / 'main.py').read_text()

    def test_free_agents_keep_max_contracts_until_signed(self):
        hitters, pitchers = league.generate_free_agents(8, 5)
        for player in hitters + pitchers:
            self.assertEqual(player.contract_length, pgen.MAX_CONTRACT_GAMES)
            self.assertEqual(player.contract_games_remaining, pgen.MAX_CONTRACT_GAMES)

    def test_coach_market_contracts_do_not_start_until_hired(self):
        hitting, pitching = league.generate_coach_markets(4, 4)
        for coach in hitting + pitching:
            self.assertGreater(getattr(coach, 'contract_length', 0), 0)
            self.assertEqual(coach.contract_games_remaining, 0)

    def test_user_and_cpu_budgets_are_split_correctly(self):
        teams = league.generate_league('My Club')
        self.assertGreater(len(teams), 1)
        self.assertEqual(teams[0].budget, 165_000_000)
        for cpu in teams[1:]:
            self.assertEqual(cpu.budget, 200_000_000)

    def test_minor_hitter_contract_activates_only_on_callup(self):
        tm = team.generate_team('Testers')
        hitter = tm.minors_hitters[0]
        self.assertGreater(hitter.contract_length, 0)
        self.assertEqual(hitter.contract_games_remaining, 0)

        ok, msg = tm.call_up_minor_hitter(0)
        self.assertTrue(ok, msg)
        called_up = next(p for p in tm.bench if not tm.is_empty_slot(p) and p.name == hitter.name)
        self.assertEqual(called_up.contract_games_remaining, called_up.contract_length)

    def test_minor_pitcher_contract_activates_only_on_callup(self):
        tm = team.generate_team('Pitch Testers')
        tm.bullpen[-1] = tm.make_empty_pitcher_slot('bullpen')
        pitcher = tm.minors_pitchers[0]
        self.assertGreater(pitcher.contract_length, 0)
        self.assertEqual(pitcher.contract_games_remaining, 0)

        ok, msg = tm.call_up_minor_pitcher(0)
        self.assertTrue(ok, msg)
        called_up = next(p for p in tm.bullpen if not tm.is_empty_slot(p) and p.name == pitcher.name)
        self.assertEqual(called_up.contract_games_remaining, called_up.contract_length)

    def test_spin_rate_lab_boosts_every_five_games(self):
        tm = team.generate_team('Spin Lab')
        pitcher = tm.rotation[0]
        start_avg = pitcher.average_minus
        start_obp = pitcher.obp_minus
        start_slg = pitcher.slugging_minus

        ok, _ = tm.toggle_spin_rate_lab_pitcher(pitcher.name)
        self.assertTrue(ok)
        boosted = tm.apply_spin_rate_lab_progress(games=5, boost_amount=2, games_per_boost=5)
        boosted_names = [name for name, _amount in boosted]
        self.assertIn(pitcher.name, boosted_names)
        self.assertEqual(pitcher.average_minus, start_avg + 2)
        self.assertEqual(pitcher.obp_minus, start_obp)
        self.assertEqual(pitcher.slugging_minus, start_slg)

    def test_coaching_progress_boosts_every_eight_games(self):
        tm = team.generate_team('Coached Club')
        hitter = tm.lineup[0]
        pitcher = tm.rotation[0]
        hcoach = pgen.gen_hitting_coach()
        pcoach = pgen.gen_pitching_coach()
        tm.hitting_coaches = [hcoach]
        tm.pitching_coach = pcoach
        tm.hitting_assignment_names = [hitter.name]
        tm.pitching_assignment_name = pitcher.name

        hitter_start = (hitter.coach_avg_bonus, hitter.coach_obp_bonus, hitter.coach_ops_bonus)
        pitcher_start = (pitcher.coach_avg_bonus, pitcher.coach_obp_bonus, pitcher.coach_slg_bonus)

        for _ in range(8):
            tm.apply_coaching_progress()

        self.assertEqual(hitter.coach_progress_games, 8)
        self.assertEqual(pitcher.coach_progress_games, 8)
        self.assertEqual(
            (hitter.coach_avg_bonus, hitter.coach_obp_bonus, hitter.coach_ops_bonus),
            (hitter_start[0] + hcoach.avg_boost, hitter_start[1] + hcoach.obp_boost, hitter_start[2] + hcoach.ops_boost),
        )
        self.assertEqual(
            (pitcher.coach_avg_bonus, pitcher.coach_obp_bonus, pitcher.coach_slg_bonus),
            (pitcher_start[0] + pcoach.avg_boost, pitcher_start[1] + pcoach.obp_boost, pitcher_start[2] + pcoach.slg_boost),
        )

    def test_injury_counter_ticks_down_and_reports_healed_players(self):
        tm = team.generate_team('Health Club')
        player = tm.lineup[0]
        player.injured_games_remaining = 2
        healed = tm.decrement_injuries(1)
        self.assertEqual(player.injured_games_remaining, 1)
        self.assertEqual(healed, [])
        healed = tm.decrement_injuries(1)
        self.assertEqual(player.injured_games_remaining, 0)
        self.assertIn(player, healed)

    def test_user_stat_history_archives_multiple_years(self):
        s = season.Season('History Club')
        user = s.user_team
        hitter = user.lineup[0]
        pitcher = user.rotation[0]

        hitter.ab = 10
        hitter.hits = 4
        hitter.walks = 2
        hitter.hbp = 1
        hitter.singles = 2
        hitter.doubles = 1
        hitter.triples = 0
        hitter.homeruns = 1
        hitter.rbi = 5

        pitcher.outs_recorded = 9
        pitcher.earned_runs = 1
        pitcher.strikeouts = 4
        pitcher.walks = 2

        s.archive_user_stats()
        s.year += 1
        s.archive_user_stats()

        self.assertEqual(len(s.user_stat_history), 2)
        self.assertEqual(s.user_stat_history[0]['year'], 1)
        self.assertEqual(s.user_stat_history[1]['year'], 2)
        self.assertTrue(any(entry['kind'] == 'hitter' for entry in s.user_stat_history[0]['roster']))
        self.assertTrue(any(entry['kind'] == 'pitcher' for entry in s.user_stat_history[0]['roster']))

    def test_main_source_has_extra_innings_logic(self):
        self.assertIn('while True:', self.main_source)
        self.assertIn('if inning >= 9 and away_score != home_score:', self.main_source)

    def test_main_source_refreshes_free_agents_every_ten_games(self):
        self.assertIn('if season.current_day % 10 == 0:', self.main_source)
        self.assertIn('free_agent_hitters[:], free_agent_pitchers[:] = generate_free_agents()', self.main_source)

    def test_main_source_enforces_playoff_lineup_page(self):
        self.assertIn('play_next_playoff_round()', self.main_source)
        self.assertIn('if playoff_round_state and playoff_round_state.get("current_series"):', self.main_source)
        self.assertIn('game_state = "lineup"', self.main_source)
        self.assertIn('Set your lineup for the next playoff game.', self.main_source)


if __name__ == '__main__':
    random.seed(7)
    unittest.main(verbosity=2)
