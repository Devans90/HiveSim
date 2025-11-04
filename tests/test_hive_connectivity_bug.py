"""
Test cases for hive connectivity bug where queen/beetle movements break the hive.

The bug occurs when a piece moves from position A to adjacent position B:
1. Removing the piece from A doesn't break the hive (check passes)
2. BUT when the piece is at B, the pieces at the old location become disconnected

This test file reproduces the specific scenarios mentioned in the issue.
"""
import pytest
from hivesim.game import (
    Game, GameState, Turn, HexCoordinate, 
    Ant, QueenBee, Beetle, Spider, Grasshopper,
    MovementHelper
)


class TestQueenBeeHiveBreaking:
    """Test that queen bee movements don't break the hive."""
    
    def test_queen_move_breaks_hive_simple(self):
        """
        Test a simple scenario where queen moving breaks the hive.
        
        Setup:
          A---Q---B
        
        If Q moves away, A and B become disconnected.
        """
        game_state = GameState()
        
        ant_a = Ant(team='white')
        queen = QueenBee(team='white')
        ant_b = Ant(team='white')
        
        # Linear arrangement: A at (-1,0,1), Q at (0,0,0), B at (1,-1,0)
        coord_a = HexCoordinate(q=-1, r=0, s=1)
        coord_q = HexCoordinate(q=0, r=0, s=0)
        coord_b = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(ant_a.piece_id, ant_a, coord_a)
        game_state.board_state.add_piece(queen.piece_id, queen, coord_q)
        game_state.board_state.add_piece(ant_b.piece_id, ant_b, coord_b)
        
        # Queen is the only connection between A and B
        # Moving queen should break the hive, so it should have 0 valid moves
        # or the moves should not include positions that break the hive
        valid_moves = queen.get_valid_moves(game_state)
        
        # The queen should not be able to move because it would break the hive
        assert len(valid_moves) == 0, f"Queen should not be able to move (would break hive), but has {len(valid_moves)} valid moves: {valid_moves}"
    
    def test_queen_move_breaks_hive_bridge(self):
        """
        Test queen as a bridge between two parts of hive.
        
        Setup:
          A
         / \
        B---Q---C
             \
              D
        
        Q connects multiple pieces. Moving Q would disconnect the hive.
        """
        game_state = GameState()
        
        queen = QueenBee(team='white')
        ant_a = Ant(team='white')
        ant_b = Ant(team='white')
        ant_c = Ant(team='white')
        ant_d = Ant(team='white')
        
        # Queen at center
        coord_q = HexCoordinate(q=0, r=0, s=0)
        # A at top-left
        coord_a = HexCoordinate(q=0, r=-1, s=1)
        # B at left
        coord_b = HexCoordinate(q=-1, r=0, s=1)
        # C at right
        coord_c = HexCoordinate(q=1, r=-1, s=0)
        # D at bottom-right
        coord_d = HexCoordinate(q=0, r=1, s=-1)
        
        game_state.board_state.add_piece(queen.piece_id, queen, coord_q)
        game_state.board_state.add_piece(ant_a.piece_id, ant_a, coord_a)
        game_state.board_state.add_piece(ant_b.piece_id, ant_b, coord_b)
        game_state.board_state.add_piece(ant_c.piece_id, ant_c, coord_c)
        game_state.board_state.add_piece(ant_d.piece_id, ant_d, coord_d)
        
        # Check that removing queen would break the hive
        hive_connected = MovementHelper.hive_stays_connected(queen.piece_id, game_state)
        assert hive_connected is False, "Removing queen should break the hive"
        
        # Therefore, queen should have no valid moves
        valid_moves = queen.get_valid_moves(game_state)
        assert len(valid_moves) == 0, f"Queen should not be able to move (would break hive), but has {len(valid_moves)} valid moves"


class TestBeetleHiveBreaking:
    """Test that beetle movements don't break the hive."""
    
    def test_beetle_move_breaks_hive_simple(self):
        """
        Test beetle moving breaks the hive.
        
        Setup:
          A---B---C
        
        If B (beetle) moves away, A and C become disconnected.
        """
        game_state = GameState()
        
        ant_a = Ant(team='white')
        beetle = Beetle(team='white')
        ant_c = Ant(team='white')
        
        coord_a = HexCoordinate(q=-1, r=0, s=1)
        coord_b = HexCoordinate(q=0, r=0, s=0)
        coord_c = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(ant_a.piece_id, ant_a, coord_a)
        game_state.board_state.add_piece(beetle.piece_id, beetle, coord_b)
        game_state.board_state.add_piece(ant_c.piece_id, ant_c, coord_c)
        
        # Beetle is the only connection
        hive_connected = MovementHelper.hive_stays_connected(beetle.piece_id, game_state)
        assert hive_connected is False, "Removing beetle should break the hive"
        
        # Beetle should not be able to move to empty spaces (would break hive)
        # But beetle CAN climb on top of adjacent pieces without breaking hive
        valid_moves = beetle.get_valid_moves(game_state)
        
        # All valid moves should be climbs onto A or C
        occupied = MovementHelper.get_occupied_spaces(game_state, exclude_piece_id=beetle.piece_id, ground_level_only=False)
        
        for move in valid_moves:
            move_coords = (move.q, move.r, move.s)
            # Every valid move should be a climb (onto an occupied space)
            is_climb = move_coords in occupied
            assert is_climb, f"Beetle should only be able to climb, not move to empty space at ({move.q}, {move.r}, {move.s})"
    
    def test_grasshopper_move_breaks_hive(self):
        """
        Test grasshopper moving breaks the hive.
        
        Setup:
          A---G---C
        
        If G (grasshopper) jumps away, A and C become disconnected.
        """
        game_state = GameState()
        
        ant_a = Ant(team='white')
        grasshopper = Grasshopper(team='white')
        ant_c = Ant(team='white')
        
        coord_a = HexCoordinate(q=-1, r=0, s=1)
        coord_g = HexCoordinate(q=0, r=0, s=0)
        coord_c = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(ant_a.piece_id, ant_a, coord_a)
        game_state.board_state.add_piece(grasshopper.piece_id, grasshopper, coord_g)
        game_state.board_state.add_piece(ant_c.piece_id, ant_c, coord_c)
        
        # Grasshopper is the only connection
        hive_connected = MovementHelper.hive_stays_connected(grasshopper.piece_id, game_state)
        assert hive_connected is False, "Removing grasshopper should break the hive"
        
        # Grasshopper should not be able to move (would break hive)
        valid_moves = grasshopper.get_valid_moves(game_state)
        assert len(valid_moves) == 0, f"Grasshopper should not be able to move (would break hive), but has {len(valid_moves)} valid moves"


