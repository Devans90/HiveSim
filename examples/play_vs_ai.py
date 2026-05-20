"""
Interactive game: play against an AI opponent.

This example demonstrates:
- Using HumanPlayer for interactive terminal-based move selection
- Live board visualization in the browser (same style as simple_game.py)
- Plugging in a custom AI class via --ai

Usage:
    python play_vs_ai.py                         # Human (white) vs RandomBot
    python play_vs_ai.py --human-color black     # Human plays black
    python play_vs_ai.py --ai mymodule.MyBot     # Use a custom AI
    python play_vs_ai.py --delay 1.0             # 1-second pause after AI moves
"""

import argparse
import importlib
import time

from hivesim.game import Game, GameState
from hivesim.robots import HumanPlayer, RandomBot
from hivesim.visualization import visualize_game_board


def load_bot_class(class_path: str):
    """Load a bot class from a dotted module path, e.g. 'mymodule.MyBot'."""
    if '.' not in class_path:
        raise ValueError(
            f"Bot class path must be 'module.ClassName', got: {class_path}"
        )
    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def play_vs_ai(
    human_color: str = 'white',
    ai_bot=None,
    delay: float = 0.5,
):
    """Run an interactive game where a human plays against an AI.

    Args:
        human_color: Which color the human controls ('white' or 'black').
        ai_bot: A pre-created bot instance.  If None a RandomBot is used.
        delay: Seconds to pause after each AI move so the board refresh is
               visible before the human is prompted.
    """
    ai_color = 'black' if human_color == 'white' else 'white'

    if ai_bot is None:
        ai_bot = RandomBot(team=ai_color, name='RandomBot')

    human = HumanPlayer(team=human_color, name='Human')
    white_player = human if human_color == 'white' else ai_bot
    black_player = ai_bot if human_color == 'white' else human

    print("HiveSim - Play vs AI")
    print("=" * 50)
    print(f"You are playing as : {human_color.upper()}")
    print(f"Opponent           : {ai_bot.name} ({ai_color.upper()})")
    print(f"AI move delay      : {delay}s")
    print("\nThe game board will open in your browser.")
    print("Make your moves in this terminal.")
    print("=" * 50)

    game = Game(game_state=GameState(verbose=False))
    max_turns = 200
    winner = None
    last_turn_num = 0

    for turn_num in range(max_turns):
        last_turn_num = turn_num

        # Check queen-placement loss before the turn
        queen_loss = game.game_state.check_queen_placement_loss()
        if queen_loss:
            print(
                f"\n{game.game_state.current_team.upper()} cannot place queen "
                f"by turn 4!"
            )
            print(f"{queen_loss.upper()} WINS by queen placement rule!")
            winner = queen_loss
            break

        current_player = (
            white_player if game.game_state.current_team == 'white'
            else black_player
        )
        is_human_turn = isinstance(current_player, HumanPlayer)

        # Always refresh board before prompting / acting
        visualize_game_board(
            game.game_state.board_state,
            show_empty_hexes=game.game_state.get_available_spaces(),
            turn_number=turn_num,
        )

        if is_human_turn:
            turn = current_player.get_move(game.game_state)
        else:
            print(f"\nAI ({current_player.name}) is thinking…")
            turn = current_player.get_move(game.game_state)
            if turn.action_type == 'place':
                coord = turn.target_coordinates
                print(
                    f"AI places {turn.piece_type} at "
                    f"({coord.q},{coord.r},{coord.s})"
                )
            elif turn.action_type == 'move':
                piece = game.game_state.all_pieces.get(turn.piece_id)
                if piece and piece.hex_coordinates:
                    fc = piece.hex_coordinates
                    tc = turn.target_coordinates
                    print(
                        f"AI moves {piece.__class__.__name__} from "
                        f"({fc.q},{fc.r},{fc.s}) to ({tc.q},{tc.r},{tc.s})"
                    )
            elif turn.action_type == 'forfeit':
                print("AI forfeits!")
            time.sleep(delay)

        try:
            game.apply_turn(turn)
        except Exception as exc:
            print(f"Error applying turn: {exc}")
            winner = ai_color if is_human_turn else human_color
            break

        winner = game.game_state.check_win_condition()
        if winner:
            break

    # Final board render
    visualize_game_board(
        game.game_state.board_state,
        turn_number=last_turn_num + 1,
    )

    print("\n" + "=" * 50)
    print("GAME OVER")
    print("=" * 50)
    if winner:
        if winner == human_color:
            print(f"You win! ({winner.upper()})")
        else:
            print(f"AI wins! ({winner.upper()})")
    else:
        print("Draw (maximum turns reached)")
    print(f"Total turns: {last_turn_num + 1}")

    return winner, last_turn_num + 1, game


def main():
    parser = argparse.ArgumentParser(
        description="Play Hive against an AI opponent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python play_vs_ai.py
  python play_vs_ai.py --human-color black
  python play_vs_ai.py --ai mymodule.MyBot
  python play_vs_ai.py --delay 1.0
        """,
    )
    parser.add_argument(
        '--human-color',
        choices=['white', 'black'],
        default='white',
        help='Color for the human player (default: white)',
    )
    parser.add_argument(
        '--ai',
        default=None,
        metavar='MODULE.CLASS',
        help=(
            "Dotted path to a custom AI bot class, e.g. 'mymodule.MyBot'. "
            "The class must accept team= and name= keyword arguments. "
            "Defaults to RandomBot."
        ),
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Seconds to pause after each AI move (default: 0.5)',
    )
    args = parser.parse_args()

    ai_color = 'black' if args.human_color == 'white' else 'white'
    ai_bot = None

    if args.ai:
        try:
            BotClass = load_bot_class(args.ai)
            ai_bot = BotClass(team=ai_color, name=args.ai.split('.')[-1])
            print(f"Loaded custom AI: {args.ai}")
        except Exception as exc:
            print(f"Failed to load custom AI '{args.ai}': {exc}")
            print("Falling back to RandomBot.")

    play_vs_ai(
        human_color=args.human_color,
        ai_bot=ai_bot,
        delay=args.delay,
    )


if __name__ == '__main__':
    main()
