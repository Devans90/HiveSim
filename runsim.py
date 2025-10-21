import time
from src.game import Game, GameState
from src.visualization import visualize_game_board
from src.robots import RandomBot

def simulate_game(white_bot, black_bot, verbose=False, plot_game: bool = False):
    """Simulate a game between two bots."""
    
    game = Game(game_state=GameState(verbose=verbose))
    
    max_turns = 200  # Prevent infinite games
    
    for turn_num in range(max_turns):
        queen_loss = game.game_state.check_queen_placement_loss()
        if queen_loss:
            if verbose:
                print(f"\n{game.game_state.current_team.upper()} cannot place queen by turn 4!")
                print(f"{queen_loss.upper()} WINS by queen placement rule!")
            return queen_loss, turn_num, game

        current_bot = white_bot if game.game_state.current_team == 'white' else black_bot
        
        # Get bot's move
        turn = current_bot.get_move(game.game_state)
        
        if verbose:
            print(f"\nTurn {turn_num}: {current_bot.name} ({current_bot.team})")
            print(f"  Action: {turn.action_type}")
            if turn.piece_type:
                print(f"  Piece: {turn.piece_type}")
            if turn.piece_id and turn.action_type == 'move':
                # Show current location for moves
                piece = game.game_state.all_pieces.get(turn.piece_id)
                if piece and piece.hex_coordinates:
                    print(f"  From: ({piece.hex_coordinates.q}, {piece.hex_coordinates.r}, {piece.hex_coordinates.s})")
            if turn.target_coordinates:
                print(f"  Target: ({turn.target_coordinates.q}, {turn.target_coordinates.r}, {turn.target_coordinates.s})")
        
        # Apply the turn
        try:
            game.apply_turn(turn)
        except Exception as e:
            print(f"Error applying turn: {e}")
            break
        
        # Check for winner
        winner = game.game_state.check_win_condition()
        if winner:
            if verbose:
                print(f"\n{winner.upper()} WINS after {turn_num + 1} turns!")
            return winner, turn_num + 1, game
    
    if verbose:
        print(f"\nGame reached maximum turns ({max_turns})")
    if plot_game:
        visualize_game_board(game.game_state.board_state, show_empty_hexes=game.game_state.get_available_spaces())
        time.sleep(1)
    return None, max_turns, game


white = RandomBot(team='white')
black = RandomBot(team='black')
_, max_turns, game =simulate_game(white, black, verbose=True, plot_game=True)

visualize_game_board(game.game_state.board_state, show_empty_hexes=game.game_state.get_available_spaces())