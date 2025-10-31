from abc import abstractmethod
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
    z_level: int = Field(default=0) # for stacked pieces like beetles
    pieces_below: List[str] = Field(default_factory=list) # piece_ids of pieces below 
    pieces_above: List[str] = Field(default_factory=list) # piece_ids of pieces above 

    def is_pinned(self) -> bool:
        """Check if this has a bug hat"""
        return len(self.pieces_above) > 0
    
    def get_top_piece(self, game_state) -> 'GamePiece':
        """Get the top piece in the stack."""
        if not self.is_pinned():
            return self
        
        top_piece_id = self.pieces_above[-1]
        top_piece = game_state.all_pieces.get(top_piece_id)
        if top_piece:
            return top_piece.get_top_piece(game_state) # fallback here if somehow the above chain is broken, this may cause headaches...
        return self

    @field_validator('team')
    @classmethod
    def validate_team(cls, v):
        if v not in ['black', 'white']:
            raise ValueError('Team must be either "black" or "white"')
        return v
    
    @abstractmethod
    def get_valid_moves(self, game_state) -> List[HexCoordinate]:
        """Return a list of valid moves for this piece given the current game state."""
        pass

    @abstractmethod
    def can_move_to(self, target: HexCoordinate, game_state) -> bool:
        """Return whether this specific piece type can move to the target hex coordinate."""
        pass

    def get_movement_range(self) -> int:
        """Return the movement range of this piece type. default if not overridden is unlimited such as ant"""
        pass

class Spider(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🕷️",
            location='offboard'
            )
    
    def get_valid_moves(self, game_state):
        if self.location != 'board':
            return []
        if self.is_pinned():
            return []
        # cannot move if removing this piece would break the hive
        if not MovementHelper.hive_stays_connected(self.piece_id, game_state):
            return []

        start = self.hex_coordinates
        occupied = MovementHelper.get_occupied_spaces(game_state, exclude_piece_id=self.piece_id)

        results = set()

        def has_neighbor(coord: HexCoordinate) -> bool:
            for n in coord.get_adjacent_hexes():
                if (n.q, n.r, n.s) in occupied:
                    return True
            return False

        def dfs(current: HexCoordinate, depth: int, visited: Set[Tuple[int,int,int]]):
            # depth counts how many steps taken so far
            if depth == 3:
                # don't include starting square
                if (current.q, current.r, current.s) != (start.q, start.r, start.s):
                    results.add((current.q, current.r, current.s))
                return

            for adj in current.get_adjacent_hexes():
                coords = (adj.q, adj.r, adj.s)

                # can't move into occupied space
                if coords in occupied:
                    continue

                # cannot revisit same hex in same spider path
                if coords in visited:
                    continue

                # must be able to physically slide into the adjacent hex
                try:
                    if not MovementHelper.can_slide_to_adjacent(current, adj, occupied):
                        continue
                except ValueError:
                    # non-adjacent input to helper -- skip
                    continue

                # intermediate and final positions must be adjacent to hive (have at least one neighbor)
                if not has_neighbor(adj):
                    continue

                visited.add(coords)
                dfs(adj, depth + 1, visited)
                visited.remove(coords)

        visited = {(start.q, start.r, start.s)}
        dfs(start, 0, visited)

        return [HexCoordinate(q=q, r=r, s=s) for (q, r, s) in results]
    def can_move_to(self, target: HexCoordinate, game_state) -> bool:
        valid_moves = self.get_valid_moves(game_state)
        for move in valid_moves:
            if move.q == target.q and move.r == target.r and move.s == target.s: # check the move is in valid moves
                return True
        return False
    
