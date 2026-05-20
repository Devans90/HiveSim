from abc import ABC, abstractmethod
import random
from typing import List
from hivesim.game import Turn, MovementHelper


class BaseBot(ABC):    
    def __init__(self, team: str, name: str = "Bot"):
        self.team = team
        self.name = name
    
    def get_available_pieces(self, game_state) -> dict:
        """Get all available pieces for this bot's team."""
        player = game_state.white_player if self.team == 'white' else game_state.black_player
        
        available = {}
        for piece in player.pieces:
            if piece.location == 'offboard':
                piece_type = piece.__class__.__name__.lower()
                if piece_type not in available:
                    available[piece_type] = []
                available[piece_type].append(piece.piece_id)
        
        return available
    
    def must_place_queen(self, game_state) -> bool:
        """Check if the bot must place the queen this turn."""
        queen = game_state.get_queen(self.team)
        if self.team == 'white':
            player_turn_number = game_state.turn // 2
        else:
            player_turn_number = (game_state.turn - 1) // 2
        return queen and queen.location == 'offboard' and player_turn_number >= 3


    @abstractmethod
    def choose_action_type(self, can_move: bool, can_place: bool, game_state) -> str:
        """Decide whether to 'move' or 'place'. Must be implemented by subclass."""
        pass
    
    @abstractmethod
    def choose_piece_type(self, available_pieces: dict, movable_pieces: dict, 
                          action_type: str, game_state) -> str:
        """Choose which type of piece to use. Must be implemented by subclass."""
        pass
    
    @abstractmethod
    def choose_piece_id(self, piece_ids: List[str], piece_type: str, 
                        action_type: str, game_state) -> str:
        """Choose specific piece instance from available pieces of chosen type."""
        pass
    
    @abstractmethod
    def choose_target_location(self, available_spaces: List, piece_type: str, 
                               action_type: str, game_state):
        """Choose where to place or move the piece."""
        pass

    def get_move(self, game_state) -> 'Turn':
        """Generate a move..."""
        
        available_pieces = self.get_available_pieces(game_state)
        movable_pieces = game_state.get_movable_pieces(game_state)
        
        if not available_pieces and not movable_pieces:
            return Turn(player=self.team, action_type='forfeit')
        
        # Check if must place the queen
        if self.must_place_queen(game_state):
            action_type = 'place'
            piece_type = 'queenbee'
        else:
            # Delegate decision
            can_move = len(movable_pieces) > 0
            can_place = len(available_pieces) > 0
            
            if not can_move and not can_place:
                return Turn(player=self.team, action_type='forfeit')
            
            action_type = self.choose_action_type(can_move, can_place, game_state)
            piece_type = self.choose_piece_type(available_pieces, movable_pieces, 
                                                action_type, game_state)
        
        available_spaces = game_state.get_available_spaces()
        
        if action_type == 'move':
            # Try all movable piece types to find valid moves
            # This ensures we don't forfeit just because the randomly chosen piece_type
            # can't move, when other piece types might have valid moves
            valid_moves = {}
            
            for piece_type_to_try in movable_pieces.keys():
                candidate_pieces = movable_pieces.get(piece_type_to_try, [])

                for pid in candidate_pieces:
                    if not MovementHelper.hive_stays_connected(pid, game_state):
                        continue
                        
                    piece = game_state.all_pieces.get(pid)
                    valid_targets = []
                    
                    for space in available_spaces:
                        try:
                            test_turn = Turn(
                                player=self.team,
                                piece_id=pid,
                                action_type='move',
                                target_coordinates=space
                            )
                            Turn.validate_movement(test_turn, game_state)
                            valid_targets.append(space)
                        except ValueError:
                            continue
                    if valid_targets:
                        valid_moves[pid] = valid_targets

            if not valid_moves:
                # No valid moves found for any piece type, fall back to placement
                action_type = 'place'
                if available_pieces:
                    piece_type = self.choose_piece_type(available_pieces, {}, 
                                                    'place', game_state)
                else:
                    return Turn(player=self.team, action_type='forfeit')
            else:
                # Choose from all pieces that have valid moves
                pieces_with_moves = list(valid_moves.keys())
                piece_id = self.choose_piece_id(pieces_with_moves, 
                                            'any', action_type, game_state)
                
                target = self.choose_target_location(valid_moves[piece_id], 'any', 
                                                    action_type, game_state)

                return Turn(
                    player=self.team,
                    piece_id=piece_id,
                    action_type='move',
                    target_coordinates=target
                )
        
        # Handle placement (or fallback from failed move)
        if action_type == 'place':  
            valid_spaces = []
            for space in available_spaces:
                try:
                    Turn.validate_placement(Turn(
                        player=self.team,
                        piece_type=piece_type,
                        action_type='place',
                        target_coordinates=space
                    ), game_state)
                    valid_spaces.append(space)
                except ValueError:
                    pass  # Invalid space, skip it
            
            if not valid_spaces:
                # Can't place this piece type, try to move instead
                # This prevents forfeiting when placement fails but moves are still possible
                if movable_pieces:
                    valid_moves = {}
                    
                    for piece_type_to_try in movable_pieces.keys():
                        candidate_pieces = movable_pieces.get(piece_type_to_try, [])

                        for pid in candidate_pieces:
                            if not MovementHelper.hive_stays_connected(pid, game_state):
                                continue
                                
                            piece = game_state.all_pieces.get(pid)
                            valid_targets = []
                            
                            for space in available_spaces:
                                try:
                                    test_turn = Turn(
                                        player=self.team,
                                        piece_id=pid,
                                        action_type='move',
                                        target_coordinates=space
                                    )
                                    Turn.validate_movement(test_turn, game_state)
                                    valid_targets.append(space)
                                except ValueError:
                                    continue
                            if valid_targets:
                                valid_moves[pid] = valid_targets
                    
                    if valid_moves:
                        # Found valid moves, use those instead
                        pieces_with_moves = list(valid_moves.keys())
                        piece_id = self.choose_piece_id(pieces_with_moves, 
                                                    'any', 'move', game_state)
                        
                        target = self.choose_target_location(valid_moves[piece_id], 'any', 
                                                            'move', game_state)

                        return Turn(
                            player=self.team,
                            piece_id=piece_id,
                            action_type='move',
                            target_coordinates=target
                        )
                
                # No valid placements and no valid moves
                if game_state.verbose:
                    print(f"No valid placement spaces for {piece_type}")
                    print(f"Available spaces checked: {len(available_spaces)}")
                return Turn(player=self.team, action_type='forfeit')
            
            # Choose specific piece and target
            piece_id = self.choose_piece_id(available_pieces[piece_type], 
                                        piece_type, 'place', game_state)
            target = self.choose_target_location(valid_spaces, piece_type, 
                                                'place', game_state)
            
            return Turn(
                player=self.team,
                action_type='place',
                piece_type=piece_type,
                piece_id=piece_id,
                target_coordinates=target
            )

