"""
Unit tests for HexCoordinate class and basic hex operations.
"""
import pytest
from hivesim.game import HexCoordinate


class TestHexCoordinate:
    """Test HexCoordinate validation and operations."""
    
    def test_valid_coordinate_creation(self):
        """Test creating valid hex coordinates."""
        coord = HexCoordinate(q=1, r=-1, s=0)
        assert coord.q == 1
        assert coord.r == -1
        assert coord.s == 0
    
    def test_invalid_coordinate_validation(self):
        """Test that invalid coordinates (q+r+s != 0) are rejected."""
        with pytest.raises(ValueError, match="Invalid cube coordinates"):
            HexCoordinate(q=1, r=1, s=1)
    
    def test_origin_coordinate(self):
        """Test the origin coordinate (0,0,0)."""
        origin = HexCoordinate(q=0, r=0, s=0)
        assert origin.q == 0
        assert origin.r == 0
        assert origin.s == 0
    
    def test_get_adjacent_hexes(self):
        """Test getting adjacent hexes for the origin."""
        origin = HexCoordinate(q=0, r=0, s=0)
        adjacent = origin.get_adjacent_hexes()
        
        # Should return 6 adjacent hexes
        assert len(adjacent) == 6
        
        # Verify each adjacent hex is valid
        for adj in adjacent:
            assert adj.q + adj.r + adj.s == 0
        
        # Check specific adjacent coordinates
        expected_coords = [
            (1, -1, 0), (1, 0, -1), (0, 1, -1),
            (-1, 1, 0), (-1, 0, 1), (0, -1, 1)
        ]
        actual_coords = [(h.q, h.r, h.s) for h in adjacent]
        assert set(actual_coords) == set(expected_coords)
    
    def test_adjacent_hexes_for_non_origin(self):
        """Test getting adjacent hexes for a non-origin coordinate."""
        coord = HexCoordinate(q=2, r=-1, s=-1)
        adjacent = coord.get_adjacent_hexes()
        
        # Should return 6 adjacent hexes
        assert len(adjacent) == 6
        
        # Verify each adjacent hex is valid
        for adj in adjacent:
            assert adj.q + adj.r + adj.s == 0
        
        # At least one should be origin + direction from coord
        expected_coords = [
            (3, -2, -1), (3, -1, -2), (2, 0, -2),
            (1, 0, -1), (1, -1, 0), (2, -2, 0)
        ]
        actual_coords = [(h.q, h.r, h.s) for h in adjacent]
        assert set(actual_coords) == set(expected_coords)
