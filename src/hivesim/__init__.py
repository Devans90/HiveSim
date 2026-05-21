"""
HiveSim - A Python simulation of the Hive board game.

This package provides:
- Full game state management with piece placement and movement validation
- Hexagonal grid coordinate system with pathfinding
- Support for multiple game piece types
- AI bot framework for automated gameplay
- Gymnasium-compatible RL environment for reinforcement learning
"""

from hivesim.game import (
    HexCoordinate,
    GamePiece,
    Ant,
    Beetle,
    Spider,
    Grasshopper,
    QueenBee,
    Ladybug,
    Mosquito,
    BoardState,
    Player,
    GameState,
    Turn,
    Game,
    MovementHelper,
)

from hivesim.robots import BaseBot, RandomBot, HumanPlayer

from hivesim.env import HiveEnv, make_hive_env
from hivesim.elo import DEFAULT_K, DEFAULT_RATING, expected_score, update_ratings
from hivesim.pool import BotEntry, BotPool
from hivesim.tournament import MatchResult, TournamentResult, run_match, run_tournament

__all__ = [
    # Core game classes
    'HexCoordinate',
    'GamePiece',
    'Ant',
    'Beetle', 
    'Spider',
    'Grasshopper',
    'QueenBee',
    'Ladybug',
    'Mosquito',
    'BoardState',
    'Player',
    'GameState',
    'Turn',
    'Game',
    'MovementHelper',
    # Bots
    'BaseBot',
    'RandomBot',
    'HumanPlayer',
    # ELO
    'DEFAULT_K',
    'DEFAULT_RATING',
    'expected_score',
    'update_ratings',
    # Bot pool
    'BotEntry',
    'BotPool',
    # Tournaments
    'MatchResult',
    'TournamentResult',
    'run_match',
    'run_tournament',
    # RL Environment
    'HiveEnv',
    'make_hive_env',
]

__version__ = '0.1.0'
