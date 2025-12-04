"""
Gymnasium-compatible environment for HiveSim reinforcement learning.

This module provides a standardized RL interface for training agents
to play the Hive board game.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from hivesim.game import (
    Game, GameState, Turn, HexCoordinate, 
    Ant, Beetle, Spider, Grasshopper, QueenBee, Ladybug, Mosquito,
    MovementHelper
)


# Piece type to integer mapping for encoding
PIECE_TYPE_MAP = {
    'ant': 1,
    'beetle': 2,
    'spider': 3,
    'grasshopper': 4,
    'queenbee': 5,
    'ladybug': 6,
    'mosquito': 7,
}

PIECE_CLASS_MAP = {
    Ant: 'ant',
    Beetle: 'beetle',
    Spider: 'spider',
    Grasshopper: 'grasshopper',
    QueenBee: 'queenbee',
    Ladybug: 'ladybug',
    Mosquito: 'mosquito',
}

# Piece types available for placement (matching Player initialization)
PLACEABLE_PIECE_TYPES = ['ant', 'grasshopper', 'spider', 'beetle', 'queenbee']


class HiveEnv(gym.Env):
    """
    Gymnasium environment for the Hive board game.
    
    The environment supports two-player turn-based gameplay where the agent
    plays as one team (configurable) against an opponent.
    
    Observation Space:
        A dictionary containing:
        - 'board': (2 * grid_size + 1, 2 * grid_size + 1, num_channels) tensor
          encoding piece positions, types, and teams
        - 'turn_info': (4,) array with [turn_number, current_team, white_queen_placed, black_queen_placed]
        - 'action_mask': (num_actions,) boolean array of legal actions
        
    Action Space:
        Discrete space encoding all possible actions:
        - Placement actions: piece_type × grid_positions
        - Movement actions: piece_id × grid_positions (simplified)
        
    Rewards:
        - +1.0 for winning
        - -1.0 for losing
        - 0.0 for draw (max turns reached)
        - Small intermediate rewards for strategic positions (optional)
    """
    
    metadata = {"render_modes": ["human", "ansi"], "name": "HiveEnv-v0"}
    
    def __init__(
        self,
        agent_team: str = 'white',
        opponent: Optional[Any] = None,
        grid_size: int = 10,
        max_turns: int = 200,
        render_mode: Optional[str] = None,
        reward_shaping: bool = False,
    ):
        """
        Initialize the Hive environment.
        
        Args:
            agent_team: Which team the agent plays ('white' or 'black')
            opponent: Optional opponent bot for self-play or evaluation.
                     If None, environment expects external opponent moves.
            grid_size: Half-size of the observation grid (total = 2*grid_size+1)
            max_turns: Maximum turns before game ends in draw
            render_mode: Rendering mode ('human', 'ansi', or None)
            reward_shaping: Whether to include intermediate rewards
        """
        super().__init__()
        
        self.agent_team = agent_team
        self.opponent = opponent
        self.grid_size = grid_size
        self.max_turns = max_turns
        self.render_mode = render_mode
        self.reward_shaping = reward_shaping
        
        # Grid dimensions
        self.grid_dim = 2 * grid_size + 1
        
        # Maximum stack height (beetles can stack on pieces)
        # In practice, stacks rarely exceed 3-4 pieces
        self.max_stack_height = 5
        
        # Observation channels per stack level:
        # 0: piece type (0=empty, 1-7=piece types) - type > 0 implies piece exists
        # 1: team (0=empty, 1=white, 2=black)
        # 2: can move (1 if piece can legally move, only meaningful for top piece)
        # 
        # Total channels = 3 channels × max_stack_height levels
        self.channels_per_level = 3
        self.num_channels = self.channels_per_level * self.max_stack_height
        
        # Define observation space
        self.observation_space = spaces.Dict({
            'board': spaces.Box(
                low=0,
                high=10,
                shape=(self.grid_dim, self.grid_dim, self.num_channels),
                dtype=np.float32
            ),
            'turn_info': spaces.Box(
                low=0,
                high=max_turns,
                shape=(4,),
                dtype=np.float32
            ),
            'action_mask': spaces.Box(
                low=0,
                high=1,
                shape=(self._get_action_space_size(),),
                dtype=np.int8
            ),
        })
        
        # Define action space
        # Actions are: (action_type, piece_type_or_id_index, target_grid_index)
        # Simplified: we use a flat discrete space
        self.action_space = spaces.Discrete(self._get_action_space_size())
        
        # Game instance
        self.game: Optional[Game] = None
        self._legal_actions: List[Turn] = []
        self._action_to_turn_map: Dict[int, Turn] = {}
    # Maximum action space size constant
    # This is computed as: placement actions + movement actions
    # Placements: 5 piece types × potential grid positions (realistically ~100 positions used)
    # Movements: ~13 pieces × ~100 potential destinations each
    # We use a generous upper bound to ensure all legal actions fit
    MAX_ACTION_SPACE_SIZE = 5000
        
    def _get_action_space_size(self) -> int:
        """
        Get the action space size.
        
        We use a fixed upper bound and mask illegal actions at each step.
        This approach is standard for games with variable legal action counts.
        
        The actual number of legal actions varies greatly:
        - Early game: ~5-20 placement actions
        - Mid game: ~50-200 placement + movement actions
        - Complex positions: potentially 500+ legal moves
        
        Using a fixed upper bound with masking allows consistent network architecture
        while still supporting all possible game states.
        """
        return self.MAX_ACTION_SPACE_SIZE
    
    def _hex_to_grid(self, coord: HexCoordinate) -> Tuple[int, int]:
        """
        Convert hex cube coordinate to 2D grid indices using axial projection.
        
        Hive uses cube coordinates (q, r, s) where q + r + s = 0.
        Since s is derived from q and r, we can use axial coordinates (q, r)
        which map directly to a 2D grid. This is a standard technique for
        representing hex grids in rectangular arrays.
        
        The grid is centered at (grid_size, grid_size) so the origin hex (0,0,0)
        maps to the center of the array.
        
        Args:
            coord: HexCoordinate with q, r, s values
            
        Returns:
            (x, y) tuple of grid indices
        """
        x = coord.q + self.grid_size
        y = coord.r + self.grid_size
        return (x, y)
    
    def _grid_to_hex(self, x: int, y: int) -> HexCoordinate:
        """
        Convert 2D grid indices back to hex cube coordinate.
        
        Args:
            x, y: Grid indices
            
        Returns:
            HexCoordinate with q, r, s values (s = -q - r)
        """
        q = x - self.grid_size
        r = y - self.grid_size
        s = -q - r
        return HexCoordinate(q=q, r=r, s=s)
    
    def _encode_board(self) -> np.ndarray:
        """
        Encode the current board state as a numpy array.
        
        The board is encoded as a 3D tensor where:
        - Dimensions 0,1 are spatial (x, y grid position from hex coordinates)
        - Dimension 2 contains channels for each stack level
        
        For each stack level (0 to max_stack_height-1):
        - Channel 0: piece type (0=empty, 1-7=piece types)
        - Channel 1: team (0=empty, 1=white, 2=black)
        - Channel 2: can move (1 if piece can legally move)
        
        This preserves full stack information - all pieces in a stack are encoded,
        not just the top piece.
        """
        board = np.zeros((self.grid_dim, self.grid_dim, self.num_channels), dtype=np.float32)
        
        if self.game is None:
            return board
            
        game_state = self.game.game_state
        
        for piece_id, piece in game_state.board_state.pieces.items():
            if piece.location != 'board' or piece.hex_coordinates is None:
                continue
                
            x, y = self._hex_to_grid(piece.hex_coordinates)
            
            # Check bounds
            if not (0 <= x < self.grid_dim and 0 <= y < self.grid_dim):
                continue
            
            # Get the z-level for this piece (clamped to max_stack_height)
            z_level = min(piece.z_level, self.max_stack_height - 1)
            
            # Calculate channel offset for this stack level
            channel_offset = z_level * self.channels_per_level
            
            # Encode piece type (non-zero type implies piece exists at this level)
            piece_type = PIECE_TYPE_MAP.get(PIECE_CLASS_MAP.get(type(piece), ''), 0)
            board[x, y, channel_offset + 0] = piece_type
            
            # Encode team
            board[x, y, channel_offset + 1] = 1 if piece.team == 'white' else 2
            
            # Check if piece can move (only top pieces can typically move)
            # A piece can only move if it's not pinned (nothing above it)
            if piece.team == game_state.current_team and not piece.is_pinned():
                try:
                    valid_moves = piece.get_valid_moves(game_state)
                    board[x, y, channel_offset + 2] = 1 if len(valid_moves) > 0 else 0
                except Exception:
                    board[x, y, channel_offset + 2] = 0
        
        return board
    
    def _encode_turn_info(self) -> np.ndarray:
        """Encode turn information."""
        if self.game is None:
            return np.zeros(4, dtype=np.float32)
            
        game_state = self.game.game_state
        
        white_queen = game_state.get_queen('white')
        black_queen = game_state.get_queen('black')
        
        return np.array([
            game_state.turn / self.max_turns,  # Normalized turn number
            1 if game_state.current_team == 'white' else 0,
            1 if white_queen and white_queen.location == 'board' else 0,
            1 if black_queen and black_queen.location == 'board' else 0,
        ], dtype=np.float32)
    
    def _get_legal_actions(self) -> List[Turn]:
        """Get all legal actions for the current player."""
        if self.game is None:
            return []
            
        game_state = self.game.game_state
        current_team = game_state.current_team
        legal_actions = []
        
        # Get available placement spaces
        available_spaces = game_state.get_available_spaces()
        
        # Get current player
        player = game_state.white_player if current_team == 'white' else game_state.black_player
        
        # Check if must place queen
        queen = game_state.get_queen(current_team)
        player_turn_number = game_state.turn // 2 if current_team == 'white' else (game_state.turn - 1) // 2
        must_place_queen = queen and queen.location == 'offboard' and player_turn_number >= 3
        
        # Placement actions
        available_pieces = {}
        for piece in player.pieces:
            if piece.location == 'offboard':
                piece_type = PIECE_CLASS_MAP.get(type(piece), '')
                if piece_type not in available_pieces:
                    available_pieces[piece_type] = piece.piece_id
        
        # If must place queen, only allow queen placement
        piece_types_to_try = ['queenbee'] if must_place_queen else list(available_pieces.keys())
        
        for piece_type in piece_types_to_try:
            if piece_type not in available_pieces:
                continue
            piece_id = available_pieces[piece_type]
            
            for space in available_spaces:
                turn = Turn(
                    player=current_team,
                    piece_type=piece_type,
                    piece_id=piece_id,
                    action_type='place',
                    target_coordinates=space
                )
                try:
                    Turn.validate_placement(turn, game_state)
                    legal_actions.append(turn)
                except ValueError:
                    continue
        
        # Movement actions (only if queen is placed and not must_place_queen)
        if not must_place_queen and queen and queen.location == 'board':
            for piece in player.pieces:
                if piece.location != 'board':
                    continue
                    
                # Check if piece can move (not pinned, won't break hive)
                if piece.is_pinned():
                    continue
                if not MovementHelper.hive_stays_connected(piece.piece_id, game_state):
                    continue
                    
                valid_moves = piece.get_valid_moves(game_state)
                for target in valid_moves:
                    turn = Turn(
                        player=current_team,
                        piece_id=piece.piece_id,
                        action_type='move',
                        target_coordinates=target
                    )
                    legal_actions.append(turn)
        
        return legal_actions
    
    def _build_action_mask(self) -> np.ndarray:
        """Build action mask for legal actions."""
        mask = np.zeros(self.action_space.n, dtype=np.int8)
        
        self._legal_actions = self._get_legal_actions()
        self._action_to_turn_map = {}
        
        for i, turn in enumerate(self._legal_actions):
            if i < self.action_space.n:
                mask[i] = 1
                self._action_to_turn_map[i] = turn
        
        return mask
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Get the current observation."""
        return {
            'board': self._encode_board(),
            'turn_info': self._encode_turn_info(),
            'action_mask': self._build_action_mask(),
        }
    
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """
        Reset the environment to initial state.
        
        Args:
            seed: Random seed for reproducibility
            options: Additional options (unused)
            
        Returns:
            observation: Initial observation
            info: Additional information
        """
        super().reset(seed=seed)
        
        # Create new game
        self.game = Game(game_state=GameState(verbose=False))
        
        # If agent plays black and opponent exists, let opponent move first
        if self.agent_team == 'black' and self.opponent is not None:
            opponent_turn = self.opponent.get_move(self.game.game_state)
            self.game.apply_turn(opponent_turn)
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, info
    
    def step(
        self,
        action: int,
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.
        
        Args:
            action: Action index from the action space
            
        Returns:
            observation: New observation
            reward: Reward for the action
            terminated: Whether the episode ended (win/loss)
            truncated: Whether the episode was truncated (max turns)
            info: Additional information
        """
        if self.game is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        # Get the turn corresponding to the action
        if action not in self._action_to_turn_map:
            # Invalid action - return negative reward and same state
            return self._get_observation(), -0.1, False, False, self._get_info()
        
        turn = self._action_to_turn_map[action]
        
        # Apply the agent's action
        try:
            self.game.apply_turn(turn)
        except ValueError as e:
            # Invalid move - should not happen if action mask is correct
            return self._get_observation(), -0.1, False, False, {'error': str(e)}
        
        # Check for game end
        winner = self.game.game_state.check_win_condition()
        if winner:
            reward = 1.0 if winner == self.agent_team else -1.0
            return self._get_observation(), reward, True, False, self._get_info()
        
        # Check for max turns
        if self.game.game_state.turn >= self.max_turns:
            return self._get_observation(), 0.0, False, True, self._get_info()
        
        # Opponent's turn (if opponent is provided)
        if self.opponent is not None:
            opponent_turn = self.opponent.get_move(self.game.game_state)
            
            if opponent_turn.action_type == 'forfeit':
                # Opponent forfeits - agent wins
                return self._get_observation(), 1.0, True, False, self._get_info()
            
            try:
                self.game.apply_turn(opponent_turn)
            except ValueError as e:
                # Opponent made invalid move - treat as forfeit
                return self._get_observation(), 1.0, True, False, {'opponent_error': str(e)}
            
            # Check for game end after opponent's move
            winner = self.game.game_state.check_win_condition()
            if winner:
                reward = 1.0 if winner == self.agent_team else -1.0
                return self._get_observation(), reward, True, False, self._get_info()
            
            # Check for max turns
            if self.game.game_state.turn >= self.max_turns:
                return self._get_observation(), 0.0, False, True, self._get_info()
        
        # Calculate intermediate reward if enabled
        reward = 0.0
        if self.reward_shaping:
            reward = self._calculate_shaped_reward()
        
        observation = self._get_observation()
        info = self._get_info()
        
        return observation, reward, False, False, info
    
    def _calculate_shaped_reward(self) -> float:
        """Calculate shaped reward based on board position."""
        if self.game is None:
            return 0.0
            
        game_state = self.game.game_state
        reward = 0.0
        
        # Reward for surrounding opponent's queen
        opponent_team = 'black' if self.agent_team == 'white' else 'white'
        opponent_queen = game_state.get_queen(opponent_team)
        if opponent_queen and opponent_queen.location == 'board':
            adjacent = opponent_queen.hex_coordinates.get_adjacent_hexes()
            occupied = set(game_state.get_occupied_spaces())
            num_surrounded = sum(1 for adj in adjacent if (adj.q, adj.r, adj.s) in occupied)
            reward += 0.01 * num_surrounded
        
        # Penalty for own queen being surrounded
        own_queen = game_state.get_queen(self.agent_team)
        if own_queen and own_queen.location == 'board':
            adjacent = own_queen.hex_coordinates.get_adjacent_hexes()
            occupied = set(game_state.get_occupied_spaces())
            num_surrounded = sum(1 for adj in adjacent if (adj.q, adj.r, adj.s) in occupied)
            reward -= 0.01 * num_surrounded
        
        return reward
    
    def _get_info(self) -> Dict[str, Any]:
        """Get additional information about the current state."""
        if self.game is None:
            return {}
            
        game_state = self.game.game_state
        
        return {
            'turn': game_state.turn,
            'current_team': game_state.current_team,
            'num_legal_actions': len(self._legal_actions),
            'pieces_on_board': len(game_state.board_state.pieces),
        }
    
    def render(self) -> Optional[str]:
        """Render the current state."""
        if self.render_mode == 'ansi':
            return self._render_ansi()
        elif self.render_mode == 'human':
            self._render_human()
            return None
        return None
    
    def _render_ansi(self) -> str:
        """Render as ASCII text."""
        if self.game is None:
            return "Game not started"
            
        game_state = self.game.game_state
        lines = [f"Turn: {game_state.turn}, Current: {game_state.current_team}"]
        lines.append(f"Pieces on board: {len(game_state.board_state.pieces)}")
        lines.append(f"Legal actions: {len(self._legal_actions)}")
        
        # Simple board representation
        for piece_id, piece in game_state.board_state.pieces.items():
            if piece.location == 'board' and piece.hex_coordinates:
                coord = piece.hex_coordinates
                lines.append(f"  {piece.icon} ({piece.team}) at ({coord.q},{coord.r},{coord.s})")
        
        return '\n'.join(lines)
    
    def _render_human(self) -> None:
        """Render using plotly visualization."""
        if self.game is None:
            return
            
        from hivesim.visualization import visualize_game_board
        visualize_game_board(
            self.game.game_state.board_state,
            show_empty_hexes=self.game.game_state.get_available_spaces(),
            turn_number=self.game.game_state.turn,
        )
    
    def get_legal_actions(self) -> List[int]:
        """Get list of legal action indices."""
        return list(self._action_to_turn_map.keys())
    
    def action_to_turn(self, action: int) -> Optional[Turn]:
        """Convert action index to Turn object."""
        return self._action_to_turn_map.get(action)
    
    def close(self) -> None:
        """Clean up resources."""
        self.game = None
        self._legal_actions = []
        self._action_to_turn_map = {}


def make_hive_env(**kwargs) -> HiveEnv:
    """Factory function to create HiveEnv."""
    return HiveEnv(**kwargs)
