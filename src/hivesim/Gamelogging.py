import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import copy


class GameLogger:
    """Logger for recording game states and moves for debugging and training."""
    
    def __init__(self, log_dir: str = "game_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.current_game_log = []
        self.game_start_time = None
        
    def start_game(self, white_bot_name: str, black_bot_name: str):
        """Initialize logging for a new game."""
        self.game_start_time = datetime.now()
        self.current_game_log = []
        self.current_game_log.append({
            "event": "game_start",
            "timestamp": self.game_start_time.isoformat(),
            "white_bot": white_bot_name,
            "black_bot": black_bot_name
        })
        
    def log_turn(self, turn_num: int, turn: 'Turn', game_state: 'GameState', 
                 bot_name: str, error: Optional[str] = None):
        """Log a single turn with full game state."""
        
        # Convert board state to serializable format
        board_pieces = {}
        for pid, piece in game_state.board_state.pieces.items():
            if piece.location == 'board':
                board_pieces[pid] = {
                    "type": piece.__class__.__name__,
                    "team": piece.team,
                    "icon": piece.icon,
                    "q": piece.hex_coordinates.q,
                    "r": piece.hex_coordinates.r,
                    "s": piece.hex_coordinates.s,
                    "z_level": piece.z_level,
                    "is_pinned": piece.is_pinned()
                }
        
        # Count offboard pieces
        offboard_count = {"white": {}, "black": {}}
        for piece in game_state.all_pieces.values():
            if piece.location == 'offboard':
                piece_type = piece.__class__.__name__
                if piece_type not in offboard_count[piece.team]:
                    offboard_count[piece.team][piece_type] = 0
                offboard_count[piece.team][piece_type] += 1
        
        turn_log = {
            "event": "turn",
            "turn_number": turn_num,
            "bot_name": bot_name,
            "team": turn.player,
            "action_type": turn.action_type,
            "piece_type": turn.piece_type,
            "piece_id": turn.piece_id,
            "target": {
                "q": turn.target_coordinates.q,
                "r": turn.target_coordinates.r,
                "s": turn.target_coordinates.s
            } if turn.target_coordinates else None,
            "board_state": board_pieces,
            "offboard_pieces": offboard_count,
            "error": error
        }
        
        # Add movement details for debugging
        if turn.action_type == 'move' and turn.piece_id:
            piece = game_state.all_pieces.get(turn.piece_id)
            if piece and piece.location == 'board':
                # Log the piece's valid moves before the move
                try:
                    valid_moves = piece.get_valid_moves(game_state)
                    turn_log["valid_moves"] = [
                        {"q": m.q, "r": m.r, "s": m.s} for m in valid_moves
                    ]
                    turn_log["num_valid_moves"] = len(valid_moves)
                except Exception as e:
                    turn_log["valid_moves_error"] = str(e)
        
        self.current_game_log.append(turn_log)
        
    def log_game_end(self, winner: Optional[str], total_turns: int, 
                     reason: str = "normal"):
        """Log the end of a game."""
        game_end_time = datetime.now()
        duration = (game_end_time - self.game_start_time).total_seconds()
        
        end_log = {
            "event": "game_end",
            "timestamp": game_end_time.isoformat(),
            "winner": winner,
            "total_turns": total_turns,
            "duration_seconds": duration,
            "reason": reason  # "normal", "forfeit", "max_turns", "queen_placement_loss", "error"
        }
        
        self.current_game_log.append(end_log)
        
    def save_current_game(self):
        """Save the current game as 'last_game.json' and append to all_games.jsonl"""
        if not self.current_game_log:
            return
        
        # Save as last_game.json (overwrite)
        last_game_path = self.log_dir / "last_game.json"
        with open(last_game_path, 'w') as f:
            json.dump(self.current_game_log, f, indent=2)
        
        # Append to all_games.jsonl (one JSON object per line)
        all_games_path = self.log_dir / "all_games.jsonl"
        with open(all_games_path, 'a') as f:
            f.write(json.dumps(self.current_game_log) + '\n')
        
        print(f"Game logged to {last_game_path} and appended to {all_games_path}")
        
    def load_last_game(self):
        """Load the last game log."""
        last_game_path = self.log_dir / "last_game.json"
        if last_game_path.exists():
            with open(last_game_path, 'r') as f:
                return json.load(f)
        return None
    
    def load_all_games(self):
        """Load all games from the JSONL file."""
        all_games_path = self.log_dir / "all_games.jsonl"
        games = []
        if all_games_path.exists():
            with open(all_games_path, 'r') as f:
                for line in f:
                    games.append(json.loads(line.strip()))
        return games
    
    def get_statistics(self):
        """Get statistics from all logged games."""
        games = self.load_all_games()
        
        stats = {
            "total_games": len(games),
            "wins": {"white": 0, "black": 0, "draw": 0},
            "avg_turns": 0,
            "avg_duration": 0,
            "reasons": {}
        }
        
        total_turns = 0
        total_duration = 0
        
        for game in games:
            end_event = next((e for e in game if e.get("event") == "game_end"), None)
            if end_event:
                winner = end_event.get("winner")
                if winner:
                    stats["wins"][winner] += 1
                else:
                    stats["wins"]["draw"] += 1
                
                total_turns += end_event.get("total_turns", 0)
                total_duration += end_event.get("duration_seconds", 0)
                
                reason = end_event.get("reason", "unknown")
                stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1
        
        if len(games) > 0:
            stats["avg_turns"] = total_turns / len(games)
            stats["avg_duration"] = total_duration / len(games)
        
        return stats


def simulate_game_with_logging(white_bot, black_bot, verbose=False, 
                                plot_game: bool = False, live_delay: float = 0.00005):
    """Simulate a game between two bots with comprehensive logging."""
    
    logger = GameLogger()
    logger.start_game(white_bot.name, black_bot.name)
    
    game = Game(game_state=GameState(verbose=verbose))
    max_turns = 200
    
    winner = None
    end_reason = "normal"

    for turn_num in range(max_turns):
        # Check for loss by queen placement rule
        queen_loss = game.game_state.check_queen_placement_loss()
        if queen_loss:
            if verbose:
                print(f"\n{game.game_state.current_team.upper()} cannot place queen by turn 4!")
                print(f"{queen_loss.upper()} WINS by queen placement rule!")
            winner = queen_loss
            end_reason = "queen_placement_loss"
            logger.log_game_end(winner, turn_num, end_reason)
            logger.save_current_game()
            return winner, turn_num, game

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
        error = None
        try:
            # Log state BEFORE applying turn
            logger.log_turn(turn_num, turn, game.game_state, current_bot.name)
            game.apply_turn(turn)
        except Exception as e:
            error = str(e)
            if verbose:
                print(f"Error applying turn: {e}")
            # Log the error
            logger.log_turn(turn_num, turn, game.game_state, current_bot.name, error=error)
            end_reason = "error"
            break

        # Live visualization
        if plot_game:
            from visualization import visualize_game_board
            visualize_game_board(
                game.game_state.board_state,
                show_empty_hexes=game.game_state.get_available_spaces(),
            )
            time.sleep(live_delay)

        # Check for a winner
        winner = game.game_state.check_win_condition()
        if winner:
            if verbose:
                print(f"\n{winner.upper()} WINS after {turn_num + 1} turns!")
            end_reason = "normal"
            logger.log_game_end(winner, turn_num + 1, end_reason)
            logger.save_current_game()
            return winner, turn_num + 1, game

    if verbose:
        print(f"\nGame reached maximum turns ({max_turns})")
    
    end_reason = "max_turns"
    logger.log_game_end(winner, max_turns, end_reason)
    logger.save_current_game()

    return None, max_turns, game


# Example usage with statistics
if __name__ == "__main__":
    import time
    from game import Game, GameState
    from robots import RandomBot
    
    white = RandomBot(team="white", name="WhiteBot")
    black = RandomBot(team="black", name="BlackBot")
    
    # Run multiple games
    for i in range(5):
        print(f"\n{'='*60}")
        print(f"Game {i+1}")
        print(f"{'='*60}")
        winner, turns, game = simulate_game_with_logging(
            white, black, 
            verbose=True, 
            plot_game=False
        )
    
    # Get statistics
    logger = GameLogger()
    stats = logger.get_statistics()
    print(f"\n{'='*60}")
    print("STATISTICS")
    print(f"{'='*60}")
    print(json.dumps(stats, indent=2))