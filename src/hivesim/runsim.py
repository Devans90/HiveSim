import time
from game import Game, GameState
from robots import RandomBot
from visualization import visualize_game_board
from Gamelogging import GameLogger

def simulate_game(white_bot, black_bot, verbose=False, plot_game: bool = False, live_delay: float = 0.5, enable_logging: bool = False):
    """Simulate a game between two bots with optional live visualization."""

    logger = GameLogger() if enable_logging else None
    if logger:
        logger.start_game(white_bot.name, black_bot.name)

    game = Game(game_state=GameState(verbose=verbose))
    max_turns = 200  # Prevent infinite games
    winner = None
    end_reason = "normal"

    for turn_num in range(max_turns):
        # Check for loss by queen placement rule
        queen_loss = game.game_state.check_queen_placement_loss()
        if queen_loss:
            if verbose:
                print(f"\n{game.game_state.current_team.upper()} cannot place queen by turn 4!")
                print(f"{queen_loss.upper()} WINS by queen placement rule!")
            end_reason = "queen_surrounded"
            if logger:
                logger.log_game_end(queen_loss, turn_num, end_reason)
                logger.save_current_game()
            return queen_loss, turn_num, game

        current_bot = white_bot if game.game_state.current_team == "white" else black_bot

        # Get bot's move
        turn = current_bot.get_move(game.game_state)

        if verbose:
            print(f"\nTurn {turn_num}: {current_bot.name} ({current_bot.team})")
            print(f"  Action: {turn.action_type}")
            if turn.piece_type:
                print(f"  Piece: {turn.piece_type}")
            if turn.piece_id and turn.action_type == "move":
                piece = game.game_state.all_pieces.get(turn.piece_id)
                if piece and piece.hex_coordinates:
                    print(f"  From: ({piece.hex_coordinates.q}, {piece.hex_coordinates.r}, {piece.hex_coordinates.s})")
            if turn.target_coordinates:
                print(f"  Target: ({turn.target_coordinates.q}, {turn.target_coordinates.r}, {turn.target_coordinates.s})")

        # Apply the turn
        try:
            if logger:
                logger.log_turn(turn_num, turn, game.game_state, current_bot.name)
            game.apply_turn(turn)
        except Exception as e:
            error = str(e)
            if verbose:
                print(f"Error applying turn: {e}")
            if logger:
                logger.log_turn(turn_num, turn, game.game_state, current_bot.name, error=error)
            end_reason = "error"
            winner = "black" if current_bot.team == "white" else "white"
            if logger:
                logger.log_game_end(winner, turn_num, end_reason)
                logger.save_current_game()
            return winner, turn_num, game

        # Live visualization
        if plot_game:
            visualize_game_board(
                game.game_state.board_state,
                show_empty_hexes=game.game_state.get_available_spaces(),
            )
            time.sleep(live_delay)  # small delay to see each frame

        # Check for a winner
        winner = game.game_state.check_win_condition()
        if winner:
            if verbose:
                print(f"\n{winner.upper()} WINS after {turn_num + 1} turns!")
            if logger:
                logger.log_game_end(winner, turn_num + 1, end_reason)
                logger.save_current_game()
            return winner, turn_num + 1, game

    if verbose:
        print(f"\nGame reached maximum turns ({max_turns})")
    end_reason = "max_turns_reached"
    if logger:
        logger.log_game_end(None, max_turns, end_reason)
        logger.save_current_game()  

    return None, max_turns, game


white = RandomBot(team="white")
black = RandomBot(team="black")

_, max_turns, game = simulate_game(white, black, verbose=True, plot_game=True)

# visualize_game_board(game.game_state.board_state, show_empty_hexes=game.game_state.get_available_spaces())