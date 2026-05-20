"""JSON-backed local bot pool for Hive competitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
import json
from pathlib import Path

from hivesim.elo import DEFAULT_RATING
from hivesim.robots import BaseBot


@dataclass
class BotEntry:
    name: str
    module: str
    class_name: str
    elo: float = DEFAULT_RATING
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0


class BotPool:
    """JSON-backed registry of bots and their ELO ratings."""

    def __init__(self, pool_file: str | Path = "pool.json") -> None:
        self.pool_file = Path(pool_file)
        self._bots: dict[str, BotEntry] = {}

        if self.pool_file.exists():
            data = json.loads(self.pool_file.read_text(encoding="utf-8"))
            self._bots = {
                name: BotEntry(**entry_data)
                for name, entry_data in data.items()
            }

    def save(self) -> None:
        payload = {name: asdict(entry) for name, entry in self._bots.items()}
        self.pool_file.parent.mkdir(parents=True, exist_ok=True)
        self.pool_file.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def register(
        self,
        name: str,
        module: str,
        class_name: str,
        elo: float = DEFAULT_RATING,
    ) -> BotEntry:
        if name in self._bots:
            raise ValueError(f"Bot '{name}' is already registered")

        entry = BotEntry(name=name, module=module, class_name=class_name, elo=elo)
        self._bots[name] = entry
        self.save()
        return entry

    def unregister(self, name: str) -> None:
        if name not in self._bots:
            raise KeyError(name)
        del self._bots[name]
        self.save()

    def get(self, name: str) -> BotEntry:
        if name not in self._bots:
            raise KeyError(name)
        return self._bots[name]

    def list_bots(self) -> list[BotEntry]:
        return sorted(self._bots.values(), key=lambda entry: (-entry.elo, entry.name))

    def load_bot(self, name: str, team: str) -> BaseBot:
        entry = self.get(name)
        module = import_module(entry.module)

        try:
            bot_class = getattr(module, entry.class_name)
        except AttributeError as exc:
            raise AttributeError(
                f"Class '{entry.class_name}' not found in module '{entry.module}'"
            ) from exc

        try:
            bot = bot_class(team=team, name=entry.name)
        except TypeError as exc:
            raise TypeError(
                f"Failed to instantiate '{entry.class_name}' with signature "
                f"(team=..., name=...): {exc}"
            ) from exc
        if not isinstance(bot, BaseBot):
            raise TypeError(f"{entry.class_name} is not a BaseBot subclass")

        return bot

    def record_result(self, name: str, new_elo: float, outcome: str) -> None:
        entry = self.get(name)
        entry.elo = new_elo
        entry.games_played += 1

        if outcome == "win":
            entry.wins += 1
        elif outcome == "loss":
            entry.losses += 1
        elif outcome == "draw":
            entry.draws += 1
        else:
            raise ValueError("outcome must be 'win', 'loss', or 'draw'")
