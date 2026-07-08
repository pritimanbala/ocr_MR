import unittest

from engineering_di.config import GeometryConfig
from engineering_di.geometry import GeometryEngine
from engineering_di.models import BoundingBox, Page, Token, VectorLine


def horizontal(identifier: str, y: float, x0: float = 0, x1: float = 100) -> VectorLine:
    return VectorLine(
        id=identifier,
        bbox=BoundingBox(x0, y, x1, y),
        page_number=1,
        x0=x0,
        y0=y,
        x1=x1,
        y1=y,
        orientation="horizontal",
    )


def vertical(identifier: str, x: float, y0: float = 0, y1: float = 50) -> VectorLine:
    return VectorLine(
        id=identifier,
        bbox=BoundingBox(x, y0, x, y1),
        page_number=1,
        x0=x,
        y0=y0,
        x1=x,
        y1=y1,
        orientation="vertical",
    )


class GeometryEngineTests(unittest.TestCase):
    def test_reconstructs_cells_and_assigns_tokens_by_overlap(self):
        page = Page(
            number=1,
            bbox=BoundingBox(0, 0, 100, 50),
            rotation=0,
            vector_lines=[
                horizontal("h0", 0),
                horizontal("h1", 25),
                horizontal("h2", 50),
                vertical("v0", 0),
                vertical("v1", 50),
                vertical("v2", 100),
            ],
            tokens=[
                Token(
                    id="word.customer",
                    text="DAT",
                    bbox=BoundingBox(10, 8, 25, 18),
                    page_number=1,
                    source="pymupdf_word",
                ),
                Token(
                    id="word.drawing",
                    text="CE-439790",
                    bbox=BoundingBox(58, 32, 92, 42),
                    page_number=1,
                    source="pymupdf_word",
                ),
            ],
        )

        result = GeometryEngine(GeometryConfig()).reconstruct_page(page)

        self.assertEqual(len(result.cells), 4)
        self.assertEqual(len(result.tables), 1)
        self.assertEqual(result.cells[0].text, "DAT")
        self.assertEqual(result.cells[3].text, "CE-439790")
        self.assertEqual(len(result.cell_graphs), 1)
        self.assertTrue(result.cell_graphs[0].horizontal_edges)
        self.assertTrue(result.cell_graphs[0].vertical_edges)


if __name__ == "__main__":
    unittest.main()