class Ant(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🐜",
            location='offboard'
            )
    def get_valid_moves(self, game_state):
        if self.location != 'board':
            return []
        
        if self.is_pinned():
            return []
        
        # is this a key ant holding the hive together?
        if not MovementHelper.hive_stays_connected(self.piece_id, game_state):
            return []

        # BFS to find all positions the ant can slide to
        visited = set()
        queue = [self.hex_coordinates]
        visited.add((self.hex_coordinates.q, self.hex_coordinates.r, self.hex_coordinates.s))
        valid_moves = []

        occupied = MovementHelper.get_occupied_spaces(game_state, exclude_piece_id=self.piece_id)

        while queue:
            current = queue.pop(0)
            
            # Get all valid slides from this position
            for next_hex in game_state.get_valid_slide_positions(current, occupied):
                hex_tuple = (next_hex.q, next_hex.r, next_hex.s)
                
                if hex_tuple not in visited:
                    visited.add(hex_tuple)
                    
                    # Don't include starting position
                    if hex_tuple != (self.hex_coordinates.q, self.hex_coordinates.r, self.hex_coordinates.s):
                        valid_moves.append(next_hex)
                    
                    # Continue searching from here
                    queue.append(next_hex)
        
        return valid_moves

    def can_move_to(self, target: HexCoordinate, game_state) -> bool:
        valid_moves = self.get_valid_moves(game_state)
        for move in valid_moves:
            if move.q == target.q and move.r == target.r and move.s == target.s: # check the move is in valid moves
                return True
        return False
    
class Beetle(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🪲",
            location='offboard'
            )
    def get_valid_moves(self, game_state):
        if self.location != 'board':
            return []
        
        if self.is_pinned():
            return []
        
        # Check if moving this piece would break the hive
        if not MovementHelper.hive_stays_connected(self.piece_id, game_state):
            # If beetle can't move without breaking hive, it can still climb
            # on adjacent pieces (since climbing doesn't remove it from hive)
            valid_moves = []
            occupied = MovementHelper.get_occupied_spaces(game_state, exclude_piece_id=self.piece_id, ground_level_only=False)
            for adj in self.hex_coordinates.get_adjacent_hexes():
                adj_coords = (adj.q, adj.r, adj.s)
                if adj_coords in occupied:
                    valid_moves.append(adj) # can climb on top of other pieces
            return valid_moves
        
        valid_moves = []
        occupied = MovementHelper.get_occupied_spaces(game_state, exclude_piece_id=self.piece_id, ground_level_only=False)

        for adj in self.hex_coordinates.get_adjacent_hexes():
            adj_coords = (adj.q, adj.r, adj.s)
            if adj_coords in occupied:
                valid_moves.append(adj) # can climb on top of other pieces
            else:
                # check freedom of movement for sliding onto empty hex
                if game_state.check_freedom_of_movement(self.hex_coordinates, adj, self.piece_id):
                    valid_moves.append(adj)

        return valid_moves

    def can_move_to(self, target: HexCoordinate, game_state) -> bool:
        valid_moves = self.get_valid_moves(game_state)
        for move in valid_moves:
            if move.q == target.q and move.r == target.r and move.s == target.s: # check the move is in valid moves
                return True
        return False

class Grasshopper(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🦗",
            location='offboard'
            )
    
    def get_valid_moves(self, game_state):
        if self.location != 'board':
            return []

        if self.is_pinned():
            return []

        # Check if moving this piece would break the hive
        if not MovementHelper.hive_stays_connected(self.piece_id, game_state):
            return []

        valid_moves = []
        directions = [(1, -1, 0), (1, 0, -1), (0, 1, -1), (-1, 1, 0), (-1, 0, 1), (0, -1, 1)]
        occupied = MovementHelper.get_occupied_spaces(game_state, exclude_piece_id=self.piece_id)

        for dq, dr, ds in directions:
            next_hex = HexCoordinate(
                q=self.hex_coordinates.q + dq,
                r=self.hex_coordinates.r + dr,
                s=self.hex_coordinates.s + ds
            )
            jumped = False

            while (next_hex.q, next_hex.r, next_hex.s) in occupied:
                jumped = True
                next_hex = HexCoordinate(
                    q=next_hex.q + dq,
                    r=next_hex.r + dr,
                    s=next_hex.s + ds
                )

            if jumped:
                valid_moves.append(next_hex)

        return valid_moves

    def can_move_to(self, target: HexCoordinate, game_state) -> bool:
        valid_moves = self.get_valid_moves(game_state)
        for move in valid_moves:
            if move.q == target.q and move.r == target.r and move.s == target.s: # check the move is in valid moves
                return True
        return False

