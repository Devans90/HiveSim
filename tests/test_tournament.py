import pytest

from hivesim.pool import BotPool
from hivesim.tournament import run_match, run_tournament


def test_run_match_updates_elo_and_stats_with_real_game(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("WhiteRandom", "hivesim.robots", "RandomBot")
    pool.register("BlackRandom", "hivesim.robots", "RandomBot")

    results = run_match(pool, "WhiteRandom", "BlackRandom", games=1, verbose=False)

    assert len(results) == 1
    result = results[0]
    assert result.white_name == "WhiteRandom"
    assert result.black_name == "BlackRandom"
    assert result.turns > 0
    assert result.winner in {"white", "black", None}

    white = pool.get("WhiteRandom")
    black = pool.get("BlackRandom")
    assert white.games_played == 1
    assert black.games_played == 1


def test_run_match_real_games_preserve_result_accounting(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("WhiteRandom", "hivesim.robots", "RandomBot")
    pool.register("BlackRandom", "hivesim.robots", "RandomBot")

    results = run_match(pool, "WhiteRandom", "BlackRandom", games=3, verbose=False)

    assert len(results) == 3
    for result in results:
        assert result.winner in {"white", "black", None}
        assert 0 < result.turns <= 200

    white = pool.get("WhiteRandom")
    black = pool.get("BlackRandom")
    assert white.games_played == 3
    assert black.games_played == 3

    assert white.wins + white.losses + white.draws == 3
    assert black.wins + black.losses + black.draws == 3
    assert white.wins == black.losses
    assert black.wins == white.losses
    assert white.draws == black.draws


def test_run_match_calls_save_after_each_game(tmp_path, monkeypatch):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("A", "hivesim.robots", "RandomBot")
    pool.register("B", "hivesim.robots", "RandomBot")

    outcomes = iter(["white", None, "black"])

    def fake_simulate_game(white_bot, black_bot, verbose=False):
        return next(outcomes), 10, object()

    save_calls = 0
    original_save = pool.save

    def counting_save():
        nonlocal save_calls
        save_calls += 1
        original_save()

    monkeypatch.setattr("hivesim.tournament.simulate_game", fake_simulate_game)
    monkeypatch.setattr(pool, "save", counting_save)

    results = run_match(pool, "A", "B", games=3)

    assert len(results) == 3
    assert save_calls == 3
    assert pool.get("A").games_played == 3
    assert pool.get("B").games_played == 3


def test_run_tournament_round_robin_game_count(tmp_path, monkeypatch):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    for name in ["A", "B", "C"]:
        pool.register(name, "hivesim.robots", "RandomBot")

    def fake_simulate_game(white_bot, black_bot, verbose=False):
        return "white", 5, object()

    monkeypatch.setattr("hivesim.tournament.simulate_game", fake_simulate_game)

    result = run_tournament(pool, games_per_side=2)
    assert result.total_games == 12  # 3 bots -> 3 unordered pairs * 2 sides * 2 games/side


def test_run_tournament_requires_at_least_two_bots(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("Solo", "hivesim.robots", "RandomBot")

    with pytest.raises(ValueError):
        run_tournament(pool)
