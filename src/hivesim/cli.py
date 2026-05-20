"""Command line interface for managing Hive bot pools and competitions."""

from __future__ import annotations

import argparse

from hivesim.pool import BotPool
from hivesim.tournament import run_match, run_tournament


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hivesim")
    parser.add_argument("--pool", default="pool.json", help="Path to bot pool JSON file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    register_parser = subparsers.add_parser("register", help="Register a bot")
    register_parser.add_argument("name")
    register_parser.add_argument("module")
    register_parser.add_argument("class_name")
    register_parser.add_argument("--elo", type=float, default=1200.0)

    unregister_parser = subparsers.add_parser("unregister", help="Unregister a bot")
    unregister_parser.add_argument("name")

    subparsers.add_parser("list", help="List bots")

    match_parser = subparsers.add_parser("match", help="Run a match")
    match_parser.add_argument("white_name")
    match_parser.add_argument("black_name")
    match_parser.add_argument("--games", type=int, default=1)
    match_parser.add_argument("--verbose", action="store_true")

    tournament_parser = subparsers.add_parser("tournament", help="Run round-robin tournament")
    tournament_parser.add_argument("--games-per-side", type=int, default=1)
    tournament_parser.add_argument("--verbose", action="store_true")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    pool = BotPool(pool_file=args.pool)

    if args.command == "register":
        entry = pool.register(args.name, args.module, args.class_name, elo=args.elo)
        print(f"Registered {entry.name} ({entry.module}.{entry.class_name})")
        return 0

    if args.command == "unregister":
        pool.unregister(args.name)
        print(f"Unregistered {args.name}")
        return 0

    if args.command == "list":
        for entry in pool.list_bots():
            print(
                f"{entry.name}: ELO={entry.elo:.1f}, "
                f"W-L-D={entry.wins}-{entry.losses}-{entry.draws}, "
                f"games={entry.games_played}"
            )
        return 0

    if args.command == "match":
        results = run_match(
            pool,
            args.white_name,
            args.black_name,
            games=args.games,
            verbose=args.verbose,
        )
        for result in results:
            print(
                f"{result.white_name} vs {result.black_name} -> "
                f"winner={result.winner}, turns={result.turns}, "
                f"ELO {result.white_elo_before:.1f}->{result.white_elo_after:.1f} / "
                f"{result.black_elo_before:.1f}->{result.black_elo_after:.1f}"
            )
        return 0

    if args.command == "tournament":
        result = run_tournament(
            pool,
            games_per_side=args.games_per_side,
            verbose=args.verbose,
        )
        print(f"Tournament completed: {result.total_games} games")
        return 0

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