class QueenBee(GamePiece):
    def __init__(self, hex_coordinates=None, team: str = 'white'):
        super().__init__(
            hex_coordinates=hex_coordinates, 
            team=team,
            icon="🐝",
            location='offboard'
            )
    def get_valid_moves(self, game_state) -> List[HexCoordinate]:
        if self.location != 'board':
            return []

        if self.is_pinned():
            return []

        if not MovementHelper.hive_stays_connected(self.piece_id, game_state):
            return [] # cannot move if it breaks the hive
        
        # queen can move one space to any adjacent unoccupied hex that 
        # maintains hive integrity and freedom of movement
        occupied = MovementHelper.get_occupied_spaces(game_state, exclude_piece_id=self.piece_id)
        valid_moves = []

        for adj in self.hex_coordinates.get_adjacent_hexes():
            adj_coords = (adj.q, adj.r, adj.s)
            if adj_coords in occupied:
                continue # occupied

            # check freedom of movement
            if not game_state.check_freedom_of_movement(self.hex_coordinates, adj, self.piece_id):
                continue

            # # check hive integrity
            # original_coords = self.hex_coordinates
            # self.hex_coordinates = adj
            # if not MovementHelper.hive_stays_connected(self.piece_id, game_state):
            #     self.hex_coordinates = original_coords
            #     continue
            # self.hex_coordinates = original_coords

            valid_moves.append(adj)
        return valid_moves

    def can_move_to(self, target: HexCoordinate, game_state) -> bool:
        valid_moves = self.get_valid_moves(game_state)
        for move in valid_moves:
            if move.q == target.q and move.r == target.r and move.s == target.s: # check the move is in valid moves
                return True
        return False

    def get_movement_range(self) -> int:
        return 1 # though i dont think this is needed anywhere
    
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

