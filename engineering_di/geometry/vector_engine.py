"""Vector utilities for future geometry expansion."""
from engineering_di.models import VectorLine

def horizontal_lines(lines: list[VectorLine]) -> list[VectorLine]:
    return [line for line in lines if line.orientation == "horizontal"]

def vertical_lines(lines: list[VectorLine]) -> list[VectorLine]:
    return [line for line in lines if line.orientation == "vertical"]
