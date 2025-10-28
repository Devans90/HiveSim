# HiveSim Examples

This directory contains example scripts demonstrating various features of HiveSim.

## Running Examples

Make sure you have installed HiveSim first:

```bash
pip install -e .
```

Then run any example:

```bash
python examples/simple_game.py
```

## Available Examples

### simple_game.py

Demonstrates:
- Creating RandomBot players
- Running a game simulation with visualization
- Manually creating and applying turns
- Basic game state inspection

**Usage:**
```bash
python examples/simple_game.py
```

The script will:
1. Create two RandomBot players (white and black)
2. Run a simulated game with live visualization
3. Display game moves in the console
4. Show the final winner and game statistics

**Note:** The visualization will open in your default web browser. Close the browser window to stop watching the game (the simulation will continue running).

## Creating Custom Bots

You can create your own bot by extending the `BaseBot` class from `hivesim.robots`:

```python
from hivesim.robots import BaseBot
from hivesim.game import Turn
from typing import List

class MyCustomBot(BaseBot):
    def choose_action_type(self, can_move, can_place, game_state):
        # Your logic to choose between 'move' and 'place'
        return 'place' if can_place else 'move'
    
    def choose_piece_type(self, available_pieces, movable_pieces, action_type, game_state):
        # Your logic to choose which piece type to use
        return list(available_pieces.keys())[0] if action_type == 'place' else list(movable_pieces.keys())[0]
    
    def choose_piece_id(self, piece_ids, piece_type, action_type, game_state):
        # Your logic to choose specific piece instance
        return piece_ids[0]
    
    def choose_target_location(self, available_spaces, piece_type, action_type, game_state):
        # Your logic to choose where to place/move
        return available_spaces[0]
```

## Tips for Game Development

1. **Verbose Mode**: Set `verbose=True` in `simulate_game()` to see detailed move information
2. **Visualization**: Set `plot_game=True` to enable live board visualization
3. **Speed Control**: Adjust `live_delay` parameter to control visualization speed
4. **Turn Limit**: Games have a 200-turn limit by default to prevent infinite loops

## Next Steps

- Try modifying the example to use different bot strategies
- Create your own bot implementation
- Experiment with different piece compositions
- Test edge cases and interesting board states