class RandomBot(BaseBot):
    """A bot that makes completely random valid moves."""
    
    def __init__(self, team: str, name: str = "RandomBot"):
        super().__init__(team, name)
    
    def choose_action_type(self, can_move: bool, can_place: bool, game_state) -> str:
        """Randomly choose between move and place."""
        options = []
        if can_move:
            options.append('move')
        if can_place:
            options.append('place')
        return random.choice(options)
    
    def choose_piece_type(self, available_pieces: dict, movable_pieces: dict,
                          action_type: str, game_state) -> str:
        """Randomly select a piece type based on action."""
        if action_type == 'move':
            return random.choice(list(movable_pieces.keys()))
        else:
            return random.choice(list(available_pieces.keys()))
    
    def choose_piece_id(self, piece_ids: List[str], piece_type: str,
                        action_type: str, game_state) -> str:
        """Randomly select a specific piece."""
        return random.choice(piece_ids)
    
    def choose_target_location(self, available_spaces: List, piece_type: str,
                               action_type: str, game_state):
        """Randomly select an available space."""
        return random.choice(available_spaces)


class HumanPlayer(BaseBot):
    """A bot that prompts a human player for input via the terminal."""

    def __init__(self, team: str, name: str = "Human"):
        super().__init__(team, name)

    # These abstract methods are required by BaseBot but are not used because
    # HumanPlayer overrides get_move() entirely.
    def choose_action_type(self, can_move: bool, can_place: bool, game_state) -> str:  # pragma: no cover
        pass

    def choose_piece_type(self, available_pieces: dict, movable_pieces: dict,
                          action_type: str, game_state) -> str:  # pragma: no cover
        pass

    def choose_piece_id(self, piece_ids: List[str], piece_type: str,
                        action_type: str, game_state) -> str:  # pragma: no cover
        pass

    def choose_target_location(self, available_spaces: List, piece_type: str,
                               action_type: str, game_state):  # pragma: no cover
        pass

    def get_move(self, game_state) -> 'Turn':
        """Enumerate all valid moves and let the human choose via numbered input."""
        available_pieces = self.get_available_pieces(game_state)
        movable_pieces = game_state.get_movable_pieces(game_state)

        if not available_pieces and not movable_pieces:
            print(f"\n{self.team.capitalize()} has no valid moves. Forfeiting.")
            return Turn(player=self.team, action_type='forfeit')

        must_place_queen = self.must_place_queen(game_state)
        valid_turns: List[Turn] = []
        descriptions: List[str] = []

        if must_place_queen:
            available_spaces = game_state.get_available_spaces()
            for space in available_spaces:
                test_turn = Turn(
                    player=self.team, piece_type='queenbee',
                    action_type='place', target_coordinates=space
                )
                try:
                    Turn.validate_placement(test_turn, game_state)
                    valid_turns.append(test_turn)
                    descriptions.append(
                        f"Place QueenBee at ({space.q},{space.r},{space.s})"
                    )
                except ValueError:
                    pass
        else:
            available_spaces = game_state.get_available_spaces()

            # --- Placements ---
            seen_placements: set = set()
            for piece_type in available_pieces:
                for space in available_spaces:
                    key = (piece_type, space.q, space.r, space.s)
                    if key in seen_placements:
                        continue
                    test_turn = Turn(
                        player=self.team, piece_type=piece_type,
                        action_type='place', target_coordinates=space
                    )
                    try:
                        Turn.validate_placement(test_turn, game_state)
                        seen_placements.add(key)
                        valid_turns.append(test_turn)
                        descriptions.append(
                            f"Place {piece_type.capitalize()} at ({space.q},{space.r},{space.s})"
                        )
                    except ValueError:
                        pass

            # --- Movements ---
            for piece_type, piece_ids in movable_pieces.items():
                for pid in piece_ids:
                    if not MovementHelper.hive_stays_connected(pid, game_state):
                        continue
                    piece = game_state.all_pieces.get(pid)
                    if piece is None or piece.hex_coordinates is None:
                        continue
                    from_coord = piece.hex_coordinates
                    piece_name = piece.__class__.__name__
                    for target in piece.get_valid_moves(game_state):
                        turn = Turn(
                            player=self.team, piece_id=pid,
                            action_type='move', target_coordinates=target
                        )
                        valid_turns.append(turn)
                        descriptions.append(
                            f"Move {piece_name} from "
                            f"({from_coord.q},{from_coord.r},{from_coord.s}) "
                            f"to ({target.q},{target.r},{target.s})"
                        )

        if not valid_turns:
            print(f"\n{self.team.capitalize()} has no valid moves. Forfeiting.")
            return Turn(player=self.team, action_type='forfeit')

        print(f"\n{'='*50}")
        print(f"Your turn! ({self.team.upper()})")
        print(f"{'='*50}")
        print("Available moves:")
        for i, desc in enumerate(descriptions, 1):
            print(f"  {i:3d}. {desc}")
        print()

        while True:
            try:
                raw = input(
                    f"Enter move number (1-{len(valid_turns)}), or 'q' to forfeit: "
                ).strip()
                if raw.lower() == 'q':
                    return Turn(player=self.team, action_type='forfeit')
                choice = int(raw)
                if 1 <= choice <= len(valid_turns):
                    print(f"  → {descriptions[choice - 1]}")
                    return valid_turns[choice - 1]
                print(f"  Please enter a number between 1 and {len(valid_turns)}")
            except ValueError:
                print("  Invalid input. Please enter a number.")
            except (EOFError, KeyboardInterrupt):
                print("\nGame interrupted.")
                return Turn(player=self.team, action_type='forfeit')