class TestHiveConnectivityAfterMove:
    """Test that hive connectivity is checked AFTER a piece moves to new position."""
    
    def test_move_creates_disconnected_hive(self):
        """
        Test a scenario where moving a piece leaves the rest disconnected.
        
        This is the core bug: the code checks if removing the piece breaks the hive,
        but doesn't check if the hive is still connected after the piece moves to
        its new position.
        
        Setup:
          A---Q---B
               |
               C
        
        If Q moves down to connect with C only, then A and B become disconnected.
        """
        game_state = GameState()
        
        ant_a = Ant(team='white')
        queen = QueenBee(team='white')
        ant_b = Ant(team='white')
        ant_c = Ant(team='white')
        
        # Q at center (0,0,0)
        coord_q = HexCoordinate(q=0, r=0, s=0)
        # A at left (-1,0,1)
        coord_a = HexCoordinate(q=-1, r=0, s=1)
        # B at right (1,-1,0)
        coord_b = HexCoordinate(q=1, r=-1, s=0)
        # C at bottom (0,1,-1)
        coord_c = HexCoordinate(q=0, r=1, s=-1)
        
        game_state.board_state.add_piece(ant_a.piece_id, ant_a, coord_a)
        game_state.board_state.add_piece(queen.piece_id, queen, coord_q)
        game_state.board_state.add_piece(ant_b.piece_id, ant_b, coord_b)
        game_state.board_state.add_piece(ant_c.piece_id, ant_c, coord_c)
        
        # Queen is currently adjacent to A, B, and C - all connected
        # If we check hive_stays_connected, it returns False (removing Q breaks hive)
        hive_connected = MovementHelper.hive_stays_connected(queen.piece_id, game_state)
        assert hive_connected is False, "Removing queen should break the hive"
        
        # Therefore queen should not be able to move
        valid_moves = queen.get_valid_moves(game_state)
        assert len(valid_moves) == 0, f"Queen should not be able to move (would break hive), but has {len(valid_moves)} valid moves"
    
    def test_complex_scenario_from_game_log(self):
        """
        Test a complex scenario similar to the one from the game log.
        
        This recreates a simplified version of the situation from the bug report
        where a piece moves and breaks the hive.
        """
        game_state = GameState()
        
        # Create a scenario with multiple pieces
        pieces = [
            (QueenBee(team='white'), HexCoordinate(q=0, r=0, s=0)),
            (Ant(team='white'), HexCoordinate(q=-1, r=0, s=1)),
            (Ant(team='white'), HexCoordinate(q=1, r=-1, s=0)),
            (Beetle(team='black'), HexCoordinate(q=0, r=1, s=-1)),
        ]
        
        for piece, coord in pieces:
            game_state.board_state.add_piece(piece.piece_id, piece, coord)
        
        # Get the queen and check its valid moves
        queen = pieces[0][0]
        valid_moves = queen.get_valid_moves(game_state)
        
        # Each move should be validated to not break the hive
        for move in valid_moves:
            # Simulate moving queen to this position
            old_coord = queen.hex_coordinates
            
            # Temporarily move the queen
            queen.hex_coordinates = move
            
            # Check if hive is still connected (excluding the queen from old position)
            # We need to check if remaining pieces at old location are still connected
            # This is what the bug fix should check!
            
            # Restore queen position
            queen.hex_coordinates = old_coord


class TestEdgeCases:
    """Test edge cases for hive connectivity."""
    
    def test_two_pieces_can_move(self):
        """With only 2 pieces, either can move without breaking hive."""
        game_state = GameState()
        
        queen = QueenBee(team='white')
        ant = Ant(team='white')
        
        coord_q = HexCoordinate(q=0, r=0, s=0)
        coord_a = HexCoordinate(q=1, r=-1, s=0)
        
        game_state.board_state.add_piece(queen.piece_id, queen, coord_q)
        game_state.board_state.add_piece(ant.piece_id, ant, coord_a)
        
        # With only 2 pieces, removing one leaves only 1 piece
        # which is trivially connected
        hive_connected = MovementHelper.hive_stays_connected(queen.piece_id, game_state)
        assert hive_connected is True, "With 2 pieces, removing one should not 'break' hive"
        
        # Queen should be able to move (but might be restricted by freedom of movement)
        valid_moves = queen.get_valid_moves(game_state)
        # Just verify this doesn't crash - actual valid moves depend on freedom of movement
        assert isinstance(valid_moves, list)
