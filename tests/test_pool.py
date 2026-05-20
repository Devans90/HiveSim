import pytest

from hivesim.pool import BotPool
from hivesim.robots import BaseBot


def _write_dummy_bot_module(tmp_path):
    package_dir = tmp_path / "dummybots"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "bots.py").write_text(
        """
from hivesim.robots import BaseBot

class DummyBot(BaseBot):
    def choose_action_type(self, can_move, can_place, game_state):
        return 'place' if can_place else 'move'

    def choose_piece_type(self, available_pieces, movable_pieces, action_type, game_state):
        source = available_pieces if action_type == 'place' else movable_pieces
        return next(iter(source))

    def choose_piece_id(self, piece_ids, piece_type, action_type, game_state):
        return piece_ids[0]

    def choose_target_location(self, available_spaces, piece_type, action_type, game_state):
        return available_spaces[0]

class NotABot:
    def __init__(self, team, name):
        self.team = team
        self.name = name
""".strip(),
        encoding="utf-8",
    )
    return package_dir


def test_register_and_persist(tmp_path):
    pool_file = tmp_path / "pool.json"
    pool = BotPool(pool_file=pool_file)

    entry = pool.register("Dummy", "hivesim.robots", "RandomBot", elo=1234.5)
    assert entry.name == "Dummy"
    assert pool_file.exists()

    reloaded = BotPool(pool_file=pool_file)
    loaded_entry = reloaded.get("Dummy")
    assert loaded_entry.elo == pytest.approx(1234.5)


def test_register_duplicate_raises(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("Dummy", "hivesim.robots", "RandomBot")

    with pytest.raises(ValueError):
        pool.register("Dummy", "hivesim.robots", "RandomBot")


def test_unregister_missing_raises_key_error(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    with pytest.raises(KeyError):
        pool.unregister("missing")


def test_list_bots_sorted_by_elo_desc(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("Low", "hivesim.robots", "RandomBot", elo=1100)
    pool.register("High", "hivesim.robots", "RandomBot", elo=1400)

    bots = pool.list_bots()
    assert [bot.name for bot in bots] == ["High", "Low"]


def test_load_bot_instantiates_basebot(tmp_path, monkeypatch):
    package_dir = _write_dummy_bot_module(tmp_path)
    monkeypatch.syspath_prepend(str(package_dir.parent))

    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("Dummy", "dummybots.bots", "DummyBot")

    bot = pool.load_bot("Dummy", team="white")
    assert isinstance(bot, BaseBot)
    assert bot.team == "white"
    assert bot.name == "Dummy"


def test_load_bot_rejects_non_basebot_class(tmp_path, monkeypatch):
    package_dir = _write_dummy_bot_module(tmp_path)
    monkeypatch.syspath_prepend(str(package_dir.parent))

    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("Invalid", "dummybots.bots", "NotABot")

    with pytest.raises(TypeError):
        pool.load_bot("Invalid", team="black")


def test_record_result_updates_counters(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("Dummy", "hivesim.robots", "RandomBot")

    pool.record_result("Dummy", 1220.0, "win")
    pool.record_result("Dummy", 1210.0, "loss")
    pool.record_result("Dummy", 1212.0, "draw")

    entry = pool.get("Dummy")
    assert entry.elo == pytest.approx(1212.0)
    assert entry.games_played == 3
    assert entry.wins == 1
    assert entry.losses == 1
    assert entry.draws == 1


def test_record_result_invalid_outcome_raises(tmp_path):
    pool = BotPool(pool_file=tmp_path / "pool.json")
    pool.register("Dummy", "hivesim.robots", "RandomBot")

    with pytest.raises(ValueError):
        pool.record_result("Dummy", 1200.0, "bad")
