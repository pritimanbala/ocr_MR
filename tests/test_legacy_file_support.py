import unittest
from pathlib import Path

from ocr_extract import is_supported_document, is_thumbs_database


class LegacyFileSupportTests(unittest.TestCase):
    def test_extensionless_thumbs_file_is_supported(self):
        self.assertTrue(is_supported_document(Path("Thumbs")))
        self.assertTrue(is_thumbs_database(Path("Thumbs")))

    def test_thumbs_db_filename_is_supported(self):
        thumbs_db = Path("Thumbs.db")
        self.assertTrue(is_supported_document(thumbs_db))
        self.assertTrue(is_thumbs_database(thumbs_db))


if __name__ == "__main__":
    unittest.main()
