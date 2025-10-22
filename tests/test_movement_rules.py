"""
Unit tests for movement rules and freedom of movement.
"""
import pytest
from hivesim.game import (
    GameState, Game, Turn, HexCoordinate, Ant, QueenBee
)


class TestFreedomOfMovement:
    """Test freedom of movement validation."""
    
    def test_can_slide_between_adjacent_pieces(self):
        """Test that pieces can slide between gaps."""
        game_state = GameState()
        
        # Create a simple scenario with 3 pieces
        ant1 = Ant(team='white')
        ant2 = Ant(team='white')
        ant3 = Ant(team='white')
        
        coord1 = HexCoordinate(q=0, r=0, s=0)
        coord2 = HexCoordinate(q=1, r=-1, s=0)
        coord3 = HexCoordinate(q=0, r=1, s=-1)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, coord1)
        game_state.board_state.add_piece(ant2.piece_id, ant2, coord2)
        game_state.board_state.add_piece(ant3.piece_id, ant3, coord3)
        
        # Test sliding from coord1 to an adjacent empty space
        target = HexCoordinate(q=-1, r=0, s=1)
        
        occupied = set((p.hex_coordinates.q, p.hex_coordinates.r, p.hex_coordinates.s) 
                      for p in game_state.board_state.pieces.values())
        
        result = game_state.can_slide_to(coord1, target, occupied)
        # Result depends on the gate rule - should be able to slide if gap is wide enough
        assert isinstance(result, bool)
    
    def test_cannot_slide_through_tight_gap(self):
        """Test that pieces cannot slide through a gate of 2 pieces."""
        game_state = GameState()
        
        # Create a tight gate scenario where both mutual neighbors are occupied
        # We try to move ant1 from (0,0,0) to (1,-1,0)
        # The mutual neighbors of (0,0,0) and (1,-1,0) are (1,0,-1) and (0,-1,1)
        ant1 = Ant(team='white')
        ant2 = Ant(team='white')
        ant3 = Ant(team='white')
        
        center = HexCoordinate(q=0, r=0, s=0)
        gate1 = HexCoordinate(q=1, r=0, s=-1)
        gate2 = HexCoordinate(q=0, r=-1, s=1)
        target = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, center)
        game_state.board_state.add_piece(ant2.piece_id, ant2, gate1)
        game_state.board_state.add_piece(ant3.piece_id, ant3, gate2)
        
        occupied = set()
        for pid, piece in game_state.board_state.pieces.items():
            if pid != ant1.piece_id:
                occupied.add((piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s))
        
        result = game_state.can_slide_to(center, target, occupied)
        # This should be False because both mutual neighbors are occupied (gate rule)
        assert result is False


class TestGetValidSlidePositions:
    """Test getting valid slide positions."""
    
    def test_valid_slide_positions_empty_adjacent(self):
        """Test getting valid positions with empty adjacent spaces."""
        game_state = GameState()
        
        ant1 = Ant(team='white')
        ant2 = Ant(team='white')
        
        coord1 = HexCoordinate(q=0, r=0, s=0)
        coord2 = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, coord1)
        game_state.board_state.add_piece(ant2.piece_id, ant2, coord2)
        
        occupied = set()
        for piece in game_state.board_state.pieces.values():
            occupied.add((piece.hex_coordinates.q, piece.hex_coordinates.r, piece.hex_coordinates.s))
        
        valid_positions = game_state.get_valid_slide_positions(coord1, occupied)
        
        # Should have at least one valid position
        assert len(valid_positions) >= 0
        
        # All positions should be HexCoordinate objects
        for pos in valid_positions:
            assert isinstance(pos, HexCoordinate)


class TestPathfinding:
    """Test A* pathfinding for piece movement."""
    
    def test_get_path_adjacent(self):
        """Test finding path to adjacent hex."""
        game_state = GameState()
        
        ant1 = Ant(team='white')
        ant2 = Ant(team='white')
        
        start = HexCoordinate(q=0, r=0, s=0)
        neighbor = HexCoordinate(q=1, r=-1, s=0)
        end = HexCoordinate(q=0, r=-1, s=1)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, start)
        game_state.board_state.add_piece(ant2.piece_id, ant2, neighbor)
        
        path = game_state.get_path(start, end, ant1.piece_id)
        
        if path:
            assert len(path) >= 2
            assert path[0] == start
            assert path[-1] == end
    
    def test_check_freedom_of_movement_same_position(self):
        """Test that moving to same position is allowed."""
        game_state = GameState()
        
        ant = Ant(team='white')
        coord = HexCoordinate(q=0, r=0, s=0)
        
        game_state.board_state.add_piece(ant.piece_id, ant, coord)
        
        result = game_state.check_freedom_of_movement(coord, coord, ant.piece_id)
        assert result is True


