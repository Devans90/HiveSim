from typing import Dict
import heapq
from typing import Set, Tuple
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import plotly.graph_objects as go
import numpy as np
from typing import List, Optional
import uuid

class HexCoordinate(BaseModel):
    q: int
    r: int
    s: int
    @field_validator('s', mode='before')
    @classmethod
    def validate_cube_coordinates(cls, v, values):
        if values.data['q'] + values.data['r'] + v != 0:
            raise ValueError('Invalid cube coordinates')
        return v

    def get_adjacent_hexes(self):
        directions = [(1, -1, 0), (1, 0, -1), (0, 1, -1), (-1, 1, 0), (-1, 0, 1), (0, -1, 1)]
        adjacent = []
        for dq, dr, ds in directions:
            adjacent.append(HexCoordinate(q=self.q + dq, r=self.r + dr, s=self.s + ds))
        return adjacent

class GamePiece(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    
    hex_coordinates: Optional[HexCoordinate] = None
    icon: str = "�"
    team: str
    piece_id: int = Field(default_factory=lambda: str(uuid.uuid4()))
    location: str = Field(default='offboard') # 'offboard', 'board', 'stacked'

    @field_validator('team')
    @classmethod
    def validate_team(cls, v):
        if v not in ['black', 'white']:
            raise ValueError('Team must be either "black" or "white"')
        return v

class Spider(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🕷️",
            location='offboard'
            )

class Ant(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🐜",
            location='offboard'
            )

class Beetle(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🪲",
            location='offboard'
            )

class Grasshopper(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🦗",
            location='offboard'
            )

class QueenBee(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🐝",
            location='offboard'
            )

class Ladybug(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🐞",
            location='offboard'
            )

class Mosquito(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🦟",
            location='offboard'
            )

class BoardState(BaseModel):
    pieces: dict = Field(default_factory=dict)

    def add_piece(self, piece_id: str, piece: GamePiece, coordinates: HexCoordinate):
        piece.hex_coordinates = coordinates
        piece.location = 'board'
        self.pieces[piece_id] = piece

    def move_piece(self, piece_id: str, piece: GamePiece, new_coordinates: HexCoordinate):
        piece.hex_coordinates = new_coordinates
        self.pieces[piece_id] = piece

        # Note: This does not handle stacking logic for Beetles or other pieces.
        # TODO maybe some cool animation here
        
    def get_piece(self, piece_id: str):
        return self.pieces.get(piece_id, None)
    
class Player(BaseModel):
    name: str
    team: str
    pieces: List[GamePiece] = Field(default_factory=None)

    def __init__(self, name: str, team: str, pieces: Optional[List[GamePiece]] = None):
        if pieces is None:
            pieces = [
                *[Ant(team=team) for _ in range(12)],
                QueenBee(team=team)
                # super basic mode to start. add more pieces later
            ]
        super().__init__(name=name, team=team, pieces=pieces)

    @field_validator('team')
    @classmethod
    def validate_team(cls, v):
        if v not in ['black', 'white']:
            raise ValueError('Team must be either "black" or "white"')
        return v

class GameState(BaseModel):
    turn: int = Field(0, ge=0)
    white_player: Player = Player(name='white', team='white', pieces=[])
    black_player: Player = Player(name='black', team='black', pieces=[])
    current_team: str = Field(default='white')
    board_state: BoardState = Field(default_factory=BoardState)
    verbose: bool = Field(default=True)
    all_pieces: Dict[str, GamePiece] = Field(default_factory=dict)

    def __init__(self, white_player: Player = None, black_player: Player = None, **data):
        if white_player is None:
            white_player = Player(name='white', team='white')
        if black_player is None:
            black_player = Player(name='black', team='black')
        super().__init__(white_player=white_player, black_player=black_player, **data)

        # construct a big ol' dictionary of all pieces for easy access
        for piece in self.white_player.pieces:
            self.all_pieces[piece.piece_id] = piece
        for piece in self.black_player.pieces:
            self.all_pieces[piece.piece_id] = piece

    def get_occupied_spaces(self):
        occupied = []
        for piece in self.board_state.pieces.values():
            if piece.location == 'offboard':    
                pass
            elif piece.location == 'board':
                occupied.append((piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s))

        return occupied

    def get_available_spaces(self):
        if len(self.board_state.pieces) == 0:
            if self.verbose:
                print("No pieces on the board, returning center hex (0,0,0) as available space.")
            return [HexCoordinate(q=0, r=0, s=0)]  # If no pieces are on the board, return the center hex
        
        # get occupied spaces
        occupied = set(self.get_occupied_spaces())
        adjacent = set()

        for q, r, s in occupied:
            for dq, dr, ds in [(1, -1, 0), (1, 0, -1), (0, 1, -1), (-1, 1, 0), (-1, 0, 1), (0, -1, 1)]:
                adjacent.add((q + dq, r + dr, s + ds))
        relative = adjacent - occupied
        coords = []
        for coord in relative:
            coords.append(HexCoordinate(q=coord[0], r=coord[1], s=coord[2]))
        return coords

    def get_movable_pieces(self, game_state) -> dict:
        """Get all pieces on the board for this bot's team."""
        player = game_state.white_player if self.current_team == 'white' else game_state.black_player
        
        movable = {}
        for piece in player.pieces:
            if piece.location == 'board':  # Only pieces ON the board
                piece_type = piece.__class__.__name__.lower()                
                if piece_type not in movable:
                    movable[piece_type] = []
                movable[piece_type].append(piece.piece_id)
        
        return movable

    def check_win_condition(self):
        # Check if either queen bee is completely surrounded
        white_queen = next((p for p in self.white_player.pieces if isinstance(p, QueenBee)), None)
        black_queen = next((p for p in self.black_player.pieces if isinstance(p, QueenBee)), None)
        if white_queen and white_queen.location == 'board':
            white_adjacent = set((hex.q, hex.r, hex.s) for hex in white_queen.hex_coordinates.get_adjacent_hexes())
            occupied = set(self.get_occupied_spaces())
            if white_adjacent.issubset(occupied):
                return 'black'  # Black wins
        if black_queen and black_queen.location == 'board':
            black_adjacent = set((hex.q, hex.r, hex.s) for hex in black_queen.hex_coordinates.get_adjacent_hexes())
            occupied = set(self.get_occupied_spaces())
            if black_adjacent.issubset(occupied):
                return 'white'  # White wins
        return None  # No winner yet

    def get_queen(self, team: str) -> Optional[QueenBee]:
        """Get the queen bee for a specific team."""
        for piece in self.all_pieces.values():
            if isinstance(piece, QueenBee) and piece.team == team:
                return piece
        return None
    
    def check_queen_placement_loss(self) -> Optional[str]:
        """Check if a player has lost by being unable to place their queen by turn 4."""
        current_player = self.white_player if self.current_team == 'white' else self.black_player
        player_turn_number = self.turn // 2
        
        # Must be at turn 4+ for this player
        if player_turn_number < 4:
            return None
        
        # Check if queen is still offboard
        queen = self.get_queen(self.current_team)
        if not queen or queen.location != 'offboard':
            return None  # Queen already placed, no issue
        
        # Check if there are any valid spaces to place the queen
        available_spaces = self.get_available_spaces()
        for space in available_spaces:
            try:
                Turn.validate_placement(Turn(
                    player=self.current_team,
                    piece_type='queenbee',
                    action_type='place',
                    target_coordinates=space
                ), self)
                return None  # Found at least one valid space
            except ValueError:
                continue  # This space is invalid, keep checking
        
        # No valid spaces found - opponent wins
        opponent = 'black' if self.current_team == 'white' else 'white'
        return opponent

    def get_pieces_by_type(self, piece_type: type, team: Optional[str] = None) -> List[GamePiece]:
        """Get all pieces of a specific type, optionally filtered by team."""
        pieces = [p for p in self.all_pieces.values() if isinstance(p, piece_type)]
        if team:
            pieces = [p for p in pieces if p.team == team]
        return pieces

    def get_piece_by_coordinates(self, coordinates: HexCoordinate) -> Optional[GamePiece]:
        """Get the piece located at specific hex coordinates."""
        for piece in self.all_pieces.values():
            if piece.hex_coordinates == coordinates and piece.location == 'board':
                return piece
        print("No piece found at the given coordinates.")
        return None

    def are_hexes_adjacent(self, hex1: HexCoordinate, hex2: HexCoordinate) -> bool:
        """Check if two hexes are adjacent to each other."""
        # Manhattan distance of 2
        distance = abs(hex1.q - hex2.q) + abs(hex1.r - hex2.r) + abs(hex1.s - hex2.s)
        return distance == 2

    def can_slide_to(self, from_hex: HexCoordinate, to_hex: HexCoordinate, occupied: Set[Tuple[int, int, int]]) -> bool:
        """
        Can slide one tile adjacent, for usage during pathing to check every step is valid.
        """

        # double check path is adjacent
        if not self.are_hexes_adjacent(from_hex, to_hex):
            raise ValueError('Hexes are not adjacent')

        # # coords
        # from_coords = (from_hex.q, from_hex.r, from_hex.s)
        # to_coords = (to_hex.q, to_hex.r, to_hex.s)

        # neighbors
        from_neighbors = set([(h.q, h.r, h.s) for h in from_hex.get_adjacent_hexes()])
        to_neighbors = set([(h.q, h.r, h.s) for h in to_hex.get_adjacent_hexes()])

        mutual_neighbors = from_neighbors.intersection(to_neighbors)
        occupied_mutual = mutual_neighbors.intersection(occupied)

        if len(occupied_mutual) >= 2:
            return False # cannot slide through tight gap
        
        # if len(occupied_mutual) == 0:
        #     # Check if we're sliding along the edge of the hive
        #     all_neighbors = from_neighbors.union(to_neighbors)
        #     all_neighbors.discard(from_coords)  # Remove the from position
        #     all_neighbors.discard(to_coords)    # Remove the to position
            
        #     non_mutual_occupied = all_neighbors.intersection(occupied) - mutual_neighbors
            
        #     # If there are no occupied pieces touching either position (except mutual neighbors),
        #     # the piece would lose contact during the slide
        #     if len(non_mutual_occupied) == 0:
        #         return False
        
        return True

    def get_valid_slide_positions(self, current: HexCoordinate, occupied: Set[Tuple[int, int, int]]) -> List[HexCoordinate]:
        """
        Get all positions that a piece can slide to from the current position.
        A piece can slide to an adjacent empty space if:
        1. The space is not occupied
        2. The piece can physically slide there (not blocked by a gate)
        3. The space is adjacent to at least one other piece (maintains hive connection)
        """
        valid_positions = []
        current_coords = (current.q, current.r, current.s)
        
        for adjacent_hex in current.get_adjacent_hexes():
            adj_coords = (adjacent_hex.q, adjacent_hex.r, adjacent_hex.s)
            
            # 1. Skip if position is occupied
            if adj_coords in occupied:
                continue

            # 2. Check if we can physically slide to this position
            if not self.can_slide_to(current, adjacent_hex, occupied):
                continue

            # 3. Check if this position maintains hive connection
            # (must be adjacent to at least one piece after the move)
            has_neighbor = False
            for neighbor_hex in adjacent_hex.get_adjacent_hexes():
                neighbor_coords = (neighbor_hex.q, neighbor_hex.r, neighbor_hex.s)
                # Don't count the current position as a neighbor (we're leaving it)
                if neighbor_coords in occupied and neighbor_coords != current_coords:
                    has_neighbor = True
                    break
            
            if has_neighbor:
                valid_positions.append(adjacent_hex)
        return valid_positions

    def check_freedom_of_movement(self, start:HexCoordinate, end:HexCoordinate, piece_id: str) -> bool:
        # check if its no move just in case of madness
        if start.q == end.q and start.r == end.r and start.s == end.s:
            return True
        
        # get occupied spaces except the moving piece
        occupied = set()
        for pid, piece in self.board_state.pieces.items():
            if pid != piece_id and piece.location == 'board':
                occupied.add((piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s))

        # check if its an ajacent move
        if self.are_hexes_adjacent(start, end):
            return self.can_slide_to(start, end, occupied) # can slide directly
        
        # use a star pathfinding to see if a path exists
        path = self.get_path(start, end, piece_id)
        if path is not None:
            return True
        return False

    def get_path(self, start: HexCoordinate, end: HexCoordinate, piece_id: str) -> Optional[List[HexCoordinate]]:

        def heuristic(a: HexCoordinate, b: HexCoordinate) -> int:
            # Manhattan distance in hex coordinates
            return (abs(a.q - b.q) + abs(a.r - b.r) + abs(a.s - b.s)) // 2
        
        # Priority queue: (f_score, counter, current_hex, path)
        # counter is used to break ties in f_score
        counter = 0
        open_set = []
        heapq.heappush(open_set, (heuristic(start, end), counter, start, [start]))
        
        # Track visited nodes to avoid cycles
        visited = set()
        visited.add((start.q, start.r, start.s))
        
        # Get all occupied spaces except the moving piece
        occupied = set()
        for pid, piece in self.board_state.pieces.items():
            if pid != piece_id and piece.location == 'board':
                occupied.add((piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s))
        
        while open_set:
            _, _, current, path = heapq.heappop(open_set)
            
            # Check if we reached the goal
            if current.q == end.q and current.r == end.r and current.s == end.s:
                return path
            
            # Explore neighbors
            for next_hex in self.get_valid_slide_positions(current, occupied):
                next_coords = (next_hex.q, next_hex.r, next_hex.s)
                
                if next_coords not in visited:
                    visited.add(next_coords)
                    g_score = len(path)  # Cost from start to current
                    h_score = heuristic(next_hex, end)  # Heuristic cost to goal
                    f_score = g_score + h_score
                    
                    counter += 1
                    new_path = path + [next_hex]
                    heapq.heappush(open_set, (f_score, counter, next_hex, new_path))
        
        return None 

    @model_validator(mode='after')
    def validate_current_team(self):
        if self.current_team not in ['white', 'black']:
            raise ValueError('Current team must be either "white" or "black"')
        return self

class Turn(BaseModel):
    player: str
    piece_id: Optional[str] = None
    piece_type: Optional[str] = None
    action_type: str # 'place', 'move', 'forfeit'
    target_coordinates: Optional[HexCoordinate] = None

    @staticmethod
    def hive_stays_connected(piece_id, game_state):
        # BFS or DFS to check if all pieces are still connected without the piece being moved
        # get all pieces on board except the one being moved
        pieces_on_board = {}
        for pid, piece in game_state.board_state.pieces.items():
            if pid == piece_id:
                continue
            if piece.location == 'board':
                pieces_on_board[pid] = piece
        
        if len(pieces_on_board) <= 1:
            return True # only one piece on board, so can't break hive
        
        # start BFS from any piece
        # aka, can i go from this one peice to every other piece
        start_id = next(iter(pieces_on_board.keys()))
        visited = {start_id}
        queue = [start_id]

        # build adjacancy map
        coord_to_pid = {}
        for pid, piece in pieces_on_board.items():
            coords = (piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s)
            coord_to_pid[coords] = pid

        while queue:
            current_id = queue.pop(0)
            current_piece = pieces_on_board[current_id]

            # check all the adcajacent pieces
            for adj_hex in current_piece.hex_coordinates.get_adjacent_hexes():
                adj_coords = (adj_hex.q, adj_hex.r, adj_hex.s)

                # find all the pieces adjacent to this piece
                if adj_coords in coord_to_pid:
                    adj_pid = coord_to_pid[adj_coords]
                    if adj_pid not in visited:
                        visited.add(adj_pid)
                        queue.append(adj_pid)
        return len(visited) == len(pieces_on_board) # ie if we visited every piece, hive is intact

    @staticmethod
    def validate_movement(turn, game_state):
        # generic movement validation (non-specific to piece type)
        # have to know what id to move
        if turn.piece_id is None:
            raise ValueError('Movement requires piece_id to specify which piece to move')
        
        # if the queen is not placed by turn 4, no moves allowed
        queen = game_state.get_queen(turn.player)
        if turn.player == 'white':
            player_turn_number = game_state.turn // 2
        else:
            player_turn_number = (game_state.turn - 1) // 2
        if player_turn_number >= 4 and queen.location == 'offboard':
            raise ValueError(f'{turn.player.capitalize()}\'s Queen has not been placed by turn 4, cannot move pieces')

        piece = game_state.all_pieces.get(turn.piece_id)
        if piece is None: # wrong id
            raise ValueError('Piece not found')
        if piece.team != turn.player: # hands off not yours
            raise ValueError('Cannot move opponent piece')
        if piece.location != 'board': # not on board
            raise ValueError('Can only move pieces that are on the board')

        # Check if the target coordinates are valid
        if turn.target_coordinates is None:
            raise ValueError('Movement requires target_coordinates to specify where to move the piece')
        
        # broken hive rule
        if not Turn.hive_stays_connected(turn.piece_id, game_state):
            raise ValueError('Move would break the hive, which is not allowed')

        # freedom of movement rule
        if not game_state.check_freedom_of_movement(piece.hex_coordinates, turn.target_coordinates, turn.piece_id):
            raise ValueError('Piece cannot slide to target coordinates due to freedom of movement rule')

        return turn
    
    @staticmethod
    def validate_placement(turn, game_state):
        
        # need either id or type, find an id if not given
        if turn.piece_id is None: 
            if turn.piece_type is None:
                raise ValueError('Placement requires either piece_id or piece_type to specify which piece to place')
            
            # find an unplaced piece of that type for that player
            piece_type_map = {
                'ant': Ant,
                'beetle': Beetle,
                'grasshopper': Grasshopper,
                'queenbee': QueenBee,
                'queen': QueenBee,
                'spider': Spider,
                'ladybug': Ladybug,
                'mosquito': Mosquito
            }
            piece_class = piece_type_map.get(turn.piece_type.lower())
            
            player = game_state.white_player if turn.player == 'white' else game_state.black_player
            available_piece = next(
                (p for p in player.pieces 
                 if isinstance(p, piece_class) and p.location == 'offboard'),
                None
            )
            # player = game_state.white_player if turn.player == 'white' else game_state.black_player

            if available_piece is None:
                raise ValueError(f'No unplaced piece of type {turn.piece_type} available for player {turn.player}')
            
            turn.piece_id = available_piece.piece_id
        
        # First piece must be placed at the center
        if game_state.turn == 0:
            if turn.target_coordinates != HexCoordinate(q=0, r=0, s=0):
                raise ValueError('First piece must be placed at the center (0,0,0)')
            else:
                return turn
        
        # check its next to an occupied space
        occupied = game_state.get_occupied_spaces()
        adjacent = turn.target_coordinates.get_adjacent_hexes()
        adjacent = [(hex.q, hex.r, hex.s) for hex in adjacent]
        occupied = set(occupied)
        adjacent = set(adjacent)
        if len(occupied.intersection(adjacent)) == 0:
            raise ValueError('Target coordinates must be adjacent to an occupied space')

        target = (turn.target_coordinates.q, turn.target_coordinates.r, turn.target_coordinates.s)
        occupied = set(game_state.get_occupied_spaces())

        if target in occupied:
            raise ValueError('Target coordinates are already occupied')

        # check its not next to an opposite colour
        if game_state.turn > 1: # skip this check for the first placement
            # get players
            player = game_state.white_player if turn.player == 'white' else game_state.black_player
            opponent = game_state.black_player if turn.player == 'white' else game_state.white_player
            
            # get ids
            player_piece_ids = [piece.piece_id for piece in player.pieces if piece.location == 'board']
            opponent_piece_ids = [piece.piece_id for piece in opponent.pieces if piece.location == 'board']

            # coordinates adjacent to player
            player_adjacent = set()
            for pid in player_piece_ids:
                piece = game_state.board_state.pieces[pid]
                for adj in piece.hex_coordinates.get_adjacent_hexes():
                    player_adjacent.add((adj.q, adj.r, adj.s))
            
            # coordinates adjacent to opponent
            opponent_adjacent = set()
            for pid in opponent_piece_ids:
                piece = game_state.board_state.pieces[pid]
                for adj in piece.hex_coordinates.get_adjacent_hexes():
                    opponent_adjacent.add((adj.q, adj.r, adj.s))

            if target not in player_adjacent:
                raise ValueError('Target coordinates must be adjacent to your own pieces')
        
            # Must NOT be adjacent to any opponent pieces
            if target in opponent_adjacent:
                raise ValueError('Target coordinates cannot be adjacent to opponent pieces')

        # check piece is offboard
        # get piece
        piece = game_state.all_pieces.get(turn.piece_id)

        if piece is None:
            raise ValueError('Piece not found in player pieces')
        if piece.location != 'offboard':
            raise ValueError('Piece is already on the board')
        
        # check if queen has been placed by turn 4
        queen = game_state.get_queen(turn.player)
        if turn.player == 'white':
            player_turn_number = game_state.turn // 2
        else:
            player_turn_number = (game_state.turn - 1) // 2

        if player_turn_number == 3 and queen.location == 'offboard':
            # On turn 4, MUST place queen
            piece = game_state.all_pieces.get(turn.piece_id)
            if not isinstance(piece, QueenBee):
                raise ValueError(f'{turn.player.capitalize()}\'s Queen must be placed on turn 4')
        elif player_turn_number > 3 and queen.location == 'offboard':
        # After turn 4, it's too late - this shouldn't happen if enforced properly
            raise ValueError(f'{turn.player.capitalize()} failed to place Queen by turn 4')
    
        return turn

class Game(BaseModel):
    game_state: GameState = Field(default_factory=GameState)
    history: List[Turn] = Field(default_factory=list)

    def apply_turn(self, turn: Turn):
        # Validate turn

        if turn.action_type == 'place':
            turn = Turn.validate_placement(turn, self.game_state)
            
            piece = self.game_state.all_pieces.get(turn.piece_id)
            piece.hex_coordinates = turn.target_coordinates
            piece.location = 'board'
            self.game_state.board_state.add_piece(turn.piece_id, piece, turn.target_coordinates)


        elif turn.action_type == 'move':
            Turn.validate_movement(turn, self.game_state)
            
            # actually move the piece
            piece = self.game_state.all_pieces.get(turn.piece_id)
            piece.hex_coordinates = turn.target_coordinates
            self.game_state.board_state.move_piece(turn.piece_id, piece, turn.target_coordinates)

        elif turn.action_type == 'forfeit':
            if self.game_state.verbose:
                print(f"{turn.player} has forfeited the game.")
            # Forfeit logic to be implemented
            pass
        
        else:
            raise ValueError('Invalid action type')
        
        # Update game state for next turn
        self.history.append(turn)
        win = self.game_state.check_win_condition()
        self.game_state.turn += 1
        self.game_state.current_team = 'black' if self.game_state.current_team == 'white' else 'white'
        return turn.piece_id

