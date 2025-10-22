"""
Unit tests for interesting board states and game mechanics.
"""
import pytest
from hivesim.game import (
    BoardState, GameState, Game, Player, Turn,
    HexCoordinate, Ant, QueenBee, Beetle
)


class TestBoardState:
    """Test BoardState operations."""
    
    def test_empty_board(self):
        """Test creating an empty board."""
        board = BoardState()
        assert len(board.pieces) == 0
    
    def test_add_piece(self):
        """Test adding a piece to the board."""
        board = BoardState()
        ant = Ant(team='white')
        coord = HexCoordinate(q=0, r=0, s=0)
        
        board.add_piece(ant.piece_id, ant, coord)
        
        assert len(board.pieces) == 1
        assert ant.hex_coordinates == coord
        assert ant.location == 'board'
    
    def test_move_piece(self):
        """Test moving a piece on the board."""
        board = BoardState()
        ant = Ant(team='white')
        start = HexCoordinate(q=0, r=0, s=0)
        end = HexCoordinate(q=1, r=-1, s=0)
        
        board.add_piece(ant.piece_id, ant, start)
        board.move_piece(ant.piece_id, ant, end)
        
        assert ant.hex_coordinates == end


class TestGameState:
    """Test GameState operations and rules."""
    
    def test_game_state_initialization(self):
        """Test creating a new game state."""
        game_state = GameState()
        assert game_state.turn == 0
        assert game_state.current_team == 'white'
        assert len(game_state.board_state.pieces) == 0
    
    def test_get_available_spaces_empty_board(self):
        """Test getting available spaces on empty board."""
        game_state = GameState()
        spaces = game_state.get_available_spaces()
        
        # Empty board should return origin
        assert len(spaces) == 1
        assert spaces[0].q == 0
        assert spaces[0].r == 0
        assert spaces[0].s == 0
    
    def test_get_available_spaces_one_piece(self):
        """Test getting available spaces with one piece on board."""
        game_state = GameState()
        ant = Ant(team='white')
        coord = HexCoordinate(q=0, r=0, s=0)
        
        game_state.board_state.add_piece(ant.piece_id, ant, coord)
        spaces = game_state.get_available_spaces()
        
        # Should have 6 adjacent spaces
        assert len(spaces) == 6
    
    def test_get_occupied_spaces(self):
        """Test getting occupied spaces."""
        game_state = GameState()
        ant1 = Ant(team='white')
        ant2 = Ant(team='black')
        coord1 = HexCoordinate(q=0, r=0, s=0)
        coord2 = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, coord1)
        game_state.board_state.add_piece(ant2.piece_id, ant2, coord2)
        
        occupied = game_state.get_occupied_spaces()
        assert len(occupied) == 2
        assert (0, 0, 0) in occupied
        assert (1, -1, 0) in occupied
    
    def test_are_hexes_adjacent(self):
        """Test checking if two hexes are adjacent."""
        game_state = GameState()
        hex1 = HexCoordinate(q=0, r=0, s=0)
        hex2 = HexCoordinate(q=1, r=-1, s=0)
        hex3 = HexCoordinate(q=2, r=-2, s=0)
        
        # Adjacent hexes
        assert game_state.are_hexes_adjacent(hex1, hex2)
        
        # Non-adjacent hexes
        assert not game_state.are_hexes_adjacent(hex1, hex3)


class TestWinCondition:
    """Test win condition detection."""
    
    def test_queen_surrounded_white_loses(self):
        """Test white loses when queen is surrounded."""
        game_state = GameState()
        
        # Place white queen at origin
        white_queen = game_state.get_queen('white')
        origin = HexCoordinate(q=0, r=0, s=0)
        game_state.board_state.add_piece(white_queen.piece_id, white_queen, origin)
        
        # Surround with black ants
        for i, adj in enumerate(origin.get_adjacent_hexes()):
            ant = game_state.black_player.pieces[i]
            game_state.board_state.add_piece(ant.piece_id, ant, adj)
        
        winner = game_state.check_win_condition()
        assert winner == 'black'
    
    def test_queen_surrounded_black_loses(self):
        """Test black loses when queen is surrounded."""
        game_state = GameState()
        
        # Place black queen at origin
        black_queen = game_state.get_queen('black')
        origin = HexCoordinate(q=0, r=0, s=0)
        game_state.board_state.add_piece(black_queen.piece_id, black_queen, origin)
        
        # Surround with white ants
        for i, adj in enumerate(origin.get_adjacent_hexes()):
            ant = game_state.white_player.pieces[i]
            game_state.board_state.add_piece(ant.piece_id, ant, adj)
        
        winner = game_state.check_win_condition()
        assert winner == 'white'
    
    def test_queen_not_surrounded(self):
        """Test no winner when queen is not fully surrounded."""
        game_state = GameState()
        
        # Place white queen at origin
        white_queen = game_state.get_queen('white')
        origin = HexCoordinate(q=0, r=0, s=0)
        game_state.board_state.add_piece(white_queen.piece_id, white_queen, origin)
        
        # Only surround with 5 ants (leave one space open)
        adjacent = origin.get_adjacent_hexes()
        for i in range(5):
            ant = game_state.black_player.pieces[i]
            game_state.board_state.add_piece(ant.piece_id, ant, adjacent[i])
        
        winner = game_state.check_win_condition()
        assert winner is None


