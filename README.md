# HiveSim

A Python simulation of the Hive board game with hexagonal grid mechanics, supporting AI bots and game visualization.

![demo 1](/media/part1.gif)

## Overview

HiveSim is a comprehensive implementation of Hive-like game mechanics using a hexagonal coordinate system. The project includes:

- Full game state management with piece placement and movement validation
- Hexagonal grid coordinate system with pathfinding
- Support for multiple game piece types (Ant, Beetle, Spider, Grasshopper, Queen Bee, Ladybug, Mosquito)
- AI bot framework for automated gameplay
- Real-time game visualization using Plotly
- Comprehensive test coverage

## Installation

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Devans90/HiveSim.git
cd HiveSim
```

2. Install the package and dependencies:
```bash
pip install -e .
```

3. (Optional) Install development dependencies for testing:
```bash
pip install pytest pytest-cov
```

## Usage

### Running a Simulation

```python
from hivesim.game import Game, GameState
from hivesim.robots import RandomBot
from hivesim.runsim import simulate_game

# Create bots for each player
white_bot = RandomBot(team='white', name='WhiteBot')
black_bot = RandomBot(team='black', name='BlackBot')

# Run a simulation with visualization
winner, turns, game = simulate_game(
    white_bot, 
    black_bot, 
    verbose=True,
    plot_game=True,
    live_delay=0.5
)

print(f"Winner: {winner} after {turns} turns")
```

### Creating a Custom Game

```python
from hivesim.game import Game, GameState, Turn, HexCoordinate

# Initialize a new game
game = Game()

# Place a piece
turn = Turn(
    player='white',
    piece_type='ant',
    action_type='place',
    target_coordinates=HexCoordinate(q=0, r=0, s=0)
)

game.apply_turn(turn)
```

## Hexagonal Coordinate System

HiveSim uses a cube coordinate system for hexagonal tiles, where each hex is represented by three coordinates (q, r, s) that must satisfy: **q + r + s = 0**

### Coordinate Directions (clockwise from top, pointy side up)

| q | r | s | Position |
|---|---|---|----------|
| 1 | -1 | 0 | Top-right |
| 1 | 0 | -1 | Right |
| 0 | 1 | -1 | Bottom-right |
| -1 | 1 | 0 | Bottom-left |
| -1 | 0 | 1 | Left |
| 0 | -1 | 1 | Top-left |

- **q**: Increases towards the upper-right
- **r**: Increases downward  
- **s**: Increases towards the upper-left

## Game Pieces

### Available Piece Types

- **Ant (🐜)**: Can move any distance around the hive
- **Beetle (🪲)**: Can move one space and climb on top of other pieces
- **Spider (🕷️)**: Moves exactly three spaces around the hive
- **Grasshopper (🦗)**: Jumps over pieces in a straight line
- **Queen Bee (🐝)**: Moves one space, must be placed by turn 4

### Not yet implemented pieces
- **Ladybug (🐞)**: Moves two on top and one down
- **Mosquito (🦟)**: Mimics adjacent pieces

### Not planned pieces
- **Pillbug (💊)**: Complex, game changing rules

## Game Rules

### Basic Rules

1. **First Placement**: The first piece must be placed at the origin (0, 0, 0)
2. **Adjacent Placement**: New pieces must be placed adjacent to your own pieces
3. **Opponent Separation**: After turn 1, pieces cannot be placed adjacent to opponent pieces
4. **Queen Placement**: The Queen Bee must be placed by your 4th turn
5. **Hive Integrity**: The hive must remain connected; pieces cannot be moved if it breaks the hive
6. **Freedom of Movement**: Pieces must be able to physically slide to their destination

### Win Condition

A player wins when their opponent's Queen Bee is completely surrounded by pieces (any color).

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=hivesim --cov-report=html

# Run specific test file
pytest tests/test_board_states.py -v
```

### Test Coverage

The test suite includes:
- Hex coordinate validation and operations
- Game piece creation and properties
- Board state management
- Win condition detection
- Hive connectivity rules
- Movement validation and pathfinding
- Complex board scenarios

## Project Structure

```
HiveSim/
├── src/hivesim/
│   ├── __init__.py
│   ├── game.py           # Core game logic and piece definitions
│   ├── robots.py         # AI bot implementations
│   ├── runsim.py         # Game simulation runner
│   └── visualization.py  # Plotly-based visualization
├── tests/
│   ├── test_hex_coordinate.py
│   ├── test_game_pieces.py
│   ├── test_board_states.py
│   └── test_movement_rules.py
├── media/                # Demo gifs and images
├── notebooks/            # Jupyter notebooks for experiments
├── pyproject.toml        # Project configuration
└── README.md
```

## Contributing

Contributions are welcome! Please ensure:
1. All tests pass: `pytest tests/`
2. Code follows existing style conventions
3. New features include appropriate tests
4. Documentation is updated for significant changes

## License

See LICENSE file for details.