class MovementHelper:

    @staticmethod
    def are_hexes_adjacent(hex1: HexCoordinate, hex2: HexCoordinate) -> bool:
        """Check if two hexes are adjacent to each other."""
        # Manhattan distance of 2
        distance = abs(hex1.q - hex2.q) + abs(hex1.r - hex2.r) + abs(hex1.s - hex2.s)
        return distance == 2

    @staticmethod
    def get_path(game_state: 'GameState', start: HexCoordinate, end: HexCoordinate, piece_id: str) -> Optional[List[HexCoordinate]]:

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
        for pid, piece in game_state.board_state.pieces.items():
            if pid != piece_id and piece.location == 'board':
                occupied.add((piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s))
        
        while open_set:
            _, _, current, path = heapq.heappop(open_set)
            
            # Check if we reached the goal
            if current.q == end.q and current.r == end.r and current.s == end.s:
                return path
            
            # Explore neighbors
            for next_hex in game_state.get_valid_slide_positions(current, occupied):
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
    
    @staticmethod
    def get_occupied_spaces(game_state: 'GameState', exclude_piece_id: Optional[str] = None, ground_level_only: bool = True) -> Set[Tuple[int, int, int]]:
        """Get all occupied spaces on the board, optionally excluding a specific piece."""
        occupied = set()
        for pid, piece in game_state.board_state.pieces.items():
            if pid != exclude_piece_id and piece.location == 'board':
                if ground_level_only or piece.z_level == 0:
                    occupied.add((piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s))
        return occupied
    
    @staticmethod
    def can_slide_to_adjacent(from_hex: HexCoordinate, to_hex: HexCoordinate, occupied: Set) -> bool:
        """Check if piece can slide one space (for Queen, Spider, Ant)."""

        # double check path is adjacent
        if not MovementHelper.are_hexes_adjacent(from_hex, to_hex):
            raise ValueError('Hexes are not adjacent')

        # neighbors
        from_neighbors = set([(h.q, h.r, h.s) for h in from_hex.get_adjacent_hexes()])
        to_neighbors = set([(h.q, h.r, h.s) for h in to_hex.get_adjacent_hexes()])

        mutual_neighbors = from_neighbors.intersection(to_neighbors)
        occupied_mutual = mutual_neighbors.intersection(occupied)

        if len(occupied_mutual) >= 2:
            return False # cannot slide through tight gap
        
        return True

    
    @staticmethod
    def get_slide_path(start: HexCoordinate, end: HexCoordinate, game_state: 'GameState', piece_id: str) -> Optional[List[HexCoordinate]]:
        """Find a sliding path around the hive."""
        return MovementHelper.get_path(game_state, start, end, piece_id)
    
    @staticmethod
    def hive_stays_connected(piece_id: str, game_state: 'GameState') -> bool:
        """Check if the hive stays connected after a piece is moved."""
        # BFS or DFS to check if all pieces are still connected without the piece being moved

        # get all pieces on board except the one being moved
        pieces_on_board = {}
        coord_to_pid = {}
        
        for pid, piece in game_state.board_state.pieces.items():
            if piece.location != 'board':
                continue

            if pid == piece_id:
                continue
            
            pieces_on_board[pid] = piece
            coords = (piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s)
            coord_to_pid[coords] = pid
        
        if len(pieces_on_board) <= 1:
            return True  # Can't break a hive of 2 pieces
        
        # BFS to check connectivity
        start_id = next(iter(pieces_on_board.keys()))
        visited = {start_id}
        queue = [start_id]
        
        while queue:
            current_id = queue.pop(0)
            current_piece = pieces_on_board[current_id]
            
            # Check all adjacent hexes
            for adj_hex in current_piece.hex_coordinates.get_adjacent_hexes():
                adj_coords = (adj_hex.q, adj_hex.r, adj_hex.s)
                
                if adj_coords in coord_to_pid:
                    adj_pid = coord_to_pid[adj_coords]
                    if adj_pid not in visited:
                        visited.add(adj_pid)
                        queue.append(adj_pid)
        
        # Hive is connected if we visited all pieces
        return len(visited) == len(pieces_on_board) # ie if we visited every piece, hive is intact

class BoardState(BaseModel):
    pieces: dict = Field(default_factory=dict)
    stacks: Dict[Tuple[int, int, int], List[str]] = Field(default_factory=dict) # key is hex coords, value is list of piece_ids in stack order

    def add_piece(self, piece_id: str, piece: GamePiece, coordinates: HexCoordinate):

        coords_tuple = (coordinates.q, coordinates.r, coordinates.s)

        if coords_tuple in self.stacks:
            bottom_piece_id = self.stacks[coords_tuple][-1]
            bottom_piece = self.pieces[bottom_piece_id]

            piece.hex_coordinates = coordinates
            piece.location = 'board'
            piece.z_level = len(self.stacks[coords_tuple])
            piece.pieces_below = self.stacks[coords_tuple].copy()

            bottom_piece.pieces_above.append(piece_id)
            self.stacks[coords_tuple].append(piece_id)
        else:
            piece.hex_coordinates = coordinates
            piece.location = 'board'
            piece.z_level = 0
            piece.pieces_below = []
            self.stacks[coords_tuple] = [piece_id]

        self.pieces[piece_id] = piece

    def move_piece(self, piece_id: str, piece: GamePiece, new_coordinates: HexCoordinate):
        old_coords = (piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s)
        new_coords = (new_coordinates.q, new_coordinates.r, new_coordinates.s)
        
        # Remove from old stack
        if old_coords in self.stacks:
            self.stacks[old_coords].remove(piece_id)
            if not self.stacks[old_coords]:
                del self.stacks[old_coords]
            
            # Update pieces that were above/below
            for pid in piece.pieces_below:
                below_piece = self.pieces.get(pid)
                if below_piece:
                    below_piece.pieces_above.remove(piece_id)
            
            for pid in piece.pieces_above:
                above_piece = self.pieces.get(pid)
                if above_piece:
                    above_piece.pieces_below.remove(piece_id)
                    # Pieces above drop down
                    above_piece.z_level -= 1
        
        # Add to new location (might be stacking)
        self.add_piece(piece_id, piece, new_coordinates)
    
    def get_top_piece_at(self, coordinates: HexCoordinate) -> Optional[GamePiece]:
        """Get the top piece at a given coordinate."""
        coords_tuple = (coordinates.q, coordinates.r, coordinates.s)
        if coords_tuple in self.stacks and self.stacks[coords_tuple]:
            top_piece_id = self.stacks[coords_tuple][-1]
            return self.pieces.get(top_piece_id)
        return None
        
    def get_piece(self, piece_id: str):
        return self.pieces.get(piece_id, None)
    
