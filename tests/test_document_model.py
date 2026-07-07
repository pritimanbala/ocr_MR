import unittest

from engineering_di.models import BoundingBox, Document, Page
from engineering_di.pdf_parser import classify_line_orientation


class DocumentModelTests(unittest.TestCase):
    def test_bounding_box_metrics_and_serialization(self):
        bbox = BoundingBox(10, 20, 40, 65)
        page = Page(number=1, bbox=bbox, rotation=0)
        document = Document(source_path="sample.pdf", page_count=1, metadata={}, pages=[page])

        self.assertEqual(bbox.width, 30)
        self.assertEqual(bbox.height, 45)
        self.assertEqual(bbox.area, 1350)
        self.assertEqual(document.to_dict()["pages"][0]["bbox"], {"x0": 10, "y0": 20, "x1": 40, "y1": 65})

    def test_line_orientation_classification(self):
        self.assertEqual(classify_line_orientation((0, 10), (100, 10.5), tolerance=1.0), "horizontal")
        self.assertEqual(classify_line_orientation((10, 0), (10.5, 100), tolerance=1.0), "vertical")
        self.assertEqual(classify_line_orientation((0, 0), (100, 100), tolerance=1.0), "diagonal")


if __name__ == "__main__":
    unittest.main()
