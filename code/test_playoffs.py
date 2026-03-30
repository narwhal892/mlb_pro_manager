import pygame
import main


class DummyTeam:
    def __init__(self, name):
        self.name = name
        self.lineup = []
        self.bench = []
        self.rotation = []
        self.bullpen = []

    def is_empty_slot(self, _p):
        return False


def build_fake_playoff_data():
    away = DummyTeam("Kings")
    home = DummyTeam("Falcons")

    main.season = type("DummySeason", (), {})()
    main.season.playoff_round = "World Series"
    main.season.champion = None

    main.user_team = home

    main.playoff_round_state = {
        "round": "World Series",
        "cpu_results": [],
        "user_series_states": [],
        "current_user_series_index": 0,
        "current_series": {
            "away_team": away,
            "home_team": home,
            "away_wins": 2,
            "home_wins": 1,
            "wins_needed": 2,
            "series_games": [],
        },
    }

    main.last_playoff_game = {
        "away_score": 4,
        "home_score": 6,
        "away_by_inning": [0, 1, 0, 0, 2, 0, 0, 1, 0],
        "home_by_inning": [1, 0, 0, 2, 0, 1, 0, 2, 0],
        "usage": {
            "Kings": {},
            "Falcons": {},
        },
        "inning_logs": [
            {
                "inning": i + 1,
                "top": {
                    "runs": [0, 1, 0, 0, 2, 0, 0, 1, 0][i],
                    "hits": 1 if i in (1, 4, 7) else 0,
                    "pitcher": "Falcons SP",
                    "plays": [
                        {
                            "outs_before": 0,
                            "bases_before": [False, False, False],
                            "hitter": "Kings Batter",
                            "outcome_text": "Single",
                            "runs_scored": 0,
                        }
                    ],
                },
                "bottom": {
                    "runs": [1, 0, 0, 2, 0, 1, 0, 2, 0][i],
                    "hits": 1 if i in (0, 3, 5, 7) else 0,
                    "pitcher": "Kings SP",
                    "plays": [
                        {
                            "outs_before": 0,
                            "bases_before": [False, False, False],
                            "hitter": "Falcons Batter",
                            "outcome_text": "Double",
                            "runs_scored": 0,
                        }
                    ],
                },
            }
            for i in range(9)
        ],
        "winner": home,
    }

    main.all_games_today = [
        {
            "title": "World Series Results",
            "away_team": away,
            "home_team": home,
            "away_score": 4,
            "home_score": 6,
            "away_by_inning": [0, 1, 0, 0, 2, 0, 0, 1, 0],
            "home_by_inning": [1, 0, 0, 2, 0, 1, 0, 2, 0],
            "usage": {"Kings": {}, "Falcons": {}},
            "inning_logs": [],
            "winner": home,
        }
    ]
    main.selected_game_index = 0
    main.box_inning_index = 0
    main.reveal_inning_index = 9
    main.status_message = "DEBUG PLAYOFF PAGE TEST"


def draw_current_state():
    if main.game_state == "playoff_intro":
        main.draw_playoff_intro()
    elif main.game_state == "inning_reveal":
        main.draw_inning_reveal()
    elif main.game_state == "media":
        main.draw_media_page()
    elif main.game_state == "series_update":
        main.draw_series_update(
            main.playoff_round_state["current_series"] if main.playoff_round_state else None
        )
    elif main.game_state == "celebration":
        winner = (
            main.last_playoff_game["winner"]
            if main.last_playoff_game and "winner" in main.last_playoff_game
            else main.user_team
        )
        round_name = (
            main.playoff_round_state["round"]
            if main.playoff_round_state
            else (main.season.playoff_round if main.season else "Playoffs")
        )
        main.draw_celebration(winner, round_name)
    elif main.game_state == "playoffs":
        main.draw_playoff_bracket()
    else:
        main.screen.fill((10, 10, 20))
        main.draw_text(f"Unknown state: {main.game_state}", 40, 40)


def run_test():
    pygame.init()
    build_fake_playoff_data()

    states = [
        "playoffs",
        "playoff_intro",
        "inning_reveal",
        "media",
        "series_update",
        "celebration",
    ]
    state_index = 0
    main.game_state = states[state_index]

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    state_index = (state_index + 1) % len(states)
                    main.game_state = states[state_index]
                elif event.key == pygame.K_LEFT:
                    state_index = (state_index - 1) % len(states)
                    main.game_state = states[state_index]
                elif event.key == pygame.K_UP:
                    main.reveal_inning_index = min(
                        len(main.last_playoff_game["inning_logs"]),
                        main.reveal_inning_index + 1
                    )
                elif event.key == pygame.K_DOWN:
                    main.reveal_inning_index = max(0, main.reveal_inning_index - 1)

        draw_current_state()
        main.draw_text("LEFT/RIGHT switch page | UP/DOWN inning reveal | ESC quit",
                       30, main.HEIGHT - 30, (255, 225, 120), main.SMALL_FONT)
        pygame.display.flip()
        main.clock.tick(main.FPS)

    pygame.quit()


if __name__ == "__main__":
    run_test()
    