class Player(BaseModel):
    name: str
    team: str
    pieces: List[GamePiece] = Field(default_factory=None)

    def __init__(self, name: str, team: str, pieces: Optional[List[GamePiece]] = None):
        if pieces is None:
            pieces = [
                *[Ant(team=team) for _ in range(6)],
                *[Grasshopper(team=team) for _ in range(2)],
                *[Spider(team=team) for _ in range(2)],
                *[Beetle(team=team) for _ in range(2)],
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

    def can_slide_to(self, from_hex: HexCoordinate, to_hex: HexCoordinate, occupied: Set[Tuple[int, int, int]]) -> bool:
        """Check if a piece can slide from one hex to an adjacent hex."""
        return MovementHelper.can_slide_to_adjacent(from_hex, to_hex, occupied)

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
            if not MovementHelper.can_slide_to_adjacent(current, adjacent_hex, occupied):
                continue

            # 3. Check if this position maintains hive connection
            # (must be adjacent to at least one piece after the move)
            has_neighbor = False
            for neighbor_hex in adjacent_hex.get_adjacent_hexes():
                neighbor_coords = (neighbor_hex.q, neighbor_hex.r, neighbor_hex.s)
                if neighbor_coords in occupied:
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
        if MovementHelper.are_hexes_adjacent(start, end):
            return MovementHelper.can_slide_to_adjacent(start, end, occupied) # can slide directly
        
        # use a star pathfinding to see if a path exists
        path = MovementHelper.get_path(self, start, end, piece_id)
        if path is not None:
            return True
        return False

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
    def validate_movement(turn, game_state):
        """Simplified - delegates to piece's own validation."""
        if turn.piece_id is None:
            raise ValueError('Movement requires piece_id')
        
        piece = game_state.all_pieces.get(turn.piece_id)
        if piece is None:
            raise ValueError('Piece not found')
        
        if piece.team != turn.player:
            raise ValueError('Cannot move opponent piece')
        
        if piece.location != 'board':
            raise ValueError('Can only move pieces on the board')
        
        if piece.is_pinned():
            raise ValueError(f'{piece.__class__.__name__} is pinned and cannot move')

        # Check queen placement rule
        queen = game_state.get_queen(turn.player)
        player_turn = game_state.turn // 2 if turn.player == 'white' else (game_state.turn - 1) // 2
        if player_turn >= 4 and queen.location == 'offboard':
            raise ValueError(f'{turn.player.capitalize()} must place Queen by turn 4')
        
        # Delegate to piece's movement validation
        if not piece.can_move_to(turn.target_coordinates, game_state):
            raise ValueError(f'{piece.__class__.__name__} cannot move to that position')
        
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

