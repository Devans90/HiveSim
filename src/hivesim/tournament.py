"""Match and tournament execution utilities for bot pool competition."""

from __future__ import annotations

from dataclasses import dataclass

from hivesim.elo import update_ratings
from hivesim.pool import BotPool
from hivesim.runsim import simulate_game


@dataclass
class MatchResult:
    white_name: str
    black_name: str
    winner: str | None
    turns: int
    white_elo_before: float
    black_elo_before: float
    white_elo_after: float
    black_elo_after: float


@dataclass
class TournamentResult:
    match_results: list[MatchResult]

    @property
    def total_games(self) -> int:
        return len(self.match_results)


def run_match(
    pool: BotPool,
    white_name: str,
    black_name: str,
    games: int = 1,
    verbose: bool = False,
) -> list[MatchResult]:
    """Run games between white_name and black_name, updating ratings after each game."""
    if games < 1:
        raise ValueError("games must be >= 1")

    results: list[MatchResult] = []

    for _ in range(games):
        white_entry = pool.get(white_name)
        black_entry = pool.get(black_name)

        white_elo_before = white_entry.elo
        black_elo_before = black_entry.elo

        white_bot = pool.load_bot(white_name, team="white")
        black_bot = pool.load_bot(black_name, team="black")

        winner, turns, _ = simulate_game(white_bot, black_bot, verbose=verbose)

        white_elo_after, black_elo_after = update_ratings(
            white_elo_before,
            black_elo_before,
            winner,
        )

        if winner == "white":
            white_outcome, black_outcome = "win", "loss"
        elif winner == "black":
            white_outcome, black_outcome = "loss", "win"
        elif winner is None:
            white_outcome = black_outcome = "draw"
        else:
            raise ValueError("simulate_game returned invalid winner value")

        pool.record_result(white_name, white_elo_after, white_outcome)
        pool.record_result(black_name, black_elo_after, black_outcome)
        pool.save()

        results.append(
            MatchResult(
                white_name=white_name,
                black_name=black_name,
                winner=winner,
                turns=turns,
                white_elo_before=white_elo_before,
                black_elo_before=black_elo_before,
                white_elo_after=white_elo_after,
                black_elo_after=black_elo_after,
            )
        )

    return results


def run_tournament(
    pool: BotPool,
    games_per_side: int = 1,
    verbose: bool = False,
) -> TournamentResult:
    """Run a round-robin tournament over all ordered bot pairs."""
    if games_per_side < 1:
        raise ValueError("games_per_side must be >= 1")

    names = [entry.name for entry in pool.list_bots()]
    if len(names) < 2:
        raise ValueError("At least two bots are required to run a tournament")

    results: list[MatchResult] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            bot_a = names[i]
            bot_b = names[j]
            results.extend(run_match(pool, bot_a, bot_b, games=games_per_side, verbose=verbose))
            results.extend(run_match(pool, bot_b, bot_a, games=games_per_side, verbose=verbose))

    return TournamentResult(match_results=results)