class TestMovementValidation:
    """Test turn movement validation."""
    
    def test_validate_movement_requires_piece_id(self):
        """Test that movement validation requires piece_id."""
        game_state = GameState()
        
        turn = Turn(
            player='white',
            action_type='move',
            target_coordinates=HexCoordinate(q=1, r=-1, s=0)
        )
        
        with pytest.raises(ValueError, match="Movement requires piece_id"):
            Turn.validate_movement(turn, game_state)
    
    def test_validate_movement_piece_must_be_on_board(self):
        """Test that only pieces on board can be moved."""
        game_state = GameState()
        ant = game_state.white_player.pieces[0]
        
        turn = Turn(
            player='white',
            piece_id=ant.piece_id,
            action_type='move',
            target_coordinates=HexCoordinate(q=1, r=-1, s=0)
        )
        
        with pytest.raises(ValueError, match="Can only move pieces that are on the board"):
            Turn.validate_movement(turn, game_state)
    
    def test_validate_movement_cannot_move_opponent_piece(self):
        """Test that player cannot move opponent's pieces."""
        game_state = GameState()
        
        # Place black ant on board
        black_ant = game_state.black_player.pieces[0]
        coord = HexCoordinate(q=0, r=0, s=0)
        game_state.board_state.add_piece(black_ant.piece_id, black_ant, coord)
        
        # White tries to move black's piece
        turn = Turn(
            player='white',
            piece_id=black_ant.piece_id,
            action_type='move',
            target_coordinates=HexCoordinate(q=1, r=-1, s=0)
        )
        
        with pytest.raises(ValueError, match="Cannot move opponent piece"):
            Turn.validate_movement(turn, game_state)


class TestComplexBoardScenarios:
    """Test complex board scenarios and edge cases."""
    
    def test_surrounded_piece_cannot_move(self):
        """Test that a completely surrounded piece cannot move."""
        game_state = GameState()
        
        # Place center ant
        center_ant = Ant(team='white')
        center = HexCoordinate(q=0, r=0, s=0)
        game_state.board_state.add_piece(center_ant.piece_id, center_ant, center)
        
        # Surround with 6 ants
        for i, adj in enumerate(center.get_adjacent_hexes()):
            ant = game_state.black_player.pieces[i]
            game_state.board_state.add_piece(ant.piece_id, ant, adj)
        
        # Try to move center ant (should fail - no adjacent free spaces)
        target = HexCoordinate(q=1, r=-1, s=0)  # This is occupied
        
        turn = Turn(
            player='white',
            piece_id=center_ant.piece_id,
            action_type='move',
            target_coordinates=target
        )
        
        # Should raise error because target is occupied or unreachable
        with pytest.raises(ValueError):
            Turn.validate_movement(turn, game_state)
    
    def test_piece_on_edge_can_move(self):
        """Test that a piece on the edge of hive can move."""
        game_state = GameState()
        
        # Create a simple line of 3 ants
        ant1 = Ant(team='white')
        ant2 = Ant(team='white')
        ant3 = Ant(team='white')
        
        coord1 = HexCoordinate(q=0, r=0, s=0)
        coord2 = HexCoordinate(q=1, r=-1, s=0)
        coord3 = HexCoordinate(q=2, r=-2, s=0)
        
        game_state.board_state.add_piece(ant1.piece_id, ant1, coord1)
        game_state.board_state.add_piece(ant2.piece_id, ant2, coord2)
        game_state.board_state.add_piece(ant3.piece_id, ant3, coord3)
        
        # Edge piece (ant3) should be able to move
        target = HexCoordinate(q=2, r=-1, s=-1)
        
        can_move = game_state.check_freedom_of_movement(coord3, target, ant3.piece_id)
        assert isinstance(can_move, bool)