class TestHiveConnectivity:
    """Test hive connectivity rules."""
    
    def test_hive_stays_connected_two_pieces(self):
        """Test that removing one of two pieces breaks the hive."""
        game_state = GameState()
        ant1 = Ant(team='white')
        ant2 = Ant(team='white')
        
        coord1 = HexCoordinate(q=0, r=0, s=0)
        coord2 = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, coord1)
        game_state.board_state.add_piece(ant2.piece_id, ant2, coord2)
        
        # With only 2 pieces, hive would break if we remove either
        # but the function should handle this case gracefully
        result = Turn.hive_stays_connected(ant1.piece_id, game_state)
        assert result is True  # Only one piece left, so hive is trivially connected
    
    def test_hive_stays_connected_three_pieces_line(self):
        """Test hive connectivity with three pieces in a line."""
        game_state = GameState()
        ant1 = Ant(team='white')
        ant2 = Ant(team='white')
        ant3 = Ant(team='white')
        
        coord1 = HexCoordinate(q=0, r=0, s=0)
        coord2 = HexCoordinate(q=1, r=-1, s=0)
        coord3 = HexCoordinate(q=2, r=-2, s=0)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, coord1)
        game_state.board_state.add_piece(ant2.piece_id, ant2, coord2)
        game_state.board_state.add_piece(ant3.piece_id, ant3, coord3)
        
        # Middle piece keeps hive connected
        result = Turn.hive_stays_connected(ant2.piece_id, game_state)
        assert result is False  # Removing middle piece would break hive
        
        # End pieces can be moved
        result1 = Turn.hive_stays_connected(ant1.piece_id, game_state)
        assert result1 is True
        
        result3 = Turn.hive_stays_connected(ant3.piece_id, game_state)
        assert result3 is True


class TestPiecePlacement:
    """Test piece placement rules."""
    
    def test_first_piece_at_origin(self):
        """Test that first piece must be placed at origin."""
        game = Game()
        ant = game.game_state.white_player.pieces[0]
        
        # First piece at origin should work
        turn = Turn(
            player='white',
            piece_id=ant.piece_id,
            action_type='place',
            target_coordinates=HexCoordinate(q=0, r=0, s=0)
        )
        
        validated = Turn.validate_placement(turn, game.game_state)
        assert validated is not None
    
    def test_first_piece_not_at_origin_fails(self):
        """Test that first piece not at origin fails."""
        game = Game()
        ant = game.game_state.white_player.pieces[0]
        
        # First piece not at origin should fail
        turn = Turn(
            player='white',
            piece_id=ant.piece_id,
            action_type='place',
            target_coordinates=HexCoordinate(q=1, r=-1, s=0)
        )
        
        with pytest.raises(ValueError, match="First piece must be placed at the center"):
            Turn.validate_placement(turn, game.game_state)
    
    def test_piece_adjacent_to_own_pieces(self):
        """Test that pieces must be placed adjacent to own pieces."""
        game = Game()
        
        # Place first white piece
        ant1 = game.game_state.white_player.pieces[0]
        turn1 = Turn(
            player='white',
            piece_id=ant1.piece_id,
            action_type='place',
            target_coordinates=HexCoordinate(q=0, r=0, s=0)
        )
        game.apply_turn(turn1)
        
        # Place first black piece (away from white)
        ant2 = game.game_state.black_player.pieces[0]
        turn2 = Turn(
            player='black',
            piece_id=ant2.piece_id,
            action_type='place',
            target_coordinates=HexCoordinate(q=1, r=-1, s=0)
        )
        game.apply_turn(turn2)
        
        # White tries to place next to white but not touching black (should work)
        # (0, -1, 1) is adjacent to (0, 0, 0) but also to (1, -1, 0), so pick a different spot
        ant3 = game.game_state.white_player.pieces[1]
        turn3 = Turn(
            player='white',
            piece_id=ant3.piece_id,
            action_type='place',
            target_coordinates=HexCoordinate(q=-1, r=0, s=1)  # Adjacent to white only
        )
        validated = Turn.validate_placement(turn3, game.game_state)
        assert validated is not None


class TestQueenPlacementRule:
    """Test the rule that queen must be placed by turn 4."""
    
    def test_queen_can_be_placed_early(self):
        """Test that queen can be placed on first turn."""
        game = Game()
        queen = game.game_state.get_queen('white')
        
        turn = Turn(
            player='white',
            piece_type='queenbee',
            action_type='place',
            target_coordinates=HexCoordinate(q=0, r=0, s=0)
        )
        
        validated = Turn.validate_placement(turn, game.game_state)
        assert validated is not None
        assert validated.piece_id == queen.piece_id
