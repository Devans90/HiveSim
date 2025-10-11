# Hexagonal grid coordinate system
# pointy top hex coordinates system

import unittest
from pydantic import BaseModel
from ast import Tuple


class HexCoordinate(BaseModel):
    q: int
    r: int
    s: int


if __name__ == "__main__":
    # Example usage
    # check if two coordinates are adjacent

    # example 1. adjacent
    coord1 = HexCoordinate(1, -1, 0)
    coord2 = HexCoordinate(2, 3, -5)

