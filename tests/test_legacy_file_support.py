import tempfile
import unittest
from pathlib import Path

from extract_folder import iter_supported_files
from ocr_extract import extract_document, is_supported_document, is_thumbs_database


class LegacyFileSupportTests(unittest.TestCase):
    def test_extensionless_thumbs_file_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            thumbs = root / "Thumbs"
            thumbs.write_bytes(b"not-a-real-ole-file")
            ignored = root / "random"
            ignored.write_text("ignored")

            self.assertTrue(is_supported_document(thumbs))
            self.assertTrue(is_thumbs_database(thumbs))
            self.assertFalse(is_supported_document(ignored))
            self.assertEqual(iter_supported_files(root), [thumbs])
            result = extract_document(thumbs)
            self.assertEqual(result["file_type"], "thumbs_database")
            self.assertEqual(result["size_bytes"], len(b"not-a-real-ole-file"))
            self.assertIn("database", result)

    def test_thumbs_db_filename_is_supported(self):
        thumbs_db = Path("Thumbs.db")
        self.assertTrue(is_supported_document(thumbs_db))
        self.assertTrue(is_thumbs_database(thumbs_db))


if __name__ == "__main__":
    unittest.main()
