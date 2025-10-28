"""
Simple example of running a HiveSim game between two random bots.

This example demonstrates:
- Setting up bots
- Running a game simulation
- Visualizing the game board
"""

from hivesim.game import Game, GameState, Turn, HexCoordinate
from hivesim.robots import RandomBot
from hivesim.runsim import simulate_game


def main():
    print("HiveSim - Simple Game Example")
    print("=" * 50)
    
    # Create bots for each team
    white_bot = RandomBot(team='white', name='WhiteBot')
    black_bot = RandomBot(team='black', name='BlackBot')
    
    # Run the simulation
    print("\nStarting game simulation...")
    print("Close the browser window to stop the visualization.\n")
    
    winner, turns, game = simulate_game(
        white_bot=white_bot,
        black_bot=black_bot,
        verbose=True,        # Print game moves to console
        plot_game=True,      # Show live visualization
        live_delay=0.5       # 0.5 second delay between moves
    )
    
    # Print final results
    print("\n" + "=" * 50)
    print("GAME OVER")
    print("=" * 50)
    print(f"Winner: {winner.upper() if winner else 'DRAW'}")
    print(f"Total turns: {turns}")
    print(f"Pieces on board: {len(game.game_state.board_state.pieces)}")
    

def manual_game_example():
    """
    Example of manually playing a game by creating turns.
    """
    print("\nManual Game Example")
    print("=" * 50)
    
    # Create a new game
    game = Game()
    
    # White places first ant at origin
    print("\n1. White places Ant at origin")
    turn1 = Turn(
        player='white',
        piece_type='ant',
        action_type='place',
        target_coordinates=HexCoordinate(q=0, r=0, s=0)
    )
    game.apply_turn(turn1)
    print(f"   Pieces on board: {len(game.game_state.board_state.pieces)}")
    
    # Black places ant adjacent to white
    print("\n2. Black places Ant adjacent to white")
    turn2 = Turn(
        player='black',
        piece_type='ant',
        action_type='place',
        target_coordinates=HexCoordinate(q=1, r=-1, s=0)
    )
    game.apply_turn(turn2)
    print(f"   Pieces on board: {len(game.game_state.board_state.pieces)}")
    
    # White places another ant
    print("\n3. White places another Ant")
    turn3 = Turn(
        player='white',
        piece_type='ant',
        action_type='place',
        target_coordinates=HexCoordinate(q=-1, r=0, s=1)
    )
    game.apply_turn(turn3)
    print(f"   Pieces on board: {len(game.game_state.board_state.pieces)}")
    
    print("\nManual game example completed!")
    print(f"Current turn: {game.game_state.turn}")
    print(f"Current team: {game.game_state.current_team}")


if __name__ == '__main__':
    # Run automated game
    main()
    
    # Uncomment to see manual game example
    # manual_game_example()
