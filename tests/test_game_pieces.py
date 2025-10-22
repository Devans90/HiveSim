"""
Unit tests for different game pieces and their properties.
"""
import pytest
from hivesim.game import (
    GamePiece, Ant, Beetle, Spider, Grasshopper, 
    QueenBee, Ladybug, Mosquito, HexCoordinate
)


class TestGamePieceCreation:
    """Test creating different game piece types."""
    
    def test_ant_creation(self):
        """Test creating an Ant piece."""
        ant = Ant(team='white')
        assert ant.team == 'white'
        assert ant.icon == "🐜"
        assert ant.location == 'offboard'
        assert ant.hex_coordinates is None
    
    def test_beetle_creation(self):
        """Test creating a Beetle piece."""
        beetle = Beetle(team='black')
        assert beetle.team == 'black'
        assert beetle.icon == "🪲"
        assert beetle.location == 'offboard'
    
    def test_spider_creation(self):
        """Test creating a Spider piece."""
        spider = Spider(team='white')
        assert spider.team == 'white'
        assert spider.icon == "🕷️"
        assert spider.location == 'offboard'
    
    def test_grasshopper_creation(self):
        """Test creating a Grasshopper piece."""
        grasshopper = Grasshopper(team='black')
        assert grasshopper.team == 'black'
        assert grasshopper.icon == "🦗"
        assert grasshopper.location == 'offboard'
    
    def test_queenbee_creation(self):
        """Test creating a QueenBee piece."""
        queen = QueenBee(team='white')
        assert queen.team == 'white'
        assert queen.icon == "🐝"
        assert queen.location == 'offboard'
    
    def test_ladybug_creation(self):
        """Test creating a Ladybug piece."""
        ladybug = Ladybug(team='black')
        assert ladybug.team == 'black'
        assert ladybug.icon == "🐞"
        assert ladybug.location == 'offboard'
    
    def test_mosquito_creation(self):
        """Test creating a Mosquito piece."""
        mosquito = Mosquito(team='white')
        assert mosquito.team == 'white'
        assert mosquito.icon == "🦟"
        assert mosquito.location == 'offboard'
    
    def test_invalid_team(self):
        """Test that invalid team names are rejected."""
        with pytest.raises(ValueError, match='Team must be either "black" or "white"'):
            Ant(team='red')
    
    def test_piece_with_coordinates(self):
        """Test creating a piece with initial coordinates."""
        coord = HexCoordinate(q=1, r=-1, s=0)
        ant = Ant(hex_coordinates=coord, team='white')
        assert ant.hex_coordinates == coord
        # Note: location should still be 'offboard' as it's set in __init__


class TestGamePieceMovement:
    """Test that pieces can be moved to different coordinates."""
    
    def test_piece_placement(self):
        """Test placing a piece on the board."""
        ant = Ant(team='white')
        coord = HexCoordinate(q=0, r=0, s=0)
        
        # Initially offboard
        assert ant.location == 'offboard'
        assert ant.hex_coordinates is None
        
        # Place on board
        ant.hex_coordinates = coord
        ant.location = 'board'
        
        assert ant.hex_coordinates == coord
        assert ant.location == 'board'
    
    def test_piece_movement(self):
        """Test moving a piece from one location to another."""
        ant = Ant(team='white')
        start_coord = HexCoordinate(q=0, r=0, s=0)
        end_coord = HexCoordinate(q=1, r=-1, s=0)
        
        # Place on board
        ant.hex_coordinates = start_coord
        ant.location = 'board'
        
        # Move to new location
        ant.hex_coordinates = end_coord
        
        assert ant.hex_coordinates == end_coord
        assert ant.location == 'board'
