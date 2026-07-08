"""Table models."""
from engineering_di.models import CellGraph, Table, TableCell
Cell = TableCell
Row = list[TableCell]
__all__ = ["Table", "TableCell", "Cell", "Row", "CellGraph"]
